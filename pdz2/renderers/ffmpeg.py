"""Encapsulation minimale de ffmpeg.

ffmpeg est une dépendance système, sondée comme n'importe quel adaptateur :
absent, les renderers se déclarent `UNAVAILABLE` avec la raison, et rien ne
les contourne en silence.

Cette couche ne fait qu'une chose : transformer une suite d'images en un
fichier vidéo, et lire ce qu'un fichier vidéo contient réellement. Toute la
décision de *quoi* dessiner est ailleurs.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from pdz2.contracts.capability import ProviderCapability

__all__ = [
    "FfmpegUnavailable",
    "encode_raw_frames",
    "EncodingFailed",
    "VideoProbe",
    "ffmpeg_capability",
    "encode_frames",
    "probe_video",
    "FFMPEG_TIMEOUT_S",
]

FFMPEG_TIMEOUT_S = 600.0
_PROBE_TIMEOUT_S = 30.0


class FfmpegUnavailable(RuntimeError):
    """Le binaire ffmpeg n'est pas disponible sur cette machine."""


class EncodingFailed(RuntimeError):
    """ffmpeg a été appelé et n'a pas rendu de vidéo exploitable."""


@dataclass(frozen=True)
class VideoProbe:
    """Ce qu'un fichier vidéo contient réellement, lu par ffprobe."""

    path: Path
    duration_s: float
    width: int
    height: int
    fps: float
    frame_count: int
    size_bytes: int
    codec: str
    has_audio: bool


def ffmpeg_capability(binary: str = "ffmpeg") -> ProviderCapability:
    """Sonde réellement ffmpeg. Ne devine jamais son état."""
    path = shutil.which(binary)
    if path is None:
        return ProviderCapability.measured(
            "ffmpeg",
            reachable=False,
            method=f"which({binary})",
            detail=(
                f"binaire {binary!r} absent du PATH — installer le paquet "
                "système « ffmpeg »"
            ),
            requires_network=False,
        )
    try:
        probe = subprocess.run(
            [binary, "-version"],
            capture_output=True,
            text=True,
            timeout=_PROBE_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return ProviderCapability.measured(
            "ffmpeg",
            reachable=False,
            method=f"{binary} -version",
            detail=f"{binary} injoignable : {error}",
            requires_network=False,
        )
    if probe.returncode != 0:
        return ProviderCapability.measured(
            "ffmpeg",
            reachable=False,
            method=f"{binary} -version",
            detail=f"{binary} -version a rendu {probe.returncode}",
            requires_network=False,
        )
    version = probe.stdout.splitlines()[0] if probe.stdout else "version inconnue"
    return ProviderCapability.measured(
        "ffmpeg",
        reachable=True,
        method=f"{binary} -version",
        detail=f"{version} en {path}",
        requires_network=False,
    )


def encode_frames(
    *,
    frames_dir: Path,
    pattern: str,
    fps: int,
    out_path: Path,
    binary: str = "ffmpeg",
    timeout_s: float = FFMPEG_TIMEOUT_S,
) -> Path:
    """Encode une suite d'images en H.264. Toute anomalie est une erreur."""
    capability = ffmpeg_capability(binary)
    if not capability.usable:
        raise FfmpegUnavailable(capability.detail)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    argv = [
        binary,
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        "-framerate", str(fps),
        "-i", str(frames_dir / pattern),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        # Reproductibilité : sans cela l'encodeur inscrit la date du jour et
        # deux rendus identiques donnent des octets différents.
        "-fflags", "+bitexact",
        "-flags:v", "+bitexact",
        "-movflags", "+faststart",
        str(out_path),
    ]
    try:
        run = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout_s, check=False
        )
    except subprocess.TimeoutExpired as error:
        raise EncodingFailed(f"ffmpeg : dépassement de {timeout_s:g}s") from error
    except OSError as error:
        raise EncodingFailed(f"ffmpeg : appel impossible ({error})") from error
    if run.returncode != 0:
        detail = (run.stderr or run.stdout or "").strip()[:400]
        raise EncodingFailed(f"ffmpeg : code {run.returncode} — {detail}")
    if not out_path.is_file() or out_path.stat().st_size == 0:
        raise EncodingFailed(f"ffmpeg : aucun fichier écrit en {out_path}")
    return out_path


def encode_raw_frames(
    *,
    frames: Iterable[bytes],
    width: int,
    height: int,
    fps: int,
    out_path: Path,
    binary: str = "ffmpeg",
    timeout_s: float = FFMPEG_TIMEOUT_S,
) -> Path:
    """Encode des images RGB brutes poussées dans l'entrée de ffmpeg.

    Écrire chaque image en PNG puis la relire coûte plusieurs fois le temps de
    l'encodage lui-même, pour un résultat identique. Le tube supprime à la fois
    la compression intermédiaire et les allers-retours disque.
    """
    capability = ffmpeg_capability(binary)
    if not capability.usable:
        raise FfmpegUnavailable(capability.detail)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    argv = [
        binary,
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        "-f", "rawvideo",
        "-pixel_format", "rgb24",
        "-video_size", f"{width}x{height}",
        "-framerate", str(fps),
        "-i", "-",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        # Reproductibilité : sans cela l'encodeur inscrit la date du jour.
        "-fflags", "+bitexact",
        "-flags:v", "+bitexact",
        "-movflags", "+faststart",
        str(out_path),
    ]
    try:
        process = subprocess.Popen(
            argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
    except OSError as error:
        raise EncodingFailed(f"ffmpeg : appel impossible ({error})") from error

    try:
        assert process.stdin is not None
        for frame in frames:
            process.stdin.write(frame)
        process.stdin.close()
    except BrokenPipeError as error:
        process.kill()
        stderr = (process.stderr.read().decode(errors="replace") if process.stderr else "")
        raise EncodingFailed(f"ffmpeg a fermé le tube : {stderr[:400]}") from error
    except OSError as error:
        process.kill()
        raise EncodingFailed(f"ffmpeg : écriture impossible ({error})") from error

    # `communicate` tenterait de vider une entrée déjà fermée : on attend et on
    # lit la sortie d'erreur à la main.
    stderr = process.stderr.read() if process.stderr else b""
    if process.stdout is not None:
        process.stdout.close()
    if process.stderr is not None:
        process.stderr.close()
    try:
        process.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired as error:
        process.kill()
        raise EncodingFailed(f"ffmpeg : dépassement de {timeout_s:g}s") from error
    if process.returncode != 0:
        raise EncodingFailed(
            f"ffmpeg : code {process.returncode} — "
            f"{stderr.decode(errors='replace').strip()[:400]}"
        )
    if not out_path.is_file() or out_path.stat().st_size == 0:
        raise EncodingFailed(f"ffmpeg : aucun fichier écrit en {out_path}")
    return out_path


def probe_video(path: Path, binary: str = "ffprobe") -> VideoProbe:
    """Lit ce que le fichier contient. Aucune valeur n'est déduite du contexte."""
    target = Path(path)
    if not target.is_file():
        raise EncodingFailed(f"fichier vidéo absent : {target}")
    argv = [
        binary,
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(target),
    ]
    try:
        run = subprocess.run(
            argv, capture_output=True, text=True, timeout=_PROBE_TIMEOUT_S, check=False
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise EncodingFailed(f"ffprobe injoignable : {error}") from error
    if run.returncode != 0:
        raise EncodingFailed(f"ffprobe : code {run.returncode} sur {target.name}")

    payload = json.loads(run.stdout)
    streams = payload.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None:
        raise EncodingFailed(f"{target.name} : aucun flux vidéo")

    rate = video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1"
    numerator, _, denominator = rate.partition("/")
    fps = float(numerator) / float(denominator or 1) if float(denominator or 1) else 0.0
    frames = video.get("nb_frames")
    duration = float(payload.get("format", {}).get("duration", 0.0) or 0.0)
    frame_count = int(frames) if frames else int(round(duration * fps))
    return VideoProbe(
        path=target,
        duration_s=duration,
        width=int(video["width"]),
        height=int(video["height"]),
        fps=round(fps, 6),
        frame_count=frame_count,
        size_bytes=target.stat().st_size,
        codec=video.get("codec_name", "inconnu"),
        has_audio=any(s.get("codec_type") == "audio" for s in streams),
    )
