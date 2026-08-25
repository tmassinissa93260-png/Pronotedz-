"""Aiguillage d'exécution : de la stratégie retenue au moteur qui l'exécute.

Le §18 sépare trois décisions que rien ne doit confondre :

    STRATEGY   décide COMMENT produire le plan
    PROVIDER   décide AVEC QUEL MOTEUR l'exécuter
    RENDERER   exécute

Sans cette couche, la chaîne appelait le renderer local en dur. Le port
`VideoProvider` existait, personne ne l'empruntait : un plan routé vers une
stratégie générative aurait été refusé à l'exécution, et la seule manière de
produire une vidéo passait par un unique moteur. C'est précisément ce qu'un
compilateur ne doit pas être — un enrobage autour d'un exécutant.

L'aiguilleur ne choisit pas la stratégie : elle est déjà décidée, déclarée et
validée en amont. Il choisit **l'exécutant** de cette stratégie, et il rend
compte de tout écart.

Ce qu'il garantit :

* un plan génératif part chez un fournisseur qui déclare savoir le faire ;
* un plan local part chez le renderer déterministe, sans fournisseur ;
* un fournisseur qui échoue **ne provoque aucune reprise à l'aveugle** : la
  panne est nommée, l'écart déclaré, et le plan retombe sur ce qui s'exécute
  réellement ici ;
* la livraison reste possible sans le moindre fournisseur.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from pdz2.contracts.enums import ArtifactKind
from pdz2.contracts.motion import MotionProgram
from pdz2.contracts.render import (
    Degradation,
    DegradationSeverity,
    ExecutionPlan,
    RenderArtifact,
    RenderSpecExecutable,
    RenderStrategy,
)
from pdz2.contracts.visual import Typography
from pdz2.engines.imagery.renderer import RenderedImage
from pdz2.engines.routing.router import STRATEGY_LADDER
from pdz2.providers.video import (
    ProviderUnavailable,
    VideoJob,
    VideoProvider,
)
from pdz2.renderers.deterministic import (
    SUPPORTED_STRATEGIES,
    DeterministicRenderer,
)
from pdz2.renderers.ffmpeg import probe_video

__all__ = [
    "ExecutionDispatcher",
    "ExecutionOutcome",
    "Dispatch",
    "Executor",
    "DispatchRejected",
]


class Executor(str, Enum):
    """Qui a réellement produit le fichier."""

    PROVIDER = "provider"
    LOCAL = "local"


class DispatchRejected(RuntimeError):
    """Aucun exécutant ne peut produire ce plan, pas même un repli."""


@dataclass(frozen=True)
class Dispatch:
    """À qui un plan a été confié, et pourquoi."""

    shot_id: str
    strategy: RenderStrategy
    executor: Executor
    provider: str | None
    detail: str


@dataclass
class ExecutionOutcome:
    artifacts: list[RenderArtifact] = field(default_factory=list)
    dispatches: list[Dispatch] = field(default_factory=list)
    degradations: list[Degradation] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def for_shot(self, shot_id: str) -> Dispatch:
        for dispatch in self.dispatches:
            if dispatch.shot_id == shot_id:
                return dispatch
        raise KeyError(shot_id)

    @property
    def by_executor(self) -> dict[Executor, int]:
        counts: dict[Executor, int] = {}
        for dispatch in self.dispatches:
            counts[dispatch.executor] = counts.get(dispatch.executor, 0) + 1
        return counts


def _local_fallback(strategy: RenderStrategy) -> RenderStrategy:
    """La stratégie locale la plus proche en deçà du barreau demandé.

    Redescendre l'échelle plutôt que sauter à `STILL` : un plan génératif
    perdu vaut mieux en procédural qu'en image fixe, et l'écart déclaré dit
    exactement de combien on est descendu.
    """
    locales = [s for s in STRATEGY_LADDER if s in SUPPORTED_STRATEGIES]
    if strategy in STRATEGY_LADDER:
        rang = STRATEGY_LADDER.index(strategy)
        en_dessous = [s for s in locales if STRATEGY_LADDER.index(s) < rang]
        if en_dessous:
            return en_dessous[-1]
    return RenderStrategy.STILL


def _budgets(plan: ExecutionPlan | None) -> dict[str, int]:
    """Budget de tentatives par exécutable, tel que le plan le déclare.

    Le plan d'exécution était produit, validé, persisté — et relu par
    personne. Ses `retry_budget` et son ordonnancement ne gouvernaient rien,
    pendant que l'aiguilleur appliquait sa propre politique en dur. Un contrat
    que personne ne relit n'est pas une frontière.
    """
    if plan is None:
        return {}
    return {
        step.spec_id: step.retry_budget
        for step in plan.steps
        if step.spec_id is not None
    }


def _ce_qui_est_perdu(demande: RenderStrategy, repli: RenderStrategy) -> str:
    """Nomme précisément l'élément perdu, plutôt qu'un « rendu localement ».

    Un plan hybride ne perd pas tout : son fond procédural, sa caméra 2.5D et
    ses incrustations s'exécutent réellement en local. Ce qu'il perd, c'est le
    sujet généré — et le dire précisément vaut mieux que laisser croire que le
    plan entier a été remplacé.
    """
    commun = (
        "la livraison ne dépend d'aucun fournisseur ; fond procédural, caméra "
        "2.5D et incrustations sont rendus localement"
    )
    if demande is RenderStrategy.HYBRID:
        return (
            f"sujet généré non exécuté, reste du plan rendu en {repli.value} : "
            + commun
        )
    return f"plan entièrement rendu en {repli.value} : " + commun


@dataclass
class ExecutionDispatcher:
    """Confie chaque plan à l'exécutant que sa stratégie appelle."""

    renderer: DeterministicRenderer = field(default_factory=DeterministicRenderer)
    providers: tuple[VideoProvider, ...] = ()

    def execute(
        self,
        *,
        executables: list[RenderSpecExecutable],
        motion_programs: list[MotionProgram],
        images: list[RenderedImage],
        into: Path,
        plan: ExecutionPlan | None = None,
        typography: Typography | None = None,
    ) -> ExecutionOutcome:
        """Exécute les plans, en suivant le plan d'exécution s'il est fourni.

        `plan` porte, par plan de tournage, un budget de tentatives et un
        délai. Sans lui, l'aiguilleur s'en tient à une tentative : c'est le
        choix le plus prudent, jamais une reprise inventée.
        """
        outcome = ExecutionOutcome()
        budgets = _budgets(plan)
        par_image = {image.shot_id: image for image in images}
        a_rendre_localement: list[RenderSpecExecutable] = []

        for executable in executables:
            fournisseur = self._provider_for(executable)
            if fournisseur is None:
                a_rendre_localement.append(executable)
                outcome.dispatches.append(
                    Dispatch(
                        shot_id=executable.shot_id,
                        strategy=executable.strategy,
                        executor=Executor.LOCAL,
                        provider=None,
                        detail=f"stratégie locale « {executable.strategy.value} »",
                    )
                )
                continue

            image = par_image.get(executable.shot_id)
            if image is None:
                raise DispatchRejected(
                    f"{executable.shot_id} : aucune image de départ pour un plan génératif"
                )
            rendu = self._try_provider(
                executable,
                fournisseur,
                image,
                into,
                outcome,
                budget=budgets.get(executable.id, 1),
            )
            if rendu is None:
                a_rendre_localement.append(self._degrade(executable, outcome))

        if a_rendre_localement:
            local = self.renderer.render(
                typography=typography,
                executables=a_rendre_localement,
                motion_programs=motion_programs,
                images=[
                    par_image[e.shot_id]
                    for e in a_rendre_localement
                    if e.shot_id in par_image
                ],
                into=into,
            )
            outcome.artifacts.extend(local.artifacts)
            outcome.notes.extend(local.notes)

        outcome.notes.insert(
            0,
            "exécution : "
            + ", ".join(
                f"{compte} plan(s) {executor.value}"
                for executor, compte in sorted(
                    outcome.by_executor.items(), key=lambda kv: kv[0].value
                )
            ),
        )
        return outcome

    # ------------------------------------------------------------- aiguillage

    def _provider_for(
        self, executable: RenderSpecExecutable
    ) -> VideoProvider | None:
        """Le fournisseur qui exécutera ce plan, ou `None` s'il est local.

        Le nom porté par l'exécutable fait foi : c'est le routeur qui l'a
        inscrit, après avoir vérifié la capacité mesurée. L'aiguilleur ne
        rechoisit pas — il retrouve.
        """
        if executable.strategy in SUPPORTED_STRATEGIES:
            return None
        for provider in self.providers:
            if executable.provider and provider.name != executable.provider:
                continue
            if provider.get_capabilities().usable:
                return provider
        return None

    def _try_provider(
        self,
        executable: RenderSpecExecutable,
        provider: VideoProvider,
        image: RenderedImage,
        into: Path,
        outcome: ExecutionOutcome,
        budget: int = 1,
    ) -> RenderArtifact | None:
        """Tente, dans la limite du budget **déclaré** par le plan d'exécution.

        Ce n'est pas une reprise à l'aveugle : le nombre de tentatives vient
        d'un contrat validé en amont, il est borné, et chaque échec est nommé.
        Par défaut le budget vaut 1 — on ne rejoue rien que personne n'a
        autorisé.
        """
        into.mkdir(parents=True, exist_ok=True)
        debut = time.monotonic()
        resultat = None
        aboutie = 1
        for tentative in range(1, max(1, budget) + 1):
            aboutie = tentative
            try:
                resultat = provider.generate(
                    VideoJob(
                        executable=executable,
                        start_image=image.composite_path,
                        reference_images=tuple(
                            image.layer_paths[role] for role in sorted(
                                image.layer_paths, key=lambda r: r.value
                            )
                        ),
                    )
                )
                break
            except (ProviderUnavailable, OSError) as panne:
                outcome.notes.append(
                    f"{executable.shot_id} : {provider.name} a échoué "
                    f"(tentative {tentative}/{max(1, budget)}) — {panne}"
                )
        if resultat is None:
            return None

        chemin = Path(resultat.path)
        if not chemin.is_file():
            outcome.notes.append(
                f"{executable.shot_id} : {provider.name} n'a écrit aucun fichier"
            )
            return None

        sonde = probe_video(chemin)
        artefact = RenderArtifact(
            kind=ArtifactKind.VIDEO,
            path=chemin.name,
            sha256=hashlib.sha256(chemin.read_bytes()).hexdigest(),
            size_bytes=sonde.size_bytes,
            duration_s=round(sonde.duration_s, 6),
            resolution=executable.resolution,
            fps=int(round(sonde.fps)) or executable.fps,
            provider=resultat.provider,
            model=resultat.model,
            source_contract_id=executable.id,
            executable_spec_id=executable.id,
            shot_id=executable.shot_id,
            actual_cost_usd=resultat.cost_usd,
            attempt=aboutie,
            latency_s=round(resultat.latency_s or (time.monotonic() - debut), 4),
            parent_id=executable.id,
        )
        outcome.artifacts.append(artefact)
        outcome.dispatches.append(
            Dispatch(
                shot_id=executable.shot_id,
                strategy=executable.strategy,
                executor=Executor.PROVIDER,
                provider=resultat.provider,
                detail=f"{resultat.provider}/{resultat.model}",
            )
        )
        return artefact

    def _degrade(
        self, executable: RenderSpecExecutable, outcome: ExecutionOutcome
    ) -> RenderSpecExecutable:
        """Redescend un plan génératif sur ce qui s'exécute réellement ici.

        L'écart est porté par un nouveau contrat, pas par une mutation : le
        contrat d'origine reste lisible tel qu'il a été validé, et sa
        descendance dit ce qui a réellement été fait.
        """
        repli = _local_fallback(executable.strategy)
        ecart = Degradation(
            field="provider_availability",
            requested=executable.strategy.value,
            executed=repli.value,
            reason=(
                f"aucun fournisseur n'a exécuté ce plan à l'exécution "
                f"({executable.provider or 'aucun fournisseur nommé'})"
            ),
            description=_ce_qui_est_perdu(executable.strategy, repli),
            severity=DegradationSeverity.PERCEPTUAL,
        )
        outcome.degradations.append(ecart)
        outcome.dispatches.append(
            Dispatch(
                shot_id=executable.shot_id,
                strategy=repli,
                executor=Executor.LOCAL,
                provider=None,
                detail=f"repli local après échec de {executable.provider or 'la génération'}",
            )
        )
        return executable.derive(
            strategy=repli,
            provider=None,
            model=None,
            estimated_cost_usd=0.0,
            degradations=[*executable.degradations, ecart],
        )
