"""Répartition du temps et courbes perceptives — tout déterministe.

Rien ici n'est une opinion : les durées se calculent à partir d'un budget et
de poids nommés, les courbes se déduisent de la suite des fonctions
narratives. Deux exécutions sur le même brief donnent le même découpage à la
milliseconde près.

Le Temporal Director complet (phase 8, §8) mesurera ces courbes sur l'audio
réel. Ce qui est ici en est la part *décidable avant la voix* : une intention
de rythme, que la timeline mesurée viendra ensuite corriger. Elle ne prétend
pas être la vérité temporelle — la règle VOICE FIRST reste entière.
"""

from __future__ import annotations

from pdz2.contracts.common import Curve, CurvePoint
from pdz2.contracts.enums import NarrativeFunction, Pacing

__all__ = [
    "FUNCTION_WEIGHT",
    "rhythm_variety",
    "FUNCTION_INTENSITY",
    "PACING_SHOT_SECONDS",
    "allocate_durations",
    "emotional_curve",
    "information_density",
]

FUNCTION_WEIGHT: dict[NarrativeFunction, float] = {
    NarrativeFunction.HOOK: 0.8,
    NarrativeFunction.SETUP: 0.9,
    NarrativeFunction.QUESTION: 0.7,
    NarrativeFunction.MECHANISM: 1.4,
    NarrativeFunction.EVIDENCE: 1.1,
    NarrativeFunction.CONTRAST: 1.0,
    NarrativeFunction.CONSEQUENCE: 1.1,
    NarrativeFunction.PAYOFF: 1.2,
    NarrativeFunction.TRANSITION: 0.5,
    NarrativeFunction.CTA: 0.6,
}
"""Un mécanisme a besoin de temps pour être vu ; une transition n'en a pas."""

FUNCTION_INTENSITY: dict[NarrativeFunction, float] = {
    NarrativeFunction.HOOK: 0.75,
    NarrativeFunction.SETUP: 0.35,
    NarrativeFunction.QUESTION: 0.55,
    NarrativeFunction.MECHANISM: 0.50,
    NarrativeFunction.EVIDENCE: 0.60,
    NarrativeFunction.CONTRAST: 0.70,
    NarrativeFunction.CONSEQUENCE: 0.65,
    NarrativeFunction.PAYOFF: 0.95,
    NarrativeFunction.TRANSITION: 0.30,
    NarrativeFunction.CTA: 0.55,
}
"""Intensité émotionnelle visée par fonction : l'accroche happe, la mise en
place respire, la chute culmine."""

PACING_SHOT_SECONDS: dict[Pacing, tuple[float, float]] = {
    Pacing.SLOW: (4.0, 12.0),
    Pacing.MEASURED: (3.0, 9.0),
    Pacing.BRISK: (2.0, 6.5),
    Pacing.RAPID: (1.2, 4.5),
}
"""Bornes de durée d'un plan. Trop court : illisible. Trop long : décrochage."""

MAX_CLAIMS_PER_SECOND = 0.12
"""Au-delà, la densité d'information sature : environ une affirmation toutes
les huit secondes est déjà soutenu pour un format court."""


def allocate_durations(
    functions: list[NarrativeFunction],
    total_seconds: float,
    pacing: Pacing,
) -> list[float]:
    """Répartit `total_seconds` entre les plans, pondéré par leur fonction.

    Les bornes de `pacing` sont respectées, et la somme retombe exactement sur
    le budget — le reliquat d'arrondi va au plan qui a le plus de marge.
    """
    if not functions:
        raise ValueError("aucune fonction narrative à cadencer")
    if total_seconds <= 0:
        raise ValueError("budget temporel nul")

    floor, ceiling = PACING_SHOT_SECONDS[pacing]
    count = len(functions)
    if count * floor > total_seconds:
        raise ValueError(
            f"{count} plans à {floor}s minimum ne tiennent pas dans "
            f"{total_seconds}s : réduire le nombre d'affirmations ou allonger"
        )

    weights = [FUNCTION_WEIGHT[function] for function in functions]
    weight_sum = sum(weights)
    raw = [total_seconds * weight / weight_sum for weight in weights]
    clamped = [min(ceiling, max(floor, value)) for value in raw]

    # Le clampage a déplacé le total : on redistribue l'écart sur les plans
    # qui ont encore de la marge, en ordre stable.
    for _ in range(len(clamped) + 1):
        drift = total_seconds - sum(clamped)
        if abs(drift) < 1e-6:
            break
        adjustable = [
            index
            for index, value in enumerate(clamped)
            if (drift > 0 and value < ceiling) or (drift < 0 and value > floor)
        ]
        if not adjustable:
            break
        share = drift / len(adjustable)
        for index in adjustable:
            clamped[index] = min(ceiling, max(floor, clamped[index] + share))

    rounded = [round(value, 3) for value in clamped]
    residue = round(total_seconds - sum(rounded), 3)
    if abs(residue) >= 0.001:
        # Le reliquat d'arrondi va au plan qui peut l'absorber sans sortir des bornes.
        target = max(
            range(count),
            key=lambda index: (ceiling - rounded[index])
            if residue > 0
            else (rounded[index] - floor),
        )
        rounded[target] = round(rounded[target] + residue, 3)
    return rounded


def emotional_curve(
    functions: list[NarrativeFunction],
    durations: list[float],
) -> Curve:
    """Courbe émotionnelle, déduite de la suite des fonctions narratives."""
    if len(functions) != len(durations):
        raise ValueError("autant de durées que de fonctions attendues")
    total = sum(durations)
    if total <= 0:
        raise ValueError("durée totale nulle")

    points: list[CurvePoint] = []
    elapsed = 0.0
    for function, duration in zip(functions, durations, strict=True):
        middle = (elapsed + duration / 2) / total
        points.append(
            CurvePoint(t=round(middle, 6), value=FUNCTION_INTENSITY[function])
        )
        elapsed += duration

    # La courbe doit couvrir [0, 1] : on prolonge par les valeurs extrêmes.
    if points[0].t > 0.0:
        points.insert(0, CurvePoint(t=0.0, value=points[0].value))
    if points[-1].t < 1.0:
        points.append(CurvePoint(t=1.0, value=points[-1].value))
    return Curve(name="emotional", points=points)


MIN_RHYTHM_VARIETY = 0.08
"""Sous ce coefficient de variation, la cadence est perçue comme régulière."""


def rhythm_variety(durations: list[float]) -> float:
    """Coefficient de variation des durées de plan.

    Le §8 interdit la monotonie autant que la surstimulation. Quand le budget
    temporel est trop serré pour le nombre de plans, toutes les durées butent
    sur la même borne et la cadence devient métronomique — le calcul est
    juste, le résultat est mauvais. Cette mesure le rend visible au lieu de le
    laisser passer.
    """
    if len(durations) < 2:
        return 0.0
    mean = sum(durations) / len(durations)
    if mean <= 0:
        return 0.0
    variance = sum((value - mean) ** 2 for value in durations) / len(durations)
    return round(variance**0.5 / mean, 4)


def information_density(claim_count: int, total_seconds: float) -> float:
    """Densité d'information, normalisée dans [0, 1]."""
    if total_seconds <= 0:
        raise ValueError("durée totale nulle")
    rate = claim_count / total_seconds
    return round(min(1.0, rate / MAX_CLAIMS_PER_SECOND), 4)
