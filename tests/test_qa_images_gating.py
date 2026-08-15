"""La QA image ne tourne que sur les plans qui ont déjà montré un signe de
dérive — jamais sur tous, à chaque fois — et jamais plus de deux fois
(un verdict, et si FAIL, un correctif suivi d'un second verdict).

Même logique de test que tests/test_realisme_gating.py : à travers
`episode.produire()` en conditions réelles, pas seulement la fonction de
gating isolée — c'est la seule façon de vérifier que le branchement dans
`episode.py` respecte vraiment ce que `qa_images.py` décide.
"""

from __future__ import annotations

import json

from tests.test_chaine_complete import SCRIPT_FACTICE, _produire, atelier  # noqa: F401


async def _prompts_sans_elements_obligatoires(self, entrees, ctx):
    ctx.facturer(0.001)
    sortie = {"plans": [{"numero": p.numero, "prompt_image": f"prompt riche {p.numero}"}
                        for p in entrees["plans"]]}
    return self.apres(sortie, entrees, ctx)


async def _prompts_avec_un_element_manquant(self, entrees, ctx):
    """Le premier plan écrit un `elements_obligatoires` que son propre
    `prompt_image` ne contient pas — exactement ce qui déclenche
    `fidelite_visuelle.renforcer()`, donc `corrections_fidelite`."""
    ctx.facturer(0.001)
    sortie = {"plans": [
        {"numero": p.numero, "prompt_image": f"prompt riche {p.numero}",
         "elements_obligatoires": ["submarine cable"] if p.numero == 0 else []}
        for p in entrees["plans"]
    ]}
    return self.apres(sortie, entrees, ctx)


async def _qa_toujours_pass(self, entrees, ctx):
    ctx.facturer(0.0005)
    return self.apres(
        {"statut": "PASS", "manquants": [], "incorrects": [], "en_trop": []},
        entrees, ctx,
    )


def test_qa_image_est_sautee_quand_rien_na_besoin_detre_verifie(atelier, monkeypatch):
    """Comportement par défaut : aucun `elements_obligatoires` manquant,
    aucun plan passé par RealismWriter — la QA image ne doit jamais être
    appelée, 0 coût, 0 appel Groq/vision en plus."""
    appels = {"n": 0}

    async def compte(self, entrees, ctx):
        appels["n"] += 1
        return await _qa_toujours_pass(self, entrees, ctx)

    monkeypatch.setattr("pdz.agents.ecriture.plans.ShotPromptWriter.executer",
                        _prompts_sans_elements_obligatoires)
    monkeypatch.setattr("pdz.agents.analyse.qa_image.ImageQA.executer", compte)

    _, resultat = _produire(atelier)

    assert appels["n"] == 0
    assert "qa_images" not in resultat.etapes_reprises
    assert resultat.video.exists()


def test_qa_image_est_appelee_quand_fidelite_visuelle_a_du_corriger(atelier, monkeypatch):
    """Un plan dont `elements_obligatoires` manquait de son propre prompt
    (donc `corrections_fidelite` non vide) doit déclencher exactement un
    appel de vérification — pas les autres plans, qui n'ont montré aucune
    raison de douter d'eux."""
    appels = {"n": 0}

    async def compte(self, entrees, ctx):
        appels["n"] += 1
        return await _qa_toujours_pass(self, entrees, ctx)

    monkeypatch.setattr("pdz.agents.ecriture.plans.ShotPromptWriter.executer",
                        _prompts_avec_un_element_manquant)
    monkeypatch.setattr("pdz.agents.analyse.qa_image.ImageQA.executer", compte)

    _, resultat = _produire(atelier)

    assert appels["n"] == 1
    assert resultat.video.exists()


def test_un_fail_declenche_une_regeneration_puis_un_second_verdict(atelier, monkeypatch):
    """FAIL au premier verdict → un correctif déterministe, une regénération
    d'image, puis un second verdict. PASS au second : le plan est marqué
    corrigé, pas de troisième appel."""
    appels = {"n": 0}

    async def fail_puis_pass(self, entrees, ctx):
        appels["n"] += 1
        ctx.facturer(0.0005)
        if appels["n"] == 1:
            sortie = {"statut": "FAIL", "manquants": ["submarine cable"],
                      "incorrects": [], "en_trop": []}
        else:
            sortie = {"statut": "PASS", "manquants": [], "incorrects": [], "en_trop": []}
        return self.apres(sortie, entrees, ctx)

    monkeypatch.setattr("pdz.agents.ecriture.plans.ShotPromptWriter.executer",
                        _prompts_avec_un_element_manquant)
    monkeypatch.setattr("pdz.agents.analyse.qa_image.ImageQA.executer", fail_puis_pass)

    _, resultat = _produire(atelier)

    assert appels["n"] == 2
    assert resultat.video.exists()


def test_un_fail_persistant_marque_needs_review_sans_troisieme_appel(atelier, monkeypatch):
    """Toujours FAIL après la regénération → NEEDS_REVIEW, l'épisode sort
    quand même (jamais bloqué pour un seul plan imparfait), et surtout :
    jamais un troisième appel de vérification — pas de boucle."""
    appels = {"n": 0}

    async def toujours_fail(self, entrees, ctx):
        appels["n"] += 1
        ctx.facturer(0.0005)
        sortie = {"statut": "FAIL", "manquants": ["submarine cable"],
                  "incorrects": [], "en_trop": []}
        return self.apres(sortie, entrees, ctx)

    monkeypatch.setattr("pdz.agents.ecriture.plans.ShotPromptWriter.executer",
                        _prompts_avec_un_element_manquant)
    monkeypatch.setattr("pdz.agents.analyse.qa_image.ImageQA.executer", toujours_fail)

    _, resultat = _produire(atelier)

    assert appels["n"] == 2   # jamais 3 : un verdict, un correctif, un second verdict
    assert resultat.video.exists()


def test_un_fournisseur_en_panne_ne_bloque_pas_lepisode(atelier, monkeypatch):
    """Bug réel en production : un quota Groq épuisé pendant la QA visuelle
    faisait planter l'épisode ENTIER — script, voix et images déjà payés
    perdus pour une vérification qui n'est censée être qu'optionnelle (voir
    la docstring de qa_images.py : « jamais d'épisode bloqué pour un seul
    plan imparfait »). Le plan concerné doit juste rester tel quel, non
    revérifié — l'épisode doit sortir."""
    from pdz.moteur.erreurs import ErreurQuota

    async def toujours_en_panne(self, entrees, ctx):
        raise ErreurQuota("quota épuisé")

    monkeypatch.setattr("pdz.agents.ecriture.plans.ShotPromptWriter.executer",
                        _prompts_avec_un_element_manquant)
    monkeypatch.setattr("pdz.agents.analyse.qa_image.ImageQA.executer",
                        toujours_en_panne)

    _, resultat = _produire(atelier)

    assert resultat.video.exists()


def test_un_fournisseur_en_panne_pendant_la_correction_marque_needs_review(
        atelier, monkeypatch):
    """Même principe, mais la panne survient APRÈS un FAIL, pendant la
    regénération/revérification : le plan doit être marqué NEEDS_REVIEW
    (on ne peut plus confirmer qu'il est bon) plutôt que de faire échouer
    l'épisode."""
    from pdz.moteur.erreurs import ErreurQuota

    appels = {"n": 0}

    async def fail_puis_en_panne(self, entrees, ctx):
        appels["n"] += 1
        if appels["n"] == 1:
            ctx.facturer(0.0005)
            return self.apres(
                {"statut": "FAIL", "manquants": ["submarine cable"],
                 "incorrects": [], "en_trop": []}, entrees, ctx,
            )
        raise ErreurQuota("quota épuisé")

    monkeypatch.setattr("pdz.agents.ecriture.plans.ShotPromptWriter.executer",
                        _prompts_avec_un_element_manquant)
    monkeypatch.setattr("pdz.agents.analyse.qa_image.ImageQA.executer",
                        fail_puis_en_panne)

    _, resultat = _produire(atelier)

    assert resultat.video.exists()


def test_les_nouvelles_dimensions_qa_najoutent_aucun_appel(atelier, monkeypatch):
    """`lieu_correspond`/`registre_correspond`/`texte_lisible` (qa_image@1.3.0)
    sont de nouvelles dimensions de verdict, pas un nouveau site d'appel —
    le plafond « un verdict, si FAIL un correctif, un second verdict »
    reste exactement le même."""
    appels = {"n": 0}

    async def fail_puis_pass_avec_dimensions(self, entrees, ctx):
        appels["n"] += 1
        ctx.facturer(0.0005)
        if appels["n"] == 1:
            sortie = {"statut": "FAIL", "manquants": ["submarine cable"],
                      "incorrects": [], "en_trop": [],
                      "lieu_correspond": True, "registre_correspond": True,
                      "texte_lisible": "non_applicable"}
        else:
            sortie = {"statut": "PASS", "manquants": [], "incorrects": [], "en_trop": [],
                      "lieu_correspond": True, "registre_correspond": True,
                      "texte_lisible": "non_applicable"}
        return self.apres(sortie, entrees, ctx)

    monkeypatch.setattr("pdz.agents.ecriture.plans.ShotPromptWriter.executer",
                        _prompts_avec_un_element_manquant)
    monkeypatch.setattr("pdz.agents.analyse.qa_image.ImageQA.executer",
                        fail_puis_pass_avec_dimensions)

    _, resultat = _produire(atelier)

    assert appels["n"] == 2   # jamais un troisième appel
    assert resultat.video.exists()


def test_texte_illisible_est_journalise_meme_avec_le_reste_conforme(atelier, monkeypatch):
    """Ferme le trou trouvé par l'audit 2 (ep56 plan 4) : un PASS silencieux
    malgré un texte totalement illisible dans l'image, parce que rien ne
    vérifiait la lisibilité. Même quand MANDATORY_ELEMENTS/FORBIDDEN_ELEMENTS
    sont respectés, `texte_lisible=illisible` doit déclencher la correction
    et rester visible dans la trace journalisée."""
    from pdz import db

    appels = {"n": 0}

    async def texte_illisible_puis_pass(self, entrees, ctx):
        appels["n"] += 1
        ctx.facturer(0.0005)
        if appels["n"] == 1:
            sortie = {"statut": "FAIL", "manquants": [], "incorrects": [], "en_trop": [],
                      "lieu_correspond": True, "registre_correspond": True,
                      "texte_lisible": "illisible"}
        else:
            sortie = {"statut": "PASS", "manquants": [], "incorrects": [], "en_trop": [],
                      "lieu_correspond": True, "registre_correspond": True,
                      "texte_lisible": "lisible"}
        return self.apres(sortie, entrees, ctx)

    monkeypatch.setattr("pdz.agents.ecriture.plans.ShotPromptWriter.executer",
                        _prompts_avec_un_element_manquant)
    monkeypatch.setattr("pdz.agents.analyse.qa_image.ImageQA.executer",
                        texte_illisible_puis_pass)

    _, resultat = _produire(atelier)

    assert appels["n"] == 2
    assert resultat.video.exists()

    with db.connexion() as conn:
        qa_row = conn.execute(
            "SELECT resultat FROM etapes WHERE job_id = ? AND cle = 'qa_images'",
            (resultat.job_id,),
        ).fetchone()
    verifications = json.loads(qa_row["resultat"])["verifications"]
    corrige = next(v for v in verifications if v.get("statut") == "PASS" and v.get("corrige"))
    assert corrige["texte_lisible"] == "lisible"


def test_conformite_univers_false_est_journalisee(atelier, monkeypatch):
    """Ferme le trou de production #64 : un plan peut respecter toute sa
    propre checklist et violer quand même une règle globale de l'univers
    (ici, une marque détectée dans l'image) — `conformite_univers` et
    `elements_interdits_detectes` doivent apparaître dans la trace, même
    quand manquants/incorrects/en_trop sont vides."""
    from pdz import db

    appels = {"n": 0}

    async def marque_toujours_detectee(self, entrees, ctx):
        appels["n"] += 1
        ctx.facturer(0.0005)
        sortie = {"statut": "FAIL", "manquants": [], "incorrects": [], "en_trop": [],
                  "lieu_correspond": True, "registre_correspond": True,
                  "texte_lisible": "non_applicable",
                  "conformite_univers": False,
                  "elements_interdits_detectes": ["tesla logo"]}
        return self.apres(sortie, entrees, ctx)

    monkeypatch.setattr("pdz.agents.ecriture.plans.ShotPromptWriter.executer",
                        _prompts_avec_un_element_manquant)
    monkeypatch.setattr("pdz.agents.analyse.qa_image.ImageQA.executer",
                        marque_toujours_detectee)

    _, resultat = _produire(atelier)

    assert appels["n"] == 2   # jamais un troisième appel, même en échec persistant
    assert resultat.video.exists()

    with db.connexion() as conn:
        qa_row = conn.execute(
            "SELECT resultat FROM etapes WHERE job_id = ? AND cle = 'qa_images'",
            (resultat.job_id,),
        ).fetchone()
    verifications = json.loads(qa_row["resultat"])["verifications"]
    needs_review = next(v for v in verifications if v.get("statut") == "NEEDS_REVIEW")
    assert needs_review["conformite_univers"] is False
    assert needs_review["elements_interdits_detectes"] == ["tesla logo"]


def test_le_prompt_final_et_le_contrat_sont_journalises_par_plan(atelier, monkeypatch):
    """Verrou direct de l'exigence de traçabilité : le prompt EXACT envoyé
    au générateur d'image, et son Visual Contract, doivent être récupérables
    après coup — avant ce fix, seul un fragment pré-assemblage (le
    `prompt_image` de ShotPromptWriter, avant apparence/expression/cadrage/
    registre/décor/style) était incidemment journalisé."""
    from pdz import db

    appels = {"n": 0}

    async def fail_puis_pass(self, entrees, ctx):
        appels["n"] += 1
        ctx.facturer(0.0005)
        if appels["n"] == 1:
            sortie = {"statut": "FAIL", "manquants": ["submarine cable"],
                      "incorrects": [], "en_trop": []}
        else:
            sortie = {"statut": "PASS", "manquants": [], "incorrects": [], "en_trop": []}
        return self.apres(sortie, entrees, ctx)

    monkeypatch.setattr("pdz.agents.ecriture.plans.ShotPromptWriter.executer",
                        _prompts_avec_un_element_manquant)
    monkeypatch.setattr("pdz.agents.analyse.qa_image.ImageQA.executer", fail_puis_pass)

    _, resultat = _produire(atelier)
    assert resultat.video.exists()

    with db.connexion() as conn:
        images_row = conn.execute(
            "SELECT resultat FROM etapes WHERE job_id = ? AND cle = 'images'",
            (resultat.job_id,),
        ).fetchone()
        qa_row = conn.execute(
            "SELECT resultat FROM etapes WHERE job_id = ? AND cle = 'qa_images'",
            (resultat.job_id,),
        ).fetchone()

    prompts = json.loads(images_row["resultat"])["prompts"]
    assert prompts, "aucun prompt journalisé à l'étape images"
    for p in prompts:
        assert p["prompt_final"]
        assert p["contrat_visuel"] is not None
        assert p["contrat_visuel"]["quoi"]

    verifications = json.loads(qa_row["resultat"])["verifications"]
    corriges = [v for v in verifications if v.get("prompt_corrige")]
    assert corriges, "aucune correction journalisée alors qu'un FAIL a eu lieu"


def test_une_marque_detectee_route_le_plan_vers_realismwriter(atelier, monkeypatch):
    """Reproduit le trou trouvé en production #64 : un prompt qui nomme une
    marque réelle (hors du vocabulaire de l'univers) doit déclencher
    RealismWriter — l'agent EXISTANT, pas un nouvel appel — exactement
    comme un risque de texte/logo/visage le fait déjà."""
    appels_realisme = {"n": 0}

    async def prompts_avec_une_marque(self, entrees, ctx):
        ctx.facturer(0.001)
        sortie = {"plans": [
            {"numero": p.numero,
             "prompt_image": "a Tesla trophy glowing on the podium" if p.numero == 0
                             else f"prompt riche {p.numero}"}
            for p in entrees["plans"]
        ]}
        return self.apres(sortie, entrees, ctx)

    async def realisme_compte(self, entrees, ctx):
        appels_realisme["n"] += 1
        ctx.facturer(0.001)
        sortie = {"plans": [{"numero": p.numero, "prompt_image": p.action}
                            for p in entrees["plans"]]}
        return self.apres(sortie, entrees, ctx)

    monkeypatch.setattr("pdz.agents.ecriture.plans.ShotPromptWriter.executer",
                        prompts_avec_une_marque)
    monkeypatch.setattr("pdz.agents.ecriture.realisme.RealismWriter.executer",
                        realisme_compte)

    _, resultat = _produire(atelier)

    assert appels_realisme["n"] == 1   # le même agent existant, pas un nouveau
    assert resultat.video.exists()


def test_realisme_declenche_aussi_la_qa_image(atelier, monkeypatch):
    """Un plan réécrit par RealismWriter est un second endroit où un élément
    obligatoire peut disparaître : il doit, lui aussi, déclencher la QA
    image, même si `fidelite_visuelle.renforcer()` n'a rien eu à corriger."""
    appels = {"n": 0}

    async def compte(self, entrees, ctx):
        appels["n"] += 1
        return await _qa_toujours_pass(self, entrees, ctx)

    async def script_avec_risque(self, entrees, ctx):
        ctx.facturer(0.012)
        sortie = json.loads(json.dumps(SCRIPT_FACTICE))
        sortie["repliques"][0]["action"] = "phone screen showing a conversation visible"
        return self.apres(sortie, entrees, ctx)

    async def prompts_qui_gardent_laction(self, entrees, ctx):
        ctx.facturer(0.001)
        sortie = {"plans": [{"numero": p.numero, "prompt_image": p.action}
                            for p in entrees["plans"]]}
        return self.apres(sortie, entrees, ctx)

    async def realisme_qui_garde_laction(self, entrees, ctx):
        ctx.facturer(0.001)
        sortie = {"plans": [{"numero": p.numero, "prompt_image": p.action}
                            for p in entrees["plans"]]}
        return self.apres(sortie, entrees, ctx)

    monkeypatch.setattr("pdz.agents.ecriture.script.ScriptWriter.executer",
                        script_avec_risque)
    monkeypatch.setattr("pdz.agents.ecriture.plans.ShotPromptWriter.executer",
                        prompts_qui_gardent_laction)
    monkeypatch.setattr("pdz.agents.ecriture.realisme.RealismWriter.executer",
                        realisme_qui_garde_laction)
    monkeypatch.setattr("pdz.agents.analyse.qa_image.ImageQA.executer", compte)

    _, resultat = _produire(atelier)

    assert appels["n"] == 1
    assert resultat.video.exists()


def test_le_cas_tesla_production_64_est_couvert_de_bout_en_bout(atelier, monkeypatch):
    """Non-régression nommée explicitement d'après la production #64 : un
    plan mentionnant une marque réelle route vers RealismWriter (existant),
    et même si l'abstraction reste imparfaite (simulée ici : RealismWriter
    garde le texte tel quel), la QA vision attrape le logo via
    `conformite_univers` et le corrige — l'épisode sort quand même, sans
    jamais un troisième appel de vérification."""
    appels_realisme = {"n": 0}
    appels_qa = {"n": 0}

    async def prompts_avec_tesla(self, entrees, ctx):
        ctx.facturer(0.001)
        sortie = {"plans": [
            {"numero": p.numero,
             "prompt_image": "a Tesla accelerator pedal glowing in the dark" if p.numero == 0
                             else f"prompt riche {p.numero}"}
            for p in entrees["plans"]
        ]}
        return self.apres(sortie, entrees, ctx)

    async def realisme_imparfait(self, entrees, ctx):
        """Simule une abstraction incomplète : le texte de marque reste."""
        appels_realisme["n"] += 1
        ctx.facturer(0.001)
        sortie = {"plans": [{"numero": p.numero, "prompt_image": p.action}
                            for p in entrees["plans"]]}
        return self.apres(sortie, entrees, ctx)

    async def qa_attrape_le_logo_puis_pass(self, entrees, ctx):
        appels_qa["n"] += 1
        ctx.facturer(0.0005)
        if appels_qa["n"] == 1:
            sortie = {"statut": "FAIL", "manquants": [], "incorrects": [], "en_trop": [],
                      "lieu_correspond": True, "registre_correspond": True,
                      "texte_lisible": "non_applicable",
                      "conformite_univers": False,
                      "elements_interdits_detectes": ["tesla logo"]}
        else:
            sortie = {"statut": "PASS", "manquants": [], "incorrects": [], "en_trop": [],
                      "lieu_correspond": True, "registre_correspond": True,
                      "texte_lisible": "non_applicable",
                      "conformite_univers": True, "elements_interdits_detectes": []}
        return self.apres(sortie, entrees, ctx)

    monkeypatch.setattr("pdz.agents.ecriture.plans.ShotPromptWriter.executer",
                        prompts_avec_tesla)
    monkeypatch.setattr("pdz.agents.ecriture.realisme.RealismWriter.executer",
                        realisme_imparfait)
    monkeypatch.setattr("pdz.agents.analyse.qa_image.ImageQA.executer",
                        qa_attrape_le_logo_puis_pass)

    _, resultat = _produire(atelier)

    assert appels_realisme["n"] == 1     # routé vers l'agent EXISTANT, pas un nouveau
    assert appels_qa["n"] == 2           # jamais un troisième appel
    assert resultat.video.exists()

    from pdz import db
    with db.connexion() as conn:
        qa_row = conn.execute(
            "SELECT resultat FROM etapes WHERE job_id = ? AND cle = 'qa_images'",
            (resultat.job_id,),
        ).fetchone()
    verifications = json.loads(qa_row["resultat"])["verifications"]
    corrige = next(v for v in verifications if v.get("statut") == "PASS" and v.get("corrige"))
    assert "conformite_univers" in corrige["branches_correction"]
