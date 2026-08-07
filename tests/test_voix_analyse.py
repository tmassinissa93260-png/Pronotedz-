"""Mesure de voix : on fabrique un son dont on connaît la hauteur, on vérifie.

Un détecteur de hauteur qui se trompe de 15 % ne se voit pas à l'œil nu dans
un rapport — il se voit six mois plus tard, quand tous les personnages ont
reçu la même voix parce que toutes les distances se valaient. D'où des tests
sur des signaux dont la vérité est connue au hertz près.
"""

from __future__ import annotations

import subprocess

import pytest

from pdz.analyse import voix
from pdz.moteur.erreurs import ErreurPdz


def _son(tmp_path, expression: str, duree: float = 5.0, nom: str = "s.wav"):
    chemin = tmp_path / nom
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", f"aevalsrc='{expression}':d={duree}:s=44100",
         "-ac", "1", str(chemin)],
        check=True, timeout=120,
    )
    return chemin


def _voyelle(f0: float) -> str:
    """Un son harmonique : une fondamentale et ses deux premiers harmoniques.

    Une sinusoïde pure serait plus facile à suivre que la réalité ; des
    harmoniques exposent le piège classique de l'autocorrélation, qui est de
    verrouiller sur l'octave au lieu de la fondamentale.
    """
    return (f"0.5*sin(2*PI*{f0}*t)+0.32*sin(2*PI*{2 * f0}*t)"
            f"+0.18*sin(2*PI*{3 * f0}*t)")


# ── Hauteur ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("f0", [95.0, 140.0, 200.0, 260.0])
def test_la_hauteur_est_retrouvee_au_hertz_pres(tmp_path, f0):
    chemin = _son(tmp_path, _voyelle(f0), nom=f"f{int(f0)}.wav")
    profil = voix.analyser(chemin)
    assert abs(profil.hauteur_hz - f0) < 2.0, profil.resume()


def test_la_hauteur_ne_verrouille_pas_sur_loctave(tmp_path):
    """Avec des harmoniques forts, un détecteur naïf renvoie 2×f0."""
    chemin = _son(tmp_path, _voyelle(120.0))
    profil = voix.analyser(chemin)
    assert 115 < profil.hauteur_hz < 125, profil.hauteur_hz


def test_le_registre_est_nomme_correctement(tmp_path):
    grave = voix.analyser(_son(tmp_path, _voyelle(100.0), nom="g.wav"))
    aigu = voix.analyser(_son(tmp_path, _voyelle(255.0), nom="a.wav"))
    assert grave.registre in ("très grave", "grave")
    assert aigu.registre in ("aigu", "très aigu")


# ── Débit ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("cadence", [3.0, 4.0, 6.0])
def test_le_debit_syllabique_suit_la_cadence(tmp_path, cadence):
    """Une modulation à N Hz vaut N syllabes par seconde, par construction."""
    expr = f"(0.55+0.45*sin(2*PI*{cadence}*t))*({_voyelle(150.0)})"
    profil = voix.analyser(_son(tmp_path, expr, duree=6.0, nom=f"c{cadence}.wav"))
    assert abs(profil.debit_syllabes_s - cadence) < cadence * 0.15, profil.resume()


def test_un_son_tenu_ne_compte_aucune_syllabe(tmp_path):
    """Sans modulation, il n'y a pas de noyau syllabique à compter.

    C'est le défaut qu'attrape la règle du creux de 4 dB : sans elle, une
    voyelle tenue est comptée cinq fois.
    """
    profil = voix.analyser(_son(tmp_path, _voyelle(150.0), duree=5.0))
    assert profil.debit_syllabes_s < 1.0, profil.debit_syllabes_s


# ── Comparaison ──────────────────────────────────────────────────────────

def test_deux_voix_proches_sont_plus_proches_que_deux_eloignees(tmp_path):
    a = voix.analyser(_son(tmp_path, _voyelle(120.0), nom="a.wav"))
    b = voix.analyser(_son(tmp_path, _voyelle(128.0), nom="b.wav"))
    c = voix.analyser(_son(tmp_path, _voyelle(240.0), nom="c.wav"))

    assert a.distance(b) < a.distance(c)
    assert a.distance(a) == 0.0


def test_la_distance_est_symetrique(tmp_path):
    a = voix.analyser(_son(tmp_path, _voyelle(130.0), nom="a.wav"))
    b = voix.analyser(_son(tmp_path, _voyelle(190.0), nom="b.wav"))
    assert a.distance(b) == pytest.approx(b.distance(a), abs=0.01)


def test_la_distance_est_en_demi_tons_pas_en_hertz(tmp_path):
    """20 Hz d'écart n'ont pas le même sens à 100 Hz qu'à 250 Hz.

    Une distance en hertz jugerait ces deux paires identiques ; l'oreille non
    (un ton et demi contre un demi-ton).
    """
    grave_a = voix.analyser(_son(tmp_path, _voyelle(100.0), nom="ga.wav"))
    grave_b = voix.analyser(_son(tmp_path, _voyelle(120.0), nom="gb.wav"))
    aigu_a = voix.analyser(_son(tmp_path, _voyelle(250.0), nom="aa.wav"))
    aigu_b = voix.analyser(_son(tmp_path, _voyelle(270.0), nom="ab.wav"))

    assert grave_a.distance(grave_b) > aigu_a.distance(aigu_b) * 1.5


# ── Réglages ─────────────────────────────────────────────────────────────

def test_les_reglages_restent_dans_les_bornes_utilisables(tmp_path):
    profil = voix.analyser(_son(tmp_path, _voyelle(150.0)))
    r = profil.vers_reglages()
    assert 0.15 <= r["stabilite"] <= 0.9
    assert 0.05 <= r["style"] <= 0.9
    # ±25 % : au-delà, ElevenLabs étire la voix de façon audible.
    assert 0.75 <= r["vitesse"] <= 1.25


def test_une_voix_monocorde_demande_peu_de_style(tmp_path):
    profil = voix.analyser(_son(tmp_path, _voyelle(150.0)))
    assert profil.vers_reglages()["style"] < 0.2


# ── Échecs propres ───────────────────────────────────────────────────────

def test_un_silence_ne_produit_pas_une_voix_inventee(tmp_path):
    chemin = _son(tmp_path, "0.00001*sin(2*PI*300*t)", duree=3.0, nom="vide.wav")
    with pytest.raises(ErreurPdz) as e:
        voix.analyser(chemin)
    assert "voix" in str(e.value).lower()


def test_un_extrait_trop_court_le_dit(tmp_path):
    chemin = _son(tmp_path, _voyelle(150.0), duree=0.01, nom="court.wav")
    with pytest.raises(ErreurPdz) as e:
        voix.analyser(chemin)
    assert "court" in str(e.value)


def test_un_fichier_absent_echoue_avant_ffmpeg(tmp_path):
    with pytest.raises(ErreurPdz) as e:
        voix.analyser(tmp_path / "rien.wav")
    assert "introuvable" in str(e.value)
