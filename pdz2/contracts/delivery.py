"""Montage, sous-titres, master.

`EditTimeline` décrit le montage final piste par piste ; `MasterArtifact`
décrit le livrable et ce qui a été mesuré dessus.
"""

from __future__ import annotations

from enum import Enum
from typing import Self

from pydantic import Field, model_validator

from pdz2.contracts.base import Contract, Element, contract
from pdz2.contracts.common import Resolution, Transition
from pdz2.contracts.enums import AspectRatio, ScreenPosition

__all__ = [
    "TrackKind",
    "Clip",
    "Track",
    "EditTimeline",
    "SubtitleCue",
    "SubtitleTrack",
    "LoudnessMeasurement",
    "MasterArtifact",
]

TIMELINE_TOLERANCE_S = 0.02


class TrackKind(str, Enum):
    VIDEO = "video"
    VOICE = "voice"
    MUSIC = "music"
    SFX = "sfx"
    OVERLAY = "overlay"


class Clip(Element):
    artifact_id: str = Field(min_length=1)
    source_in_s: float = Field(ge=0.0)
    source_out_s: float = Field(gt=0.0)
    timeline_in_s: float = Field(ge=0.0)
    timeline_out_s: float = Field(gt=0.0)
    transition_in: Transition = Field(default_factory=Transition)
    transition_out: Transition = Field(default_factory=Transition)
    gain_db: float = Field(default=0.0, ge=-60.0, le=12.0)
    shot_id: str | None = None

    @model_validator(mode="after")
    def _spans_are_forward(self) -> Self:
        if self.source_out_s <= self.source_in_s:
            raise ValueError(f"clip {self.artifact_id} : extrait source à l'envers")
        if self.timeline_out_s <= self.timeline_in_s:
            raise ValueError(f"clip {self.artifact_id} : position montage à l'envers")
        return self

    @property
    def duration_s(self) -> float:
        return self.timeline_out_s - self.timeline_in_s

    @property
    def source_duration_s(self) -> float:
        return self.source_out_s - self.source_in_s


class Track(Element):
    kind: TrackKind
    name: str = Field(min_length=1)
    clips: list[Clip] = Field(default_factory=list)
    muted: bool = False

    @model_validator(mode="after")
    def _clips_do_not_overlap(self) -> Self:
        ordered = sorted(self.clips, key=lambda clip: clip.timeline_in_s)
        if [clip.timeline_in_s for clip in self.clips] != [
            clip.timeline_in_s for clip in ordered
        ]:
            raise ValueError(f"piste {self.name} : clips dans le désordre")
        previous_end = 0.0
        for clip in ordered:
            if clip.timeline_in_s < previous_end - TIMELINE_TOLERANCE_S:
                raise ValueError(
                    f"piste {self.name} : chevauchement à {clip.timeline_in_s:.3f}s"
                )
            previous_end = clip.timeline_out_s
        return self

    @property
    def end_s(self) -> float:
        return max((clip.timeline_out_s for clip in self.clips), default=0.0)


class SubtitleCue(Element):
    index: int = Field(ge=0)
    text: str = Field(min_length=1)
    start_s: float = Field(ge=0.0)
    end_s: float = Field(gt=0.0)
    position: ScreenPosition = ScreenPosition.LOWER_THIRD

    @model_validator(mode="after")
    def _forward(self) -> Self:
        if self.end_s <= self.start_s:
            raise ValueError(f"sous-titre {self.index} : fin avant début")
        return self


@contract("subtitle_track", "1.0.0")
class SubtitleTrack(Contract):
    voice_timeline_id: str = Field(min_length=1)
    language: str = Field(default="fr", min_length=2, max_length=8)
    cues: list[SubtitleCue] = Field(min_length=1)
    max_chars_per_line: int = Field(default=28, gt=0)

    @model_validator(mode="after")
    def _cues_are_ordered(self) -> Self:
        indexes = [cue.index for cue in self.cues]
        if indexes != list(range(len(indexes))):
            raise ValueError(f"sous-titres non contigus depuis 0 : {indexes}")
        previous_end = 0.0
        for cue in self.cues:
            if cue.start_s < previous_end - TIMELINE_TOLERANCE_S:
                raise ValueError(f"sous-titre {cue.index} : chevauche le précédent")
            previous_end = cue.end_s
        return self


@contract("edit_timeline", "1.0.0")
class EditTimeline(Contract):
    episode_id: str = Field(min_length=1)
    shot_graph_id: str = Field(min_length=1)
    tracks: list[Track] = Field(min_length=1)
    duration_s: float = Field(gt=0.0)
    fps: int = Field(gt=0, le=120)
    resolution: Resolution
    aspect_ratio: AspectRatio

    @model_validator(mode="after")
    def _timeline_is_consistent(self) -> Self:
        names = [track.name for track in self.tracks]
        if len(set(names)) != len(names):
            raise ValueError("montage : deux pistes du même nom")
        if not any(track.kind is TrackKind.VIDEO for track in self.tracks):
            raise ValueError("montage sans piste vidéo")
        longest = max(track.end_s for track in self.tracks)
        if longest > self.duration_s + TIMELINE_TOLERANCE_S:
            raise ValueError(
                f"montage : une piste finit à {longest:.3f}s au-delà de la durée "
                f"déclarée {self.duration_s:.3f}s"
            )
        if not self.resolution.matches(self.aspect_ratio):
            raise ValueError(
                f"résolution {self.resolution.width}x{self.resolution.height} "
                f"incompatible avec le format {self.aspect_ratio.value}"
            )
        return self

    def track(self, name: str) -> Track:
        for track in self.tracks:
            if track.name == name:
                return track
        raise KeyError(name)


class LoudnessMeasurement(Element):
    """Mesures normalisées EBU R128."""

    integrated_lufs: float
    true_peak_dbtp: float
    loudness_range_lu: float = Field(ge=0.0)
    method: str = Field(default="ebu-r128", min_length=1)


@contract("master_artifact", "1.0.0")
class MasterArtifact(Contract):
    """Livrable final et ce qui a été vérifié dessus."""

    episode_id: str = Field(min_length=1)
    edit_timeline_id: str = Field(min_length=1)
    video_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    size_bytes: int = Field(gt=0)
    duration_s: float = Field(gt=0.0)
    resolution: Resolution
    aspect_ratio: AspectRatio
    fps: int = Field(gt=0, le=120)
    loudness: LoudnessMeasurement
    subtitles_path: str | None = None
    final_qa_report_id: str | None = None
    delivered: bool = False

    @model_validator(mode="after")
    def _delivery_is_earned(self) -> Self:
        if self.delivered and not self.final_qa_report_id:
            raise ValueError("livraison déclarée sans rapport de QA finale")
        if not self.resolution.matches(self.aspect_ratio):
            raise ValueError(
                f"résolution {self.resolution.width}x{self.resolution.height} "
                f"incompatible avec le format {self.aspect_ratio.value}"
            )
        return self
