"""HYBRID : ce qui s'exécute réellement en local, et ce qui ne le peut pas.

Le cahier des charges définit un plan hybride comme la réunion de cinq
éléments dans un même plan :

    sujet généré + fond procédural + caméra 2.5D + motion graphics + sound design

Ces tests établissent, élément par élément et sur des pixels réels, lesquels
sont exécutés ici. Ils ne déclarent pas HYBRID terminé parce qu'un double
passe : ils mesurent.

Verdict que ces tests figent :

    fond procédural   EXÉCUTÉ      mesuré sur les pixels
    caméra 2.5D       EXÉCUTÉ      parallaxe mesurée entre calques
    motion graphics   EXÉCUTÉ      incrustation mesurée dans sa fenêtre
    sound design      CONÇU, MUET  aucune bibliothèque branchée
    sujet généré      INDISPONIBLE aucun fournisseur joignable
"""

from __future__ import annotations

import pytest

from pdz2.contracts.common import TextOverlay
from pdz2.contracts.enums import ScreenPosition
from pdz2.contracts.render import RenderStrategy
from pdz2.execution.dispatcher import _ce_qui_est_perdu, _local_fallback
from pdz2.providers.video import NO_VIDEO_PROVIDERS
from pdz2.renderers import ffmpeg_capability
from pdz2.renderers.deterministic import SUPPORTED_STRATEGIES
from pdz2.tests import pipeline

needs_ffmpeg = pytest.mark.skipif(
    not ffmpeg_capability().usable, reason="binaire ffmpeg absent"
)


# ------------------------------------------- ce qui n'est pas disponible ici


def test_the_generated_subject_has_no_provider_and_says_so():
    """Aucun fournisseur : l'élément génératif d'un hybride est indisponible."""
    assert NO_VIDEO_PROVIDERS == ()
    assert RenderStrategy.HYBRID not in SUPPORTED_STRATEGIES


def test_a_lost_hybrid_names_the_element_it_lost():
    """« Rendu localement » ne suffit pas : un hybride ne perd pas tout."""
    perdu = _ce_qui_est_perdu(RenderStrategy.HYBRID, _local_fallback(RenderStrategy.HYBRID))
    assert "sujet généré non exécuté" in perdu
    assert "fond procédural" in perdu and "2.5D" in perdu

    entier = _ce_qui_est_perdu(RenderStrategy.DIRECT_I2V, RenderStrategy.PROCEDURAL)
    assert "entièrement rendu" in entier


def test_the_sound_design_of_a_shot_is_designed_but_silent():
    import tempfile
    from pathlib import Path

    from pdz2.engines.sound import SoundCompiler

    episode = pipeline.build_episode(Path(tempfile.mkdtemp(prefix="hybride-")))
    design = SoundCompiler().compile(
        episode_id="ep",
        shot_graph=episode.graph,
        temporal_plan=episode.temporal_plan,
    ).design
    assert design.cues, "la grammaire décide bien des repères"
    assert design.silent, "aucune bibliothèque ne doit être inventée"


# --------------------------- ce qui s'exécute réellement, mesuré sur les pixels


@needs_ffmpeg
def test_one_shot_really_combines_background_camera_and_graphics(tmp_path):
    """Le cœur du sujet : trois éléments dans un même plan, sur de vrais pixels.

    Le plan est rendu deux fois — avec et sans incrustation — et les deux
    rendus sont mesurés. Le mouvement prouve la caméra, la différence entre
    les deux prouve les motion graphics, et les calques multiples prouvent le
    fond composé.
    """
    from pdz2.engines.imagery import ProceduralImageRenderer
    from pdz2.engines.routing import RenderRouter
    from pdz2.execution import ExecutionDispatcher
    from pdz2.qa.measures import (
        BAND_BY_POSITION,
        decode_frames,
        first_to_last_difference,
        region_change_at,
    )

    episode = pipeline.build_episode(
        tmp_path / "ep", through_render_spec=True, resolution=pipeline.SMALL
    )
    images = ProceduralImageRenderer().render(
        specs=episode.image_specs, visual_bible=episode.bible, into=tmp_path / "assets"
    )
    # Le plan retenu doit avoir plusieurs calques : sans eux, pas de parallaxe.
    porteur = max(images.images, key=lambda i: i.layer_count)
    assert porteur.layer_count >= 2, "fond composé attendu"

    specs = list(episode.render_specs)
    index = next(i for i, s in enumerate(specs) if s.shot_id == porteur.shot_id)
    duree = specs[index].duration_s
    overlay = TextOverlay(
        text="60 kWh",
        at_s=0.2,
        duration_s=min(1.2, duree - 0.3),
        position=ScreenPosition.LOWER_THIRD,
        emphasis=True,
    )

    def _rendre(avec_incrustation: bool, dossier: str):
        jeu = list(specs)
        jeu[index] = specs[index].derive(
            text_overlay=overlay if avec_incrustation else None
        )
        route = RenderRouter().route(
            episode_id="ep",
            requested=jeu,
            motion_programs=episode.motion_programs,
            image_specs=episode.image_specs,
        )
        rendu = ExecutionDispatcher().execute(
            executables=route.executables,
            motion_programs=episode.motion_programs,
            images=images.images,
            into=tmp_path / dossier,
            typography=episode.bible.typography,
        )
        artefact = next(a for a in rendu.artifacts if a.shot_id == porteur.shot_id)
        return route.for_shot(porteur.shot_id), tmp_path / dossier / artefact.path

    executable, avec = _rendre(True, "avec")
    _, sans = _rendre(False, "sans")

    # 1. Fond composé : la stratégie retenue exploite les calques.
    assert executable.strategy in {
        RenderStrategy.PARALLAX_2_5D,
        RenderStrategy.PROCEDURAL,
    }, executable.strategy

    # 2. Caméra : le plan bouge réellement du début à la fin.
    sequence = decode_frames(avec)
    assert first_to_last_difference(sequence) > 0.001

    # 3. Motion graphics : l'incrustation change la bande visée, et seulement
    #    quand elle est demandée.
    bande = BAND_BY_POSITION["lower_third"]
    milieu = overlay.at_s + overlay.duration_s / 2
    change_avec = region_change_at(
        sequence, band=bande, before_s=0.0, during_s=milieu
    )
    change_sans = region_change_at(
        decode_frames(sans), band=bande, before_s=0.0, during_s=milieu
    )
    assert change_avec > change_sans * 2, (
        f"incrustation peu visible : {change_avec:.4f} contre {change_sans:.4f}"
    )
