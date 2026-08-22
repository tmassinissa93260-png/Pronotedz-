"""Versions de contrats, registre et migrations.

Chaque type de contrat déclare une version sémantique. Un lecteur accepte une
charge utile si et seulement si :

  * le nom de contrat est connu du registre ;
  * la version majeure est identique ;
  * la version mineure de la charge est <= celle du lecteur.

Toute autre combinaison exige une migration explicitement enregistrée. Aucune
lecture « au mieux » : un document illisible est refusé, pas deviné.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typage seul
    from pdz2.contracts.base import Contract

__all__ = [
    "Version",
    "ContractRegistry",
    "UnknownContract",
    "IncompatibleVersion",
    "MigrationError",
    "registry",
]

_SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


class UnknownContract(LookupError):
    """Nom de contrat absent du registre."""


class IncompatibleVersion(ValueError):
    """Version illisible et sans chemin de migration."""


class MigrationError(RuntimeError):
    """Une migration enregistrée a échoué ou boucle."""


@dataclass(frozen=True, order=True)
class Version:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, text: str) -> Version:
        match = _SEMVER.match(text.strip())
        if match is None:
            raise ValueError(f"version non sémantique : {text!r}")
        return cls(int(match[1]), int(match[2]), int(match[3]))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def can_read(self, payload: Version) -> bool:
        """Vrai si un lecteur en version `self` peut lire `payload` tel quel."""
        return payload.major == self.major and payload.minor <= self.minor


# (nom, version source) -> (version cible, fonction)
_MigrationStep = tuple[Version, Callable[[dict[str, Any]], dict[str, Any]]]


class ContractRegistry:
    """Annuaire des contrats connus et de leurs migrations."""

    def __init__(self) -> None:
        self._types: dict[str, type[Contract]] = {}
        self._migrations: dict[tuple[str, Version], _MigrationStep] = {}

    # ------------------------------------------------------------------ types

    def register(self, contract_type: type[Contract]) -> type[Contract]:
        """Décorateur : enregistre un type de contrat."""
        name = contract_type.CONTRACT_NAME
        if not name:
            raise ValueError(f"{contract_type.__name__} ne déclare pas CONTRACT_NAME")
        version = Version.parse(contract_type.CONTRACT_VERSION)
        existing = self._types.get(name)
        if existing is not None and existing is not contract_type:
            raise ValueError(
                f"nom de contrat déjà pris : {name!r} "
                f"({existing.__name__} vs {contract_type.__name__})"
            )
        contract_type.CONTRACT_SEMVER = version
        self._types[name] = contract_type
        return contract_type

    def get(self, name: str) -> type[Contract]:
        try:
            return self._types[name]
        except KeyError as exc:
            raise UnknownContract(f"contrat inconnu : {name!r}") from exc

    def names(self) -> list[str]:
        return sorted(self._types)

    def types(self) -> list[type[Contract]]:
        return [self._types[name] for name in self.names()]

    def __contains__(self, name: object) -> bool:
        return name in self._types

    # ------------------------------------------------------------- migrations

    def register_migration(
        self,
        name: str,
        from_version: str,
        to_version: str,
        step: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> None:
        """Enregistre une transformation de charge utile entre deux versions."""
        source = Version.parse(from_version)
        target = Version.parse(to_version)
        if target <= source:
            raise ValueError("une migration doit aller vers une version supérieure")
        key = (name, source)
        if key in self._migrations:
            raise ValueError(f"migration déjà enregistrée pour {name} {source}")
        self._migrations[key] = (target, step)

    def migrate(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Amène une charge utile à la version courante de son contrat."""
        name = payload.get("contract_type")
        if not isinstance(name, str):
            raise UnknownContract("charge utile sans champ 'contract_type'")
        contract_type = self.get(name)
        current = Version.parse(contract_type.CONTRACT_VERSION)
        raw_version = payload.get("version")
        if not isinstance(raw_version, str):
            raise IncompatibleVersion(f"{name} : charge utile sans champ 'version'")
        version = Version.parse(raw_version)

        working = dict(payload)
        seen: set[Version] = set()
        while not current.can_read(version):
            if version in seen:
                raise MigrationError(f"{name} : boucle de migration en {version}")
            seen.add(version)
            entry = self._migrations.get((name, version))
            if entry is None:
                raise IncompatibleVersion(
                    f"{name} : version {version} illisible par {current} "
                    "et aucune migration enregistrée"
                )
            target, step = entry
            working = step(working)
            working["version"] = str(target)
            version = target
        return working

    # ----------------------------------------------------------------- lecture

    def load(self, payload: dict[str, Any]) -> Contract:
        """Migre puis instancie une charge utile en contrat typé."""
        migrated = self.migrate(payload)
        contract_type = self.get(migrated["contract_type"])
        return contract_type.model_validate(migrated)

    def load_many(self, payloads: Iterable[dict[str, Any]]) -> list[Contract]:
        return [self.load(item) for item in payloads]


registry = ContractRegistry()
