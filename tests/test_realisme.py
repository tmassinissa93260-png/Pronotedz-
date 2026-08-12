"""RealismWriter : corrige en amont ce qu'un modèle d'image rate toujours.

Texte seul, aucun appel image. Repère dans chaque prompt déjà écrit ce qui
demande implicitement du texte lisible, un logo, ou un visage interdit par
l'univers, et le remplace par un équivalent que le modèle sait rendre.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pdz.agents.ecriture.realisme import RealismWriter
from pdz.moteur.erreurs import ErreurValidation
from pdz.moteur.pipeline import Contexte
from pdz.production.storyboard import PlanScript
from pdz.prompts import charger
from pdz.univers import Univers

FRUITS = Path("univers/fruit-island.yaml")


def _contexte():
    return Contexte(job_id="j", etape_cle="realisme", profil="equilibre",
                    budget_restant=0.60)


def _plans(n=3):
    return [
        PlanScript(numero=i, replique_numero=i + 1, personnage="strawberina",
                   action=f"prompt original {i}", emotion="calme",
                   fonction="établit l'échelle du monde")
        for i in range(n)
    ]


def test_les_variables_reprennent_le_prompt_de_chaque_plan():
    u = Univers.charger(FRUITS)
    v = RealismWriter().variables({"univers": u, "plans": _plans(3)}, _contexte())
    assert len(v["plans"]) == 3
    assert v["plans"][0]["prompt_image"] == "prompt original 0"
    assert v["contexte_univers"] == u.contexte_script()


def test_le_schema_impose_un_prompt_corrige_par_plan():
    u = Univers.charger(FRUITS)
    base = charger("ecriture/realisme").schema_sortie
    schema = RealismWriter().schema(base, {"univers": u, "plans": _plans(5)}, _contexte())
    assert schema["properties"]["plans"]["minItems"] == 5


def test_des_corrections_manquantes_sont_refusees():
    entrees = {"univers": None, "plans": _plans(3)}
    sortie = {"plans": [{"numero": 0, "prompt_image": "x"}, {"numero": 1, "prompt_image": "y"}]}
    with pytest.raises(ErreurValidation) as e:
        RealismWriter().apres(sortie, entrees, _contexte())
    assert "2" in str(e.value)


def test_des_corrections_completes_passent():
    entrees = {"univers": None, "plans": _plans(3)}
    sortie = {"plans": [{"numero": i, "prompt_image": f"corrigé {i}"} for i in (0, 1, 2)]}
    resultat = RealismWriter().apres(sortie, entrees, _contexte())
    assert len(resultat["plans"]) == 3


def test_fusionner_remplace_laction_par_le_prompt_corrige():
    plans = _plans(2)
    sortie = {"plans": [
        {"numero": 0, "prompt_image": "lumière d'écran, bulles floues"},
        {"numero": 1, "prompt_image": "silhouette de dos, contre-jour"},
    ]}
    fusionnes = RealismWriter().fusionner(plans, sortie)
    assert fusionnes[0].action == "lumière d'écran, bulles floues"
    assert fusionnes[1].action == "silhouette de dos, contre-jour"
    # Le reste du plan (fonction, émotion...) n'est pas touché.
    assert fusionnes[0].fonction == "établit l'échelle du monde"
    assert fusionnes[0].emotion == "calme"


def test_fusionner_garde_le_prompt_dorigine_si_un_numero_manque():
    """`apres()` refuse normalement les manques avant d'arriver ici — ce
    test couvre l'appelant qui, par erreur, sauterait la validation."""
    plans = _plans(2)
    sortie = {"plans": [{"numero": 0, "prompt_image": "corrigé"}]}
    fusionnes = RealismWriter().fusionner(plans, sortie)
    assert fusionnes[0].action == "corrigé"
    assert fusionnes[1].action == "prompt original 1"


def test_les_plans_dorigine_ne_sont_pas_mutes():
    plans = _plans(1)
    sortie = {"plans": [{"numero": 0, "prompt_image": "corrigé"}]}
    RealismWriter().fusionner(plans, sortie)
    assert plans[0].action == "prompt original 0"


def test_la_signature_reference_le_prompt_actif():
    sig = RealismWriter().signature()
    assert sig["agent"] == "realisme"
    assert sig["prompt"] == charger("ecriture/realisme").ref


def test_le_prompt_actif_couvre_texte_logo_et_visage():
    """Les trois pièges connus (mesurés à l'écran sur techno-holo, ce soir)
    doivent être couverts par la consigne active, pas seulement par
    l'intuition du modèle."""
    texte = charger("ecriture/realisme").systeme_stable.lower()
    assert "texte" in texte
    assert "logo" in texte
    assert "visage" in texte
