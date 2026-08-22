"""Disposition d'un dossier d'épisode.

Un épisode est un dossier lisible à la main : chaque contrat y est un JSON
nommé, et l'état de la machine y est repris tel quel. Les fichiers dont la
production relève de phases ultérieures sont déclarés ici mais ne sont pas
créés tant que l'étape correspondante n'existe pas.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["EpisodeLayout", "SINGLETON_FILES", "COLLECTION_DIRS", "MEDIA_FILES"]

SINGLETON_FILES: dict[str, str] = {
    "topic_request": "topic_request.json",
    "research_state": "research.json",
    "director_state": "director_state.json",
    "script_state": "script.json",
    "voice_timeline": "voice_timeline.json",
    "visual_bible": "visual_bible.json",
    "shot_graph": "shot_graph.json",
    "edit_timeline": "edit_timeline.json",
    "master_artifact": "master.json",
    "episode_snapshot": "state.json",
}
"""Contrats dont il n'existe qu'un exemplaire par épisode."""

COLLECTION_DIRS: dict[str, str] = {
    "render_spec_requested": "render_specs",
    "render_spec_executable": "render_specs",
    "execution_plan": "execution_plans",
    "motion_program": "motion_programs",
    "camera_program": "motion_programs",
    "image_spec": "render_specs",
    "render_artifact": "renders",
    "observation_report": "observations",
    "failure_diagnosis": "observations",
    "repair_plan": "repairs",
    "subtitle_track": "subtitles",
}
"""Contrats produits en série, un fichier par identifiant."""

MEDIA_FILES: dict[str, str] = {
    "voice": "voice.wav",
    "audio_master": "audio_master.wav",
    "final": "final.mp4",
    "production_log": "production_log.json",
}
"""Fichiers non contractuels, produits par les phases 2, 10 et 12."""


@dataclass(frozen=True)
class EpisodeLayout:
    """Chemins relatifs d'un épisode, sans toucher au disque."""

    @staticmethod
    def relative_path(contract_type: str, contract_id: str | None = None) -> str:
        if contract_type in SINGLETON_FILES:
            return SINGLETON_FILES[contract_type]
        if contract_type in COLLECTION_DIRS:
            if not contract_id:
                raise ValueError(
                    f"{contract_type} est produit en série : un identifiant est requis"
                )
            return f"{COLLECTION_DIRS[contract_type]}/{contract_id}.json"
        raise KeyError(f"aucun emplacement défini pour le contrat {contract_type!r}")

    @staticmethod
    def directories() -> tuple[str, ...]:
        return tuple(sorted(set(COLLECTION_DIRS.values()) | {"assets"}))
