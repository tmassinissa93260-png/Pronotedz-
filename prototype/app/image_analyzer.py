"""analyze_image() puis generate_animation_prompt().

L'ordre est impose : on n'invente jamais l'animation avant d'avoir regarde
l'image. L'analyse decrit ce qui est REELLEMENT la ; le prompt d'animation
n'est ecrit qu'a partir de cette analyse.
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

from . import config, prompts
from .models import MOTION_INTENTS, AnimationPlan, ImageAnalysis, Shot, StoryboardError
from .openai_client import OpenAIError, chat_json


def analyze_image(image: Path | str) -> ImageAnalysis:
    """Ce qui est visible dans l'image. Rien de plus."""
    raw = chat_json(
        config.OPENAI_VISION_MODEL,
        [
            {"role": "system", "content": prompts.ANALYSIS_SYSTEM},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompts.ANALYSIS_USER},
                    {"type": "image_url", "image_url": {"url": image_payload(image)}},
                ],
            },
        ],
    )
    try:
        return ImageAnalysis.from_dict(raw)
    except StoryboardError as exc:
        raise OpenAIError(f"analyse d'image inexploitable : {exc}") from exc


def generate_animation_prompt(shot: Shot, analysis: ImageAnalysis) -> AnimationPlan:
    """Le plan d'animation, ecrit a partir de l'analyse et de la voix."""
    raw = chat_json(
        config.OPENAI_MODEL,
        [
            {"role": "system", "content": prompts.ANIMATION_SYSTEM},
            {
                "role": "user",
                "content": prompts.animation_user(
                    shot.voice, shot.educational_function,
                    analysis.as_block(), MOTION_INTENTS),
            },
        ],
    )
    try:
        return AnimationPlan.from_dict(raw)
    except StoryboardError as exc:
        raise OpenAIError(f"plan d'animation inexploitable : {exc}") from exc


def animate(shot: Shot, image: Path | str) -> tuple[ImageAnalysis, AnimationPlan]:
    """IMAGE -> ANALYSE -> PROMPT D'ANIMATION, dans cet ordre et pas un autre."""
    analysis = analyze_image(image)
    return analysis, generate_animation_prompt(shot, analysis)


def image_payload(image: Path | str) -> str:
    """URL directe telle quelle, fichier local encode en base64."""
    if isinstance(image, str) and image.startswith(("http://", "https://")):
        return image
    path = Path(image)
    if not path.is_file():
        raise OpenAIError(
            f"image introuvable pour l'analyse : {path}\n"
            "  Donne un chemin existant ou une URL http(s) directe."
        )
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"
