"""Structures de donnees du storyboard et validation de la reponse OpenAI."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

REQUIRED_SHOT_FIELDS = ("id", "duration", "voice", "visual_description", "image_prompt")


class StoryboardError(ValueError):
    """La reponse d'OpenAI n'a pas la forme attendue."""


@dataclass
class Shot:
    id: int
    duration: str
    voice: str
    visual_description: str
    image_prompt: str

    @property
    def slug(self) -> str:
        return f"shot_{self.id:02d}"


@dataclass
class Storyboard:
    subject: str
    duration: int
    visual_style: str
    visual_continuity: str
    shots: list[Shot] = field(default_factory=list)

    def shot(self, shot_id: int) -> Shot:
        for s in self.shots:
            if s.id == shot_id:
                return s
        raise KeyError(f"plan {shot_id} absent du storyboard")

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path) -> Storyboard:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise StoryboardError(f"project.json introuvable: {path}") from None
        except json.JSONDecodeError as exc:
            raise StoryboardError(f"project.json illisible: {exc}") from exc
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: object, expected_shots: int | None = None) -> Storyboard:
        if not isinstance(raw, dict):
            raise StoryboardError("la reponse doit etre un objet JSON")

        for key in ("subject", "visual_style", "visual_continuity"):
            if not str(raw.get(key) or "").strip():
                raise StoryboardError(f"champ '{key}' vide ou manquant")

        shots_raw = raw.get("shots")
        if not isinstance(shots_raw, list) or not shots_raw:
            raise StoryboardError("champ 'shots' vide ou manquant")

        if expected_shots is not None and len(shots_raw) != expected_shots:
            raise StoryboardError(
                f"{len(shots_raw)} plan(s) recu(s), {expected_shots} attendu(s)"
            )

        shots = [_parse_shot(i, s) for i, s in enumerate(shots_raw)]

        ids = [s.id for s in shots]
        if ids != list(range(1, len(shots) + 1)):
            raise StoryboardError(f"les id doivent aller de 1 a {len(shots)}, recu {ids}")

        try:
            duration = int(raw.get("duration"))
        except (TypeError, ValueError):
            raise StoryboardError("champ 'duration' absent ou non numerique") from None

        return cls(
            subject=str(raw["subject"]).strip(),
            duration=duration,
            visual_style=str(raw["visual_style"]).strip(),
            visual_continuity=str(raw["visual_continuity"]).strip(),
            shots=shots,
        )


def _parse_shot(index: int, raw: object) -> Shot:
    label = f"plan #{index + 1}"
    if not isinstance(raw, dict):
        raise StoryboardError(f"{label}: doit etre un objet JSON")

    missing = [f for f in REQUIRED_SHOT_FIELDS if not str(raw.get(f) or "").strip()]
    if missing:
        raise StoryboardError(f"{label}: champ(s) vide(s) ou manquant(s): {', '.join(missing)}")

    try:
        shot_id = int(raw["id"])
    except (TypeError, ValueError):
        raise StoryboardError(f"{label}: 'id' non numerique") from None

    return Shot(
        id=shot_id,
        duration=str(raw["duration"]).strip(),
        voice=str(raw["voice"]).strip(),
        visual_description=str(raw["visual_description"]).strip(),
        image_prompt=str(raw["image_prompt"]).strip(),
    )
