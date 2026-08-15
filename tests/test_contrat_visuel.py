"""contrat_visuel.compiler() : le plan traduit en 8 questions, sans appel IA.

Aucun mock d'agent ici — la compilation est une fonction pure qui ne lit que
des champs déjà écrits ailleurs dans le pipeline (`PlanScript`, `Personnage`,
`Univers`). La preuve de pureté, c'est qu'aucun test de ce fichier ne
monkeypatch le moindre agent.
"""

from __future__ import annotations

from pathlib import Path

from pdz.production import contrat_visuel
from pdz.production.storyboard import PlanScript
from pdz.univers import Univers

FRUITS = Path(__file__).resolve().parent.parent / "univers" / "fruit-island.yaml"


def _plan(**kwargs):
    base = dict(
        numero=0, replique_numero=0, personnage="strawberina",
        action="strawberina holds a golden trophy", emotion="joie",
    )
    base.update(kwargs)
    return PlanScript(**base)


def test_compiler_reprend_les_champs_du_plan_sans_appel_ia():
    univers = Univers.charger(FRUITS)
    perso = univers.personnage("strawberina")
    plan = _plan(
        decor="villa", fonction="révèle la victoire", cadrage="plan_moyen",
        elements_obligatoires=["golden trophy"], elements_a_exclure=["banana"],
    )

    contrat = contrat_visuel.compiler(plan, perso, univers)

    assert contrat.qui == "strawberina"
    assert contrat.qui_apparence == perso.apparence
    assert contrat.quoi == plan.action
    assert contrat.avec_quoi == ["golden trophy"]
    assert contrat.ne_doit_pas_apparaitre == ["banana"]
    assert contrat.ou_id == "villa"
    assert contrat.ou == univers.decor("villa").description
    assert contrat.cadrage == "plan_moyen"
    assert "révèle la victoire" in contrat.etat_moment
    assert "joie" in contrat.etat_moment


def test_relations_detecte_une_main_qui_touche_sans_appel_ia():
    univers = Univers.charger(FRUITS)
    perso = univers.personnage("strawberina")
    plan = _plan(action="a hand touches the glowing trophy",
                elements_obligatoires=["glowing trophy"])

    contrat = contrat_visuel.compiler(plan, perso, univers)

    assert contrat.relations != []
    assert contrat.avec_quoi == ["glowing trophy"]


def test_registre_univers_reste_le_plancher_si_le_plan_ne_precise_rien():
    univers = Univers.charger(FRUITS)
    perso = univers.personnage("strawberina")
    plan = _plan(registre_visuel="")

    contrat = contrat_visuel.compiler(plan, perso, univers)

    assert contrat.registre == univers.style.rendu
    assert contrat.registre != ""


def test_registre_du_plan_prime_sur_celui_de_lunivers_quand_precise():
    univers = Univers.charger(FRUITS)
    perso = univers.personnage("strawberina")
    plan = _plan(registre_visuel="wireframe abstract diagram, no cartoon rendering")

    contrat = contrat_visuel.compiler(plan, perso, univers)

    assert contrat.registre == "wireframe abstract diagram, no cartoon rendering"
    assert contrat.registre_univers == univers.style.rendu
