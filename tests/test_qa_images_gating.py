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
