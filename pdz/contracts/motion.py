"""L'intention temporelle d'un plan — ce qui change, ce qui ne change pas.

Reprend `pdz.production.motion_program.MotionProgram`, qui a raison sur
l'essentiel et qu'il ne s'agit pas de refaire : le principe image→vidéo
(l'image générée juste avant est la source de vérité), les invariants
`doit_preserver` / `peut_changer` / `interdit`, la cible perceptuelle
déterministe, et zéro appel IA.

Ce que ce contrat ajoute : la NATURE du mouvement. « L'aile se déforme » et
« l'avion se déplace » sont deux échecs très différents quand ils arrivent au
mauvais endroit, et le diagnostic ne peut pas les distinguer si le programme
ne les a jamais distingués.

La caméra, elle, part dans `pdz/contracts/camera.py` : ce sont deux
programmes, pas deux champs du même.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict

from pdz.contracts.base import Contrat


class NatureMouvement(str, Enum):
    """Ce qui bouge, et comment — la distinction que le diagnostic exige."""

    STATIQUE = "static"          # rien ne doit bouger ici
    RIGIDE = "rigid"             # déplacement sans déformation
    NON_RIGIDE = "non_rigid"     # déformation attendue (tissu, fumée, visage)
    ENVIRONNEMENT = "environment"


class Trajectoire(BaseModel):
    """Le déplacement d'une entité, en qualitatif.

    Aucune coordonnée : le dépôt a déjà établi (`geometrie.py`) qu'un modèle
    d'image ne respecte pas des coordonnées, et qu'en stocker donnerait
    l'illusion d'un contrôle inexistant. Le jour où un backend acceptera de
    vraies trajectoires, ce contrat gagnera un champ — et ce champ sera
    rempli seulement pour ce backend-là.

    Un `BaseModel` : ça n'existe qu'à l'intérieur d'un `MotionProgram`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    entite: str = ""
    depuis: str = ""            # « bottom-left », « background »…
    vers: str = ""
    nature: NatureMouvement = NatureMouvement.RIGIDE
    # « progressive », « constante », « brusque » — la forme du mouvement
    # dans le temps, pas sa vitesse chiffrée.
    courbe: str = ""


class MotionProgram(Contrat):
    """L'intention temporelle d'UN plan — jamais sa description visuelle."""

    VERSION = "1.0.0"

    shot_id: str = ""
    duree_s: float = 0.0
    action: str = ""
    environnement: str = ""
    intensite: str = ""             # faible | modere | fort
    cible_perceptuelle: str = ""
    trajectoires: tuple[Trajectoire, ...] = ()
    # Les régions qui ne doivent PAS bouger. Aujourd'hui aucun backend ne
    # sait les imposer ; le champ existe parce que le diagnostic, lui, peut
    # déjà constater qu'elles ont bougé.
    regions_statiques: tuple[str, ...] = ()
    doit_preserver: tuple[str, ...] = ()
    peut_changer: tuple[str, ...] = ()
    interdit: tuple[str, ...] = ()
    registre: str = ""
    # L'ordre d'importance des mouvements. Quand un backend n'en rend qu'un,
    # c'est celui-ci qu'il faut obtenir — et son absence est un échec, là où
    # l'absence d'un mouvement secondaire n'en est pas un.
    priorite: tuple[str, ...] = ()
