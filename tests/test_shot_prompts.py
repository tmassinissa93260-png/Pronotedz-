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
