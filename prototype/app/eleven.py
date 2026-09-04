"""ElevenLabs : la vraie voix, une phrase a la fois.

Le service n'est pas joignable depuis toutes les machines — ici la politique
reseau refuse api.elevenlabs.io — mais il l'est depuis un runner GitHub. La
cle vit dans l'environnement, jamais dans le code ni dans un fichier du
projet : ELEVENLABS_API_KEY en local dans .env, en secret de depot sur GitHub.

On synthetise PHRASE PAR PHRASE, et pas la piste entiere d'un bloc. Une piste
entiere obligerait a retrouver les frontieres a l'oreille — c'est ce que fait
`voix.caler_sur`, et ca marche, mais a 0,4 s pres. Un fichier par plan donne
la duree exacte, sans rien deviner. Les morceaux sont ensuite colles bout a
bout pour la piste complete.

Rien de ce module ne s'execute sans cle : sans elle il refuse tout de suite,
avec la marche a suivre.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

from . import config, voix
from .models import Storyboard

API = "https://api.elevenlabs.io/v1"
#: Le format que le montage sait relire sans reencoder.
FORMAT = "mp3_44100_128"
DELAI = 180


class ElevenError(RuntimeError):
    """L'appel a ElevenLabs n'a pas abouti, avec un message lisible."""


def exiger_cle() -> str:
    if not config.ELEVENLABS_API_KEY:
        raise ElevenError(
            "ELEVENLABS_API_KEY manquante.\n"
            f"  En local  : ajoute-la dans {config.ROOT_DIR / '.env'}\n"
            "  Sur GitHub : Settings -> Secrets and variables -> Actions ->\n"
            "               New repository secret -> ELEVENLABS_API_KEY\n"
            "  Ne la colle jamais dans le code, ni dans un fichier du projet.")
    return config.ELEVENLABS_API_KEY


def _demander(chemin: str, corps: dict | None = None, methode: str = "GET",
              ouvrir=None) -> bytes:
    """Un appel, et une erreur lisible quand ca ne passe pas."""
    ouvrir = ouvrir or urllib.request.urlopen
    requete = urllib.request.Request(
        f"{API}{chemin}", method=methode,
        data=json.dumps(corps).encode("utf-8") if corps is not None else None,
        headers={"xi-api-key": exiger_cle(), "Content-Type": "application/json"})
    try:
        with ouvrir(requete, timeout=DELAI) as reponse:
            return reponse.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        if exc.code == 401:
            raise ElevenError(f"clé refusée par ElevenLabs : {detail}") from exc
        if exc.code == 422:
            raise ElevenError(f"requête refusée (voix ou modèle inconnu ?) : "
                              f"{detail}") from exc
        if exc.code == 429:
            raise ElevenError(
                "quota ElevenLabs épuisé pour ce mois.\n"
                "  Le palier gratuit tient environ dix minutes de voix.\n"
                f"  {detail}") from exc
        raise ElevenError(f"ElevenLabs a répondu {exc.code} : {detail}") from exc
    except urllib.error.URLError as exc:
        raise ElevenError(
            f"service injoignable : {exc.reason}\n"
            "  Certaines machines n'ont pas accès à api.elevenlabs.io ; un "
            "runner GitHub, si.") from exc


def voix_disponibles(ouvrir=None) -> list[dict]:
    """Les voix du compte : leur identifiant et leur nom."""
    brut = json.loads(_demander("/voices", ouvrir=ouvrir) or b"{}")
    return [{"voice_id": v.get("voice_id", ""), "name": v.get("name", ""),
             "labels": v.get("labels") or {}}
            for v in (brut.get("voices") or []) if v.get("voice_id")]


def choisir_voix(ouvrir=None) -> str:
    """L'identifiant configure, ou la premiere voix du compte."""
    if config.ELEVENLABS_VOICE_ID:
        return config.ELEVENLABS_VOICE_ID
    disponibles = voix_disponibles(ouvrir)
    if not disponibles:
        raise ElevenError("aucune voix sur ce compte ElevenLabs.")
    return disponibles[0]["voice_id"]


def dire(texte: str, mp3: Path, voice_id: str, modele: str = "",
         stabilite: float = 0.4, style: float = 0.3, ouvrir=None) -> Path:
    """Une phrase, dite, ecrite en MP3."""
    corps = {
        "text": texte,
        "model_id": modele or config.ELEVENLABS_MODEL,
        "voice_settings": {"stability": stabilite, "similarity_boost": 0.8,
                           "style": style, "use_speaker_boost": True},
    }
    donnees = _demander(f"/text-to-speech/{voice_id}?output_format={FORMAT}",
                        corps, "POST", ouvrir)
    if not donnees:
        raise ElevenError("ElevenLabs a rendu un fichier vide.")
    mp3.parent.mkdir(parents=True, exist_ok=True)
    mp3.write_bytes(donnees)
    return mp3


def par_plan(sb: Storyboard, dossier: Path, voice_id: str = "",
             ouvrir=None, on_shot=None) -> dict[int, float]:
    """Une phrase par plan, dite et mesuree. La duree n'est plus devinee."""
    voice_id = voice_id or choisir_voix(ouvrir)
    mesurees = {}
    for shot in sb.shots:
        mp3 = dossier / f"shot_{shot.id:02d}.mp3"
        dire(shot.voice, mp3, voice_id, ouvrir=ouvrir)
        # La pause qui suit la phrase dans la piste appartient au plan :
        # sans elle, la timeline finirait avant la voix.
        mesurees[shot.id] = round(voix.duree(mp3) + voix.PAUSE, 3)
        if on_shot:
            on_shot(shot, mesurees[shot.id])
    return mesurees


def piste(sb: Storyboard, dossier: Path, sortie: Path, voice_id: str = "",
          ouvrir=None, on_shot=None) -> tuple[Path, dict[int, float]]:
    """La piste entiere, phrase apres phrase, avec le souffle entre elles."""
    mesurees = par_plan(sb, dossier, voice_id, ouvrir, on_shot)
    fichiers = [dossier / f"shot_{s.id:02d}.mp3" for s in sb.shots]
    return voix.assembler(fichiers, dossier, sortie), mesurees
