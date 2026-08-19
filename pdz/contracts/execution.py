"""Le plan d'exécution : un DAG, même quand il n'a qu'un nœud.

Un plan simple reste un seul nœud — le forcer à ressembler à un graphe
complexe n'apporterait rien. Mais un plan en 2.5D a besoin d'une image, puis
d'une carte de profondeur, puis d'un rendu de caméra, et ces dépendances
existent qu'on les écrive ou non. Les écrire permet de les paralléliser, de
les reprendre une par une et de les mettre en cache séparément.

`cle_cache` reprend le mécanisme du dépôt (`moteur/pipeline.py::empreinte()`),
descendu au NŒUD plutôt qu'à l'étape : reprendre une production ne doit pas
refaire une carte de profondeur parce que le rendu vidéo qui la suivait a
échoué.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from pdz.contracts.base import Contrat


class StatutNoeud(str, Enum):
    EN_ATTENTE = "pending"
    EN_COURS = "running"
    TERMINE = "done"
    ECHOUE = "failed"
    # Servi par le cache : distinct de TERMINE, pour que le coût évité soit
    # mesurable plutôt que noyé dans les succès.
    REUTILISE = "cached"
    IGNORE = "skipped"


class NoeudExecution(BaseModel):
    """Une opération du DAG. `BaseModel` : ne vit qu'au sein d'un plan."""

    model_config = ConfigDict(extra="forbid")

    noeud_id: str = ""
    operation: str = ""          # « image », « profondeur », « masque », « video »…
    depend_de: tuple[str, ...] = ()
    entrees: dict[str, str] = Field(default_factory=dict)
    sortie: str = ""
    statut: StatutNoeud = StatutNoeud.EN_ATTENTE
    cle_cache: str = ""
    cout_estime_eur: float = 0.0
    cout_reel_eur: float = 0.0
    duree_estimee_ms: int = 0
    duree_reelle_ms: int = 0
    tentatives_max: int = 1
    tentative: int = 0
    erreur: str = ""


class ExecutionPlan(Contrat):
    VERSION = "1.0.0"

    shot_id: str = ""
    noeuds: tuple[NoeudExecution, ...] = ()

    def par_id(self, noeud_id: str) -> NoeudExecution | None:
        return next((n for n in self.noeuds if n.noeud_id == noeud_id), None)

    @property
    def cout_estime_eur(self) -> float:
        return sum(n.cout_estime_eur for n in self.noeuds)

    @property
    def cout_reel_eur(self) -> float:
        return sum(n.cout_reel_eur for n in self.noeuds)

    def ordonnancer(self) -> tuple[tuple[str, ...], ...]:
        """Les vagues de nœuds exécutables en parallèle, dans l'ordre.

        Tri topologique par niveaux : chaque vague ne dépend que des
        précédentes, donc tout ce qui s'y trouve peut partir ensemble. Une
        dépendance circulaire lève plutôt que de boucler — un DAG qui n'en
        est pas un doit se voir tout de suite.
        """
        restants = {n.noeud_id: set(n.depend_de) for n in self.noeuds}
        connus = set(restants)
        for noeud_id, deps in restants.items():
            if (inconnues := deps - connus):
                raise ValueError(
                    f"{noeud_id} dépend de nœuds absents du plan : "
                    f"{', '.join(sorted(inconnues))}"
                )

        vagues: list[tuple[str, ...]] = []
        faits: set[str] = set()
        while restants:
            prets = tuple(sorted(n for n, d in restants.items() if d <= faits))
            if not prets:
                raise ValueError(
                    f"Dépendance circulaire entre : {', '.join(sorted(restants))}"
                )
            vagues.append(prets)
            faits.update(prets)
            for n in prets:
                del restants[n]
        return tuple(vagues)
