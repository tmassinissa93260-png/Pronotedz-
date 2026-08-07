"""L'analyse visuelle : est-ce qu'on retrouve vraiment ce qu'on a mis dedans ?

Le principe de ces tests : fabriquer une image ou une vidéo dont on connaît
exactement les propriétés, puis vérifier que la mesure les retrouve. C'est la
seule façon de savoir si une mesure vaut quelque chose — sur une vraie vidéo,
on n'a aucune vérité de référence à quoi la comparer.
"""

from __future__ import annotations

import subprocess

import numpy as np
import pytest

from pdz.analyse import visuel
from pdz.moteur.erreurs import ErreurPdz


def _image(tmp_path, couleurs, nom="a.png", taille=(240, 400)):
    """Une image faite de bandes horizontales de couleurs connues."""
    from PIL import Image

    largeur, hauteur = taille
    tableau = np.zeros((hauteur, largeur, 3), dtype=np.uint8)
    part = hauteur // len(couleurs)
    for i, (r, v, b) in enumerate(couleurs):
        tableau[i * part:(i + 1) * part] = (r, v, b)
    chemin = tmp_path / nom
    Image.fromarray(tableau).save(chemin)
    return chemin


def _video(tmp_path, couleurs_hex, duree_par_plan=2, nom="v.mp4"):
    entrees, filtres = [], []
    for i, c in enumerate(couleurs_hex):
        entrees += ["-f", "lavfi", "-i",
                    f"color=c={c}:s=304x540:d={duree_par_plan}"]
        filtres.append(f"[{i}:v]")
    chemin = tmp_path / nom
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *entrees,
         "-filter_complex",
         "".join(filtres) + f"concat=n={len(couleurs_hex)}:v=1:a=0[v]",
         "-map", "[v]", "-r", "24", "-pix_fmt", "yuv420p", str(chemin)],
        check=True, timeout=120,
    )
    return chemin, duree_par_plan * len(couleurs_hex)


# ── Palette ──────────────────────────────────────────────────────────────

def test_la_palette_retrouve_les_couleurs_quon_a_mises(tmp_path):
    """Trois couleurs franches doivent ressortir, à quelques unités près.

    C'est la mesure la plus utilisée en aval : c'est elle qui devient la
    palette de l'univers produit.
    """
    chemin = _image(tmp_path, [(255, 77, 109), (17, 138, 178), (255, 209, 102)])
    palette = visuel.palette_dominante([visuel._charger(chemin)])

    trouvees = {c.hex.upper() for c in palette}
    for attendue in ("#FF4D6D", "#118AB2", "#FFD166"):
        proche = any(_ecart_hex(attendue, t) < 12 for t in trouvees)
        assert proche, f"{attendue} absente de {trouvees}"


def test_la_palette_ne_confond_pas_deux_teintes_voisines(tmp_path):
    """Un k-means aurait fusionné ces deux bleus en un seul."""
    chemin = _image(tmp_path, [(20, 60, 200), (20, 200, 220), (240, 240, 240)])
    palette = visuel.palette_dominante([visuel._charger(chemin)])
    teintes = sorted(c.teinte for c in palette if c.saturation > 0.2)
    assert len(teintes) >= 2
    assert max(teintes) - min(teintes) > 20


def test_une_couleur_marginale_nentre_pas_dans_la_palette(tmp_path):
    """Un liseré de deux pixels n'est pas une couleur de la série."""
    from PIL import Image

    tableau = np.full((400, 240, 3), (30, 30, 30), dtype=np.uint8)
    tableau[0:2] = (255, 0, 255)          # 0,5 % de l'image
    chemin = tmp_path / "liseré.png"
    Image.fromarray(tableau).save(chemin)

    palette = visuel.palette_dominante([visuel._charger(chemin)])
    assert all(c.saturation < 0.5 for c in palette), [c.hex for c in palette]


# ── Mesures d'image ──────────────────────────────────────────────────────

def test_une_image_plate_na_pas_de_sujet(tmp_path):
    """Sur un aplat, annoncer « sujet en haut à gauche » serait faux.

    Le cas se produit vraiment : fondu au noir, carton de fin, écran de
    chargement. Le centre de masse d'un gradient nul valait (0, 0) avant
    correction, ce qui se lisait « gauche-haut » dans le rapport.
    """
    chemin = _image(tmp_path, [(70, 70, 70)])
    m = visuel._mesurer_image(visuel._charger(chemin))
    assert m["cadrage_x"] == 0.5 and m["cadrage_y"] == 0.5
    assert m["echelle_sujet"] == 0.0


def test_le_contraste_distingue_le_plat_du_contraste(tmp_path):
    plat = _image(tmp_path, [(128, 128, 128)], nom="plat.png")
    fort = _image(tmp_path, [(0, 0, 0), (255, 255, 255)], nom="fort.png")

    m_plat = visuel._mesurer_image(visuel._charger(plat))
    m_fort = visuel._mesurer_image(visuel._charger(fort))
    assert m_plat["contraste"] < 0.02 < m_fort["contraste"]


def test_la_temperature_separe_le_chaud_du_froid(tmp_path):
    chaud = _image(tmp_path, [(230, 90, 40)], nom="chaud.png")
    froid = _image(tmp_path, [(40, 90, 230)], nom="froid.png")

    assert visuel._mesurer_image(visuel._charger(chaud))["temperature"] > 0.3
    assert visuel._mesurer_image(visuel._charger(froid))["temperature"] < -0.3


def test_le_cadrage_suit_le_sujet(tmp_path):
    """Un détail placé en bas doit être annoncé en bas."""
    from PIL import Image

    tableau = np.full((400, 240, 3), 20, dtype=np.uint8)
    # Damier fin dans le tiers bas : c'est là qu'est tout le détail.
    for y in range(300, 380, 4):
        for x in range(60, 180, 4):
            tableau[y:y + 2, x:x + 2] = 240
    chemin = tmp_path / "bas.png"
    Image.fromarray(tableau).save(chemin)

    m = visuel._mesurer_image(visuel._charger(chemin))
    assert m["cadrage_y"] > 0.6, m


# ── Choix des instants ───────────────────────────────────────────────────

def test_les_instants_tombent_au_milieu_des_plans_les_plus_longs():
    """Le milieu d'un plan est stable ; un bord tombe sur une transition."""
    instants = visuel.instants_representatifs(
        30.0, coupes=[2.0, 4.0, 20.0], combien=2
    )
    # Plans : 0-2, 2-4, 4-20, 20-30 → les deux plus longs sont 4-20 et 20-30.
    assert instants == pytest.approx([12.0, 25.0], abs=0.01)


def test_sans_coupes_on_evite_les_bords():
    instants = visuel.instants_representatifs(60.0, coupes=None, combien=4)
    assert min(instants) > 1.0
    assert max(instants) < 59.0
    assert len(instants) == 4


# ── Analyse complète ─────────────────────────────────────────────────────

def test_une_video_a_style_constant_a_une_confiance_haute(tmp_path):
    chemin, duree = _video(tmp_path, ["0x203040", "0x223244", "0x1E2E3E"])
    a = visuel.analyser(chemin, duree, dossier_images=tmp_path / "im")
    assert a.confiance > 0.8, a.resume()


def test_une_video_qui_change_de_style_le_signale(tmp_path):
    """Trois images sans rapport : une moyenne unique ne décrirait aucune.

    Mieux vaut une confiance basse qu'un chiffre unique présenté comme un fait.
    """
    chemin, duree = _video(tmp_path, ["0x000000", "0xFFFFFF", "0xFF0000"])
    a = visuel.analyser(chemin, duree, dossier_images=tmp_path / "im")
    assert a.confiance < 0.5, a.resume()


def test_le_bloc_de_prompt_contient_les_mesures(tmp_path):
    chemin, duree = _video(tmp_path, ["0x8844AA", "0x8B4AAF"])
    a = visuel.analyser(chemin, duree, dossier_images=tmp_path / "im")
    bloc = a.bloc_pour_prompt()
    for attendu in ("Palette dominante", "Luminosité", "Température",
                    "Netteté", "Cadrage type"):
        assert attendu in bloc
    assert a.palette_hex[0] in bloc


def test_une_video_absente_echoue_clairement(tmp_path):
    with pytest.raises(ErreurPdz) as e:
        visuel.analyser(tmp_path / "rien.mp4", 10.0)
    assert "introuvable" in str(e.value)


def _ecart_hex(a: str, b: str) -> float:
    def rgb(h):
        h = h.lstrip("#")
        return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=float)
    return float(np.abs(rgb(a) - rgb(b)).max())
