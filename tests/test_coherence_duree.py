"""coherence_duree : la vidéo produite doit durer aussi longtemps que la voix.

Zéro appel IA — juste ffprobe et une soustraction. Voir le bug réel qui a
motivé ce module : 28,1 s de vidéo pour 42,7 s de voix, sans une seule
erreur nulle part.
"""

from __future__ import annotations

from pdz.production import coherence_duree


def test_une_duree_qui_colle_ne_declenche_rien():
    assert coherence_duree.message_si_incoherent(42.7, 42.5, contexte="Voix") is None


def test_un_petit_ecart_dans_la_tolerance_ne_declenche_rien():
    assert coherence_duree.message_si_incoherent(42.0, 42.9, contexte="Voix") is None


def test_un_grand_ecart_declenche_un_message():
    msg = coherence_duree.message_si_incoherent(42.7, 28.1, contexte="Voix")
    assert msg is not None
    assert "Voix" in msg
    assert "42.7" in msg
    assert "28.1" in msg


def test_le_message_rapporte_lecart_absolu_quel_que_soit_le_sens():
    plus_court = coherence_duree.message_si_incoherent(10.0, 20.0, contexte="Montage")
    plus_long = coherence_duree.message_si_incoherent(20.0, 10.0, contexte="Montage")
    assert plus_court is not None and plus_long is not None
    assert "10.0" in plus_court and "10.0" in plus_long


def test_ecart_est_toujours_positif():
    assert coherence_duree.ecart(10.0, 8.0) == coherence_duree.ecart(8.0, 10.0) == 2.0


# ── Vidéo finale : flux vidéo et flux audio comparés séparément ──────────
# Jamais `format.duration` — voir pdz/analyse/sonde.py et le bug réel :
# un fichier où la vidéo s'arrête avant l'audio fait quand même remonter
# `format.duration` = la durée de l'audio (le flux le plus long).

def test_video_et_audio_coherents_ne_declenchent_rien():
    assert coherence_duree.message_si_video_finale_incoherente(
        28.5, video_s=28.5, audio_s=28.5,
    ) is None


def test_une_video_trop_courte_declenche_un_message():
    msg = coherence_duree.message_si_video_finale_incoherente(
        28.5, video_s=24.1, audio_s=28.58,
    )
    assert msg is not None
    assert "trop courte" in msg


def test_un_audio_plus_long_que_la_video_declenche_un_message():
    msg = coherence_duree.message_si_video_finale_incoherente(
        28.5, video_s=24.1, audio_s=28.58,
    )
    assert msg is not None


def test_une_video_plus_longue_que_lattendu_ne_declenche_rien():
    """Seule une vidéo trop COURTE ou un audio qui la dépasse comptent —
    une vidéo plus longue que prévu n'est pas le défaut visé ici."""
    assert coherence_duree.message_si_video_finale_incoherente(
        20.0, video_s=25.0, audio_s=20.0,
    ) is None
