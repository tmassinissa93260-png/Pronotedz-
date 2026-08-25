"""Export des schémas JSON des contrats.

Les schémas sont versionnés dans le dépôt : une modification de contrat se
voit dans la revue, et un test échoue si l'export n'a pas été régénéré.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pdz2.contracts.base import Contract
from pdz2.contracts.versioning import registry

__all__ = ["SCHEMA_DIR", "schema_for", "schema_filename", "export_all", "check_up_to_date"]

SCHEMA_DIR = Path(__file__).parent / "json"


def schema_filename(contract_type: type[Contract]) -> str:
    return f"{contract_type.CONTRACT_NAME}-{contract_type.CONTRACT_VERSION}.json"


def schema_for(contract_type: type[Contract]) -> dict[str, Any]:
    schema = contract_type.model_json_schema(mode="serialization")
    schema["$id"] = f"pdz2:{contract_type.CONTRACT_NAME}/{contract_type.CONTRACT_VERSION}"
    return schema


def _serialise(schema: dict[str, Any]) -> str:
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def export_all(directory: Path | None = None) -> list[Path]:
    """Écrit un schéma par contrat enregistré. Retourne les fichiers écrits."""
    target_dir = Path(directory) if directory is not None else SCHEMA_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    expected: set[str] = set()
    for contract_type in registry.types():
        name = schema_filename(contract_type)
        expected.add(name)
        path = target_dir / name
        path.write_text(_serialise(schema_for(contract_type)), encoding="utf-8")
        written.append(path)
    # Une version retirée ne laisse pas de schéma orphelin derrière elle.
    for stale in target_dir.glob("*.json"):
        if stale.name not in expected:
            stale.unlink()
    return sorted(written)


def check_up_to_date(directory: Path | None = None) -> list[str]:
    """Retourne la liste des écarts entre le code et les schémas exportés."""
    target_dir = Path(directory) if directory is not None else SCHEMA_DIR
    problems: list[str] = []
    expected: set[str] = set()
    for contract_type in registry.types():
        name = schema_filename(contract_type)
        expected.add(name)
        path = target_dir / name
        if not path.is_file():
            problems.append(f"schéma manquant : {name}")
            continue
        if path.read_text(encoding="utf-8") != _serialise(schema_for(contract_type)):
            problems.append(f"schéma périmé : {name}")
    for stale in sorted(target_dir.glob("*.json")):
        if stale.name not in expected:
            problems.append(f"schéma orphelin : {stale.name}")
    return problems
