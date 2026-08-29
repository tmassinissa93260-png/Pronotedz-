"""Configuration du prototype. Les trois valeurs de l'ETAPE 1 sont en haut."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def env(name: str, default: str = "") -> str:
    """Lit une variable d'environnement. Une valeur VIDE compte comme absente.

    os.getenv(name, defaut) rend "" quand la variable existe mais est vide —
    ce que fait GitHub Actions pour une variable de depot non definie. Le
    defaut n'etait donc jamais applique, et un model="" partait a l'API.
    """
    return (os.getenv(name) or "").strip() or default

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
SHOT_COUNT = 20

# True  : on s'arrete apres avoir colle le prompt du SHOT 01 (preuve de boucle).
# False : les 4 plans s'enchainent automatiquement.
# True : on s'arrete apres le storyboard valide. Aucune image, aucune video.
TEST_MODE = True

# Combien de fois, au plus, on renvoie ses erreurs a OpenAI pour correction.
MAX_REPAIR_ATTEMPTS = int(env("MAX_REPAIR_ATTEMPTS", "4"))

# ---------------------------------------------------------------------------
# OpenAI - la cle vient de .env, JAMAIS du code
# ---------------------------------------------------------------------------

# Groq expose une API compatible OpenAI (voir pdz2/providers/groq.py) : le
# meme SDK, le meme code, une autre adresse. Si aucune cle OpenAI n'est
# fournie mais qu'une cle Groq l'est, on bascule dessus automatiquement.
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

_openai_key = env("OPENAI_API_KEY")
_groq_key = env("GROQ_API_KEY")

USING_GROQ = not _openai_key and bool(_groq_key)

OPENAI_API_KEY = _openai_key or (_groq_key if USING_GROQ else "")
OPENAI_BASE_URL = env("OPENAI_BASE_URL") or (
    GROQ_BASE_URL if USING_GROQ else None
)

_default_model = env("GROQ_MODEL", "openai/gpt-oss-120b") if USING_GROQ else "gpt-4o"
OPENAI_MODEL = env("OPENAI_MODEL", _default_model)

# L'analyse d'image exige un modele qui SAIT lire une image. Chez OpenAI
# gpt-4o le fait ; chez Groq il faut nommer explicitement un modele vision,
# sinon l'appel echouera — bruyamment, avec le message du service.
OPENAI_VISION_MODEL = env("OPENAI_VISION_MODEL", OPENAI_MODEL)

OPENAI_TIMEOUT = float(env("OPENAI_TIMEOUT", "120"))

def cerveau() -> str:
    """Quel service repond aux appels « OpenAI », en clair."""
    if not OPENAI_API_KEY:
        return "aucun (aucune cle)"
    if USING_GROQ:
        return f"Groq ({OPENAI_MODEL})"
    if OPENAI_BASE_URL:
        return f"{OPENAI_BASE_URL} ({OPENAI_MODEL})"
    return f"OpenAI ({OPENAI_MODEL})"

# ---------------------------------------------------------------------------
# Arborescence locale
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path(env("OUTPUT_DIR") or APP_DIR / "output")

# Ce que tu as deja refuse. Le fichier est versionne : ecris-y une ligne,
# elle vaut pour tous les runs suivants. C'est la memoire du systeme.
FEEDBACK_FILE = Path(env("FEEDBACK_FILE") or ROOT_DIR / "feedback.md")
PROJECT_FILE = OUTPUT_DIR / "project.json"
STATUS_FILE = OUTPUT_DIR / "status.json"
PASTE_SHEET = OUTPUT_DIR / "prompts_a_coller.txt"
SHOTS_DIR = OUTPUT_DIR / "shots"
# L'utilisateur depose ici les videos qu'il a produites lui-meme.
VIDEOS_DIR = Path(env("VIDEOS_DIR") or OUTPUT_DIR / "videos")
ELEMENTS_FILE = OUTPUT_DIR / "elements.md"
TIMELINE_FILE = OUTPUT_DIR / "timeline.json"
SRT_FILE = OUTPUT_DIR / "sous_titres.srt"
FINAL_FILE = OUTPUT_DIR / "final.mp4"
VOICE_FILE = Path(env("VOICE_FILE") or OUTPUT_DIR / "voix.mp3")
MUSIC_FILE = Path(env("MUSIC_FILE") or OUTPUT_DIR / "musique.mp3")
SCREENSHOT_DIR = OUTPUT_DIR / "screenshots"

def shot_dir(shot_id: int) -> Path:
    """shots/shot_01, shots/shot_02, ..."""
    return SHOTS_DIR / f"shot_{shot_id:02d}"

def ensure_dirs(shot_count: int = SHOT_COUNT) -> None:
    """Les dossiers des plans, et EUX SEULS.

    Un run plus court que le precedent laissait les dossiers en trop : la
    branche a porte un shot_05 et un shot_06 du run a six plans alors que le
    storyboard courant n'en avait que quatre. Les prompts perimes restaient
    lisibles et copiables, mais ils appartenaient a une autre video.
    """
    import shutil

    for path in (OUTPUT_DIR, SHOTS_DIR, SCREENSHOT_DIR):
        path.mkdir(parents=True, exist_ok=True)
    for i in range(1, shot_count + 1):
        shot_dir(i).mkdir(parents=True, exist_ok=True)

    for reste in sorted(SHOTS_DIR.glob("shot_*")):
        numero = reste.name.removeprefix("shot_")
        if reste.is_dir() and numero.isdigit() and int(numero) > shot_count:
            shutil.rmtree(reste)
