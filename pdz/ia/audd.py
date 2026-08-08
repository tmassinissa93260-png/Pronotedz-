"""AudD — identifier un morceau à partir d'un extrait audio.

Le service compare l'empreinte acoustique de l'extrait à une base de plus de
cent millions de titres. C'est le même principe que Shazam ; Shazam ne
proposant pas d'API publique, AudD est le service qui s'en approche le plus
avec une tarification lisible : 300 requêtes gratuites à l'inscription, puis
environ 5 $ pour 1 000 requêtes — un demi-centime l'identification.

Ce qu'il faut savoir avant de s'y fier :

  · **Il ne trouve que ce qui est publié.** Une musique libre de droits d'un
    petit catalogue, un son fait maison, une reprise amateur : introuvables.
    Un échec ne veut donc pas dire « la vidéo n'a pas de musique ».
  · **La voix par-dessus fait chuter le taux de reconnaissance.** D'où
    l'extraction préalable d'un passage sans parole
    (`pdz.analyse.musique`), qui est le vrai travail.
  · **L'appel est facturé même quand rien n'est trouvé.** Le garde-fou est
    donc en amont : on n'envoie qu'un seul extrait, le meilleur.

⚠️ Ce module n'a pas pu être exécuté depuis l'environnement de développement :
la politique réseau y bloque `api.audd.io`. Il est écrit pour la machine de
l'utilisateur. Tout ce qui ne dépend pas du réseau — construction de la
requête, lecture de la réponse, classement des erreurs — est testé hors ligne.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from pdz import db
from pdz.config import config
from pdz.moteur.erreurs import (
    ErreurConfig,
    ErreurFournisseur,
    ErreurQuota,
    ErreurRefus,
    ErreurReseau,
    ErreurValidation,
)

log = logging.getLogger(__name__)

BASE = "https://api.audd.io/"

# 10 Mo est la limite du service. Un extrait mono de 12 s en 128 kbit/s pèse
# environ 200 ko : on est très loin du plafond, mais mieux vaut échouer ici
# avec un message clair qu'en HTTP 413.
TAILLE_MAX_OCTETS = 10 * 1024 * 1024

# Coût constaté : 5 $ pour 1 000 requêtes. Converti à la louche en euros pour
# entrer dans le suivi de dépense comme n'importe quel autre appel payant.
COUT_PAR_REQUETE_EUR = 0.0046


@dataclass
class Morceau:
    titre: str
    artiste: str
    album: str = ""
    sortie: str = ""
    label: str = ""
    lien: str = ""
    spotify: str = ""
    apple_music: str = ""
    timecode: str = ""

    def resume(self) -> str:
        morceaux = [f"« {self.titre} » — {self.artiste}"]
        if self.album:
            morceaux.append(f"album {self.album}")
        if self.sortie:
            morceaux.append(self.sortie[:4])
        if self.label:
            morceaux.append(self.label)
        return " · ".join(morceaux)


def _cle() -> str:
    valeur = (config().audd_api_key or "").strip().strip("\"'")
    if not valeur:
        raise ErreurConfig(
            "Pas de clé AudD. Crée-en une gratuitement sur audd.io "
            "(300 identifications offertes) et colle-la dans .env sous "
            "AUDD_API_KEY. Sans elle, `pdz musique` mesure quand même le "
            "tempo, la tonalité et l'énergie — il ne donne juste pas le titre."
        )
    return valeur


def _lever(r: httpx.Response) -> None:
    if r.status_code == 429:
        raise ErreurQuota("Limite de débit AudD atteinte.")
    if r.status_code in (401, 403):
        raise ErreurRefus("Clé AudD refusée. Vérifie AUDD_API_KEY dans .env.")
    if r.status_code == 413:
        raise ErreurValidation("Extrait trop lourd pour AudD (10 Mo maximum).")
    if r.status_code >= 500:
        raise ErreurFournisseur(f"AudD indisponible ({r.status_code}).")
    if r.status_code >= 400:
        raise ErreurValidation(f"AudD a refusé la requête ({r.status_code}).")


# Les codes d'erreur d'AudD, traduits en messages qui disent quoi faire.
MESSAGES = {
    900: ("Clé AudD invalide ou expirée. Vérifie AUDD_API_KEY dans .env.",
          ErreurRefus),
    901: ("Plus de requêtes AudD disponibles. Le compte gratuit en donne 300 ; "
          "au-delà il faut recharger sur audd.io.", ErreurQuota),
    300: ("AudD n'a pas réussi à lire le fichier envoyé.", ErreurValidation),
}


def identifier(extrait: Path, *, timeout_s: float = 60.0,
               job_id: str | None = None) -> Morceau | None:
    """Envoie un extrait et renvoie le morceau reconnu, ou `None`.

    `None` n'est pas une erreur : c'est le résultat normal quand la musique
    n'est pas dans la base, ce qui arrive souvent avec les musiques libres de
    droits. L'appel reste facturé, et il est journalisé comme tel.
    """
    extrait = Path(extrait)
    if not extrait.exists():
        raise ErreurValidation(f"Extrait introuvable : {extrait}")
    taille = extrait.stat().st_size
    if taille > TAILLE_MAX_OCTETS:
        raise ErreurValidation(
            f"Extrait de {taille / 1e6:.1f} Mo : AudD s'arrête à 10 Mo. "
            "Réduis la durée demandée."
        )

    debut = time.perf_counter()
    try:
        with extrait.open("rb") as f:
            r = httpx.post(
                BASE,
                data={"api_token": _cle(), "return": "spotify,apple_music"},
                files={"file": (extrait.name, f, "audio/mpeg")},
                timeout=timeout_s,
            )
    except httpx.TimeoutException as e:
        raise ErreurReseau(f"AudD n'a pas répondu en {timeout_s:.0f} s.") from e
    except httpx.HTTPError as e:
        raise ErreurReseau(f"AudD injoignable : {e}") from e

    _lever(r)
    duree_ms = int((time.perf_counter() - debut) * 1000)

    try:
        charge = r.json()
    except ValueError as e:
        raise ErreurValidation("Réponse AudD illisible (JSON invalide).") from e

    _journaliser(duree_ms, job_id)

    if charge.get("status") == "error":
        erreur = charge.get("error") or {}
        code = erreur.get("error_code")
        message, classe = MESSAGES.get(
            code, (erreur.get("error_message", "erreur AudD inconnue"),
                   ErreurFournisseur)
        )
        raise classe(message)

    return morceau_depuis(charge)


def morceau_depuis(charge: dict) -> Morceau | None:
    """Lit la réponse d'AudD. `None` quand rien n'a été reconnu.

    Isolé de l'appel réseau pour être testable hors ligne — c'est la partie
    qui casse quand un fournisseur change la forme de sa réponse.
    """
    resultat = charge.get("result")
    if not resultat:
        return None

    def lien(bloc: str, *chemin: str) -> str:
        valeur = resultat.get(bloc)
        if not isinstance(valeur, dict):
            return ""
        for cle in chemin:
            valeur = valeur.get(cle) if isinstance(valeur, dict) else None
            if valeur is None:
                return ""
        return valeur if isinstance(valeur, str) else ""

    return Morceau(
        titre=resultat.get("title", "") or "",
        artiste=resultat.get("artist", "") or "",
        album=resultat.get("album", "") or "",
        sortie=resultat.get("release_date", "") or "",
        label=resultat.get("label", "") or "",
        lien=resultat.get("song_link", "") or "",
        spotify=lien("spotify", "external_urls", "spotify"),
        apple_music=lien("apple_music", "url"),
        timecode=resultat.get("timecode", "") or "",
    )


def _journaliser(duree_ms: int, job_id: str | None) -> None:
    """Une identification est un appel payant : elle entre dans `pdz cout`."""
    with db.connexion() as conn:
        conn.execute(
            "INSERT INTO appels_ia (id, job_id, agent, modele, unites, cout,"
            " duree_ms, cree_le) VALUES (?,?,?,?,?,?,?,?)",
            (db.nouvel_id("app"), job_id, "musique", "audd/recognize",
             1, COUT_PAR_REQUETE_EUR, duree_ms, db.maintenant()),
        )
