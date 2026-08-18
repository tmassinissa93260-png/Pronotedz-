"""Voix ElevenLabs — synthèse et **timings réels mot par mot**.

Le second point est le plus important. Aujourd'hui, `mots_depuis_texte()`
*estime* quand chaque mot est prononcé, au prorata de sa longueur. C'est une
approximation : le karaoké dérive de quelques dixièmes sur une phrase longue.

ElevenLabs renvoie l'alignement **caractère par caractère** de ce qu'il a
réellement prononcé. On le regroupe en mots, et la synchro devient exacte.

⚠️ Ce module n'a jamais pu être exécuté depuis l'environnement de
développement : la politique réseau y bloque `api.elevenlabs.io`. Il est écrit
pour tourner sur la machine de l'utilisateur. Le regroupement des caractères
en mots, lui, est testé hors ligne sur des données d'exemple.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path

import httpx

from pdz.ia.registre import registre
from pdz.moteur.erreurs import (
    ErreurConfig,
    ErreurFournisseur,
    ErreurQuota,
    ErreurReseau,
    ErreurValidation,
)
from pdz.video.soustitres import Mot

log = logging.getLogger(__name__)

BASE = "https://api.elevenlabs.io/v1"

# eleven_multilingual_v2 : meilleure prosodie en français que turbo, pour un
# surcoût qui reste faible au volume visé.
MODELE_DEFAUT = "eleven_multilingual_v2"


class Voix:
    def __init__(self, donnees: dict):
        self.id = donnees["voice_id"]
        self.nom = donnees.get("name", "")
        self.langue = (donnees.get("labels") or {}).get("language", "")
        self.genre = (donnees.get("labels") or {}).get("gender", "")
        self.usage = (donnees.get("labels") or {}).get("use_case", "")

    def __repr__(self) -> str:
        return f"Voix({self.nom!r}, {self.genre}, {self.usage})"


def _cle() -> str:
    return registre().cle_fournisseur("elevenlabs")


# Ce qu'ElevenLabs met dans `detail.status` sur un 401 quand la clé est
# parfaitement valide — et que le problème est ailleurs. Mesuré en production
# (run #75) : deux répliques synthétisées avec succès, puis 401 sur la
# troisième. Une clé refusée échoue à la PREMIÈRE, jamais à la troisième.
_401_QUI_NE_SONT_PAS_UNE_CLE = {
    "quota_exceeded": "Crédits ElevenLabs épuisés.",
    "detected_unusual_activity": (
        "ElevenLabs a désactivé le palier gratuit pour ce compte — c'est ce "
        "qu'il fait quand les requêtes viennent d'une IP de centre de données, "
        "ce qu'est un runner GitHub Actions."
    ),
}


def _lever(r: httpx.Response) -> None:
    if r.status_code < 400:
        return
    detail = r.text[:300]
    if r.status_code == 401:
        # Ne PAS accuser la clé sans avoir lu ce qu'ElevenLabs répond. Le
        # message générique « vérifie ELEVENLABS_API_KEY » envoyait chercher
        # un problème inexistant, et jetait au passage la seule explication
        # disponible — celle du fournisseur, qui dit précisément lequel de
        # ces cas s'applique et combien de crédits il reste.
        statut = ""
        try:
            corps = r.json().get("detail")
            statut = (corps or {}).get("status", "") if isinstance(corps, dict) else ""
        except Exception:
            statut = ""
        if explication := _401_QUI_NE_SONT_PAS_UNE_CLE.get(statut):
            # Pas une ErreurConfig : la clé est bonne, l'arrêt n'est pas
            # définitif, et le repli garde un sens.
            raise ErreurQuota(f"{explication} {detail}")
        raise ErreurConfig(
            f"Clé ElevenLabs refusée. Vérifie ELEVENLABS_API_KEY dans .env. {detail}"
        )
    if r.status_code == 429:
        raise ErreurQuota(f"Quota ElevenLabs atteint. {detail}")
    if r.status_code >= 500:
        raise ErreurFournisseur(f"ElevenLabs indisponible ({r.status_code}).")
    raise ErreurValidation(f"ElevenLabs a refusé la requête ({r.status_code}). {detail}")


def lister_voix() -> list[Voix]:
    try:
        r = httpx.get(f"{BASE}/voices", headers={"xi-api-key": _cle()}, timeout=30)
    except httpx.HTTPError as e:
        raise ErreurReseau(f"ElevenLabs injoignable : {e}") from e
    _lever(r)
    return [Voix(v) for v in r.json().get("voices", [])]


def quota() -> dict:
    """Caractères restants — à vérifier avant un lot, pas après."""
    try:
        r = httpx.get(f"{BASE}/user/subscription",
                      headers={"xi-api-key": _cle()}, timeout=30)
    except httpx.HTTPError as e:
        raise ErreurReseau(f"ElevenLabs injoignable : {e}") from e
    _lever(r)
    d = r.json()
    utilises = d.get("character_count", 0)
    plafond = d.get("character_limit", 0)
    return {"formule": d.get("tier"), "utilises": utilises,
            "plafond": plafond, "restants": plafond - utilises}


def synthetiser(texte: str, sortie: Path, *, voice_id: str,
                modele: str = MODELE_DEFAUT,
                stabilite: float = 0.5, style: float = 0.4,
                vitesse: float = 1.0) -> tuple[Path, list[Mot]]:
    """Génère l'audio ET les timings réels de chaque mot.

    On appelle `/with-timestamps` plutôt que l'endpoint simple : le surcoût
    est nul et on récupère l'alignement exact, ce qui supprime la dérive du
    karaoké sur les phrases longues.
    """
    corps = {
        "text": texte,
        "model_id": modele,
        "voice_settings": {
            "stability": stabilite,
            "similarity_boost": 0.75,
            "style": style,
            "speed": vitesse,
        },
    }
    try:
        r = httpx.post(
            f"{BASE}/text-to-speech/{voice_id}/with-timestamps",
            headers={"xi-api-key": _cle(), "content-type": "application/json"},
            json=corps, timeout=120,
        )
    except httpx.TimeoutException as e:
        raise ErreurReseau("ElevenLabs n'a pas répondu en 120 s.") from e
    except httpx.HTTPError as e:
        raise ErreurReseau(f"ElevenLabs injoignable : {e}") from e
    _lever(r)

    charge = r.json()
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_bytes(base64.b64decode(charge["audio_base64"]))

    mots = mots_depuis_alignement(charge.get("alignment") or {})
    log.info("Voix : %d caractères → %s (%d mots datés)",
             len(texte), sortie.name, len(mots))
    return sortie, mots


def mots_depuis_alignement(alignement: dict) -> list[Mot]:
    """Regroupe l'alignement caractère par caractère en mots.

    ElevenLabs renvoie trois listes parallèles : les caractères, leurs débuts
    et leurs fins en secondes. Un mot commence au premier caractère non blanc
    et finit au dernier avant l'espace suivant.
    """
    chars = alignement.get("characters") or []
    debuts = alignement.get("character_start_times_seconds") or []
    fins = alignement.get("character_end_times_seconds") or []
    if not chars or len(chars) != len(debuts) or len(chars) != len(fins):
        return []

    mots: list[Mot] = []
    courant, debut, fin = "", None, None

    for c, d, f in zip(chars, debuts, fins, strict=True):
        if c.isspace():
            if courant:
                mots.append(Mot(courant, round(debut * 1000), round(fin * 1000)))
                courant, debut, fin = "", None, None
            continue
        if not courant:
            debut = d
        courant += c
        fin = f

    if courant:
        mots.append(Mot(courant, round(debut * 1000), round(fin * 1000)))
    return mots
