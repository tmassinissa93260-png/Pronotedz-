"""Versionnage, registre et migrations."""

from __future__ import annotations

import pytest
from pydantic import Field

from pdz2.contracts.base import Contract
from pdz2.contracts.versioning import (
    ContractRegistry,
    IncompatibleVersion,
    UnknownContract,
    Version,
    registry,
)


class TestVersion:
    def test_parses_semver(self) -> None:
        assert Version.parse("1.2.3") == Version(1, 2, 3)

    @pytest.mark.parametrize("text", ["1.2", "v1.2.3", "1.2.3.4", "abc", ""])
    def test_rejects_non_semver(self, text: str) -> None:
        with pytest.raises(ValueError):
            Version.parse(text)

    def test_orders_by_component(self) -> None:
        assert Version(1, 0, 0) < Version(1, 0, 1) < Version(1, 1, 0) < Version(2, 0, 0)

    def test_reader_accepts_same_or_older_minor(self) -> None:
        reader = Version(1, 3, 0)
        assert reader.can_read(Version(1, 3, 0))
        assert reader.can_read(Version(1, 2, 9))

    def test_reader_refuses_newer_minor_and_other_major(self) -> None:
        reader = Version(1, 3, 0)
        assert not reader.can_read(Version(1, 4, 0))
        assert not reader.can_read(Version(2, 0, 0))
        assert not reader.can_read(Version(0, 9, 0))


class TestRegistry:
    def test_every_registered_contract_has_a_unique_name(self) -> None:
        names = registry.names()
        assert len(names) == len(set(names))

    def test_registered_versions_are_semver(self) -> None:
        for contract_type in registry.types():
            Version.parse(contract_type.CONTRACT_VERSION)

    def test_unknown_name_raises(self) -> None:
        with pytest.raises(UnknownContract):
            registry.get("pas_un_contrat")

    def test_duplicate_name_is_refused(self) -> None:
        local = ContractRegistry()

        class A(Contract):
            CONTRACT_NAME = "double"
            CONTRACT_VERSION = "1.0.0"

        class B(Contract):
            CONTRACT_NAME = "double"
            CONTRACT_VERSION = "1.0.0"

        local.register(A)
        with pytest.raises(ValueError, match="déjà pris"):
            local.register(B)

    def test_registering_the_same_class_twice_is_idempotent(self) -> None:
        local = ContractRegistry()

        class A(Contract):
            CONTRACT_NAME = "idempotent"
            CONTRACT_VERSION = "1.0.0"

        local.register(A)
        local.register(A)
        assert local.names() == ["idempotent"]


class TestMigrations:
    """Le mécanisme de migration est réel : on l'exerce sur un contrat dédié."""

    def _registry_with_v2(self) -> tuple[ContractRegistry, type[Contract]]:
        local = ContractRegistry()

        class Sample(Contract):
            CONTRACT_NAME = "sample"
            CONTRACT_VERSION = "2.0.0"
            label: str = Field(min_length=1)
            weight: float = 1.0

        local.register(Sample)

        def one_zero_to_one_one(payload: dict) -> dict:
            payload = dict(payload)
            payload["weight"] = 1.0
            return payload

        def one_one_to_two_zero(payload: dict) -> dict:
            payload = dict(payload)
            payload["label"] = payload.pop("name")
            return payload

        local.register_migration("sample", "1.0.0", "1.1.0", one_zero_to_one_one)
        local.register_migration("sample", "1.1.0", "2.0.0", one_one_to_two_zero)
        return local, Sample

    def test_chain_runs_end_to_end(self) -> None:
        local, sample = self._registry_with_v2()
        payload = {
            "contract_type": "sample",
            "version": "1.0.0",
            "id": "sample-1",
            "created_at": "2026-01-01T00:00:00Z",
            "parent_id": None,
            "status": "draft",
            "name": "ancien",
        }
        loaded = local.load(payload)
        assert isinstance(loaded, sample)
        assert loaded.label == "ancien"
        assert loaded.weight == 1.0
        assert loaded.version == "2.0.0"

    def test_missing_migration_is_refused_not_guessed(self) -> None:
        local = ContractRegistry()

        class Sample(Contract):
            CONTRACT_NAME = "sample_bare"
            CONTRACT_VERSION = "2.0.0"

        local.register(Sample)
        with pytest.raises(IncompatibleVersion, match="aucune migration"):
            local.migrate(
                {"contract_type": "sample_bare", "version": "1.0.0"}
            )

    def test_backwards_migration_is_refused(self) -> None:
        local = ContractRegistry()

        class Sample(Contract):
            CONTRACT_NAME = "sample_back"
            CONTRACT_VERSION = "1.0.0"

        local.register(Sample)
        with pytest.raises(ValueError, match="version supérieure"):
            local.register_migration("sample_back", "2.0.0", "1.0.0", lambda p: p)

    def test_older_minor_needs_no_migration(self) -> None:
        local = ContractRegistry()

        class Sample(Contract):
            CONTRACT_NAME = "sample_minor"
            CONTRACT_VERSION = "1.4.0"

        local.register(Sample)
        payload = {"contract_type": "sample_minor", "version": "1.2.0"}
        assert local.migrate(payload)["version"] == "1.2.0"
