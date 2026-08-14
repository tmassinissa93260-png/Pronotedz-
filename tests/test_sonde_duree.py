"""sonder() doit lire la durée du flux VIDÉO, pas `format.duration`.

Bug réel (audit de l'épisode #56) : un fichier dont la piste vidéo
s'arrête avant la piste audio (un clip animé plus court que prévu) fait
quand même remonter `format.duration` = la durée de l'AUDIO, le flux le
plus long. Un garde-fou qui comparait à `format.duration` n'a donc rien vu,
alors que la vidéo était réellement tronquée de 4,5 s.
"""

from __future__ import annotations

import subprocess

from pdz.analyse.sonde import sonder


def _video_video_plus_courte_que_laudio(chemin, *, duree_video=2.0, duree_audio=4.0):
    """Piste vidéo et piste audio de durées différentes, sans -shortest —
    exactement la forme du fichier réellement livré en production."""
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-t", str(duree_video), "-i", "color=c=red:s=320x240:r=25",
        "-f", "lavfi", "-t", str(duree_audio), "-i", "sine=frequency=440",
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", str(chemin),
    ], check=True, capture_output=True)
    return chemin


def test_la_duree_rapportee_est_celle_du_flux_video_pas_du_conteneur(tmp_path):
    v = _video_video_plus_courte_que_laudio(tmp_path / "tronque.mp4")
    m = sonder(v)
    assert 1.8 < m.duree_s < 2.2, (
        f"duree_s={m.duree_s} — devrait être ~2.0 s (le flux vidéo), pas "
        f"~4.0 s (format.duration, piloté par le flux audio le plus long)"
    )


def test_la_duree_audio_est_rapportee_separement(tmp_path):
    v = _video_video_plus_courte_que_laudio(tmp_path / "tronque.mp4")
    m = sonder(v)
    assert 3.8 < m.duree_audio_s < 4.2
    assert m.duree_audio_s > m.duree_s


def test_une_video_bien_formee_garde_les_deux_durees_egales(tmp_path):
    v = _video_video_plus_courte_que_laudio(
        tmp_path / "ok.mp4", duree_video=3.0, duree_audio=3.0,
    )
    m = sonder(v)
    assert abs(m.duree_s - m.duree_audio_s) < 0.2
