"""Appel à Claude, avec sortie structurée, cache de prompt et coût mesuré.

Trois choix qui font la différence en production :

1. **Sortie structurée forcée** — on passe un JSON Schema en outil et on force
   son usage. Claude renvoie alors du JSON valide, pas du texte à découper à la
   regex. Plus de pipeline qui casse parce que le modèle a ajouté une phrase
   d'introduction.

2. **Cache de prompt** — les blocs stables (règles de l'univers, casting) sont
   marqués `cache_control`. Sur une série, ils sont identiques d'un épisode à
   l'autre : ~10 % du prix au lieu de 100 %.

3. **Coût mesuré, pas estimé** — chaque réponse contient son `usage`. On l'écrit
   en base. C'est la seule façon de savoir où part l'argent.
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import time
from pathlib import Path
from typing import Any

import httpx

from pdz import db
from pdz.ia.registre import Modele, registre
from pdz.moteur.erreurs import (
    ErreurFournisseur,
    ErreurQuota,
    ErreurRefus,
    ErreurReseau,
    ErreurValidation,
)

log = logging.getLogger(__name__)

VERSION_API = "2023-06-01"


class ReponseClaude:
    def __init__(self, donnees: dict, usage: dict, modele: Modele, duree_ms: int):
        self.donnees = donnees
        self.usage = usage
        self.modele = modele
        self.duree_ms = duree_ms

    @property
    def cout(self) -> float:
        u = self.usage
        return self.modele.cout_texte(
            entree=u.get("input_tokens", 0),
            sortie=u.get("output_tokens", 0),
            cache_lu=u.get("cache_read_input_tokens", 0),
            cache_ecrit=u.get("cache_creation_input_tokens", 0),
        )

    @property
    def economie_cache(self) -> float:
        """Ce que le cache a évité de payer sur cet appel."""
        lus = self.usage.get("cache_read_input_tokens", 0)
        plein = lus * self.modele.prix.entree_par_million / 1_000_000
        return plein - plein * self.modele.cache.lecture


async def appeler(
    *,
    alias: str,
    systeme_stable: str,
    systeme_variable: str = "",
    message: str,
    schema_sortie: dict,
    images: list[Path] | None = None,
    nom_outil: str = "reponse",
    max_tokens: int = 4000,
    temperature: float | None = None,
    profil: str = "equilibre",
    budget_restant_pct: float = 100.0,
    job_id: str | None = None,
    etape: str | None = None,
    agent: str | None = None,
    prompt_ref: str | None = None,
) -> ReponseClaude:
    """Un appel à Claude qui renvoie du JSON conforme au schéma, ou lève.

    `systeme_stable` est mis en cache. C'est là que doit aller tout ce qui ne
    change pas d'un épisode à l'autre : les règles du monde, le casting, le
    style. `systeme_variable` contient ce qui bouge.
    """
    reg = registre()
    res = reg.resoudre(alias, profil=profil, budget_restant_pct=budget_restant_pct)
    modele = res.modele

    # Bloc système : la partie stable est marquée pour le cache.
    systeme: list[dict[str, Any]] = [{
        "type": "text",
        "text": systeme_stable,
        "cache_control": {"type": "ephemeral"},
    }]
    if systeme_variable:
        systeme.append({"type": "text", "text": systeme_variable})

    corps = {
        "model": modele.id,
        "max_tokens": max_tokens,          # jamais absent — voir docs/06-solidite.md
        "system": systeme,
        "messages": [{"role": "user", "content": _contenu(message, images)}],
        # Sortie structurée : on impose l'outil, donc la forme de la réponse.
        "tools": [{
            "name": nom_outil,
            "description": "Renvoie la réponse dans le format demandé.",
            "input_schema": schema_sortie,
        }],
        "tool_choice": {"type": "tool", "name": nom_outil},
    }
    temp = temperature if temperature is not None else res.temperature
    if temp is not None:
        corps["temperature"] = temp

    entetes = {
        "x-api-key": reg.cle_fournisseur("anthropic"),
        "anthropic-version": VERSION_API,
        "content-type": "application/json",
    }

    debut = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(
                f"{reg.base_url('anthropic')}/messages",
                headers=entetes, json=corps,
            )
    except httpx.TimeoutException as e:
        raise ErreurReseau(f"Claude n'a pas répondu en 120 s ({alias})") from e
    except httpx.HTTPError as e:
        raise ErreurReseau(f"Connexion à Claude impossible : {e}") from e

    duree_ms = int((time.perf_counter() - debut) * 1000)
    _lever_si_erreur(r)

    charge = r.json()

    if charge.get("stop_reason") == "refusal":
        raise ErreurRefus("Claude a refusé de répondre à cette demande.")

    donnees = _extraire_outil(charge, nom_outil)
    reponse = ReponseClaude(donnees, charge.get("usage", {}), modele, duree_ms)

    _journaliser(reponse, job_id, etape, agent, prompt_ref)
    log.info(
        "Claude %s — %d ms, %.4f € (cache : %.4f € évités)",
        modele.id, duree_ms, reponse.cout, reponse.economie_cache,
    )
    return reponse


def _contenu(message: str, images: list[Path] | None) -> Any:
    """Construit le contenu du message — texte seul, ou images puis texte.

    L'ordre compte : les images **avant** la consigne. C'est la
    recommandation d'Anthropic, et l'écart est net quand on demande une
    description structurée de plusieurs images à la fois.

    Chaque image est étiquetée par son rang. Sans ces étiquettes, une réponse
    qui dit « la troisième image » est inexploitable : on ne sait pas à quel
    fichier elle correspond.
    """
    if not images:
        return message

    blocs: list[dict[str, Any]] = []
    for i, chemin in enumerate(images, start=1):
        chemin = Path(chemin)
        if not chemin.exists():
            raise ErreurValidation(f"Image introuvable : {chemin}")
        mime = mimetypes.guess_type(chemin.name)[0] or "image/png"
        if mime not in ("image/png", "image/jpeg", "image/gif", "image/webp"):
            raise ErreurValidation(
                f"Format d'image non accepté par l'API ({mime}) : {chemin.name}"
            )
        blocs.append({"type": "text", "text": f"Image {i} — {chemin.name}"})
        blocs.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": mime,
                "data": base64.b64encode(chemin.read_bytes()).decode(),
            },
        })

    blocs.append({"type": "text", "text": message})
    return blocs


def _lever_si_erreur(r: httpx.Response) -> None:
    if r.status_code < 400:
        return

    detail = ""
    try:
        detail = r.json().get("error", {}).get("message", "")
    except Exception:
        detail = r.text[:300]

    if r.status_code == 429:
        raise ErreurQuota(
            f"Limite de débit Anthropic atteinte. {detail}",
            retry_after=float(r.headers.get("retry-after", 0)) or None,
        )
    if r.status_code in (401, 403):
        raise ErreurRefus(f"Clé d'API Anthropic refusée ({r.status_code}). {detail}")
    if r.status_code >= 500:
        raise ErreurFournisseur(f"Anthropic indisponible ({r.status_code}). {detail}")
    raise ErreurValidation(f"Requête refusée par Anthropic ({r.status_code}). {detail}")


def _extraire_outil(charge: dict, nom_outil: str) -> dict:
    for bloc in charge.get("content", []):
        if bloc.get("type") == "tool_use" and bloc.get("name") == nom_outil:
            return bloc.get("input", {})

    # Ne devrait pas arriver avec tool_choice forcé, mais si le modèle est
    # tronqué par max_tokens il renvoie du texte : c'est réparable au 2e essai.
    if charge.get("stop_reason") == "max_tokens":
        raise ErreurValidation(
            "Réponse coupée : max_tokens trop bas pour cette sortie."
        )
    raise ErreurValidation(
        f"Aucune sortie structurée « {nom_outil} » dans la réponse. "
        f"stop_reason={charge.get('stop_reason')}"
    )


def _journaliser(reponse: ReponseClaude, job_id, etape, agent, prompt_ref) -> None:
    """Une ligne par appel payant. Sans ça, on découvre le coût sur le relevé."""
    u = reponse.usage
    with db.connexion() as conn:
        conn.execute(
            "INSERT INTO appels_ia (id, job_id, etape_cle, agent, modele, prompt_ref,"
            " tokens_in, tokens_out, tokens_cache, cout, duree_ms, cree_le)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                db.nouvel_id("app"), job_id, etape, agent, reponse.modele.id, prompt_ref,
                u.get("input_tokens", 0), u.get("output_tokens", 0),
                u.get("cache_read_input_tokens", 0),
                reponse.cout, reponse.duree_ms, db.maintenant(),
            ),
        )


def schema_depuis(proprietes: dict, requis: list[str]) -> dict:
    """Petit raccourci pour décrire une sortie attendue."""
    return {
        "type": "object",
        "properties": proprietes,
        "required": requis,
        "additionalProperties": False,
    }
