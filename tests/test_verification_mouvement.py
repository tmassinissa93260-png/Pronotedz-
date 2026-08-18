"""verification_mouvement.verifier() : un clip peut être un fichier vidéo
valide, de la bonne durée, et pourtant visuellement statique — « API 200 »
et « fichier livré » ne prouvent jamais qu'une image a réellement changé
d'une frame à l'autre (enquête run #66). Zéro appel IA : ffprobe/ffmpeg +
différence de pixels en niveaux de gris.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from pdz.production import verification_mouvement as vm


def _clip_statique(destination: Path, *, duree_s: float = 2.0) -> None:
    """Même image répétée — aucun mouvement, par construction."""
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-t", str(duree_s), "-i", "color=c=blue:s=64x64:r=10",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        str(destination),
    ], check=True, capture_output=True)


def _clip_anime(destination: Path, *, duree_s: float = 2.0) -> None:
    """Motif animé — un vrai déplacement d'une frame à l'autre."""
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-t", str(duree_s), "-i", f"testsrc=size=64x64:rate=10",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        str(destination),
    ], check=True, capture_output=True)


def test_un_clip_statique_nest_pas_detecte_comme_anime(tmp_path):
    clip = tmp_path / "statique.mp4"
    _clip_statique(clip)

    verdict = vm.verifier(clip)

    assert verdict.fichier_valide is True
    assert verdict.mouvement_detecte is False
    assert verdict.raison == "static_clip"


def test_un_clip_avec_mouvement_reel_est_detecte(tmp_path):
    clip = tmp_path / "anime.mp4"
    _clip_anime(clip)

    verdict = vm.verifier(clip)

    assert verdict.fichier_valide is True
    assert verdict.mouvement_detecte is True
    assert verdict.raison == "ok"


def test_un_fichier_inexistant_est_invalide(tmp_path):
    verdict = vm.verifier(tmp_path / "inexistant.mp4")

    assert verdict.fichier_valide is False
    assert verdict.raison == "fichier_invalide"


def test_un_fichier_non_video_est_invalide(tmp_path):
    faux = tmp_path / "pas_une_video.mp4"
    faux.write_text("ceci n'est pas un fichier vidéo")

    verdict = vm.verifier(faux)

    assert verdict.fichier_valide is False
    assert verdict.raison == "fichier_invalide"


def test_le_verdict_porte_la_duree_et_le_fps_mesures(tmp_path):
    clip = tmp_path / "anime.mp4"
    _clip_anime(clip, duree_s=3.0)

    verdict = vm.verifier(clip)

    assert verdict.duree_s == pytest.approx(3.0, abs=0.2)
    assert verdict.fps == pytest.approx(10.0, abs=0.5)


def test_verifier_segment_isole_une_fenetre_dune_video_deja_montee(tmp_path):
    """`qa_video_finale` a besoin d'extraire UNE fenêtre d'une vidéo déjà
    concaténée — sans redécouper les coupes, les bornes sont déjà connues."""
    statique = tmp_path / "statique.mp4"
    anime = tmp_path / "anime.mp4"
    combo = tmp_path / "combo.mp4"
    _clip_statique(statique, duree_s=2.0)
    _clip_anime(anime, duree_s=2.0)
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(statique), "-i", str(anime),
        "-filter_complex",
        "[0:v]trim=duration=2,setpts=PTS-STARTPTS[v0];"
        "[1:v]trim=duration=2,setpts=PTS-STARTPTS[v1];"
        "[v0][v1]concat=n=2:v=1:a=0[v]",
        "-map", "[v]", str(combo),
    ], check=True, capture_output=True)

    premier = vm.verifier_segment(combo, debut_s=0.0, duree_s=2.0)
    second = vm.verifier_segment(combo, debut_s=2.0, duree_s=2.0)

    assert premier.mouvement_detecte is False
    assert second.mouvement_detecte is True


def test_le_mouvement_est_juge_sur_la_fenetre_gardee_par_le_montage(tmp_path):
    """Le montage ne garde que les `plan.duree_s` premières secondes d'un
    clip (`trim=duration=`). Un clip immobile sur cette fenêtre mais animé
    dans la portion COUPÉE ne doit pas passer pour animé : le spectateur ne
    verra jamais ce mouvement."""
    statique = tmp_path / "statique.mp4"
    anime = tmp_path / "anime.mp4"
    clip = tmp_path / "immobile_puis_anime.mp4"
    _clip_statique(statique, duree_s=3.0)
    _clip_anime(anime, duree_s=3.0)
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(statique), "-i", str(anime),
        "-filter_complex",
        "[0:v]trim=duration=3,setpts=PTS-STARTPTS[v0];"
        "[1:v]trim=duration=3,setpts=PTS-STARTPTS[v1];"
        "[v0][v1]concat=n=2:v=1:a=0[v]",
        "-map", "[v]", str(clip),
    ], check=True, capture_output=True)

    # Sur le clip ENTIER, le mouvement de la fin masque l'immobilité du début.
    assert vm.verifier(clip).mouvement_detecte is True

    # Sur la fenêtre réellement montée (3 s), il n'y a aucun mouvement.
    fenetre = vm.verifier(clip, fenetre_s=3.0)
    assert fenetre.mouvement_detecte is False
    assert fenetre.raison == "static_clip"
    # La durée reste celle du clip complet : c'est elle qui dit s'il est
    # assez long, une question distincte de celle du mouvement.
    assert fenetre.duree_s > 5.0
