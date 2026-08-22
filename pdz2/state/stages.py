"""Graphe de dépendances des étapes et garde-fous de dépense.

Le graphe encode des invariants du cahier des charges directement dans la
structure :

  * `TIMELINE` dépend de `VOICE` — la timeline officielle ne peut pas être
    construite avant que l'audio réel existe (règle VOICE FIRST) ;
  * `ASSETS` et `RENDER` sont barrés tant que `STATIC_VALIDATION` n'est pas
    franchie — aucun appel API coûteux avant validation ;
  * `EDIT` dépend de `DIAGNOSIS` et `REPAIR`, qui sont sautables avec motif :
    on ne monte jamais sans avoir explicitement statué sur l'observation.
"""

from __future__ import annotations

from dataclasses import dataclass

from pdz2.contracts.pipeline import Stage

__all__ = [
    "StageDefinition",
    "STAGE_DEFINITIONS",
    "STAGE_ORDER",
    "COST_GATE",
    "definition",
    "dependents_of",
    "transitive_dependents",
]

COST_GATE = Stage.STATIC_VALIDATION
"""Étape qui autorise la dépense de rendu."""


@dataclass(frozen=True)
class StageDefinition:
    stage: Stage
    depends_on: tuple[Stage, ...] = ()
    produces: tuple[str, ...] = ()
    """Noms de contrats que l'étape doit produire, à titre documentaire."""

    incurs_cost: bool = False
    """L'étape peut appeler un service payant."""

    gated_by_validation: bool = False
    """L'étape est interdite tant que le validateur statique n'a pas statué."""

    optional: bool = False
    """L'étape peut être sautée, avec un motif obligatoire."""

    description: str = ""


def _d(*args, **kwargs) -> StageDefinition:
    return StageDefinition(*args, **kwargs)


STAGE_DEFINITIONS: dict[Stage, StageDefinition] = {
    definition.stage: definition
    for definition in (
        _d(
            Stage.RESEARCH,
            produces=("research_state", "fact_graph", "claim", "evidence"),
            incurs_cost=True,
            description="Chercher, sourcer, pondérer, construire le Fact Graph.",
        ),
        _d(
            Stage.DIRECTION,
            depends_on=(Stage.RESEARCH,),
            produces=("director_state", "anchor_spec", "shot_intent"),
            incurs_cost=True,
            description="Décision conceptuelle unique : thèse, preuves visuelles, ancres.",
        ),
        _d(
            Stage.SCRIPT,
            depends_on=(Stage.DIRECTION,),
            produces=("script_state", "script_line"),
            incurs_cost=True,
            description="Compiler l'intention en répliques.",
        ),
        _d(
            Stage.VOICE,
            depends_on=(Stage.SCRIPT,),
            produces=("render_artifact",),
            incurs_cost=True,
            description="Synthèse vocale réelle. Produit l'audio dont tout dépend.",
        ),
        _d(
            Stage.TIMELINE,
            depends_on=(Stage.VOICE,),
            produces=("voice_timeline",),
            description="Mesurer l'audio réel et en tirer la vérité temporelle.",
        ),
        _d(
            Stage.VISUAL_BIBLE,
            depends_on=(Stage.DIRECTION,),
            produces=("visual_bible",),
            incurs_cost=True,
            description="Figer le registre visuel de l'épisode.",
        ),
        _d(
            Stage.SHOT_GRAPH,
            depends_on=(Stage.TIMELINE, Stage.VISUAL_BIBLE),
            produces=("shot_graph", "shot_spec"),
            description="Découper le temps mesuré en plans motivés.",
        ),
        _d(
            Stage.MOTION,
            depends_on=(Stage.SHOT_GRAPH,),
            produces=("motion_program", "camera_program"),
            description="Programmes de mouvement et de caméra, typés.",
        ),
        _d(
            Stage.RENDER_SPEC,
            depends_on=(Stage.SHOT_GRAPH, Stage.MOTION),
            produces=("render_spec_requested", "image_spec"),
            description="Traduire l'intention en demandes de rendu.",
        ),
        _d(
            Stage.STATIC_VALIDATION,
            depends_on=(Stage.RENDER_SPEC,),
            produces=("render_spec_executable", "execution_plan"),
            description="Refuser avant de dépenser. Barrière de coût.",
        ),
        _d(
            Stage.ROUTING,
            depends_on=(Stage.STATIC_VALIDATION,),
            produces=("execution_plan",),
            description="Choisir une stratégie de rendu par plan.",
        ),
        _d(
            Stage.ASSETS,
            depends_on=(Stage.STATIC_VALIDATION,),
            produces=("render_artifact",),
            incurs_cost=True,
            gated_by_validation=True,
            description="Générer les images de départ.",
        ),
        _d(
            Stage.RENDER,
            depends_on=(Stage.ROUTING, Stage.ASSETS),
            produces=("render_artifact",),
            incurs_cost=True,
            gated_by_validation=True,
            description="Exécuter : I2V, 2.5D, procédural, hybride.",
        ),
        _d(
            Stage.OBSERVATION,
            depends_on=(Stage.RENDER,),
            produces=("observation_report",),
            description="Mesurer ce qui est sorti. Déterministe.",
        ),
        _d(
            Stage.DIAGNOSIS,
            depends_on=(Stage.OBSERVATION,),
            produces=("failure_diagnosis",),
            optional=True,
            description="Expliquer les échecs mesurés. Sautable si tout passe.",
        ),
        _d(
            Stage.REPAIR,
            depends_on=(Stage.DIAGNOSIS,),
            produces=("repair_plan",),
            incurs_cost=True,
            gated_by_validation=True,
            optional=True,
            description="Adapter, puis rembobiner le rendu. Sautable si rien à réparer.",
        ),
        _d(
            Stage.EDIT,
            depends_on=(Stage.OBSERVATION, Stage.DIAGNOSIS, Stage.REPAIR),
            produces=("edit_timeline",),
            description="Monter. Ne démarre pas sans statuer sur l'observation.",
        ),
        _d(
            Stage.AUDIO_MASTER,
            depends_on=(Stage.EDIT,),
            produces=("render_artifact",),
            description="Mixage et normalisation de loudness.",
        ),
        _d(
            Stage.SUBTITLES,
            depends_on=(Stage.TIMELINE, Stage.EDIT),
            produces=("subtitle_track",),
            optional=True,
            description="Sous-titres calés sur la timeline mesurée.",
        ),
        _d(
            Stage.FINAL_QA,
            depends_on=(Stage.AUDIO_MASTER, Stage.SUBTITLES),
            produces=("observation_report",),
            description="Dernier contrôle avant livraison.",
        ),
        _d(
            Stage.DELIVERY,
            depends_on=(Stage.FINAL_QA,),
            produces=("master_artifact",),
            description="Sceller le master.",
        ),
    )
}


def definition(stage: Stage) -> StageDefinition:
    return STAGE_DEFINITIONS[stage]


def _topological_order() -> tuple[Stage, ...]:
    remaining = {
        stage: set(spec.depends_on) for stage, spec in STAGE_DEFINITIONS.items()
    }
    order: list[Stage] = []
    while remaining:
        ready = [stage for stage, need in remaining.items() if not need]
        if not ready:
            raise RuntimeError("graphe d'étapes cyclique")
        # Ordre stable : l'ordre de déclaration sert d'arbitrage.
        ready.sort(key=lambda stage: list(STAGE_DEFINITIONS).index(stage))
        for stage in ready:
            order.append(stage)
            del remaining[stage]
        for need in remaining.values():
            need.difference_update(ready)
    return tuple(order)


STAGE_ORDER: tuple[Stage, ...] = _topological_order()
"""Étapes triées : une dépendance précède toujours ce qui en dépend."""

_DEPENDENTS: dict[Stage, tuple[Stage, ...]] = {
    stage: tuple(
        other
        for other, spec in STAGE_DEFINITIONS.items()
        if stage in spec.depends_on
    )
    for stage in STAGE_DEFINITIONS
}


def dependents_of(stage: Stage) -> tuple[Stage, ...]:
    """Étapes qui dépendent directement de `stage`."""
    return _DEPENDENTS[stage]


def transitive_dependents(stage: Stage) -> tuple[Stage, ...]:
    """Toutes les étapes en aval, dans l'ordre topologique."""
    reached: set[Stage] = set()
    frontier = [stage]
    while frontier:
        current = frontier.pop()
        for child in _DEPENDENTS[current]:
            if child not in reached:
                reached.add(child)
                frontier.append(child)
    return tuple(item for item in STAGE_ORDER if item in reached)


# Sanité au chargement : toute dépendance doit exister, et les étapes barrées
# par le validateur doivent effectivement se trouver en aval de la barrière.
for _stage, _spec in STAGE_DEFINITIONS.items():
    for _dependency in _spec.depends_on:
        if _dependency not in STAGE_DEFINITIONS:
            raise RuntimeError(f"{_stage} dépend d'une étape inconnue {_dependency}")
    if _spec.gated_by_validation and _stage not in transitive_dependents(COST_GATE):
        raise RuntimeError(
            f"{_stage.value} est barrée par le validateur statique sans en dépendre"
        )
if set(STAGE_ORDER) != set(Stage):
    raise RuntimeError("le graphe d'étapes ne couvre pas toutes les étapes")
