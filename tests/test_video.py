"""Sous-titres karaoké et construction du montage.

Aucun appel réseau, aucun coût : tout est du calcul de temps et de chaînes.
"""

from pathlib import Path

import pytest

from pdz.moteur.erreurs import ErreurPdz
from pdz.video import Montage, Mouvement, Plan, generer_ass, mots_depuis_texte
from pdz.video.soustitres import Mot, StyleSousTitres, decouper_en_cartes

# ── Sous-titres ──────────────────────────────────────────────────────────

def test_les_mots_couvrent_exactement_la_duree():
    mots = mots_depuis_texte("Tu savais depuis le début", 1000, 2000)
    assert mots[0].debut_ms == 1000
    assert mots[-1].fin_ms == 3000
    # Aucun trou ni chevauchement entre deux mots consécutifs.
    for a, b in zip(mots, mots[1:], strict=False):
        assert a.fin_ms == b.debut_ms


def test_les_mots_longs_durent_plus_longtemps():
    """Répartir la durée également donnerait un karaoké décalé du son."""
    mots = mots_depuis_texte("a incompréhensible", 0, 2000)
    assert mots[1].duree_cs > mots[0].duree_cs


def test_la_ponctuation_coupe_la_carte():
    mots = [Mot(t, i * 100, i * 100 + 100)
            for i, t in enumerate(["Bien.", "Mais", "non"])]
    cartes = decouper_en_cartes(mots, par_carte=3)
    assert len(cartes) == 2, "« Bien. » doit finir sa carte"


def test_le_ass_contient_les_balises_karaoke():
    ass = generer_ass(mots_depuis_texte("un deux trois", 0, 1500))
    assert "[V4+ Styles]" in ass and "Dialogue:" in ass
    assert ass.count("\\k") == 3, "une balise \\k par mot"


def test_le_texte_reste_au_dessus_des_boutons_tiktok():
    """La marge basse doit laisser passer l'interface de la plateforme."""
    ass = generer_ass([Mot("x", 0, 500)], hauteur=1920)
    ligne = next(x for x in ass.splitlines() if x.startswith("Style:"))
    marge_basse = int(ligne.split(",")[-2])
    assert 600 <= marge_basse <= 850, marge_basse


def test_un_mot_trop_long_est_retreci():
    """Un mot qui sort du cadre est un défaut visible immédiatement.

    Le cas arrive dès qu'on affiche un mot à la fois : « quatre-vingt-trois »
    à 150 px déborde d'un écran de 1080.
    """
    st = StyleSousTitres(taille=150, mots_par_carte=1)
    assert st.taille_pour("BIP", 1080) == 150
    assert st.taille_pour("QUATRE-VINGT-TROIS", 1080) < 150
    # Après réduction, le mot doit tenir dans la largeur utile.
    t = st.taille_pour("QUATRE-VINGT-TROIS", 1080)
    assert len("QUATRE-VINGT-TROIS") * t * st.largeur_caractere <= 1080 - 2 * st.marge_laterale


def test_le_retrecissement_est_ecrit_dans_le_ass():
    st = StyleSousTitres(taille=150, mots_par_carte=1)
    ass = generer_ass(mots_depuis_texte("bip quatre-vingt-trois", 0, 2000), style=st)
    lignes = [x for x in ass.splitlines() if x.startswith("Dialogue")]
    assert "\\fs" not in lignes[0], "un mot court ne doit pas être retouché"
    assert "\\fs" in lignes[1], "un mot long doit porter une taille réduite"


def test_le_mode_majuscules():
    st = StyleSousTitres(majuscules=True, mots_par_carte=1)
    ass = generer_ass(mots_depuis_texte("spoutnik", 0, 500), style=st)
    assert "SPOUTNIK" in ass and "spoutnik" not in ass


def test_par_defaut_le_texte_nest_pas_transforme():
    ass = generer_ass(mots_depuis_texte("Spoutnik", 0, 500))
    assert "Spoutnik" in ass


# ── Montage ──────────────────────────────────────────────────────────────

@pytest.fixture
def image(tmp_path):
    from PIL import Image
    p = tmp_path / "img.jpg"
    Image.new("RGB", (1458, 2592), (200, 60, 80)).save(p)
    return p


def test_le_filtre_lent_nest_jamais_utilise(image):
    """Garde-fou de performance.

    Le filtre `zoompan` de ffmpeg, que recommandent la plupart des tutoriels,
    coûte 8 à 14× le temps réel. L'approche par recadrage mobile coûte 0,33×.
    Si quelqu'un le réintroduit un jour, ce test le rattrape.

    On n'inspecte que la chaîne de filtres : les chemins de fichiers de pytest
    contiennent le nom du test, donc le mot recherché.
    """
    m = Montage(plans=[Plan(image, 2.0, mv) for mv in Mouvement])
    cmd = m.commande(Path("/tmp/x.mp4"))
    filtres = cmd[cmd.index("-filter_complex") + 1]
    assert "zoompan" not in filtres
    assert "crop=" in filtres


def test_chaque_mouvement_produit_un_filtre_valide(image):
    for mv in Mouvement:
        m = Montage(plans=[Plan(image, 2.0, mv)])
        cmd = m.commande(Path("/tmp/x.mp4"))
        filtres = cmd[cmd.index("-filter_complex") + 1]
        assert "setsar=1" in filtres, f"{mv} : SAR non forcé → concat échouera"
        assert "[v0]" in filtres


def test_les_mouvements_alternent():
    """Le même zoom sur tous les plans trahit la génération automatique."""
    quatre = [Mouvement.alterne(i) for i in range(4)]
    assert len(set(quatre)) == 4
    assert Mouvement.alterne(0) is Mouvement.alterne(4)


def test_la_duree_est_la_somme_des_plans(image):
    m = Montage(plans=[Plan(image, 1.5), Plan(image, 2.5)])
    assert m.duree_s == 4.0


def test_le_son_est_normalise(image, tmp_path):
    """-14 LUFS : une vidéo trop faible ou saturée est zappée en une seconde."""
    voix = tmp_path / "v.wav"
    voix.write_bytes(b"RIFF")
    m = Montage(plans=[Plan(image, 2.0)], voix=voix)
    filtres = " ".join(m.commande(Path("/tmp/x.mp4")))
    assert "loudnorm=I=-14" in filtres


def test_un_montage_vide_echoue_clairement():
    with pytest.raises(ErreurPdz, match="aucun plan"):
        Montage().commande(Path("/tmp/x.mp4"))


def test_une_image_absente_est_signalee(tmp_path):
    m = Montage(plans=[Plan(tmp_path / "fantome.jpg", 2.0)])
    with pytest.raises(ErreurPdz, match="introuvable"):
        m.commande(Path("/tmp/x.mp4"))
