"""Configuration du prototype. Les trois valeurs de l'ETAPE 1 sont en haut."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent

# .env cherche a la racine du prototype, puis dans app/ (les deux tolerees).
load_dotenv(ROOT_DIR / ".env")
load_dotenv(APP_DIR / ".env")

# ---------------------------------------------------------------------------
# ETAPE 1 - INPUT : les seules valeurs a modifier au quotidien
# ---------------------------------------------------------------------------

SUBJECT = "Fonctionnement d'une voiture électrique"
DURATION = 16
SHOT_COUNT = 4

# True  : on s'arrete apres avoir colle le prompt du SHOT 01 (preuve de boucle).
# False : les 4 plans s'enchainent automatiquement.
TEST_MODE = True

# ---------------------------------------------------------------------------
# META AI - destination fixe du prototype
# ---------------------------------------------------------------------------

META_AI_URL = "https://www.meta.ai/prompt/f1da6c85-fb08-433d-b203-04cc41e575c6"

# ---------------------------------------------------------------------------
# OpenAI - la cle vient de .env, JAMAIS du code
# ---------------------------------------------------------------------------

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o").strip()
OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", OPENAI_MODEL).strip()
OPENAI_TIMEOUT = float(os.getenv("OPENAI_TIMEOUT", "120"))

# ---------------------------------------------------------------------------
# fal.ai - images et animation, quand on veut la chaine 100% automatique
# ---------------------------------------------------------------------------

FAL_KEY = os.getenv("FAL_KEY", "").strip()
FAL_IMAGE_MODEL = os.getenv("FAL_IMAGE_MODEL", "fal-ai/flux/schnell").strip()
FAL_VIDEO_MODEL = os.getenv(
    "FAL_VIDEO_MODEL", "fal-ai/kling-video/v2.1/standard/image-to-video"
).strip()
FAL_IMAGE_STEPS = int(os.getenv("FAL_IMAGE_STEPS", "4"))
FAL_TIMEOUT = float(os.getenv("FAL_TIMEOUT", "600"))

# 9:16 vertical, comme impose par la direction artistique.
IMAGE_WIDTH = int(os.getenv("IMAGE_WIDTH", "1080"))
IMAGE_HEIGHT = int(os.getenv("IMAGE_HEIGHT", "1920"))

# ---------------------------------------------------------------------------
# Arborescence locale
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", APP_DIR / "output"))
PROJECT_FILE = OUTPUT_DIR / "project.json"
STATUS_FILE = OUTPUT_DIR / "status.json"
PASTE_SHEET = OUTPUT_DIR / "prompts_a_coller.txt"
SHOTS_DIR = OUTPUT_DIR / "shots"
SCREENSHOT_DIR = OUTPUT_DIR / "screenshots"

# Profil navigateur persistant : garde la session Meta entre deux lancements.
# Il ne contient jamais d'identifiant ecrit par nous, seulement les cookies
# que le navigateur pose lui-meme quand TU te connectes a la main.
BROWSER_PROFILE_DIR = Path(os.getenv("BROWSER_PROFILE_DIR", ROOT_DIR / "browser_profile"))

# ---------------------------------------------------------------------------
# Navigateur
# ---------------------------------------------------------------------------

# Navigateur VISIBLE par defaut, comme demande. HEADLESS=1 sert uniquement
# aux verifications automatiques (machine sans ecran).
HEADLESS = os.getenv("HEADLESS", "0") == "1"
CHROMIUM_PATH = os.getenv("CHROMIUM_PATH", "").strip() or None

# Quel navigateur ouvrir : vide = le Chromium installe par Playwright.
# "chrome" ou "msedge" = TON navigateur, celui ou tu es deja connecte.
BROWSER_CHANNEL = os.getenv("BROWSER_CHANNEL", "").strip() or None
PAGE_TIMEOUT_MS = int(os.getenv("PAGE_TIMEOUT_MS", "60000"))
GENERATION_TIMEOUT_S = int(os.getenv("GENERATION_TIMEOUT_S", "240"))


def shot_dir(shot_id: int) -> Path:
    """shots/shot_01, shots/shot_02, ..."""
    return SHOTS_DIR / f"shot_{shot_id:02d}"


def ensure_dirs(shot_count: int = SHOT_COUNT) -> None:
    for path in (OUTPUT_DIR, SHOTS_DIR, SCREENSHOT_DIR):
        path.mkdir(parents=True, exist_ok=True)
    for i in range(1, shot_count + 1):
        shot_dir(i).mkdir(parents=True, exist_ok=True)
