"""Director Core : brief, rythme, compilation, refus."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from pdz2.contracts.direction import AnchorKind, IdentityAttribute, VisualLanguage
from pdz2.contracts.enums import NarrativeFunction, Pacing, Tone
from pdz2.contracts.research import ResearchState, TopicRequest, VerificationStatus
from pdz2.engines.direction import (
    AnchorDraft,
    BriefRejected,
    DirectorBrief,
    DirectorCompiler,
    VisualProofDraft,
    allocate_durations,
    emotional_curve,
    information_density,
    load_brief,
    save_brief,
)
from pdz2.engines.direction.ports import brief_template
from pdz2.engines.direction.rhythm import (
    MIN_RHYTHM_VARIETY,
    PACING_SHOT_SECONDS,
    rhythm_variety,
)
from pdz2.engines.research import LocalCorpusProvider, ResearchEngine
from pdz2.tests.fixtures import CORPUS

TOPIC = "Comment fonctionne une voiture électrique ?"
F = NarrativeFunction


@pytest.fixture(scope="module")
def research_pair() -> tuple[TopicRequest, ResearchState]:
    request = TopicRequest(topic=TOPIC, target_duration_s=45.0)
    state = ResearchEngine(providers=[LocalCorpusProvider(CORPUS)]).run(request).state
    return request, state


def _fresh(duration: float) -> tuple[TopicRequest, ResearchState]:
    """Nouvelle paire question/recherche : la lignée reste cohérente."""
    request = TopicRequest(topic=TOPIC, target_duration_s=duration)
    state = ResearchEngine(providers=[LocalCorpusProvider(CORPUS)]).run(request).state
    return request, state


def _claim(state: ResearchState, fragment: str):
    return next(claim for claim in state.claims if fragment in claim.text)


def _proof(claim_id: str, **overrides) -> VisualProofDraft:
    payload = {
        "claim_id": claim_id,
        "causal_mechanism": "Le courant crée un champ qui met le rotor en rotation.",
        "evidence_required": "Voir l'énergie entrer et la rotation sortir.",
        "visual_proof": "Coupe transparente : le courant circule, puis l'arbre tourne.",
        "anchor_names": ["moteur-coupe"],
    }
    return VisualProofDraft(**(payload | overrides))


def _brief(request, research, claims: list[str], **overrides) -> DirectorBrief:
    payload = {
        "topic_request_id": request.id,
        "research_state_id": research.id,
        "thesis": "Une voiture électrique convertit de l'énergie stockée en rotation.",
        "audience": "grand public curieux",
        "tone": Tone.DOCUMENTARY,
        "pacing": Pacing.MEASURED,
        "ending_payoff": "Le couple est immédiat, sans explosion à attendre.",
        "visual_language": VisualLanguage(visual_register="coupe technique transparente"),
        "anchors": [
            AnchorDraft(
                name="moteur-coupe",
                kind=AnchorKind.MACHINE,
                canonical_description="Moteur synchrone en coupe, carter bleu nuit.",
                identity=[IdentityAttribute(name="carter", value="bleu nuit mat")],
            )
        ],
        "visual_proofs": [_proof(claim_id) for claim_id in claims],
    }
    return DirectorBrief(**(payload | overrides))


# ------------------------------------------------------------------- rythme


class TestRhythm:
    def test_the_budget_is_spent_exactly(self) -> None:
        durations = allocate_durations([F.HOOK, F.MECHANISM, F.PAYOFF], 30.0, Pacing.MEASURED)
        assert sum(durations) == pytest.approx(30.0, abs=1e-6)

    def test_every_shot_stays_within_the_pacing_bounds(self) -> None:
        floor, ceiling = PACING_SHOT_SECONDS[Pacing.BRISK]
        durations = allocate_durations([F.MECHANISM] * 8, 40.0, Pacing.BRISK)
        assert all(floor - 1e-6 <= value <= ceiling + 1e-6 for value in durations)

    def test_a_mechanism_gets_more_time_than_a_transition(self) -> None:
        durations = allocate_durations([F.MECHANISM, F.TRANSITION], 20.0, Pacing.SLOW)
        assert durations[0] > durations[1]

    def test_too_many_shots_for_the_budget_is_refused(self) -> None:
        with pytest.raises(ValueError, match="ne tiennent pas"):
            allocate_durations([F.MECHANISM] * 20, 20.0, Pacing.SLOW)

    def test_allocation_is_deterministic(self) -> None:
        functions = [F.HOOK, F.MECHANISM, F.EVIDENCE, F.PAYOFF]
        assert allocate_durations(functions, 45.0, Pacing.MEASURED) == allocate_durations(
            functions, 45.0, Pacing.MEASURED
        )

    def test_the_emotional_curve_spans_the_whole_episode(self) -> None:
        functions = [F.HOOK, F.MECHANISM, F.PAYOFF]
        durations = allocate_durations(functions, 30.0, Pacing.MEASURED)
        curve = emotional_curve(functions, durations)
        assert curve.points[0].t == 0.0
        assert curve.points[-1].t == 1.0

    def test_the_curve_peaks_on_the_payoff(self) -> None:
        functions = [F.HOOK, F.SETUP, F.MECHANISM, F.PAYOFF]
        durations = allocate_durations(functions, 40.0, Pacing.MEASURED)
        curve = emotional_curve(functions, durations)
        assert curve.points[-1].value == max(point.value for point in curve.points)

    def test_a_metronomic_cadence_is_measurable(self) -> None:
        assert rhythm_variety([9.0, 9.0, 9.0]) < MIN_RHYTHM_VARIETY
        assert rhythm_variety([4.0, 9.0, 6.0]) > MIN_RHYTHM_VARIETY

    def test_information_density_saturates_at_one(self) -> None:
        assert information_density(100, 10.0) == 1.0
        assert 0.0 < information_density(3, 45.0) < 1.0


# -------------------------------------------------------------------- brief


class TestDirectorBrief:
    def test_a_vague_visual_proof_is_refused(self, research_pair) -> None:
        request, research = research_pair
        with pytest.raises(ValidationError, match="trop vague"):
            _proof(_claim(research, "convertit").id, visual_proof="le moteur")

    def test_two_proofs_for_one_claim_are_refused(self, research_pair) -> None:
        request, research = research_pair
        claim_id = _claim(research, "convertit").id
        with pytest.raises(ValidationError, match="deux preuves visuelles"):
            _brief(request, research, [claim_id, claim_id])

    def test_a_proof_citing_an_unknown_anchor_is_refused(self, research_pair) -> None:
        request, research = research_pair
        claim_id = _claim(research, "convertit").id
        with pytest.raises(ValidationError, match="ancres inconnues"):
            _brief(
                request,
                research,
                [],
                visual_proofs=[_proof(claim_id, anchor_names=["fantome"])],
            )

    def test_a_claim_cannot_be_kept_and_excluded(self, research_pair) -> None:
        request, research = research_pair
        claim_id = _claim(research, "convertit").id
        with pytest.raises(ValidationError, match="retenues et exclues"):
            _brief(request, research, [claim_id], excluded_claim_ids=[claim_id])

    def test_a_brief_round_trips_through_a_file(self, research_pair, tmp_path) -> None:
        request, research = research_pair
        brief = _brief(request, research, [_claim(research, "convertit").id])
        save_brief(brief, tmp_path / "brief.json")
        assert load_brief(tmp_path / "brief.json") == brief

    def test_help_keys_of_a_template_are_stripped_on_load(
        self, research_pair, tmp_path
    ) -> None:
        request, research = research_pair
        brief = _brief(request, research, [_claim(research, "convertit").id])
        payload = brief.to_payload()
        payload["_help"] = "rappel destiné au rédacteur"
        payload["visual_proofs"][0]["_claim_text"] = "texte de l'affirmation"
        path = tmp_path / "brief.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        assert load_brief(path) == brief


class TestBriefTemplate:
    def test_it_ranks_by_measured_demonstrability(self, research_pair) -> None:
        request, research = research_pair
        template = brief_template(request, research, max_proofs=4)
        scores = [proof["_demonstrability"] for proof in template["visual_proofs"]]
        assert scores == sorted(scores, reverse=True)

    def test_it_writes_nothing_the_author_must_decide(self, research_pair) -> None:
        request, research = research_pair
        template = brief_template(request, research)
        assert template["thesis"] == ""
        assert template["ending_payoff"] == ""
        assert all(proof["visual_proof"] == "" for proof in template["visual_proofs"])

    def test_an_unfilled_template_is_refused(self, research_pair, tmp_path) -> None:
        request, research = research_pair
        path = tmp_path / "template.json"
        path.write_text(
            json.dumps(brief_template(request, research), ensure_ascii=False),
            encoding="utf-8",
        )
        with pytest.raises(ValidationError):
            load_brief(path)


# --------------------------------------------------------------- compilation


class TestDirectorCompiler:
    def _compiled(self, request, research, fragments: list[str], **brief_overrides):
        claims = [_claim(research, fragment).id for fragment in fragments]
        brief = _brief(request, research, claims, **brief_overrides)
        return DirectorCompiler().compile(
            request=request, research=research, brief=brief
        ), brief

    def test_it_produces_a_valid_director_state(self, research_pair) -> None:
        request, research = research_pair
        outcome, brief = self._compiled(research_pair[0], research, ["stator", "rotor porte"])
        state = outcome.state
        assert state.thesis == brief.thesis
        assert state.parent_id == brief.id
        assert state.research_state_id == research.id

    def test_shot_durations_spend_the_target_exactly(self, research_pair) -> None:
        request, research = research_pair
        outcome, _ = self._compiled(request, research, ["stator", "rotor porte"])
        total = sum(intent.target_duration_s for intent in outcome.state.shot_intents)
        assert total == pytest.approx(request.target_duration_s, abs=1e-3)

    def test_it_opens_on_a_hook_and_closes_on_a_payoff(self, research_pair) -> None:
        request, research = research_pair
        outcome, _ = self._compiled(request, research, ["stator"])
        functions = [i.narrative_function for i in outcome.state.shot_intents]
        assert functions[0] is F.HOOK
        assert functions[-1] is F.PAYOFF

    def test_the_causal_chain_follows_the_fact_graph(self, research_pair) -> None:
        request, research = research_pair
        outcome, _ = self._compiled(request, research, ["rotor porte", "stator"])
        chain = outcome.state.causal_chain
        stator_id = _claim(research, "stator").id
        rotor_id = _claim(research, "rotor porte").id
        # Le graphe dit : le stator cause l'alignement du rotor.
        assert chain.index(stator_id) < chain.index(rotor_id)

    def test_the_narrative_function_follows_the_claim_kind(self, research_pair) -> None:
        request, research = research_pair
        outcome, _ = self._compiled(request, research, ["stator", "rotor porte"])
        by_claim = {
            intent.claim_id: intent.narrative_function
            for intent in outcome.state.shot_intents
            if intent.claim_id
        }
        assert by_claim[_claim(research, "stator").id] is F.MECHANISM
        assert by_claim[_claim(research, "rotor porte").id] is F.CONSEQUENCE

    def test_anchors_reach_the_shots_that_cite_them(self, research_pair) -> None:
        request, research = research_pair
        outcome, _ = self._compiled(request, research, ["stator"])
        anchor_id = outcome.state.continuity_anchors[0].id
        demonstrative = [
            intent for intent in outcome.state.shot_intents if intent.claim_id
        ]
        assert all(anchor_id in intent.anchor_ids for intent in demonstrative)

    def test_a_disputed_claim_needs_an_explicit_acknowledgement(
        self, research_pair
    ) -> None:
        request, research = research_pair
        disputed = next(
            claim
            for claim in research.claims
            if claim.verification is VerificationStatus.DISPUTED
        )
        with pytest.raises(BriefRejected, match="sans aveu explicite"):
            self._compiled(request, research, [], visual_proofs=[_proof(disputed.id)])

    def test_an_acknowledged_dispute_is_allowed(self, research_pair) -> None:
        request, research = research_pair
        disputed = next(
            claim
            for claim in research.claims
            if claim.verification is VerificationStatus.DISPUTED
        )
        outcome, _ = self._compiled(
            request,
            research,
            [],
            visual_proofs=[_proof(disputed.id, acknowledged_dispute=True)],
        )
        assert disputed.id in outcome.state.claim_ids

    def test_a_proof_on_an_unknown_claim_is_refused(self, research_pair) -> None:
        request, research = research_pair
        with pytest.raises(BriefRejected, match="absente de la recherche"):
            self._compiled(
                request, research, [], visual_proofs=[_proof("claim-fantome")]
            )

    def test_a_brief_written_on_another_research_state_is_refused(
        self, research_pair
    ) -> None:
        request, research = research_pair
        other = ResearchEngine(providers=[LocalCorpusProvider(CORPUS)]).run(request).state
        brief = _brief(request, other, [_claim(other, "stator").id])
        with pytest.raises(BriefRejected, match="autre état de recherche"):
            DirectorCompiler().compile(request=request, research=research, brief=brief)

    def test_no_room_for_a_demonstrative_shot_is_refused(self, research_pair) -> None:
        request, research = research_pair
        brief = _brief(request, research, [_claim(research, "stator").id])
        with pytest.raises(BriefRejected, match="aucun plan démonstratif"):
            DirectorCompiler(max_shots=2).compile(
                request=request, research=research, brief=brief
            )

    def test_an_unknown_exclusion_is_refused(self, research_pair) -> None:
        request, research = research_pair
        with pytest.raises(BriefRejected, match="exclusions portant sur"):
            self._compiled(
                request,
                research,
                ["stator"],
                excluded_claim_ids=["claim-fantome"],
            )

    def test_an_exclusion_is_recorded_never_silent(self, research_pair) -> None:
        request, research = research_pair
        excluded = _claim(research, "thermique").id
        outcome, _ = self._compiled(
            request, research, ["stator"], excluded_claim_ids=[excluded]
        )
        assert any(excluded in line for line in outcome.dropped)

    def test_claims_beyond_the_shot_budget_are_reported(self) -> None:
        request, research = _fresh(120.0)
        demonstrable = sorted(
            research.claims, key=lambda claim: -claim.demonstrability
        )[:9]
        brief = _brief(
            request,
            research,
            [],
            visual_proofs=[
                _proof(claim.id, acknowledged_dispute=True) for claim in demonstrable
            ],
        )
        outcome = DirectorCompiler(max_shots=6).compile(
            request=request, research=research, brief=brief
        )
        assert len(outcome.state.claim_ids) == 4
        assert len(outcome.dropped) == 5
        assert all("au-delà de 4 plans" in line for line in outcome.dropped)

    def test_a_metronomic_cadence_is_flagged(self) -> None:
        """45 s pour 5 plans « measured » : toutes les durées butent sur 9 s."""
        request, research = _fresh(45.0)
        brief = _brief(
            request,
            research,
            [_claim(research, f).id for f in ("stator", "rotor porte", "convertit")],
        )
        outcome = DirectorCompiler().compile(
            request=request, research=research, brief=brief
        )
        joined = " ".join(outcome.notes)
        assert "métronomique" in joined
        assert "§8" in joined

    def test_the_compilation_is_deterministic(self, research_pair) -> None:
        request, research = research_pair
        claims = [_claim(research, f).id for f in ("stator", "rotor porte")]
        brief = _brief(request, research, claims)
        first = DirectorCompiler().compile(request=request, research=research, brief=brief)
        second = DirectorCompiler().compile(request=request, research=research, brief=brief)
        assert [i.target_duration_s for i in first.state.shot_intents] == [
            i.target_duration_s for i in second.state.shot_intents
        ]
        assert first.state.causal_chain == second.state.causal_chain


class TestFramingShots:
    """L'ouverture et la chute ne disent pas la même chose."""

    def test_the_payoff_carries_the_payoff_not_the_thesis(self, research_pair) -> None:
        request, research = research_pair
        brief = _brief(request, research, [_claim(research, "stator").id])
        state = DirectorCompiler().compile(
            request=request, research=research, brief=brief
        ).state
        hook = state.shot_intents[0]
        payoff = state.shot_intents[-1]
        assert hook.what_the_viewer_must_understand == brief.thesis
        assert payoff.what_the_viewer_must_understand == brief.ending_payoff
        assert hook.what_the_viewer_must_understand != payoff.what_the_viewer_must_understand
