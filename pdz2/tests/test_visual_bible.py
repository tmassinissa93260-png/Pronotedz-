"""Visual Bible : décidée ou par préréglage, jamais dépendante d'un moteur."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from pdz2.contracts.direction import VisualStyleDecision
from pdz2.contracts.enums import Pacing, Tone
from pdz2.engines.visual import (
    CAMERA_LANGUAGE,
    STYLE_PRESETS,
    VisualBibleCompiler,
    VisualBibleRejected,
    preset_for,
)
from pdz2.tests import pipeline

VISUAL_PACKAGE = Path(__file__).resolve().parents[1] / "engines" / "visual"

PROVIDER_NAMES = (
    "kling", "veo", "runway", "pika", "luma", "sora", "midjourney", "stability",
    "openai", "anthropic", "replicate", "fal", "comfyui", "elevenlabs", "espeak",
)


@pytest.fixture(scope="module")
def episode(tmp_path_factory):
    return pipeline.build_episode(tmp_path_factory.mktemp("bible"))


class TestProviderAgnostic:
    def test_no_provider_name_appears_in_the_compiled_bible(self, episode) -> None:
        # Recherche sur mots entiers : « fal » se cache dans « False », et une
        # correspondance par sous-chaîne ferait échouer le test sur du français.
        payload = str(episode.bible.to_payload()).lower()
        found = [
            name for name in PROVIDER_NAMES if re.search(rf"\b{name}\b", payload)
        ]
        assert not found, f"la bible nomme un fournisseur : {found}"

    def test_no_provider_name_appears_in_the_presets(self) -> None:
        offenders: list[str] = []
        for path in sorted(VISUAL_PACKAGE.rglob("*.py")):
            lowered = path.read_text(encoding="utf-8").lower()
            for name in PROVIDER_NAMES:
                if re.search(rf"\b{name}\b", lowered):
                    offenders.append(f"{path.name} mentionne {name!r}")
        assert not offenders, offenders

    def test_the_bible_describes_intent_not_execution(self, episode) -> None:
        forbidden = ("prompt", "model", "api", "endpoint", "seed", "checkpoint")
        payload = str(episode.bible.to_payload()).lower()
        assert not [word for word in forbidden if word in payload]


class TestDecidedVersusDefaulted:
    def test_a_brief_without_a_style_falls_back_and_says_so(self, episode) -> None:
        outcome = VisualBibleCompiler().compile(
            director_state=episode.director_state, brief=episode.brief
        )
        assert outcome.style_was_decided is False
        assert any("préréglage déclaré" in note for note in outcome.notes)

    def test_a_decided_style_is_used_verbatim(self, tmp_path) -> None:
        decision = VisualStyleDecision(
            style="maquette filaire animée",
            lighting="lumière plate",
            palette=["#101010", "#F0F0F0"],
            lens_language="orthographique",
            materials=["fil de fer"],
            texture="aucune",
            environment="grille infinie",
            graphics="cotes techniques",
        )
        episode = pipeline.build_episode(
            tmp_path / "decided", brief_overrides={"visual_style": decision}
        )
        outcome = VisualBibleCompiler().compile(
            director_state=episode.director_state, brief=episode.brief
        )
        assert outcome.style_was_decided is True
        assert "maquette filaire animée" in outcome.bible.style
        assert outcome.bible.lighting == "lumière plate"
        assert outcome.bible.color.palette == ["#101010", "#F0F0F0"]

    def test_every_tone_has_a_declared_preset(self) -> None:
        for tone in Tone:
            preset = preset_for(tone)
            assert preset.style and preset.lighting and len(preset.palette) >= 2

    def test_presets_are_tables_not_generations(self) -> None:
        """Deux appels rendent le même objet : rien n'est fabriqué à l'exécution."""
        assert preset_for(Tone.DOCUMENTARY) is STYLE_PRESETS[Tone.DOCUMENTARY]
        assert preset_for(Tone.CINEMATIC) == preset_for(Tone.CINEMATIC)


class TestDerivedFields:
    def test_visual_density_comes_from_information_density(self, episode) -> None:
        assert episode.bible.visual_density == (
            episode.director_state.information_density
        )

    def test_camera_language_comes_from_the_pacing(self, episode) -> None:
        assert episode.bible.camera_language == (
            CAMERA_LANGUAGE[episode.director_state.pacing]
        )

    def test_a_different_pacing_changes_the_camera_language(self, tmp_path) -> None:
        rapid = pipeline.build_episode(
            tmp_path / "rapid", brief_overrides={"pacing": Pacing.RAPID}
        )
        assert rapid.bible.camera_language == CAMERA_LANGUAGE[Pacing.RAPID]
        assert rapid.bible.camera_language != CAMERA_LANGUAGE[Pacing.MEASURED]

    def test_forbidden_imagery_is_carried_over(self, tmp_path) -> None:
        from pdz2.contracts.direction import VisualLanguage

        episode = pipeline.build_episode(
            tmp_path / "forbidden",
            brief_overrides={
                "visual_language": VisualLanguage(
                    visual_register="coupe technique",
                    forbidden_imagery=["visages reconnaissables", "logos de marque"],
                )
            },
        )
        assert episode.bible.forbidden == [
            "visages reconnaissables",
            "logos de marque",
        ]

    def test_the_decided_register_opens_the_style(self, episode) -> None:
        register = episode.director_state.visual_language.visual_register
        assert episode.bible.style.startswith(register)

    def test_a_dense_episode_tightens_the_typography(self, tmp_path) -> None:
        episode = pipeline.build_episode(tmp_path / "dense")
        bible = episode.bible
        if bible.visual_density >= 0.6:
            assert bible.typography.max_chars_per_line == 22
        else:
            assert bible.typography.max_chars_per_line == 34

    def test_the_bible_descends_from_the_director_state(self, episode) -> None:
        assert episode.bible.parent_id == episode.director_state.id
        assert episode.bible.director_state_id == episode.director_state.id


class TestRefusals:
    def test_a_brief_that_is_not_the_parent_is_refused(self, episode, tmp_path) -> None:
        other = pipeline.build_episode(tmp_path / "other")
        with pytest.raises(VisualBibleRejected, match="n'est pas celui"):
            VisualBibleCompiler().compile(
                director_state=episode.director_state, brief=other.brief
            )
