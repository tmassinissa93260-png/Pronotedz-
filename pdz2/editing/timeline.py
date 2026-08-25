"""Compilation de la timeline de montage.

Le montage n'invente rien : il pose bout à bout les plans rendus, dans l'ordre
du `ShotGraph`, aux instants du `TemporalPlan`, et ajoute la voix mesurée sur
sa propre piste.

Les durées viennent de deux sources et d'une seule vérité : la `VoiceTimeline`
mesurée en phase 2, dont le découpage de la phase 3 dérive. Le montage
vérifie que les deux concordent et refuse si elles divergent — un montage bâti
sur deux vérités temporelles produit un décalage qu'on ne rattrape plus.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pdz2.contracts.delivery import Clip, EditTimeline, Track, TrackKind
from pdz2.contracts.enums import ArtifactKind, AspectRatio
from pdz2.contracts.render import RenderArtifact
from pdz2.contracts.script import VoiceTimeline
from pdz2.contracts.shots import ShotGraph
from pdz2.contracts.temporal import TemporalPlan

__all__ = ["EditCompiler", "EditOutcome", "EditRejected", "SYNC_TOLERANCE_S"]

SYNC_TOLERANCE_S = 0.05
"""Écart toléré entre la durée du découpage et celle de la voix mesurée."""


class EditRejected(ValueError):
    """Le montage ne peut pas être composé sans trahir une durée."""


@dataclass
class EditOutcome:
    timeline: EditTimeline
    notes: list[str] = field(default_factory=list)


@dataclass
class EditCompiler:
    fps: int = 30

    def compile(
        self,
        *,
        episode_id: str,
        shot_graph: ShotGraph,
        temporal_plan: TemporalPlan,
        voice_timeline: VoiceTimeline,
        video_artifacts: list[RenderArtifact],
        voice_artifact_path: str,
        aspect_ratio: AspectRatio,
    ) -> EditOutcome:
        self._check_lineage(shot_graph, temporal_plan, voice_timeline)

        by_shot = {
            artifact.shot_id: artifact
            for artifact in video_artifacts
            if artifact.kind is ArtifactKind.VIDEO and artifact.shot_id
        }
        video_clips: list[Clip] = []
        for slot in temporal_plan.slots:
            artifact = by_shot.get(slot.shot_id)
            if artifact is None:
                raise EditRejected(
                    f"{slot.shot_id} : aucun rendu vidéo — le montage aurait un trou"
                )
            rendered = artifact.duration_s or 0.0
            if abs(rendered - slot.duration_s) > SYNC_TOLERANCE_S:
                raise EditRejected(
                    f"{slot.shot_id} : rendu de {rendered:.3f}s pour un créneau de "
                    f"{slot.duration_s:.3f}s — le montage dériverait de "
                    f"{abs(rendered - slot.duration_s) * 1000:.0f} ms"
                )
            video_clips.append(
                Clip(
                    artifact_id=artifact.id,
                    source_in_s=0.0,
                    source_out_s=round(slot.duration_s, 6),
                    timeline_in_s=round(slot.start_s, 6),
                    timeline_out_s=round(slot.end_s, 6),
                    shot_id=slot.shot_id,
                )
            )

        duration = temporal_plan.total_duration_s
        if abs(voice_timeline.total_duration_s - duration) > SYNC_TOLERANCE_S:
            raise EditRejected(
                f"la voix dure {voice_timeline.total_duration_s:.3f}s et le "
                f"découpage {duration:.3f}s : deux vérités temporelles"
            )

        resolution = video_artifacts[0].resolution
        if resolution is None:
            raise EditRejected("le premier rendu ne déclare pas sa résolution")

        timeline = EditTimeline(
            episode_id=episode_id,
            shot_graph_id=shot_graph.id,
            tracks=[
                Track(kind=TrackKind.VIDEO, name="v1", clips=video_clips),
                Track(
                    kind=TrackKind.VOICE,
                    name="a1",
                    clips=[
                        Clip(
                            artifact_id=voice_artifact_path,
                            source_in_s=0.0,
                            source_out_s=round(voice_timeline.total_duration_s, 6),
                            timeline_in_s=0.0,
                            timeline_out_s=round(
                                voice_timeline.total_duration_s, 6
                            ),
                        )
                    ],
                ),
            ],
            duration_s=round(duration, 6),
            fps=self.fps,
            resolution=resolution,
            aspect_ratio=aspect_ratio,
            parent_id=shot_graph.id,
        )
        return EditOutcome(
            timeline=timeline,
            notes=[
                f"{len(video_clips)} clips vidéo bout à bout sur {duration:.3f}s",
                f"voix mesurée de {voice_timeline.total_duration_s:.3f}s sur sa piste",
                f"{resolution.width}×{resolution.height} à {self.fps} i/s",
            ],
        )

    @staticmethod
    def _check_lineage(shot_graph, temporal_plan, voice_timeline) -> None:
        if temporal_plan.voice_timeline_id != voice_timeline.id:
            raise EditRejected(
                "le découpage ne dérive pas de cette timeline de voix"
            )
        if shot_graph.voice_timeline_id != voice_timeline.id:
            raise EditRejected(
                "le shot graph ne dérive pas de cette timeline de voix"
            )
