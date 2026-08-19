"""Les chaînes de cause à effet — et la décision de ce qu'il faut MONTRER.

`pedale_enfoncee → signal → couple → rotation → accélération` : la chaîne
entière est vraie, mais une vidéo de 45 s ne peut pas montrer cinq maillons.
Ce contrat porte les deux choses : la chaîne telle qu'elle est, et le
sous-ensemble que la mise en scène retient — parce que confondre « ce qui est
vrai » et « ce qu'on montre » produit soit des vidéos illisibles, soit des
raccourcis qui deviennent des erreurs.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from pdz.contracts.base import Contrat
from pdz.contracts.communs import Certitude


class Maillon(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    cause: str
    effet: str
    # Ce qu'on sait du LIEN, pas de ses extrémités : deux faits établis
    # peuvent être reliés par une causalité qui n'est qu'une hypothèse.
    certitude: Certitude = Certitude.INCONNU
    # Le claim (explicatif) ou l'événement (fiction) dont ce maillon dépend.
    reference: str = ""


class CausalState(Contrat):
    VERSION = "1.0.0"

    maillons: tuple[Maillon, ...] = ()
    # Les maillons que la mise en scène a décidé de MONTRER. Sous-ensemble
    # strict de `maillons` — une conséquence non montrée reste vraie.
    a_montrer: tuple[str, ...] = ()

    def par_id(self, maillon_id: str) -> Maillon | None:
        return next((m for m in self.maillons if m.id == maillon_id), None)

    @property
    def chaine_montree(self) -> tuple[Maillon, ...]:
        return tuple(m for m in self.maillons if m.id in self.a_montrer)
