"""Lecture et écriture d'un dossier d'épisode.

Écriture atomique (fichier temporaire puis remplacement) : une interruption
laisse le dossier cohérent, donc reprenable.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import TypeVar

from pdz2.contracts.base import Contract
from pdz2.contracts.pipeline import EpisodeSnapshot
from pdz2.contracts.versioning import registry
from pdz2.storage.layout import EpisodeLayout

__all__ = ["EpisodeStore"]

T = TypeVar("T", bound=Contract)


class EpisodeStore:
    """Dossier d'un épisode sur disque."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    # ------------------------------------------------------------------ dossier

    def initialise(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        for name in EpisodeLayout.directories():
            (self.root / name).mkdir(parents=True, exist_ok=True)
        return self.root

    def path_for(self, contract_type: str, contract_id: str | None = None) -> Path:
        return self.root / EpisodeLayout.relative_path(contract_type, contract_id)

    def exists(self, contract_type: str, contract_id: str | None = None) -> bool:
        return self.path_for(contract_type, contract_id).is_file()

    # ------------------------------------------------------------------ contrats

    def save(self, item: Contract) -> Path:
        target = self.path_for(item.CONTRACT_NAME, item.id)
        _write_json(target, item.to_payload())
        return target

    def load(self, contract_type: str, contract_id: str | None = None) -> Contract:
        target = self.path_for(contract_type, contract_id)
        payload = json.loads(target.read_text(encoding="utf-8"))
        return registry.load(payload)

    def load_as(
        self,
        expected: type[T],
        contract_id: str | None = None,
    ) -> T:
        loaded = self.load(expected.CONTRACT_NAME, contract_id)
        if not isinstance(loaded, expected):
            raise TypeError(
                f"{expected.CONTRACT_NAME} attendu, "
                f"{loaded.CONTRACT_NAME} trouvé"
            )
        return loaded

    def load_collection(self, contract_type: str) -> list[Contract]:
        directory = self.path_for(contract_type, "placeholder").parent
        if not directory.is_dir():
            return []
        items: list[Contract] = []
        for path in sorted(directory.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("contract_type") != contract_type:
                continue
            items.append(registry.load(payload))
        return items

    # -------------------------------------------------------------------- état

    def save_snapshot(self, snapshot: EpisodeSnapshot) -> Path:
        target = self.path_for("episode_snapshot")
        _write_json(target, snapshot.to_payload())
        return target

    def load_snapshot(self) -> EpisodeSnapshot:
        return self.load_as(EpisodeSnapshot)

    def has_snapshot(self) -> bool:
        return self.exists("episode_snapshot")


def _write_json(target: Path, payload: dict) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    handle = tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
        delete=False,
    )
    try:
        with handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(handle.name, target)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise
