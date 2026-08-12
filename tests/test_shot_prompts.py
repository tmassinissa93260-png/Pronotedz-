"""ShotPromptWriter : le prompt d'image, écrit séparément du dialogue.

ScriptWriter écrit `action` en même temps que le dialogue — une phrase
sommaire, pas un cadrage. Cet agent reprend le script déjà figé et écrit,
pour chaque réplique, un prompt d'image digne d'un directeur de la
photographie (cadrage, netteté), qui remplace `action` avant la génération
d'image.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pdz.agents.ecriture.plans import ShotPromptWriter
from pdz.moteur.erreurs import ErreurValidation
from pdz.moteur.pipeline import Contexte
from pdz.prompts import charger
from pdz.univers import Univers

FRUITS = Path("univers/fruit-island.yaml")


def _contexte():
    return Contexte(job_id="j", etape_cle="shot_prompts", profil="equilibre",
                    budget_restant=0.60)


def _repliques(n=3):
    return [
        {"numero": i + 1, "personnage": "strawberina", "replique": f"réplique {i + 1}",
         "action": "action minimale", "fonction_plan": "établit l'échelle du monde"}
        for i in range(n)
    ]


def test_les_variables_reprennent_chaque_replique():
    u = Univers.charger(FRUITS)
    v = ShotPromptWriter().variables({"univers": u, "repliques": _repliques(3)}, _contexte())
    assert len(v["repliques"]) == 3
    assert v["repliques"][0]["fonction_plan"] == "établit l'échelle du monde"
    assert v["contexte_univers"] == u.contexte_script()


def test_le_schema_impose_au_moins_un_prompt_par_replique():
    u = Univers.charger(FRUITS)
    base = charger("ecriture/plans").schema_sortie
    schema = ShotPromptWriter().schema(base, {"univers": u, "repliques": _repliques(5)}, _contexte())
    assert schema["properties"]["plans"]["minItems"] == 5


def test_des_prompts_manquants_sont_refuses():
    entrees = {"univers": None, "repliques": _repliques(3)}
    sortie = {"plans": [{"numero": 1, "prompt_image": "x"}, {"numero": 2, "prompt_image": "y"}]}
    with pytest.raises(ErreurValidation) as e:
        ShotPromptWriter().apres(sortie, entrees, _contexte())
    assert "3" in str(e.value)


def test_des_prompts_complets_passent():
    entrees = {"univers": None, "repliques": _repliques(3)}
    sortie = {"plans": [{"numero": i, "prompt_image": f"prompt {i}"} for i in (1, 2, 3)]}
    resultat = ShotPromptWriter().apres(sortie, entrees, _contexte())
    assert len(resultat["plans"]) == 3


def test_fusionner_remplace_laction_par_le_prompt_riche():
    repliques = _repliques(2)
    sortie = {"plans": [
        {"numero": 1, "prompt_image": "gros plan sur son visage inquiet"},
        {"numero": 2, "prompt_image": "plan large, elle traverse la pièce"},
    ]}
    fusionnees = ShotPromptWriter().fusionner(repliques, sortie)
    assert fusionnees[0]["action"] == "gros plan sur son visage inquiet"
    assert fusionnees[1]["action"] == "plan large, elle traverse la pièce"
    # Le reste de la réplique (dialogue, fonction_plan...) n'est pas touché.
    assert fusionnees[0]["fonction_plan"] == "établit l'échelle du monde"
    assert fusionnees[0]["replique"] == repliques[0]["replique"]


def test_fusionner_garde_laction_dorigine_si_un_numero_manque():
    """`apres()` refuse normalement les manques avant d'arriver ici — ce
    test couvre l'appelant qui, par erreur, sauterait la validation."""
    repliques = _repliques(2)
    sortie = {"plans": [{"numero": 1, "prompt_image": "gros plan sur son visage"}]}
    fusionnees = ShotPromptWriter().fusionner(repliques, sortie)
    assert fusionnees[0]["action"] == "gros plan sur son visage"
    assert fusionnees[1]["action"] == "action minimale"


def test_les_repliques_dorigine_ne_sont_pas_mutees():
    repliques = _repliques(1)
    sortie = {"plans": [{"numero": 1, "prompt_image": "nouveau prompt"}]}
    ShotPromptWriter().fusionner(repliques, sortie)
    assert repliques[0]["action"] == "action minimale"


def test_la_signature_reference_le_prompt_actif():
    sig = ShotPromptWriter().signature()
    assert sig["agent"] == "shot_prompts"
    assert sig["prompt"] == charger("ecriture/plans").ref
