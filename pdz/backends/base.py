"""Les interfaces que tout fournisseur doit respecter.

Le métier ne connaît que ces protocoles. Il ne sait pas que fal.ai, Kling,
ElevenLabs ou AudD existent — il demande une CAPACITÉ, et un registre décide
qui l'exécute.

── Pourquoi quatre méthodes et pas une ──────────────────────────────────

    capabilities()  ce que ce backend sait faire, et à quel titre on le croit
    valider()       ce qui est refusable AVANT de dépenser
    estimer()       ce que ça coûtera, avant d'engager
    executer()      la dépense elle-même

Séparer les trois premières de la quatrième est ce qui permet de refuser un
plan infaisable sans payer pour l'apprendre. Une interface réduite à
`executer()` obligerait à découvrir chez le fournisseur ce qu'on pouvait
savoir chez soi.

── Les backends n'inventent pas de certitude ────────────────────────────

`capabilities()` rend un `ModeleCapacites`, dont chaque entrée porte son
`StatutCapacite` : ANNONCE (la documentation le dit), MESURE (on l'a
constaté, à une date), INCONNU (on ne sait pas). Un backend n'a pas le droit
de déclarer MESURE ce qu'il n'a pas mesuré — c'est la règle que
`Capacite.utilisable` fait respecter, et elle ne vaut que si les backends
sont honnêtes en amont.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from pdz.contracts.capabilities import ModeleCapacites
from pdz.contracts.render import RenderSpecExecutable


class EstimationCout:
    """Ce qu'une exécution devrait coûter, et à quel point on en est sûr."""

    def __init__(self, eur: float = 0.0, latence_ms: int = 0, sur: bool = False,
                 detail: str = ""):
        self.eur = eur
        self.latence_ms = latence_ms
        # `False` quand le prix vient d'un tarif public non revérifié — les
        # prix bougent tous les 2-3 mois, et le dépôt le documente déjà en
        # tête de `modeles.yaml`. Un budget calculé sur du non-sûr reste un
        # budget, mais il ne doit pas être présenté comme une facture.
        self.sur = sur
        self.detail = detail

    def __repr__(self) -> str:  # pragma: no cover - confort de journal
        return f"EstimationCout({self.eur:.4f} €, sûr={self.sur})"


class Validation:
    """Ce qui empêche cette exécution — ou rien.

    Les problèmes sont séparés en BLOQUANTS et AVERTISSEMENTS parce qu'ils
    appellent des actions opposées : le premier interdit de dépenser, le
    second dit qu'on dépense en connaissance de cause.
    """

    def __init__(self, bloquants: tuple[str, ...] = (),
                 avertissements: tuple[str, ...] = ()):
        self.bloquants = bloquants
        self.avertissements = avertissements

    @property
    def ok(self) -> bool:
        return not self.bloquants

    def __repr__(self) -> str:  # pragma: no cover - confort de journal
        return f"Validation(ok={self.ok}, bloquants={self.bloquants})"


class ArtefactRendu:
    """Ce qu'une exécution a produit, et ce qu'elle a réellement coûté.

    `cout_eur` est le coût RÉEL, distinct de l'estimation : leur écart est
    exactement ce que `ExperienceRecord.ecart_de_cout` mesure, et un écart
    systématique invalide l'arbitrage coût/valeur bien avant le budget.
    """

    def __init__(self, fichier: Path, cout_eur: float = 0.0, latence_ms: int = 0,
                 modele: str = "", fournisseur: str = "", meta: dict | None = None):
        self.fichier = fichier
        self.cout_eur = cout_eur
        self.latence_ms = latence_ms
        self.modele = modele
        self.fournisseur = fournisseur
        self.meta = meta or {}


@runtime_checkable
class VideoBackend(Protocol):
    """Fabriquer un clip. La forme complète, parce que c'est ici que les
    stratégies viendront se brancher (PHASE 8)."""

    nom: str

    def capabilities(self, profil: str = "equilibre") -> ModeleCapacites: ...
    def valider(self, spec: RenderSpecExecutable) -> Validation: ...
    def estimer(self, spec: RenderSpecExecutable) -> EstimationCout: ...
    def executer(self, spec: RenderSpecExecutable) -> ArtefactRendu: ...


class VoixDisponible:
    """Une voix proposée par un backend de synthèse.

    Vit ICI et non chez le fournisseur, volontairement : c'est une FORME de
    donnée, pas un client HTTP. La laisser chez ElevenLabs obligeait
    `production/appariement_voix.py` à importer le fournisseur rien que pour
    annoter une variable — un couplage pour un nom de type.

    Les champs sont ceux que tous les catalogues de voix exposent :
    identifiant, nom, langue, genre, usage. Un fournisseur qui en porterait
    d'autres les met dans `extra` plutôt que d'élargir l'interface commune.
    """

    def __init__(self, id: str, nom: str = "", langue: str = "",
                 genre: str = "", usage: str = "", extra: dict | None = None):
        self.id = id
        self.nom = nom
        self.langue = langue
        self.genre = genre
        self.usage = usage
        self.extra = extra or {}

    def __repr__(self) -> str:  # pragma: no cover - confort de journal
        return f"VoixDisponible({self.nom!r}, {self.genre}, {self.usage})"


@runtime_checkable
class TTSBackend(Protocol):
    """Dire une phrase, et rendre les timings RÉELS de chaque mot.

    Volontairement pas modelé sur un `RenderSpec` : la voix n'est pas un
    rendu visuel, et l'y forcer produirait une abstraction pour elle-même.
    Ce qui compte ici est l'alignement mot à mot — la chronologie officielle
    de toute la production en dépend.
    """

    nom: str

    def capabilities(self) -> ModeleCapacites: ...
    def voix_disponibles(self) -> list[VoixDisponible]: ...
    def synthetiser(self, texte: str, sortie: Path, *, voice_id: str,
                    stabilite: float = 0.5, style: float = 0.4,
                    vitesse: float = 1.0) -> tuple[Path, list]: ...


@runtime_checkable
class ReconnaissanceAudioBackend(Protocol):
    """Identifier un morceau à partir d'un extrait.

    `None` en sortie n'est pas une erreur : c'est le résultat normal quand la
    musique n'est pas dans la base, ce qui arrive souvent avec les musiques
    libres de droits. L'appel reste facturé.
    """

    nom: str

    def capabilities(self) -> ModeleCapacites: ...
    def identifier(self, extrait: Path, *, job_id: str | None = None): ...
