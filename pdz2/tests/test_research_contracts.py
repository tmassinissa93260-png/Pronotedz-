"""Invariants du moteur de recherche et du Fact Graph."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pdz2.contracts import (
    CausalEdge,
    Claim,
    FactGraph,
    ResearchState,
    TopicRequest,
    VerificationStatus,
)
from pdz2.contracts.research import UNVERIFIED_CONFIDENCE_CEILING
from pdz2.tests import factories


class TestClaimNeverBecomesCertain:
    def test_unverified_claim_cannot_be_confident(self) -> None:
        # Une preuve existe, mais la vérification n'a pas conclu : la confiance
        # reste plafonnée. C'est le cœur de la règle « jamais un fait certain ».
        source = factories.source()
        evidence = factories.evidence(source.id)
        with pytest.raises(ValidationError, match="plafond"):
            factories.claim(
                evidence_ids=[evidence.id],
                verification=VerificationStatus.UNVERIFIED,
                confidence=0.9,
            )

    def test_unverified_claim_under_the_ceiling_is_accepted(self) -> None:
        source = factories.source()
        evidence = factories.evidence(source.id)
        claim = factories.claim(
            evidence_ids=[evidence.id],
            verification=VerificationStatus.UNVERIFIED,
            confidence=UNVERIFIED_CONFIDENCE_CEILING,
        )
        assert claim.confidence == UNVERIFIED_CONFIDENCE_CEILING

    def test_ceiling_is_the_boundary(self) -> None:
        claim = factories.claim(
            evidence_ids=[],
            verification=VerificationStatus.UNVERIFIED,
            confidence=0.0,
        )
        assert claim.confidence == 0.0
        assert UNVERIFIED_CONFIDENCE_CEILING < 1.0

    def test_claim_without_evidence_cannot_be_corroborated(self) -> None:
        with pytest.raises(ValidationError, match="sans preuve"):
            factories.claim(
                evidence_ids=[],
                verification=VerificationStatus.CORROBORATED,
                confidence=0.0,
            )

    def test_claim_without_evidence_has_zero_confidence(self) -> None:
        with pytest.raises(ValidationError, match="confiance forcée à 0"):
            factories.claim(
                evidence_ids=[],
                verification=VerificationStatus.UNVERIFIED,
                confidence=0.3,
            )

    def test_refuted_claim_carries_no_confidence(self) -> None:
        source = factories.source()
        evidence = factories.evidence(source.id)
        with pytest.raises(ValidationError, match="réfutée"):
            factories.claim(
                evidence_ids=[evidence.id],
                verification=VerificationStatus.REFUTED,
                confidence=0.4,
            )

    def test_corroborated_claim_with_evidence_is_accepted(self) -> None:
        source = factories.source()
        evidence = factories.evidence(source.id)
        claim = factories.claim(evidence_ids=[evidence.id])
        assert claim.verification is VerificationStatus.CORROBORATED
        assert claim.confidence > 0


class TestVisualEvidence:
    def test_demonstrable_claim_needs_a_visual_proof(self) -> None:
        with pytest.raises(ValidationError, match="visual_proof"):
            factories.claim(visually_demonstrable=True, visual_proof=None)

    def test_load_bearing_claim_needs_the_full_quartet(self) -> None:
        with pytest.raises(ValidationError, match="causal_mechanism"):
            factories.claim(load_bearing=True, causal_mechanism=None)

    def test_non_load_bearing_claim_may_stay_light(self) -> None:
        claim = Claim(
            text="Une voiture électrique n'a pas de boîte de vitesses classique.",
            load_bearing=False,
        )
        assert claim.visual_proof is None

    def test_claim_cannot_depend_on_itself(self) -> None:
        claim = factories.claim()
        with pytest.raises(ValidationError, match="elle-même"):
            Claim(**(claim.model_dump() | {"depends_on": [claim.id]}))


class TestFactGraph:
    def test_cycle_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="cyclique"):
            FactGraph(
                claim_ids=["a", "b"],
                edges=[
                    CausalEdge(from_claim_id="a", to_claim_id="b"),
                    CausalEdge(from_claim_id="b", to_claim_id="a"),
                ],
            )

    def test_edge_towards_unknown_claim_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="arête vers un inconnu"):
            FactGraph(
                claim_ids=["a"],
                edges=[CausalEdge(from_claim_id="a", to_claim_id="z")],
            )

    def test_reflexive_edge_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="réflexive"):
            CausalEdge(from_claim_id="a", to_claim_id="a")

    def test_topological_order_respects_causality(self) -> None:
        graph = FactGraph(
            claim_ids=["c", "a", "b"],
            edges=[
                CausalEdge(from_claim_id="a", to_claim_id="b"),
                CausalEdge(from_claim_id="b", to_claim_id="c"),
            ],
        )
        order = graph.topological_order()
        assert order.index("a") < order.index("b") < order.index("c")

    def test_duplicate_claim_id_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="en double"):
            FactGraph(claim_ids=["a", "a"])


class TestResearchState:
    def _state(self, **overrides) -> ResearchState:
        source = factories.source()
        evidence = factories.evidence(source.id)
        claim = factories.claim([evidence.id])
        payload = {
            "topic_request_id": "topic_request-x",
            "question": "Comment fonctionne une voiture électrique ?",
            "sources": [source],
            "evidence": [evidence],
            "claims": [claim],
            "fact_graph": FactGraph(claim_ids=[claim.id]),
            "coverage": 0.5,
        }
        return ResearchState(**(payload | overrides))

    def test_valid_state_is_accepted(self) -> None:
        state = self._state()
        assert state.demonstrable_claims()
        assert state.claim(state.claims[0].id) is state.claims[0]

    def test_evidence_must_point_at_a_known_source(self) -> None:
        source = factories.source()
        evidence = factories.evidence("source_reference-fantome")
        with pytest.raises(ValidationError, match="source inconnue"):
            self._state(sources=[source], evidence=[evidence], claims=[])

    def test_claim_must_point_at_known_evidence(self) -> None:
        source = factories.source()
        evidence = factories.evidence(source.id)
        claim = factories.claim(["evidence-fantome"])
        with pytest.raises(ValidationError, match="preuve inconnue"):
            self._state(
                sources=[source],
                evidence=[evidence],
                claims=[claim],
                fact_graph=FactGraph(claim_ids=[claim.id]),
            )

    def test_fact_graph_stays_inside_the_state(self) -> None:
        with pytest.raises(ValidationError, match="absentes de l'état"):
            self._state(fact_graph=FactGraph(claim_ids=["claim-fantome"]))


class TestTopicRequest:
    def test_defaults_are_vertical_and_ai_allowed(self) -> None:
        request = TopicRequest(
            topic="Comment fonctionne une voiture électrique ?",
            target_duration_s=45.0,
        )
        assert request.aspect_ratio.value == "9:16"
        assert request.allow_ai_video is True

    def test_duration_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            TopicRequest(topic="x", target_duration_s=0.0)
