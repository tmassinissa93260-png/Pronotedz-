"""Le plan comme NŒUD, pas comme ligne d'une liste.

`pdz.production.storyboard.PlanScript` porte déjà l'essentiel : numéro,
personnage, action, émotion, décor, durée, cadrage, éléments obligatoires…
Ce contrat le reprend et ajoute les quatre choses qui manquaient pour qu'un
plan soit vraiment spécifié :

  · `but`             — POURQUOI ce plan existe (question 1)
  · `etat_avant/apres`— ce qu'il fait CHANGER (question 3)
  · `criteres_reussite`— comment on saura qu'il a marché (question 5)
  · `porte`           — le claim ou l'événement qu'il porte

Un plan qui ne peut pas répondre aux cinq questions de
docs/TARGET_ARCHITECTURE.md § 8 n'est pas suffisamment spécifié. Ce contrat
rend la question posable ; il ne la répond pas tout seul.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from pdz.contracts.base import Contrat


class Critere(BaseModel):
    """Une condition vérifiable de réussite du plan.

    `sonde` nomme QUI saura répondre (« verification_mouvement »,
    « qa_image »). Vide = personne ne sait mesurer ce critère : il restera
    `INCERTAIN`, ce qui est une information, pas un échec.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    description: str
    sonde: str = ""
    obligatoire: bool = True


class ShotSpec(Contrat):
    """Un plan, complètement spécifié."""

    VERSION = "1.0.0"

    numero: int = 0
    duree_s: float = 0.0

    # ── Question 1 : pourquoi ce plan existe ────────────────────────────
    but: str = ""
    # L'identifiant du claim (explicatif) ou de l'événement (fiction) porté.
    # Nommé `porte` et non `reference` : `Contrat.reference()` est déjà la
    # référence versionnée du contrat lui-même (« ShotSpec@1.0.0 »), et un
    # champ du même nom la masquerait — pydantic le signalait, à raison.
    porte: str = ""
    # La fonction narrative, telle que le dépôt la nomme déjà sur
    # `PlanScript.fonction` (« révèle une information », « fait monter la
    # tension ») — jamais ce que le plan montre littéralement.
    fonction: str = ""

    # ── Question 2 : ce qu'il montre ────────────────────────────────────
    sujet: str = ""
    entites_secondaires: tuple[str, ...] = ()
    decor: str = ""
    cadrage: str = ""
    disposition: str = ""
    registre_visuel: str = ""
    elements_obligatoires: tuple[str, ...] = ()
    elements_a_exclure: tuple[str, ...] = ()

    # ── Question 3 : comment il évolue ──────────────────────────────────
    etat_avant: str = ""
    evenement: str = ""
    etat_apres: str = ""

    # ── Question 5 : comment on saura ───────────────────────────────────
    criteres_reussite: tuple[Critere, ...] = ()

    # ── Continuité ──────────────────────────────────────────────────────
    ancres: tuple[str, ...] = ()
    emotion: str = ""

    @property
    def est_specifie(self) -> bool:
        """Les cinq questions ont-elles une réponse ?

        Ne juge PAS la qualité du plan — seulement qu'il est assez décrit
        pour être fabriqué et vérifié. Les questions 4 (comment le
        fabriquer) et 5 partiellement relèvent du RenderSpec et des sondes,
        pas de ce contrat : ici on vérifie ce que le Director doit fournir.
        """
        return bool(self.but and self.sujet and self.criteres_reussite
                    and (self.evenement or self.etat_apres))


class ShotGraph(Contrat):
    """Les plans ET ce qui les relie.

    Une liste ne dit pas qu'un plan de réaction dépend du plan parlant qui
    le précède, ni qu'une ancre traverse six plans. Un graphe, si — et c'est
    ce qui permettra plus tard de décomposer un plan sans perdre le fil.
    """

    VERSION = "1.0.0"

    plans: tuple[ShotSpec, ...] = ()
    # (source, cible, nature) — « continuite », « cause », « reaction ».
    aretes: tuple[tuple[str, str, str], ...] = Field(default_factory=tuple)

    def par_numero(self, numero: int) -> ShotSpec | None:
        return next((p for p in self.plans if p.numero == numero), None)

    @property
    def duree_totale_s(self) -> float:
        return sum(p.duree_s for p in self.plans)

    @property
    def non_specifies(self) -> tuple[ShotSpec, ...]:
        return tuple(p for p in self.plans if not p.est_specifie)
