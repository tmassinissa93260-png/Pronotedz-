"""Socle des contrats : estampille, lignée, sérialisation, identité."""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from pydantic import Field, ValidationError

from pdz2.contracts import ContractStatus, deterministic_ids, registry
from pdz2.contracts.base import Contract
from pdz2.contracts.versioning import ContractRegistry
from pdz2.tests import factories


class Sample(Contract):
    CONTRACT_NAME = "test_sample"
    CONTRACT_VERSION = "1.0.0"
    label: str = Field(default="x", min_length=1)


ContractRegistry().register(Sample)


class TestStamping:
    def test_required_fields_are_filled_automatically(self) -> None:
        item = Sample()
        assert item.contract_type == "test_sample"
        assert item.version == "1.0.0"
        assert item.id.startswith("test_sample-")
        assert item.created_at.tzinfo is not None
        assert item.parent_id is None
        assert item.status is ContractStatus.DRAFT

    def test_every_registered_contract_carries_the_five_fields(self) -> None:
        required = {"id", "version", "created_at", "parent_id", "status"}
        for contract_type in registry.types():
            missing = required - set(contract_type.model_fields)
            assert not missing, f"{contract_type.CONTRACT_NAME} : champs manquants {missing}"

    def test_identity_fields_are_frozen(self) -> None:
        item = Sample()
        for field in ("id", "version", "created_at", "parent_id", "contract_type"):
            with pytest.raises(ValidationError):
                setattr(item, field, "autre")

    def test_status_stays_mutable(self) -> None:
        item = Sample()
        item.status = ContractStatus.VALIDATED
        assert item.status is ContractStatus.VALIDATED

    def test_naive_timestamp_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="fuseau"):
            Sample(created_at=datetime(2026, 1, 1))

    def test_wrong_contract_type_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="contract_type"):
            Sample(contract_type="autre_chose")

    def test_future_minor_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="illisible"):
            Sample(version="1.1.0")

    def test_unknown_field_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            Sample(champ_inconnu=1)


class TestLineage:
    def test_derive_creates_a_child(self) -> None:
        parent = Sample(label="v1", status=ContractStatus.VALIDATED)
        child = parent.derive(label="v2")
        assert child.parent_id == parent.id
        assert child.id != parent.id
        assert child.label == "v2"
        assert child.status is ContractStatus.DRAFT
        assert parent.label == "v1"

    def test_supersede_marks_the_parent(self) -> None:
        parent = Sample()
        child = parent.derive()
        parent.superseded_by(child)
        assert parent.status is ContractStatus.SUPERSEDED

    def test_supersede_refuses_an_unrelated_contract(self) -> None:
        parent = Sample()
        stranger = Sample()
        with pytest.raises(ValueError, match="ne descend pas"):
            parent.superseded_by(stranger)

    def test_self_parenting_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="propre parent"):
            Sample(id="test_sample-1", parent_id="test_sample-1")


class TestSerialisation:
    def test_round_trip_through_json(self) -> None:
        original = factories.director_state()
        text = json.dumps(original.to_payload(), ensure_ascii=False)
        reloaded = registry.load(json.loads(text))
        assert reloaded == original

    def test_every_contract_round_trips(self) -> None:
        samples = [
            factories.source(),
            factories.claim(),
            factories.anchor(),
            factories.director_state(),
            factories.script_state(),
            factories.voice_timeline(),
            factories.camera_program(),
            factories.motion_program(),
            factories.shot_spec(),
            factories.render_spec_requested(),
            factories.render_spec_executable(),
        ]
        for item in samples:
            payload = json.loads(json.dumps(item.to_payload(), ensure_ascii=False))
            assert registry.load(payload) == item, item.CONTRACT_NAME

    def test_load_rejects_a_mismatched_expected_type(self) -> None:
        from pdz2.contracts import Claim

        payload = factories.source().to_payload()
        with pytest.raises(TypeError):
            Claim.from_payload(payload)


class TestDeterministicIdentity:
    def test_same_seed_gives_same_ids(self) -> None:
        with deterministic_ids("graine-42"):
            first = [Sample().id for _ in range(3)]
        with deterministic_ids("graine-42"):
            second = [Sample().id for _ in range(3)]
        assert first == second
        assert len(set(first)) == 3

    def test_different_seeds_diverge(self) -> None:
        with deterministic_ids("a"):
            first = Sample().id
        with deterministic_ids("b"):
            second = Sample().id
        assert first != second

    def test_factory_is_restored_after_the_block(self) -> None:
        with deterministic_ids("x"):
            inside = Sample().id
        outside = Sample().id
        assert inside != outside
