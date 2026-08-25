"""Script Compiler : compilation, pas nouvelle décision narrative."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from pdz2.contracts.enums import Emotion, NarrativeFunction
from pdz2.contracts.script import ScriptState
from pdz2.engines.script import (
    ScriptCompiler,
    ScriptRejected,
    estimate_duration_s,
    syllable_count,
)
from pdz2.tests.test_direction import _brief, _claim, research_pair  # noqa: F401

SCRIPT_PACKAGE = Path(__file__).resolve().parents[1] / "engines" / "script"


@pytest.fixture()
def director_state(research_pair):  # noqa: F811
    from pdz2.engines.direction import DirectorCompiler

    request, research = research_pair
    brief = _brief(
        request,
        research,
        [_claim(research, fragment).id for fragment in ("stator", "rotor porte")],
    )
    return DirectorCompiler().compile(
        request=request, research=research, brief=brief
    ).state


class TestEstimation:
    def test_syllables_are_counted_per_vowel_group(self) -> None:
        assert syllable_count("le moteur") == 3
        assert syllable_count("") == 0

    def test_a_longer_text_estimates_longer(self) -> None:
        short = estimate_duration_s("Le rotor tourne.")
        long = estimate_duration_s(
            "Le rotor tourne sous l'effet du champ magnétique créé par le stator."
        )
        assert long > short

    def test_a_slower_rate_estimates_longer(self) -> None:
        text = "Le rotor tourne sous l'effet du champ magnétique."
        assert estimate_duration_s(text, 110) > estimate_duration_s(text, 200)

    def test_punctuation_adds_breathing_room(self) -> None:
        assert estimate_duration_s("le rotor tourne puis ralentit") < estimate_duration_s(
            "le rotor tourne, puis ralentit."
        )

    def test_a_null_rate_is_refused(self) -> None:
        with pytest.raises(ValueError, match="débit"):
            estimate_duration_s("texte", 0)


class TestCompilationNotDecision:
    def test_every_line_traces_back_to_the_director_state(self, director_state) -> None:
        """Aucun mot prononcé n'apparaît au moment de la compilation."""
        outcome = ScriptCompiler().compile(director_state=director_state)
        decided = {director_state.thesis, director_state.ending_payoff}
        decided |= {plan.causal_mechanism for plan in director_state.evidence_plan}
        for line in outcome.state.lines:
            assert line.text in decided, f"texte inventé : {line.text!r}"

    def test_one_line_per_shot_intent(self, director_state) -> None:
        outcome = ScriptCompiler().compile(director_state=director_state)
        assert len(outcome.state.lines) == len(director_state.shot_intents)
        assert [line.shot_intent_order for line in outcome.state.lines] == [
            intent.order for intent in director_state.shot_intents
        ]

    def test_the_narrative_function_is_carried_over(self, director_state) -> None:
        outcome = ScriptCompiler().compile(director_state=director_state)
        assert [line.function for line in outcome.state.lines] == [
            intent.narrative_function for intent in director_state.shot_intents
        ]

    def test_energy_is_read_from_the_emotional_curve(self, director_state) -> None:
        outcome = ScriptCompiler().compile(director_state=director_state)
        payoff = outcome.state.lines[-1]
        hook = outcome.state.lines[0]
        # La courbe culmine sur la chute : l'énergie suit, sans nouvelle décision.
        assert payoff.energy > hook.energy
        assert payoff.emotion is Emotion.WONDER

    def test_the_visual_requirement_comes_from_the_shot(self, director_state) -> None:
        outcome = ScriptCompiler().compile(director_state=director_state)
        assert [line.visual_requirement for line in outcome.state.lines] == [
            intent.what_the_viewer_must_see for intent in director_state.shot_intents
        ]

    def test_the_line_descends_from_its_shot_intent(self, director_state) -> None:
        outcome = ScriptCompiler().compile(director_state=director_state)
        parents = {intent.id for intent in director_state.shot_intents}
        assert all(line.parent_id in parents for line in outcome.state.lines)
        assert outcome.state.parent_id == director_state.id

    def test_emphasis_words_exist_in_their_line(self, director_state) -> None:
        outcome = ScriptCompiler().compile(director_state=director_state)
        for line in outcome.state.lines:
            for word in line.emphasis_words:
                assert word.lower() in line.text.lower()

    def test_compilation_is_deterministic(self, director_state) -> None:
        first = ScriptCompiler().compile(director_state=director_state).state
        second = ScriptCompiler().compile(director_state=director_state).state
        assert [line.text for line in first.lines] == [line.text for line in second.lines]
        assert [line.energy for line in first.lines] == [
            line.energy for line in second.lines
        ]
        assert first.estimated_total_s == second.estimated_total_s


class TestNoLlmCall:
    def test_the_compiler_makes_no_network_or_subprocess_call(self) -> None:
        """Rule 8 : aucun appel supplémentaire pour passer du script au timing."""
        forbidden = {"httpx", "requests", "urllib", "socket", "subprocess", "http"}
        offenders: list[str] = []
        for path in sorted(SCRIPT_PACKAGE.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for name in names:
                    if name.split(".")[0] in forbidden:
                        offenders.append(f"{path.name} importe {name}")
        assert not offenders, offenders


class TestRefusals:
    def test_a_demonstrative_shot_without_a_mechanism_is_refused(
        self, director_state
    ) -> None:
        from pdz2.contracts.direction import DirectorState

        stripped = DirectorState(
            **(director_state.model_dump() | {"evidence_plan": []})
        )
        with pytest.raises(ScriptRejected, match="sans mécanisme rédigé"):
            ScriptCompiler().compile(director_state=stripped)


class TestObservability:
    def test_the_estimate_is_announced_as_an_estimate(self, director_state) -> None:
        outcome = ScriptCompiler().compile(director_state=director_state)
        joined = " ".join(outcome.notes)
        assert "ESTIMÉE" in joined
        assert "TTS mesuré" in joined

    def test_a_script_far_from_the_target_is_flagged_before_paying(
        self, director_state
    ) -> None:
        outcome = ScriptCompiler().compile(director_state=director_state)
        target = sum(i.target_duration_s for i in director_state.shot_intents)
        divergence = abs(outcome.estimated_total_s - target) / target
        if divergence >= 0.25:
            assert any("avant de payer" in note for note in outcome.notes)

    def test_the_state_is_a_valid_script_state(self, director_state) -> None:
        outcome = ScriptCompiler().compile(director_state=director_state)
        assert isinstance(outcome.state, ScriptState)
        assert outcome.state.lines[0].function is NarrativeFunction.HOOK
        assert outcome.state.lines[-1].function is NarrativeFunction.PAYOFF
