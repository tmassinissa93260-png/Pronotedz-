"""qa_video_finale.verifier() : combien de plans ont RÉELLEMENT bougé dans
la vidéo finale déjà montée — pas combien de requêtes d'animation ont
réussi. Les bornes de chaque plan sont déjà connues (`plan.duree_s`
cumulés) : pas besoin de redétecter les coupes.
"""

from __future__ import annotations

import subprocess

from pdz.production import qa_video_finale
from pdz.production.storyboard import PlanScript


def _plan(numero: int, duree_s: float) -> PlanScript:
    return PlanScript(numero=numero, replique_numero=numero, personnage="x",
                      action="a", emotion="calme", duree_s=duree_s)


def test_verifier_distingue_un_plan_statique_dun_plan_anime(tmp_path):
    statique = tmp_path / "statique.mp4"
    anime = tmp_path / "anime.mp4"
    combo = tmp_path / "combo.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-t", "2", "-i", "color=c=blue:s=64x64:r=10",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        str(statique),
    ], check=True, capture_output=True)
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-t", "2", "-i", "testsrc=size=64x64:rate=10",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        str(anime),
    ], check=True, capture_output=True)
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(statique), "-i", str(anime),
        "-filter_complex",
        "[0:v]trim=duration=2,setpts=PTS-STARTPTS[v0];"
        "[1:v]trim=duration=2,setpts=PTS-STARTPTS[v1];"
        "[v0][v1]concat=n=2:v=1:a=0[v]",
        "-map", "[v]", str(combo),
    ], check=True, capture_output=True)

    plans = [_plan(0, 2.0), _plan(1, 2.0)]
    resultats = qa_video_finale.verifier(combo, plans)

    assert resultats[0]["numero"] == 0
    assert resultats[0]["mouvement_confirme"] is False
    assert resultats[1]["numero"] == 1
    assert resultats[1]["mouvement_confirme"] is True
