"""Deux lacunes fermées : la traçabilité des capacités et l'autorité du temps.

1. `capability_snapshot_id` était déclaré et jamais renseigné. Impossible de
   répondre après coup à « quelles capacités ont servi à décider que ce plan
   était exécutable ? ».

2. `deadline_s` et `ExecutionStep.timeout_s` exprimaient la même idée à deux
   endroits, et l'aiguilleur ne lisait ni l'un ni l'autre : un fournisseur
   pouvait bloquer indéfiniment.
"""

from __future__ import annotations

import time

import pytest
from pydantic import ValidationError

from pdz2.contracts.capacity import CapabilityMatrix
from pdz2.contracts.render import (
    ExecutionStepKind,
    RenderSpecExecutable,
    RenderStrategy,
)
from pdz2.engines.routing import RenderRouter
from pdz2.engines.routing.router import DEFAULT_TIMEOUT_S, _budget
from pdz2.execution.dispatcher import _delais, _sous_delai
from pdz2.providers.video import ProviderUnavailable
from pdz2.storage import EpisodeStore
from pdz2.tests import factories, pipeline
from pdz2.tests.provider_double import LocalVideoDouble


@pytest.fixture(scope="module")
def episode(tmp_path_factory):
    return pipeline.build_episode(
        tmp_path_factory.mktemp("phase20"), through_render_spec=True,
        resolution=pipeline.SMALL,
    )


def _route(episode, **kwargs):
    return RenderRouter(**kwargs).route(
        episode_id="ep",
        requested=episode.render_specs,
        motion_programs=episode.motion_programs,
        image_specs=episode.image_specs,
    )


# =========================================== 1. traçabilité des capacités


def test_the_snapshot_is_really_produced_and_stamped(episode):
    matrice = CapabilityMatrix()
    outcome = _route(episode, capability_matrix=matrice)
    assert all(e.capability_snapshot_id == matrice.id for e in outcome.executables)


def test_the_snapshot_persists_and_stays_findable(tmp_path, episode):
    """Un instantané qu'on écrase n'en est plus un : ils s'accumulent."""
    store = EpisodeStore(tmp_path / "ep")
    store.initialise()
    premiere, seconde = CapabilityMatrix(), CapabilityMatrix()
    store.save(premiere)
    store.save(seconde)

    connus = {m.id for m in store.load_collection("capability_matrix")}
    assert {premiere.id, seconde.id} <= connus, "un instantané a été écrasé"
    assert store.latest("capability_matrix").id in connus


def test_the_capabilities_behind_a_decision_can_be_recovered(tmp_path, episode):
    """La question à laquelle tout ceci sert à répondre."""
    from pdz2.engines.governance import CapabilityProbe

    store = EpisodeStore(tmp_path / "ep")
    store.initialise()
    matrice = CapabilityProbe().run().matrix
    store.save(matrice)

    outcome = _route(episode, capability_matrix=matrice)
    executable = outcome.executables[0]

    # Six mois plus tard, avec le seul exécutable en main :
    retrouvee = next(
        m
        for m in store.load_collection("capability_matrix")
        if m.id == executable.capability_snapshot_id
    )
    assert retrouvee.entries, "l'instantané doit porter des capacités"
    provenances = {
        v.provenance.value for e in retrouvee.entries for v in e.values
    }
    # Les provenances sont conservées telles quelles : rien n'est requalifié.
    assert provenances <= {"measured", "announced", "unknown"}


def test_naming_a_provider_without_a_snapshot_is_refused():
    """Construction directe : la fabrique, elle, remplit l'instantané d'office."""
    demande = factories.render_spec_requested()
    with pytest.raises(ValidationError, match="sans instantané de capacités"):
        RenderSpecExecutable(
            requested_spec_id=demande.id,
            shot_id=demande.shot_id,
            requested=demande.echo(),
            strategy=RenderStrategy.PARALLAX_2_5D,
            execution_camera=demande.requested_camera,
            duration_s=demande.duration_s,
            resolution=demande.resolution,
            fps=demande.fps,
            provider="atelier",
        )


def test_a_provider_is_set_aside_when_it_cannot_be_justified(episode):
    """Le routeur ne retient pas un fournisseur qu'il ne peut pas justifier."""
    outcome = _route(
        episode, video_capabilities=[LocalVideoDouble().get_capabilities()]
    )
    assert all(e.provider is None for e in outcome.executables)
    assert any(
        "instantané de capacités" in d.reason for d in outcome.degradations
    )


def test_a_local_shot_needs_no_snapshot(episode):
    """Aucun fournisseur nommé : rien à justifier, le champ reste vide."""
    outcome = _route(episode)
    assert all(e.provider is None for e in outcome.executables)
    assert all(e.capability_snapshot_id is None for e in outcome.executables)


# ================================================= 2. une seule autorité


def test_the_deadline_is_the_intent_and_the_timeout_is_derived():
    assert _budget(None, "render") == DEFAULT_TIMEOUT_S["render"]
    # Une échéance serre le budget…
    assert _budget(45.0, "render") == 45.0
    # …mais ne peut pas l'élargir au-delà du défaut de la nature d'étape.
    assert _budget(900.0, "render") == DEFAULT_TIMEOUT_S["render"]


def test_the_plan_carries_the_derived_budget(episode):
    serres = [s.derive(deadline_s=12.0) for s in episode.render_specs]
    outcome = RenderRouter().route(
        episode_id="ep",
        requested=serres,
        motion_programs=episode.motion_programs,
        image_specs=episode.image_specs,
    )
    rendus = [
        s for s in outcome.plan.steps
        if s.kind is not ExecutionStepKind.OBSERVE and s.spec_id
    ]
    assert rendus
    assert all(s.timeout_s == 12.0 for s in rendus), [s.timeout_s for s in rendus]


def test_only_the_plan_declares_a_timeout_to_the_dispatcher(episode):
    """L'aiguilleur ne lit que le plan : pas de seconde source de délai."""
    outcome = _route(episode)
    delais = _delais(outcome.plan)
    assert delais, "le plan doit déclarer un délai par exécutable"
    assert set(delais) <= {e.id for e in outcome.executables}
    # Sans plan, aucun délai n'est inventé.
    assert _delais(None) == {}


def test_a_provider_that_never_returns_is_abandoned():
    """Le cas qui bloquait : un fournisseur qui ne rend jamais la main."""

    class _Bloque:
        name = "atelier-bloque"

        def get_capabilities(self):
            return LocalVideoDouble().get_capabilities()

        def generate(self, job):
            time.sleep(30)
            raise AssertionError("ne devrait jamais aboutir")

    debut = time.monotonic()
    with pytest.raises(TimeoutError, match="dépassement"):
        _sous_delai(_Bloque(), object(), 0.3)
    ecoule = time.monotonic() - debut
    assert ecoule < 5, f"l'appel a été attendu {ecoule:.1f}s au lieu de 0.3s"


def test_a_provider_failure_still_surfaces_under_a_deadline():
    """Le délai ne doit pas masquer une panne ordinaire."""

    class _Panne:
        name = "atelier-panne"

        def generate(self, job):
            raise ProviderUnavailable("refus du moteur")

    with pytest.raises(ProviderUnavailable, match="refus du moteur"):
        _sous_delai(_Panne(), object(), 5.0)


def test_without_a_deadline_no_thread_is_spawned():
    """On n'ajoute pas un fil d'exécution pour rien."""
    appels = []

    class _Direct:
        name = "direct"

        def generate(self, job):
            import threading

            appels.append(threading.current_thread() is threading.main_thread())
            return "ok"

    assert _sous_delai(_Direct(), object(), None) == "ok"
    assert appels == [True], "l'appel doit rester sur le fil principal"


def test_no_stage_can_stay_running_for_ever():
    """Le pendant côté machine à états : une étape bloquée se récupère."""
    from pdz2.contracts.pipeline import Stage, StageStatus
    from pdz2.state import EpisodeStateMachine

    machine = EpisodeStateMachine.create(
        episode_id="ep", topic_request_id="topic_request-1"
    )
    # RESEARCH plutôt que RENDER : la barrière de coût interdit à juste titre
    # de démarrer un rendu avant la validation statique.
    machine.start(Stage.RESEARCH)
    repris = EpisodeStateMachine.resume(machine.snapshot)
    assert repris.interrupted_stages == [Stage.RESEARCH]
    repris.recover(reason="délai dépassé")
    assert repris.snapshot.state(Stage.RESEARCH).status is StageStatus.PENDING


def test_the_time_budget_survives_in_the_persisted_plan(tmp_path, episode):
    """Le budget temporel est conservé, relisible après coup."""
    store = EpisodeStore(tmp_path / "ep")
    store.initialise()
    serres = [s.derive(deadline_s=30.0) for s in episode.render_specs]
    outcome = RenderRouter().route(
        episode_id="ep",
        requested=serres,
        motion_programs=episode.motion_programs,
        image_specs=episode.image_specs,
    )
    store.save(outcome.plan)
    relu = store.load_collection("execution_plan")[0]
    assert all(s.timeout_s > 0 for s in relu.steps)
    assert any(s.timeout_s == 30.0 for s in relu.steps)


def test_the_timeout_is_hardcoded_in_exactly_one_place():
    """Aucune double autorité : une seule table de défauts."""
    import inspect

    from pdz2.engines.routing import router
    from pdz2.execution import dispatcher

    source_routeur = inspect.getsource(router)
    assert source_routeur.count("DEFAULT_TIMEOUT_S") >= 2
    # L'aiguilleur n'invente aucune valeur de délai.
    source_aiguilleur = inspect.getsource(dispatcher)
    assert "timeout_s=" not in source_aiguilleur
    assert "DEFAULT_TIMEOUT_S" not in source_aiguilleur
