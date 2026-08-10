"""Pollinations.ai — images, sans clé et sans carte bancaire.

L'alternative à fal.ai pour le profil « gratuit » : aucune inscription,
aucun paiement, rien à coller dans `.env`. La contrepartie, à connaître avant
de choisir ce profil : contrairement à fal.ai, ce service ne prend pas
d'image de référence en entrée. Le mécanisme qui garde un personnage
identique d'un plan à l'autre (voir `pdz/production/images.py`) ne
s'applique donc pas ici — la constance visuelle sera moins bonne qu'avec
fal.ai, surtout sur un épisode à plusieurs plans du même personnage.

⚠️ Non vérifiable depuis l'environnement de développement : image.pollinations.ai
y est bloqué par la politique réseau. Écrit d'après leur documentation
publique (endpoint GET synchrone, pas de clé) ; à confirmer sur la machine
de l'utilisateur.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from urllib.parse import quote

import httpx

from pdz import db
from pdz.ia.registre import registre
from pdz.moteur.erreurs import (
    ErreurFournisseur,
    ErreurQuota,
    ErreurReseau,
    ErreurValidation,
)

log = logging.getLogger(__name__)

BASE = "https://image.pollinations.ai/prompt"

# Proche du 9:16 utilisé ailleurs dans le projet, en multiples de 16 —
# attendu par les modèles de diffusion sous-jacents.
LARGEUR, HAUTEUR = 896, 1600


def _lever(r: httpx.Response) -> None:
    if r.status_code < 400:
        return
    if r.status_code == 429:
        raise ErreurQuota("Limite de débit Pollinations atteinte (image).")
    if r.status_code >= 500:
        raise ErreurFournisseur(f"Pollinations indisponible ({r.status_code}, image).")
    raise ErreurValidation(f"Pollinations a refusé la requête ({r.status_code}, image).")


def _journaliser(modele: str, duree_ms: int, job_id: str | None,
                 etape: str | None, agent: str | None) -> None:
    with db.connexion() as conn:
        conn.execute(
            "INSERT INTO appels_ia (id, job_id, etape_cle, agent, modele,"
            " unites, cout, duree_ms, cree_le) VALUES (?,?,?,?,?,?,?,?,?)",
            (db.nouvel_id("app"), job_id, etape, agent, modele,
             1, 0.0, duree_ms, db.maintenant()),
        )


def generer_image(
    prompt: str, destination: Path, *,
    alias: str = "images",
    image_reference: Path | None = None,  # ignoré, voir docstring du module
    seed: int | None = None,
    profil: str = "equilibre",
    budget_restant_pct: float = 100.0,
    job_id: str | None = None,
    etape: str | None = None,
    agent: str | None = None,
) -> tuple[Path, float]:
    """Génère une image et l'écrit sur le disque. Renvoie (chemin, coût=0)."""
    modele = registre().resoudre(
        alias, profil=profil, budget_restant_pct=budget_restant_pct,
        repli_si_cle_absente=True,
    ).modele

    params: dict[str, str | int] = {
        "width": LARGEUR, "height": HAUTEUR, "nologo": "true",
        # `safe` fait échouer la requête plutôt que de renvoyer un contenu
        # inapproprié : mesuré en conditions réelles, un prompt de
        # personnage cartoon a produit une image d'humain dénudé sans lui.
        # `enhance=false` empêche Pollinations de réécrire le prompt à sa
        # façon — on veut le respect exact de l'apparence du personnage,
        # pas une réinterprétation créative.
        "safe": "true",
        "enhance": "false",
    }
    if seed is not None:
        params["seed"] = seed

    destination.parent.mkdir(parents=True, exist_ok=True)
    debut = time.perf_counter()
    try:
        with httpx.stream(
            "GET", f"{BASE}/{quote(prompt)}", params=params,
            timeout=180, follow_redirects=True,
        ) as r:
            _lever(r)
            with destination.open("wb") as f:
                for bloc in r.iter_bytes(65536):
                    f.write(bloc)
    except httpx.TimeoutException as e:
        raise ErreurReseau("Pollinations n'a pas répondu en 180 s (image).") from e
    except httpx.HTTPError as e:
        raise ErreurReseau(f"Pollinations injoignable : {e}") from e

    if not destination.exists() or destination.stat().st_size < 1000:
        raise ErreurValidation("Pollinations n'a renvoyé aucune image exploitable.")

    duree_ms = int((time.perf_counter() - debut) * 1000)
    _journaliser(modele.id, duree_ms, job_id, etape, agent)

    log.info("Image %s → %s (%d ms, gratuit)", modele.id, destination.name, duree_ms)
    return destination, 0.0
