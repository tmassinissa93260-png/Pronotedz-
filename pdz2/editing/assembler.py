"""Assemblage final : de la timeline de montage au MP4 livrable.

Trois opérations, dans cet ordre, et aucune de plus :

    1. concaténer les plans rendus, sans ré-encoder ce qui n'en a pas besoin
    2. y coller la voix masterisée
    3. incruster les sous-titres, si on les demande

La durée du fichier produit est **re-mesurée** et confrontée à celle du
montage. Un écart au-delà de la tolérance est refusé : livrer une vidéo dont
la durée ne correspond pas à sa timeline, c'est livrer un décalage.
"""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from pdz2.contracts.delivery import EditTimeline, TrackKind
from pdz2.renderers.ffmpeg import EncodingFailed, ffmpeg_capability, probe_video

__all__ = ["VideoAssembler", "AssemblyOutcome", "AssemblyFailed", "DURATION_TOLERANCE_S"]

DURATION_TOLERANCE_S = 0.15
"""Écart toléré entre le montage et le fichier produit."""

_TIMEOUT_S = 900.0


class AssemblyFailed(RuntimeError):
    """L'assemblage a échoué. La raison est nommée."""


@dataclass
class AssemblyOutcome:
    path: Path
    duration_s: float
    width: int
    height: int
    fps: float
    size_bytes: int
    sha256: str
    has_audio: bool
    has_burned_subtitles: bool
    notes: list[str] = field(default_factory=list)


@dataclass
class VideoAssembler:
    binary: str = "ffmpeg"
    crf: int = 20

    def assemble(
        self,
        *,
        timeline: EditTimeline,
        clip_paths: dict[str, Path],
        audio_path: Path,
        out_path: Path,
        subtitle_path: Path | None = None,
        burn_subtitles: bool = False,
    ) -> AssemblyOutcome:
        capability = ffmpeg_capability(self.binary)
        if not capability.usable:
            raise AssemblyFailed(capability.detail)
        if not audio_path.is_file():
            raise AssemblyFailed(f"audio masterisé absent : {audio_path}")

        video_track = next(
            (track for track in timeline.tracks if track.kind is TrackKind.VIDEO),
            None,
        )
        if video_track is None or not video_track.clips:
            raise AssemblyFailed("montage sans clip vidéo")

        ordered = sorted(video_track.clips, key=lambda clip: clip.timeline_in_s)
        missing = [
            clip.artifact_id for clip in ordered if clip.artifact_id not in clip_paths
        ]
        if missing:
            raise AssemblyFailed(f"clips sans fichier : {missing}")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        concat_list = out_path.parent / f".{out_path.stem}-concat.txt"
        concat_list.write_text(
            "".join(
                f"file '{clip_paths[clip.artifact_id].resolve()}'\n"
                for clip in ordered
            ),
            encoding="utf-8",
        )

        argv = [
            self.binary, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-i", str(audio_path),
        ]
        filters = []
        if burn_subtitles and subtitle_path is not None:
            if not subtitle_path.is_file():
                raise AssemblyFailed(f"sous-titres absents : {subtitle_path}")
            escaped = str(subtitle_path.resolve()).replace(":", r"\:")
            filters.append(
                f"subtitles='{escaped}':force_style="
                f"'FontSize=18,Outline=2,MarginV=60'"
            )
        if filters:
            argv += ["-vf", ",".join(filters)]
            argv += ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(self.crf)]
        else:
            argv += ["-c:v", "copy"]
        argv += [
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            "-movflags", "+faststart",
            str(out_path),
        ]

        try:
            run = subprocess.run(
                argv, capture_output=True, text=True, timeout=_TIMEOUT_S, check=False
            )
        except subprocess.TimeoutExpired as error:
            raise AssemblyFailed(f"dépassement de {_TIMEOUT_S:g}s") from error
        finally:
            concat_list.unlink(missing_ok=True)
        if run.returncode != 0:
            raise AssemblyFailed(
                f"ffmpeg : code {run.returncode} — {run.stderr.strip()[:400]}"
            )

        try:
            probe = probe_video(out_path)
        except EncodingFailed as error:
            raise AssemblyFailed(str(error)) from error

        drift = abs(probe.duration_s - timeline.duration_s)
        if drift > DURATION_TOLERANCE_S:
            raise AssemblyFailed(
                f"le master dure {probe.duration_s:.3f}s pour un montage de "
                f"{timeline.duration_s:.3f}s (écart {drift * 1000:.0f} ms) : "
                "livrer cela serait livrer un décalage"
            )
        if not probe.has_audio:
            raise AssemblyFailed("le master n'a pas de piste audio")

        return AssemblyOutcome(
            path=out_path,
            duration_s=probe.duration_s,
            width=probe.width,
            height=probe.height,
            fps=probe.fps,
            size_bytes=probe.size_bytes,
            sha256=hashlib.sha256(out_path.read_bytes()).hexdigest(),
            has_audio=True,
            has_burned_subtitles=bool(filters),
            notes=[
                f"{len(ordered)} plans concaténés"
                + ("" if filters else " sans ré-encodage vidéo"),
                f"{probe.duration_s:.3f}s, {probe.width}×{probe.height}, "
                f"{probe.fps:.2f} i/s, {probe.size_bytes // 1024} Kio",
                "sous-titres incrustés" if filters else "sous-titres en fichier séparé",
            ],
        )
