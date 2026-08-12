"""Le filtre déterministe qui décide si un prompt mérite RealismWriter.

Aucun appel IA ici — juste des motifs qui repèrent une description qui
IMPLIQUE du texte lisible, un logo, ou un visage interdit, sans jamais
déclencher sur un mot isolé anodin.
"""

from __future__ import annotations

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
