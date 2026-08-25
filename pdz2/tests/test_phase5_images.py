"""Phase 5 : le moteur d'image produit de vrais fichiers, déterministes."""

from __future__ import annotations

import pytest
from PIL import Image

from pdz2.contracts.enums import ArtifactKind, ScreenPosition
from pdz2.contracts.visual import LayerRole
from pdz2.engines.imagery import (
    ImageRenderFailed,
    ProceduralImageRenderer,
)
from pdz2.tests import pipeline


def _alpha_values(alpha):
    """Valeurs du canal alpha, sans l'API dépréciée de Pillow."""
    return alpha.tobytes()


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    root = tmp_path_factory.mktemp("phase5")
    episode = pipeline.build_episode(root, through_render_spec=True)
    outcome = ProceduralImageRenderer().render(
        specs=episode.image_specs, visual_bible=episode.bible, into=root / "assets"
    )
    return episode, outcome, root


class TestRealFiles:
    def test_one_composite_per_image_spec(self, rendered) -> None:
        episode, outcome, _ = rendered
        assert len(outcome.images) == len(episode.image_specs)
        for image in outcome.images:
            assert image.composite_path.is_file()
            assert image.composite_path.stat().st_size > 1000

    def test_the_composite_opens_at_the_requested_resolution(self, rendered) -> None:
        _, outcome, _ = rendered
        for image in outcome.images:
            with Image.open(image.composite_path) as opened:
                assert opened.size == (
                    image.resolution.width,
                    image.resolution.height,
                )

    def test_one_file_per_declared_layer(self, rendered) -> None:
        episode, outcome, _ = rendered
        by_shot = {spec.shot_id: spec for spec in episode.image_specs}
        for image in outcome.images:
            spec = by_shot[image.shot_id]
            assert set(image.layer_paths) == {layer.role for layer in spec.layers}
            for path in image.layer_paths.values():
                assert path.is_file()

    def test_layers_carry_transparency_for_the_parallax(self, rendered) -> None:
        """Sans canal alpha, aucun parallaxe n'est possible."""
        _, outcome, _ = rendered
        for image in outcome.images:
            for role, path in image.layer_paths.items():
                if role is LayerRole.SKY:
                    continue
                with Image.open(path) as opened:
                    assert opened.mode == "RGBA"

    def test_an_artifact_is_recorded_for_every_file(self, rendered) -> None:
        _, outcome, _ = rendered
        assert all(a.kind is ArtifactKind.IMAGE for a in outcome.artifacts)
        assert all(len(a.sha256) == 64 for a in outcome.artifacts)
        assert all(a.size_bytes > 0 for a in outcome.artifacts)
        expected = sum(image.layer_count + 1 for image in outcome.images)
        assert len(outcome.artifacts) == expected

    def test_the_recorded_checksum_matches_the_file(self, rendered) -> None:
        import hashlib

        _, outcome, root = rendered
        for artifact in outcome.artifacts:
            path = root / "assets" / artifact.path
            assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact.sha256


class TestDeterminism:
    def test_two_renders_produce_identical_bytes(self, rendered, tmp_path) -> None:
        episode, outcome, _ = rendered
        again = ProceduralImageRenderer().render(
            specs=episode.image_specs,
            visual_bible=episode.bible,
            into=tmp_path / "again",
        )
        for first, second in zip(outcome.images, again.images, strict=True):
            assert first.composite_path.read_bytes() == second.composite_path.read_bytes()

    def test_a_different_seed_produces_a_different_image(
        self, rendered, tmp_path
    ) -> None:
        episode, outcome, _ = rendered
        reseeded = [
            spec.model_copy(update={"seed": spec.seed + 1})
            for spec in episode.image_specs
        ]
        other = ProceduralImageRenderer().render(
            specs=reseeded, visual_bible=episode.bible, into=tmp_path / "reseeded"
        )
        differences = [
            first.composite_path.read_bytes() != second.composite_path.read_bytes()
            for first, second in zip(outcome.images, other.images, strict=True)
        ]
        assert any(differences)


class TestTheBibleDrivesTheImage:
    def test_the_palette_reaches_the_pixels(self, rendered) -> None:
        episode, outcome, _ = rendered
        dominant = tuple(
            int(episode.bible.color.palette[0].lstrip("#")[i : i + 2], 16)
            for i in (0, 2, 4)
        )
        with Image.open(outcome.images[0].composite_path) as opened:
            corner = opened.convert("RGB").getpixel((5, 5))
        # Le coin haut-gauche est du fond : proche de la dominante.
        assert sum(abs(a - b) for a, b in zip(corner, dominant, strict=True)) < 120

    def test_a_different_palette_changes_the_image(self, rendered, tmp_path) -> None:
        episode, outcome, _ = rendered
        from pdz2.contracts.visual import ColorScheme

        repainted = episode.bible.model_copy(
            update={
                "color": ColorScheme(
                    palette=["#F5F0E6", "#C0392B", "#2C3E50", "#FFFFFF"]
                )
            }
        )
        specs = [
            spec.model_copy(update={"visual_bible_id": repainted.id})
            for spec in episode.image_specs
        ]
        other = ProceduralImageRenderer().render(
            specs=specs, visual_bible=repainted, into=tmp_path / "repaint"
        )
        assert (
            other.images[0].composite_path.read_bytes()
            != outcome.images[0].composite_path.read_bytes()
        )

    def test_the_framing_changes_the_subject_size(self, rendered, tmp_path) -> None:
        """Un gros plan occupe plus de cadre qu'un plan large."""
        from pdz2.contracts.enums import Framing

        episode, _, _ = rendered
        spec = episode.image_specs[0]

        def subject_pixels(framing: Framing) -> int:
            composition = spec.composition.model_copy(update={"framing": framing})
            variant = spec.model_copy(
                update={
                    "composition": composition,
                    "layers": [
                        layer
                        for layer in spec.layers
                        if layer.role is LayerRole.SUBJECT
                    ]
                    or spec.layers[:1],
                }
            )
            outcome = ProceduralImageRenderer().render(
                specs=[variant],
                visual_bible=episode.bible,
                into=tmp_path / framing.value,
            )
            path = outcome.images[0].layer_paths[LayerRole.SUBJECT]
            with Image.open(path) as opened:
                alpha = opened.split()[-1]
            return sum(1 for value in _alpha_values(alpha) if value > 10)

        assert subject_pixels(Framing.CLOSE) > subject_pixels(Framing.WIDE)

    def test_the_subject_position_moves_the_subject(self, rendered, tmp_path) -> None:
        episode, _, _ = rendered
        spec = episode.image_specs[0]

        def centroid(position: ScreenPosition) -> float:
            composition = spec.composition.model_copy(
                update={"subject_position": position}
            )
            variant = spec.model_copy(
                update={
                    "composition": composition,
                    "layers": [
                        layer
                        for layer in spec.layers
                        if layer.role is LayerRole.SUBJECT
                    ]
                    or spec.layers[:1],
                }
            )
            outcome = ProceduralImageRenderer().render(
                specs=[variant],
                visual_bible=episode.bible,
                into=tmp_path / f"pos-{position.value}",
            )
            path = outcome.images[0].layer_paths[LayerRole.SUBJECT]
            with Image.open(path) as opened:
                alpha = opened.split()[-1]
                width = opened.width
            total = weighted = 0
            for index, value in enumerate(_alpha_values(alpha)):
                if value > 10:
                    total += 1
                    weighted += index % width
            return weighted / max(1, total)

        assert centroid(ScreenPosition.LEFT) < centroid(ScreenPosition.RIGHT)


class TestRefusals:
    def test_an_image_from_another_bible_is_refused(self, rendered, tmp_path) -> None:
        episode, _, _ = rendered
        stranger = pipeline.build_episode(tmp_path / "stranger")
        with pytest.raises(ImageRenderFailed, match="ne descend pas"):
            ProceduralImageRenderer().render(
                specs=episode.image_specs,
                visual_bible=stranger.bible,
                into=tmp_path / "out",
            )
