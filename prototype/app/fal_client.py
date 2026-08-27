"""Client fal.ai direct : image (FLUX) et animation (image vers video).

Volontairement minuscule et sans machinerie : un POST, une reponse, un
telechargement. Pas de sonde de capacite, pas de gouverneur de cout, pas de
repli silencieux — un echec leve avec sa raison.

Les formes d'appel reprennent celles de pdz2/providers/fal.py, deja presentes
dans ce depot : meme base, meme en-tete d'autorisation, memes modeles.
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

import httpx

from . import config

BASE_URL = "https://fal.run"


class FalError(RuntimeError):
    """Appel fal.ai en echec, avec un message lisible."""


def _key() -> str:
    if not config.FAL_KEY:
        raise FalError(
            "FAL_KEY absente.\n"
            "  En local  : ajoute FAL_KEY=... dans prototype/.env\n"
            "  Sur GitHub: Settings > Secrets and variables > Actions > FAL_KEY\n"
            "  La cle se recupere sur fal.ai/dashboard/keys"
        )
    return config.FAL_KEY


def _call(model: str, payload: dict, timeout: float) -> dict:
    try:
        response = httpx.post(
            f"{BASE_URL}/{model}",
            headers={"Authorization": f"Key {_key()}", "Content-Type": "application/json"},
            json=payload,
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        raise FalError(f"{model} : impossible de joindre fal.ai — {exc}") from exc

    if response.status_code == 401:
        raise FalError(f"{model} : cle FAL_KEY refusee (401)")
    if response.status_code == 402:
        raise FalError(f"{model} : credit fal.ai insuffisant (402)")
    if response.status_code >= 400:
        raise FalError(f"{model} : code {response.status_code} — {response.text[:300]}")

    try:
        return response.json()
    except ValueError as exc:
        raise FalError(f"{model} : reponse illisible — {response.text[:200]}") from exc


def _download(url: str, dest: Path, timeout: float) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with httpx.stream("GET", url, timeout=timeout, follow_redirects=True) as flow:
            flow.raise_for_status()
            with dest.open("wb") as out:
                for chunk in flow.iter_bytes():
                    out.write(chunk)
    except httpx.HTTPError as exc:
        raise FalError(f"telechargement impossible depuis {url[:80]} — {exc}") from exc

    if dest.stat().st_size == 0:
        raise FalError(f"fichier vide rendu par fal.ai : {dest.name}")
    return dest


# ---------------------------------------------------------------------------
# Image
# ---------------------------------------------------------------------------


def build_payload(prompt: str, model: str) -> dict:
    """La charge utile, adaptee au modele vise.

    Les modeles de la famille FLUX n'acceptent pas tous les memes champs :
    « ultra » raisonne en rapport d'image, les « pro » ne prennent pas de
    nombre de pas, et schnell ignore la guidance. Envoyer un champ inconnu
    fait rejeter l'appel.
    """
    payload: dict = {"prompt": prompt, "num_images": 1}

    if "ultra" in model:
        payload["aspect_ratio"] = "9:16"
    else:
        payload["image_size"] = {"width": config.IMAGE_WIDTH, "height": config.IMAGE_HEIGHT}

    if "pro" not in model:
        payload["num_inference_steps"] = (
            config.FAL_IMAGE_STEPS or (4 if "schnell" in model else 28)
        )
    if "schnell" not in model:
        payload["guidance_scale"] = config.FAL_GUIDANCE

    return payload


def generate_image(prompt: str, dest: Path, model: str | None = None) -> Path:
    """Un prompt photo -> un fichier image 9:16."""
    model = model or config.FAL_IMAGE_MODEL
    out = _call(model, build_payload(prompt, model), config.FAL_TIMEOUT)

    images = out.get("images") or []
    if not images or not images[0].get("url"):
        raise FalError(f"reponse sans image : {str(out)[:200]}")
    return _download(images[0]["url"], dest, config.FAL_TIMEOUT)


# ---------------------------------------------------------------------------
# Animation
# ---------------------------------------------------------------------------

# kling n'accepte que des durees entieres en secondes, et pas moins de 5.
ALLOWED_DURATIONS = (5, 10)


def clamp_duration(seconds: float) -> int:
    """La duree demandee ramenee a ce que le modele accepte reellement."""
    return min(ALLOWED_DURATIONS, key=lambda allowed: abs(allowed - seconds))


def animate(image_path: Path, prompt: str, seconds: float, dest: Path) -> Path:
    """Une image + un prompt d'animation -> un fichier video."""
    if not image_path.is_file():
        raise FalError(f"image introuvable pour l'animation : {image_path}")

    mime = mimetypes.guess_type(image_path.name)[0] or "image/png"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")

    payload = {
        "image_url": f"data:{mime};base64,{encoded}",
        "prompt": prompt,
        "duration": str(clamp_duration(seconds)),
    }
    out = _call(config.FAL_VIDEO_MODEL, payload, config.FAL_TIMEOUT)

    url = (out.get("video") or {}).get("url")
    if not url:
        raise FalError(f"reponse sans video : {str(out)[:200]}")
    return _download(url, dest, config.FAL_TIMEOUT)
