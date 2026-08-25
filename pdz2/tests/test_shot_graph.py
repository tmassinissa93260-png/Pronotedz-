"""ShotGraph : compilation, propagation, et absence de décision nouvelle.

Les quatre preuves de propagation demandées, plus celle qui compte le plus :
aucune décision narrative n'apparaît en silence dans le découpage.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from pdz2.contracts.enums import NarrativeFunction, TransitionKind
from pdz2.contracts.research import ClaimKind
from pdz2.engines.shots import ShotGraphCompiler, ShotGraphRejected
from pdz2.engines.shots.grammar import FUNCTION_FRAMING, LOCK_BELOW, overlay_for
from pdz2.tests import pipeline

SHOTS_PACKAGE = Path(__file__).resolve().parents[1] / "engines" / "shots"


@pytest.fixture(scope="module")
def episode(tmp_path_factory):
    return pipeline.build_episode(tmp_path_factory.mktemp("shots"))


# ------------------------------------------------- chaque plan est complet


class TestEveryShotIsFullySpecified:
    def test_the_required_fields_are_all_populated(self, episode) -> None:
        for shot in episode.graph.shots:
            assert shot.shot_id
            assert shot.duration_s > 0
            assert shot.narrative_function
            assert shot.visual_subject
            assert shot.composition
            assert shot.camera_program_id
            assert shot.subject_motion is not None
            assert shot.environment_motion is not None
            assert shot.transition_in is not None
            assert shot.transition_out is not None
            assert shot.audio_events is not None
            assert shot.continuity_dependencies is not None
            assert shot.render_constraints is not None

    def test_a_demonstrative_shot_carries_its_claim_and_its_evidence(
        self, episode
    ) -> None:
        demonstrative = {NarrativeFunction.MECHANISM, NarrativeFunction.EVIDENCE}
        for shot in episode.graph.shots:
            if shot.narrative_function in demonstrative:
                assert shot.claim_id
                assert shot.evidence_required

    def test_every_camera_program_exists_and_is_referenced_once(self, episode) -> None:
        ids = [shot.camera_program_id for shot in episode.graph.shots]
        assert len(set(ids)) == len(ids)
        known = {program.id for program in episode.camera_programs}
        assert set(ids) <= known

    def test_each_shot_descends_from_its_shot_intent(self, episode) -> None:
        parents = {intent.id for intent in episode.director_state.shot_intents}
        assert all(shot.parent_id in parents for shot in episode.graph.shots)


# ---------------------------------------- Claim → Visual Evidence → ShotSpec


class TestTheClaimLinkIsStructural:
    def test_every_claim_of_the_causal_chain_has_a_shot(self, episode) -> None:
        for claim_id in episode.director_state.causal_chain:
            assert episode.graph.shots_for_claim(claim_id), claim_id

    def test_the_shot_carries_the_written_visual_proof_verbatim(self, episode) -> None:
        proofs = {
            plan.claim_id: plan for plan in episode.director_state.evidence_plan
        }
        for shot in episode.graph.shots:
            if shot.claim_id is None:
                continue
            proof = proofs[shot.claim_id]
            assert shot.visual_subject == proof.visual_proof
            assert shot.evidence_required == proof.evidence_required

    def test_a_claim_without_a_written_proof_is_refused(self, episode) -> None:
        from pdz2.contracts.direction import DirectorState

        stripped = DirectorState(
            **(episode.director_state.model_dump() | {"evidence_plan": []})
        )
        with pytest.raises(ShotGraphRejected, match="sans preuve visuelle"):
            ShotGraphCompiler().compile(
                director_state=stripped,
                temporal_plan=episode.temporal_plan,
                visual_bible=episode.bible,
                script=episode.script,
                research=episode.research,
                request=episode.request,
            )

    def test_the_lookup_finds_nothing_for_an_unknown_claim(self, episode) -> None:
        assert episode.graph.shots_for_claim("claim-fantome") == []


# -------------------------------------------------------------- propagation


class TestPropagation:
    """Changer une entrée doit changer ce qui en dépend, et rien d'autre."""

    def test_a_changed_director_state_changes_the_shot_graph(self, tmp_path) -> None:
        base = pipeline.build_episode(tmp_path / "a", fragments=("stator", "rotor porte"))
        other = pipeline.build_episode(
            tmp_path / "b", fragments=("stator", "convertit")
        )
        assert base.director_state.claim_ids != other.director_state.claim_ids
        assert [s.visual_subject for s in base.graph.shots] != [
            s.visual_subject for s in other.graph.shots
        ]

    def test_a_changed_pacing_changes_framing_and_motion(self, tmp_path) -> None:
        from pdz2.contracts.enums import Pacing

        base = pipeline.build_episode(tmp_path / "c")
        rapid = pipeline.build_episode(
            tmp_path / "d", brief_overrides={"pacing": Pacing.RAPID}
        )
        base_motion = [
            base.temporal_plan.targets_for(s.shot_id)["motion"] for s in base.graph.shots
        ]
        rapid_motion = [
            rapid.temporal_plan.targets_for(s.shot_id)["motion"]
            for s in rapid.graph.shots
        ]
        assert sum(rapid_motion) / len(rapid_motion) > sum(base_motion) / len(base_motion)

    def test_a_changed_voice_timeline_moves_every_shot(self, tmp_path) -> None:
        short = pipeline.build_episode(tmp_path / "e", durations=[2.0] * 4)
        long = pipeline.build_episode(tmp_path / "f", durations=[7.0] * 4)
        assert [line.text for line in short.script.lines] == [
            line.text for line in long.script.lines
        ]
        assert long.graph.total_duration_s > short.graph.total_duration_s * 2
        for quick, slow in zip(short.graph.shots, long.graph.shots, strict=True):
            assert slow.duration_s > quick.duration_s
        assert [slot.start_s for slot in short.temporal_plan.slots] != [
            slot.start_s for slot in long.temporal_plan.slots
        ]

    def test_lengthening_one_line_only_shifts_what_follows(self, tmp_path) -> None:
        base = pipeline.build_episode(tmp_path / "g", durations=[4.0, 4.0, 4.0, 4.0])
        tweaked = pipeline.build_episode(
            tmp_path / "h", durations=[4.0, 9.0, 4.0, 4.0]
        )
        assert tweaked.temporal_plan.slots[0].duration_s == pytest.approx(
            base.temporal_plan.slots[0].duration_s, abs=1e-3
        )
        assert tweaked.temporal_plan.slots[1].duration_s > (
            base.temporal_plan.slots[1].duration_s
        )
        assert tweaked.temporal_plan.slots[2].start_s > (
            base.temporal_plan.slots[2].start_s
        )

    def test_a_changed_claim_changes_the_shots_that_demonstrate_it(
        self, episode
    ) -> None:
        target = episode.graph.shots[1]
        assert target.claim_id
        claim = next(c for c in episode.research.claims if c.id == target.claim_id)
        # Une affirmation de mécanisme fait tourner le sujet ; changer sa nature
        # change le mouvement du plan qui la démontre.
        assert claim.kind is ClaimKind.MECHANISM
        assert target.subject_motion.primitive.value == "rotate"

        rewritten = [
            c.model_copy(update={"kind": ClaimKind.DEFINITION})
            if c.id == target.claim_id
            else c
            for c in episode.research.claims
        ]
        altered = episode.research.model_copy(update={"claims": rewritten})
        recompiled = ShotGraphCompiler().compile(
            director_state=episode.director_state,
            temporal_plan=episode.temporal_plan,
            visual_bible=episode.bible,
            script=episode.script,
            research=altered,
            request=episode.request,
        )
        moved = recompiled.graph.shot(target.shot_id)
        assert moved.subject_motion.primitive != target.subject_motion.primitive

    def test_a_changed_visual_bible_changes_the_visual_specification(
        self, episode
    ) -> None:
        dense = episode.bible.model_copy(update={"visual_density": 1.0})
        recompiled = ShotGraphCompiler().compile(
            director_state=episode.director_state,
            temporal_plan=episode.temporal_plan,
            visual_bible=dense,
            script=episode.script,
            research=episode.research,
            request=episode.request,
        )
        before = [s.composition.negative_space for s in episode.graph.shots]
        after = [s.composition.negative_space for s in recompiled.graph.shots]
        assert after != before
        assert all(value < 0.3 for value in after)

    def test_the_shot_graph_points_back_at_the_measured_timeline(
        self, episode
    ) -> None:
        assert episode.graph.voice_timeline_id == episode.timeline.id
        assert episode.graph.visual_bible_id == episode.bible.id
        assert episode.graph.director_state_id == episode.director_state.id


# ------------------------------------ aucune décision narrative nouvelle


class TestNoNewNarrativeDecision:
    NARRATIVE_FIELDS = ("thesis", "ending_payoff", "audience")

    def test_every_visual_subject_comes_from_the_director_state(
        self, episode
    ) -> None:
        decided = {plan.visual_proof for plan in episode.director_state.evidence_plan}
        decided |= {
            intent.what_the_viewer_must_see
            for intent in episode.director_state.shot_intents
        }
        for shot in episode.graph.shots:
            assert shot.visual_subject in decided, shot.visual_subject

    def test_every_evidence_requirement_comes_from_the_evidence_plan(
        self, episode
    ) -> None:
        decided = {
            plan.evidence_required for plan in episode.director_state.evidence_plan
        }
        for shot in episode.graph.shots:
            if shot.evidence_required is not None:
                assert shot.evidence_required in decided

    def test_every_narrative_function_comes_from_a_shot_intent(self, episode) -> None:
        decided = {
            intent.narrative_function for intent in episode.director_state.shot_intents
        }
        assert {shot.narrative_function for shot in episode.graph.shots} <= decided

    def test_every_claim_comes_from_a_shot_intent(self, episode) -> None:
        decided = {
            intent.claim_id
            for intent in episode.director_state.shot_intents
            if intent.claim_id
        }
        found = {shot.claim_id for shot in episode.graph.shots if shot.claim_id}
        assert found <= decided

    def test_every_anchor_comes_from_the_director_state(self, episode) -> None:
        known = {anchor.id for anchor in episode.director_state.continuity_anchors}
        for shot in episode.graph.shots:
            assert set(shot.continuity_dependencies) <= known

    def test_the_only_text_overlay_rule_is_the_measured_quantity(self, episode) -> None:
        """Le compilateur n'écrit pas de texte : il recopie un chiffre existant."""
        for shot in episode.graph.shots:
            if shot.text_overlay is None:
                continue
            line = next(
                line
                for line in episode.script.lines
                if line.shot_intent_order
                == next(
                    i.order
                    for i in episode.director_state.shot_intents
                    if i.id == shot.parent_id
                )
            )
            assert shot.text_overlay.text in line.text

    def test_the_compiler_makes_no_model_or_network_call(self) -> None:
        forbidden = {"httpx", "requests", "urllib", "socket", "subprocess", "http"}
        offenders: list[str] = []
        for path in sorted(SHOTS_PACKAGE.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for name in names:
                    if name.split(".")[0] in forbidden:
                        offenders.append(f"{path.name} importe {name}")
        assert not offenders, offenders

    def test_the_compiler_never_reads_a_narrative_field_to_write_one(self) -> None:
        """Thèse, chute et audience n'ont rien à faire dans la mise en image."""
        source = (SHOTS_PACKAGE / "grammar.py").read_text(encoding="utf-8")
        for field in self.NARRATIVE_FIELDS:
            assert field not in source, f"grammar.py touche à {field}"


# ------------------------------------------------------------ grammaire


class TestGrammarRules:
    def test_framing_follows_the_narrative_function(self, episode) -> None:
        for shot in episode.graph.shots:
            expected, _ = FUNCTION_FRAMING[shot.narrative_function]
            assert shot.composition.framing is expected

    def test_a_low_motion_target_locks_the_camera(self, episode) -> None:
        for shot in episode.graph.shots:
            target = episode.temporal_plan.targets_for(shot.shot_id)["motion"]
            program = next(
                p for p in episode.camera_programs if p.id == shot.camera_program_id
            )
            if target < LOCK_BELOW:
                assert program.locked
                assert program.velocity == 0.0
            else:
                assert not program.locked
                assert program.velocity > 0

    def test_consecutive_moving_cameras_differ(self, episode) -> None:
        moves = [
            next(p for p in episode.camera_programs if p.id == shot.camera_program_id).move
            for shot in episode.graph.shots
        ]
        moving = [move for move in moves if move.value != "lock"]
        for first, second in zip(moving, moving[1:], strict=False):
            assert first is not second

    def test_transitions_agree_on_both_sides_of_a_cut(self, episode) -> None:
        for upstream, downstream in zip(
            episode.graph.shots, episode.graph.shots[1:], strict=False
        ):
            if downstream.transition_in.kind is TransitionKind.CUT:
                continue
            assert upstream.transition_out.kind is downstream.transition_in.kind
            assert upstream.transition_out.duration_s == pytest.approx(
                downstream.transition_in.duration_s
            )

    def test_transitions_never_swallow_their_shot(self, episode) -> None:
        for shot in episode.graph.shots:
            total = shot.transition_in.duration_s + shot.transition_out.duration_s
            assert total <= shot.duration_s

    def test_the_episode_opens_and_closes_on_a_fade(self, episode) -> None:
        assert episode.graph.shots[0].transition_in.kind is TransitionKind.FADE_IN
        assert episode.graph.shots[-1].transition_out.kind is TransitionKind.FADE_OUT

    def test_audio_events_stay_inside_their_shot(self, episode) -> None:
        for shot in episode.graph.shots:
            for event in shot.audio_events:
                assert event.at_s + event.duration_s <= shot.duration_s + 0.05

    def test_a_quantity_claim_gets_its_figure_on_screen(self) -> None:
        overlay = overlay_for(
            text="Le rendement atteint 90 % de l'énergie restituée.",
            claim_kind=ClaimKind.QUANTITY,
            duration_s=5.0,
            max_chars=22,
        )
        assert overlay is not None
        assert "90" in overlay.text

    def test_a_non_quantity_claim_gets_no_overlay(self) -> None:
        assert (
            overlay_for(
                text="Le rotor tourne sous l'effet du champ.",
                claim_kind=ClaimKind.MECHANISM,
                duration_s=5.0,
                max_chars=22,
            )
            is None
        )

    def test_a_shot_too_short_for_an_overlay_gets_none(self) -> None:
        assert (
            overlay_for(
                text="Le rendement atteint 90 %.",
                claim_kind=ClaimKind.QUANTITY,
                duration_s=0.4,
                max_chars=22,
            )
            is None
        )


class TestRenderConstraints:
    def test_a_ban_on_ai_video_makes_the_shot_deterministic_only(
        self, episode
    ) -> None:
        request = episode.request.model_copy(update={"allow_ai_video": False})
        recompiled = ShotGraphCompiler().compile(
            director_state=episode.director_state,
            temporal_plan=episode.temporal_plan,
            visual_bible=episode.bible,
            script=episode.script,
            research=episode.research,
            request=request,
        )
        for shot in recompiled.graph.shots:
            assert shot.render_constraints.allow_ai_video is False
            assert shot.render_constraints.deterministic_only is True

    def test_anchored_shots_require_an_identity_lock(self, episode) -> None:
        for shot in episode.graph.shots:
            expected = bool(shot.continuity_dependencies)
            assert shot.render_constraints.requires_identity_lock is expected

    def test_the_budget_is_split_across_the_shots(self, episode) -> None:
        request = episode.request.model_copy(update={"budget_cap_usd": 6.0})
        recompiled = ShotGraphCompiler().compile(
            director_state=episode.director_state,
            temporal_plan=episode.temporal_plan,
            visual_bible=episode.bible,
            script=episode.script,
            research=episode.research,
            request=request,
        )
        caps = [s.render_constraints.max_cost_usd for s in recompiled.graph.shots]
        assert all(cap is not None for cap in caps)
        assert sum(caps) == pytest.approx(6.0, abs=1e-6)


class TestLineageRefusals:
    def _other(self, tmp_path):
        return pipeline.build_episode(tmp_path / "stranger")

    def test_a_temporal_plan_from_elsewhere_is_refused(self, episode, tmp_path) -> None:
        other = self._other(tmp_path)
        with pytest.raises(ShotGraphRejected, match="plan temporel"):
            ShotGraphCompiler().compile(
                director_state=episode.director_state,
                temporal_plan=other.temporal_plan,
                visual_bible=episode.bible,
                script=episode.script,
                research=episode.research,
                request=episode.request,
            )

    def test_a_bible_from_elsewhere_is_refused(self, episode, tmp_path) -> None:
        other = self._other(tmp_path / "b")
        with pytest.raises(ShotGraphRejected, match="bible visuelle"):
            ShotGraphCompiler().compile(
                director_state=episode.director_state,
                temporal_plan=episode.temporal_plan,
                visual_bible=other.bible,
                script=episode.script,
                research=episode.research,
                request=episode.request,
            )
