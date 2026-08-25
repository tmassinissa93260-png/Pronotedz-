"""Incrustations de texte : contrat → producteur → rendu → observation.

`ShotSpec.text_overlay` était produit par la grammaire de plans, validé par le
contrat, compté dans les notes du compilateur — et **jamais dessiné**. Il
n'atteignait même pas `RenderSpecRequested`. Un contrat produit puis jeté,
exactement le motif que l'audit traque.

Ces tests suivent la chaîne entière, jusqu'aux pixels et à leur mesure.
"""

from __future__ import annotations

import pytest
from PIL import Image

from pdz2.contracts.common import TextOverlay
from pdz2.contracts.enums import ScreenPosition
from pdz2.contracts.visual import Typography
from pdz2.renderers import ffmpeg_capability
from pdz2.renderers.graphics import (
    FADE_S,
    draw_text_overlay,
    overlay_opacity_at,
    overlay_visible_at,
)
from pdz2.tests import pipeline

needs_ffmpeg = pytest.mark.skipif(
    not ffmpeg_capability().usable, reason="binaire ffmpeg absent"
)

TYPO = Typography(family="DejaVu Sans", weight=700, uppercase=True)


def _overlay(**changes) -> TextOverlay:
    base = dict(
        text="60 kWh",
        at_s=1.0,
        duration_s=2.0,
        position=ScreenPosition.LOWER_THIRD,
        emphasis=True,
    )
    return TextOverlay(**(base | changes))


# ------------------------------------------------------------- la fenêtre


def test_the_overlay_exists_only_inside_its_window():
    overlay = _overlay()
    assert not overlay_visible_at(overlay, 0.99)
    assert overlay_visible_at(overlay, 1.0)
    assert overlay_visible_at(overlay, 3.0)
    assert not overlay_visible_at(overlay, 3.01)


def test_the_opacity_fades_in_and_out():
    overlay = _overlay()
    assert overlay_opacity_at(overlay, 0.5) == 0.0
    assert overlay_opacity_at(overlay, 1.0) == 0.0
    assert 0.0 < overlay_opacity_at(overlay, 1.0 + FADE_S / 2) < 1.0
    assert overlay_opacity_at(overlay, 2.0) == 1.0
    assert 0.0 < overlay_opacity_at(overlay, 3.0 - FADE_S / 2) < 1.0
    assert overlay_opacity_at(overlay, 3.5) == 0.0


def test_a_very_short_overlay_still_reaches_full_opacity():
    """Le fondu se réduit plutôt que d'avaler toute la fenêtre."""
    court = _overlay(duration_s=0.3)
    assert overlay_opacity_at(court, court.at_s + 0.15) == pytest.approx(1.0, abs=0.01)


# ------------------------------------------------------------- les pixels


def test_drawing_changes_pixels_only_inside_the_window():
    fond = Image.new("RGB", (360, 640), (40, 60, 90))
    overlay = _overlay()
    for instant, attendu in ((0.5, False), (2.0, True), (3.5, False)):
        rendu = draw_text_overlay(fond, overlay, TYPO, instant)
        change = rendu.tobytes() != fond.tobytes()
        assert change is attendu, f"t={instant}"


def test_the_source_frame_is_never_painted_in_place():
    """Peindre en place laisserait une traînée d'une image à l'autre."""
    fond = Image.new("RGB", (360, 640), (40, 60, 90))
    avant = fond.tobytes()
    draw_text_overlay(fond, _overlay(), TYPO, 2.0)
    assert fond.tobytes() == avant


def test_the_drawing_is_deterministic():
    fond = Image.new("RGB", (360, 640), (40, 60, 90))
    premier = draw_text_overlay(fond, _overlay(), TYPO, 2.0).tobytes()
    second = draw_text_overlay(fond, _overlay(), TYPO, 2.0).tobytes()
    assert premier == second


@pytest.mark.parametrize("position", list(ScreenPosition))
def test_every_screen_position_draws_somewhere(position):
    fond = Image.new("RGB", (360, 640), (40, 60, 90))
    rendu = draw_text_overlay(fond, _overlay(position=position), TYPO, 2.0)
    assert rendu.tobytes() != fond.tobytes()


def test_a_stronger_opacity_changes_more_pixels():
    fond = Image.new("RGB", (360, 640), (40, 60, 90))
    overlay = _overlay()

    def ecart(t: float) -> int:
        rendu = draw_text_overlay(fond, overlay, TYPO, t)
        return sum(
            1
            for a, b in zip(fond.tobytes(), rendu.tobytes(), strict=True)
            if a != b
        )

    assert ecart(2.0) > 0
    assert ecart(1.0 + FADE_S / 4) < ecart(2.0)


# ----------------------------------------------- la chaîne jusqu'à la mesure


@needs_ffmpeg
def test_the_overlay_travels_from_the_shot_graph_to_the_measured_pixels(tmp_path):
    """Le test qui compte : de la décision du plan jusqu'au constat mesuré."""
    from pdz2.engines.imagery import ProceduralImageRenderer
    from pdz2.engines.routing import RenderRouter
    from pdz2.execution import ExecutionDispatcher
    from pdz2.qa import DeterministicObserver

    episode = pipeline.build_episode(
        tmp_path / "ep", through_render_spec=True, resolution=pipeline.SMALL
    )
    # On pose une incrustation sur la première demande, comme le ferait un
    # ShotSpec qui porte une grandeur chiffrée.
    specs = list(episode.render_specs)
    vise = specs[0]
    overlay = _overlay(at_s=0.2, duration_s=min(1.5, vise.duration_s - 0.3))
    specs[0] = vise.derive(text_overlay=overlay)

    images = ProceduralImageRenderer().render(
        specs=episode.image_specs, visual_bible=episode.bible, into=tmp_path / "assets"
    )
    route = RenderRouter().route(
        episode_id="ep",
        requested=specs,
        motion_programs=episode.motion_programs,
        image_specs=episode.image_specs,
    )
    # L'incrustation a bien traversé le routeur.
    porteur = next(e for e in route.executables if e.shot_id == vise.shot_id)
    assert porteur.text_overlay == overlay

    rendu = ExecutionDispatcher().execute(
        executables=route.executables,
        motion_programs=episode.motion_programs,
        images=images.images,
        into=tmp_path / "renders",
        typography=episode.bible.typography,
    )
    observation = DeterministicObserver().observe(
        artifacts=rendu.artifacts,
        executables=route.executables,
        motion_programs=episode.motion_programs,
        visual_bible=episode.bible,
        renders_dir=tmp_path / "renders",
    )
    rapport = next(r for r in observation.reports if r.shot_id == vise.shot_id)
    controle = next(c for c in rapport.checks if c.check_id == "overlay_rendered")
    assert controle.passed, (
        f"incrustation demandée mais non mesurée : {controle.observed}"
    )

    # Et un plan sans incrustation n'invente pas ce contrôle.
    sans = next(r for r in observation.reports if r.shot_id != vise.shot_id)
    assert not [c for c in sans.checks if c.check_id == "overlay_rendered"]


@needs_ffmpeg
def test_an_overlay_that_is_not_drawn_is_caught(tmp_path):
    """Contre-épreuve : sans dessin, le contrôle doit échouer.

    Sans elle, le test précédent prouverait seulement que le contrôle existe,
    pas qu'il sait détecter l'absence.
    """
    from pdz2.contracts.render import RenderSpecExecutable
    from pdz2.qa.measures import BAND_BY_POSITION, decode_frames, region_change_at
    from pdz2.renderers.ffmpeg import encode_raw_frames

    largeur, hauteur, images = 120, 200, 60
    chemin = tmp_path / "sans-incrustation.mp4"
    encode_raw_frames(
        frames=(bytes([80]) * (largeur * hauteur * 3) for _ in range(images)),
        width=largeur,
        height=hauteur,
        fps=30,
        out_path=chemin,
    )
    sequence = decode_frames(chemin)
    ecart = region_change_at(
        sequence,
        band=BAND_BY_POSITION["lower_third"],
        before_s=0.2,
        during_s=1.0,
    )
    from pdz2.qa.observer import OVERLAY_MIN_CHANGE

    assert ecart < OVERLAY_MIN_CHANGE, f"écart {ecart} sur une vidéo sans texte"
    assert RenderSpecExecutable.model_fields["text_overlay"] is not None
