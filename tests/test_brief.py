"""BriefWriter : la phrase devient une structure narrative avant tout dialogue.

Sans lui, le sujet passait directement à ScriptWriter, qui inventait sa
propre structure à chaque appel — aucun garde-fou sur le nombre de temps
forts ni leur répartition. `beats` (SQUELETTE NARRATIF) existait déjà côté
ScriptWriter, mais rien ne le remplissait automatiquement.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pdz.agents.base import nb_beats_pour
from pdz.agents.ecriture.brief import BriefWriter
from pdz.moteur.erreurs import ErreurValidation
from pdz.moteur.pipeline import Contexte
from pdz.prompts import charger
from pdz.univers import Univers

FRUITS = Path("univers/fruit-island.yaml")


def _contexte():
    return Contexte(job_id="j", etape_cle="brief", profil="equilibre",
                    budget_restant=0.60)


def _beat(pct, role="hook", quoi="il se passe quelque chose de précis ici"):
    return {"position_pct": pct, "role": role, "quoi": quoi}


def test_les_variables_incluent_le_nombre_de_beats_vise():
    u = Univers.charger(FRUITS)
    v = BriefWriter().variables({"univers": u, "situation": "test", "duree_s": 45}, _contexte())
    assert v["situation"] == "test"
    assert v["nb_beats"] == nb_beats_pour(45)
    assert v["contexte_univers"] == u.contexte_script()


def test_sans_duree_explicite_retombe_sur_celle_de_lunivers():
    u = Univers.charger(FRUITS)
    v = BriefWriter().variables({"univers": u, "situation": "test"}, _contexte())
    assert v["duree_s"] == u.duree_cible_s


def test_le_schema_impose_le_nombre_de_beats():
    u = Univers.charger(FRUITS)
    base = charger("ecriture/brief").schema_sortie
    schema = BriefWriter().schema(base, {"univers": u, "duree_s": 45}, _contexte())
    assert schema["properties"]["beats"]["minItems"] == nb_beats_pour(45)


def test_un_brief_vide_est_refuse():
    u = Univers.charger(FRUITS)
    with pytest.raises(ErreurValidation) as e:
        BriefWriter().apres({"beats": []}, {"univers": u, "duree_s": 45}, _contexte())
    assert "vide" in str(e.value)


def test_trop_peu_de_beats_est_refuse():
    u = Univers.charger(FRUITS)
    attendus = nb_beats_pour(45)
    trop_court = [_beat(0)] * (attendus - 1)
    with pytest.raises(ErreurValidation) as e:
        BriefWriter().apres({"beats": trop_court}, {"univers": u, "duree_s": 45}, _contexte())
    assert "incomplet" in str(e.value)


def test_des_positions_dans_le_desordre_sont_refusees():
    u = Univers.charger(FRUITS)
    attendus = nb_beats_pour(45)
    beats = [_beat(pct) for pct in range(0, attendus * 10, 10)]
    beats[1], beats[2] = beats[2], beats[1]  # désordonne
    with pytest.raises(ErreurValidation) as e:
        BriefWriter().apres({"beats": beats}, {"univers": u, "duree_s": 45}, _contexte())
    assert "ordre" in str(e.value)


def test_un_brief_valide_passe():
    u = Univers.charger(FRUITS)
    attendus = nb_beats_pour(45)
    beats = [_beat(pct) for pct in range(0, attendus * 10, 10)][:attendus]
    sortie = BriefWriter().apres({"beats": beats}, {"univers": u, "duree_s": 45}, _contexte())
    assert len(sortie["beats"]) == attendus


def test_la_signature_reference_le_prompt_actif():
    sig = BriefWriter().signature()
    assert sig["agent"] == "brief"
    assert sig["prompt"] == charger("ecriture/brief").ref
