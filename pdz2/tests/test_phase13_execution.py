"""Aiguillage d'exécution : stratégie → exécutant → artefact.

Ce que ces tests verrouillent, c'est la séparation que le §18 exige et que la
chaîne ne réalisait pas : la stratégie dit COMMENT, le fournisseur dit AVEC
QUOI, le renderer exécute. Avant cette couche, le port `VideoProvider`
n'était appelé par personne — un plan routé vers une stratégie générative
aurait été refusé à l'exécution.

Le fournisseur employé ici est un double **local et réel** (il encode
vraiment, par ffmpeg) : voir `pdz2/tests/provider_double.py` pour pourquoi
ce n'est pas un faux adaptateur, et pourquoi il ne change rien à ce que
`pdz2 capabilities` déclare.
"""

from __future__ import annotations

import pytest

from pdz2.contracts.capability import CapabilityState
from pdz2.contracts.enums import Pacing
from pdz2.contracts.render import RenderStrategy
from pdz2.execution import ExecutionDispatcher, Executor
from pdz2.execution.dispatcher import DispatchRejected, _local_fallback
from pdz2.providers.video import NO_VIDEO_PROVIDERS, VideoProvider
from pdz2.renderers import ffmpeg_capability
from pdz2.tests import pipeline
from pdz2.tests.provider_double import AlwaysFailingProvider, LocalVideoDouble

needs_ffmpeg = pytest.mark.skipif(
    not ffmpeg_capability().usable, reason="binaire ffmpeg absent"
)


@pytest.fixture(scope="module")
def episode(tmp_path_factory):
    """Un épisode au rythme rapide.

    Le seuil génératif est calé sur des valeurs mesurées : au rythme mesuré,
    l'énergie plafonne à 0.70 et aucun plan n'appelle de fournisseur — c'est
    le comportement voulu. Pour exercer le chemin génératif il faut donc un
    épisode qui le demande réellement, pas un seuil abaissé pour l'occasion.

    Mesuré sur cette fixture : rythme mesuré → [0.65, 0.40, 0.20, 0.60],
    soutenu → [0.75, 0.50, 0.30, 0.70], rapide → [0.85, 0.60, 0.40, 0.80].
    Seul le rythme rapide franchit 0.80, et sur deux plans des quatre — ce qui
    donne précisément le mélange fournisseur / local qu'on veut prouver.
    """
    return pipeline.build_episode(
        tmp_path_factory.mktemp("phase13"),
        through_render_spec=True,
        resolution=pipeline.SMALL,
        brief_overrides={"pacing": Pacing.RAPID},
    )


@pytest.fixture(scope="module")
def episode_pose(tmp_path_factory):
    """Un épisode au rythme mesuré : rien n'y justifie de payer un moteur."""
    return pipeline.build_episode(
        tmp_path_factory.mktemp("phase13-pose"),
        through_render_spec=True,
        resolution=pipeline.SMALL,
    )


@pytest.fixture(scope="module")
def rendu(episode, tmp_path_factory):
    """Images réellement calquées, comme en production."""
    from pdz2.engines.imagery import ProceduralImageRenderer

    into = tmp_path_factory.mktemp("phase13-assets")
    return ProceduralImageRenderer().render(
        specs=episode.image_specs, visual_bible=episode.bible, into=into
    )


def _executables(episode, providers=()):
    from pdz2.engines.routing import RenderRouter

    capabilities = [p.get_capabilities() for p in providers]
    return RenderRouter(video_capabilities=capabilities).route(
        episode_id="ep",
        requested=episode.render_specs,
        motion_programs=episode.motion_programs,
        image_specs=episode.image_specs,
    )


# ------------------------------------------------------------------ le port


def test_the_double_really_satisfies_the_port():
    assert isinstance(LocalVideoDouble(), VideoProvider)
    assert isinstance(AlwaysFailingProvider(), VideoProvider)


def test_the_shipped_repository_still_declares_no_video_provider():
    """Le double ne doit jamais devenir une capacité annoncée."""
    assert NO_VIDEO_PROVIDERS == ()


# ------------------------------------------------------- routage vers l'IA


def test_a_reachable_provider_makes_a_generative_strategy_selectable(episode):
    """Sans fournisseur, aucun plan ne peut être génératif ; avec, si."""
    sans = _executables(episode)
    assert all(e.strategy not in {RenderStrategy.DIRECT_I2V} for e in sans.executables)

    avec = _executables(episode, providers=(LocalVideoDouble(),))
    generatifs = [
        e for e in avec.executables if e.strategy is RenderStrategy.DIRECT_I2V
    ]
    assert generatifs, "aucun plan n'a atteint le barreau génératif"
    for executable in generatifs:
        assert executable.provider == "atelier-local"
        assert executable.model == "double-1"


def test_a_measured_pace_never_pays_for_a_provider(episode_pose):
    """Une narration posée se rend entièrement en local, fournisseur ou non."""
    avec = _executables(episode_pose, providers=(LocalVideoDouble(),))
    assert all(e.provider is None for e in avec.executables)
    energies = [
        m.perceptual_target.motion_energy for m in episode_pose.motion_programs
    ]
    assert max(energies) <= 0.70


def test_a_provider_that_cannot_hold_the_shot_is_set_aside(episode):
    """Une limite mesurée et dépassée écarte le fournisseur, et le dit."""
    court = LocalVideoDouble(max_duration_s=0.05)
    outcome = _executables(episode, providers=(court,))
    assert all(e.provider is None for e in outcome.executables)
    raisons = " ".join(d.reason for d in outcome.degradations)
    assert "ne tient pas ce plan" in raisons
    assert "durée" in raisons


def test_an_unreachable_provider_is_never_selected(episode):
    injoignable = LocalVideoDouble(state=CapabilityState.UNKNOWN)
    outcome = _executables(episode, providers=(injoignable,))
    assert all(e.provider is None for e in outcome.executables)


# --------------------------------------------------------------- exécution


@needs_ffmpeg
def test_a_generative_shot_is_executed_by_the_provider(episode, rendu, tmp_path):
    fournisseur = LocalVideoDouble(into=tmp_path)
    route = _executables(episode, providers=(fournisseur,))
    dispatcher = ExecutionDispatcher(providers=(fournisseur,))
    outcome = dispatcher.execute(
        executables=route.executables,
        motion_programs=episode.motion_programs,
        images=rendu.images,
        into=tmp_path,
    )
    par_fournisseur = [
        d for d in outcome.dispatches if d.executor is Executor.PROVIDER
    ]
    assert par_fournisseur, "aucun plan n'est parti chez le fournisseur"
    assert fournisseur.jobs, "le port n'a jamais été appelé"

    for dispatch in par_fournisseur:
        artefact = next(
            a for a in outcome.artifacts if a.shot_id == dispatch.shot_id
        )
        # L'artefact décrit un fichier qui existe vraiment et qu'on a mesuré.
        assert artefact.provider == "atelier-local"
        assert artefact.size_bytes > 0
        assert artefact.duration_s and artefact.duration_s > 0
        assert len(artefact.sha256) == 64


@needs_ffmpeg
def test_local_and_provider_shots_coexist_in_one_run(episode, rendu, tmp_path):
    """Le compilateur mélange les modes dans un même épisode."""
    fournisseur = LocalVideoDouble(into=tmp_path)
    route = _executables(episode, providers=(fournisseur,))
    outcome = ExecutionDispatcher(providers=(fournisseur,)).execute(
        executables=route.executables,
        motion_programs=episode.motion_programs,
        images=rendu.images,
        into=tmp_path,
    )
    comptes = outcome.by_executor
    assert comptes.get(Executor.PROVIDER, 0) >= 1
    assert comptes.get(Executor.LOCAL, 0) >= 1
    assert len(outcome.artifacts) == len(route.executables)


@needs_ffmpeg
def test_a_provider_failure_falls_back_locally_and_declares_it(
    episode, rendu, tmp_path
):
    """Le cas qui compte : la panne ne perd pas la livraison, et se voit."""
    en_panne = AlwaysFailingProvider()
    route = _executables(episode, providers=(en_panne,))
    generatifs = [
        e.shot_id for e in route.executables if e.provider == en_panne.name
    ]
    assert generatifs, "le test ne prouverait rien sans plan génératif"

    outcome = ExecutionDispatcher(providers=(en_panne,)).execute(
        executables=route.executables,
        motion_programs=episode.motion_programs,
        images=rendu.images,
        into=tmp_path,
    )
    # Aucune reprise à l'aveugle : une tentative par plan, pas davantage.
    assert en_panne.appels == len(generatifs)
    # Tous les plans sont livrés malgré la panne.
    assert len(outcome.artifacts) == len(route.executables)
    assert all(d.executor is Executor.LOCAL for d in outcome.dispatches)
    # Et l'écart est déclaré, pas subi en silence.
    assert outcome.degradations
    assert any("aucun fournisseur n'a exécuté" in d.reason for d in outcome.degradations)


@needs_ffmpeg
def test_delivery_needs_no_provider_at_all(episode, rendu, tmp_path):
    """Sans le moindre fournisseur, chaque plan sort quand même."""
    route = _executables(episode)
    outcome = ExecutionDispatcher(providers=()).execute(
        executables=route.executables,
        motion_programs=episode.motion_programs,
        images=rendu.images,
        into=tmp_path,
    )
    assert len(outcome.artifacts) == len(route.executables)
    assert all(d.executor is Executor.LOCAL for d in outcome.dispatches)
    assert all(a.provider is None for a in outcome.artifacts)


def test_a_generative_shot_without_an_image_is_refused(episode, tmp_path):
    fournisseur = LocalVideoDouble(into=tmp_path)
    route = _executables(episode, providers=(fournisseur,))
    if not any(e.provider for e in route.executables):
        pytest.skip("aucun plan génératif à refuser")
    with pytest.raises(DispatchRejected, match="aucune image de départ"):
        ExecutionDispatcher(providers=(fournisseur,)).execute(
            executables=route.executables,
            motion_programs=episode.motion_programs,
            images=[],
            into=tmp_path,
        )


# ------------------------------------------------------------------- repli


@pytest.mark.parametrize(
    "strategie, attendu",
    [
        (RenderStrategy.DIRECT_I2V, RenderStrategy.PROCEDURAL),
        (RenderStrategy.HYBRID, RenderStrategy.PROCEDURAL),
        (RenderStrategy.STILL, RenderStrategy.STILL),
    ],
)
def test_the_fallback_steps_down_the_ladder(strategie, attendu):
    """Un plan génératif perdu vaut mieux en procédural qu'en image fixe."""
    assert _local_fallback(strategie) == attendu
