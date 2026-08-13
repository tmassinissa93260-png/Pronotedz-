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
