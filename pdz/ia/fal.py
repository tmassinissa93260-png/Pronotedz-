"""fal.ai — images (FLUX) **et** animation (Kling), avec la même clé.

Deux façons d'appeler fal, et le choix n'est pas anodin :

  · `fal.run/...`        — synchrone. Bien pour une image (2 à 8 s).
  · `queue.fal.run/...`  — file d'attente. **Obligatoire pour la vidéo** :
                           une animation prend 1 à 3 minutes, aucun appel
                           synchrone ne tient aussi longtemps sans tomber en
                           timeout côté réseau ou côté proxy.

⚠️ Ce module n'a pas pu être exécuté depuis l'environnement de développement :
la politique réseau y bloque `fal.run`. Il est écrit pour la machine de
l'utilisateur. Tout ce qui ne dépend pas du réseau — construction des
requêtes, lecture des réponses, calcul du coût, classement des erreurs — est
testé hors ligne.
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import time
from pathlib import Path

import httpx

from pdz import db
from pdz.ia.registre import registre
from pdz.moteur.erreurs import (
    ErreurFournisseur,
    ErreurQuota,
    ErreurRefus,
    ErreurReseau,
    ErreurValidation,
)

log = logging.getLogger(__name__)

DIRECT = "https://fal.run"
FILE = "https://queue.fal.run"

# Formats verticaux acceptés par les modèles d'image de fal.
FORMAT_VERTICAL = "portrait_16_9"


def _entetes() -> dict[str, str]:
    return {
        "Authorization": f"Key {registre().cle_fournisseur('fal')}",
        "Content-Type": "application/json",
    }


def _lever(r: httpx.Response, quoi: str) -> None:
    if r.status_code < 400:
        return
    detail = r.text[:400]
    if r.status_code in (401, 403):
        raise ErreurRefus(f"Clé fal.ai refusée ({quoi}). Vérifie FAL_KEY dans .env.")
    if r.status_code == 429:
        raise ErreurQuota(f"Limite de débit fal.ai atteinte ({quoi}).")
    if r.status_code == 402:
        raise ErreurRefus(
            f"Crédit fal.ai épuisé ({quoi}). Recharge dans l'onglet Billing."
        )
    if r.status_code >= 500:
        raise ErreurFournisseur(f"fal.ai indisponible ({r.status_code}, {quoi}).")
    raise ErreurValidation(f"fal.ai a refusé la requête ({r.status_code}, {quoi}). {detail}")


def _data_uri(chemin: Path) -> str:
    """Encode une image locale en URI de données.

    Évite d'avoir à téléverser le fichier puis à gérer une URL temporaire :
    une image de départ pèse quelques centaines de kilo-octets, ça passe
    largement dans le corps de la requête.
    """
    mime = mimetypes.guess_type(chemin.name)[0] or "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(chemin.read_bytes()).decode()}"


def _telecharger(url: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with httpx.stream("GET", url, timeout=180, follow_redirects=True) as r:
            r.raise_for_status()
            with destination.open("wb") as f:
                for bloc in r.iter_bytes(65536):
                    f.write(bloc)
    except httpx.HTTPError as e:
        raise ErreurReseau(f"Téléchargement impossible depuis fal.ai : {e}") from e
    return destination


def _journaliser(modele: str, unites: float, cout: float, duree_ms: int,
                 job_id: str | None, etape: str | None, agent: str | None) -> None:
    with db.connexion() as conn:
        conn.execute(
            "INSERT INTO appels_ia (id, job_id, etape_cle, agent, modele,"
            " unites, cout, duree_ms, cree_le) VALUES (?,?,?,?,?,?,?,?,?)",
            (db.nouvel_id("app"), job_id, etape, agent, modele,
             unites, cout, duree_ms, db.maintenant()),
        )


# ── Images ───────────────────────────────────────────────────────────────

def generer_image(
    prompt: str, destination: Path, *,
    alias: str = "images",
    image_reference: Path | None = None,
    seed: int | None = None,
    profil: str = "equilibre",
    budget_restant_pct: float = 100.0,
    job_id: str | None = None,
    etape: str | None = None,
    agent: str | None = None,
) -> tuple[Path, float]:
    """Génère une image et l'écrit sur le disque. Renvoie (chemin, coût).

    `image_reference` sert la constance des personnages : chaque plan repart
    de la fiche du personnage plutôt que d'une génération libre.
    """
    reg = registre()
    res = reg.resoudre(alias, profil=profil, budget_restant_pct=budget_restant_pct,
                       repli_si_cle_absente=True)
    modele = res.modele

    corps: dict = {
        "prompt": prompt,
        "image_size": FORMAT_VERTICAL,
        "num_images": 1,
        "enable_safety_checker": True,
    }
    if seed is not None:
        corps["seed"] = seed
    if image_reference is not None:
        corps["image_url"] = _data_uri(image_reference)

    debut = time.perf_counter()
    try:
        r = httpx.post(f"{DIRECT}/{modele.id}", headers=_entetes(),
                       json=corps, timeout=180)
    except httpx.TimeoutException as e:
        raise ErreurReseau("fal.ai n'a pas répondu en 180 s (image).") from e
    except httpx.HTTPError as e:
        raise ErreurReseau(f"fal.ai injoignable : {e}") from e

    _lever(r, "image")
    duree_ms = int((time.perf_counter() - debut) * 1000)

    images = r.json().get("images") or []
    if not images or not images[0].get("url"):
        raise ErreurValidation("fal.ai n'a renvoyé aucune image.")

    _telecharger(images[0]["url"], destination)
    cout = modele.cout_unites(1, "image")
    _journaliser(modele.id, 1, cout, duree_ms, job_id, etape, agent)

    log.info("Image %s → %s (%d ms, %.4f €)", modele.id, destination.name,
             duree_ms, cout)
    return destination, cout


# ── Animation ────────────────────────────────────────────────────────────

def animer_image(
    image: Path, prompt: str, destination: Path, *,
    duree_s: int = 5,
    alias: str = "animation",
    profil: str = "equilibre",
    budget_restant_pct: float = 100.0,
    attente_max_s: int = 420,
    job_id: str | None = None,
    etape: str | None = None,
    agent: str | None = None,
) -> tuple[Path, float]:
    """Anime une image fixe. Passe par la file : ça prend 1 à 3 minutes.

    C'est le poste le plus cher du système — d'où le garde-fou de budget
    vérifié avant l'envoi plutôt qu'après.
    """
    reg = registre()
    res = reg.resoudre(alias, profil=profil, budget_restant_pct=budget_restant_pct,
                       repli_si_cle_absente=True)
    modele = res.modele

    cout_prevu = modele.cout_unites(duree_s, "seconde")
    log.info("Animation %s : %d s prévues, ~%.3f €", modele.id, duree_s, cout_prevu)

    corps = {
        "prompt": prompt,
        "image_url": _data_uri(image),
        "duration": str(duree_s),
        "aspect_ratio": "9:16",
    }

    debut = time.perf_counter()
    try:
        r = httpx.post(f"{FILE}/{modele.id}", headers=_entetes(),
                       json=corps, timeout=120)
    except httpx.HTTPError as e:
        raise ErreurReseau(f"fal.ai injoignable (animation) : {e}") from e
    _lever(r, "animation")

    requete = r.json().get("request_id")
    if not requete:
        raise ErreurValidation("fal.ai n'a pas renvoyé d'identifiant de requête.")

    url = _attendre(modele.id, requete, attente_max_s)
    _telecharger(url, destination)

    duree_ms = int((time.perf_counter() - debut) * 1000)
    _journaliser(modele.id, duree_s, cout_prevu, duree_ms, job_id, etape, agent)

    log.info("Animation → %s (%d s d'attente, %.3f €)",
             destination.name, duree_ms // 1000, cout_prevu)
    return destination, cout_prevu


def _attendre(modele_id: str, requete: str, attente_max_s: int) -> str:
    """Interroge la file jusqu'à ce que le rendu soit prêt.

    L'intervalle grandit progressivement : inutile de marteler le serveur
    pendant les vingt premières secondes, où rien n'est jamais prêt.
    """
    base = f"{FILE}/{modele_id.split('/')[0]}/{modele_id.split('/', 1)[1]}"
    debut, intervalle = time.monotonic(), 3.0

    while time.monotonic() - debut < attente_max_s:
        time.sleep(intervalle)
        intervalle = min(intervalle * 1.35, 15.0)
        try:
            s = httpx.get(f"{base}/requests/{requete}/status",
                          headers=_entetes(), timeout=60)
        except httpx.HTTPError as e:
            raise ErreurReseau(f"Suivi de file impossible : {e}") from e
        _lever(s, "suivi d'animation")

        etat = s.json().get("status")
        if etat == "COMPLETED":
            r = httpx.get(f"{base}/requests/{requete}", headers=_entetes(), timeout=120)
            _lever(r, "résultat d'animation")
            return url_video(r.json())
        if etat in ("FAILED", "CANCELLED"):
            raise ErreurFournisseur(f"fal.ai a abandonné le rendu ({etat}).")

    raise ErreurReseau(
        f"Animation toujours pas prête après {attente_max_s} s. "
        "Le rendu continue peut-être chez fal.ai — relancer l'étape la reprendra."
    )


def url_video(charge: dict) -> str:
    """Extrait l'URL de la vidéo — la forme varie selon le modèle."""
    video = charge.get("video")
    if isinstance(video, dict) and video.get("url"):
        return video["url"]
    if isinstance(video, str) and video.startswith("http"):
        return video
    videos = charge.get("videos") or []
    if videos and isinstance(videos[0], dict) and videos[0].get("url"):
        return videos[0]["url"]
    raise ErreurValidation(f"Aucune vidéo dans la réponse fal.ai : {list(charge)}")
