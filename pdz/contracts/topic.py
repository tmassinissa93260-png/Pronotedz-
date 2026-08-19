"""Ce que l'utilisateur a demandé, sous forme structurée.

Le sujet ne part JAMAIS directement dans un prompt vidéo. Entre « comment
fonctionne un moteur électrique ? » et la première image, il y a toute la
chaîne de compilation — et cette chaîne a besoin de savoir pour qui, en
combien de temps, dans quelle langue et sous quel profil, toutes choses
qu'une phrase seule ne dit pas.
"""

from __future__ import annotations

from pydantic import Field, field_validator

from pdz.contracts.base import Contrat
from pdz.contracts.communs import Profil


class TopicRequest(Contrat):
    """L'intention de départ, normalisée."""

    VERSION = "1.0.0"

    sujet: str
    profil: Profil = Profil.FICTION
    langue: str = "fr"
    audience: str = "grand_public"
    duree_cible_s: float = 45.0
    plateformes: tuple[str, ...] = ("tiktok", "shorts")
    # L'identifiant d'univers pour une fiction, vide en explicatif. Porté
    # ici plutôt que dans un champ libre : c'est ce qui décide quelle
    # implémentation du Director sera choisie.
    univers_id: str = ""
    # La forme mesurée d'une vidéo de référence (`str_xxx`), quand la
    # production doit en épouser le rythme. Vide = aucune contrainte.
    forme_id: str = ""
    famille_de_style: str = ""
    contraintes: dict[str, str] = Field(default_factory=dict)

    @field_validator("sujet")
    @classmethod
    def _sujet_non_vide(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("un sujet vide ne compile pas : il n'y a rien à raconter")
        return v.strip()

    @field_validator("duree_cible_s")
    @classmethod
    def _duree_plausible(cls, v: float) -> float:
        # Bornes larges et assumées : en dessous de 5 s il n'y a pas de
        # narration, au-delà de 10 min ce n'est plus le format que ce
        # système sait produire. Ce n'est pas un goût, c'est le domaine
        # de validité de tout ce qui suit (découpage, rétention, budget).
        if not 5.0 <= v <= 600.0:
            raise ValueError(f"durée hors du domaine du système : {v} s (attendu 5–600)")
        return v

    @property
    def est_explicatif(self) -> bool:
        return self.profil is Profil.EXPLICATIF
