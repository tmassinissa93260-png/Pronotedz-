"""Structures du storyboard, de l'analyse d'image et du plan d'animation.

Le JSON attendu d'OpenAI est decrit ici et nulle part ailleurs : c'est le
contrat. `validator.py` verifie qu'il est tenu.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Vocabulaire controle des intentions de mouvement (CONDITION « MOTION INTENT »).
MOTION_INTENTS = (
    "reveal",
    "orbit",
    "macro_travel",
    "interaction",
    "tracking",
    "energy_follow",
    "mechanical_rotation",
    "electromagnetic_rotation",
    "gear_rotation",
    "drivetrain_follow",
    "causal_traversal",
    "acceleration",
    "deceleration",
    "reverse_energy",
    "energy_generation",
    "energy_return",
)

VISUAL_BIBLE_FIELDS = (
    "vehicle",
    "environment",
    "materials",
    "lighting",
    "color_palette",
    "camera_language",
)

SHOT_TEXT_FIELDS = (
    "voice",
    "visual_description",
    "educational_function",
    "image_prompt",
)


class StoryboardError(ValueError):
    """Le JSON recu n'a pas la forme du contrat."""


@dataclass
class VisualBible:
    vehicle: str
    environment: str
    materials: str
    lighting: str
    color_palette: str
    camera_language: str

    def as_block(self) -> str:
        """La bible telle qu'elle est injectee dans chaque prompt photo."""
        return (
            f"Vehicle: {self.vehicle}\n"
            f"Environment: {self.environment}\n"
            f"Materials: {self.materials}\n"
            f"Lighting: {self.lighting}\n"
            f"Colour palette: {self.color_palette}\n"
            f"Camera language: {self.camera_language}"
        )

    @classmethod
    def from_dict(cls, raw: object) -> VisualBible:
        if not isinstance(raw, dict):
            raise StoryboardError("'visual_bible' manquante ou invalide")
        missing = [f for f in VISUAL_BIBLE_FIELDS if not str(raw.get(f) or "").strip()]
        if missing:
            raise StoryboardError(f"visual_bible : champ(s) vide(s) : {', '.join(missing)}")
        return cls(**{f: str(raw[f]).strip() for f in VISUAL_BIBLE_FIELDS})


@dataclass
class Shot:
    id: int
    duration_seconds: float
    voice: str
    visual_description: str
    educational_function: str
    image_prompt: str
    semantic_alignment_score: float

    @property
    def slug(self) -> str:
        return f"shot_{self.id:02d}"

    @property
    def word_count(self) -> int:
        return len([w for w in self.voice.split() if w.strip()])

    @property
    def words_per_second(self) -> float:
        return self.word_count / self.duration_seconds if self.duration_seconds else 0.0

    @classmethod
    def from_dict(cls, index: int, raw: object) -> Shot:
        label = f"plan #{index + 1}"
        if not isinstance(raw, dict):
            raise StoryboardError(f"{label} : doit etre un objet JSON")

        missing = [f for f in SHOT_TEXT_FIELDS if not str(raw.get(f) or "").strip()]
        if missing:
            raise StoryboardError(f"{label} : champ(s) vide(s) : {', '.join(missing)}")

        return cls(
            id=_number(raw.get("id"), f"{label} 'id'", integer=True),
            duration_seconds=_number(raw.get("duration_seconds"), f"{label} 'duration_seconds'"),
            voice=str(raw["voice"]).strip(),
            visual_description=str(raw["visual_description"]).strip(),
            educational_function=str(raw["educational_function"]).strip(),
            image_prompt=str(raw["image_prompt"]).strip(),
            semantic_alignment_score=_number(
                raw.get("semantic_alignment_score"), f"{label} 'semantic_alignment_score'"
            ),
        )


@dataclass
class Storyboard:
    subject: str
    duration_seconds: float
    shot_count: int
    visual_bible: VisualBible
    shots: list[Shot] = field(default_factory=list)

    @property
    def total_duration(self) -> float:
        return round(sum(s.duration_seconds for s in self.shots), 3)

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
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    @classmethod
    def load(cls, path: Path) -> Storyboard:
        try:
            return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except FileNotFoundError:
            raise StoryboardError(f"project.json introuvable : {path}") from None
        except json.JSONDecodeError as exc:
            raise StoryboardError(f"project.json illisible : {exc}") from exc

    @classmethod
    def from_dict(cls, raw: object) -> Storyboard:
        if not isinstance(raw, dict):
            raise StoryboardError("la reponse doit etre un objet JSON")
        if not str(raw.get("subject") or "").strip():
            raise StoryboardError("champ 'subject' vide ou manquant")

        shots_raw = raw.get("shots")
        if not isinstance(shots_raw, list) or not shots_raw:
            raise StoryboardError("champ 'shots' vide ou manquant")

        return cls(
            subject=str(raw["subject"]).strip(),
            duration_seconds=_number(raw.get("duration_seconds"), "'duration_seconds'"),
            shot_count=_number(raw.get("shot_count"), "'shot_count'", integer=True),
            visual_bible=VisualBible.from_dict(raw.get("visual_bible")),
            shots=[Shot.from_dict(i, s) for i, s in enumerate(shots_raw)],
        )


# ---------------------------------------------------------------------------
# Analyse d'image et plan d'animation
# ---------------------------------------------------------------------------

ANALYSIS_LIST_FIELDS = ("visible_subjects", "important_components", "preserve", "possible_motion")
ANALYSIS_TEXT_FIELDS = ("composition", "camera", "lighting")


@dataclass
class ImageAnalysis:
    """Ce qui est REELLEMENT visible dans l'image, avant toute animation."""

    visible_subjects: list[str]
    composition: str
    camera: str
    lighting: str
    important_components: list[str]
    preserve: list[str]
    possible_motion: list[str]

    def as_block(self) -> str:
        return (
            f"Visible subjects: {', '.join(self.visible_subjects)}\n"
            f"Composition: {self.composition}\n"
            f"Camera: {self.camera}\n"
            f"Lighting: {self.lighting}\n"
            f"Important components: {', '.join(self.important_components)}\n"
            f"Must be preserved: {', '.join(self.preserve)}\n"
            f"Possible motion: {', '.join(self.possible_motion)}"
        )

    @classmethod
    def from_dict(cls, raw: object) -> ImageAnalysis:
        if not isinstance(raw, dict):
            raise StoryboardError("l'analyse d'image doit etre un objet JSON")
        missing = [f for f in ANALYSIS_TEXT_FIELDS if not str(raw.get(f) or "").strip()]
        empty = [f for f in ANALYSIS_LIST_FIELDS if not _as_list(raw.get(f))]
        if missing or empty:
            raise StoryboardError(
                f"analyse d'image : champ(s) vide(s) : {', '.join(missing + empty)}"
            )
        return cls(
            visible_subjects=_as_list(raw["visible_subjects"]),
            composition=str(raw["composition"]).strip(),
            camera=str(raw["camera"]).strip(),
            lighting=str(raw["lighting"]).strip(),
            important_components=_as_list(raw["important_components"]),
            preserve=_as_list(raw["preserve"]),
            possible_motion=_as_list(raw["possible_motion"]),
        )


@dataclass
class AnimationPlan:
    animation_prompt: str
    motion_intent: str
    camera_motion: str
    mechanical_motion: str
    energy_motion: str
    preserve: list[str]
    forbidden: list[str]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: object) -> AnimationPlan:
        if not isinstance(raw, dict):
            raise StoryboardError("le plan d'animation doit etre un objet JSON")

        intent = str(raw.get("motion_intent") or "").strip()
        if intent not in MOTION_INTENTS:
            raise StoryboardError(
                f"motion_intent '{intent}' hors vocabulaire.\n"
                f"  Valeurs admises : {', '.join(MOTION_INTENTS)}"
            )

        prompt = str(raw.get("animation_prompt") or "").strip()
        if len(prompt) < 80:
            raise StoryboardError(
                f"animation_prompt trop court pour etre pedagogique : {prompt!r}"
            )

        for champ in ("camera_motion", "mechanical_motion", "energy_motion"):
            if not str(raw.get(champ) or "").strip():
                raise StoryboardError(f"plan d'animation : '{champ}' vide")
        if not _as_list(raw.get("preserve")):
            raise StoryboardError("plan d'animation : 'preserve' vide")
        if not _as_list(raw.get("forbidden")):
            raise StoryboardError("plan d'animation : 'forbidden' vide")

        return cls(
            animation_prompt=prompt,
            motion_intent=intent,
            camera_motion=str(raw["camera_motion"]).strip(),
            mechanical_motion=str(raw["mechanical_motion"]).strip(),
            energy_motion=str(raw["energy_motion"]).strip(),
            preserve=_as_list(raw["preserve"]),
            forbidden=_as_list(raw["forbidden"]),
        )


# ---------------------------------------------------------------------------


def _number(value: object, label: str, integer: bool = False) -> float | int:
    try:
        number = int(value) if integer else float(value)
    except (TypeError, ValueError):
        raise StoryboardError(f"{label} absent ou non numerique") from None
    return number


def _as_list(value: object) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()]
