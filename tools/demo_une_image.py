"""Une seule image → une vidéo de six plans.

C'est la technique annoncée dans docs/11-etat-de-lart.md : pour tenir le
rythme de 2026 (un changement visuel toutes les 1,5 à 2 s), on n'a pas besoin
d'autant d'images que de plans. Un recadrage différent EST un plan différent
à l'œil.

Ici, une image générée à la main dans Meta AI devient six plans distincts,
plus le mouvement et les sous-titres. Coût : 0 €.

    python tools/demo_une_image.py chemin/vers/image.png
"""

from __future__ import annotations

import random
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image, ImageEnhance, ImageFilter  # noqa: E402

from pdz.video.vie import Effets, animer  # noqa: E402

from pdz.video import Montage, Mouvement, Plan  # noqa: E402
from pdz.video.montage import MARGE_MOUVEMENT  # noqa: E402
from pdz.video.soustitres import (  # noqa: E402
    StyleSousTitres,
    generer_ass,
    mots_depuis_texte,
)

SORTIE = Path("donnees/sorties")
TRAVAIL = Path("donnees/travail/une-image")

L, H = 1080, 1920
CADRE_L, CADRE_H = round(L * MARGE_MOUVEMENT), round(H * MARGE_MOUVEMENT)

STYLE = StyleSousTitres(
    taille=132, position_ratio=0.74, mots_par_carte=1,
    epaisseur_contour=7.0, majuscules=True,
    couleur="&H00FFFFFF", couleur_active="&H00FFFFFF",
)

# (zone à cadrer en fraction de l'image, mouvement, texte)
#   zone = (x_centre, y_centre, largeur) — tout en fraction de la largeur.
# (zone, mouvement, texte, sens du travelling, zone qui scintille)
PLANS = [
    ((0.50, 0.55, 1.00), Mouvement.ZOOM_AVANT,
     "Quand un module se pose sur la Lune, il n'y a pas d'air.",
     1, (0.50, 0.62, 0.16)),
    ((0.52, 0.82, 0.55), Mouvement.PAN_DROITE,
     "La poussière ne retombe pas. Elle part en ligne droite.",
     1, (0.50, 0.40, 0.22)),
    ((0.48, 0.30, 0.42), Mouvement.ZOOM_AVANT,
     "Pendant les vingt dernières secondes, le pilote ne voit plus le sol.",
     -1, None),
    ((0.68, 0.60, 0.50), Mouvement.PAN_GAUCHE,
     "Le souffle du moteur soulève un voile qui masque tout.",
     1, None),
    ((0.50, 0.78, 0.34), Mouvement.ZOOM_ARRIERE,
     "Il faut se poser à l'aveugle.",
     -1, (0.48, 0.34, 0.26)),
    ((0.13, 0.16, 0.30), Mouvement.ZOOM_AVANT,
     "Et derrière, la Terre regarde. Trois cent quatre-vingt mille kilomètres.",
     1, None),
]

DEBIT_WPM = 150

# Travelling + particules + scintillement. Coûte ~3 s de calcul par seconde
# de vidéo, et rapporte beaucoup sur une image fixe.
ANIME = "--simple" not in sys.argv


def preparer_plan(source: Image.Image, zone, destination: Path,
                  *, grain: int = 7) -> Path:
    """Découpe une zone et en fait une image de plan, prête à être animée.

    Le fond flouté comble le format vertical : l'image d'origine est en
    paysage, un recadrage plein cadre perdrait les trois quarts de la scène
    et forcerait un agrandissement bien trop fort.
    """
    cx, cy, larg = zone
    lw = max(80, round(source.width * larg))
    lh = round(lw * CADRE_H / CADRE_L)

    x = round(source.width * cx - lw / 2)
    y = round(source.height * cy - lh / 2)

    # Fond : la zone élargie, floutée et assombrie.
    marge = 2.2
    fx = round(source.width * cx - lw * marge / 2)
    fy = round(source.height * cy - lh * marge / 2)
    fond = (source
            .crop((fx, fy, fx + round(lw * marge), fy + round(lh * marge)))
            .resize((CADRE_L, CADRE_H), Image.LANCZOS)
            .filter(ImageFilter.GaussianBlur(38)))
    fond = ImageEnhance.Brightness(fond).enhance(0.42)

    # Sujet net, ajusté à la largeur du cadre.
    net = source.crop((x, y, x + lw, y + lh))
    hauteur_nette = round(CADRE_L * net.height / net.width)
    net = net.resize((CADRE_L, hauteur_nette), Image.LANCZOS)

    img = fond.copy()
    img.paste(net, (0, (CADRE_H - hauteur_nette) // 2))

    # Grain léger : masque l'agrandissement et donne un aspect argentique.
    if grain:
        r = random.Random(0)
        px = img.load()
        for _ in range(CADRE_L * CADRE_H // 90):
            gx, gy = r.randrange(CADRE_L), r.randrange(CADRE_H)
            v = r.randint(-grain, grain)
            p = px[gx, gy]
            px[gx, gy] = tuple(max(0, min(255, c + v)) for c in p)

    destination.parent.mkdir(parents=True, exist_ok=True)
    img.save(destination, quality=94)
    return destination


def voix_factice(duree_s: float, chemin: Path) -> Path:
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", f"anoisesrc=d={duree_s:.3f}:c=brown:a=0.02",
         str(chemin)], check=True)
    return chemin


def main(chemin_source: str) -> int:
    source = Image.open(chemin_source).convert("RGB")
    TRAVAIL.mkdir(parents=True, exist_ok=True)
    SORTIE.mkdir(parents=True, exist_ok=True)

    durees = [max(2.2, len(p[2].split()) / DEBIT_WPM * 60) for p in PLANS]
    total = sum(durees)

    print(f"\n  Source : {source.size[0]}×{source.size[1]} — UNE seule image")
    print(f"  → {len(PLANS)} plans · {total:.0f} s · "
          f"{total / len(PLANS):.1f} s par plan\n")

    debut = time.perf_counter()
    plans = []
    for i, ((zone, mv, texte, sens, feu), duree) in enumerate(
            zip(PLANS, durees, strict=True)):
        base = preparer_plan(source, zone, TRAVAIL / f"plan{i}.jpg")

        if ANIME:
            # Travelling + poussières + scintillement des flammes.
            clip = animer(
                base, duree, TRAVAIL / f"clip{i}.mp4",
                effets=Effets(
                    dolly=0.065, sens=sens, derive_x=0.015 * sens,
                    particules=100, vitesse_particules=30,
                    # Les particules restent dans l'image nette, pas dans les
                    # bandes noires du haut et du bas.
                    zone_particules=(0.22, 0.80),
                    scintillement=feu, force_scintillement=0.20,
                    graine=i,
                ),
            )
            plans.append(Plan(image=clip, duree_s=duree, anime=True))
        else:
            plans.append(Plan(image=base, duree_s=duree, mouvement=mv))

        print(f"  ✓ plan {i + 1}  cadre {zone[2] * 100:3.0f} %  "
              f"{'travelling' if ANIME else mv.value:12s} {duree:4.1f} s"
              f"{'  + flammes' if (ANIME and feu) else ''}")

    print(f"\n  6 plans préparés en {time.perf_counter() - debut:.0f} s")

    mots, curseur = [], 0.0
    for (_, _, texte, _, _), duree in zip(PLANS, durees, strict=True):
        mots += mots_depuis_texte(texte, round(curseur * 1000), round(duree * 1000))
        curseur += duree
    ass = TRAVAIL / "st.ass"
    ass.write_text(generer_ass(mots, style=STYLE), encoding="utf-8")
    print(f"  ✓ {len(mots)} mots")

    fichier = SORTIE / ("une-image-lune-anime.mp4" if ANIME
                       else "une-image-lune.mp4")
    print("\n  Montage…")
    t = time.perf_counter()
    Montage(plans=plans, voix=voix_factice(total, TRAVAIL / "voix.wav"),
            sous_titres=ass).rendre(fichier)

    print(f"\n  ✓ {fichier}")
    print(f"    {fichier.stat().st_size / 1024:.0f} Ko · "
          f"monté en {time.perf_counter() - t:.1f} s pour {total:.0f} s")
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    raise SystemExit(main(args[0] if args else "donnees/sources/lune.png"))
