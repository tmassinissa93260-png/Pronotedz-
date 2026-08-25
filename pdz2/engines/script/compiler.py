"""Script Compiler : DirectorState → ScriptState.

`ScriptState` est une **compilation** de `DirectorState`, pas une seconde
décision narrative. Chaque mot prononcé remonte à quelque chose que la
réalisation a déjà tranché :

    plan d'ouverture     → la thèse
    plan démonstratif    → le mécanisme causal rédigé dans le plan de preuve
    plan de chute        → la chute

Aucun appel de modèle. Aucun texte inventé au moment de la compilation. Ce
qui est calculé l'est à partir de ce qui est déjà là :

    fonction narrative   ← intention de plan
    émotion              ← fonction narrative
    énergie              ← courbe émotionnelle du DirectorState, lue au plan
    mots à accentuer     ← termes saillants présents dans la réplique
    exigence visuelle    ← ce que le plan doit montrer
    durée estimée        ← modèle de débit, marqué estimation

Le compilateur refuse plutôt que de combler : un plan démonstratif dont
l'affirmation n'a pas de mécanisme rédigé ne peut pas produire de réplique,
et le dire vaut mieux que de réciter la citation brute d'une source.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from pdz2.contracts.direction import DirectorState
from pdz2.contracts.enums import Emotion, NarrativeFunction
from pdz2.contracts.script import ScriptLine, ScriptState
from pdz2.engines.research.text import STOP_WORDS, normalise
from pdz2.engines.script.estimation import DEFAULT_SPEECH_RATE_WPM, estimate_duration_s

__all__ = ["ScriptCompiler", "ScriptOutcome", "ScriptRejected", "FUNCTION_EMOTION"]

FUNCTION_EMOTION: dict[NarrativeFunction, Emotion] = {
    NarrativeFunction.HOOK: Emotion.CURIOUS,
    NarrativeFunction.SETUP: Emotion.NEUTRAL,
    NarrativeFunction.QUESTION: Emotion.CURIOUS,
    NarrativeFunction.MECHANISM: Emotion.SERIOUS,
    NarrativeFunction.EVIDENCE: Emotion.SERIOUS,
    NarrativeFunction.CONTRAST: Emotion.TENSE,
    NarrativeFunction.CONSEQUENCE: Emotion.WONDER,
    NarrativeFunction.PAYOFF: Emotion.WONDER,
    NarrativeFunction.TRANSITION: Emotion.NEUTRAL,
    NarrativeFunction.CTA: Emotion.WARM,
}

_WORD = re.compile(r"[^\W\d_]{4,}", re.UNICODE)


class ScriptRejected(ValueError):
    """Le DirectorState ne permet pas d'écrire un script. La raison est nommée."""


@dataclass
class ScriptOutcome:
    state: ScriptState
    notes: list[str] = field(default_factory=list)

    @property
    def estimated_total_s(self) -> float:
        """Somme des estimations. Rappel : ce n'est pas une durée officielle."""
        return round(self.state.estimated_total_s, 3)


@dataclass
class ScriptCompiler:
    speech_rate_wpm: float = DEFAULT_SPEECH_RATE_WPM
    max_emphasis_words: int = 2
    divergence_warning: float = 0.25
    """Écart relatif estimation/cible au-delà duquel on prévient, avant de payer."""

    def compile(
        self,
        *,
        director_state: DirectorState,
        language: str = "fr",
    ) -> ScriptOutcome:
        mechanisms = {
            plan.claim_id: plan.causal_mechanism
            for plan in director_state.evidence_plan
        }
        lines: list[ScriptLine] = []

        for index, intent in enumerate(
            sorted(director_state.shot_intents, key=lambda item: item.order)
        ):
            text = self._text_for(intent, mechanisms)
            energy = director_state.emotional_curve.value_at(
                self._position(director_state, intent.order)
            )
            lines.append(
                ScriptLine(
                    index=index,
                    text=text,
                    function=intent.narrative_function,
                    emotion=FUNCTION_EMOTION[intent.narrative_function],
                    energy=round(energy, 4),
                    emphasis_words=self._emphasis(text),
                    visual_requirement=intent.what_the_viewer_must_see,
                    claim_id=intent.claim_id,
                    shot_intent_order=intent.order,
                    estimated_duration_s=max(
                        0.2, estimate_duration_s(text, self.speech_rate_wpm)
                    ),
                    parent_id=intent.id,
                )
            )

        state = ScriptState(
            director_state_id=director_state.id,
            language=language,
            lines=lines,
            parent_id=director_state.id,
        )
        return ScriptOutcome(state=state, notes=self._notes(state, director_state))

    # ------------------------------------------------------------------ pièces

    @staticmethod
    def _text_for(intent, mechanisms: dict[str, str]) -> str:
        """La réplique, prise là où la réalisation l'a déjà écrite."""
        if intent.claim_id is None:
            # Ouverture et chute : le plan porte déjà la phrase décidée.
            return intent.what_the_viewer_must_understand
        mechanism = mechanisms.get(intent.claim_id)
        if not mechanism:
            raise ScriptRejected(
                f"plan {intent.order} démontre {intent.claim_id} sans mécanisme "
                "rédigé dans le plan de preuve — le script n'a rien à dire, et "
                "réciter la citation brute de la source n'est pas une narration"
            )
        return mechanism

    @staticmethod
    def _position(director_state: DirectorState, order: int) -> float:
        """Position normalisée du plan, au milieu de sa durée cible."""
        intents = sorted(director_state.shot_intents, key=lambda item: item.order)
        total = sum(intent.target_duration_s for intent in intents)
        if total <= 0:
            raise ScriptRejected("durées cibles nulles dans le DirectorState")
        elapsed = 0.0
        for intent in intents:
            if intent.order == order:
                return min(1.0, (elapsed + intent.target_duration_s / 2) / total)
            elapsed += intent.target_duration_s
        raise KeyError(order)

    def _emphasis(self, text: str) -> list[str]:
        """Mots à accentuer, choisis dans la réplique elle-même.

        Le contrat exige que chaque mot accentué figure dans le texte : on
        retourne donc la forme de surface, pas une forme normalisée.
        """
        seen: set[str] = set()
        candidates: list[tuple[int, str]] = []
        for match in _WORD.finditer(text):
            surface = match.group(0)
            flat = normalise(surface)
            if flat in STOP_WORDS or flat in seen:
                continue
            seen.add(flat)
            candidates.append((len(flat), surface))
        candidates.sort(key=lambda item: (-item[0], item[1]))
        return [surface for _, surface in candidates[: self.max_emphasis_words]]

    def _notes(self, state: ScriptState, director_state: DirectorState) -> list[str]:
        target = sum(intent.target_duration_s for intent in director_state.shot_intents)
        estimated = state.estimated_total_s
        notes = [
            f"{len(state.lines)} répliques compilées depuis "
            f"{len(director_state.shot_intents)} intentions de plan",
            f"durée ESTIMÉE {estimated:.2f}s à {self.speech_rate_wpm:g} mots/min "
            "— estimation, la durée officielle viendra du TTS mesuré",
        ]
        if target > 0:
            divergence = (estimated - target) / target
            if abs(divergence) >= self.divergence_warning:
                sense = "au-dessus" if divergence > 0 else "en dessous"
                notes.append(
                    f"l'estimation est {abs(divergence) * 100:.0f} % {sense} de la "
                    f"cible de {target:.0f}s : le script risque de ne pas tomber "
                    "juste une fois synthétisé — ajuster avant de payer la voix"
                )
        return notes
