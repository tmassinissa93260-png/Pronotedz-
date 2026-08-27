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
SHOT_COUNT = 4

# True  : on s'arrete apres avoir colle le prompt du SHOT 01 (preuve de boucle).
# False : les 4 plans s'enchainent automatiquement.
# True : on s'arrete apres le storyboard valide. Aucune image, aucune video.
TEST_MODE = True

# Combien de fois, au plus, on renvoie ses erreurs a OpenAI pour correction.
MAX_REPAIR_ATTEMPTS = int(env("MAX_REPAIR_ATTEMPTS", "2"))

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
# fal.ai - images et animation, quand on veut la chaine 100% automatique
# ---------------------------------------------------------------------------

FAL_KEY = env("FAL_KEY")
# Dans la famille FLUX, du plus faible au plus fort :
#   flux/schnell     distille a 4 pas, fait pour la vitesse. Casse sur un
#                    prompt d'ingenierie long : geometries incoherentes,
#                    texte hallucine. C'etait le defaut, c'etait une erreur.
#   flux/dev         ~28 pas, tient la structure. Correct.
#   flux-pro/v1.1    le meilleur rapport tenue du prompt / coherence.
#   flux-pro/v1.1-ultra  plus grand, plus cher, prend aspect_ratio.
# La commande « comparer » sert a trancher sur pieces plutot que sur parole.
FAL_IMAGE_MODEL = env("FAL_IMAGE_MODEL", "fal-ai/flux-pro/v1.1")

# Les modeles compares par defaut par la commande « comparer ».
FAL_COMPARE_MODELS = [
    m.strip() for m in env(
        "FAL_COMPARE_MODELS",
        "fal-ai/flux-pro/v1.1,fal-ai/flux/dev,fal-ai/flux/schnell",
    ).split(",") if m.strip()
]
FAL_VIDEO_MODEL = env(
    "FAL_VIDEO_MODEL", "fal-ai/kling-video/v2.1/standard/image-to-video"
)
# 4 pas pour schnell (il est distille pour ca), ~28 pour dev. Les modeles pro
# ne prennent pas ce reglage : on ne le leur envoie pas.
FAL_IMAGE_STEPS = int(env("FAL_IMAGE_STEPS", "0"))

# Guidance : ignoré par schnell, utile a dev pour coller au prompt.
FAL_GUIDANCE = float(env("FAL_GUIDANCE", "3.5"))
FAL_TIMEOUT = float(env("FAL_TIMEOUT", "600"))

# 9:16 vertical, comme impose par la direction artistique.
#
# 768x1344 = 1,03 Mpx. FLUX est entraine autour de 1 Mpx : au dela il perd la
# coherence geometrique et invente des motifs. 1080x1920 valait 2,07 Mpx, soit
# le double — d'ou les tiges qui sortent des roues et le texte en miroir.
# Pour du 1080p final, agrandir apres coup plutot que generer trop grand.
IMAGE_WIDTH = int(env("IMAGE_WIDTH", "768"))
IMAGE_HEIGHT = int(env("IMAGE_HEIGHT", "1344"))

# ---------------------------------------------------------------------------
# Arborescence locale
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path(env("OUTPUT_DIR") or APP_DIR / "output")
PROJECT_FILE = OUTPUT_DIR / "project.json"
STATUS_FILE = OUTPUT_DIR / "status.json"
PASTE_SHEET = OUTPUT_DIR / "prompts_a_coller.txt"
SHOTS_DIR = OUTPUT_DIR / "shots"
SCREENSHOT_DIR = OUTPUT_DIR / "screenshots"




def shot_dir(shot_id: int) -> Path:
    """shots/shot_01, shots/shot_02, ..."""
    return SHOTS_DIR / f"shot_{shot_id:02d}"


def ensure_dirs(shot_count: int = SHOT_COUNT) -> None:
    for path in (OUTPUT_DIR, SHOTS_DIR, SCREENSHOT_DIR):
        path.mkdir(parents=True, exist_ok=True)
    for i in range(1, shot_count + 1):
        shot_dir(i).mkdir(parents=True, exist_ok=True)
