"""La caméra comme PROGRAMME séparé — pas comme un champ du mouvement.

Aujourd'hui la caméra est une valeur parmi cinq dans `MotionProgram.camera`
(`push_in_lent`, `pan_lent`, `fixe`…), et le montage porte de son côté une
seconde notion de caméra (`montage.Mouvement`, le Ken Burns) qui n'a aucun
rapport avec la première. Deux représentations du même concept, qui ne se
parlent pas.

Ce contrat les réunit. Le point qui compte : mouvement d'objet et mouvement
de caméra sont **distincts** mais partagent le même repère — c'est
exactement ce qui permet de dire `CAMERA_DOMINANT` (ça bouge, mais ce n'est
pas le sujet).

── L'honnêteté héritée de `ControleCamera.TEXTE_SEULEMENT` ──────────────

`ControleCamera` dit COMMENT la contrainte atteint le fournisseur. Avec
`TEXTE_SEULEMENT`, « caméra verrouillée » est une INTENTION exprimée en
toutes lettres dans un prompt, pas une garantie technique : l'adaptateur
fal.ai n'envoie aucun paramètre de caméra. Un désaccord en aval sera donc un
écart intention/résultat, jamais un bug de paramétrage — et le code doit le
dire plutôt que de le laisser croire.
"""

from __future__ import annotations

from enum import Enum

from pdz.contracts.base import Contrat


class ControleCamera(str, Enum):
    """Par quel canal la contrainte de caméra atteint réellement le backend."""

    # Le prompt, et rien d'autre. Seule valeur atteignable aujourd'hui.
    TEXTE_SEULEMENT = "text_only"
    # Un paramètre dédié du fournisseur. N'apparaîtra que le jour où un
    # backend l'accepte ET où on l'a MESURÉ — pas sur la foi d'une
    # documentation (voir `StatutCapacite`).
    PARAMETRIQUE = "parametric"
    # Une trajectoire imposée. Réservé aux moteurs qu'on pilote vraiment :
    # 2.5D local, procédural, 3D.
    TRAJECTOIRE = "trajectory"


class MouvementCamera(str, Enum):
    """Le vocabulaire fixe, repris tel quel de `motion_program.PHRASES_CAMERA`.

    Une table, pas une génération : c'est ce qui permet à Python de vérifier
    la variété d'un plan à l'autre sans appeler de modèle.
    """

    FIXE = "fixe"
    PUSH_IN_LENT = "push_in_lent"
    PULL_BACK_LENT = "pull_back_lent"
    PAN_LENT = "pan_lent"
    LEGER_TREMBLEMENT = "leger_tremblement"
    # Ken Burns et consorts : le montage local les rend DÉJÀ, gratuitement
    # et de façon garantie (`pdz/video/montage.py`). Les nommer ici est ce
    # qui permettra de choisir entre « demander au modèle » et « le faire
    # soi-même à coup sûr ».
    ZOOM_LOCAL = "zoom_local"
    TRAVELLING_LOCAL = "travelling_local"


class CameraProgram(Contrat):
    VERSION = "1.0.0"

    shot_id: str = ""
    mouvement: MouvementCamera = MouvementCamera.FIXE
    controle: ControleCamera = ControleCamera.TEXTE_SEULEMENT
    # Ce que la caméra suit, quand elle suit quelque chose. Vide = caméra
    # indépendante du sujet.
    cible: str = ""
    cadrage: str = ""
    # « lente », « progressive » — jamais une valeur chiffrée qu'aucun
    # backend ne saurait honorer.
    vitesse: str = ""
    intensite: str = ""

    @property
    def verrouillee(self) -> bool:
        """Aucun mouvement de caméra voulu.

        Sert au diagnostic : un `CAMERA_DOMINANT` sur un plan verrouillé est
        un échec ; sur un `pan_lent`, c'est ce qui était demandé.
        """
        return self.mouvement is MouvementCamera.FIXE

    @property
    def est_garantie(self) -> bool:
        """Le mouvement demandé est-il TENU, ou seulement demandé ?

        `TEXTE_SEULEMENT` ne garantit rien — c'est une phrase dans un prompt.
        Un contrôle par trajectoire, exécuté localement, tient.
        """
        return self.controle in (ControleCamera.PARAMETRIQUE, ControleCamera.TRAJECTOIRE)
