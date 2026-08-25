"""Grammaire de plan : des cibles temporelles aux spécifications visuelles.

Chaque fonction de ce module répond à une question du `ShotSpec`, et chacune
suit une règle écrite, sans exception cachée. Aucune ne décide *quoi*
démontrer : le sujet, l'affirmation et la preuve visuelle viennent du
`DirectorState` et sont recopiés tels quels. Ce qui est décidé ici est
strictement de la mise en image : cadrage, caméra, mouvement, raccord,
ponctuation sonore.
"""

from __future__ import annotations

from pdz2.contracts.common import Composition, TextOverlay, Transition, Vec3
from pdz2.contracts.enums import (
    AudioEventKind,
    CameraAngle,
    Framing,
    NarrativeFunction,
    ScreenPosition,
    TransitionKind,
)
from pdz2.contracts.motion import (
    CameraMove,
    CameraProgram,
    Easing,
    MotionDescriptor,
    MotionPrimitive,
    Trajectory,
)
from pdz2.contracts.research import ClaimKind
from pdz2.contracts.shots import AudioEvent
from pdz2.engines.research.text import quantity_match

__all__ = [
    "FUNCTION_FRAMING",
    "compose",
    "camera_for",
    "subject_motion_for",
    "environment_motion_for",
    "transition_between",
    "audio_events_for",
    "overlay_for",
    "LOCK_BELOW",
    "MIN_OVERLAY_SECONDS",
    "MAX_CAMERA_VELOCITY",
]

MIN_OVERLAY_SECONDS = 0.8
"""Durée minimale d'une incrustation, en secondes.

Un chiffre affiché un tiers de seconde n'est pas lu : il clignote. Sous ce
seuil, on n'incruste pas — mieux vaut aucune incrustation qu'une incrustation
que personne ne peut lire, et qui laisserait croire que l'information a été
donnée.
"""

LOCK_BELOW = 0.30
"""Sous cette cible de mouvement, la caméra est verrouillée.

Une caméra qui bouge « un peu » ne se lit pas comme un choix : elle se lit
comme un défaut. En dessous du seuil, on assume l'immobilité.
"""

MAX_CAMERA_VELOCITY = 0.8
"""Vitesse caméra à cible de mouvement maximale, en unités de cadre par seconde."""

FUNCTION_FRAMING: dict[NarrativeFunction, tuple[Framing, CameraAngle]] = {
    NarrativeFunction.HOOK: (Framing.WIDE, CameraAngle.LOW),
    NarrativeFunction.SETUP: (Framing.MEDIUM_WIDE, CameraAngle.EYE),
    NarrativeFunction.QUESTION: (Framing.MEDIUM, CameraAngle.EYE),
    NarrativeFunction.MECHANISM: (Framing.CUTAWAY_DIAGRAM, CameraAngle.CROSS_SECTION),
    NarrativeFunction.EVIDENCE: (Framing.CLOSE, CameraAngle.EYE),
    NarrativeFunction.CONTRAST: (Framing.MEDIUM_WIDE, CameraAngle.HIGH),
    NarrativeFunction.CONSEQUENCE: (Framing.MEDIUM, CameraAngle.EYE),
    NarrativeFunction.PAYOFF: (Framing.WIDE, CameraAngle.LOW),
    NarrativeFunction.TRANSITION: (Framing.EXTREME_WIDE, CameraAngle.EYE),
    NarrativeFunction.CTA: (Framing.MEDIUM_CLOSE, CameraAngle.EYE),
}
"""Cadrage attendu par fonction. Un mécanisme se montre en coupe, une preuve
chiffrée se lit de près, une chute a besoin d'air.
"""

_NOVELTY_POSITIONS = (
    ScreenPosition.CENTER,
    ScreenPosition.LEFT,
    ScreenPosition.RIGHT,
    ScreenPosition.UPPER_THIRD,
)
_ALTERNATING_MOVES = (CameraMove.PUSH_IN, CameraMove.PAN, CameraMove.PULL_OUT, CameraMove.TILT)


def compose(
    *,
    function: NarrativeFunction,
    novelty_target: float,
    index: int,
    density: float,
) -> Composition:
    """Cadrage d'un plan.

        cadrage, angle   ← fonction narrative
        position sujet   ← rotation déterministe quand la nouveauté est exigée
        espace négatif   ← densité visuelle de la bible (dense = moins de vide)
    """
    framing, angle = FUNCTION_FRAMING[function]
    position = ScreenPosition.CENTER
    if novelty_target >= 0.55:
        # Décaler le sujet est le moyen le moins coûteux de rompre la
        # ressemblance entre deux plans consécutifs.
        position = _NOVELTY_POSITIONS[index % len(_NOVELTY_POSITIONS)]
    return Composition(
        framing=framing,
        angle=angle,
        subject_position=position,
        headroom=0.08 if framing in {Framing.CLOSE, Framing.EXTREME_CLOSE} else 0.12,
        negative_space=round(max(0.1, 0.45 - 0.3 * density), 4),
        safe_area_pct=0.86,
    )


def camera_for(*, motion_target: float, index: int, duration_s: float) -> CameraProgram:
    """Programme caméra.

        cible < LOCK_BELOW  → caméra verrouillée, sans trajectoire
        sinon               → mouvement alterné, vitesse = cible × MAX_VELOCITY

    L'alternance est indexée sur le rang du plan : deux plans voisins n'ont
    jamais le même mouvement, et la suite reste reproductible.
    """
    if motion_target < LOCK_BELOW:
        return CameraProgram(move=CameraMove.LOCK, locked=True, focal_length_mm=40.0)

    move = _ALTERNATING_MOVES[index % len(_ALTERNATING_MOVES)]
    velocity = round(max(0.05, motion_target * MAX_CAMERA_VELOCITY), 4)
    amplitude = round(max(0.05, velocity * duration_s), 4)
    axis = Vec3(z=1.0) if move in {CameraMove.PUSH_IN, CameraMove.PULL_OUT} else Vec3(y=1.0)
    end = Vec3(
        z=amplitude if move is CameraMove.PUSH_IN else -amplitude
        if move is CameraMove.PULL_OUT
        else 0.0,
        x=amplitude if move is CameraMove.PAN else 0.0,
        y=amplitude if move is CameraMove.TILT else 0.0,
    )
    return CameraProgram(
        move=move,
        locked=False,
        position=Vec3(),
        target=end,
        focal_length_mm=40.0,
        velocity=velocity,
        acceleration=0.0,
        trajectory=Trajectory(
            primitive=MotionPrimitive.LINEAR,
            control_points=[Vec3(), end],
            amplitude=amplitude,
            easing=Easing.EASE_IN_OUT,
            axis=axis,
        ),
    )


def subject_motion_for(
    *, motion_target: float, claim_kind: ClaimKind | None
) -> MotionDescriptor:
    """Mouvement du sujet.

        cible < LOCK_BELOW           → sujet immobile
        affirmation de mécanisme     → rotation (un mécanisme se démontre en tournant)
        sinon                        → translation linéaire
    """
    if motion_target < LOCK_BELOW:
        return MotionDescriptor()
    magnitude = round(motion_target, 4)
    if claim_kind is ClaimKind.MECHANISM:
        return MotionDescriptor(
            primitive=MotionPrimitive.ROTATE,
            direction=Vec3(y=1.0),
            magnitude=magnitude,
            trajectory=Trajectory(
                primitive=MotionPrimitive.ROTATE,
                amplitude=round(120.0 * motion_target, 4),
                axis=Vec3(y=1.0),
            ),
            description="rotation du sujet démontrant le mécanisme",
        )
    return MotionDescriptor(
        primitive=MotionPrimitive.LINEAR,
        direction=Vec3(x=1.0),
        magnitude=magnitude,
        trajectory=Trajectory(
            primitive=MotionPrimitive.LINEAR,
            control_points=[Vec3(), Vec3(x=magnitude)],
            amplitude=magnitude,
            easing=Easing.EASE_IN_OUT,
        ),
        description="déplacement du sujet dans le cadre",
    )


def environment_motion_for(*, motion_target: float) -> MotionDescriptor:
    """Mouvement d'environnement : un flux discret, seulement si ça bouge déjà."""
    if motion_target < 0.55:
        return MotionDescriptor()
    magnitude = round(0.25 * motion_target, 4)
    return MotionDescriptor(
        primitive=MotionPrimitive.FLOW,
        direction=Vec3(x=1.0),
        magnitude=magnitude,
        trajectory=Trajectory(
            primitive=MotionPrimitive.FLOW,
            amplitude=magnitude,
            control_points=[Vec3(), Vec3(x=magnitude)],
        ),
        description="poussière ou particules en suspension",
    )


def transition_between(
    *,
    previous_claim: str | None,
    claim_id: str | None,
    shared_anchors: bool,
    downstream_duration_s: float,
    upstream_duration_s: float,
) -> Transition:
    """Raccord entre deux plans.

        même affirmation, ancres partagées → coupe franche (on continue)
        affirmation qui change             → fondu court (on tourne la page)
        sinon                              → coupe franche

    La durée d'un fondu est plafonnée au quart du plus court des deux plans :
    un raccord ne mange jamais le plan qu'il relie.
    """
    continues = claim_id is not None and claim_id == previous_claim and shared_anchors
    if continues:
        return Transition(kind=TransitionKind.CUT, duration_s=0.0)
    budget = 0.25 * min(downstream_duration_s, upstream_duration_s)
    duration = round(min(0.35, budget), 3)
    if duration < 0.05:
        return Transition(kind=TransitionKind.CUT, duration_s=0.0)
    return Transition(kind=TransitionKind.DISSOLVE, duration_s=duration)


def audio_events_for(
    *, function: NarrativeFunction, motion_target: float, duration_s: float
) -> list[AudioEvent]:
    """Ponctuation sonore, déduite de la fonction et du mouvement visé."""
    events: list[AudioEvent] = []
    if function is NarrativeFunction.PAYOFF:
        events.append(
            AudioEvent(
                kind=AudioEventKind.IMPACT,
                at_s=0.0,
                duration_s=round(min(0.6, duration_s), 3),
                gain_db=-6.0,
                hint="ponctuation de chute",
            )
        )
    elif function is NarrativeFunction.CONTRAST:
        events.append(
            AudioEvent(
                kind=AudioEventKind.WHOOSH,
                at_s=0.0,
                duration_s=round(min(0.4, duration_s), 3),
                gain_db=-12.0,
                hint="bascule d'opposition",
            )
        )
    if motion_target >= 0.55:
        events.append(
            AudioEvent(
                kind=AudioEventKind.AMBIENCE,
                at_s=0.0,
                duration_s=round(duration_s, 3),
                gain_db=-24.0,
                hint="lit sonore soutenant le mouvement",
            )
        )
    return events


def overlay_for(
    *,
    text: str,
    claim_kind: ClaimKind | None,
    duration_s: float,
    max_chars: int,
) -> TextOverlay | None:
    """Incrustation de texte.

    Une seule règle, volontairement étroite : **une affirmation chiffrée
    affiche son chiffre**. Un nombre entendu s'oublie, un nombre lu reste. Tout
    le reste du texte à l'écran relève d'une décision de réalisation, pas d'une
    compilation — le compilateur n'en invente donc aucune.
    """
    if claim_kind is not ClaimKind.QUANTITY:
        return None
    quantity = quantity_match(text)
    if quantity is None or len(quantity) > max_chars:
        return None
    at = round(min(0.35, duration_s * 0.15), 3)
    span = round(min(2.5, duration_s - at), 3)
    if span < MIN_OVERLAY_SECONDS:
        return None
    return TextOverlay(
        text=quantity,
        at_s=at,
        duration_s=span,
        position=ScreenPosition.LOWER_THIRD,
        emphasis=True,
    )
