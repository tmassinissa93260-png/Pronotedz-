"""Ce qu'un modèle sait faire — et à quel titre on le croit.

Le dépôt porte déjà les capacités dans `modeles.yaml` (`fait: [...]`,
`durees_s`, `sorties_structurees`). Ce qui manque, et qui est ici : le
**statut** de chaque capacité.

Aujourd'hui, `fait: [ecriture, vision]` mélange sans distinction ce que la
documentation annonce et ce qu'on a réellement constaté. Les mesures existent
pourtant — elles vivent en COMMENTAIRES : « ltx-video rend ~4,84 s qu'on lui
demande 5 ou 10 », « limite réelle : 5 images par requête ». Un commentaire
ne se requête pas, ne s'agrège pas, et ne peut pas empêcher une décision.

Deux modèles ont été retirés en 2026 (`llama-3.3-70b-versatile`,
`llama-4-maverick`) alors que leurs capacités annoncées étaient exactes
jusqu'au dernier jour. Une annonce n'a jamais rien garanti.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from pdz.contracts.base import Contrat
from pdz.contracts.communs import StatutCapacite


class Capacite(BaseModel):
    """Une capacité, sa valeur, et d'où vient ce qu'on en sait."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    nom: str
    statut: StatutCapacite = StatutCapacite.INCONNU
    # `None` quand le statut est INCONNU : `False` voudrait dire « on a
    # vérifié que non », ce qui est une tout autre information. Le système
    # ne doit jamais lire une ignorance comme un refus.
    valeur: bool | None = None
    # Quand la mesure a été faite (ISO). Vide pour une annonce — une
    # documentation n'a pas de date de mesure, par définition.
    mesure_le: str = ""
    # Comment on l'a mesurée : la trace qui permet de refaire le test.
    methode: str = ""
    note: str = ""

    @property
    def utilisable(self) -> bool:
        """Peut-on s'appuyer dessus pour ENGAGER une dépense ?

        Seule une capacité MESURÉE et vraie engage. Une annonce sert à
        ordonner des candidats, jamais à promettre un résultat — c'est la
        différence entre « essayons celui-ci d'abord » et « celui-ci le fait ».
        """
        return self.statut.est_garanti and self.valeur is True


class ModeleCapacites(Contrat):
    """Le profil de capacités d'UN modèle."""

    VERSION = "1.0.0"

    modele: str = ""
    fournisseur: str = ""
    capacites: tuple[Capacite, ...] = ()
    # Les durées de clip réellement livrées, en secondes croissantes. Repris
    # de `Modele.durees_s` : c'est déjà une capacité MESURÉE dans le dépôt,
    # documentée comme telle en commentaire.
    durees_s: tuple[int, ...] = ()

    def capacite(self, nom: str) -> Capacite:
        """Toujours une `Capacite`, jamais `None`.

        Une capacité absente du profil est INCONNUE, et le dire explicitement
        évite le `if capacite(...)` qui traite l'absence comme un refus.
        """
        trouvee = next((c for c in self.capacites if c.nom == nom), None)
        return trouvee or Capacite(nom=nom, statut=StatutCapacite.INCONNU)

    def sait_faire(self, nom: str) -> bool:
        """Vrai UNIQUEMENT sur une capacité mesurée. Voir `Capacite.utilisable`."""
        return self.capacite(nom).utilisable


class CapabilityGraph(Contrat):
    """Tous les modèles connus, et ce qu'on sait de chacun."""

    VERSION = "1.0.0"

    modeles: tuple[ModeleCapacites, ...] = Field(default_factory=tuple)

    def par_modele(self, modele: str) -> ModeleCapacites | None:
        return next((m for m in self.modeles if m.modele == modele), None)

    def candidats(self, capacite: str) -> tuple[ModeleCapacites, ...]:
        """Les modèles utilisables pour cette capacité, MESURÉS d'abord.

        Les annoncés viennent ensuite : ils restent des candidats — c'est
        ainsi qu'une capacité passe un jour d'ANNONCE à MESURE — mais jamais
        avant ce qui est prouvé.
        """
        mesures = [m for m in self.modeles if m.sait_faire(capacite)]
        annonces = [m for m in self.modeles
                    if not m.sait_faire(capacite)
                    and m.capacite(capacite).statut is StatutCapacite.ANNONCE
                    and m.capacite(capacite).valeur is True]
        return tuple(mesures + annonces)

    @property
    def inconnues(self) -> tuple[tuple[str, str], ...]:
        """(modèle, capacité) dont on ne sait rien — la liste des mesures à faire."""
        return tuple(
            (m.modele, c.nom)
            for m in self.modeles for c in m.capacites
            if c.statut is StatutCapacite.INCONNU
        )
