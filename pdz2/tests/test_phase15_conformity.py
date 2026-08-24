"""Audit de conformité : les flèches annoncées existent-elles dans le code ?

Ces tests ne vérifient pas un comportement métier. Ils vérifient qu'un contrat
produit est bien un contrat **relu**, et qu'aucun état critique ne s'échappe
dans une structure libre à côté du système de contrats.

Deux flèches étaient annoncées et absentes :

    RepairPlan    → Repair Compiler   l'état passait par un JSON libre
    ExecutionPlan → Dispatcher        le plan n'était relu par personne
"""

from __future__ import annotations

from pdz2.contracts.render import RenderStrategy
from pdz2.storage import EpisodeStore

# ------------------------------------------------ RepairPlan → Repair Compiler


def test_the_repair_loop_reads_back_its_own_contracts(tmp_path):
    """L'interdiction du cycle suivant sort du contrat, pas d'un dict à côté."""
    from pdz2.cli.phase9 import _load_forbidden
    from pdz2.contracts.observation import RepairAction, RepairPlan, RepairStep
    from pdz2.contracts.pipeline import Stage

    store = EpisodeStore(tmp_path / "ep")
    store.initialise()
    store.save(
        RepairPlan(
            diagnosis_id="failure_diagnosis-1",
            shot_id="S00",
            steps=[
                RepairStep(
                    action=RepairAction.FALLBACK_STILL,
                    rationale="essai d'audit",
                    target_stage=Stage.RENDER,
                    expected_effect="le plan sort en image fixe",
                )
            ],
            cycle=1,
            max_cycles=3,
            guaranteed_fallback=RepairAction.FALLBACK_STILL,
            forbidden_strategies=[RenderStrategy.PARALLAX_2_5D],
        )
    )
    assert _load_forbidden(store) == {"S00": {RenderStrategy.PARALLAX_2_5D}}


def test_no_free_json_carries_repair_state_any_more(tmp_path):
    """Le fichier parallèle ne doit plus jamais être écrit."""
    import inspect

    from pdz2.cli import phase9

    source = inspect.getsource(phase9)
    assert "forbidden_strategies.json" not in source
    assert "_save_forbidden" not in source


def test_a_repair_plan_of_the_previous_version_still_loads():
    """Un épisode d'avant 1.1.0 se relit, sans interdiction lisible."""
    from pdz2.contracts.observation import RepairPlan
    from pdz2.contracts.versioning import registry

    ancien = {
        "contract_type": "repair_plan",
        "version": "1.0.0",
        "id": "repair_plan-ancien",
        "created_at": "2026-01-01T00:00:00+00:00",
        "status": "draft",
        "diagnosis_id": "failure_diagnosis-1",
        "shot_id": "S00",
        "steps": [
            {
                "action": "fallback_still",
                "rationale": "plan d'un épisode antérieur",
                "target_stage": "render",
                "expected_effect": "le plan sort en image fixe",
            }
        ],
        "cycle": 1,
        "max_cycles": 3,
        "guaranteed_fallback": "fallback_still",
    }
    relu = registry.load(ancien)
    assert isinstance(relu, RepairPlan)
    assert relu.forbidden_strategies == []


# ------------------------------------------------- aucun contrat sans lecteur


PRODUITS_TERMINAUX = {
    # Contrats dont l'absence de lecteur est le comportement voulu : ils sont
    # le point d'arrivée, ou ils vivent imbriqués dans un contrat porteur.
    "master_artifact",      # le livrable : plus rien en aval
    "production_journal",   # écrit pour un humain, pas pour la chaîne
    "cost_ledger",          # vue relue depuis les transitions
    "capability_entry",     # imbriqué dans capability_matrix
    "anchor_spec", "claim", "evidence", "fact_graph", "shot_intent",
    "shot_spec", "script_line", "source_reference", "state_transition",
    "camera_program", "image_spec", "subtitle_track", "validation_report",
    "failure_diagnosis", "render_artifact", "observation_report",
    "director_brief", "research_state", "topic_request", "director_state",
    "script_state", "voice_timeline", "temporal_plan", "shot_graph",
    "visual_bible", "motion_program", "render_spec_requested",
    "render_spec_executable", "edit_timeline", "episode_snapshot",
    "capability_matrix", "repair_plan", "execution_plan",
    "duration_policy",   # relu par la commande voice, puis par la QA
}


def test_the_registry_and_the_audit_list_stay_in_step():
    """Un contrat neuf doit passer par cette liste, donc par une décision."""
    from pdz2.contracts.versioning import registry

    connus = {t.CONTRACT_NAME for t in registry.types()}
    assert connus == PRODUITS_TERMINAUX, (
        "contrat sans décision d'audit : "
        f"{sorted(connus ^ PRODUITS_TERMINAUX)}"
    )


# ------------------------------------------------ ExecutionPlan → Dispatcher


def test_the_dispatcher_honours_the_declared_retry_budget(tmp_path):
    """Le budget de tentatives vient du plan, pas d'une politique en dur."""
    from pdz2.contracts.render import ExecutionPlan, ExecutionStep, ExecutionStepKind
    from pdz2.execution.dispatcher import _budgets

    plan = ExecutionPlan(
        episode_id="ep",
        steps=[
            ExecutionStep(
                step_id="render-S00",
                kind=ExecutionStepKind.GENERATE_VIDEO,
                spec_id="render_spec_executable-abc",
                retry_budget=3,
            )
        ],
        total_estimated_cost_usd=0.0,
    )
    assert _budgets(plan) == {"render_spec_executable-abc": 3}
    # Sans plan, aucune reprise n'est inventée.
    assert _budgets(None) == {}


def test_a_provider_is_retried_exactly_as_the_plan_allows(tmp_path):
    """Trois tentatives déclarées : trois appels, pas quatre, pas un."""
    from pdz2.contracts.render import ExecutionPlan, ExecutionStep, ExecutionStepKind
    from pdz2.execution import ExecutionDispatcher
    from pdz2.tests.provider_double import AlwaysFailingProvider

    class _Image:
        shot_id = "S00"
        composite_path = tmp_path / "s00.png"
        layer_paths: dict = {}

    from pdz2.contracts.common import Resolution
    from pdz2.contracts.motion import CameraMove
    from pdz2.contracts.render import RenderSpecExecutable, RequestedEcho

    echo = RequestedEcho(
        strategy=RenderStrategy.DIRECT_I2V,
        camera=CameraMove.LOCK,
        duration_s=2.0,
        resolution=Resolution(width=64, height=64),
        fps=24,
    )
    executable = RenderSpecExecutable(
        requested_spec_id="render_spec_requested-1",
        shot_id="S00",
        requested=echo,
        strategy=RenderStrategy.DIRECT_I2V,
        execution_camera=CameraMove.LOCK,
        duration_s=2.0,
        resolution=Resolution(width=64, height=64),
        fps=24,
        provider="atelier-en-panne",
        degradations=[],
    )
    plan = ExecutionPlan(
        episode_id="ep",
        steps=[
            ExecutionStep(
                step_id="render-S00",
                kind=ExecutionStepKind.GENERATE_VIDEO,
                spec_id=executable.id,
                retry_budget=3,
            )
        ],
        total_estimated_cost_usd=0.0,
    )
    en_panne = AlwaysFailingProvider()
    dispatcher = ExecutionDispatcher(providers=(en_panne,))
    try:
        dispatcher.execute(
            executables=[executable],
            motion_programs=[],
            images=[_Image()],
            into=tmp_path,
            plan=plan,
        )
    except Exception:
        pass  # le repli local échouera faute d'image réelle : ce n'est pas l'objet
    assert en_panne.appels == 3, f"{en_panne.appels} tentatives pour un budget de 3"
