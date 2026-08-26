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
from pdz2.contracts.capacity import CapabilityMatrix
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


def _executables(episode, providers=(), animes=8):
    from pdz2.engines.routing import RenderRouter

    capabilities = [p.get_capabilities() for p in providers]
    # Retenir un fournisseur exige de montrer sur quoi on s'est fondé — et,
    # depuis que le compte porte du crédit, une autorisation de dépense :
    # `animated_shots_max` vaut zéro par défaut, et zéro veut dire zéro appel
    # payant. Ces tests l'ouvrent explicitement, comme le ferait un opérateur.
    return RenderRouter(
        video_capabilities=capabilities,
        capability_matrix=CapabilityMatrix() if providers else None,
        animated_shots_max=animes,
    ).route(
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


def test_nothing_is_paid_for_without_an_authorisation(episode_pose):
    """Zéro plan animé autorisé : aucun appel payant, fournisseur ou non.

    C'est la garantie qui a remplacé « une narration posée se rend entièrement
    en local ». L'ancienne reposait sur `_GENERATIVE_ABOVE = 0.80`, un seuil
    d'énergie de **caméra** — et c'était le mauvais critère : un mécanisme qui
    doit tourner justifie le génératif quelle que soit la vitesse de
    l'appareil. Le seuil n'a d'ailleurs jamais été franchi en production, ce
    qui rendait l'animation inatteignable.

    La borne n'est donc plus une énergie mais une **autorisation de dépense**,
    et elle vaut zéro tant que personne n'a écrit un nombre.
    """
    avec = _executables(episode_pose, providers=(LocalVideoDouble(),), animes=0)
    assert all(e.provider is None for e in avec.executables)
    energies = [
        m.perceptual_target.motion_energy for m in episode_pose.motion_programs
    ]
    assert max(energies) <= 0.70


def test_a_mechanism_reaches_the_generative_even_at_a_measured_pace(episode_pose):
    """Ce que l'ancien seuil d'énergie interdisait, et qu'il ne devait pas.

    Le spectateur du run #8 l'a dit en une phrase : « moteur qui tourne,
    électricité qui bouge ». Un plan qui démontre un mécanisme a besoin que le
    sujet bouge dans le cadre, et aucune stratégie locale ne sait le faire.
    L'énergie de caméra n'a rien à dire là-dessus.
    """
    from pdz2.contracts.motion import MotionPrimitive
    from pdz2.engines.routing.router import _MECHANICAL

    mecaniques = {
        motion.shot_id
        for motion in episode_pose.motion_programs
        if motion.subject_motion.primitive in _MECHANICAL
    }
    if not mecaniques:
        pytest.skip("cette fixture ne démontre aucun mécanisme")

    avec = _executables(episode_pose, providers=(LocalVideoDouble(),), animes=8)
    animes = {e.shot_id for e in avec.executables if e.provider is not None}
    assert animes & mecaniques, (
        "aucun plan de mécanisme n'a atteint le génératif malgré l'autorisation"
    )
    assert MotionPrimitive.STATIC not in {
        m.subject_motion.primitive
        for m in episode_pose.motion_programs
        if m.shot_id in animes
    }, "un plan sans mouvement de sujet a été payé"


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
    """Le compilateur mélange les modes dans un même épisode.

    Le mélange vient désormais du **plafond** et non d'un seuil d'énergie :
    deux plans animés autorisés sur un épisode qui en demanderait davantage,
    et le reste se rend en local. C'est le cas nominal une fois du crédit
    déposé — on paie ce qu'on a décidé de payer, pas ce que le rythme décide.
    """
    fournisseur = LocalVideoDouble(into=tmp_path)
    route = _executables(episode, providers=(fournisseur,), animes=2)
    outcome = ExecutionDispatcher(providers=(fournisseur,)).execute(
        executables=route.executables,
        motion_programs=episode.motion_programs,
        images=rendu.images,
        into=tmp_path,
        animated_shots_max=2,
    )
    comptes = outcome.by_executor
    assert comptes.get(Executor.PROVIDER, 0) >= 1
    assert comptes.get(Executor.PROVIDER, 0) <= 2, "le plafond n'a pas été tenu"
    assert comptes.get(Executor.LOCAL, 0) >= 1
    assert len(outcome.artifacts) == len(route.executables)


@needs_ffmpeg
def test_the_dispatcher_holds_the_ceiling_even_if_the_plan_does_not(
    episode, rendu, tmp_path
):
    """Deuxième verrou : un exécutable génératif de trop ne part pas.

    Le routeur planifie, le répartiteur exécute — et il ne fait pas confiance
    sur parole à ce qu'il reçoit quand la conséquence est une facture. Ici le
    routage en autorise huit et le répartiteur n'en laisse passer qu'un.
    """
    fournisseur = LocalVideoDouble(into=tmp_path)
    route = _executables(episode, providers=(fournisseur,), animes=8)
    prevus = sum(1 for e in route.executables if e.provider is not None)
    assert prevus > 1, "le routage n'a pas prévu assez de plans génératifs"

    outcome = ExecutionDispatcher(providers=(fournisseur,)).execute(
        executables=route.executables,
        motion_programs=episode.motion_programs,
        images=rendu.images,
        into=tmp_path,
        animated_shots_max=1,
    )
    assert outcome.by_executor.get(Executor.PROVIDER, 0) == 1
    assert len(fournisseur.jobs) == 1, "un appel payant de trop est parti"
    assert any("plafond de plans animés atteint" in n for n in outcome.notes)


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
