"""Commandes de la phase 10 : monter, masteriser, sous-titrer, livrer.

    pdz2 edit      OBSERVATION → EDIT          timeline de montage
    pdz2 master    EDIT        → AUDIO_MASTER  normalisation EBU R128
    pdz2 subtitle  EDIT        → SUBTITLES     cartons calés sur la voix mesurée
    pdz2 deliver   FINAL_QA    → DELIVERY      assemblage, contrôle, MP4
"""

from __future__ import annotations

import argparse
import sys

from pdz2.audio import AudioMasterer, MasteringFailed
from pdz2.contracts.delivery import EditTimeline, MasterArtifact
from pdz2.contracts.enums import ArtifactKind
from pdz2.contracts.pipeline import Stage
from pdz2.contracts.research import TopicRequest
from pdz2.contracts.script import ScriptState, VoiceTimeline
from pdz2.contracts.shots import ShotGraph
from pdz2.contracts.temporal import TemporalPlan
from pdz2.contracts.visual import VisualBible
from pdz2.editing import (
    AssemblyFailed,
    EditCompiler,
    EditRejected,
    SubtitleCompiler,
    SubtitleRejected,
    VideoAssembler,
    to_srt,
)
from pdz2.qa import FinalQa
from pdz2.state import EpisodeStateMachine, TransitionRefused
from pdz2.storage import EpisodeStore

__all__ = ["register", "cmd_edit", "cmd_master", "cmd_subtitle", "cmd_deliver"]

MASTER_AUDIO = "audio_master.wav"
SUBTITLES = "subtitles/episode.srt"
FINAL = "final.mp4"


def _open(episode: str):
    store = EpisodeStore(episode)
    if not store.has_snapshot():
        print(f"aucun épisode dans {episode}", file=sys.stderr)
        return None
    return store, EpisodeStateMachine.resume(store.load_snapshot())


def cmd_edit(args: argparse.Namespace) -> int:
    opened = _open(args.episode)
    if opened is None:
        return 1
    store, machine = opened
    videos = [
        artifact
        for artifact in store.load_collection("render_artifact")
        if artifact.kind is ArtifactKind.VIDEO
    ]
    if not videos:
        print("aucun rendu vidéo — lancer `pdz2 render`", file=sys.stderr)
        return 1
    try:
        machine.start(Stage.EDIT, reason=f"{len(videos)} plans à monter")
    except TransitionRefused as refusal:
        print(f"étape refusée : {refusal}", file=sys.stderr)
        return 1

    request = store.load_as(TopicRequest)
    try:
        outcome = EditCompiler(fps=args.fps).compile(
            episode_id=store.root.name,
            shot_graph=store.load_as(ShotGraph),
            temporal_plan=store.load_as(TemporalPlan),
            voice_timeline=store.load_as(VoiceTimeline),
            video_artifacts=videos,
            voice_artifact_path=MASTER_AUDIO,
            aspect_ratio=request.aspect_ratio,
        )
    except EditRejected as failure:
        machine.fail(Stage.EDIT, reason=str(failure))
        store.save_snapshot(machine.snapshot)
        print(f"montage refusé : {failure}", file=sys.stderr)
        return 1

    store.save(outcome.timeline)
    machine.complete(Stage.EDIT, artifact_ids=[outcome.timeline.id])
    store.save_snapshot(machine.snapshot)
    for note in outcome.notes:
        print(note)
    print(f"\nécrit : {store.path_for('edit_timeline')}")
    return 0


def cmd_master(args: argparse.Namespace) -> int:
    opened = _open(args.episode)
    if opened is None:
        return 1
    store, machine = opened
    voice = store.root / "voice.wav"
    if not voice.is_file():
        print("pas de voix — lancer `pdz2 voice`", file=sys.stderr)
        return 1
    try:
        machine.start(Stage.AUDIO_MASTER, reason="normalisation EBU R128")
    except TransitionRefused as refusal:
        print(f"étape refusée : {refusal}", file=sys.stderr)
        return 1
    try:
        outcome = AudioMasterer().master(
            source=voice, out_path=store.root / MASTER_AUDIO
        )
    except MasteringFailed as failure:
        machine.fail(Stage.AUDIO_MASTER, reason=str(failure))
        store.save_snapshot(machine.snapshot)
        print(f"mastering refusé : {failure}", file=sys.stderr)
        return 1
    machine.complete(
        Stage.AUDIO_MASTER,
        reason=f"{outcome.loudness.integrated_lufs:.2f} LUFS",
    )
    store.save_snapshot(machine.snapshot)
    for note in outcome.notes:
        print(note)
    return 0


def cmd_subtitle(args: argparse.Namespace) -> int:
    opened = _open(args.episode)
    if opened is None:
        return 1
    store, machine = opened
    if not store.exists("script_state") or not store.exists("voice_timeline"):
        print("pas de script ou de voix mesurée", file=sys.stderr)
        return 1
    try:
        machine.start(Stage.SUBTITLES, reason="calage sur la voix mesurée")
    except TransitionRefused as refusal:
        print(f"étape refusée : {refusal}", file=sys.stderr)
        return 1
    try:
        outcome = SubtitleCompiler().compile(
            script=store.load_as(ScriptState),
            voice_timeline=store.load_as(VoiceTimeline),
            typography=store.load_as(VisualBible).typography,
        )
    except SubtitleRejected as failure:
        machine.fail(Stage.SUBTITLES, reason=str(failure))
        store.save_snapshot(machine.snapshot)
        print(f"sous-titres refusés : {failure}", file=sys.stderr)
        return 1

    store.save(outcome.track)
    srt = store.root / SUBTITLES
    srt.parent.mkdir(parents=True, exist_ok=True)
    srt.write_text(to_srt(outcome.track), encoding="utf-8")
    machine.complete(Stage.SUBTITLES, artifact_ids=[outcome.track.id])
    store.save_snapshot(machine.snapshot)
    for note in outcome.notes:
        print(note)
    print(f"\nécrit : {srt}")
    return 0


def cmd_deliver(args: argparse.Namespace) -> int:
    opened = _open(args.episode)
    if opened is None:
        return 1
    store, machine = opened
    if not store.exists("edit_timeline"):
        print("pas de montage — lancer `pdz2 edit`", file=sys.stderr)
        return 1
    audio = store.root / MASTER_AUDIO
    if not audio.is_file():
        print("pas d'audio masterisé — lancer `pdz2 master`", file=sys.stderr)
        return 1

    timeline = store.load_as(EditTimeline)
    request = store.load_as(TopicRequest)
    clip_paths = {
        artifact.id: store.root / "renders" / artifact.path
        for artifact in store.load_collection("render_artifact")
        if artifact.kind is ArtifactKind.VIDEO
    }
    srt = store.root / SUBTITLES
    final = store.root / FINAL

    try:
        machine.start(Stage.FINAL_QA, reason="assemblage puis contrôle du livrable")
    except TransitionRefused as refusal:
        print(f"étape refusée : {refusal}", file=sys.stderr)
        return 1

    try:
        assembly = VideoAssembler().assemble(
            timeline=timeline,
            clip_paths=clip_paths,
            audio_path=audio,
            out_path=final,
            subtitle_path=srt if srt.is_file() else None,
            burn_subtitles=args.burn_subtitles,
        )
    except AssemblyFailed as failure:
        machine.fail(Stage.FINAL_QA, reason=str(failure))
        store.save_snapshot(machine.snapshot)
        print(f"assemblage refusé : {failure}", file=sys.stderr)
        return 1

    for note in assembly.notes:
        print(note)

    from pdz2.audio.mastering import measure_loudness
    from pdz2.contracts.common import Resolution

    loudness = measure_loudness(audio)
    master = MasterArtifact(
        episode_id=store.root.name,
        edit_timeline_id=timeline.id,
        video_path=FINAL,
        sha256=assembly.sha256,
        size_bytes=assembly.size_bytes,
        duration_s=assembly.duration_s,
        resolution=Resolution(width=assembly.width, height=assembly.height),
        aspect_ratio=request.aspect_ratio,
        fps=int(round(assembly.fps)),
        loudness=loudness,
        subtitles_path=SUBTITLES if srt.is_file() else None,
        delivered=False,
        parent_id=timeline.id,
    )
    qa = FinalQa().check(
        master_path=final,
        timeline=timeline,
        loudness=loudness,
        aspect_ratio=request.aspect_ratio,
        master_artifact_id=master.id,
        target_duration_s=request.target_duration_s,
    )
    store.save(qa.report)

    print()
    for check in qa.report.checks:
        state = "ok " if check.passed else "NON"
        print(
            f"  [{state} {check.severity.value:<8}] {check.check_id} "
            f"observé {check.observed} attendu {check.expected}"
        )
        if not check.passed and check.detail:
            print(f"        {check.detail}")

    if not qa.deliverable:
        failing = [c.check_id for c in qa.report.checks if not c.passed]
        machine.fail(Stage.FINAL_QA, reason=f"QA finale : {', '.join(failing)}")
        store.save_snapshot(machine.snapshot)
        print("\nREFUSÉ À LA LIVRAISON.", file=sys.stderr)
        return 1

    machine.complete(Stage.FINAL_QA, artifact_ids=[qa.report.id])
    delivered = MasterArtifact(
        **(master.model_dump() | {"delivered": True, "final_qa_report_id": qa.report.id})
    )
    store.save(delivered)
    machine.start(Stage.DELIVERY, reason="master scellé")
    machine.complete(Stage.DELIVERY, artifact_ids=[delivered.id])
    store.save_snapshot(machine.snapshot)

    print(f"\n{qa.notes[-1]}")
    print(f"\nLIVRÉ : {final}")
    print(
        f"  {delivered.duration_s:.2f}s  {delivered.resolution.width}×"
        f"{delivered.resolution.height}  {delivered.fps} i/s  "
        f"{delivered.size_bytes // 1024} Kio"
    )
    print(f"  loudness {loudness.integrated_lufs:.2f} LUFS, "
          f"crête {loudness.true_peak_dbtp:.2f} dBTP")
    return 0


def register(subparsers) -> None:
    edit = subparsers.add_parser("edit", help="composer la timeline de montage")
    edit.add_argument("--episode", required=True)
    edit.add_argument("--fps", type=int, default=30)
    edit.set_defaults(func=cmd_edit)

    master = subparsers.add_parser("master", help="normaliser la voix (EBU R128)")
    master.add_argument("--episode", required=True)
    master.set_defaults(func=cmd_master)

    subtitle = subparsers.add_parser("subtitle", help="produire les sous-titres")
    subtitle.add_argument("--episode", required=True)
    subtitle.set_defaults(func=cmd_subtitle)

    deliver = subparsers.add_parser("deliver", help="assembler, contrôler, livrer")
    deliver.add_argument("--episode", required=True)
    deliver.add_argument(
        "--burn-subtitles",
        action="store_true",
        dest="burn_subtitles",
        help="incruster les sous-titres dans l'image (ré-encode la vidéo)",
    )
    deliver.set_defaults(func=cmd_deliver)
