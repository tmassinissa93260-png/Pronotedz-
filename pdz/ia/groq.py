"""Appel à un modèle de texte gratuit (Groq / Llama), pour écrire sans payer.

Existe pour une seule raison : l'API de Claude n'a pas d'offre gratuite,
contrairement à l'appli où on discute. Ce module parle le même langage
qu'elle (sortie structurée forcée, coût mesuré) mais avec un modèle Llama
hébergé par Groq, dont le palier gratuit sert des dizaines de milliers de
jetons par jour sans carte bancaire.

Ce que ça **ne** fait **pas** — à savoir avant de basculer dessus :

  · **pas de vision.** Le modèle est en texte seul. Un agent qui envoie des
    images (`analyse/charte`, pour regarder une vidéo de référence) échouera
    ici avec un message clair plutôt qu'une erreur HTTP obscure.
  · **pas de cache de prompt.** Claude relit le contexte d'univers à 10 % du
    prix sur une série ; Groq n'a pas cet équivalent documenté. Sans
    conséquence sur le coût puisque c'est déjà gratuit, mais la facture
    d'entrée est pleine à chaque appel — sans importance ici.
  · **une écriture probablement moins fine.** Llama tient une contrainte de
    format mieux qu'une contrainte de ton. À réserver au dépannage, pas au
    choix par défaut si le budget Claude est possible.

⚠️ Ce module n'a jamais pu être exécuté depuis l'environnement de
développement : la politique réseau y bloque `api.groq.com`. L'identifiant
de modèle (`llama-3.3-70b-versatile`) vient du catalogue Groq documenté au
moment de l'écriture — si Groq l'a renommé, l'appel échouera avec un message
« model not found » explicite, pas silencieusement.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import httpx

from pdz import db
from pdz.ia.registre import Modele, registre
from pdz.moteur.erreurs import (
    ErreurConfig,
    ErreurFournisseur,
    ErreurQuota,
    ErreurRefus,
    ErreurReseau,
    ErreurValidation,
)

log = logging.getLogger(__name__)


class ReponseGroq:
    """Même forme que `ReponseClaude` : c'est ce que `pdz.ia.texte` attend
    en retour, quel que soit le fournisseur choisi en dessous."""

    def __init__(self, donnees: dict, usage: dict, modele: Modele, duree_ms: int):
        self.donnees = donnees
        self.usage = usage
        self.modele = modele
        self.duree_ms = duree_ms

    @property
    def cout(self) -> float:
        u = self.usage
        return self.modele.cout_texte(
            entree=u.get("prompt_tokens", 0),
            sortie=u.get("completion_tokens", 0),
        )

    @property
    def economie_cache(self) -> float:
        # Pas de cache de prompt côté Groq : toujours nul. Le champ existe
        # pour que le journal puisse traiter les deux fournisseurs pareil.
        return 0.0


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
) -> ReponseGroq:
    """Même contrat que `pdz.ia.claude.appeler` — voir ce module pour le détail
    des paramètres. Seule la mécanique HTTP change (API compatible OpenAI)."""
    if images:
        raise ErreurConfig(
            "Cet agent envoie des images, et le modèle gratuit (Groq/Llama) "
            "ne fait pas de vision. Cette étape a besoin de crédit Anthropic "
            "— console.anthropic.com → Billing — ou reste réservée au profil "
            "par défaut."
        )

    reg = registre()
    res = reg.resoudre(alias, profil=profil, budget_restant_pct=budget_restant_pct,
                       repli_si_cle_absente=True)
    modele = res.modele

    systeme = systeme_stable
    if systeme_variable:
        systeme = f"{systeme_stable}\n\n{systeme_variable}"

    corps: dict[str, Any] = {
        "model": modele.id,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": systeme},
            {"role": "user", "content": message},
        ],
        # Format OpenAI : « function », pas « tool » comme chez Anthropic —
        # c'est la seule vraie différence de forme entre les deux API.
        "tools": [{
            "type": "function",
            "function": {
                "name": nom_outil,
                "description": "Renvoie la réponse dans le format demandé.",
                "parameters": schema_sortie,
            },
        }],
        "tool_choice": {"type": "function", "function": {"name": nom_outil}},
    }
    temp = temperature if temperature is not None else res.temperature
    if temp is not None:
        corps["temperature"] = temp

    entetes = {
        "Authorization": f"Bearer {reg.cle_fournisseur('groq')}",
        "content-type": "application/json",
    }

    debut = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(
                f"{reg.base_url('groq')}/chat/completions",
                headers=entetes, json=corps,
            )
    except httpx.TimeoutException as e:
        raise ErreurReseau(f"Groq n'a pas répondu en 120 s ({alias})") from e
    except httpx.HTTPError as e:
        raise ErreurReseau(f"Connexion à Groq impossible : {e}") from e

    duree_ms = int((time.perf_counter() - debut) * 1000)
    _lever_si_erreur(r)

    charge = r.json()
    donnees = _extraire_outil(charge, nom_outil)
    reponse = ReponseGroq(donnees, charge.get("usage", {}), modele, duree_ms)

    _journaliser(reponse, job_id, etape, agent, prompt_ref)
    log.info("Groq %s — %d ms, gratuit", modele.id, duree_ms)
    return reponse


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
            f"Limite de débit Groq atteinte (le palier gratuit est journalier). {detail}",
            retry_after=float(r.headers.get("retry-after", 0)) or None,
        )
    if r.status_code in (401, 403):
        raise ErreurRefus(f"Clé d'API Groq refusée ({r.status_code}). {detail}")
    if r.status_code == 404 and "model" in detail.lower():
        raise ErreurConfig(
            f"Modèle Groq introuvable : {detail}. Le nom a peut-être changé "
            "— vérifie le catalogue sur console.groq.com et ajuste "
            "modeles.yaml."
        )
    if r.status_code >= 500:
        raise ErreurFournisseur(f"Groq indisponible ({r.status_code}). {detail}")
    raise ErreurValidation(f"Requête refusée par Groq ({r.status_code}). {detail}")


def _extraire_outil(charge: dict, nom_outil: str) -> dict:
    choix = (charge.get("choices") or [{}])[0]
    message = choix.get("message") or {}

    for appel in message.get("tool_calls") or []:
        fonction = appel.get("function") or {}
        if fonction.get("name") == nom_outil:
            try:
                return json.loads(fonction.get("arguments") or "{}")
            except json.JSONDecodeError as e:
                raise ErreurValidation(
                    f"Groq a renvoyé un JSON invalide pour « {nom_outil} » : {e}"
                ) from e

    if choix.get("finish_reason") == "length":
        raise ErreurValidation(
            "Réponse coupée : max_tokens trop bas pour cette sortie."
        )
    raise ErreurValidation(
        f"Aucune sortie structurée « {nom_outil} » dans la réponse Groq. "
        f"finish_reason={choix.get('finish_reason')}"
    )


def _journaliser(reponse: ReponseGroq, job_id, etape, agent, prompt_ref) -> None:
    u = reponse.usage
    with db.connexion() as conn:
        conn.execute(
            "INSERT INTO appels_ia (id, job_id, etape_cle, agent, modele, prompt_ref,"
            " tokens_in, tokens_out, tokens_cache, cout, duree_ms, cree_le)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                db.nouvel_id("app"), job_id, etape, agent, reponse.modele.id, prompt_ref,
                u.get("prompt_tokens", 0), u.get("completion_tokens", 0), 0,
                reponse.cout, reponse.duree_ms, db.maintenant(),
            ),
        )
