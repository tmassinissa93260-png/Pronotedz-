"""L'état du monde : ce qui existe, où, dans quel état — et ce qu'on en observe.

Volontairement LÉGER. Ce n'est pas un simulateur physique, et il ne doit
jamais le devenir : la seule question à laquelle ce contrat répond est
« qu'est-ce qui a changé entre le plan précédent et celui-ci, et le rendu
l'a-t-il vraiment montré ? ».

Le couple `attendu` / `observe` est ce qui distingue ce module d'une simple
fiche de décor. Un état attendu seul ne se vérifie pas ; c'est leur écart qui
produit un diagnostic.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from pdz.contracts.base import Contrat


class Position(BaseModel):
    """QUALITATIVE, jamais une coordonnée.

    Le dépôt a déjà tranché ce point (`pdz/production/geometrie.py`) : donner
    des coordonnées à un modèle d'image ne les fait pas respecter, et les
    stocker ferait croire à une précision que rien ne tient.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    zone: str = ""          # top | bottom | left | right | center
    profondeur: str = ""    # background | midground | foreground


class Etat(BaseModel):
    """L'état d'une entité à un instant, avec ce qu'on en sait."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Formulé prêt à l'emploi (« visibly pressed »), jamais un verbe brut :
    # c'est la convention que `ShotPromptWriter` suit déjà pour `relations`.
    description: str = ""
    position: Position = Field(default_factory=Position)
    # 0..1 — à quel point on croit à cet état. Un état ATTENDU est décidé
    # (confiance 1) ; un état OBSERVÉ est mesuré, et sa confiance vient de
    # la sonde qui l'a produit.
    confiance: float = 1.0


class Entite(BaseModel):
    """Quelque chose qui persiste d'un plan à l'autre et dont l'identité compte."""

    model_config = ConfigDict(extra="forbid")

    id: str
    nature: str = ""            # « personnage » | « objet » | « décor »…
    # L'identité visuelle à préserver. C'est ce que `doit_preserver` protège
    # côté mouvement, et ce qu'un `IDENTITY_DRIFT` signale quand ça lâche.
    apparence: str = ""
    materiau: str = ""
    attendu: Etat = Field(default_factory=Etat)
    # Vide tant qu'aucune observation n'a eu lieu. Vide ≠ « conforme » :
    # c'est « pas encore regardé », et les deux ne doivent jamais se
    # confondre — c'est l'erreur qui fait passer un clip statique.
    observe: Etat | None = None

    @property
    def ecart_connu(self) -> bool:
        """Vrai seulement si on a REGARDÉ et vu autre chose que prévu."""
        return self.observe is not None and self.observe.description != self.attendu.description


class Relation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str
    cible: str
    nature: str = ""            # « tient », « regarde », « est dans »…


class WorldState(Contrat):
    """Le monde tel qu'il est au moment d'un plan donné."""

    VERSION = "1.0.0"

    shot_id: str = ""
    entites: tuple[Entite, ...] = ()
    relations: tuple[Relation, ...] = ()
    decor: str = ""

    def par_id(self, entite_id: str) -> Entite | None:
        return next((e for e in self.entites if e.id == entite_id), None)

    @property
    def entites_derivees(self) -> tuple[Entite, ...]:
        """Celles dont l'observation contredit l'attente — la matière du diagnostic."""
        return tuple(e for e in self.entites if e.ecart_connu)
