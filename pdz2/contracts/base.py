"""Socle commun des contrats PDZ 2.

Tout contrat porte : id, version, created_at, parent_id, status. `parent_id`
donne la lignée — un contrat réparé pointe vers celui qu'il remplace, ce qui
rend une production rejouable et auditable.

Les objets de valeur qui ne sont pas des contrats du cahier des charges
(composition, transition, point de courbe…) héritent d'`Element` : mêmes
règles de validation strictes, pas d'identité propre.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pdz2.contracts.identity import new_id
from pdz2.contracts.versioning import IncompatibleVersion, Version, registry

__all__ = ["ContractStatus", "Element", "Contract", "contract"]


class ContractStatus(str, Enum):
    """Cycle de vie commun à tous les contrats."""

    DRAFT = "draft"
    """Produit, pas encore passé par son validateur."""

    VALIDATED = "validated"
    """Accepté par le validateur statique : exécutable."""

    REJECTED = "rejected"
    """Refusé par le validateur statique : aucune dépense autorisée."""

    EXECUTED = "executed"
    """Consommé par l'aval avec succès."""

    SUPERSEDED = "superseded"
    """Remplacé par un descendant (réparation, nouvelle passe)."""

    FAILED = "failed"
    """Exécution tentée et perdue."""


class Element(BaseModel):
    """Objet de valeur imbriqué dans un contrat. Pas d'identité propre."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        use_enum_values=False,
        str_strip_whitespace=True,
    )


class Contract(Element):
    """Base de tout contrat versionné."""

    CONTRACT_NAME: ClassVar[str] = ""
    CONTRACT_VERSION: ClassVar[str] = "0.0.0"
    CONTRACT_SEMVER: ClassVar[Version] = Version(0, 0, 0)

    contract_type: str = Field(frozen=True)
    version: str = Field(frozen=True)
    id: str = Field(frozen=True)
    created_at: datetime = Field(frozen=True)
    parent_id: str | None = Field(default=None, frozen=True)
    status: ContractStatus = ContractStatus.DRAFT

    # ------------------------------------------------------------- estampille

    @model_validator(mode="before")
    @classmethod
    def _stamp(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if not cls.CONTRACT_NAME:
            raise TypeError(f"{cls.__name__} n'est pas enregistré comme contrat")
        data = dict(data)
        data.setdefault("contract_type", cls.CONTRACT_NAME)
        data.setdefault("version", cls.CONTRACT_VERSION)
        data.setdefault("id", new_id(cls.CONTRACT_NAME))
        data.setdefault("created_at", datetime.now(UTC))
        return data

    @model_validator(mode="after")
    def _check_stamp(self) -> Self:
        if self.contract_type != self.CONTRACT_NAME:
            raise ValueError(
                f"contract_type {self.contract_type!r} lu par "
                f"{type(self).__name__} ({self.CONTRACT_NAME!r})"
            )
        payload = Version.parse(self.version)
        current = Version.parse(self.CONTRACT_VERSION)
        if not current.can_read(payload):
            raise IncompatibleVersion(
                f"{self.CONTRACT_NAME} : version {payload} illisible par {current}"
            )
        if self.created_at.tzinfo is None:
            raise ValueError("created_at doit porter un fuseau (UTC attendu)")
        if self.parent_id == self.id:
            raise ValueError("un contrat ne peut pas être son propre parent")
        return self

    # ------------------------------------------------------------------ lignée

    def derive(self, **changes: Any) -> Self:
        """Produit un descendant : identité neuve, `parent_id` renseigné.

        Le contrat courant n'est pas modifié — c'est à l'appelant de le marquer
        `SUPERSEDED` une fois le descendant accepté.
        """
        payload = self.model_dump(mode="python")
        payload.update(changes)
        payload["parent_id"] = self.id
        payload["id"] = new_id(self.CONTRACT_NAME)
        payload["version"] = self.CONTRACT_VERSION
        payload["created_at"] = datetime.now(UTC)
        if "status" not in changes:
            payload["status"] = ContractStatus.DRAFT
        return type(self).model_validate(payload)

    def superseded_by(self, successor: Contract) -> Self:
        """Marque ce contrat comme remplacé par `successor`."""
        if successor.parent_id != self.id:
            raise ValueError("le successeur ne descend pas de ce contrat")
        self.status = ContractStatus.SUPERSEDED
        return self

    # ------------------------------------------------------------ sérialisation

    def to_payload(self) -> dict[str, Any]:
        """Charge utile JSON-compatible, relisible par `registry.load`."""
        return self.model_dump(mode="json")

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> Self:
        """Relit une charge utile, migrations comprises."""
        loaded = registry.load(dict(payload))
        if not isinstance(loaded, cls):
            raise TypeError(
                f"{payload.get('contract_type')!r} n'est pas un {cls.__name__}"
            )
        return loaded


def contract(name: str, version: str):
    """Déclare et enregistre un contrat.

    Usage :

        @contract("shot_spec", "1.0.0")
        class ShotSpec(Contract): ...
    """

    def decorate(cls: type[Contract]) -> type[Contract]:
        cls.CONTRACT_NAME = name
        cls.CONTRACT_VERSION = version
        registry.register(cls)
        return cls

    return decorate
