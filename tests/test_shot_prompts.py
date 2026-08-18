"""ShotPromptWriter : le prompt d'image, écrit séparément du dialogue,
APRÈS le découpage en plans.

ScriptWriter écrit `action` en même temps que le dialogue — une phrase
sommaire, pas un cadrage. Le découpage transforme les répliques en plans, et
un plan de réaction (« celui qui écoute ») n'existe qu'à cette étape-là — il
ne recevait donc jamais de prompt écrit pour lui avant cette version. Cet
agent reprend le storyboard déjà découpé et écrit, pour chaque plan, un
prompt d'image digne d'un directeur de la photographie (cadrage, netteté),
qui remplace `action` avant la génération d'image.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pdz.agents.ecriture.plans import ShotPromptWriter
from pdz.moteur.erreurs import ErreurValidation
from pdz.moteur.pipeline import Contexte
from pdz.production.storyboard import PlanScript
from pdz.prompts import charger
from pdz.univers import Univers

FRUITS = Path("univers/fruit-island.yaml")


def _contexte():
    return Contexte(job_id="j", etape_cle="shot_prompts", profil="equilibre",
                    budget_restant=0.60)


def _repliques(n=3):
    return [
        {"numero": i + 1, "personnage": "strawberina", "replique": f"réplique {i + 1}"}
        for i in range(n)
    ]


def _plans(n=3, avec_reaction=False):
    plans = [
        PlanScript(numero=i, replique_numero=i + 1, personnage="strawberina",
                   action="action minimale", emotion="calme",
                   fonction="établit l'échelle du monde")
        for i in range(n)
    ]
    if avec_reaction:
        plans.append(PlanScript(numero=n, replique_numero=n, personnage="bananito",
                                action="reacting to what strawberina just said, listening",
                                emotion="surprise", reaction=True,
                                fonction="réaction : établit l'échelle du monde"))
    return plans


def test_les_variables_reprennent_chaque_plan_avec_sa_replique():
    u = Univers.charger(FRUITS)
    v = ShotPromptWriter().variables(
        {"univers": u, "plans": _plans(3), "repliques": _repliques(3)}, _contexte())
    assert len(v["plans"]) == 3
    assert v["plans"][0]["fonction_plan"] == "établit l'échelle du monde"
    assert v["plans"][0]["replique"] == "réplique 1"
    assert v["contexte_univers"] == u.contexte_script()


def test_le_premier_plan_est_toujours_une_nouvelle_scene():
    u = Univers.charger(FRUITS)
    v = ShotPromptWriter().variables(
        {"univers": u, "plans": _plans(3), "repliques": _repliques(3)}, _contexte())
    assert v["plans"][0]["nouvelle_scene"] is True


def test_un_changement_de_decor_marque_une_nouvelle_scene():
    from dataclasses import replace

    u = Univers.charger(FRUITS)
    plans = _plans(3)
    plans[0] = replace(plans[0], decor="villa")
    plans[1] = replace(plans[1], decor="villa")
    plans[2] = replace(plans[2], decor="ceremonie")
    v = ShotPromptWriter().variables(
        {"univers": u, "plans": plans, "repliques": _repliques(3)}, _contexte())
    assert v["plans"][1]["nouvelle_scene"] is False
    assert v["plans"][2]["nouvelle_scene"] is True


def test_les_variables_portent_le_format_de_lunivers():
    """La règle « personne n'est jamais visible » (plans@1.6.0) ne
    s'applique qu'en narration — il faut donc savoir si l'univers est
    animé ou non pour l'activer conditionnellement."""
    u = Univers.charger(FRUITS)
    v = ShotPromptWriter().variables(
        {"univers": u, "plans": _plans(3), "repliques": _repliques(3)}, _contexte())
    assert v["anime"] == u.anime


def test_le_dernier_plan_est_marque_comme_tel():
    """Nécessaire pour cibler UNIQUEMENT ce plan avec la consigne de
    bouclage — voir plans@1.8.0 et l'audit data-flow : `derniere_image`."""
    u = Univers.charger(FRUITS)
    v = ShotPromptWriter().variables(
        {"univers": u, "plans": _plans(3), "repliques": _repliques(3)}, _contexte())
    assert v["plans"][-1]["dernier"] is True
    assert v["plans"][0]["dernier"] is False


def test_derniere_image_passe_dans_les_variables():
    """`derniere_image` est déjà écrit par ScriptWriter à chaque script
    (CONTRAINTE ABSOLUE #7) mais n'atteignait jamais cet agent — voir
    l'audit data-flow, dead metadata totale."""
    u = Univers.charger(FRUITS)
    v = ShotPromptWriter().variables(
        {"univers": u, "plans": _plans(3), "repliques": _repliques(3),
         "derniere_image": "le plan revient sur la même ville, vue de plus haut"},
        _contexte(),
    )
    assert v["derniere_image"] == "le plan revient sur la même ville, vue de plus haut"


def test_sans_derniere_image_les_variables_retombent_sur_une_chaine_vide():
    """Non-régression : un appelant qui n'a pas encore ce champ (job en
    cache d'avant plans@1.8.0) ne doit pas planter."""
    u = Univers.charger(FRUITS)
    v = ShotPromptWriter().variables(
        {"univers": u, "plans": _plans(3), "repliques": _repliques(3)}, _contexte())
    assert v["derniere_image"] == ""


def test_un_plan_de_reaction_est_marque_comme_tel():
    u = Univers.charger(FRUITS)
    v = ShotPromptWriter().variables(
        {"univers": u, "plans": _plans(3, avec_reaction=True), "repliques": _repliques(3)},
        _contexte(),
    )
    assert v["plans"][-1]["reaction"] is True
    assert v["plans"][0]["reaction"] is False


def test_le_schema_impose_un_prompt_par_plan_reaction_comprise():
    u = Univers.charger(FRUITS)
    base = charger("ecriture/plans").schema_sortie
    plans = _plans(3, avec_reaction=True)
    schema = ShotPromptWriter().schema(base, {"univers": u, "plans": plans}, _contexte())
    assert schema["properties"]["plans"]["minItems"] == 4


def test_des_prompts_manquants_sont_refuses():
    entrees = {"univers": None, "plans": _plans(3)}
    sortie = {"plans": [{"numero": 0, "prompt_image": "x"}, {"numero": 1, "prompt_image": "y"}]}
    with pytest.raises(ErreurValidation) as e:
        ShotPromptWriter().apres(sortie, entrees, _contexte())
    assert "2" in str(e.value)


def test_des_prompts_complets_passent():
    entrees = {"univers": None, "plans": _plans(3)}
    sortie = {"plans": [{"numero": i, "prompt_image": f"prompt {i}"} for i in (0, 1, 2)]}
    resultat = ShotPromptWriter().apres(sortie, entrees, _contexte())
    assert len(resultat["plans"]) == 3


def test_fusionner_remplace_laction_par_le_prompt_riche():
    plans = _plans(2)
    sortie = {"plans": [
        {"numero": 0, "prompt_image": "gros plan sur son visage inquiet"},
        {"numero": 1, "prompt_image": "plan large, elle traverse la pièce"},
    ]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    assert fusionnes[0].action == "gros plan sur son visage inquiet"
    assert fusionnes[1].action == "plan large, elle traverse la pièce"
    # Le reste du plan (fonction, émotion...) n'est pas touché.
    assert fusionnes[0].fonction == "établit l'échelle du monde"
    assert fusionnes[0].emotion == "calme"


def test_fusionner_couvre_aussi_les_plans_de_reaction():
    plans = _plans(2, avec_reaction=True)
    sortie = {"plans": [
        {"numero": 0, "prompt_image": "gros plan sur son visage inquiet"},
        {"numero": 1, "prompt_image": "plan large, elle traverse la pièce"},
        {"numero": 2, "prompt_image": "gros plan sur son visage, surpris, figé"},
    ]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    plan_reaction = next(p for p in fusionnes if p.reaction)
    assert plan_reaction.action == "gros plan sur son visage, surpris, figé"


def test_fusionner_garde_laction_dorigine_si_un_numero_manque():
    """`apres()` refuse normalement les manques avant d'arriver ici — ce
    test couvre l'appelant qui, par erreur, sauterait la validation."""
    plans = _plans(2)
    sortie = {"plans": [{"numero": 0, "prompt_image": "gros plan sur son visage"}]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    assert fusionnes[0].action == "gros plan sur son visage"
    assert fusionnes[1].action == "action minimale"


def test_les_plans_dorigine_ne_sont_pas_mutes():
    plans = _plans(1)
    sortie = {"plans": [{"numero": 0, "prompt_image": "nouveau prompt"}]}
    ShotPromptWriter().fusionner(plans, sortie)
    assert plans[0].action == "action minimale"


def test_fusionner_reprend_aussi_le_cadrage():
    plans = _plans(2)
    sortie = {"plans": [
        {"numero": 0, "prompt_image": "x", "cadrage": "gros_plan"},
        {"numero": 1, "prompt_image": "y", "cadrage": "plan_large"},
    ]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    assert fusionnes[0].cadrage == "gros_plan"
    assert fusionnes[1].cadrage == "plan_large"


def test_fusionner_sans_cadrage_garde_celui_dorigine():
    """Non-régression : un job en cache d'avant plans@1.2.0 n'a pas de
    `cadrage` dans sa sortie stockée — ne doit pas planter."""
    plans = _plans(1)
    sortie = {"plans": [{"numero": 0, "prompt_image": "x"}]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    assert fusionnes[0].cadrage == ""


def test_fusionner_reprend_aussi_le_registre_visuel():
    plans = _plans(1)
    sortie = {"plans": [{
        "numero": 0, "prompt_image": "x",
        "registre_visuel": "abstract wireframe, not a realistic map",
    }]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    assert fusionnes[0].registre_visuel == "abstract wireframe, not a realistic map"


def test_fusionner_sans_registre_visuel_garde_celui_dorigine():
    """Non-régression : un job en cache d'avant plans@1.7.0 n'a pas de
    `registre_visuel` dans sa sortie stockée — ne doit pas planter."""
    plans = _plans(1)
    sortie = {"plans": [{"numero": 0, "prompt_image": "x"}]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    assert fusionnes[0].registre_visuel == ""


def test_fusionner_reprend_aussi_les_elements_secondaires():
    plans = _plans(1)
    sortie = {"plans": [{
        "numero": 0, "prompt_image": "x", "elements_secondaires": ["orange cable"],
    }]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    assert fusionnes[0].elements_secondaires == ["orange cable"]


def test_elements_secondaires_sont_optionnels_et_narrivent_jamais_a_null():
    """Non-régression : un job en cache d'avant plans@1.10.0 n'a pas
    `elements_secondaires` dans sa sortie stockée — ne doit pas planter,
    et ne doit jamais devenir None."""
    plans = _plans(1)
    sortie = {"plans": [{"numero": 0, "prompt_image": "x"}]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    assert fusionnes[0].elements_secondaires == []


def test_apres_ne_leve_jamais_pour_un_cadrage_repete(caplog):
    """Diagnostic seulement (voir cadrage.py) : deux plans consécutifs avec
    le même cadrage ne doivent jamais faire échouer la validation — ça
    ajouterait une relance, donc un appel Groq de plus."""
    import logging

    entrees = {"univers": None, "plans": _plans(2)}
    sortie = {"plans": [
        {"numero": 0, "prompt_image": "x", "cadrage": "gros_plan"},
        {"numero": 1, "prompt_image": "y", "cadrage": "gros_plan"},
    ]}
    with caplog.at_level(logging.INFO):
        resultat = ShotPromptWriter().apres(sortie, entrees, _contexte())
    assert len(resultat["plans"]) == 2
    assert any("même cadrage" in m for m in caplog.messages)


def test_la_signature_reference_le_prompt_actif():
    sig = ShotPromptWriter().signature()
    assert sig["agent"] == "shot_prompts"
    assert sig["prompt"] == charger("ecriture/plans").ref


# ── Bouclage : `derniere_image` (plans@1.8.0) ────────────────────────────

def test_le_prompt_actif_relaie_la_consigne_de_bouclage_au_dernier_plan():
    """Le champ existe déjà côté script (CONTRAINTE ABSOLUE #7) ; ce test
    vérifie que le PROMPT réellement envoyé au modèle relaie bien cette
    description, et seulement pour le plan marqué comme le dernier."""
    p = charger("ecriture/plans")
    u = Univers.charger(FRUITS)
    stable, _, message = p.rendre(
        contexte_univers=u.contexte_script(), anime=u.anime,
        derniere_image="le plan revient sur la ville, vue de plus haut",
        plans=[
            {"numero": 0, "personnage": "strawberina", "replique": "r1",
             "reaction": False, "action": "a", "fonction_plan": "",
             "nouvelle_scene": True, "dernier": False},
            {"numero": 1, "personnage": "strawberina", "replique": "r2",
             "reaction": False, "action": "b", "fonction_plan": "",
             "nouvelle_scene": False, "dernier": True},
        ],
    )
    assert "le plan revient sur la ville, vue de plus haut" in stable
    assert "(dernier plan)" in message


def test_le_prompt_actif_exige_langlais_pour_prompt_image():
    """Audit data-flow SCRIPT → PROMPT → IMAGE : `prompt_image` n'avait
    jamais eu de consigne de langue, alors que `elements_obligatoires`,
    `elements_a_exclure` et `registre_visuel` l'ont explicitement depuis
    leur ajout — et que `style.rendu`/les décors/`consignes_image` de
    chaque univers le sont déjà tous. Un `prompt_image` en français mêlé
    aux morceaux anglais du prompt final est un risque de dérive/texte
    illisible mesuré sur un épisode réel (audit épisode #56)."""
    p = charger("ecriture/plans")
    assert "anglais" in p.systeme_stable.lower()
    description = p.schema_sortie["properties"]["plans"]["items"]["properties"][
        "prompt_image"]["description"]
    assert "anglais" in description.lower()


def test_sans_derniere_image_le_prompt_ne_mentionne_aucun_bouclage():
    """Entrée optionnelle : la majorité des reprises n'ont rien à dire sur
    le bouclage, et `.rendre()` ne doit ni planter ni ajouter de section
    vide au prompt envoyé."""
    p = charger("ecriture/plans")
    u = Univers.charger(FRUITS)
    stable, _, _ = p.rendre(
        contexte_univers=u.contexte_script(), anime=u.anime,
        plans=[{"numero": 0, "personnage": "strawberina", "replique": "r1",
                "reaction": False, "action": "a", "fonction_plan": "",
                "nouvelle_scene": True, "dernier": True}],
    )
    assert "### BOUCLAGE" not in stable


# ── Fidélité visuelle : les éléments nommés par la réplique ─────────────

def test_fusionner_rajoute_un_element_obligatoire_manquant():
    plans = _plans(1)
    sortie = {"plans": [{
        "numero": 0, "prompt_image": "a generic glowing hologram",
        "elements_obligatoires": ["submarine cable"],
    }]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    assert "submarine cable" in fusionnes[0].action


def test_fusionner_ne_touche_pas_un_prompt_qui_montre_deja_lelement():
    plans = _plans(1)
    sortie = {"plans": [{
        "numero": 0, "prompt_image": "a glowing submarine cable under the ocean",
        "elements_obligatoires": ["submarine cable"],
    }]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    assert fusionnes[0].action == "a glowing submarine cable under the ocean"


def test_fusionner_sans_elements_obligatoires_garde_le_prompt_tel_quel():
    """Non-régression : un job en cache d'avant plans@1.4.0 n'a pas ce champ
    dans sa sortie stockée — ne doit pas planter."""
    plans = _plans(1)
    sortie = {"plans": [{"numero": 0, "prompt_image": "x"}]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    assert fusionnes[0].action == "x"


def test_fusionner_applique_les_elements_a_exclure():
    plans = _plans(1)
    sortie = {"plans": [{
        "numero": 0, "prompt_image": "a wide shot of a city",
        "elements_a_exclure": ["smartphone", "human"],
    }]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    assert fusionnes[0].action == "a wide shot of a city, no smartphone, no human"


def test_fusionner_combine_renfort_et_exclusion():
    plans = _plans(1)
    sortie = {"plans": [{
        "numero": 0, "prompt_image": "a generic glowing hologram",
        "elements_obligatoires": ["submarine cable"],
        "elements_a_exclure": ["smartphone"],
    }]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    assert fusionnes[0].action == (
        "a generic glowing hologram, featuring submarine cable, no smartphone"
    )


# ── Checklist persistée : QA image (pdz/production/qa_images.py) en a besoin ─

def test_fusionner_garde_la_checklist_complete_sur_le_plan():
    """`elements_obligatoires`/`elements_a_exclure` doivent survivre au-delà
    de la fusion (pas seulement servir à corriger le texte du prompt) : la
    QA image, plus tard dans le pipeline, doit encore savoir ce qui était
    attendu sur CE plan précis."""
    plans = _plans(1)
    sortie = {"plans": [{
        "numero": 0, "prompt_image": "a wide shot of a city",
        "elements_obligatoires": ["submarine cable", "city"],
        "elements_a_exclure": ["smartphone"],
    }]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    assert fusionnes[0].elements_obligatoires == ["submarine cable", "city"]
    assert fusionnes[0].elements_a_exclure == ["smartphone"]


def test_fusionner_marque_corrections_fidelite_seulement_si_ca_a_manque():
    plans = _plans(2)
    sortie = {"plans": [
        {"numero": 0, "prompt_image": "a submarine cable under the ocean",
         "elements_obligatoires": ["submarine cable"]},
        {"numero": 1, "prompt_image": "a generic glowing hologram",
         "elements_obligatoires": ["submarine cable"]},
    ]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    assert fusionnes[0].corrections_fidelite == []
    assert fusionnes[1].corrections_fidelite == ["submarine cable"]


# ── ShotPromptWriter comme Visual Director : relations/abstractions/
# risques_predits/disposition, tous écrits dans le même appel, tous
# réellement consommés dans le prompt par fusionner() (voir le plan) ──────

def test_abstraction_remplace_le_concept_risque_par_sa_representation():
    """Cas Tesla / pédale d'accélérateur : le concept, s'il apparaît tel
    quel dans le prompt, est remplacé — jamais laissé à côté de son
    substitut."""
    plans = _plans(1)
    sortie = {"plans": [{
        "numero": 0, "prompt_image": "a Tesla accelerator pedal glowing in the dark",
        "abstractions": [{"concept": "Tesla", "representation": "generic unbranded vehicle component"}],
    }]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    assert "Tesla" not in fusionnes[0].action
    assert "generic unbranded vehicle component" in fusionnes[0].action


def test_abstraction_est_ajoutee_meme_si_le_concept_nest_pas_dans_le_prompt():
    """Défense en profondeur (voir le plan §6) : le concept peut avoir
    disparu du texte final sans que sa representation ait été écrite."""
    plans = _plans(1)
    sortie = {"plans": [{
        "numero": 0, "prompt_image": "an accelerator pedal glowing in the dark",
        "abstractions": [{"concept": "Tesla", "representation": "generic unbranded vehicle component"}],
    }]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    assert "generic unbranded vehicle component" in fusionnes[0].action


def test_mere_smartphone_message_relation_ajoute_letat_pas_seulement_lobjet():
    """Cas mère / smartphone / message : `relations` doit contribuer une
    vraie formulation d'état, pas juste le nom nu de l'objet."""
    plans = _plans(1)
    sortie = {"plans": [{
        "numero": 0, "prompt_image": "a mother in her kitchen",
        "elements_obligatoires": ["smartphone"],
        "relations": [{"cible": "smartphone", "etat": "held up, screen visible"}],
    }]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    assert "smartphone held up, screen visible" in fusionnes[0].action


def test_cables_sous_marins_le_registre_visuel_ecarte_map():
    """Cas câbles sous-marins : le contrôle de contradiction déjà prévu
    (registre_visuel explicite) est repris tel quel — aucune régression."""
    plans = _plans(1)
    sortie = {"plans": [{
        "numero": 0, "prompt_image": "glowing data pulses along a submarine cable",
        "registre_visuel": "abstract wireframe, not a realistic map",
    }]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    assert fusionnes[0].registre_visuel == "abstract wireframe, not a realistic map"
    assert "map" not in fusionnes[0].action.lower()


def test_interaction_humaine_avec_interface_ajoute_la_mitigation():
    """Cas interaction humaine avec une interface : `risques_predits` doit
    injecter la mitigation, pas seulement journaliser le risque."""
    plans = _plans(1)
    sortie = {"plans": [{
        "numero": 0, "prompt_image": "a finger taps a glowing interface",
        "risques_predits": [{"risque": "human hand",
                            "mitigation": "mechanical actuator only, no visible human hand"}],
    }]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    assert "mechanical actuator only, no visible human hand" in fusionnes[0].action


def test_wireframe_technique_la_disposition_rejoint_le_registre_visuel_pas_laction():
    """Cas wireframe technique : `disposition` est un vocabulaire fixe
    replié dans `registre_visuel`, jamais injecté directement dans
    `action`/`prompt_plan()`."""
    plans = _plans(1)
    sortie = {"plans": [{
        "numero": 0, "prompt_image": "a wireframe mechanism exposed",
        "disposition": "technical-cutaway",
    }]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    assert "technical cutaway view exposing internal mechanism" in fusionnes[0].registre_visuel
    assert "technical cutaway" not in fusionnes[0].action


def test_message_sans_texte_lisible_ajoute_la_mitigation_de_texte_illisible():
    """Cas message sans texte lisible : une mitigation `risques_predits`
    peut cibler du texte illisible, pas seulement une marque ou une main."""
    plans = _plans(1)
    sortie = {"plans": [{
        "numero": 0, "prompt_image": "an abstract message flashes on screen",
        "risques_predits": [{"risque": "garbled text",
                            "mitigation": "abstract interface marks, no legible typography"}],
    }]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    assert "abstract interface marks, no legible typography" in fusionnes[0].action


def test_le_meme_plan_produit_un_prompt_enrichi_avec_les_nouveaux_champs_vs_sans():
    """La garantie centrale : à texte de base identique, la version qui
    porte les 4 nouveaux champs contient strictement plus d'information
    vérifiable que la version qui ne les porte pas."""
    plans = _plans(1)
    base = "an accelerator pedal glowing in the dark"
    sortie_sans = {"plans": [{"numero": 0, "prompt_image": base}]}
    sortie_avec = {"plans": [{
        "numero": 0, "prompt_image": base,
        "abstractions": [{"concept": "Tesla", "representation": "generic unbranded vehicle component"}],
        "risques_predits": [{"risque": "real brand",
                            "mitigation": "no manufacturer badge, no logo, unbranded design"}],
        "relations": [{"cible": "pedal", "etat": "visibly depressed"}],
    }]}
    action_sans = ShotPromptWriter().fusionner(plans, sortie_sans)[0].action
    action_avec = ShotPromptWriter().fusionner(plans, sortie_avec)[0].action

    assert action_sans == base
    assert "generic unbranded vehicle component" in action_avec
    assert "no manufacturer badge, no logo, unbranded design" in action_avec
    assert "pedal visibly depressed" in action_avec
    assert action_avec != action_sans


def test_un_prompt_deja_complet_nest_pas_modifie():
    """Non-remplissage : quand le modèle a déjà bien écrit sa prose, le
    filet déterministe ne doit RIEN rajouter — prouve que chaque mécanisme
    est conditionnel, pas systématique."""
    plans = _plans(1)
    prompt_deja_complet = (
        "an accelerator pedal glowing in the dark, generic unbranded vehicle "
        "component, no manufacturer badge, no logo, unbranded design, "
        "pedal visibly depressed"
    )
    sortie = {"plans": [{
        "numero": 0, "prompt_image": prompt_deja_complet,
        "abstractions": [{"concept": "Tesla", "representation": "generic unbranded vehicle component"}],
        "risques_predits": [{"risque": "real brand",
                            "mitigation": "no manufacturer badge, no logo, unbranded design"}],
        "relations": [{"cible": "pedal", "etat": "visibly depressed"}],
    }]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    assert fusionnes[0].action == prompt_deja_complet


def test_priorite_visuelle_ajoute_une_clause_de_focus_jamais_de_position_physique():
    """VISUAL_PRIORITY : jamais foreground/background — une clause de
    priorité perceptuelle, ajoutée seulement quand des éléments secondaires
    existent."""
    plans = _plans(1)
    sortie = {"plans": [{
        "numero": 0, "prompt_image": "a submarine cable under the ocean",
        "elements_obligatoires": ["submarine cable"],
        "elements_secondaires": ["distant fish"],
    }]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    assert "submarine cable as the visual focus, distant fish secondary in the frame" in fusionnes[0].action
    assert "foreground" not in fusionnes[0].action
    assert "background" not in fusionnes[0].action


def test_fusionner_porte_les_nouveaux_champs_sur_le_plan_pour_la_qa():
    """Comme `elements_obligatoires`/`elements_a_exclure` : ces champs
    doivent survivre au-delà de la fusion, pour `ContratVisuel`/la QA en
    aval — pas seulement corriger le texte du prompt."""
    plans = _plans(1)
    sortie = {"plans": [{
        "numero": 0, "prompt_image": "x",
        "relations": [{"cible": "pedal", "etat": "visibly depressed"}],
        "abstractions": [{"concept": "Tesla", "representation": "generic unbranded vehicle component"}],
        "risques_predits": [{"risque": "real brand", "mitigation": "no logo"}],
        "disposition": "technical-cutaway",
    }]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    assert fusionnes[0].relations == [{"cible": "pedal", "etat": "visibly depressed"}]
    assert fusionnes[0].abstractions == [{"concept": "Tesla", "representation": "generic unbranded vehicle component"}]
    assert fusionnes[0].risques_predits == [{"risque": "real brand", "mitigation": "no logo"}]
    assert fusionnes[0].disposition == "technical-cutaway"


def test_sans_les_nouveaux_champs_ils_retombent_sur_des_valeurs_vides():
    """Non-régression : un job en cache d'avant plans@1.11.0 n'a aucun de
    ces champs dans sa sortie stockée — ne doit pas planter."""
    plans = _plans(1)
    sortie = {"plans": [{"numero": 0, "prompt_image": "x"}]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    assert fusionnes[0].relations == []
    assert fusionnes[0].abstractions == []
    assert fusionnes[0].risques_predits == []
    assert fusionnes[0].disposition == ""


# ── geometrie : où se place chaque objet, jamais une coordonnée (plans@1.12.0) ─

def test_geometrie_avion_piste_aeroport_ajoute_une_phrase_par_objet():
    """Cas obligatoire (dossier « geometry-light ») : avion + piste +
    aéroport, chacun avec sa position — le prompt final doit porter les
    trois positions ET la relation de trajectoire."""
    plans = _plans(1)
    sortie = {"plans": [{
        "numero": 0,
        "prompt_image": "a futuristic passenger airliner climbing into the sky just after takeoff",
        "elements_obligatoires": ["airliner", "runway", "airport"],
        "relations": [{"cible": "flight path",
                       "etat": "originates at the aircraft, curves upward to the right, glowing blue holographic line"}],
        "geometrie": [
            {"entite": "airliner", "zone": "center", "profondeur": "foreground"},
            {"entite": "runway", "zone": "bottom", "profondeur": "foreground"},
            {"entite": "airport", "zone": "center", "profondeur": "background"},
        ],
    }]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    action = fusionnes[0].action
    assert "airliner, centered in the frame, in the foreground" in action
    assert "runway, near the bottom of the frame, in the foreground" in action
    assert "airport, centered in the frame, in the background" in action
    assert "originates at the aircraft, curves upward to the right" in action


def test_geometrie_deja_couverte_par_la_prose_nest_pas_dupliquee():
    plans = _plans(1)
    sortie = {"plans": [{
        "numero": 0,
        "prompt_image": "a runway, near the bottom of the frame, in the foreground, wet asphalt",
        "geometrie": [{"entite": "runway", "zone": "bottom", "profondeur": "foreground"}],
    }]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    assert fusionnes[0].action.count("near the bottom of the frame") == 1


def test_geometrie_est_vide_par_defaut_sans_regression():
    """Non-régression : un job en cache d'avant plans@1.12.0 n'a pas ce
    champ dans sa sortie stockée — ne doit pas planter."""
    plans = _plans(1)
    sortie = {"plans": [{"numero": 0, "prompt_image": "x"}]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    assert fusionnes[0].geometrie == []


def test_geometrie_est_portee_sur_le_plan_pour_la_qa():
    plans = _plans(1)
    geo = [{"entite": "airliner", "zone": "center", "profondeur": "foreground"}]
    sortie = {"plans": [{"numero": 0, "prompt_image": "x", "geometrie": geo}]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    assert fusionnes[0].geometrie == geo


# ── mouvement_* (plans@1.13.0) : passthrough pur, jamais dans le prompt image ─

def test_mouvement_est_porte_sur_le_plan_sans_toucher_au_prompt_image():
    plans = _plans(1)
    sortie = {"plans": [{
        "numero": 0, "prompt_image": "an accelerator pedal glowing in the dark",
        "mouvement_sujet": "the pedal moves downward smoothly",
        "mouvement_camera": "push_in_lent",
        "mouvement_environnement": "energy pulses travel along the cables",
        "intensite_mouvement": "fort",
    }]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    assert fusionnes[0].mouvement_sujet == "the pedal moves downward smoothly"
    assert fusionnes[0].mouvement_camera == "push_in_lent"
    assert fusionnes[0].mouvement_environnement == "energy pulses travel along the cables"
    assert fusionnes[0].intensite_mouvement == "fort"
    # Le prompt d'IMAGE reste intouché — ces champs sont pour l'animation
    # uniquement (voir pdz.production.animation._prompt_mouvement()).
    assert fusionnes[0].action == "an accelerator pedal glowing in the dark"


def test_sans_mouvement_les_champs_retombent_sur_des_valeurs_vides():
    """Non-régression : un job en cache d'avant plans@1.13.0 n'a aucun de
    ces champs dans sa sortie stockée — ne doit pas planter."""
    plans = _plans(1)
    sortie = {"plans": [{"numero": 0, "prompt_image": "x"}]}
    fusionnes = ShotPromptWriter().fusionner(plans, sortie)
    assert fusionnes[0].mouvement_sujet == ""
    assert fusionnes[0].mouvement_camera == ""
    assert fusionnes[0].mouvement_environnement == ""
    assert fusionnes[0].intensite_mouvement == ""
