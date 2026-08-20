"""La compilation d'un plan en contrats, et l'attendu qui en découle.

── Ce que ce module ajoute aux adaptateurs ──────────────────────────────

Les adaptateurs (`pdz/adaptateurs.py`) traduisent une structure en une
autre. Ce module les **ordonne** et en tire ce qu'aucun d'eux ne peut
produire seul : l'`Attendu` du diagnostic, qui a besoin du mouvement ET de la
caméra ET du contrat perceptuel à la fois.

C'est aussi ici que la question « ce plan attend-il un mouvement de SUJET,
d'AMBIANCE ou de CAMÉRA ? » reçoit sa réponse — celle dont le graphe de
stratégies a besoin pour ne pas payer un modèle là où la parallaxe suffit.
"""

from __future__ import annotations

from dataclasses import dataclass

from pdz.contracts.camera import CameraProgram, MouvementCamera
from pdz.contracts.motion import MotionProgram
from pdz.contracts.perception import PerceptualContract
from pdz.contracts.shot import ShotSpec
from pdz.contracts.world import WorldState
from pdz.diagnostics import Attendu


@dataclass(frozen=True)
class PlanCompile:
    """Un plan et tous ses contrats — la forme que le reste du système lit."""

    spec: ShotSpec
    perception: PerceptualContract
    mouvement: MotionProgram
    camera: CameraProgram
    monde: WorldState

    @property
    def mouvement_attendu(self) -> str:
        """`"sujet"` | `"ambiance"` | `"camera"` | `""`.

        LA réponse dont le graphe de stratégies a besoin. L'ordre des tests
        n'est pas arbitraire : un plan qui demande un mouvement de sujet ET
        un pan de caméra reste avant tout un plan de sujet — c'est ce que la
        parallaxe locale ne saura pas rendre, et donc ce qui décide.
        """
        if self.mouvement.action and self.mouvement.peut_changer:
            if "subject motion" in self.mouvement.peut_changer:
                return "sujet"
            if "environmental motion" in self.mouvement.peut_changer:
                return "ambiance"
        if not self.camera.verrouillee:
            return "camera"
        return ""

    @property
    def attendu(self) -> Attendu:
        """Ce que le diagnostic devra confronter à l'observation.

        Réduit à ce qui est VÉRIFIABLE : le reste attend une sonde qui sache
        le mesurer, et le déclarer sans pouvoir l'observer produirait des
        diagnostics `INCONNU` en série.
        """
        return Attendu(
            shot_id=self.spec.id,
            sujet_doit_bouger=self.mouvement_attendu == "sujet",
            camera_doit_bouger=not self.camera.verrouillee,
            duree_s=self.spec.duree_s,
            confusions_interdites=self.perception.ne_doit_pas_etre_confondu_avec,
            importance=self.importance,
        )

    @property
    def importance(self) -> float:
        """Ce que ce plan pèse dans le récit, entre 0 et 1.

        Reprend les critères que `animation.noter()` applique déjà, dans le
        même ordre de force — le premier plan décide de tout, une relance est
        un temps fort voulu, une émotion forte se voit. Ce qui change, c'est
        que le score sert désormais aussi à choisir la STRATÉGIE et à graduer
        la sévérité d'un diagnostic, pas seulement à élire les plans à animer.
        """
        score = 0.0
        # Les trois premières secondes décident de tout, et c'est le seul
        # endroit où un mouvement réel se remarque à coup sûr.
        if self.spec.numero == 0:
            score += 0.45
        if self.spec.fonction:
            score += 0.15
        # Un plan qui porte un claim ou un événement nommé n'est pas décoratif.
        if self.spec.porte:
            score += 0.20
        if self.spec.emotion in ("colere", "surprise", "peur"):
            score += 0.20
        if self.spec.elements_obligatoires:
            score += 0.10
        return min(1.0, score)


def compiler_plan(plan, univers, monde: WorldState | None = None,
                  *, personnage=None) -> PlanCompile:
    """`PlanScript` + `Univers` → tous les contrats de ce plan.

    `monde` est l'état AVANT ce plan. Sans lui, on repart d'un monde vide :
    correct pour le premier plan, faux pour les suivants — d'où
    `compiler_plans()`, qui fait suivre l'état.
    """
    from pdz.adaptateurs import (
        camera_program,
        motion_program,
        perceptual_contract,
        shot_spec,
    )
    from pdz.production import contrat_visuel as visuel_module
    from pdz.production import motion_program as motion_legacy
    from pdz.world import appliquer, etat_initial

    spec = shot_spec(plan)
    legacy = motion_legacy.depuis_plan(plan.en_dict(), univers)

    personnage = personnage or univers.personnage(plan.personnage)
    if personnage is not None:
        visuel = visuel_module.compiler(plan, personnage, univers)
        perception = perceptual_contract(visuel, legacy, shot_id=spec.id)
    else:
        # Un personnage absent de l'univers n'est pas une raison de ne rien
        # produire : le plan existe, il a un mouvement et une caméra. Seule
        # la perception reste vide, et `est_verifiable` le dira.
        perception = PerceptualContract(id=f"perception_{spec.id}", shot_id=spec.id)

    return PlanCompile(
        spec=spec,
        perception=perception,
        mouvement=motion_program(legacy),
        camera=camera_program(legacy),
        monde=appliquer(monde or etat_initial(), spec),
    )


def compiler_plans(plans, univers, *, decor: str = "") -> tuple[PlanCompile, ...]:
    """Toute la suite, avec l'état du monde qui se propage d'un plan au suivant.

    C'est cette propagation qui rend la continuité vérifiable : sans elle,
    chaque plan repartirait d'un monde vide et aucune dérive ne serait
    détectable.
    """
    from pdz.world import etat_initial

    monde = etat_initial(decor=decor)
    compiles = []
    for plan in plans:
        compile = compiler_plan(plan, univers, monde)
        compiles.append(compile)
        monde = compile.monde
    return tuple(compiles)


# Le vocabulaire de caméra du montage local. Une valeur ici veut dire que le
# mouvement sera rendu par FFmpeg — donc GARANTI — plutôt que demandé à un
# modèle. Voir `CameraProgram.est_garantie`.
CAMERAS_LOCALES = (MouvementCamera.ZOOM_LOCAL, MouvementCamera.TRAVELLING_LOCAL)
