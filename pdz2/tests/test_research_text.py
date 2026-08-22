"""Outils de texte : ce sont eux qui décident ce qu'est une contradiction."""

from __future__ import annotations

import pytest

from pdz2.engines.research.text import (
    contains_quantity,
    is_negated,
    jaccard,
    normalise,
    overlap,
    sentences,
    tokens,
)


class TestNormalise:
    def test_accents_and_case_disappear(self) -> None:
        assert normalise("Énergie ÉLECTRIQUE") == "energie electrique"

    def test_whitespace_collapses(self) -> None:
        assert normalise("  le\n  moteur  ") == "le moteur"


class TestTokens:
    def test_stop_words_are_dropped(self) -> None:
        assert tokens(normalise("le moteur et la batterie")) == ["moteur", "batterie"]

    def test_french_elisions_are_undone(self) -> None:
        """« l'énergie » et « énergie » sont le même mot."""
        assert tokens(normalise("l'énergie de la batterie")) == ["energie", "batterie"]

    def test_negated_verb_keeps_its_stem(self) -> None:
        """Sans cela, une phrase niée cesse de ressembler à son homologue."""
        assert "atteint" in tokens(normalise("n'atteint pas 90 %"))

    def test_interrogatives_are_stop_words(self) -> None:
        assert tokens(normalise("comment fonctionne le moteur")) == [
            "fonctionne",
            "moteur",
        ]


class TestSentences:
    def test_splits_on_terminal_punctuation(self) -> None:
        assert len(sentences("Le moteur tourne. Le rotor suit. Vraiment ?")) == 3

    def test_abbreviations_do_not_split(self) -> None:
        result = sentences("Le rendement atteint 90 %, cf. p. 14. Le reste suit.")
        assert len(result) == 2
        assert "cf. p. 14" in result[0]


class TestNegation:
    @pytest.mark.parametrize(
        "text",
        [
            "Le rendement n'atteint pas 90 %.",
            "Le moteur ne tourne jamais à vide.",
            "Une chaîne sans boîte de vitesses.",
            "Aucun carburant n'est brûlé.",
        ],
    )
    def test_detects_negation(self, text: str) -> None:
        assert is_negated(text)

    @pytest.mark.parametrize(
        "text",
        [
            "Le rendement d'une chaîne de traction atteint 90 %.",
            "Le stator génère un champ magnétique tournant.",
            "La cathode reçoit les ions.",
        ],
    )
    def test_affirmative_sentences_are_not_negated(self, text: str) -> None:
        assert not is_negated(text)

    def test_ne_inside_a_word_is_not_a_negation(self) -> None:
        """« chaîne » contient « ne » : une recherche par sous-chaîne se
        tromperait, et transformerait une contradiction en corroboration."""
        assert not is_negated("Le rendement d'une chaîne de traction atteint 90 %.")


class TestSimilarity:
    def test_jaccard_is_symmetric(self) -> None:
        a, b = "le moteur tourne vite", "le moteur tourne lentement"
        assert jaccard(a, b) == jaccard(b, a)

    def test_reformulations_score_high(self) -> None:
        score = jaccard(
            "Le moteur électrique convertit l'énergie électrique de la batterie "
            "en énergie mécanique de rotation.",
            "Le moteur électrique convertit l'énergie électrique de la batterie "
            "en mouvement de rotation de l'arbre.",
        )
        assert score > 0.5

    def test_unrelated_sentences_score_low(self) -> None:
        score = jaccard(
            "Le stator génère un champ magnétique tournant.",
            "Le rotor porte des aimants qui s'alignent sur ce champ.",
        )
        assert score < 0.25

    def test_overlap_favours_the_shorter_text(self) -> None:
        """Une grandeur courte peut porter sur un mécanisme long."""
        short = "Le rendement d'une chaîne électrique atteint 90 %."
        long = (
            "Le moteur électrique convertit l'énergie électrique de la batterie "
            "en énergie mécanique de rotation."
        )
        assert overlap(short, long) > jaccard(short, long)

    def test_overlap_is_zero_without_shared_words(self) -> None:
        assert overlap("le stator génère un champ", "les pistons montent") == 0.0

    def test_empty_text_scores_zero(self) -> None:
        assert jaccard("", "le moteur") == 0.0
        assert overlap("", "le moteur") == 0.0


class TestQuantities:
    @pytest.mark.parametrize(
        "text",
        ["95 % de rendement", "400 V continu", "12 kWh stockés", "150 km/h", "0,5 s"],
    )
    def test_detects_quantities(self, text: str) -> None:
        assert contains_quantity(text)

    @pytest.mark.parametrize("text", ["un bon rendement", "une centaine de moteurs"])
    def test_ignores_vague_amounts(self, text: str) -> None:
        assert not contains_quantity(text)
