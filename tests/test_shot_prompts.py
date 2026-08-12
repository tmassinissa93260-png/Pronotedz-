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


def test_la_signature_reference_le_prompt_actif():
    sig = ShotPromptWriter().signature()
    assert sig["agent"] == "shot_prompts"
    assert sig["prompt"] == charger("ecriture/plans").ref
