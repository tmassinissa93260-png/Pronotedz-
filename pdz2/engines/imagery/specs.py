"""Compilation des `ImageSpec` : ce qu'une image doit contenir.

Une `ImageSpec` n'est pas un prompt. C'est une description structurée de ce
qui doit être à l'écran, dérivée de trois sources déjà décidées :

    ShotSpec      → le sujet, le cadrage, les ancres
    VisualBible   → le style, la lumière, la palette, les interdits
    AnchorSpec    → les traits d'identité à tenir, un par un

Le champ `intent` assemble ces éléments en une description lisible. Il est
construit par concaténation de chaînes **déjà décidées** : rien n'y est
inventé au moment de la compilation. Sa traduction en prompt appartient à
l'adaptateur qui saura quoi en faire, jamais au cœur du système.

Les calques 2.5D sont posés ici parce qu'ils dépendent du cadrage : un plan
large a un ciel et un lointain, une macro n'en a pas.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from pdz2.contracts.common import Resolution
from pdz2.contracts.direction import AnchorSpec, DirectorState
from pdz2.contracts.enums import AspectRatio, Framing
from pdz2.contracts.research import TopicRequest
from pdz2.contracts.shots import ShotGraph, ShotSpec
from pdz2.contracts.visual import ImageSpec, LayerRole, LayerSpec, VisualBible

__all__ = ["ImageSpecCompiler", "ImageSpecOutcome", "RESOLUTIONS", "layers_for"]

RESOLUTIONS: dict[AspectRatio, Resolution] = {
    AspectRatio.VERTICAL: Resolution(width=1080, height=1920),
    AspectRatio.HORIZONTAL: Resolution(width=1920, height=1080),
    AspectRatio.SQUARE: Resolution(width=1080, height=1080),
    AspectRatio.CLASSIC: Resolution(width=1080, height=1350),
}

_DEEP_FRAMINGS = {
    Framing.EXTREME_WIDE,
    Framing.WIDE,
    Framing.MEDIUM_WIDE,
}
_FLAT_FRAMINGS = {
    Framing.MACRO,
    Framing.EXTREME_CLOSE,
    Framing.CUTAWAY_DIAGRAM,
}


def layers_for(
    framing: Framing, subject: str = "", *, separable: bool = True
) -> list[LayerSpec]:
    """Calques séparables, choisis sur la profondeur qu'admet le cadrage.

    Le moteur 2.5D a besoin de plans distincts pour créer du parallaxe. Un
    cadrage large en offre plusieurs ; une coupe technique n'en a qu'un, et
    prétendre le contraire donnerait un parallaxe sur du vide.

    **Chaque calque porte le sujet.** Il ne le portait pas : les descriptions
    étaient des constantes — « fond lointain », « décor d'arrière-plan »,
    « sujet principal », « éléments de premier plan ». Un fournisseur d'images
    reçoit un appel par calque ; sur un plan large, trois des quatre demandes
    ne contenaient donc aucune matière. Les images étaient génériques parce
    que la commande l'était.

    Le rôle reste ce qui distingue les calques entre eux — sans quoi quatre
    appels rendraient quatre fois la même image et le parallaxe n'aurait plus
    de profondeur à animer.
    """
    scene = subject.strip()
    de_la_scene = f" de la scène : {scene}" if scene else ""
    du_sujet = f" — {scene}" if scene else ""

    if not separable:
        # Le moteur d'images retenu rend des images opaques. Demander quatre
        # calques donnerait quatre images dont trois seraient écrasées à la
        # composition — c'est ce qui est arrivé aux runs #7 et #8, par les deux
        # bouts du tri. Un seul calque, celui du sujet, et le routeur constate
        # qu'il n'y a pas de profondeur à décaler.
        return [
            LayerSpec(
                role=LayerRole.SUBJECT,
                depth=0.5,
                description=f"scène entière, sujet compris{du_sujet}",
                must_be_separable=False,
            )
        ]

    if framing in _FLAT_FRAMINGS:
        return [
            LayerSpec(
                role=LayerRole.SUBJECT,
                depth=0.5,
                description=f"sujet unique, occupant le cadre{du_sujet}",
            )
        ]
    if framing in _DEEP_FRAMINGS:
        return [
            LayerSpec(
                role=LayerRole.SKY,
                depth=0.0,
                description=f"fond lointain{de_la_scene}, sans le sujet lui-même",
            ),
            LayerSpec(
                role=LayerRole.BACKGROUND,
                depth=0.25,
                description=f"décor d'arrière-plan{de_la_scene}, sujet exclu",
            ),
            LayerSpec(
                role=LayerRole.SUBJECT,
                depth=0.6,
                description=f"sujet principal, isolé sur fond neutre{du_sujet}",
            ),
            LayerSpec(
                role=LayerRole.FOREGROUND,
                depth=0.9,
                description=f"éléments de premier plan{de_la_scene}, cadre partiel",
            ),
        ]
    return [
        LayerSpec(
            role=LayerRole.BACKGROUND,
            depth=0.2,
            description=f"fond{de_la_scene}, sujet exclu",
        ),
        LayerSpec(
            role=LayerRole.SUBJECT,
            depth=0.7,
            description=f"sujet principal, isolé sur fond neutre{du_sujet}",
        ),
    ]


@dataclass
class ImageSpecOutcome:
    specs: list[ImageSpec]
    notes: list[str] = field(default_factory=list)

    def for_shot(self, shot_id: str) -> ImageSpec:
        for spec in self.specs:
            if spec.shot_id == shot_id:
                return spec
        raise KeyError(shot_id)


@dataclass
class ImageSpecCompiler:
    separable_layers: bool = True
    """Le moteur d'images qui rendra ces spécifications sait-il la transparence ?

    Ce n'est pas une préférence esthétique : c'est une capacité du
    fournisseur, et elle décide combien de calques ont un sens à demander.
    Le moteur procédural local dessine sur fond transparent et en admet
    plusieurs ; `flux`, chez fal, rend un PNG opaque et n'en admet qu'un.

    La valeur par défaut vaut pour le moteur local, qui est le repli garanti.
    L'appelant qui sait qu'un moteur distant prendra la main la renseigne."""

    def compile(
        self,
        *,
        shot_graph: ShotGraph,
        visual_bible: VisualBible,
        director_state: DirectorState,
        request: TopicRequest,
    ) -> ImageSpecOutcome:
        resolution = RESOLUTIONS[request.aspect_ratio]
        anchors = {anchor.id: anchor for anchor in director_state.continuity_anchors}
        specs: list[ImageSpec] = []

        for shot in shot_graph.shots:
            shot_anchors = [anchors[a] for a in shot.continuity_dependencies]
            specs.append(
                ImageSpec(
                    shot_id=shot.shot_id,
                    visual_bible_id=visual_bible.id,
                    anchor_ids=list(shot.continuity_dependencies),
                    claim_id=shot.claim_id,
                    evidence_required=shot.evidence_required,
                    subject_matter=request.topic,
                    subject=shot.visual_subject,
                    composition=shot.composition.model_copy(deep=True),
                    resolution=resolution,
                    aspect_ratio=request.aspect_ratio,
                    intent=self._intent(shot, visual_bible, shot_anchors),
                    forbidden=list(visual_bible.forbidden),
                    layers=layers_for(
                        shot.composition.framing,
                        shot.visual_subject,
                        separable=self.separable_layers,
                    ),
                    seed=self._seed(request, shot),
                    parent_id=shot.id,
                )
            )
        return ImageSpecOutcome(
            specs=specs,
            notes=[
                f"{len(specs)} spécifications d'image en "
                f"{resolution.width}×{resolution.height} ({request.aspect_ratio.value})",
                f"{sum(len(s.layers) for s in specs)} calques au total",
                f"{sum(1 for s in specs if s.evidence_required)} image(s) "
                "portent une exigence de preuve",
                f"sujet de l'épisode transmis à chaque image : {request.topic}",
                *(
                    []
                    if self.separable_layers
                    else [
                        "calques non séparables : le moteur d'images retenu rend "
                        "des images opaques, un seul calque par plan est demandé"
                    ]
                ),
            ],
        )

    # ------------------------------------------------------------------ règles

    @staticmethod
    def _intent(
        shot: ShotSpec, bible: VisualBible, anchors: list[AnchorSpec]
    ) -> str:
        """Assemble des éléments déjà décidés. N'en invente aucun."""
        parts = [
            shot.visual_subject,
            f"Cadrage : {shot.composition.framing.value}, angle "
            f"{shot.composition.angle.value}, sujet {shot.composition.subject_position.value}.",
            f"Style : {bible.style}.",
            f"Lumière : {bible.lighting}.",
            f"Optique : {bible.lens_language}.",
            f"Profondeur : {bible.depth_of_field}.",
            f"Matières : {', '.join(bible.materials)}." if bible.materials else "",
            f"Texture : {bible.texture}.",
            f"Décor : {bible.environment}.",
        ]
        for anchor in anchors:
            traits = ", ".join(
                f"{attribute.name} {attribute.value}"
                for attribute in anchor.fixed_attributes()
            )
            parts.append(f"Continuité — {anchor.name} : {traits}.")
        return " ".join(part for part in parts if part)

    @staticmethod
    def _seed(request: TopicRequest, shot: ShotSpec) -> int:
        """Graine reproductible : même épisode, même plan, même image.

        Dérivée de la graine de l'épisode quand elle existe, du sujet sinon.
        Deux exécutions donnent la même valeur, ce qui rend une génération
        comparable à la précédente.
        """
        base = str(request.seed) if request.seed is not None else request.topic
        digest = hashlib.sha256(f"{base}|{shot.shot_id}".encode()).digest()
        return int.from_bytes(digest[:4], "big")
