"""geometrie.phrase() : traduit une zone/profondeur qualitative en phrase
anglaise prête pour le prompt — jamais une coordonnée inventée.
"""

from __future__ import annotations

from pdz.production import geometrie


def test_phrase_combine_zone_et_profondeur():
    assert geometrie.phrase("airliner", "center", "foreground") == (
        "airliner, centered in the frame, in the foreground"
    )


def test_phrase_zone_seule():
    assert geometrie.phrase("runway", "bottom", "") == (
        "runway, near the bottom of the frame"
    )


def test_phrase_profondeur_seule():
    assert geometrie.phrase("airport", "", "background") == (
        "airport, in the background"
    )


def test_phrase_sans_entite_est_vide():
    assert geometrie.phrase("", "center", "foreground") == ""


def test_phrase_sans_zone_ni_profondeur_est_vide():
    """Une entité seule, sans aucune position reconnue, ne dit rien de
    plus qu'un nom déjà présent ailleurs dans le prompt — pas de phrase à
    ajouter."""
    assert geometrie.phrase("airliner", "", "") == ""


def test_phrase_valeur_hors_vocabulaire_est_ignoree():
    """Filet : une valeur qui ne serait pas dans l'enum (théorique, Groq
    ne valide que le `type`) est simplement ignorée, jamais une exception
    ni une valeur par défaut inventée."""
    assert geometrie.phrase("airliner", "diagonal", "far") == ""
