"""Render Strategy Engine : choisir une stratégie, et dire ce qu'elle coûte.

    ROUTERS CHOOSE.

Le routeur reçoit une demande de rendu et l'ensemble des capacités réellement
mesurées. Il en tire une stratégie exécutable et, pour **chaque écart** avec
la demande, une `Degradation` nommée : le champ, le demandé, l'exécuté, la
raison. Le contrat `RenderSpecExecutable` refuse tout écart non déclaré — une
dégradation silencieuse est structurellement impossible.

Les critères du §18, dans l'ordre où ils sont appliqués :

    interdiction de la vidéo IA   → écarte les stratégies génératives
    capacité mesurée              → écarte ce qu'aucun exécutant ne sait faire
    échecs antérieurs             → écarte ce qui a déjà raté sur ce plan
    risque d'identité             → préfère ce qui tient une image de référence
    complexité de mouvement       → arbitre entre still, ken burns, 2.5D, procédural
    exigence caméra               → vérifie que le mouvement demandé est tenable
    durée et coût                 → écarte ce qui dépasse plafond ou budget

Le dernier recours est toujours `STILL` : une image fixe se rend sans
personne, ce qui rend la livraison garantie.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pdz2.contracts.capacity import CapabilityMatrix
from pdz2.contracts.motion import CameraMove, MotionPrimitive, MotionProgram
from pdz2.contracts.render import (
    AI_VIDEO_STRATEGIES,
    DETERMINISTIC_STRATEGIES,
    Degradation,
    DegradationSeverity,
    ExecutionPlan,
    ExecutionStep,
    ExecutionStepKind,
    RenderSpecExecutable,
    RenderSpecRequested,
    RenderStrategy,
)
from pdz2.contracts.visual import ImageSpec
from pdz2.providers.video import VideoCapability
from pdz2.renderers.mechanism import ANIMATED_PRIMITIVES

__all__ = [
    "RenderRouter",
    "RoutingOutcome",
    "RoutingRejected",
    "LOCAL_CAPABILITY",
    "MOTION_COMPLEXITY_ORDER",
]

LOCAL_CAPABILITY: frozenset[RenderStrategy] = DETERMINISTIC_STRATEGIES
"""Stratégies exécutables sans le moindre fournisseur. Toujours disponibles."""

MOTION_COMPLEXITY_ORDER: tuple[RenderStrategy, ...] = (
    RenderStrategy.STILL,
    RenderStrategy.KEN_BURNS,
    RenderStrategy.PARALLAX_2_5D,
    RenderStrategy.PROCEDURAL,
)
"""Stratégies locales, de la plus sobre à la plus mouvante.

L'ordre n'est pas une préférence : c'est une échelle. Le routeur y entre à la
hauteur de l'énergie de mouvement visée, puis redescend si la capacité, la
durée ou le budget l'y obligent.
"""

STRATEGY_LADDER: tuple[RenderStrategy, ...] = (
    *MOTION_COMPLEXITY_ORDER,
    RenderStrategy.HYBRID,
    RenderStrategy.CONTROLLED_I2V,
    RenderStrategy.DIRECT_I2V,
)
"""L'échelle entière, du plus sobre au plus mouvant.

Les quatre premiers barreaux s'exécutent sans personne ; les trois derniers
demandent un fournisseur. Un barreau génératif n'entre dans les stratégies
mobilisables que si un fournisseur joignable le déclare, mesuré : c'est ce qui
fait qu'en l'absence de fournisseur, l'échelle se réduit exactement à
`MOTION_COMPLEXITY_ORDER` et que le routeur se comporte comme avant.

`HYBRID` s'y trouve au-dessus du procédural et en dessous de l'I2V : il
combine une base générative et un traitement local, donc il demande un
fournisseur, mais il en demande moins qu'un plan entièrement généré.
"""

DEFAULT_TIMEOUT_S: dict[str, float] = {
    "render": 300.0,
    "observe": 120.0,
    "assemble": 600.0,
}
"""Budget d'exécution par nature d'étape, quand aucune échéance n'est posée.

Une seule autorité pour le temps, en deux étages qui ne se contredisent pas :

    deadline_s   sur RenderSpecRequested   l'INTENTION : « ce plan ne doit pas
                                           coûter plus de N secondes à produire »
    timeout_s    sur ExecutionStep         le BUDGET DÉRIVÉ, appliqué par
                                           l'aiguilleur

Le routeur est le seul à faire la dérivation, l'aiguilleur est le seul à
appliquer. Sans échéance, ces valeurs par défaut s'appliquent ; avec une
échéance, elle plafonne le budget — un budget ne peut jamais dépasser
l'intention qui le borne.
"""

_NEEDS_PROVIDER: frozenset[RenderStrategy] = AI_VIDEO_STRATEGIES | {
    RenderStrategy.HYBRID
}
"""Barreaux qu'aucune machine locale ne sait franchir seule.

`HYBRID` en fait partie : sa base est générée. Sans fournisseur, il n'entre
jamais dans les stratégies mobilisables.
"""

_GENERATIVE_ABOVE = 0.80
"""Au-delà, le mouvement dépasse ce que l'échelle locale sait porter.

Calé sur les valeurs réellement produites, pas au jugé. L'énergie visée sort
de `FUNCTION_MOTION[fonction] + PACING_MOTION_BIAS[rythme] (+ regain de
répétition)`, ce qui donne :

    plafond par fonction            MECHANISM   0.70
    rythme mesuré (documentaire)    +0.00       → 0.70  jamais génératif
    rythme soutenu                  +0.10       → 0.80  génératif
    rythme rapide                   +0.20       → 0.90  génératif
    mécanisme répété, mesuré        +0.15       → 0.85  génératif

Mesuré sur l'épisode de référence (8 plans, rythme mesuré) : énergies de 0.30
à 0.70, donc **aucun plan génératif** — ce qui est le comportement voulu, une
narration posée n'a pas besoin qu'on paie un modèle. Un seuil plus haut, lui,
n'aurait jamais pu se déclencher : 0.90 exige à la fois le mécanisme et le
rythme rapide.

Le procédural entre à 0.70 et ne coûte rien : on ne paie un fournisseur que
pour ce qu'aucune stratégie gratuite ne sait produire.
"""

_STILL_BELOW = 0.15
_KEN_BURNS_BELOW = 0.40
_PARALLAX_BELOW = 0.70

_CAMERA_BY_STRATEGY: dict[RenderStrategy, frozenset[CameraMove]] = {
    RenderStrategy.STILL: frozenset({CameraMove.LOCK}),
    RenderStrategy.KEN_BURNS: frozenset(
        {CameraMove.LOCK, CameraMove.PUSH_IN, CameraMove.PULL_OUT, CameraMove.PAN,
         CameraMove.TILT}
    ),
    RenderStrategy.PARALLAX_2_5D: frozenset(
        {CameraMove.LOCK, CameraMove.PUSH_IN, CameraMove.PULL_OUT, CameraMove.PAN,
         CameraMove.TILT, CameraMove.PARALLAX, CameraMove.TRACK}
    ),
    RenderStrategy.PROCEDURAL: frozenset(
        {CameraMove.LOCK, CameraMove.PUSH_IN, CameraMove.PULL_OUT, CameraMove.PAN,
         CameraMove.TILT, CameraMove.PARALLAX, CameraMove.TRACK, CameraMove.ORBIT}
    ),
}
"""Mouvements caméra que chaque stratégie locale sait réellement tenir.

Mesuré au sens strict : c'est ce que les renderers de la phase 7 implémentent.
Aucune ligne n'y est annoncée sans code derrière.
"""


_SUBJECT_MOTION_BY_STRATEGY: dict[RenderStrategy, frozenset[MotionPrimitive]] = {
    RenderStrategy.STILL: frozenset(),
    RenderStrategy.KEN_BURNS: frozenset(),
    RenderStrategy.PARALLAX_2_5D: frozenset(),
    RenderStrategy.PROCEDURAL: ANIMATED_PRIMITIVES,
}
"""Mouvements **du sujet** que chaque stratégie locale sait exécuter.

Trois lignes vides, et c'est la vérité : recadrer une image fixe ou faire
glisser des calques déplace la **caméra**, jamais ce qui est dans le cadre. Un
moteur ne tourne pas, un courant ne circule pas.

La ligne du procédural n'est pas écrite ici : elle **est** l'ensemble des
primitives que `pdz2.renderers.mechanism` sait réellement dessiner. Recopier
cette liste l'aurait fait diverger au premier ajout — et une table de
capacités qui ment sur ce qu'un renderer sait faire est pire qu'une absence de
table, puisqu'on s'y fie.

Cette table manquait entièrement. Le routeur enregistrait des dégradations
pour la caméra, l'identité, le fournisseur — jamais pour le mouvement du
sujet, alors que `MotionProgram.subject_motion` est déclaré source de vérité
du mouvement. Un plan exigeant « rotation du sujet démontrant le mécanisme »
recevait un panoramique, et le journal annonçait zéro dégradation.

C'est exactement la dégradation silencieuse que le cahier des charges
interdit. La table la rend visible : ce que la stratégie ne sait pas faire est
désormais déclaré, plan par plan.
"""


_UPGRADABLE_FOR_SUBJECT: frozenset[RenderStrategy] = frozenset(
    {RenderStrategy.KEN_BURNS, RenderStrategy.PARALLAX_2_5D}
)
"""Visées qu'un mouvement de sujet peut relever vers le procédural.

Les deux stratégies qui déplacent la caméra sur une image fixe, et elles
seules. `STILL` en est exclu — l'énergie garde son veto — et les stratégies
génératives aussi : les rabattre reviendrait à interdire la vidéo par IA, qui
est ce qui animerait le mieux un sujet."""


def _budget(deadline_s: float | None, nature: str) -> float:
    """Budget d'exécution d'une étape, dérivé de l'échéance quand il y en a une.

    L'échéance est l'intention ; le budget en découle et ne peut pas la
    dépasser. Sans échéance, la valeur par défaut de la nature d'étape.
    """
    defaut = DEFAULT_TIMEOUT_S[nature]
    if deadline_s is None:
        return defaut
    return round(min(defaut, deadline_s), 3)


class RoutingRejected(ValueError):
    """Aucune stratégie ne peut satisfaire cette demande, pas même un repli."""


@dataclass
class RoutingOutcome:
    executables: list[RenderSpecExecutable]
    plan: ExecutionPlan
    notes: list[str] = field(default_factory=list)

    def for_shot(self, shot_id: str) -> RenderSpecExecutable:
        for executable in self.executables:
            if executable.shot_id == shot_id:
                return executable
        raise KeyError(shot_id)

    @property
    def degradations(self) -> list[Degradation]:
        return [d for e in self.executables for d in e.degradations]


@dataclass
class RenderRouter:
    """Choisit une stratégie par plan et enregistre chaque écart."""

    video_capabilities: list[VideoCapability] = field(default_factory=list)
    capability_matrix: CapabilityMatrix | None = None
    """Instantané des capacités connues au moment du routage.

    Son identifiant est estampillé sur chaque exécutable produit : c'est ce
    qui permet de retrouver, six mois plus tard, sur quelles capacités
    mesurées ou inconnues la décision s'appuyait."""
    local_strategies: frozenset[RenderStrategy] = LOCAL_CAPABILITY
    previous_failures: dict[str, set[RenderStrategy]] = field(default_factory=dict)
    """Stratégies déjà mises en échec sur un plan. Alimenté par la réparation."""

    def route(
        self,
        *,
        episode_id: str,
        requested: list[RenderSpecRequested],
        motion_programs: list[MotionProgram],
        image_specs: list[ImageSpec],
        budget_cap_usd: float | None = None,
    ) -> RoutingOutcome:
        motions = {program.id: program for program in motion_programs}
        images = {spec.id: spec for spec in image_specs}
        par_demande = {spec.id: spec.deadline_s for spec in requested}
        executables: list[RenderSpecExecutable] = []
        releves: list[str] = []

        for spec in requested:
            motion = motions.get(spec.motion_program_id)
            if motion is None:
                raise RoutingRejected(
                    f"{spec.shot_id} : programme de mouvement introuvable"
                )
            layers = max(
                (len(images[ref].layers) for ref in spec.image_spec_ids if ref in images),
                default=1,
            )
            executables.append(self._route_one(spec, motion, layers, releves))

        plan = self._plan(
            episode_id,
            executables,
            budget_cap_usd,
            # L'échéance de la demande borne le budget de l'étape : une seule
            # chaîne d'autorité, de l'intention au temps réellement appliqué.
            deadlines={
                executable.id: par_demande.get(executable.requested_spec_id)
                for executable in executables
            },
        )
        return RoutingOutcome(
            executables=executables,
            plan=plan,
            notes=[*releves, *self._notes(executables, plan)],
        )

    # ------------------------------------------------------------------ choix

    def _route_one(
        self,
        spec: RenderSpecRequested,
        motion: MotionProgram,
        layer_count: int,
        releves: list[str] | None = None,
    ) -> RenderSpecExecutable:
        degradations: list[Degradation] = []
        available = self._available(spec, degradations)
        failed = self.previous_failures.get(spec.shot_id, set())
        usable = [s for s in available if s not in failed]
        if failed and not usable:
            degradations.append(
                Degradation(
                    field="retry_strategy",
                    requested="stratégie précédemment tentée",
                    executed=RenderStrategy.STILL.value,
                    reason=(
                        "toutes les stratégies disponibles ont déjà échoué sur ce "
                        f"plan ({sorted(s.value for s in failed)})"
                    ),
                    description="repli sur une image fixe, qui aboutit toujours",
                    severity=DegradationSeverity.NARRATIVE,
                )
            )
            usable = [RenderStrategy.STILL]

        energy = motion.perceptual_target.motion_energy
        wanted = spec.preferred_strategy or self._aim(energy, available)
        if spec.preferred_strategy is None:
            releve = self._aim_for_subject(wanted, motion)
            if releve is not wanted:
                # Ce n'est pas une dégradation — le plan reçoit PLUS que ce que
                # l'énergie seule lui donnait. Mais un choix qui ne se lit
                # nulle part est un choix qu'on ne peut pas discuter.
                if releves is not None:
                    releves.append(
                        f"{spec.shot_id} : {wanted.value} → {releve.value}, "
                        f"le sujet doit exécuter "
                        f"« {motion.subject_motion.primitive.value} »"
                    )
            wanted = releve
        wanted = self._respect_layers(wanted, layer_count, degradations)
        chosen = self._best(wanted, usable)

        if chosen is not wanted and wanted in available:
            pass  # écarté par un échec antérieur : déjà consigné
        elif chosen is not wanted:
            # Pas un écart de stratégie : la réalisation n'en demandait aucune.
            # C'est l'énergie de mouvement visée qui n'est pas atteinte.
            degradations.append(
                Degradation(
                    field="strategy" if spec.preferred_strategy is not None else "motion",
                    requested=wanted.value,
                    executed=chosen.value,
                    reason=self._why_not(wanted, spec),
                    description=(
                        f"énergie de mouvement {energy:.2f} visée, rendue par "
                        f"{chosen.value}"
                    ),
                    severity=(
                        DegradationSeverity.NARRATIVE
                        if chosen is RenderStrategy.STILL and energy >= _KEN_BURNS_BELOW
                        else DegradationSeverity.PERCEPTUAL
                    ),
                )
            )

        retenu = self._porteur(chosen)
        camera = self._camera(spec, chosen, degradations)
        self._subject_motion(motion, chosen, degradations)
        if spec.identity_lock_required and chosen in AI_VIDEO_STRATEGIES:
            degradations.append(
                Degradation(
                    field="identity_lock",
                    requested="verrou strict",
                    executed="au mieux",
                    reason="aucun fournisseur ne garantit l'identité image à image",
                    description="l'ancre est portée par l'image de départ seule",
                    severity=DegradationSeverity.PERCEPTUAL,
                )
            )

        return RenderSpecExecutable(
            requested_spec_id=spec.id,
            shot_id=spec.shot_id,
            requested=spec.echo(),
            strategy=chosen,
            execution_camera=camera,
            text_overlay=spec.text_overlay,
            duration_s=spec.duration_s,
            resolution=spec.resolution,
            fps=spec.fps,
            capability_snapshot_id=(
                self.capability_matrix.id if self.capability_matrix else None
            ),
            provider=retenu.capability.provider if retenu else None,
            model=(retenu.model or None) if retenu else None,
            degradations=degradations,
            estimated_cost_usd=self._cout_attendu(retenu, spec.duration_s),
            parent_id=spec.id,
        )

    @staticmethod
    def _tient_le_plan(
        capability: VideoCapability,
        spec: RenderSpecRequested,
        degradations: list[Degradation],
    ) -> bool:
        """Le fournisseur tient-il réellement la durée et le cadre demandés ?

        Une limite `None` n'est pas « pas de limite » : c'est une limite
        inconnue. Le §14 est clair — UNKNOWN ne devient jamais SUPPORTED sans
        preuve — donc une limite non mesurée ne sert pas à écarter le
        fournisseur, mais elle ne sert pas non plus à le retenir : seule une
        limite mesurée et dépassée l'écarte, et l'écart est déclaré.
        """
        trop = []
        if capability.max_duration_s is not None and spec.duration_s > capability.max_duration_s:
            trop.append(
                f"durée {spec.duration_s:.2f}s au-delà de "
                f"{capability.max_duration_s:.2f}s"
            )
        if capability.max_width is not None and spec.resolution.width > capability.max_width:
            trop.append(f"largeur {spec.resolution.width} au-delà de {capability.max_width}")
        if capability.max_height is not None and spec.resolution.height > capability.max_height:
            trop.append(f"hauteur {spec.resolution.height} au-delà de {capability.max_height}")
        if not trop:
            return True
        degradations.append(
            Degradation(
                field="provider_availability",
                requested=f"génération par {capability.capability.provider}",
                executed="stratégie déterministe locale",
                reason=(
                    f"{capability.capability.provider} ne tient pas ce plan : "
                    + " ; ".join(trop)
                ),
                description="le plan dépasse une limite mesurée du fournisseur",
                severity=DegradationSeverity.PERCEPTUAL,
            )
        )
        return False

    def _porteur(self, strategy: RenderStrategy) -> VideoCapability | None:
        """Le fournisseur qui exécutera cette stratégie, s'il en faut un.

        Une stratégie locale ne nomme personne : le renderer déterministe
        n'est pas un fournisseur, il n'a ni compte ni facture. Nommer un
        fournisseur là où il n'y en a pas ferait croire à une dépendance qui
        n'existe pas.
        """
        if strategy not in _NEEDS_PROVIDER:
            return None
        for capability in self.video_capabilities:
            if capability.usable and strategy in capability.strategies:
                return capability
        return None

    @staticmethod
    def _cout_attendu(retenu: VideoCapability | None, duree_s: float) -> float:
        """Coût attendu, et seulement s'il est chiffré par la capacité.

        Un fournisseur qui ne dit pas ce qu'il coûte laisse 0 ici : c'est le
        gouverneur de coût qui refusera la dépense pour `UNMEASURED_COST`.
        Inventer un chiffre à sa place serait exactement ce que le §14
        interdit.
        """
        if retenu is None or retenu.cost_per_second_usd is None:
            return 0.0
        return round(retenu.cost_per_second_usd * duree_s, 6)

    def _available(
        self, spec: RenderSpecRequested, degradations: list[Degradation]
    ) -> list[RenderStrategy]:
        """Stratégies réellement mobilisables pour cette demande."""
        available = list(self.local_strategies)
        reachable = [
            capability
            for capability in self.video_capabilities
            if capability.usable
        ]
        if spec.allow_ai_video and reachable and self.capability_matrix is None:
            # Un fournisseur qu'on ne peut pas justifier ne sera pas retenu.
            # Le contrat refuserait l'exécutable, et il aurait raison : décider
            # qu'un moteur sait faire quelque chose sans pouvoir montrer sur
            # quoi on se fondait n'est pas une décision.
            degradations.append(
                Degradation(
                    field="provider_availability",
                    requested="génération vidéo par IA",
                    executed="stratégie déterministe locale",
                    reason=(
                        "aucun instantané de capacités fourni au routeur : le "
                        "choix d'un fournisseur ne serait pas traçable"
                    ),
                    description=(
                        "le plan est rendu localement ; sonder les capacités "
                        "(`pdz2 capabilities`) rend les fournisseurs éligibles"
                    ),
                    severity=DegradationSeverity.PERCEPTUAL,
                )
            )
            reachable = []
        if spec.allow_ai_video:
            if reachable:
                for capability in reachable:
                    if not self._tient_le_plan(capability, spec, degradations):
                        continue
                    available.extend(
                        strategy
                        for strategy in capability.strategies
                        if strategy in _NEEDS_PROVIDER
                    )
            else:
                degradations.append(
                    Degradation(
                        field="provider_availability",
                        requested="génération vidéo par IA",
                        executed="stratégie déterministe locale",
                        reason=(
                            "aucun fournisseur vidéo joignable : "
                            + (
                                "aucun adaptateur actif dans cet environnement"
                                if not self.video_capabilities
                                else "tous les adaptateurs se déclarent injoignables"
                            )
                        ),
                        description=(
                            "le plan est rendu localement, sans modèle génératif"
                        ),
                        severity=DegradationSeverity.PERCEPTUAL,
                    )
                )
        if not available:
            raise RoutingRejected(
                f"{spec.shot_id} : aucune stratégie disponible, pas même un repli"
            )
        return available

    def _aim(
        self, energy: float, available: list[RenderStrategy]
    ) -> RenderStrategy:
        """Stratégie visée : l'énergie de mouvement, puis ce qu'on sait faire.

        Au-delà de `_GENERATIVE_ABOVE`, le mouvement demandé dépasse ce qu'un
        recadrage ou un décalage de calques sait rendre : c'est là, et là
        seulement, qu'un fournisseur génératif vaut son coût. S'il n'y en a
        aucun, `available` ne contient aucun barreau génératif et la visée
        redescend d'elle-même sur l'échelle locale — sans écart à déclarer,
        puisque rien de génératif n'a été demandé.
        """
        local = self._by_energy(energy)
        if energy < _GENERATIVE_ABOVE:
            return local
        generative = [s for s in STRATEGY_LADDER if s in available and s in _NEEDS_PROVIDER]
        return generative[-1] if generative else local

    @staticmethod
    def _by_energy(energy: float) -> RenderStrategy:
        """Stratégie visée par la seule énergie de mouvement."""
        if energy < _STILL_BELOW:
            return RenderStrategy.STILL
        if energy < _KEN_BURNS_BELOW:
            return RenderStrategy.KEN_BURNS
        if energy < _PARALLAX_BELOW:
            return RenderStrategy.PARALLAX_2_5D
        return RenderStrategy.PROCEDURAL

    @staticmethod
    def _aim_for_subject(
        wanted: RenderStrategy, motion: MotionProgram
    ) -> RenderStrategy:
        """Relève la visée quand le SUJET doit bouger, pas seulement la caméra.

        La visée ne dépendait que de l'énergie de mouvement. Or le §18 fonde
        le choix sur la *complexité du mouvement*, et un mouvement de sujet en
        est une : une rotation demandée pour démontrer un mécanisme n'est pas
        la même chose qu'un déplacement de caméra de même énergie.

        Un plan d'énergie moyenne recevait donc un Ken Burns — qui recadre une
        image fixe — alors que son programme exigeait « rotation du sujet
        démontrant le mécanisme ». La stratégie était choisie sans regarder ce
        qu'on lui demandait d'exécuter.

        On ne relève que d'un cran, et seulement vers le procédural : c'est la
        seule stratégie locale qui dessine dans le cadre. Si elle n'est pas
        mobilisable, le choix redescend par le chemin habituel et la
        dégradation s'inscrit.

        Deux visées sont hors de portée de ce relèvement, et la suite de tests
        l'a établi avant qu'un épisode n'en souffre :

        * **STILL** — l'énergie garde son droit de veto. Un plan voulu calme à
          0,02 doit rester calme, même si son programme nomme une rotation.
          L'énergie dit *s'il y a du mouvement*, le mouvement de sujet dit
          *lequel* ; le second ne renverse pas le premier.
        * **les stratégies génératives** — rabattre une visée I2V vers le
          procédural aurait interdit à tout jamais la vidéo générative, qui
          est précisément ce qui saurait animer un sujet le mieux.
        """
        if wanted not in _UPGRADABLE_FOR_SUBJECT:
            return wanted
        demande = motion.subject_motion.primitive
        if demande is MotionPrimitive.STATIC:
            return wanted
        if demande in _SUBJECT_MOTION_BY_STRATEGY.get(wanted, frozenset()):
            return wanted
        if demande in _SUBJECT_MOTION_BY_STRATEGY[RenderStrategy.PROCEDURAL]:
            return RenderStrategy.PROCEDURAL
        return wanted

    @staticmethod
    def _respect_layers(
        wanted: RenderStrategy,
        layer_count: int,
        degradations: list[Degradation],
    ) -> RenderStrategy:
        """Le parallaxe a besoin de calques séparés. S'il n'y en a qu'un, il
        n'a rien à décaler — et le dire vaut mieux que de retomber en silence
        sur un mouvement plus pauvre.
        """
        if wanted is not RenderStrategy.PARALLAX_2_5D or layer_count >= 2:
            return wanted
        degradations.append(
            Degradation(
                field="motion",
                requested=RenderStrategy.PARALLAX_2_5D.value,
                executed=RenderStrategy.KEN_BURNS.value,
                reason=(
                    f"un seul calque séparable dans l'image ({layer_count}) : "
                    "le parallaxe n'a aucune profondeur à décaler"
                ),
                description=(
                    "mouvement rendu par recadrage progressif au lieu du parallaxe"
                ),
                severity=DegradationSeverity.PERCEPTUAL,
            )
        )
        return RenderStrategy.KEN_BURNS

    @staticmethod
    def _best(
        wanted: RenderStrategy, usable: list[RenderStrategy]
    ) -> RenderStrategy:
        """La stratégie visée, ou la plus proche en deçà sur l'échelle."""
        if wanted in usable:
            return wanted
        scale = [s for s in STRATEGY_LADDER if s in usable]
        if not scale:
            raise RoutingRejected("aucune stratégie disponible")
        if wanted in STRATEGY_LADDER:
            index = STRATEGY_LADDER.index(wanted)
            below = [s for s in scale if STRATEGY_LADDER.index(s) <= index]
            if below:
                return below[-1]
        return scale[-1]

    @staticmethod
    def _why_not(wanted: RenderStrategy, spec: RenderSpecRequested) -> str:
        if wanted in AI_VIDEO_STRATEGIES:
            return "aucun fournisseur n'expose cette stratégie"
        return f"{wanted.value} n'est pas exécutable pour ce plan"

    @staticmethod
    def _camera(
        spec: RenderSpecRequested,
        strategy: RenderStrategy,
        degradations: list[Degradation],
    ) -> CameraMove:
        """Mouvement caméra réellement tenable par la stratégie retenue."""
        supported = _CAMERA_BY_STRATEGY.get(strategy, frozenset({CameraMove.LOCK}))
        if spec.requested_camera in supported:
            return spec.requested_camera
        fallback = (
            CameraMove.PUSH_IN
            if CameraMove.PUSH_IN in supported
            else CameraMove.LOCK
        )
        degradations.append(
            Degradation(
                field="camera",
                requested=spec.requested_camera.value,
                executed=fallback.value,
                reason=(
                    f"la stratégie {strategy.value} n'expose pas le mouvement "
                    f"{spec.requested_camera.value}"
                ),
                description=(
                    f"{spec.requested_camera.value} remplacé par une approximation "
                    f"déterministe en {fallback.value}"
                ),
                severity=DegradationSeverity.PERCEPTUAL,
            )
        )
        return fallback

    @staticmethod
    def _subject_motion(
        motion: MotionProgram,
        strategy: RenderStrategy,
        degradations: list[Degradation],
    ) -> None:
        """Le sujet bougera-t-il vraiment, ou seulement la caméra ?

        Ne change rien à l'exécution — la stratégie est déjà choisie et aucune
        approximation ne remplace un moteur qui tourne. Le rôle de ce contrôle
        est d'inscrire ce qui ne sera pas fait, pour qu'un épisode livré avec
        huit plans immobiles ne se présente plus comme irréprochable.
        """
        demande = motion.subject_motion.primitive
        if demande is MotionPrimitive.STATIC:
            return
        tenables = _SUBJECT_MOTION_BY_STRATEGY.get(strategy, frozenset())
        if demande in tenables:
            return
        degradations.append(
            Degradation(
                field="subject_motion",
                requested=demande.value,
                executed=MotionPrimitive.STATIC.value,
                reason=(
                    f"la stratégie {strategy.value} déplace la caméra, pas le "
                    f"sujet : elle n'exécute pas « {demande.value} »"
                ),
                description=(
                    f"{motion.subject_motion.description or demande.value} — "
                    "le plan montrera une image fixe parcourue par la caméra"
                ),
                severity=DegradationSeverity.PERCEPTUAL,
            )
        )

    # ------------------------------------------------------------------- plan

    @staticmethod
    def _plan(
        episode_id: str,
        executables: list[RenderSpecExecutable],
        budget_cap_usd: float | None,
        deadlines: dict[str, float | None] | None = None,
    ) -> ExecutionPlan:
        deadlines = deadlines or {}
        steps: list[ExecutionStep] = []
        for executable in executables:
            kind = (
                ExecutionStepKind.GENERATE_VIDEO
                if executable.strategy in AI_VIDEO_STRATEGIES
                else ExecutionStepKind.COMPOSE_2_5D
                if executable.strategy is RenderStrategy.PARALLAX_2_5D
                else ExecutionStepKind.RENDER_PROCEDURAL
            )
            render_id = f"render-{executable.shot_id}"
            steps.append(
                ExecutionStep(
                    step_id=render_id,
                    kind=kind,
                    spec_id=executable.id,
                    retry_budget=1,
                    timeout_s=_budget(deadlines.get(executable.id), "render"),
                    estimated_cost_usd=executable.estimated_cost_usd,
                )
            )
            steps.append(
                ExecutionStep(
                    step_id=f"observe-{executable.shot_id}",
                    kind=ExecutionStepKind.OBSERVE,
                    spec_id=executable.id,
                    depends_on=[render_id],
                    retry_budget=0,
                    timeout_s=_budget(deadlines.get(executable.id), "observe"),
                    estimated_cost_usd=0.0,
                )
            )
        steps.append(
            ExecutionStep(
                step_id="assemble",
                kind=ExecutionStepKind.ASSEMBLE,
                depends_on=[f"observe-{e.shot_id}" for e in executables],
                retry_budget=1,
                timeout_s=DEFAULT_TIMEOUT_S["assemble"],
                estimated_cost_usd=0.0,
            )
        )
        total = sum(step.estimated_cost_usd for step in steps)
        return ExecutionPlan(
            episode_id=episode_id,
            steps=steps,
            total_estimated_cost_usd=round(total, 6),
            budget_cap_usd=budget_cap_usd,
        )

    @staticmethod
    def _notes(executables, plan) -> list[str]:
        counts: dict[str, int] = {}
        for executable in executables:
            counts[executable.strategy.value] = (
                counts.get(executable.strategy.value, 0) + 1
            )
        degradations = [d for e in executables for d in e.degradations]
        narrative = [
            d for d in degradations if d.severity is DegradationSeverity.NARRATIVE
        ]
        return [
            "stratégies retenues : "
            + ", ".join(f"{name}×{count}" for name, count in sorted(counts.items())),
            f"{len(degradations)} dégradation(s) enregistrée(s), "
            f"dont {len(narrative)} narrative(s)",
            f"{len(plan.steps)} étapes d'exécution pour "
            f"{plan.total_estimated_cost_usd:.4f} USD estimés",
        ]
