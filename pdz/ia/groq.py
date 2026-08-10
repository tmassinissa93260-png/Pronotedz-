"""Appel à un modèle de texte gratuit (Groq / Llama), pour écrire sans payer.

Existe pour une seule raison : l'API de Claude n'a pas d'offre gratuite,
contrairement à l'appli où on discute. Ce module parle le même langage
qu'elle (sortie structurée forcée, coût mesuré) mais avec un modèle Llama
hébergé par Groq, dont le palier gratuit sert des dizaines de milliers de
jetons par jour sans carte bancaire.

La **vision** passe par un modèle distinct (Llama 4 Maverick) : le registre
le choisit tout seul dès qu'un agent envoie des images, sans que le profil
ait à le savoir. Groq plafonne à 5 images par requête, contre 6 images-clés
extraites par l'analyse — la dernière est écartée, avec un avertissement.

Ce que ça **ne** fait **pas** — à savoir avant de basculer dessus :

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

import base64
import json
import logging
import mimetypes
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

# Groq documente 5 images par requête au maximum pour ses modèles de vision.
# L'analyse visuelle en extrait 6 : au-delà, on écarte plutôt que de laisser
# le fournisseur refuser toute la requête.
IMAGES_MAX = 5

# Llama rend volontiers « "true" » là où le schéma demande `true`. Groq
# valide le schéma sur son serveur : un seul champ de travers et TOUTE la
# réponse est refusée (400), après avoir été écrite et facturée. Plutôt que
# d'assouplir le schéma du domaine — qui resterait faux pour les autres
# fournisseurs — on l'assouplit à l'envoi et on rend aux booléens leur type
# à la lecture. Le reste du programme ne voit jamais la différence.
_VRAI = {"true", "vrai", "oui", "yes", "1"}


def _assouplir_booleens(schema: Any) -> Any:
    """Accepte aussi une chaîne partout où le schéma attend un booléen."""
    if not isinstance(schema, dict):
        return schema
    assoupli = dict(schema)
    if assoupli.get("type") == "boolean":
        assoupli["type"] = ["boolean", "string"]
    if isinstance(assoupli.get("properties"), dict):
        assoupli["properties"] = {
            nom: _assouplir_booleens(sous)
            for nom, sous in assoupli["properties"].items()
        }
    if "items" in assoupli:
        assoupli["items"] = _assouplir_booleens(assoupli["items"])
    return assoupli


def _durcir_booleens(valeur: Any, schema: Any) -> Any:
    """Rend leur type aux booléens, en s'appuyant sur le schéma d'origine."""
    if not isinstance(schema, dict):
        return valeur
    if schema.get("type") == "boolean" and isinstance(valeur, str):
        return valeur.strip().lower() in _VRAI
    if isinstance(valeur, dict) and isinstance(schema.get("properties"), dict):
        return {
            nom: _durcir_booleens(sous, schema["properties"].get(nom, {}))
            for nom, sous in valeur.items()
        }
    if isinstance(valeur, list) and "items" in schema:
        return [_durcir_booleens(sous, schema["items"]) for sous in valeur]
    return valeur


def _data_uri(chemin: Path) -> str:
    mime = mimetypes.guess_type(chemin.name)[0] or "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(chemin.read_bytes()).decode()}"


def _contenu_utilisateur(message: str, images: list[Path] | None):
    """Le message utilisateur, au format OpenAI.

    Sans image, une simple chaîne — c'est la forme que tous les modèles
    acceptent, y compris ceux qui ne font pas de vision. Avec images, une
    liste de blocs typés. Le texte passe en premier : les modèles
    multimodaux suivent mieux une consigne posée avant ce qu'elle décrit.
    """
    if not images:
        return message

    retenues = images[:IMAGES_MAX]
    if len(images) > IMAGES_MAX:
        log.warning(
            "%d images fournies, %d envoyées : Groq n'en accepte pas plus. "
            "L'analyse porte donc sur un échantillon un peu plus étroit.",
            len(images), IMAGES_MAX,
        )
    return [
        {"type": "text", "text": message},
        *({"type": "image_url", "image_url": {"url": _data_uri(c)}}
          for c in retenues),
    ]


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
    reg = registre()
    res = reg.resoudre(alias, profil=profil, budget_restant_pct=budget_restant_pct,
                       repli_si_cle_absente=True,
                       capacite_requise="vision" if images else None)
    modele = res.modele

    systeme = systeme_stable
    if systeme_variable:
        systeme = f"{systeme_stable}\n\n{systeme_variable}"

    corps: dict[str, Any] = {
        "model": modele.id,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": systeme},
            {"role": "user", "content": _contenu_utilisateur(message, images)},
        ],
        # Format OpenAI : « function », pas « tool » comme chez Anthropic —
        # c'est la seule vraie différence de forme entre les deux API.
        "tools": [{
            "type": "function",
            "function": {
                "name": nom_outil,
                "description": "Renvoie la réponse dans le format demandé.",
                "parameters": _assouplir_booleens(schema_sortie),
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
    donnees = _durcir_booleens(_extraire_outil(charge, nom_outil), schema_sortie)
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
