"""Commandes de la phase 2 : script, voix, timeline.

Trois commandes pour trois étapes, et ce découpage n'est pas cosmétique :

    pdz2 script    DIRECTION → SCRIPT    compile, n'appelle personne
    pdz2 voice     SCRIPT    → VOICE     synthétise, écrit des fichiers
    pdz2 timeline  VOICE     → TIMELINE  mesure ces fichiers, fait autorité

On ne peut pas obtenir une timeline sans que de l'audio existe sur le disque.
La règle VOICE FIRST devient une impossibilité pratique, pas une consigne.

`timeline` **re-mesure** les fichiers au lieu de croire ce que `voice` a
enregistré : si un fichier a bougé entre les deux, l'écart est refusé.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from pdz2.audio import (
    AudioError,
    EspeakSynthesiser,
    MeasuredLine,
    NarrationRecorder,
    VoiceSpec,
    VoiceTimelineBuilder,
    measure_wav,
)
from pdz2.audio.duration import DurationNegotiator
from pdz2.audio.errors import (
    DurationInconsistent,
    SynthesiserUnavailable,
    SynthesisFailed,
)
from pdz2.contracts.direction import DirectorState
from pdz2.contracts.enums import ArtifactKind
from pdz2.contracts.pipeline import Stage
from pdz2.contracts.render import RenderArtifact
from pdz2.contracts.research import TopicRequest
from pdz2.contracts.script import ScriptState
from pdz2.engines.script import ScriptCompiler, ScriptRejected
from pdz2.state import EpisodeStateMachine, TransitionRefused
from pdz2.storage import EpisodeStore

__all__ = ["register", "cmd_script", "cmd_voice", "cmd_timeline"]

DEFAULT_RATE_WPM = 165
"""Débit de départ quand l'opérateur n'en impose pas.

Point de calibration, pas une autorité : la négociation de durée s'en écarte
si la commande l'exige, et `--rate` le fige quand l'opérateur tranche.
"""

LINES_DIR = "audio/lines"
MEASUREMENT_TOLERANCE_S = 0.001


def _open(episode: str) -> tuple[EpisodeStore, EpisodeStateMachine] | None:
    store = EpisodeStore(episode)
    if not store.has_snapshot():
        print(f"aucun épisode dans {episode} — commencer par `pdz2 research`",
              file=sys.stderr)
        return None
    return store, EpisodeStateMachine.resume(store.load_snapshot())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ------------------------------------------------------------------- script


def cmd_script(args: argparse.Namespace) -> int:
    opened = _open(args.episode)
    if opened is None:
        return 1
    store, machine = opened
    if not store.exists("director_state"):
        print("pas de DirectorState — lancer `pdz2 direct` d'abord", file=sys.stderr)
        return 1

    director_state = store.load_as(DirectorState)
    try:
        machine.start(Stage.SCRIPT, reason=f"compilation depuis {director_state.id}")
    except TransitionRefused as refusal:
        print(f"étape refusée : {refusal}", file=sys.stderr)
        return 1

    compiler = ScriptCompiler(speech_rate_wpm=args.rate)
    try:
        outcome = compiler.compile(director_state=director_state, language=args.language)
    except (ScriptRejected, KeyError) as failure:
        machine.fail(Stage.SCRIPT, reason=str(failure))
        store.save_snapshot(machine.snapshot)
        print(f"script refusé : {failure}", file=sys.stderr)
        return 1

    store.save(outcome.state)
    machine.complete(Stage.SCRIPT, artifact_ids=[outcome.state.id])
    store.save_snapshot(machine.snapshot)

    for note in outcome.notes:
        print(note)
    print()
    for line in outcome.state.lines:
        print(
            f"  {line.index}. [{line.function.value:<11} {line.emotion.value:<8} "
            f"énergie {line.energy:.2f} ~{line.estimated_duration_s:>5.2f}s] {line.text[:66]}"
        )
    print(f"\nécrit : {store.path_for('script_state')}")
    return 0


# --------------------------------------------------------------------- voix


def cmd_voice(args: argparse.Namespace) -> int:
    opened = _open(args.episode)
    if opened is None:
        return 1
    store, machine = opened
    if not store.exists("script_state"):
        print("pas de script — lancer `pdz2 script` d'abord", file=sys.stderr)
        return 1

    script = store.load_as(ScriptState)
    synthesiser = EspeakSynthesiser()
    capability = synthesiser.get_capabilities()
    print(f"moteur {capability.provider} : {capability.state.value} — {capability.detail}")

    debit_impose = args.rate is not None
    voice = VoiceSpec(
        voice_id=args.voice,
        rate_wpm=args.rate if debit_impose else DEFAULT_RATE_WPM,
        pitch=args.pitch,
        gap_ms=args.gap,
    )

    # La durée commandée se négocie AVANT la synthèse définitive, sur une
    # calibration réellement synthétisée puis mesurée. Aucune estimation
    # n'entre ici, et la durée officielle restera celle de la VoiceTimeline.
    request = store.load_as(TopicRequest)
    negociateur = DurationNegotiator(synthesiser=synthesiser)
    try:
        policy = negociateur.negotiate(
            script=script,
            voice=voice,
            requested_s=request.target_duration_s,
            workdir=store.root / "audio",
        )
    except (SynthesisFailed, SynthesiserUnavailable, ValueError) as failure:
        print(f"calibration impossible : {failure}", file=sys.stderr)
        return 1
    store.save(policy)
    for note in negociateur.notes:
        print(note)
    print(f"durée : {policy.decision.value} — {policy.rationale}")
    if debit_impose and policy.chosen_rate_wpm != voice.rate_wpm:
        # Un débit passé en argument est une décision d'opérateur : elle prime.
        # La négociation reste consignée, pour que l'écart avec la commande
        # soit lisible plutôt que subi.
        print(
            f"débit imposé à {voice.rate_wpm} mots/min : la négociation "
            f"({policy.chosen_rate_wpm}) n'est pas appliquée"
        )
    elif policy.chosen_rate_wpm != voice.rate_wpm:
        voice = VoiceSpec(
            voice_id=voice.voice_id,
            rate_wpm=policy.chosen_rate_wpm,
            pitch=voice.pitch,
            amplitude=voice.amplitude,
            gap_ms=voice.gap_ms,
        )

    try:
        machine.start(Stage.VOICE, reason=f"synthèse {voice.fingerprint()}")
    except TransitionRefused as refusal:
        print(f"étape refusée : {refusal}", file=sys.stderr)
        return 1

    recorder = NarrationRecorder(synthesiser=synthesiser, voice=voice)
    try:
        outcome = recorder.record(script=script, into=store.root / LINES_DIR)
    except AudioError as failure:
        machine.fail(Stage.VOICE, reason=str(failure))
        store.save_snapshot(machine.snapshot)
        print(f"synthèse refusée : {failure}", file=sys.stderr)
        return 1

    artifacts = []
    for item in outcome.lines:
        artifact = RenderArtifact(
            kind=ArtifactKind.AUDIO,
            path=str(item.audio_path.relative_to(store.root)),
            sha256=_sha256(item.audio_path),
            size_bytes=item.measurement.size_bytes,
            duration_s=item.duration_s,
            provider=item.engine,
            model=item.engine_version,
            source_contract_id=item.line.id,
            latency_s=item.latency_s,
            parent_id=item.line.id,
        )
        store.save(artifact)
        artifacts.append(artifact)

    machine.complete(
        Stage.VOICE,
        artifact_ids=[artifact.id for artifact in artifacts],
        reason=f"{len(artifacts)} répliques synthétisées",
    )
    store.save_snapshot(machine.snapshot)

    for note in outcome.notes:
        print(note)
    print("\ndurées MESURÉES par réplique :")
    for item in outcome.lines:
        estimated = item.line.estimated_duration_s
        drift = item.duration_s - estimated
        print(
            f"  {item.line.index}. mesurée {item.duration_s:>6.3f}s "
            f"(estimation {estimated:>5.2f}s, écart {drift:+.2f}s) "
            f"crête {item.measurement.peak:.2f}"
        )
    print(f"\nfichiers : {store.root / LINES_DIR}")
    print("la timeline officielle se construit avec `pdz2 timeline`")
    return 0


# ----------------------------------------------------------------- timeline


def cmd_timeline(args: argparse.Namespace) -> int:
    opened = _open(args.episode)
    if opened is None:
        return 1
    store, machine = opened
    if not store.exists("script_state"):
        print("pas de script", file=sys.stderr)
        return 1

    script = store.load_as(ScriptState)
    try:
        machine.start(Stage.TIMELINE, reason="mesure de l'audio réel")
    except TransitionRefused as refusal:
        print(f"étape refusée : {refusal}", file=sys.stderr)
        return 1

    try:
        measured = _reload_measured(store, script)
        built = VoiceTimelineBuilder().build(
            script=script,
            measured=measured,
            out_path=store.root / "voice.wav",
        )
    except AudioError as failure:
        machine.fail(Stage.TIMELINE, reason=str(failure))
        store.save_snapshot(machine.snapshot)
        print(f"timeline refusée : {failure}", file=sys.stderr)
        return 1

    store.save(built.timeline)
    machine.complete(Stage.TIMELINE, artifact_ids=[built.timeline.id])
    store.save_snapshot(machine.snapshot)

    timeline = built.timeline
    print(f"audio assemblé : {built.audio_path}")
    print(
        f"durée OFFICIELLE {timeline.total_duration_s:.4f}s "
        f"({timeline.timing_source.value}, {timeline.engine})"
    )
    print(
        f"durée estimée du script  {script.estimated_total_s:.2f}s "
        f"— écart {timeline.total_duration_s - script.estimated_total_s:+.2f}s"
    )
    print("\nsegments :")
    for segment in timeline.segments:
        print(
            f"  {segment.line_index}. {segment.start_s:>7.3f} → {segment.end_s:>7.3f}"
            f"  ({segment.duration_s:.3f}s)"
        )
    print(f"\nécrit : {store.path_for('voice_timeline')}")
    return 0


def _reload_measured(store: EpisodeStore, script: ScriptState) -> list[MeasuredLine]:
    """Recharge les répliques en **re-mesurant** les fichiers sur le disque.

    On ne fait pas confiance à la durée enregistrée à la synthèse : si un
    fichier a été remplacé, tronqué ou réécrit depuis, la timeline doit suivre
    le fichier, pas le souvenir qu'on en avait.
    """
    artifacts = {
        artifact.source_contract_id: artifact
        for artifact in store.load_collection("render_artifact")
        if artifact.kind is ArtifactKind.AUDIO and artifact.source_contract_id
    }
    measured: list[MeasuredLine] = []
    for line in script.lines:
        artifact = artifacts.get(line.id)
        if artifact is None:
            raise DurationInconsistent(
                f"réplique {line.index} sans audio synthétisé — relancer `pdz2 voice`"
            )
        path = store.root / artifact.path
        measurement = measure_wav(path)
        recorded = artifact.duration_s or 0.0
        if abs(measurement.duration_s - recorded) > MEASUREMENT_TOLERANCE_S:
            raise DurationInconsistent(
                f"{path.name} : {measurement.duration_s:.4f}s mesurées contre "
                f"{recorded:.4f}s enregistrées à la synthèse — le fichier a changé"
            )
        measured.append(
            MeasuredLine(
                line=line,
                audio_path=path,
                measurement=measurement,
                engine=artifact.provider or "inconnu",
                engine_version=artifact.model or "inconnue",
                voice_fingerprint=artifact.model or "inconnue",
            )
        )
    return measured


def register(subparsers) -> None:
    script = subparsers.add_parser(
        "script", help="compiler le DirectorState en ScriptState"
    )
    script.add_argument("--episode", required=True)
    script.add_argument("--rate", type=float, default=165.0,
                        help="débit du modèle d'ESTIMATION, en mots/min")
    script.add_argument("--language", default="fr")
    script.set_defaults(func=cmd_script)

    voice = subparsers.add_parser("voice", help="synthétiser la voix, réellement")
    voice.add_argument("--episode", required=True)
    voice.add_argument("--voice", default="fr")
    voice.add_argument(
        "--rate",
        type=int,
        default=None,
        help="débit du moteur TTS ; imposé, il prime sur la négociation de durée",
    )
    voice.add_argument("--pitch", type=int, default=50)
    voice.add_argument("--gap", type=int, default=0)
    voice.set_defaults(func=cmd_voice)

    timeline = subparsers.add_parser(
        "timeline", help="mesurer l'audio et produire la timeline officielle"
    )
    timeline.add_argument("--episode", required=True)
    timeline.set_defaults(func=cmd_timeline)
