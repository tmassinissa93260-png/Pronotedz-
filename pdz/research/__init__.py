"""Profil EXPLICATIF : ce qu'on sait du sujet, et à quel titre on le sait.

Indépendant du LLM par construction : `RechercheBackend` est un `Protocol`,
et le module ne connaît aucun fournisseur. C'est ce qui permettra d'ajouter
un adaptateur réel en PHASE 6 sans toucher une ligne d'ici.

── La règle du module ───────────────────────────────────────────────────

**Rien ne remonte d'un cran.** Un énoncé sans source reste `HEURISTIQUE`,
quelle que soit l'assurance avec laquelle un modèle l'a formulé. Un énoncé
contredit ne devient pas vrai parce que la contradiction est minoritaire. Et
`INCONNU` ne devient jamais `FAUX` : ne pas savoir n'est pas savoir que non.

Ces règles vivent dans `_qualifier()`, à un seul endroit, et sont testées.
Le jour où un adaptateur réel arrive, il fournit des sources — il n'a pas le
droit de fournir des certitudes.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pdz.contracts.communs import Certitude
from pdz.contracts.research import Claim, ResearchState, Source

__all__ = [
    "RechercheBackend",
    "RechercheMock",
    "SansRecherche",
    "construire",
    "qualifier",
]


@runtime_checkable
class RechercheBackend(Protocol):
    """Ce qu'un moteur de recherche doit savoir faire — et rien de plus.

    Il rend des ÉNONCÉS ET LEURS SOURCES. Il ne rend jamais de certitude :
    qualifier est la responsabilité de ce module, pas du fournisseur. Un
    backend qui déciderait lui-même qu'une chose est un fait mettrait la
    règle d'honnêteté hors de portée du code qui la teste.
    """

    nom: str

    def chercher(self, sujet: str, langue: str = "fr") -> list[dict[str, Any]]:
        """`[{"enonce": str, "sources": [{"url":…}], "date": str}, …]`"""
        ...


class SansRecherche:
    """Le backend par défaut : il ne cherche rien, et le dit.

    N'est PAS un backend dégradé — c'est la réponse honnête quand aucune
    recherche n'est configurée. Il produit un `ResearchState` vide dont la
    lacune est explicite, ce qui vaut infiniment mieux qu'un graphe de
    claims inventés par un modèle de langage à qui l'on aurait demandé « ce
    que tu sais » sur un sujet.
    """

    nom = "sans_recherche"

    def chercher(self, sujet: str, langue: str = "fr") -> list[dict[str, Any]]:
        return []


class RechercheMock:
    """Backend de test : rend exactement ce qu'on lui a donné.

    Indispensable au corpus golden et aux tests d'intégration — sans lui,
    aucune vérification de la chaîne explicative ne serait ni gratuite ni
    déterministe.
    """

    nom = "mock"

    def __init__(self, resultats: list[dict[str, Any]] | None = None):
        self.resultats = resultats or []

    def chercher(self, sujet: str, langue: str = "fr") -> list[dict[str, Any]]:
        return list(self.resultats)


def qualifier(sources: list[dict[str, Any]], conflits: tuple[str, ...] = (),
              statut_temporel: str = "") -> tuple[Certitude, float]:
    """(certitude, confiance) — LA fonction qui applique la règle d'honnêteté.

    Un seul endroit, testable, plutôt qu'une décision reprise à chaque
    appelant. Les paliers, et pourquoi ils sont là :

      · aucune source          → `HEURISTIQUE`. Un énoncé non sourcé peut
        être vrai ; il n'est pas VÉRIFIÉ, et c'est ce que le statut dit.
      · une contradiction      → `HEURISTIQUE`, quoi qu'il arrive par
        ailleurs. Le système ne tranche pas un désaccord tout seul.
      · une information périmée→ `HEURISTIQUE`. Vraie en 2019 et fausse
        aujourd'hui n'est pas une erreur de source.
      · sources concordantes   → `FAIT`.

    La confiance monte avec le nombre de sources, mais **plafonne sous 1,0** :
    aucune recherche automatique ne mérite la certitude absolue, et laisser
    le nombre atteindre 1 inviterait à traiter la confiance comme le statut.
    """
    if conflits or statut_temporel == "obsolete":
        return Certitude.HEURISTIQUE, min(0.4, 0.1 * len(sources))
    if not sources:
        return Certitude.HEURISTIQUE, 0.2
    return Certitude.FAIT, min(0.5 + 0.15 * len(sources), 0.95)


def construire(sujet: str, backend: RechercheBackend | None = None,
               langue: str = "fr") -> ResearchState:
    """Interroge le backend et en fait un graphe de connaissance qualifié.

    Sans backend, le résultat est un état VIDE dont la lacune est nommée.
    C'est volontaire : le profil explicatif doit pouvoir dire « je n'ai rien
    vérifié » plutôt que de produire une vidéo affirmative sur du vide.
    """
    moteur = backend or SansRecherche()
    bruts = moteur.chercher(sujet, langue)

    if not bruts:
        return ResearchState(
            id="research_state", sujet=sujet,
            lacunes=(f"aucune recherche effectuée (backend « {moteur.nom} ») : "
                     f"rien n'est vérifié sur « {sujet} »",),
            provenance=_provenance(moteur),
        )

    claims = tuple(
        _claim(f"claim_{i:03d}", brut) for i, brut in enumerate(bruts, start=1)
    )
    return ResearchState(
        id="research_state", sujet=sujet, claims=claims,
        lacunes=_lacunes(claims),
        requetes=(sujet,),
        provenance=_provenance(moteur),
    )


def _claim(claim_id: str, brut: dict[str, Any]) -> Claim:
    sources = list(brut.get("sources") or [])
    conflits = tuple(str(c) for c in brut.get("conflits") or ())
    statut = str(brut.get("statut_temporel", ""))
    certitude, confiance = qualifier(sources, conflits, statut)

    return Claim(
        id=claim_id,
        enonce=str(brut.get("enonce", "")).strip(),
        certitude=certitude,
        confiance=confiance,
        sources=tuple(
            Source(url=str(s.get("url", "")), titre=str(s.get("titre", "")),
                   editeur=str(s.get("editeur", "")), date=str(s.get("date", "")),
                   extrait=str(s.get("extrait", "")))
            for s in sources
        ),
        conflits=conflits,
        statut_temporel=statut,
        # Le backend ne juge pas ce qui est montrable : c'est une décision
        # de mise en scène. `0.0` = « pas évalué », et le Director le verra.
        visualisabilite=float(brut.get("visualisabilite", 0.0) or 0.0),
    )


def _lacunes(claims: tuple[Claim, ...]) -> tuple[str, ...]:
    """Ce que le graphe ne garantit PAS — écrit noir sur blanc.

    Une lacune énoncée est utilisable (le Director peut décider de ne pas
    affirmer) ; une lacune silencieuse produit une vidéo assurée sur du vide.
    """
    lacunes = []
    if (sans_source := [c.id for c in claims if not c.sources]):
        lacunes.append(f"sans source : {', '.join(sans_source)}")
    if (contredits := [c.id for c in claims if c.conflits]):
        lacunes.append(f"sources contradictoires : {', '.join(contredits)}")
    if (perimes := [c.id for c in claims if c.statut_temporel == "obsolete"]):
        lacunes.append(f"information périmée : {', '.join(perimes)}")
    if not any(c.utilisable_comme_fait for c in claims):
        lacunes.append("aucun énoncé n'est affirmable sans réserve")
    return tuple(lacunes)


def _provenance(moteur: RechercheBackend):
    from pdz.contracts.base import Provenance
    return Provenance(producteur=f"research.{moteur.nom}")
