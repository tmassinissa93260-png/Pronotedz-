"""Le filtre déterministe qui décide si un prompt mérite RealismWriter.

Aucun appel IA ici — juste des motifs qui repèrent une description qui
IMPLIQUE du texte lisible, un logo, ou un visage interdit, sans jamais
déclencher sur un mot isolé anodin.
"""

from __future__ import annotations

import pytest

from pdz.production import risque_prompt


def test_un_prompt_neutre_ne_declenche_rien():
    raisons = risque_prompt.raisons_de_correction(
        "wide shot of an empty room, cold blue light", visage_interdit=True,
    )
    assert raisons == []


def test_une_conversation_visible_declenche_le_risque_texte():
    raisons = risque_prompt.raisons_de_correction(
        "phone screen showing a conversation visible, close-up", visage_interdit=True,
    )
    assert "texte lisible" in raisons


def test_un_ecran_affichant_du_texte_declenche_le_risque_texte_en_francais():
    raisons = risque_prompt.raisons_de_correction(
        "gros plan sur un écran affichant une notification", visage_interdit=True,
    )
    assert "texte lisible" in raisons


def test_un_logo_declenche_le_risque_logo():
    raisons = risque_prompt.raisons_de_correction(
        "product shot with a visible logo on the packaging", visage_interdit=True,
    )
    assert "logo" in raisons


def test_un_visage_ne_declenche_rien_si_lunivers_lautorise():
    raisons = risque_prompt.raisons_de_correction(
        "close-up on a detailed facial features", visage_interdit=False,
    )
    assert "visage" not in raisons


def test_un_visage_declenche_le_risque_si_lunivers_linterdit():
    raisons = risque_prompt.raisons_de_correction(
        "portrait shot, detailed facial features", visage_interdit=True,
    )
    assert "visage" in raisons


def test_plusieurs_risques_sont_tous_rapportes():
    raisons = risque_prompt.raisons_de_correction(
        "close-up on a screen showing a conversation visible, brand logo in corner",
        visage_interdit=True,
    )
    assert set(raisons) >= {"texte lisible", "logo"}


def test_un_mot_isole_anodin_ne_declenche_pas_de_faux_positif():
    """« texte » seul, hors d'une formule qui l'implique vraiment à
    l'écran, ne doit pas déclencher — sinon presque tout prompt finirait
    par passer par RealismWriter, annulant l'intérêt du filtre."""
    raisons = risque_prompt.raisons_de_correction(
        "a wall covered in graffiti texture, dark alley", visage_interdit=True,
    )
    assert raisons == []


def test_visage_est_interdit_lit_les_consignes_de_lunivers():
    assert risque_prompt.visage_est_interdit(["no human faces, no facial features"])
    assert risque_prompt.visage_est_interdit(["wireframe only"]) is False


def test_visage_est_interdit_reconnait_le_francais():
    assert risque_prompt.visage_est_interdit(["aucun visage reconnaissable"])


# ── Présence humaine non qualifiée : le vrai bug mesuré à l'écran ────────

def test_une_presence_humaine_non_qualifiee_declenche_le_risque():
    """Bug réel (techno-holo) : « a determined man » sans jamais dire
    « visage » ni « face » a quand même produit un visage humain complet,
    détaillé, photoréaliste à l'écran — la consigne générale de l'univers
    ne suffisait pas à l'arrêter."""
    raisons = risque_prompt.raisons_de_correction(
        "a determined man emerges through the data stream, eyes narrowed",
        visage_interdit=True,
    )
    assert "visage" in raisons


def test_une_presence_humaine_ne_declenche_rien_si_lunivers_lautorise():
    raisons = risque_prompt.raisons_de_correction(
        "a determined man emerges through the data stream", visage_interdit=False,
    )
    assert "visage" not in raisons


def test_homme_en_francais_declenche_aussi_le_risque():
    raisons = risque_prompt.raisons_de_correction(
        "un homme se dresse au milieu du réseau numérique", visage_interdit=True,
    )
    assert "visage" in raisons


# ── HUMAN_PRESENCE_RISK : mains, doigts, bras — pas seulement un visage ──

def test_un_doigt_qui_touche_lecran_declenche_le_risque():
    """Bug réel (épisode #56) : « a finger touches an icon » a produit une
    main photoréaliste à peau colorée, sur fond chaud — sans jamais dire
    « man », « woman » ni « face »."""
    raisons = risque_prompt.raisons_de_correction(
        "a finger touches an icon on the screen", visage_interdit=True,
    )
    assert "visage" in raisons


def test_une_main_ne_declenche_rien_si_lunivers_autorise_les_humains():
    raisons = risque_prompt.raisons_de_correction(
        "a hand touches an icon on the screen", visage_interdit=False,
    )
    assert "visage" not in raisons


@pytest.mark.parametrize("mot", ["hand", "fingers", "arm", "wrist", "skin", "palm"])
def test_chaque_mot_de_presence_humaine_declenche_le_risque(mot):
    raisons = risque_prompt.raisons_de_correction(
        f"a close-up of a {mot} reaching toward the light", visage_interdit=True,
    )
    assert "visage" in raisons


# ── SCREEN_TEXT_RISK : formulations indirectes qui produisent du faux texte ─

def test_un_digital_readout_declenche_le_risque_texte():
    raisons = risque_prompt.raisons_de_correction(
        "a wide shot with a digital readout in the corner", visage_interdit=True,
    )
    assert "texte lisible" in raisons


def test_une_legende_de_carte_declenche_le_risque_texte():
    """Bug réel (épisode #56) : une carte des câbles sous-marins avec sa
    légende cartographique a produit du texte illisible partout."""
    raisons = risque_prompt.raisons_de_correction(
        "a realistic map of undersea cables with a map legend", visage_interdit=True,
    )
    assert "texte lisible" in raisons


def test_une_icone_pressee_sans_le_mot_doigt_declenche_le_risque_visage():
    """Bug réel (ep56 plan 5, ep60 plan 0) : « an icon lights up as it is
    pressed » ne nomme jamais une main ni un doigt, et produit pourtant une
    main pleine, photoréaliste, sur un wireframe UI par ailleurs correct."""
    raisons = risque_prompt.raisons_de_correction(
        "an icon lights up as it is pressed on the wireframe panel",
        visage_interdit=True,
    )
    assert "visage" in raisons


def test_un_flux_de_donnees_abstrait_ne_declenche_rien():
    """« data stream » seul reste un motif visuel central de cet univers —
    trop générique pour être un risque de texte, sinon presque tous les
    plans déclencheraient RealismWriter."""
    raisons = risque_prompt.raisons_de_correction(
        "an abstract stream of glowing data particles flowing through the dark",
        visage_interdit=True,
    )
    assert "texte lisible" not in raisons


# ── Risque de marque : bug réel (production #64, logo Tesla non détecté) ──

def test_marque_est_interdite_lit_les_interdits_de_lunivers():
    assert risque_prompt.marque_est_interdite(["marques réelles"])
    assert risque_prompt.marque_est_interdite(["marques automobiles réelles nommées"])
    assert risque_prompt.marque_est_interdite(["violence explicite"]) is False


def test_un_nom_hors_vocabulaire_declenche_le_risque_marque():
    """Reproduit exactement le cas de production #64 : le sujet nomme une
    marque réelle, jamais présente dans le vocabulaire propre de
    l'univers."""
    vocabulaire = risque_prompt.vocabulaire_connu(["narrateur", "Le narrateur", "voix off"])
    raisons = risque_prompt.raisons_de_correction(
        "a Tesla accelerator pedal glowing in the dark",
        visage_interdit=False, marque_interdite=True,
        elements_obligatoires=[], vocabulaire_connu=vocabulaire,
    )
    assert "marque" in raisons


def test_un_mot_du_vocabulaire_de_lunivers_ne_declenche_rien():
    vocabulaire = risque_prompt.vocabulaire_connu(["Strawberina", "strawberina", "fraise"])
    raisons = risque_prompt.raisons_de_correction(
        "Strawberina holds a golden trophy on stage",
        visage_interdit=False, marque_interdite=True,
        elements_obligatoires=[], vocabulaire_connu=vocabulaire,
    )
    assert "marque" not in raisons


def test_le_premier_mot_de_la_phrase_nest_jamais_un_signal_seul():
    vocabulaire = risque_prompt.vocabulaire_connu([])
    raisons = risque_prompt.raisons_de_correction(
        "Wide shot of an empty wireframe room",
        visage_interdit=False, marque_interdite=True,
        elements_obligatoires=[], vocabulaire_connu=vocabulaire,
    )
    assert "marque" not in raisons


def test_le_risque_marque_najamais_sans_le_vocabulaire_fourni():
    """Défaut inerte : sans vocabulaire_connu explicite, aucun risque de
    marque n'est jamais évalué — rétrocompatible avec tout appel existant."""
    raisons = risque_prompt.raisons_de_correction(
        "a Tesla accelerator pedal", visage_interdit=False, marque_interdite=True,
    )
    assert "marque" not in raisons


def test_mots_hors_vocabulaire_scanne_aussi_les_elements_obligatoires():
    vocabulaire = risque_prompt.vocabulaire_connu([])
    trouves = risque_prompt.mots_hors_vocabulaire(
        "a wide shot of a car", ["Tesla logo"], vocabulaire,
    )
    assert "Tesla" in trouves
