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


# ── exclure() : pas de canal negative_prompt chez Flux, donc en texte ────

def test_exclure_ajoute_les_elements_au_prompt():
    prompt = fidelite_visuelle.exclure("a wide shot of a city", ["smartphone", "human"])
    assert prompt == "a wide shot of a city, no smartphone, no human"


def test_exclure_sans_element_ne_change_rien():
    prompt = fidelite_visuelle.exclure("a wide shot of a city", [])
    assert prompt == "a wide shot of a city"


def test_exclure_ignore_les_elements_vides():
    prompt = fidelite_visuelle.exclure("un prompt", ["", "  "])
    assert prompt == "un prompt"


# ── assainir() : le filet contre un verdict QA hors format ───────────────

def test_assainir_garde_un_court_token_anglais_valide():
    assert fidelite_visuelle.assainir(["submarine cable"]) == ["submarine cable"]
    assert fidelite_visuelle.assainir(["laptop"]) == ["laptop"]


def test_assainir_rejette_une_phrase_francaise_reconstruite_de_laudit():
    """Cas réel reconstruit (audit 2, ep56/ep62) : le verdict QA renvoie une
    phrase française entière au lieu d'un court mot-clé anglais."""
    phrase = ("une main humaine qui touche l'écran alors qu'aucune main ne "
              "devrait être visible dans ce plan")
    assert fidelite_visuelle.assainir([phrase]) == []


def test_assainir_rejette_plus_de_quatre_mots():
    assert fidelite_visuelle.assainir(["a very long descriptive phrase here"]) == []


def test_assainir_rejette_un_caractere_accentue():
    assert fidelite_visuelle.assainir(["écran affiché"]) == []


def test_assainir_rejette_un_mot_vide_francais_meme_court():
    assert fidelite_visuelle.assainir(["dans le cadre"]) == []


def test_assainir_ignore_les_elements_vides():
    assert fidelite_visuelle.assainir(["", "   "]) == []


def test_assainir_garde_les_valides_et_rejette_les_autres():
    resultat = fidelite_visuelle.assainir(["submarine cable", "une phrase française trop longue à rejeter"])
    assert resultat == ["submarine cable"]


# ── renforcer_libre() : des clauses complètes, pas des objets à nommer ───

def test_renforcer_libre_ajoute_une_clause_absente():
    prompt, ajoutees = fidelite_visuelle.renforcer_libre(
        "an accelerator pedal glowing in the dark",
        ["no manufacturer badge, no logo, unbranded design"],
    )
    assert "no manufacturer badge, no logo, unbranded design" in prompt
    assert ajoutees == ["no manufacturer badge, no logo, unbranded design"]


def test_renforcer_libre_najoute_rien_si_deja_present():
    prompt, ajoutees = fidelite_visuelle.renforcer_libre(
        "a pedal, no manufacturer badge, no logo, unbranded design",
        ["no manufacturer badge, no logo, unbranded design"],
    )
    assert prompt == "a pedal, no manufacturer badge, no logo, unbranded design"
    assert ajoutees == []


def test_renforcer_libre_najamais_le_prefixe_featuring():
    prompt, _ = fidelite_visuelle.renforcer_libre(
        "a pedal", ["mechanical actuator only, no visible human hand"],
    )
    assert "featuring" not in prompt
