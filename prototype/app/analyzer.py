"""Analyse de ce que l'utilisateur produit lui-meme.

Deux usages :
  · une IMAGE reelle -> ce qui y est vraiment -> prompt d'animation ajuste
  · les VIDEOS renvoyees -> ce qu'elles montrent vraiment -> timeline

Rien n'est suppose : on ne decrit que ce que l'analyse rapporte.
"""

from __future__ import annotations

import base64
import mimetypes
import shutil
import subprocess
from pathlib import Path

from . import config, prompts
from .models import MOTION_INTENTS, Shot, StoryboardError, VideoAnalysis
from .openai_client import OpenAIError, chat_json

# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------


def analyze_image(image: Path | str, visual_concept: str) -> dict:
    """Ce qui est visible dans l'image, et si l'element pedagogique y est."""
    brut = chat_json(config.OPENAI_VISION_MODEL, [
        {"role": "system", "content": prompts.IMAGE_ANALYSIS_SYSTEM},
        {"role": "user", "content": [
            {"type": "text", "text": prompts.image_analysis_user(visual_concept)},
            {"type": "image_url", "image_url": {"url": image_payload(image)}},
        ]},
    ])
    for champ in ("visible_subjects", "composition", "camera", "lighting"):
        if not brut.get(champ):
            raise OpenAIError(f"analyse d'image inexploitable : '{champ}' vide")
    return brut


def refine_animation(shot: Shot, analyse: dict) -> dict:
    """Reecrit le prompt d'animation a partir de l'image REELLE."""
    bloc = "\n".join(f"{k}: {v}" for k, v in analyse.items())
    brut = chat_json(config.OPENAI_MODEL, [
        {"role": "system", "content": prompts.ANIMATION_SYSTEM},
        {"role": "user", "content": prompts.animation_user(
            shot.voice, shot.educational_function, shot.visual_concept, bloc)},
    ])
    intent = str(brut.get("motion_intent") or "").strip()
    if intent not in MOTION_INTENTS:
        raise OpenAIError(f"motion_intent '{intent}' hors vocabulaire")
    if len(str(brut.get("animation_prompt") or "").strip()) < 80:
        raise OpenAIError("prompt d'animation trop court pour etre pedagogique")
    return brut


# ---------------------------------------------------------------------------
# Videos renvoyees
# ---------------------------------------------------------------------------


def ffprobe_duration(video: Path) -> float:
    """Duree reelle du fichier, mesuree. 0.0 si ffprobe est absent."""
    if not shutil.which("ffprobe"):
        return 0.0
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(video)],
            capture_output=True, text=True, timeout=60)
        return round(float(out.stdout.strip()), 3)
    except (ValueError, subprocess.SubprocessError):
        return 0.0


def sample_frames(video: Path, into: Path, count: int = 4) -> list[Path]:
    """Quelques images prises dans l'ordre : c'est ce qu'on donne a analyser.

    Un modele de vision lit des images, pas un flux video. Echantillonner
    permet de juger ce qui BOUGE entre le debut et la fin.
    """
    if not shutil.which("ffmpeg"):
        raise OpenAIError(
            "ffmpeg est absent : impossible d'echantillonner la video.\n"
            "  Installe-le (apt install ffmpeg, brew install ffmpeg) et relance.")
    into.mkdir(parents=True, exist_ok=True)
    for ancienne in into.glob("frame_*.jpg"):
        ancienne.unlink()
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(video),
         "-vf", f"select='not(mod(n\\,{max(1, count)}))',scale=512:-1",
         "-vsync", "vfr", "-frames:v", str(count), str(into / "frame_%02d.jpg")],
        check=False, capture_output=True, timeout=300)
    images = sorted(into.glob("frame_*.jpg"))
    if not images:
        raise OpenAIError(f"aucune image extraite de {video.name} — fichier illisible ?")
    return images


def analyze_video(shot: Shot, video: Path, into: Path) -> VideoAnalysis:
    """Ce que la video montre reellement, face a ce qui etait prevu."""
    mesuree = ffprobe_duration(video)
    images = sample_frames(video, into / "frames")

    contenu: list[dict] = [{"type": "text", "text": prompts.video_analysis_user(
        shot.id, shot.voice, shot.duration_seconds, mesuree,
        shot.visual_concept, shot.animation_prompt)}]
    contenu += [{"type": "image_url", "image_url": {"url": image_payload(i)}} for i in images]

    brut = chat_json(config.OPENAI_VISION_MODEL, [
        {"role": "system", "content": prompts.VIDEO_ANALYSIS_SYSTEM},
        {"role": "user", "content": contenu},
    ])
    try:
        return VideoAnalysis.from_dict(shot.id, mesuree, brut)
    except StoryboardError as exc:
        raise OpenAIError(f"analyse video inexploitable : {exc}") from exc


# ---------------------------------------------------------------------------


def image_payload(image: Path | str) -> str:
    """URL directe telle quelle, fichier local encode en base64."""
    if isinstance(image, str) and image.startswith(("http://", "https://")):
        return image
    chemin = Path(image)
    if not chemin.is_file():
        raise OpenAIError(f"fichier introuvable pour l'analyse : {chemin}")
    mime = mimetypes.guess_type(chemin.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(chemin.read_bytes()).decode('ascii')}"
