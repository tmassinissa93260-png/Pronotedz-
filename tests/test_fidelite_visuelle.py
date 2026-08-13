"""fidelite_visuelle.renforcer() : le prompt d'image doit montrer ce que la
réplique nomme concrètement — pas juste « l'esprit » de la scène.

Zéro appel Groq : une simple vérification de sous-chaîne, et une
concaténation si un élément désigné manque. Voir plans@1.4.0.yaml.
"""

from __future__ import annotations

from pdz.production import fidelite_visuelle


def test_un_element_deja_present_nest_pas_rajoute():
    prompt, manquants = fidelite_visuelle.renforcer(
        "a submarine cable glowing under the ocean", ["submarine cable"]
    )
    assert prompt == "a submarine cable glowing under the ocean"
    assert manquants == []


def test_un_element_absent_est_rajoute():
    prompt, manquants = fidelite_visuelle.renforcer(
        "a generic glowing hologram", ["submarine cable"]
    )
    assert "submarine cable" in prompt
    assert manquants == ["submarine cable"]


def test_plusieurs_elements_absents_sont_tous_rajoutes():
    prompt, manquants = fidelite_visuelle.renforcer(
        "a wide shot of a wireframe city", ["submarine cable", "phone"]
    )
    assert "submarine cable" in prompt
    assert "phone" in prompt
    assert manquants == ["submarine cable", "phone"]


def test_la_comparaison_ignore_la_casse():
    prompt, manquants = fidelite_visuelle.renforcer(
        "A SUBMARINE CABLE under the ocean", ["submarine cable"]
    )
    assert manquants == []
    assert prompt == "A SUBMARINE CABLE under the ocean"


def test_une_liste_delements_vide_ne_change_rien():
    prompt, manquants = fidelite_visuelle.renforcer("un prompt quelconque", [])
    assert prompt == "un prompt quelconque"
    assert manquants == []


def test_un_element_vide_est_ignore():
    prompt, manquants = fidelite_visuelle.renforcer("un prompt", ["", "   "])
    assert prompt == "un prompt"
    assert manquants == []
