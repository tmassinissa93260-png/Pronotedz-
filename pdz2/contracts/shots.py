"""Shot Graph : graphe temporel des plans.

Chaque plan a une raison narrative (`narrative_function`) et, dès qu'il
démontre quelque chose, l'affirmation qu'il démontre. Les contraintes de
rendu sont déclarées ici sous forme de *limites*, pas de choix de moteur :
le choix appartient au routeur de stratégie (phase 6).
"""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from pdz2.contracts.base import Contract, Element, contract
from pdz2.contracts.common import Composition, Resolution, TextOverlay, Transition
from pdz2.contracts.enums import AudioEventKind, NarrativeFunction
from pdz2.contracts.motion import MotionDescriptor

__all__ = [
    "AudioEvent",
    "RenderConstraints",
    "ShotSpec",
    "ShotEdge",
    "ShotGraph",
]

DURATION_TOLERANCE_S = 0.05
"""Tolérance de recollement des durées, en secondes."""


class AudioEvent(Element):
    kind: AudioEventKind
    at_s: float = Field(ge=0.0)
    duration_s: float = Field(gt=0.0)
    gain_db: float = Field(default=0.0, ge=-60.0, le=12.0)
    hint: str = ""


class RenderConstraints(Element):
    """Limites que l'exécution doit respecter. Aucun fournisseur nommé."""

    max_cost_usd: float | None = Field(default=None, ge=0.0)
    min_resolution: Resolution | None = None
    requires_identity_lock: bool = False
    allow_ai_video: bool = True
    max_attempts: int = Field(default=2, ge=1, le=10)
    deterministic_only: bool = False
    """Vrai : seuls les rendus reproductibles bit à bit sont autorisés."""

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        if self.deterministic_only and self.allow_ai_video:
            raise ValueError(
                "deterministic_only exclut la génération vidéo par IA : "
                "poser allow_ai_video=false"
            )
        return self


@contract("shot_spec", "1.0.0")
class ShotSpec(Contract):
    shot_id: str = Field(min_length=1)
    """Identifiant lisible dans l'épisode, par exemple 'S03'."""

    duration_s: float = Field(gt=0.0)
    narrative_function: NarrativeFunction
    claim_id: str | None = None
    evidence_required: str | None = None
    visual_subject: str = Field(min_length=1)
    composition: Composition
    camera_program_id: str = Field(min_length=1)
    subject_motion: MotionDescriptor = Field(default_factory=MotionDescriptor)
    environment_motion: MotionDescriptor = Field(default_factory=MotionDescriptor)
    transition_in: Transition = Field(default_factory=Transition)
    transition_out: Transition = Field(default_factory=Transition)
    audio_events: list[AudioEvent] = Field(default_factory=list)
    text_overlay: TextOverlay | None = None
    continuity_dependencies: list[str] = Field(default_factory=list)
    """Identifiants d'ancres qui doivent rester identiques dans ce plan."""

    render_constraints: RenderConstraints = Field(default_factory=RenderConstraints)

    @model_validator(mode="after")
    def _events_fit_inside_the_shot(self) -> Self:
        span = self.duration_s + DURATION_TOLERANCE_S
        for event in self.audio_events:
            if event.at_s + event.duration_s > span:
                raise ValueError(
                    f"{self.shot_id} : évènement audio {event.kind.value} hors du plan"
                )
        if self.text_overlay is not None:
            overlay = self.text_overlay
            if overlay.at_s + overlay.duration_s > span:
                raise ValueError(f"{self.shot_id} : incrustation hors du plan")
        total_transitions = self.transition_in.duration_s + self.transition_out.duration_s
        if total_transitions > self.duration_s:
            raise ValueError(
                f"{self.shot_id} : transitions ({total_transitions}s) plus longues "
                f"que le plan ({self.duration_s}s)"
            )
        return self

    @model_validator(mode="after")
    def _a_demonstration_shot_demonstrates(self) -> Self:
        demonstrative = {NarrativeFunction.EVIDENCE, NarrativeFunction.MECHANISM}
        if self.narrative_function in demonstrative:
            if not self.claim_id:
                raise ValueError(
                    f"{self.shot_id} : plan {self.narrative_function.value} sans claim_id"
                )
            if not (self.evidence_required or "").strip():
                raise ValueError(
                    f"{self.shot_id} : plan {self.narrative_function.value} sans "
                    "evidence_required — que doit-on voir pour être convaincu ?"
                )
        return self


class ShotEdge(Element):
    from_shot_id: str = Field(min_length=1)
    to_shot_id: str = Field(min_length=1)
    carried_anchor_ids: list[str] = Field(default_factory=list)
    """Ancres qui doivent survivre à la coupe."""

    @model_validator(mode="after")
    def _no_self_loop(self) -> Self:
        if self.from_shot_id == self.to_shot_id:
            raise ValueError("arête de montage réflexive")
        return self


@contract("shot_graph", "1.0.0")
class ShotGraph(Contract):
    director_state_id: str = Field(min_length=1)
    voice_timeline_id: str = Field(min_length=1)
    """La timeline mesurée dont ce découpage dérive (règle VOICE FIRST)."""

    visual_bible_id: str = Field(min_length=1)
    shots: list[ShotSpec] = Field(min_length=1)
    edges: list[ShotEdge] = Field(default_factory=list)
    total_duration_s: float = Field(gt=0.0)

    @model_validator(mode="after")
    def _graph_is_a_valid_sequence(self) -> Self:
        ids = [shot.shot_id for shot in self.shots]
        if len(set(ids)) != len(ids):
            raise ValueError("shot graph : shot_id en double")
        known = set(ids)
        for edge in self.edges:
            for endpoint in (edge.from_shot_id, edge.to_shot_id):
                if endpoint not in known:
                    raise ValueError(f"shot graph : arête vers un plan inconnu {endpoint!r}")
        total = sum(shot.duration_s for shot in self.shots)
        if abs(total - self.total_duration_s) > DURATION_TOLERANCE_S:
            raise ValueError(
                f"shot graph : somme des plans {total:.3f}s "
                f"contre total déclaré {self.total_duration_s:.3f}s"
            )
        return self

    @model_validator(mode="after")
    def _continuity_is_carried(self) -> Self:
        by_id = {shot.shot_id: shot for shot in self.shots}
        for edge in self.edges:
            downstream = by_id[edge.to_shot_id]
            missing = [
                anchor
                for anchor in edge.carried_anchor_ids
                if anchor not in downstream.continuity_dependencies
            ]
            if missing:
                raise ValueError(
                    f"continuité rompue vers {edge.to_shot_id} : "
                    f"ancres transportées mais non déclarées {missing}"
                )
        return self

    def shots_for_claim(self, claim_id: str) -> list[ShotSpec]:
        """Plans qui démontrent une affirmation. Le lien est dans les données."""
        return [shot for shot in self.shots if shot.claim_id == claim_id]

    def demonstrated_claim_ids(self) -> list[str]:
        seen: list[str] = []
        for shot in self.shots:
            if shot.claim_id and shot.claim_id not in seen:
                seen.append(shot.claim_id)
        return seen

    def shot(self, shot_id: str) -> ShotSpec:
        for shot in self.shots:
            if shot.shot_id == shot_id:
                return shot
        raise KeyError(shot_id)
