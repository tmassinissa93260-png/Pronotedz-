"""Appels OpenAI : storyboard (texte) et prompt d'animation (vision)."""

from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path

import openai

from . import config, prompts
from .models import Shot, Storyboard


class OpenAIError(RuntimeError):
    """Echec d'un appel OpenAI, avec un message lisible."""


def _client() -> openai.OpenAI:
    if not config.OPENAI_API_KEY:
        raise OpenAIError(
            "OPENAI_API_KEY absente.\n"
            f"  Cree {config.ROOT_DIR / '.env'} a partir de .env.example, "
            "puis mets ta cle dedans :\n"
            "      OPENAI_API_KEY=sk-...\n"
            "  (la cle ne doit jamais etre ecrite dans le code)"
        )
    return openai.OpenAI(api_key=config.OPENAI_API_KEY, timeout=config.OPENAI_TIMEOUT)


def _chat_json(model: str, messages: list[dict]) -> dict:
    """Un appel chat en mode JSON, avec les erreurs traduites en clair."""
    try:
        response = _client().chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
        )
    except openai.AuthenticationError as exc:
        raise OpenAIError(f"cle OpenAI refusee: {exc}") from exc
    except openai.NotFoundError as exc:
        raise OpenAIError(
            f"modele '{model}' indisponible pour ce compte: {exc}\n"
            "  Choisis-en un autre via OPENAI_MODEL=... dans .env"
        ) from exc
    except openai.APIConnectionError as exc:
        raise OpenAIError(f"impossible de joindre l'API OpenAI: {exc}") from exc
    except openai.RateLimitError as exc:
        raise OpenAIError(f"quota ou cadence OpenAI depasse: {exc}") from exc
    except openai.APIStatusError as exc:
        raise OpenAIError(f"OpenAI a repondu {exc.status_code}: {exc}") from exc

    content = (response.choices[0].message.content or "").strip()
    if not content:
        raise OpenAIError("OpenAI a renvoye une reponse vide")
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise OpenAIError(f"reponse OpenAI non JSON: {exc}\n---\n{content[:500]}") from exc


# ---------------------------------------------------------------------------
# ETAPE 2 - storyboard
# ---------------------------------------------------------------------------


def generate_storyboard(subject: str, duration: int, shot_count: int) -> Storyboard:
    raw = _chat_json(
        config.OPENAI_MODEL,
        [
            {"role": "system", "content": prompts.STORYBOARD_SYSTEM},
            {"role": "user", "content": prompts.storyboard_user(subject, duration, shot_count)},
        ],
    )
    storyboard = Storyboard.from_dict(raw, expected_shots=shot_count)

    # Filet de securite : la direction artistique doit etre dans CHAQUE prompt photo,
    # meme si le modele l'a oubliee.
    for shot in storyboard.shots:
        shot.image_prompt = prompts.enforce_style(shot.image_prompt)

    return storyboard


# ---------------------------------------------------------------------------
# ETAPE 6 - analyse de l'image reelle -> prompt d'animation
# ---------------------------------------------------------------------------


def build_animation_prompt(image: Path | str, shot: Shot) -> str:
    """`image` est un fichier local ou une URL http(s) directe."""
    image_url = _image_payload(image)

    raw = _chat_json(
        config.OPENAI_VISION_MODEL,
        [
            {"role": "system", "content": prompts.ANIMATION_SYSTEM},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompts.animation_user(shot.voice, shot.visual_description),
                    },
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            },
        ],
    )

    animation_prompt = str(raw.get("animation_prompt") or "").strip()
    if not animation_prompt:
        raise OpenAIError(f"pas de champ 'animation_prompt' dans la reponse: {raw}")
    if len(animation_prompt) < 60:
        raise OpenAIError(
            f"prompt d'animation trop court pour etre pedagogique: {animation_prompt!r}"
        )
    return animation_prompt


def _image_payload(image: Path | str) -> str:
    """URL directe telle quelle, fichier local encode en base64."""
    if isinstance(image, str) and image.startswith(("http://", "https://")):
        return image
    path = Path(image)
    if not path.is_file():
        raise OpenAIError(
            f"image introuvable pour l'analyse: {path}\n"
            "  Donne un chemin de fichier existant ou une URL http(s) directe."
        )
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"
