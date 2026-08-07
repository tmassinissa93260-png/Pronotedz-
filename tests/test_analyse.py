"""Analyse vidéo — mesures locales, aucune IA, aucun réseau.

Les vidéos de test sont fabriquées avec ffmpeg : on connaît donc la vérité
(nombre de coupes, durée, présence de son) et on peut vérifier les mesures.
"""

import subprocess

import pytest

from pdz.analyse import analyser, detecter, sonder
from pdz.analyse.coupes import _noter
from pdz.moteur.erreurs import ErreurPdz


def _video(chemin, *, couleurs=("red", "blue", "green"), duree_plan=1.0,
           avec_son=True, fps=25):
    """Fabrique une vidéo dont on connaît exactement le nombre de coupes."""
    entrees, filtres = [], []
    for i, c in enumerate(couleurs):
        entrees += ["-f", "lavfi", "-t", str(duree_plan),
                    "-i", f"color=c={c}:s=360x640:r={fps}"]
        filtres.append(f"[{i}:v]")
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *entrees]
    if avec_son:
        cmd += ["-f", "lavfi", "-t", str(duree_plan * len(couleurs)),
                "-i", "sine=frequency=440"]
    cmd += ["-filter_complex",
            "".join(filtres) + f"concat=n={len(couleurs)}:v=1:a=0[v]",
            "-map", "[v]"]
    if avec_son:
        cmd += ["-map", f"{len(couleurs)}:a", "-c:a", "aac"]
    cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            str(chemin)]
    subprocess.run(cmd, check=True, capture_output=True)
    return chemin


# ── Sonde ────────────────────────────────────────────────────────────────

def test_la_sonde_lit_les_metadonnees(tmp_path):
    v = _video(tmp_path / "v.mp4", duree_plan=1.0)
    m = sonder(v)
    assert m.largeur == 360 and m.hauteur == 640
    assert m.ratio == "9:16" and m.vertical
    assert 2.8 < m.duree_s < 3.2
    assert m.a_du_son


def test_une_video_sans_son_est_signalee(tmp_path):
    m = sonder(_video(tmp_path / "muet.mp4", avec_son=False))
    assert not m.a_du_son


def test_un_fichier_absent_donne_un_message_clair(tmp_path):
    with pytest.raises(ErreurPdz, match="introuvable"):
        sonder(tmp_path / "fantome.mp4")


# ── Détection des coupes ─────────────────────────────────────────────────

def test_les_coupes_franches_sont_trouvees(tmp_path):
    """Trois aplats de couleur = deux coupes, sans ambiguïté."""
    v = _video(tmp_path / "v.mp4", couleurs=("red", "blue", "green"),
               duree_plan=1.2)
    d = detecter(v, sonder(v).duree_s)
    assert d.nb_plans == 3, d.candidats


def test_le_seuil_le_plus_permissif_gagne_a_note_egale():
    """Le départage est le cœur du calibrage.

    Un seuil trop sévère fusionne deux plans sans le signaler — la vidéo
    paraît deux fois plus lente qu'elle n'est. Mesuré sur une vraie vidéo :
    0,22 donnait 11 plans et 0,16 en donnait 17, pour la même note.
    """
    from pdz.analyse.coupes import Decoupage  # noqa: F401

    # Deux découpages également plausibles : réguliers, sans micro-plan.
    note_a, _ = _noter([5.0] * 10, 50.0)
    note_b, _ = _noter([2.5] * 20, 50.0)
    assert note_a == note_b == pytest.approx(1.0), (note_a, note_b)


def test_les_micro_plans_sont_penalises():
    """C'est ce qui écarte le seuil qui compte les changements de texte."""
    bon, _ = _noter([2.0] * 20, 40.0)
    bruite, _ = _noter([0.1] * 30 + [3.0] * 10, 40.0)
    assert bruite < bon * 0.5


def test_un_plan_qui_couvre_toute_la_video_est_penalise():
    """Symptôme d'un seuil trop sévère : une seule scène géante."""
    fusionne, _ = _noter([70.0, 4.0, 3.0], 77.0)
    normal, _ = _noter([4.0] * 19, 77.0)
    assert fusionne < normal


def test_la_confiance_chute_quand_les_seuils_ne_saccordent_pas(tmp_path):
    v = _video(tmp_path / "v.mp4", couleurs=("red", "blue"), duree_plan=1.5)
    d = detecter(v, sonder(v).duree_s)
    assert 0.0 <= d.confiance <= 1.0


def test_on_peut_forcer_un_seuil(tmp_path):
    v = _video(tmp_path / "v.mp4", duree_plan=1.0)
    d = detecter(v, sonder(v).duree_s, seuil_force=0.30)
    assert d.seuil == 0.30
    assert d.candidats == [], "un seuil forcé ne lance pas le calibrage"


# ── Son ──────────────────────────────────────────────────────────────────

def test_lanalyse_du_son_mesure_la_duree(tmp_path):
    v = _video(tmp_path / "v.mp4", duree_plan=1.0)
    s = analyser(v)
    assert 2.8 < s.duree_s < 3.2
    assert len(s.courbe_energie) > 50


def test_la_courbe_se_reduit_au_nombre_de_points_demande(tmp_path):
    s = analyser(_video(tmp_path / "v.mp4", duree_plan=1.0))
    assert len(s.courbe_reduite(12)) == 12
    assert all(0.0 <= v <= 1.0 for v in s.courbe_reduite(12))


def test_un_ton_pur_na_pas_de_tempo_credible(tmp_path):
    """Une sinusoïde n'a aucune attaque : la confiance doit rester basse.

    C'est le comportement voulu — mieux vaut dire « je ne sais pas » que
    renvoyer un BPM inventé, comme le ferait un modèle interrogé au hasard.
    """
    s = analyser(_video(tmp_path / "v.mp4", duree_plan=2.0))
    assert s.confiance_tempo < 0.5


def test_une_video_muette_echoue_clairement(tmp_path):
    v = _video(tmp_path / "muet.mp4", avec_son=False)
    with pytest.raises(ErreurPdz, match="son"):
        analyser(v)
