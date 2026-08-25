"""Invariants de la couche INTENTION NARRATIVE."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pdz2.contracts import (
    AnchorSpec,
    AttributeBinding,
    Curve,
    CurvePoint,
    DirectorState,
    IdentityAttribute,
    NarrativeFunction,
    VisualEvidencePlan,
)
from pdz2.tests import factories


class TestAnchorSpec:
    def test_identity_must_be_pinned_by_a_fixed_attribute(self) -> None:
        with pytest.raises(ValidationError, match="l'identité n'est pas ancrée"):
            factories.anchor(
                identity=[
                    IdentityAttribute(
                        name="angle", value="trois quarts", binding=AttributeBinding.SOFT
                    )
                ]
            )

    def test_duplicate_attribute_names_are_refused(self) -> None:
        with pytest.raises(ValidationError, match="en double"):
            factories.anchor(
                identity=[
                    IdentityAttribute(name="carter", value="bleu"),
                    IdentityAttribute(name="carter", value="rouge"),
                ]
            )

    def test_empty_identity_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            AnchorSpec(
                name="x",
                kind="object",
                canonical_description="x",
                identity=[],
            )

    def test_fixed_attributes_are_reachable(self) -> None:
        anchor = factories.anchor()
        assert [a.name for a in anchor.fixed_attributes()] == ["carter"]


class TestVisualEvidencePlan:
    def test_a_vague_visual_proof_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="trop vague"):
            VisualEvidencePlan(
                claim_id="claim-1",
                causal_mechanism="le courant crée un champ",
                evidence_required="montrer le champ",
                visual_proof="le moteur",
            )

    def test_a_concrete_visual_proof_is_accepted(self) -> None:
        plan = VisualEvidencePlan(
            claim_id="claim-1",
            causal_mechanism="le courant crée un champ tournant",
            evidence_required="voir le champ puis la rotation",
            visual_proof=(
                "Coupe transparente du moteur montrant le courant, le champ "
                "magnétique et la rotation du rotor."
            ),
        )
        assert plan.claim_id == "claim-1"


class TestCurve:
    def test_curve_must_span_zero_to_one(self) -> None:
        with pytest.raises(ValidationError, match="t=0 à t=1"):
            Curve(name="c", points=[CurvePoint(t=0.2, value=0.1), CurvePoint(t=1.0, value=0.9)])

    def test_points_must_be_ordered(self) -> None:
        with pytest.raises(ValidationError, match="non ordonnés"):
            Curve(
                name="c",
                points=[
                    CurvePoint(t=0.0, value=0.1),
                    CurvePoint(t=0.8, value=0.5),
                    CurvePoint(t=0.4, value=0.5),
                    CurvePoint(t=1.0, value=0.9),
                ],
            )

    def test_interpolation_is_linear(self) -> None:
        curve = Curve(
            name="c",
            points=[CurvePoint(t=0.0, value=0.0), CurvePoint(t=1.0, value=1.0)],
        )
        assert curve.value_at(0.0) == pytest.approx(0.0)
        assert curve.value_at(0.25) == pytest.approx(0.25)
        assert curve.value_at(1.0) == pytest.approx(1.0)


class TestShotIntent:
    def test_a_mechanism_shot_must_cite_a_claim(self) -> None:
        with pytest.raises(ValidationError, match="sans claim_id"):
            factories.shot_intent(0, None)

    def test_a_hook_shot_may_stand_alone(self) -> None:
        intent = factories.shot_intent(
            0, None, narrative_function=NarrativeFunction.HOOK
        )
        assert intent.claim_id is None


class TestDirectorState:
    """Les variantes repartent du *même* état, pour ne casser qu'une règle."""

    @staticmethod
    def _variant(state, **changes):
        return DirectorState(**(state.model_dump() | changes))

    def test_valid_state_is_accepted(self) -> None:
        state = factories.director_state()
        assert state.intent(0).order == 0
        assert state.anchor(state.continuity_anchors[0].id)

    def test_causal_chain_stays_inside_the_claims(self) -> None:
        state = factories.director_state()
        with pytest.raises(ValidationError, match="chaîne causale hors périmètre"):
            self._variant(state, causal_chain=["claim-fantome"])

    def test_shot_intents_are_contiguous(self) -> None:
        state = factories.director_state()
        claim_id = state.claim_ids[0]
        anchor_id = state.continuity_anchors[0].id
        with pytest.raises(ValidationError, match="non contiguës"):
            self._variant(
                state,
                shot_intents=[
                    factories.shot_intent(0, claim_id, anchor_ids=[anchor_id]),
                    factories.shot_intent(2, claim_id, anchor_ids=[anchor_id]),
                ],
            )

    def test_a_shot_cannot_reference_an_unknown_anchor(self) -> None:
        state = factories.director_state()
        with pytest.raises(ValidationError, match="ancres inconnues"):
            self._variant(
                state,
                shot_intents=[
                    factories.shot_intent(
                        0, state.claim_ids[0], anchor_ids=["anchor_spec-fantome"]
                    )
                ],
            )

    def test_a_shot_cannot_reference_an_unknown_claim(self) -> None:
        state = factories.director_state()
        anchor_id = state.continuity_anchors[0].id
        with pytest.raises(ValidationError, match="affirmation inconnue"):
            self._variant(
                state,
                shot_intents=[
                    factories.shot_intent(0, "claim-fantome", anchor_ids=[anchor_id])
                ],
            )

    def test_evidence_plan_has_one_entry_per_claim(self) -> None:
        state = factories.director_state()
        plan = state.evidence_plan[0]
        with pytest.raises(ValidationError, match="deux entrées"):
            self._variant(state, evidence_plan=[plan, plan])

    def test_evidence_plan_stays_inside_the_claims(self) -> None:
        state = factories.director_state()
        stray = state.evidence_plan[0].model_copy(update={"claim_id": "claim-fantome"})
        with pytest.raises(ValidationError, match="plan de preuve visuelle hors périmètre"):
            self._variant(state, evidence_plan=[stray])
