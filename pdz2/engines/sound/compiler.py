"""Compilation sonore : des évènements de plan aux repères de l'épisode.

Le compilateur ne décide aucun son. La grammaire de plans a déjà tranché — un
impact sur la chute, un souffle sur une opposition, une ambiance quand le
mouvement le porte — et ces décisions dorment dans `ShotSpec.audio_events`.

Ici, trois choses seulement :

    placer   l'instant du plan devient un instant de l'épisode
    résoudre une bibliothèque est interrogée pour chaque repère
    déclarer ce qui n'a pas de source le dit, avec sa raison

Le troisième point est le seul qui compte dans cet environnement, puisque
aucune bibliothèque n'y est branchée. Le compilateur ne synthétise rien : un
bruit fabriqué à la volée serait un son, pas une conception sonore.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pdz2.audio.library import NO_SOUND_LIBRARIES, SoundLibrary
from pdz2.contracts.shots import ShotGraph
from pdz2.contracts.sound import AudioCue, AudioDesign, CueState
from pdz2.contracts.temporal import TemporalPlan

__all__ = ["SoundCompiler", "SoundOutcome", "SoundRejected"]


class SoundRejected(ValueError):
    """La conception sonore ne peut pas être compilée. La raison est nommée."""


@dataclass
class SoundOutcome:
    design: AudioDesign
    notes: list[str] = field(default_factory=list)


@dataclass
class SoundCompiler:
    """Place les repères sonores, et dit lesquels resteront muets."""

    libraries: tuple[SoundLibrary, ...] = NO_SOUND_LIBRARIES

    def compile(
        self, *, episode_id: str, shot_graph: ShotGraph, temporal_plan: TemporalPlan
    ) -> SoundOutcome:
        creneaux = {slot.shot_id: slot for slot in temporal_plan.slots}
        joignables = [
            bibliotheque
            for bibliotheque in self.libraries
            if bibliotheque.get_capabilities().usable
        ]
        cues: list[AudioCue] = []

        for shot in shot_graph.shots:
            creneau = creneaux.get(shot.shot_id)
            if creneau is None:
                raise SoundRejected(
                    f"{shot.shot_id} : aucun créneau temporel, le repère sonore "
                    "n'a pas d'instant où exister"
                )
            for event in shot.audio_events:
                cues.append(
                    self._place(shot.shot_id, event, creneau, joignables,
                                temporal_plan.total_duration_s)
                )

        design = AudioDesign(
            episode_id=episode_id,
            shot_graph_id=shot_graph.id,
            total_duration_s=temporal_plan.total_duration_s,
            cues=cues,
            library=", ".join(b.name for b in joignables),
            parent_id=shot_graph.id,
        )
        return SoundOutcome(design=design, notes=self._notes(design, joignables))

    # ------------------------------------------------------------- placement

    def _place(self, shot_id, event, creneau, joignables, total_s) -> AudioCue:
        debut = round(creneau.start_s + event.at_s, 6)
        duree = round(min(event.duration_s, max(0.001, total_s - debut)), 6)
        if duree <= 0.0:
            return AudioCue(
                shot_id=shot_id,
                kind=event.kind,
                timeline_at_s=min(debut, total_s - 0.001),
                duration_s=0.001,
                gain_db=event.gain_db,
                hint=event.hint,
                state=CueState.REFUSED,
                detail="le repère tombe après la fin de l'épisode",
            )

        for bibliotheque in joignables:
            chemin = bibliotheque.resolve(event.kind, duree)
            if chemin is not None:
                return AudioCue(
                    shot_id=shot_id,
                    kind=event.kind,
                    timeline_at_s=debut,
                    duration_s=duree,
                    gain_db=event.gain_db,
                    hint=event.hint,
                    state=CueState.RESOLVED,
                    source_path=str(chemin),
                )

        return AudioCue(
            shot_id=shot_id,
            kind=event.kind,
            timeline_at_s=debut,
            duration_s=duree,
            gain_db=event.gain_db,
            hint=event.hint,
            state=CueState.UNRESOLVED,
            detail=(
                "aucune bibliothèque sonore branchée"
                if not joignables
                else "aucune bibliothèque ne propose ce son"
            ),
        )

    @staticmethod
    def _notes(design: AudioDesign, joignables) -> list[str]:
        notes = [
            f"{len(design.cues)} repère(s) sonore(s) placés sur "
            f"{design.total_duration_s:.2f}s",
            f"{len(design.resolved)} résolu(s), {len(design.unresolved)} sans source",
        ]
        if not joignables:
            notes.append(
                "aucune bibliothèque sonore n'est branchée dans cet "
                "environnement : l'épisode sortira sans habillage sonore, et "
                "chaque repère décidé le déclare plutôt que de disparaître"
            )
        return notes
