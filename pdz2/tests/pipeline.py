"""Chaîne complète jusqu'à la phase 3, pour les tests.

L'audio est produit par des sinusoïdes de durée choisie plutôt que par le
moteur de synthèse : ce sont de **vrais fichiers WAV**, réellement mesurés par
la même chaîne, mais dont la durée est maîtrisée par le test. Les tests de
découpage portent ainsi sur le découpage, pas sur la disponibilité d'un
binaire système — et un test qui veut allonger l'audio le fait sans détour.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from pdz2.audio import MeasuredLine, VoiceTimelineBuilder, measure_wav, write_wav
from pdz2.contracts.direction import DirectorBrief, DirectorState
from pdz2.contracts.research import ResearchState, TopicRequest
from pdz2.contracts.script import ScriptState, VoiceTimeline
from pdz2.contracts.temporal import TemporalPlan
from pdz2.contracts.visual import VisualBible
from pdz2.engines.direction import DirectorCompiler
from pdz2.engines.imagery import ImageSpecCompiler
from pdz2.engines.motion import MotionCompiler
from pdz2.engines.renderspec import RenderSpecCompiler
from pdz2.engines.research import LocalCorpusProvider, ResearchEngine
from pdz2.engines.script import ScriptCompiler
from pdz2.engines.shots import ShotGraphCompiler
from pdz2.engines.temporal import TemporalDirector
from pdz2.engines.validation import StaticValidator
from pdz2.engines.visual import VisualBibleCompiler
from pdz2.tests.fixtures import CORPUS
from pdz2.tests.test_audio_measurement import tone

TOPIC = "Comment fonctionne une voiture électrique ?"
DEFAULT_LINE_SECONDS = 4.0


@dataclass
class Episode:
    """Tous les contrats d'un épisode mené jusqu'au ShotGraph."""

    request: TopicRequest
    research: ResearchState
    brief: DirectorBrief
    director_state: DirectorState
    script: ScriptState
    timeline: VoiceTimeline
    bible: VisualBible
    temporal_plan: TemporalPlan
    graph: object
    camera_programs: list
    motion_programs: list | None = None
    image_specs: list | None = None
    render_specs: list | None = None
    validation: object | None = None

    def claim(self, fragment: str):
        return next(c for c in self.research.claims if fragment in c.text)


def build_research(duration_s: float = 45.0) -> tuple[TopicRequest, ResearchState]:
    request = TopicRequest(topic=TOPIC, target_duration_s=duration_s)
    research = ResearchEngine(providers=[LocalCorpusProvider(CORPUS)]).run(request).state
    return request, research


def build_brief(request, research, fragments, **overrides) -> DirectorBrief:
    """Brief dont chaque preuve visuelle est **propre à son affirmation**.

    Une preuve générique recopiée d'un plan à l'autre rendrait les tests de
    propagation aveugles : changer d'affirmation ne changerait rien de visible.
    """
    from pdz2.tests.test_direction import _brief, _claim, _proof

    proofs = []
    for fragment in fragments:
        claim = _claim(research, fragment)
        proofs.append(
            _proof(
                claim.id,
                causal_mechanism=f"Mécanisme de « {fragment} » : {claim.text[:70]}",
                evidence_required=f"Voir ce que « {fragment} » produit à l'écran.",
                visual_proof=(
                    f"Plan sur « {fragment} » : {claim.text[:80]}"
                ),
            )
        )
    payload = {"visual_proofs": proofs} | overrides
    return _brief(request, research, [], **payload)


def synthesise(
    script: ScriptState,
    directory: Path,
    durations: list[float] | None = None,
) -> VoiceTimeline:
    """Écrit un WAV réel par réplique, puis mesure et assemble."""
    directory.mkdir(parents=True, exist_ok=True)
    spans = durations or [DEFAULT_LINE_SECONDS] * len(script.lines)
    if len(spans) != len(script.lines):
        raise ValueError("autant de durées que de répliques attendues")
    measured: list[MeasuredLine] = []
    for line, span in zip(script.lines, spans, strict=True):
        path = write_wav(tone(span), directory / f"line-{line.index:03d}.wav")
        measured.append(
            MeasuredLine(
                line=line,
                audio_path=path,
                measurement=measure_wav(path),
                engine="test-tone",
                engine_version="1.0",
                voice_fingerprint="tone@1",
            )
        )
    return VoiceTimelineBuilder().build(
        script=script, measured=measured, out_path=directory / "voice.wav"
    ).timeline


def build_episode(
    directory: Path,
    *,
    fragments: tuple[str, ...] = ("stator", "rotor porte"),
    durations: list[float] | None = None,
    target_duration_s: float = 45.0,
    brief_overrides: dict | None = None,
    through_render_spec: bool = False,
) -> Episode:
    """Chaîne complète : recherche → réalisation → script → voix → plans."""
    request, research = build_research(target_duration_s)
    brief = build_brief(request, research, fragments, **(brief_overrides or {}))
    director_state = DirectorCompiler().compile(
        request=request, research=research, brief=brief
    ).state
    script = ScriptCompiler().compile(director_state=director_state).state
    timeline = synthesise(script, directory / "audio", durations)
    bible = VisualBibleCompiler().compile(
        director_state=director_state, brief=brief
    ).bible
    plan = TemporalDirector().plan(
        director_state=director_state, script=script, timeline=timeline
    ).plan
    shots = ShotGraphCompiler().compile(
        director_state=director_state,
        temporal_plan=plan,
        visual_bible=bible,
        script=script,
        research=research,
        request=request,
    )
    episode = Episode(
        request=request,
        research=research,
        brief=brief,
        director_state=director_state,
        script=script,
        timeline=timeline,
        bible=bible,
        temporal_plan=plan,
        graph=shots.graph,
        camera_programs=shots.camera_programs,
    )
    return with_render_specs(episode) if through_render_spec else episode


def with_render_specs(episode: Episode) -> Episode:
    """Prolonge un épisode jusqu'aux demandes de rendu validées (phase 4)."""
    motions = MotionCompiler().compile(
        shot_graph=episode.graph,
        temporal_plan=episode.temporal_plan,
        camera_programs=episode.camera_programs,
        director_state=episode.director_state,
        visual_bible=episode.bible,
    ).programs
    images = ImageSpecCompiler().compile(
        shot_graph=episode.graph,
        visual_bible=episode.bible,
        director_state=episode.director_state,
        request=episode.request,
    ).specs
    specs = RenderSpecCompiler().compile(
        shot_graph=episode.graph,
        motion_programs=motions,
        camera_programs=episode.camera_programs,
        image_specs=images,
        request=episode.request,
    ).specs
    report = StaticValidator().validate(
        episode_id="test-episode",
        shot_graph=episode.graph,
        requested=specs,
        motion_programs=motions,
        camera_programs=episode.camera_programs,
        image_specs=images,
        request=episode.request,
    ).report
    return replace(
        episode,
        motion_programs=motions,
        image_specs=images,
        render_specs=specs,
        validation=report,
    )


def recompile_shots(episode: Episode, **replacements) -> Episode:
    """Recompile le découpage en remplaçant un maillon, et rien d'autre.

    C'est l'outil des tests de propagation : changer une seule entrée et
    observer ce qui bouge en aval.
    """
    updated = replace(episode, **replacements)
    plan = TemporalDirector().plan(
        director_state=updated.director_state,
        script=updated.script,
        timeline=updated.timeline,
    ).plan
    shots = ShotGraphCompiler().compile(
        director_state=updated.director_state,
        temporal_plan=plan,
        visual_bible=updated.bible,
        script=updated.script,
        research=updated.research,
        request=updated.request,
    )
    return replace(
        updated,
        temporal_plan=plan,
        graph=shots.graph,
        camera_programs=shots.camera_programs,
    )
