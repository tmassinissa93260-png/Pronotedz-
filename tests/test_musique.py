"""Reconnaissance de musique : séparer la parole, mesurer, identifier.

Comme pour la voix, on fabrique des signaux dont on connaît la vérité — un
accord de La mineur à 120 BPM avec de la parole par-dessus entre la 4e et la
10e seconde — et on vérifie que la mesure la retrouve. C'est la seule façon de
savoir si le découpage parole/musique vaut quelque chose : sur une vraie
vidéo, personne ne sait où sont les frontières.
"""

from __future__ import annotations

import wave

import numpy as np
import pytest

from pdz.analyse import musique
from pdz.ia import audd
from pdz.moteur.erreurs import ErreurPdz, ErreurQuota, ErreurRefus

TAUX = 44100


def _ecrire(chemin, signal):
    signal = signal / max(1e-9, np.abs(signal).max()) * 0.85
    with wave.open(str(chemin), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TAUX)
        w.writeframes((signal * 32767).astype(np.int16).tobytes())
    return chemin


def _musique(duree, bpm=120, tonique=220.0):
    """Un accord mineur tenu, plus un kick au tempo demandé.

    La tonique par défaut est un La : l'accord La-Do-Mi est donc La mineur,
    ce que la détection de tonalité doit retrouver.
    """
    n = int(duree * TAUX)
    t = np.arange(n) / TAUX
    accord = sum(np.sin(2 * np.pi * f * t) * a for f, a in (
        (tonique, .35), (tonique * 1.1892, .30),      # tierce mineure
        (tonique * 1.4983, .25), (tonique * 2, .12),  # quinte, octave
    ))
    kick = (np.sin(2 * np.pi * (bpm / 60) * t) > 0.9) * np.sin(2 * np.pi * 60 * t)
    return accord * 0.5 + kick * 0.5


def _parole(duree, syllabes_hz=4.5):
    n = int(duree * TAUX)
    t = np.arange(n) / TAUX
    enveloppe = np.clip(0.5 + 0.5 * np.sin(2 * np.pi * syllabes_hz * t), 0, None)
    return enveloppe * sum(np.sin(2 * np.pi * f * t) * a
                           for f, a in ((150, .5), (300, .3), (450, .15)))


def _melange(tmp_path, bpm=120, syllabes_hz=4.5, nom="melange.wav"):
    """4 s de musique · 6 s de musique + parole · 3 s de musique."""
    return _ecrire(tmp_path / nom, np.concatenate([
        _musique(4.0, bpm),
        _musique(6.0, bpm) + _parole(6.0, syllabes_hz) * 1.4,
        _musique(3.0, bpm),
    ]))


# ── Séparer la parole de la musique ──────────────────────────────────────

def test_les_passages_sans_parole_sont_trouves(tmp_path):
    a = musique.analyser(_melange(tmp_path))
    assert a.passages, "aucun passage instrumental trouvé"
    premier = a.passages[0]
    assert premier.debut_s < 1.0
    assert 3.0 < premier.fin_s < 4.6, premier


def test_un_passage_ne_deborde_pas_sur_la_parole(tmp_path):
    """Le point qui décide de la réussite : un reste de voix dans l'extrait
    fait échouer la reconnaissance, et l'appel est facturé quand même."""
    a = musique.analyser(_melange(tmp_path))
    parle = (4.0, 10.0)
    for p in a.passages:
        chevauche = min(p.fin_s, parle[1]) - max(p.debut_s, parle[0])
        assert chevauche < 1.0, f"{p} déborde de {chevauche:.1f} s sur la parole"


@pytest.mark.parametrize("bpm", [90, 120, 140])
def test_la_separation_tient_a_tous_les_tempos(tmp_path, bpm):
    """Un seuil fixe se trompait ici : la musique seule monte de 0,43 à 0,46
    selon son tempo, et croise la parole lente."""
    a = musique.analyser(_melange(tmp_path, bpm=bpm, nom=f"t{bpm}.wav"))
    assert a.passages
    assert a.passages[0].debut_s < 1.0


def test_de_la_parole_seule_ne_donne_aucun_passage(tmp_path):
    chemin = _ecrire(tmp_path / "voix.wav", _parole(8.0))
    a = musique.analyser(chemin)
    assert a.passages == []
    assert not a.y_a_de_la_musique


def test_de_la_musique_seule_est_instrumentale_de_bout_en_bout(tmp_path):
    chemin = _ecrire(tmp_path / "mus.wav", _musique(8.0))
    a = musique.analyser(chemin)
    assert a.y_a_de_la_musique
    assert a.part_instrumentale > 0.7, a.part_instrumentale


def test_une_video_homogene_le_signale_par_une_separation_nulle(tmp_path):
    """Rien à séparer n'est pas la même chose que « je sais séparer »."""
    chemin = _ecrire(tmp_path / "mus.wav", _musique(8.0))
    assert musique.analyser(chemin).separation < musique.ECART_MINIMAL


def test_un_melange_donne_une_separation_nette(tmp_path):
    assert musique.analyser(_melange(tmp_path)).separation >= musique.ECART_MINIMAL


def test_une_hesitation_isolee_ne_cree_pas_de_passage(tmp_path):
    """Le vote majoritaire : une fenêtre ambiguë au milieu de la parole ne
    doit pas ouvrir un faux passage instrumental d'une seconde."""
    a = musique.analyser(_melange(tmp_path))
    for p in a.passages:
        assert p.duree_s >= musique.DUREE_MIN_PASSAGE_S


# ── Mesures ──────────────────────────────────────────────────────────────

def test_la_tonalite_est_retrouvee(tmp_path):
    chemin = _ecrire(tmp_path / "lam.wav", _musique(8.0, tonique=220.0))
    a = musique.analyser(chemin)
    assert a.tonalite.startswith("La"), a.tonalite
    assert "mineur" in a.tonalite


def test_changer_de_tonique_change_la_tonalite(tmp_path):
    la = musique.analyser(_ecrire(tmp_path / "a.wav", _musique(8.0, tonique=220.0)))
    re = musique.analyser(_ecrire(tmp_path / "d.wav", _musique(8.0, tonique=293.66)))
    assert la.tonalite != re.tonalite, (la.tonalite, re.tonalite)


def test_un_signal_sans_hauteur_ne_pretend_pas_avoir_de_tonalite():
    nom, confiance = musique.tonalite(np.zeros(12))
    assert nom == "indéterminée"
    assert confiance == 0.0


def test_un_chroma_plat_a_une_confiance_basse():
    """Un chroma uniforme corrèle correctement avec les 24 tonalités : c'est
    l'écart avec la deuxième, pas la corrélation brute, qui fait la confiance."""
    _, confiance = musique.tonalite(np.full(12, 1 / 12) + np.random.default_rng(0).normal(0, 1e-6, 12))
    assert confiance < 0.3


@pytest.mark.parametrize("bpm", [90, 120])
def test_le_tempo_est_retrouve(tmp_path, bpm):
    chemin = _ecrire(tmp_path / f"b{bpm}.wav", _musique(10.0, bpm=bpm))
    a = musique.analyser(chemin)
    assert a.tempo_bpm is not None
    assert abs(a.tempo_bpm - bpm) < bpm * 0.1, a.tempo_bpm


def test_la_recherche_de_musique_libre_donne_des_criteres(tmp_path):
    a = musique.analyser(_melange(tmp_path))
    texte = a.pour_chercher_une_musique_libre()
    assert "BPM" in texte


# ── Extraction de l'échantillon ──────────────────────────────────────────

def test_lechantillon_est_pris_dans_un_passage_sans_parole(tmp_path):
    chemin = _melange(tmp_path)
    a = musique.analyser(chemin)
    extrait, raison = musique.extraire_echantillon(chemin, tmp_path / "e.mp3", a)
    assert extrait.exists() and extrait.stat().st_size > 1000
    assert "sans parole" in raison


def test_sans_passage_la_commande_le_dit_au_lieu_de_faire_semblant(tmp_path):
    chemin = _ecrire(tmp_path / "voix.wav", _parole(8.0))
    a = musique.analyser(chemin)
    _, raison = musique.extraire_echantillon(chemin, tmp_path / "e.mp3", a)
    assert "moins fiable" in raison


def test_un_fichier_absent_echoue_clairement(tmp_path):
    with pytest.raises(ErreurPdz) as e:
        musique.analyser(tmp_path / "rien.wav")
    assert "introuvable" in str(e.value)


# ── Sans musique, on n'appelle pas le service payant ─────────────────────

def test_aucune_musique_donc_aucun_appel_facture(tmp_path, monkeypatch):
    """L'appel est facturé même quand rien n'est trouvé : sur une piste sans
    musique, le lancer serait payer pour un échec certain."""
    appels = []
    monkeypatch.setattr("pdz.ia.audd.identifier",
                        lambda *a, **k: appels.append(1))

    chemin = _ecrire(tmp_path / "voix.wav", _parole(8.0))
    r = musique.reconnaitre(chemin, dossier=tmp_path)

    assert appels == []
    assert not r.identifie
    assert "Aucune musique" in r.echec_identification


def test_une_identification_ratee_nemporte_pas_les_mesures(tmp_path, monkeypatch):
    def echoue(*a, **k):
        raise ErreurQuota("plus de requêtes")

    monkeypatch.setattr("pdz.ia.audd.identifier", echoue)
    r = musique.reconnaitre(_melange(tmp_path), dossier=tmp_path)

    assert not r.identifie
    assert "ErreurQuota" in r.echec_identification
    assert r.analyse.tempo_bpm is not None       # les mesures sont là
    assert r.analyse.passages


# ── Lecture des réponses AudD ────────────────────────────────────────────

def test_une_reponse_complete_est_lue():
    m = audd.morceau_depuis({
        "status": "success",
        "result": {
            "artist": "Machinedrum", "title": "Sunset Drive",
            "album": "Human Energy", "release_date": "2016-09-16",
            "label": "Ninja Tune", "timecode": "00:31",
            "song_link": "https://lis.tn/abc",
            "spotify": {"external_urls": {"spotify": "https://open.spotify.com/x"}},
            "apple_music": {"url": "https://music.apple.com/y"},
        },
    })
    assert m.titre == "Sunset Drive"
    assert m.artiste == "Machinedrum"
    assert m.spotify.startswith("https://open.spotify.com")
    assert m.apple_music.startswith("https://music.apple.com")
    assert "Ninja Tune" in m.resume()


def test_aucun_resultat_nest_pas_une_erreur():
    """Le cas le plus courant sur une musique libre de droits."""
    assert audd.morceau_depuis({"status": "success", "result": None}) is None


def test_une_reponse_partielle_ne_casse_pas():
    """Les blocs spotify/apple_music n'existent que si on les a demandés."""
    m = audd.morceau_depuis({"result": {"title": "X", "artist": "Y"}})
    assert m.titre == "X" and m.spotify == "" and m.apple_music == ""


def test_un_bloc_spotify_deforme_ne_casse_pas():
    m = audd.morceau_depuis({"result": {"title": "X", "artist": "Y",
                                        "spotify": "pas un objet"}})
    assert m.spotify == ""


def test_un_extrait_trop_lourd_est_refuse_avant_lenvoi(tmp_path):
    gros = tmp_path / "gros.mp3"
    gros.write_bytes(b"\0" * (audd.TAILLE_MAX_OCTETS + 1))
    with pytest.raises(Exception) as e:
        audd.identifier(gros)
    assert "10 Mo" in str(e.value)


def test_une_cle_absente_explique_quoi_faire(tmp_path, monkeypatch):
    monkeypatch.setenv("DONNEES", str(tmp_path))
    from pdz.config import config
    config.cache_clear()

    petit = tmp_path / "p.mp3"
    petit.write_bytes(b"\0" * 100)
    with pytest.raises(Exception) as e:
        audd.identifier(petit)
    message = str(e.value)
    assert "audd.io" in message
    assert "tempo" in message          # dit ce qui marche quand même
    config.cache_clear()


def test_les_codes_derreur_audd_sont_traduits():
    """Un code 901 doit devenir « recharge ton compte », pas « erreur 901 »."""
    message, classe = audd.MESSAGES[901]
    assert classe is ErreurQuota
    assert "300" in message

    message, classe = audd.MESSAGES[900]
    assert classe is ErreurRefus
    assert "AUDD_API_KEY" in message
