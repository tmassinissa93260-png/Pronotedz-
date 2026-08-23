"""Visual Bible : le registre visuel de l'épisode, compilé une fois.

Deux natures de champs, et le compilateur ne les mélange pas :

* **Décidé** — style, lumière, palette, optique, matières, texture, décor,
  graphisme. Aucun calcul ne les produit. Ils viennent de
  `DirectorBrief.visual_style`, ou d'un **préréglage déclaré** choisi sur le
  ton — et dans ce cas le compilateur l'écrit noir sur blanc.

* **Dérivé** — densité visuelle depuis la densité d'information, interdits
  depuis l'imagerie proscrite, langage caméra et profondeur de champ depuis le
  rythme. Ce sont des conséquences, pas des choix.

La bible ne nomme aucun fournisseur, aucun modèle, aucun moteur. Elle décrit
ce que l'épisode doit *être* ; comment l'obtenir ne la regarde pas.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pdz2.contracts.direction import DirectorBrief, DirectorState
from pdz2.contracts.visual import ColorScheme, Typography, VisualBible
from pdz2.engines.visual.presets import CAMERA_LANGUAGE, DEPTH_OF_FIELD, preset_for

__all__ = ["VisualBibleCompiler", "VisualBibleOutcome", "VisualBibleRejected"]

_DENSITY_TO_CONTRAST = 0.35
"""Un épisode dense a besoin de plus de contraste pour rester lisible."""

_MAX_CHARS_BY_DENSITY = (34, 22)
"""Longueur de ligne d'incrustation, de la moins dense à la plus dense."""


class VisualBibleRejected(ValueError):
    """Le brief et l'état de réalisation ne concordent pas."""


@dataclass
class VisualBibleOutcome:
    bible: VisualBible
    notes: list[str] = field(default_factory=list)
    style_was_decided: bool = True
    """Faux : le style vient d'un préréglage, pas d'une décision de l'auteur."""


@dataclass
class VisualBibleCompiler:
    def compile(
        self,
        *,
        director_state: DirectorState,
        brief: DirectorBrief,
    ) -> VisualBibleOutcome:
        if brief.id != director_state.parent_id:
            raise VisualBibleRejected(
                "ce brief n'est pas celui dont descend l'état de réalisation "
                f"({brief.id} ≠ {director_state.parent_id})"
            )

        decided = brief.visual_style is not None
        style = brief.visual_style or preset_for(director_state.tone)
        density = director_state.information_density
        language = director_state.visual_language

        notes = [
            f"registre : {language.visual_register}",
            f"densité visuelle {density} reprise de la densité d'information",
        ]
        if decided:
            notes.append("style décidé dans le brief")
        else:
            notes.append(
                f"style NON décidé : préréglage déclaré pour le ton "
                f"« {director_state.tone.value} » — le renseigner dans le brief "
                "pour que l'épisode ait un parti pris qui lui soit propre"
            )

        bible = VisualBible(
            director_state_id=director_state.id,
            style=self._with_register(style.style, language.visual_register),
            lighting=style.lighting,
            color=ColorScheme(
                palette=list(style.palette),
                contrast=round(min(1.0, 0.45 + _DENSITY_TO_CONTRAST * density), 4),
                saturation=round(max(0.15, 0.65 - 0.25 * density), 4),
                temperature=0.0,
            ),
            camera_language=CAMERA_LANGUAGE[director_state.pacing],
            lens_language=style.lens_language,
            materials=list(style.materials),
            depth_of_field=DEPTH_OF_FIELD[director_state.pacing],
            environment=style.environment,
            graphics=self._with_motifs(style.graphics, language.recurring_motifs),
            typography=Typography(
                family=style.typography_family,
                weight=700,
                uppercase=False,
                max_chars_per_line=(
                    _MAX_CHARS_BY_DENSITY[1]
                    if density >= 0.6
                    else _MAX_CHARS_BY_DENSITY[0]
                ),
            ),
            texture=style.texture,
            visual_density=density,
            forbidden=list(language.forbidden_imagery),
            parent_id=director_state.id,
        )
        return VisualBibleOutcome(
            bible=bible, notes=notes, style_was_decided=decided
        )

    @staticmethod
    def _with_register(style: str, register: str) -> str:
        """Le registre décidé par la réalisation ouvre la description du style."""
        return f"{register} — {style}"

    @staticmethod
    def _with_motifs(graphics: str, motifs: list[str]) -> str:
        if not motifs:
            return graphics
        return f"{graphics} ; motifs récurrents : {', '.join(motifs)}"
