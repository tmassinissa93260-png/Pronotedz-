"""Adaptateur Groq — raisonneur gratuit, sorties contraintes par appel d'outil.

    ⚠️ JAMAIS EXÉCUTÉ DANS L'ENVIRONNEMENT OÙ CE CODE A ÉTÉ ÉCRIT.

`api.groq.com` y est injoignable. La forme de l'API et le choix du modèle ne
sont pourtant **pas devinés** : ils viennent de connaissances mesurées en
production, que ce fichier consigne pour qu'on sache d'où elles sortent.

## Ce qui est su, et comment

**La contrainte de forme passe par un appel d'outil forcé**, pas par
`response_format`. C'est la forme OpenAI : `tools: [{type: "function", …}]`
plus `tool_choice` qui désigne cette fonction. Le schéma part dans
`function.parameters`, et la décision revient dans les arguments de l'appel.

**Groq rend parfois `"true"` en chaîne là où le schéma attend un booléen.**
Le contrat `VisualProofDraft.acknowledged_dispute` est un booléen : sans
traitement, la décision serait refusée à chaque fois qu'un modèle prend cette
liberté. Le schéma envoyé accepte donc les deux types, et la réponse est
durcie au retour. Ce n'est pas de la complaisance : le contrat, lui, reste
strict — c'est la traduction d'un dialecte, pas un assouplissement.

**Le modèle par défaut est `openai/gpt-oss-120b`.** Le choix est daté :
`llama-3.3-70b-versatile` a été coupé par Groq le 17/06/2026, ce qui s'est
mesuré en production le 18/08/2026 par un 404 « modèle introuvable » avant le
premier appel. Un identifiant périmé n'est pas rattrapable par un repli : il
arrête tout. La sonde de ce module vérifie donc que le modèle est réellement
au catalogue, et le dit s'il n'y est plus.

Ce qui n'est pas su : si la décision produite tiendra le contrat. C'est le
travail du contrat de le dire, et de la boucle de reprise de `reasoning.py`
d'en donner une seconde chance.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

from pdz2.contracts.capability import CapabilityState, ProviderCapability
from pdz2.contracts.direction import DirectorBrief
from pdz2.contracts.research import ResearchState, TopicRequest
from pdz2.engines.direction.ports import ReasonerUnavailable
from pdz2.providers.reasoning import SYSTEM, decision_schema, draft_with

__all__ = [
    "GroqReasoner",
    "GROQ_KEY_ENV",
    "GROQ_MODEL_ENV",
    "GROQ_TPM_ENV",
    "DEFAULT_MODEL",
    "DEFAULT_TPM",
]

GROQ_KEY_ENV = "GROQ_API_KEY"
GROQ_MODEL_ENV = "GROQ_MODEL"
GROQ_TPM_ENV = "GROQ_TPM"
BASE_URL = "https://api.groq.com/openai/v1"

DEFAULT_TPM = 8000
"""Jetons par minute du palier gratuit, **mesuré** le 25/08/2026 :

    413 — Request too large for `openai/gpt-oss-120b` … service tier
    `on_demand` on tokens per minute (TPM): Limit 8000, Requested 18813

Le piège tient dans ce « Requested » : il ne compte pas ce qu'on envoie, mais
ce qu'on envoie **plus la sortie qu'on réserve**. Une demande de 16 000 jetons
de sortie brûle donc deux fois le plafond avant d'avoir écrit un mot. Un
compte payant relève cette limite : `GROQ_TPM` permet de le déclarer."""

DEFAULT_MODEL = "openai/gpt-oss-120b"
"""Écriture, sans vision, sorties structurées. Voir l'en-tête pour la date."""

_TOOL_NAME = "decision_de_realisation"
_PROBE_TIMEOUT_S = 20.0
_DECISION_TIMEOUT_S = 300.0
_TEMPERATURE = 0.4

_CARACTERES_PAR_JETON = 3.4
"""Estimation, volontairement pessimiste, pour du JSON en français.

On ne compte pas les jetons exactement : il faudrait le tokeniseur du modèle,
qui n'est pas là. Sous-estimer coûterait un refus, alors on surestime — et
`_MARGE` absorbe le reste."""

_MARGE_JETONS = 400
_SORTIE_MINIMALE = 1500
"""En dessous, une décision de six preuves visuelles ne tient pas. Mieux vaut
refuser en le disant que rendre un brief tronqué."""

_SORTIE_MAXIMALE = 8000
_FENETRE_S = 60.0

_FRACTION_UTILISABLE = 0.92
"""On ne vise pas le plafond, on vise en dessous.

Le compte de jetons est estimé ici et exact chez Groq ; viser la limite au
jeton près, c'est transformer chaque écart d'estimation en refus. Huit pour
cent de réserve coûtent quelques centaines de jetons de sortie et évitent de
rejouer un épisode entier pour une virgule."""

_VRAI = {"true", "vrai", "oui", "yes", "1"}


# ------------------------------------------------- le dialecte des booléens


def _accepte_aussi_une_chaine(schema: Any) -> Any:
    """Autorise `"true"` partout où le schéma attend un booléen.

    Élargir le schéma **envoyé** n'élargit rien du contrat : la décision est
    durcie au retour, puis jugée par `DirectorBrief` comme n'importe quelle
    autre. On accepte un dialecte à la porte, pas dans la maison.
    """
    if isinstance(schema, list):
        return [_accepte_aussi_une_chaine(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    large = {cle: _accepte_aussi_une_chaine(valeur) for cle, valeur in schema.items()}
    if large.get("type") == "boolean":
        large["type"] = ["boolean", "string"]
    return large


def _rend_leur_type(valeur: Any, schema: Any, defs: dict[str, Any]) -> Any:
    """Retraduit les booléens rendus en chaîne, en suivant le schéma d'origine."""
    if isinstance(schema, dict) and "$ref" in schema:
        schema = defs.get(schema["$ref"].rsplit("/", 1)[-1], {})
    if not isinstance(schema, dict):
        return valeur
    if schema.get("type") == "boolean" and isinstance(valeur, str):
        return valeur.strip().lower() in _VRAI
    if isinstance(valeur, dict) and isinstance(schema.get("properties"), dict):
        return {
            nom: _rend_leur_type(sous, schema["properties"].get(nom, {}), defs)
            for nom, sous in valeur.items()
        }
    if isinstance(valeur, list) and "items" in schema:
        return [_rend_leur_type(sous, schema["items"], defs) for sous in valeur]
    return valeur


def _jetons(charge: Any) -> int:
    """Taille estimée d'un fragment de requête, en jetons."""
    texte = charge if isinstance(charge, str) else json.dumps(charge, ensure_ascii=False)
    return int(len(texte) / _CARACTERES_PAR_JETON) + 1


# ------------------------------------------------------------- adaptateur


@dataclass
class GroqReasoner:
    """Raisonneur distant, sur le palier gratuit de Groq."""

    name: str = "groq"
    model: str = field(default_factory=lambda: _modele_demande())
    temperature: float = _TEMPERATURE
    tpm: int = field(default_factory=lambda: _plafond_declare())
    """Jetons par minute autorisés. Voir `DEFAULT_TPM` pour d'où vient le chiffre."""

    notes: list[str] = field(default_factory=list)
    _last_usage: dict[str, int] = field(default_factory=dict, repr=False)
    _fenetre_ouverte_a: float = field(default=0.0, repr=False)
    _consomme: int = field(default=0, repr=False)

    # ------------------------------------------------------------- sonde

    def _cle(self) -> str | None:
        return os.environ.get(GROQ_KEY_ENV, "").strip() or None

    def get_capabilities(self) -> ProviderCapability:
        """Vérifie la clé **et** que le modèle est encore au catalogue.

        Le second point n'est pas du zèle : un identifiant retiré par Groq
        fait échouer la production avant le premier appel, et l'a déjà fait.
        """
        cle = self._cle()
        if cle is None:
            return self._capacite(False, f"{GROQ_KEY_ENV} absente de l'environnement")
        try:
            reponse = httpx.get(
                f"{BASE_URL}/models",
                headers={"Authorization": f"Bearer {cle}"},
                timeout=_PROBE_TIMEOUT_S,
            )
        except httpx.HTTPError as erreur:
            return self._capacite(False, f"{BASE_URL} injoignable : {erreur}")
        if reponse.status_code in (401, 403):
            return self._capacite(False, f"clé refusée ({reponse.status_code})")
        if reponse.status_code >= 400:
            return self._capacite(False, f"catalogue illisible ({reponse.status_code})")

        catalogue = [
            entree.get("id", "") for entree in (reponse.json() or {}).get("data", [])
        ]
        if self.model not in catalogue:
            return self._capacite(
                False,
                f"modèle {self.model!r} absent du catalogue Groq — il a peut-être "
                f"été retiré ; {len(catalogue)} modèles disponibles, en choisir un "
                f"avec {GROQ_MODEL_ENV}",
            )
        return self._capacite(
            True, f"modèle {self.model} au catalogue ({len(catalogue)} disponibles)"
        )

    def _capacite(self, joignable: bool, detail: str) -> ProviderCapability:
        return ProviderCapability(
            provider=self.name,
            state=CapabilityState.AVAILABLE if joignable else CapabilityState.UNAVAILABLE,
            measured_at=datetime.now(UTC),
            measurement_method=f"GET {BASE_URL}/models",
            detail=detail,
            requires_network=True,
            requires_credentials=True,
        )

    # ---------------------------------------------------------- décision

    def draft_brief(self, request: TopicRequest, research: ResearchState) -> DirectorBrief:
        capacite = self.get_capabilities()
        if not capacite.usable:
            raise ReasonerUnavailable(f"{self.name} : {capacite.detail}")
        return draft_with(
            self._decide, request=request, research=research, author=self.name
        )

    def _decide(self, echanges: list[dict[str, Any]]) -> dict[str, Any]:
        schema = decision_schema()
        outil = {
            "type": "function",
            "function": {
                "name": _TOOL_NAME,
                "description": "Rend la décision de réalisation demandée.",
                "parameters": _accepte_aussi_une_chaine(schema),
            },
        }
        messages = [{"role": "system", "content": SYSTEM}, *echanges]
        entree = _jetons(messages) + _jetons(outil) + _MARGE_JETONS
        sortie = self._sortie_possible(entree)
        self._attendre_la_fenetre(entree + sortie)

        charge = {
            "model": self.model,
            "max_tokens": sortie,
            "temperature": self.temperature,
            "messages": messages,
            "tools": [outil],
            "tool_choice": {"type": "function", "function": {"name": _TOOL_NAME}},
        }
        try:
            reponse = httpx.post(
                f"{BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._cle()}",
                    "content-type": "application/json",
                },
                json=charge,
                timeout=_DECISION_TIMEOUT_S,
            )
        except httpx.HTTPError as erreur:
            raise ReasonerUnavailable(
                f"{self.name} : appel impossible ({erreur})"
            ) from erreur
        if reponse.status_code >= 400:
            raise ReasonerUnavailable(f"{self.name} : {_motif(reponse)}")

        charge_rendue = reponse.json()
        usage = charge_rendue.get("usage") or {}
        self._last_usage = {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        }
        brut = _arguments_de_l_outil(charge_rendue, self.name)
        return _rend_leur_type(brut, schema, schema.get("$defs", {}))

    # ------------------------------------------------------- le plafond

    def _sortie_possible(self, entree: int) -> int:
        """Ce qu'il reste pour écrire, une fois la question payée.

        Le plafond porte sur l'envoi **et** la sortie réservée. Réserver
        largement « au cas où » consomme donc le budget avant le premier mot :
        c'est ce qui a fait échouer le premier appel réel, à 18 813 jetons
        demandés pour 8 000 permis, dont 16 000 de sortie jamais écrite.
        """
        utilisable = int(self.tpm * _FRACTION_UTILISABLE)
        reste = utilisable - entree
        if reste < _SORTIE_MINIMALE:
            raise ReasonerUnavailable(
                f"{self.name} : le plafond de {self.tpm} jetons/minute ne laisse "
                f"que {max(reste, 0)} jetons pour écrire, il en faut au moins "
                f"{_SORTIE_MINIMALE}. Relever {GROQ_TPM_ENV} si le compte le permet."
            )
        return min(reste, _SORTIE_MAXIMALE)

    def _attendre_la_fenetre(self, demande: int) -> None:
        """Patiente si cette minute est déjà pleine, au lieu de se faire refuser.

        La reprise du contrat renvoie une seconde requête quelques secondes
        après la première : sur un plafond par minute, les deux s'additionnent.
        Attendre le tour de la fenêtre est plus honnête qu'échouer sur une
        limite qu'on savait atteindre.
        """
        maintenant = time.monotonic()
        if maintenant - self._fenetre_ouverte_a >= _FENETRE_S:
            self._fenetre_ouverte_a = maintenant
            self._consomme = 0
        elif self._consomme + demande > self.tpm:
            repos = _FENETRE_S - (maintenant - self._fenetre_ouverte_a)
            self.notes.append(
                f"plafond de {self.tpm} jetons/minute atteint après "
                f"{self._consomme} : attente de {repos:.0f}s avant la suite"
            )
            time.sleep(max(repos, 0.0))
            self._fenetre_ouverte_a = time.monotonic()
            self._consomme = 0
        self._consomme += demande


def _modele_demande() -> str:
    return os.environ.get(GROQ_MODEL_ENV, "").strip() or DEFAULT_MODEL


def _plafond_declare() -> int:
    """Le plafond déclaré par l'environnement, ou celui du palier gratuit."""
    brut = os.environ.get(GROQ_TPM_ENV, "").strip()
    if not brut.isdigit() or int(brut) <= 0:
        return DEFAULT_TPM
    return int(brut)


def _motif(reponse: httpx.Response) -> str:
    """Traduit un code HTTP en raison lisible, sans en inventer une.

    Le détail rendu par Groq dit déjà laquelle de ses limites a été
    atteinte — par minute ou par jour. On le rapporte tel quel plutôt que
    d'affirmer l'une des deux.
    """
    try:
        detail = (reponse.json().get("error") or {}).get("message", "")
    except ValueError:
        detail = reponse.text[:300]
    code = reponse.status_code
    if code == 429:
        return f"limite de débit atteinte — {detail}"
    if code in (401, 403):
        return f"clé refusée ({code}) — {detail}"
    if code == 404:
        return f"modèle {code} introuvable — {detail}"
    if code >= 500:
        return f"service indisponible ({code}) — {detail}"
    return f"code {code} — {detail}"


def _arguments_de_l_outil(charge: dict[str, Any], nom: str) -> dict[str, Any]:
    """Extrait la décision de l'appel d'outil, ou dit précisément ce qui manque."""
    choix = (charge.get("choices") or [{}])[0].get("message") or {}
    appels = choix.get("tool_calls") or []
    if not appels:
        # Un modèle qui répond en prose malgré `tool_choice` n'a pas décidé :
        # on ne va pas deviner sa pensée dans un paragraphe.
        raise ReasonerUnavailable(
            f"{nom} : aucune décision structurée rendue malgré l'outil imposé"
        )
    arguments = (appels[0].get("function") or {}).get("arguments")
    if not arguments:
        raise ReasonerUnavailable(f"{nom} : appel d'outil sans arguments")
    try:
        decision = json.loads(arguments)
    except json.JSONDecodeError as erreur:
        raise ReasonerUnavailable(
            f"{nom} : arguments d'outil illisibles ({erreur})"
        ) from erreur
    if not isinstance(decision, dict):
        raise ReasonerUnavailable(
            f"{nom} : décision de type {type(decision).__name__}"
        )
    return decision
