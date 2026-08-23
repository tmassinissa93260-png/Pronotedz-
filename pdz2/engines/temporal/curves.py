"""Les cinq courbes du Temporal Director.

Une courbe ici n'est pas une intuition chiffrée : c'est une **formule écrite**,
avec des constantes nommées et des propriétés testables. Chacune répond à une
question précise, et sa dérivation tient en quelques lignes qu'on peut
contester.

Deux natures, à ne pas confondre :

* **Transportée** — `emotional_curve` est une *décision* du Director. Elle
  n'est pas recalculée, elle est ré-échantillonnée sur le temps mesuré.

* **Cibles dérivées** — `information`, `attention`, `motion`,
  `visual_novelty`. Elles disent ce que le rendu devra viser. Ce ne sont pas
  des mesures : l'observateur déterministe (phase 8) dira ce qui a réellement
  été obtenu, et l'écart sera un constat, pas une surprise.

Aucune de ces courbes ne décide du sujet, de la thèse, ni de ce qui est
démontré. Elles ne portent que du rythme.
"""

from __future__ import annotations

from dataclasses import dataclass

from pdz2.contracts.common import Curve, CurvePoint
from pdz2.contracts.enums import NarrativeFunction, Pacing
from pdz2.contracts.script import ScriptState
from pdz2.contracts.temporal import ShotSlot, sample_position
from pdz2.engines.research.text import syllable_count

__all__ = [
    "CurveRules",
    "SlotContext",
    "emotional_curve",
    "information_curve",
    "attention_curve",
    "motion_curve",
    "visual_novelty_curve",
    "MAX_SYLLABLES_PER_SECOND",
    "FUNCTION_MOTION",
]

MAX_SYLLABLES_PER_SECOND = 7.5
"""Débit syllabique servant de plafond de normalisation, en français parlé.

Sert de dénominateur à la courbe d'information. Le numérateur est un comptage
de syllabes du texte ; le dénominateur est une **durée mesurée** sur l'audio.
Le rapport est donc un débit réel : ralentissez la voix sans toucher au texte
et la densité baisse.

Repères mesurés sur de la narration réelle, qui servent à poser les seuils
plus bas dans ce fichier — sans eux, ce sont des chiffres tombés du ciel :

    narration documentaire courante   5,7 – 6,0 syll/s   → 0,76 – 0,80
    parole soutenue, dense            6,4 syll/s         → 0,85
    débit rapide, à la limite du lisible  7,0 syll/s     → 0,93
"""

FUNCTION_MOTION: dict[NarrativeFunction, float] = {
    NarrativeFunction.HOOK: 0.65,
    NarrativeFunction.SETUP: 0.25,
    NarrativeFunction.QUESTION: 0.35,
    NarrativeFunction.MECHANISM: 0.70,
    NarrativeFunction.EVIDENCE: 0.35,
    NarrativeFunction.CONTRAST: 0.55,
    NarrativeFunction.CONSEQUENCE: 0.50,
    NarrativeFunction.PAYOFF: 0.60,
    NarrativeFunction.TRANSITION: 0.40,
    NarrativeFunction.CTA: 0.30,
}
"""Mouvement attendu par fonction narrative.

Un mécanisme *est* un mouvement : on ne démontre pas une rotation avec une
image fixe. Une preuve chiffrée demande l'inverse — le spectateur doit lire.
"""

PACING_MOTION_BIAS: dict[Pacing, float] = {
    Pacing.SLOW: -0.15,
    Pacing.MEASURED: 0.0,
    Pacing.BRISK: 0.10,
    Pacing.RAPID: 0.20,
}


@dataclass(frozen=True)
class CurveRules:
    """Constantes des formules. Toutes nommées, toutes discutables."""

    # -- attention
    attention_start: float = 0.92
    """Attention au tout début : le spectateur vient de choisir de regarder."""

    attention_halflife_s: float = 22.0
    """Sans rien de neuf, l'attention perd la moitié de sa valeur en ce temps."""

    attention_floor: float = 0.20
    cut_lift: float = 0.22
    """Regain apporté par un changement de plan."""

    cut_lift_halflife_s: float = 4.0
    """Ce regain s'éteint vite : une coupe ne tient pas vingt secondes."""

    # -- mouvement
    repetition_motion_lift: float = 0.15
    """Deux plans d'affilée sur la même affirmation : il faut bouger davantage."""

    density_readability_penalty: float = 0.30
    """Parole dense et mouvement fort ne se lisent pas ensemble."""

    density_readability_threshold: float = 0.85
    """Densité au-delà de laquelle le mouvement nuit à la lecture.

    Posé à 0,85, soit 6,4 syllabes/seconde. Le seuil précédent, 0,65, valait
    4,9 syll/s : il se déclenchait sur une narration parfaitement normale
    (5,8 syll/s mesurées) et rabotait donc *tous* les mouvements de caméra
    sans que rien ne le signale. Un seuil qui frappe le cas courant ne mesure
    plus rien — il déguise une constante en règle."""

    # -- nouveauté visuelle
    novelty_base: float = 0.30
    same_claim_lift: float = 0.25
    same_anchors_lift: float = 0.15
    staleness_period_s: float = 12.0
    """Temps sans changement de fonction narrative au bout duquel la demande de
    nouveauté est saturée."""

    new_claim_relief: float = 0.20
    """Une affirmation neuve apporte sa nouveauté d'elle-même."""


@dataclass(frozen=True)
class SlotContext:
    """Ce qu'un créneau sait de lui-même et de son prédécesseur."""

    slot: ShotSlot
    function: NarrativeFunction
    claim_id: str | None
    anchor_ids: tuple[str, ...]
    text: str
    is_new_claim: bool
    same_claim_as_previous: bool
    same_anchors_as_previous: bool
    seconds_since_function_change: float


def _curve(name: str, contexts: list[SlotContext], total_s: float, values: list[float]) -> Curve:
    """Assemble une courbe échantillonnée au milieu de chaque créneau."""
    points: list[CurvePoint] = []
    for context, value in zip(contexts, values, strict=True):
        points.append(
            CurvePoint(
                t=sample_position(context.slot, total_s),
                value=round(_clamp(value), 6),
            )
        )
    if points[0].t > 0.0:
        points.insert(0, CurvePoint(t=0.0, value=points[0].value))
    if points[-1].t < 1.0:
        points.append(CurvePoint(t=1.0, value=points[-1].value))
    return Curve(name=name, points=points)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


# --------------------------------------------------------------- transportée


def emotional_curve(
    director_curve: Curve,
    contexts: list[SlotContext],
    total_s: float,
) -> Curve:
    """Décision du Director, ré-échantillonnée sur le temps **mesuré**.

    La courbe d'origine a été posée sur des durées cibles ; l'audio réel a une
    autre longueur. Comme elle est normalisée sur [0, 1], la lire à la position
    normalisée du créneau mesuré transporte l'intention sans la réinventer.
    """
    values = [
        director_curve.value_at(sample_position(c.slot, total_s)) for c in contexts
    ]
    return _curve("emotional", contexts, total_s, values)


# ------------------------------------------------------------------ dérivées


def information_curve(
    contexts: list[SlotContext],
    total_s: float,
    script: ScriptState,
) -> Curve:
    """Densité de parole réellement soutenue par le créneau.

        information = syllabes(texte) / durée_parole_MESURÉE / MAX_SYLLABLES_PER_SECOND

    Le numérateur vient du texte, le dénominateur de l'audio. Ralentir la voix
    sans toucher au script fait donc baisser la densité — ce qui est exactement
    ce qu'on veut dire par « densité d'information ».
    """
    values: list[float] = []
    for context in contexts:
        speech = context.slot.speech_duration_s
        if speech <= 0:
            values.append(0.0)
            continue
        # Une réplique découpée voit ses syllabes réparties sur ses parts.
        syllables = syllable_count(context.text) / max(1, context.slot.part_count)
        values.append(syllables / speech / MAX_SYLLABLES_PER_SECOND)
    return _curve("information", contexts, total_s, values)


def attention_curve(
    contexts: list[SlotContext],
    total_s: float,
    rules: CurveRules,
) -> Curve:
    """**Modèle** d'attention — une prédiction déclarée, pas une mesure.

        attention(t) = plancher
                     + (départ − plancher) · 2^(−t / demi_vie)
                     + Σ_coupes  regain · 2^(−(t − t_coupe) / demi_vie_coupe)

    Propriétés que les tests vérifient : décroît strictement sans coupe ;
    remonte à chaque coupe ; un découpage plus serré relève la moyenne.

    Ce n'est pas une mesure d'attention réelle — personne ici ne regarde le
    spectateur. C'est une hypothèse chiffrée, nommée, et remplaçable le jour où
    des données d'audience existeront.
    """
    cut_times = [context.slot.start_s for context in contexts[1:]]
    values: list[float] = []
    for context in contexts:
        t = context.slot.start_s + context.slot.duration_s / 2
        decay = 2.0 ** (-t / rules.attention_halflife_s)
        value = rules.attention_floor + (rules.attention_start - rules.attention_floor) * decay
        for cut in cut_times:
            if cut <= t:
                value += rules.cut_lift * 2.0 ** (-(t - cut) / rules.cut_lift_halflife_s)
        values.append(value)
    return _curve("attention", contexts, total_s, values)


def motion_curve(
    contexts: list[SlotContext],
    total_s: float,
    pacing: Pacing,
    information: Curve,
    rules: CurveRules,
) -> Curve:
    """Mouvement **visé** par plan.

        mouvement = FUNCTION_MOTION[fonction]
                  + biais_de_rythme
                  + regain_de_répétition   (même affirmation que le plan d'avant)
                  − pénalité_de_lisibilité (si la parole est déjà dense)

    Le dernier terme est le seul qui soustrait, et c'est le plus important :
    une parole dense sur une image qui bouge beaucoup ne se lit pas.
    """
    values: list[float] = []
    for context in contexts:
        position = sample_position(context.slot, total_s)
        value = FUNCTION_MOTION[context.function] + PACING_MOTION_BIAS[pacing]
        if context.same_claim_as_previous:
            value += rules.repetition_motion_lift
        if information.value_at(position) >= rules.density_readability_threshold:
            value -= rules.density_readability_penalty
        values.append(value)
    return _curve("motion", contexts, total_s, values)


def visual_novelty_curve(
    contexts: list[SlotContext],
    total_s: float,
    rules: CurveRules,
) -> Curve:
    """Nouveauté visuelle **exigée** par plan.

        nouveauté = base
                  + regain_même_affirmation
                  + regain_mêmes_ancres
                  + usure · min(1, temps_sans_changement / période_d_usure)
                  − détente_affirmation_neuve

    C'est une *demande*, pas un constat : plus le plan ressemble à ce qui
    précède, plus il doit se distinguer par ailleurs — cadrage, angle, échelle.
    """
    values: list[float] = []
    for context in contexts:
        value = rules.novelty_base
        if context.same_claim_as_previous:
            value += rules.same_claim_lift
        if context.same_anchors_as_previous:
            value += rules.same_anchors_lift
        staleness = min(
            1.0, context.seconds_since_function_change / rules.staleness_period_s
        )
        value += staleness * rules.same_claim_lift
        if context.is_new_claim:
            value -= rules.new_claim_relief
        values.append(value)
    return _curve("visual_novelty", contexts, total_s, values)
