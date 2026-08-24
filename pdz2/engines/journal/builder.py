"""Construction du journal de production, à partir du dossier d'épisode.

Le journal se **relit** depuis les artefacts, il ne s'écrit pas au fil de
l'eau. La raison est simple : un journal tenu à la main diverge de ce qui
s'est réellement passé dès la première reprise. Reconstruit depuis les
contrats, il ne peut pas mentir — s'il dit qu'une dégradation a eu lieu, c'est
qu'elle est dans un contrat sur le disque.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from pdz2.contracts.capability import ProviderCapability
from pdz2.contracts.journal import (
    JournalEntry,
    JournalEntryKind,
    ProductionJournal,
)
from pdz2.contracts.versioning import registry
from pdz2.storage import EpisodeStore

__all__ = ["JournalBuilder", "JournalOutcome"]


@dataclass
class JournalOutcome:
    journal: ProductionJournal
    notes: list[str] = field(default_factory=list)


@dataclass
class JournalBuilder:
    """Relit un dossier d'épisode et en tire un récit vérifiable."""

    def build(
        self,
        *,
        store: EpisodeStore,
        capabilities: list[ProviderCapability] | None = None,
        tool_versions: list[str] | None = None,
    ) -> JournalOutcome:
        snapshot = store.load_snapshot()
        request = store.load_as(
            registry.get("topic_request")  # type: ignore[arg-type]
        )
        entries: list[JournalEntry] = []

        entries += self._decisions(store)
        entries += self._degradations(store)
        entries += self._findings(store)
        entries += self._refusals(store, snapshot)
        entries += self._spend(snapshot)
        entries += self._limitations(store)
        entries += self._duree_commandee(store, request)
        for capability in capabilities or []:
            entries.append(
                JournalEntry(
                    kind=JournalEntryKind.CAPABILITY,
                    at=capability.measured_at or datetime.now(UTC),
                    subject_id=capability.provider,
                    summary=f"{capability.provider} : {capability.state.value}",
                    detail=capability.detail,
                )
            )

        entries.sort(key=lambda entry: entry.at)
        started = (
            snapshot.transitions[0].at if snapshot.transitions else snapshot.created_at
        )
        ended = snapshot.transitions[-1].at if snapshot.transitions else None

        journal = ProductionJournal(
            episode_id=snapshot.episode_id,
            topic=request.topic,
            episode_status=snapshot.episode_status,
            started_at=started,
            ended_at=ended,
            entries=entries,
            transitions=list(snapshot.transitions),
            capabilities=list(capabilities or []),
            total_spent_usd=snapshot.spent_usd,
            contract_versions=[
                f"{contract_type.CONTRACT_NAME}@{contract_type.CONTRACT_VERSION}"
                for contract_type in registry.types()
            ],
            tool_versions=list(tool_versions or []),
            parent_id=snapshot.id,
        )
        return JournalOutcome(
            journal=journal,
            notes=[
                f"{len(entries)} entrées reconstruites depuis les contrats",
                f"{len(snapshot.transitions)} transitions d'état",
                f"{len(journal.unresolved)} point(s) non résolu(s) à lire avant "
                "de publier",
            ],
        )

    # ------------------------------------------------------------- collectes

    @staticmethod
    def _decisions(store: EpisodeStore) -> list[JournalEntry]:
        entries: list[JournalEntry] = []
        if store.exists("director_brief"):
            brief = store.load("director_brief")
            entries.append(
                JournalEntry(
                    kind=JournalEntryKind.DECISION,
                    at=brief.created_at,
                    stage="direction",
                    subject_id=brief.id,
                    summary=f"brief de réalisation par {brief.author}",
                    detail=f"thèse : {brief.thesis}",
                )
            )
            if brief.visual_style is None:
                entries.append(
                    JournalEntry(
                        kind=JournalEntryKind.LIMITATION,
                        at=brief.created_at,
                        stage="visual_bible",
                        subject_id=brief.id,
                        summary="style visuel non décidé",
                        detail=(
                            "un préréglage déclaré a été appliqué selon le ton : "
                            "l'épisode n'a pas de parti pris qui lui soit propre"
                        ),
                    )
                )
        for executable in store.load_collection("render_spec_executable"):
            entries.append(
                JournalEntry(
                    kind=JournalEntryKind.DECISION,
                    at=executable.created_at,
                    stage="routing",
                    subject_id=executable.shot_id,
                    summary=f"stratégie « {executable.strategy.value} »",
                    detail=f"caméra {executable.execution_camera.value}",
                )
            )
        return entries

    @staticmethod
    def _degradations(store: EpisodeStore) -> list[JournalEntry]:
        entries: list[JournalEntry] = []
        for executable in store.load_collection("render_spec_executable"):
            for degradation in executable.degradations:
                entries.append(
                    JournalEntry(
                        kind=JournalEntryKind.DEGRADATION,
                        at=executable.created_at,
                        stage="routing",
                        subject_id=executable.shot_id,
                        summary=(
                            f"[{degradation.severity.value}] {degradation.field} : "
                            f"{degradation.requested} → {degradation.executed}"
                        ),
                        detail=f"{degradation.reason} ; {degradation.description}",
                    )
                )
        return entries

    @staticmethod
    def _findings(store: EpisodeStore) -> list[JournalEntry]:
        entries: list[JournalEntry] = []
        if store.exists("temporal_plan"):
            plan = store.load("temporal_plan")
            for finding in plan.findings:
                entries.append(
                    JournalEntry(
                        kind=JournalEntryKind.FINDING,
                        at=plan.created_at,
                        stage="shot_graph",
                        subject_id=finding.shot_id or "",
                        summary=f"rythme : {finding.kind.value}",
                        detail=finding.detail,
                    )
                )
        for report in store.load_collection("observation_report"):
            for check in report.checks:
                if check.passed:
                    continue
                entries.append(
                    JournalEntry(
                        kind=JournalEntryKind.FINDING,
                        at=report.created_at,
                        stage="observation",
                        subject_id=report.shot_id or "",
                        summary=f"contrôle en échec : {check.check_id}",
                        detail=(
                            f"observé {check.observed}, attendu {check.expected}"
                            f" — {check.detail}"
                        ),
                    )
                )
        return entries

    @staticmethod
    def _refusals(store: EpisodeStore, snapshot) -> list[JournalEntry]:
        entries: list[JournalEntry] = []
        if store.exists("validation_report"):
            report = store.load("validation_report")
            for issue in report.issues:
                entries.append(
                    JournalEntry(
                        kind=JournalEntryKind.REFUSAL
                        if issue.severity.value == "blocking"
                        else JournalEntryKind.FINDING,
                        at=report.created_at,
                        stage="static_validation",
                        subject_id=issue.subject_id,
                        summary=f"{issue.rule.value} [{issue.severity.value}]",
                        detail=issue.detail,
                    )
                )
        for transition in snapshot.transitions:
            if transition.to_status.value == "failed":
                entries.append(
                    JournalEntry(
                        kind=JournalEntryKind.REFUSAL,
                        at=transition.at,
                        stage=transition.stage.value,
                        summary=f"étape en échec : {transition.stage.value}",
                        detail=transition.reason,
                    )
                )
            elif transition.to_status.value == "skipped":
                entries.append(
                    JournalEntry(
                        kind=JournalEntryKind.DECISION,
                        at=transition.at,
                        stage=transition.stage.value,
                        summary=f"étape sautée : {transition.stage.value}",
                        detail=transition.reason,
                    )
                )
        return entries

    @staticmethod
    def _spend(snapshot) -> list[JournalEntry]:
        return [
            JournalEntry(
                kind=JournalEntryKind.SPEND,
                at=transition.at,
                stage=transition.stage.value,
                summary=f"{transition.cost_usd:.4f} USD",
                detail=transition.reason,
            )
            for transition in snapshot.transitions
            if transition.cost_usd > 0
        ]

    @staticmethod
    def _duree_commandee(store: EpisodeStore, request) -> list[JournalEntry]:
        """La durée livrée tient-elle la commande ?

        La durée officielle vient de la voix mesurée, et elle est juste — ce
        n'est pas elle qu'on met en doute. Ce qui se perdait, c'est que la
        **commande** ne soit pas tenue : un épisode de 27 s pour 40 s
        demandées est un autre objet éditorial, et rien ne le disait une fois
        le MP4 écrit.
        """
        if not store.exists("voice_timeline") or not request.target_duration_s:
            return []
        timeline = store.load("voice_timeline")
        cible = request.target_duration_s
        mesuree = timeline.total_duration_s
        ecart = (mesuree - cible) / cible
        if abs(ecart) < 0.15:
            return []
        sens = "au-dessus" if ecart > 0 else "en dessous"
        return [
            JournalEntry(
                kind=JournalEntryKind.FINDING,
                at=timeline.created_at,
                stage="timeline",
                subject_id=timeline.id,
                summary=(
                    f"durée commandée non tenue : {mesuree:.1f}s pour {cible:.0f}s"
                ),
                detail=(
                    f"{abs(ecart) * 100:.0f} % {sens} de la commande. La durée "
                    "mesurée est exacte ; c'est le script qui n'a pas la "
                    "longueur demandée. Sans raisonneur branché, le script est "
                    "assemblé à partir des seules affirmations du corpus : sa "
                    "longueur est bornée par celle des sources."
                ),
            )
        ]

    @staticmethod
    def _limitations(store: EpisodeStore) -> list[JournalEntry]:
        entries: list[JournalEntry] = []
        for track in store.load_collection("subtitle_track"):
            entries.append(
                JournalEntry(
                    kind=JournalEntryKind.LIMITATION,
                    at=track.created_at,
                    stage="subtitles",
                    summary="sous-titres calés au caractère, pas à la syllabe",
                    detail=(
                        "les timings de mots ne sont pas mesurés : le découpage "
                        "des cartons est proportionnel au nombre de caractères"
                    ),
                )
            )
        for timeline in store.load_collection("voice_timeline"):
            if not any(segment.words for segment in timeline.segments):
                entries.append(
                    JournalEntry(
                        kind=JournalEntryKind.LIMITATION,
                        at=timeline.created_at,
                        stage="timeline",
                        summary="aucun timing de mot mesuré",
                        detail=(
                            "le moteur de synthèse ne rend pas de marques de mot "
                            "exploitables ; rien n'est calé à la syllabe"
                        ),
                    )
                )
        return entries
