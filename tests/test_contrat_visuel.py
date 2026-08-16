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


def test_relations_reprend_directement_celles_ecrites_par_shotpromptwriter():
    """`relations` n'est plus deviné par position sur le texte déjà écrit —
    ShotPromptWriter les écrit directement (voir plans@1.11.0), `compiler()`
    les reprend telles quelles."""
    univers = Univers.charger(FRUITS)
    perso = univers.personnage("strawberina")
    plan = _plan(action="a hand touches the glowing trophy",
                elements_obligatoires=["glowing trophy"],
                relations=[{"cible": "glowing trophy", "etat": "visibly touched"}])

    contrat = contrat_visuel.compiler(plan, perso, univers)

    assert contrat.relations == [{"cible": "glowing trophy", "etat": "visibly touched"}]
    assert contrat.avec_quoi == ["glowing trophy"]


def test_relations_est_vide_par_defaut_sans_supposition_par_position():
    univers = Univers.charger(FRUITS)
    perso = univers.personnage("strawberina")
    plan = _plan(action="a hand touches the glowing trophy",
                elements_obligatoires=["glowing trophy"])

    contrat = contrat_visuel.compiler(plan, perso, univers)

    assert contrat.relations == []


def test_abstractions_risques_predits_disposition_reprennent_le_plan():
    univers = Univers.charger(FRUITS)
    perso = univers.personnage("strawberina")
    plan = _plan(
        abstractions=[{"concept": "Tesla", "representation": "generic unbranded vehicle component"}],
        risques_predits=[{"risque": "human hand", "mitigation": "mechanical actuator only, no visible human hand"}],
        disposition="technical-cutaway",
    )

    contrat = contrat_visuel.compiler(plan, perso, univers)

    assert contrat.abstractions == [{"concept": "Tesla", "representation": "generic unbranded vehicle component"}]
    assert contrat.risques_predits == [{"risque": "human hand", "mitigation": "mechanical actuator only, no visible human hand"}]
    assert contrat.disposition == "technical-cutaway"


def test_geometrie_reprend_directement_celle_ecrite_par_shotpromptwriter():
    univers = Univers.charger(FRUITS)
    perso = univers.personnage("strawberina")
    geo = [{"entite": "trophy", "zone": "center", "profondeur": "foreground"}]
    plan = _plan(geometrie=geo)

    contrat = contrat_visuel.compiler(plan, perso, univers)

    assert contrat.geometrie == geo


def test_geometrie_est_vide_par_defaut():
    univers = Univers.charger(FRUITS)
    perso = univers.personnage("strawberina")
    plan = _plan()

    contrat = contrat_visuel.compiler(plan, perso, univers)

    assert contrat.geometrie == []


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


def test_avec_quoi_secondaire_reprend_les_elements_secondaires_du_plan():
    univers = Univers.charger(FRUITS)
    perso = univers.personnage("strawberina")
    plan = _plan(elements_secondaires=["confetti"])

    contrat = contrat_visuel.compiler(plan, perso, univers)

    assert contrat.avec_quoi_secondaire == ["confetti"]


def test_contrat_visuel_porte_les_risques_de_marque_deja_calcules():
    """`risques_marque` vient de l'appelant, jamais recalculé par
    `compiler()` — voir pdz/production/images.py::fabriquer()."""
    univers = Univers.charger(FRUITS)
    perso = univers.personnage("strawberina")
    plan = _plan(action="a Tesla trophy on the podium")

    contrat = contrat_visuel.compiler(plan, perso, univers, risques_marque=["Tesla"])

    assert contrat.risques_marque == ["Tesla"]


def test_risques_marque_est_vide_par_defaut():
    univers = Univers.charger(FRUITS)
    perso = univers.personnage("strawberina")
    plan = _plan()

    contrat = contrat_visuel.compiler(plan, perso, univers)

    assert contrat.risques_marque == []
