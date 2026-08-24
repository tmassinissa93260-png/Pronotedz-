"""Dessine et anime les personnages — sans aucune IA.

Ce module remplace FLUX (les images) et Kling (l'animation) pour vérifier la
chaîne complète avant de dépenser un centime. Les personnages sont dessinés
avec des formes simples, mais ils ont ce qui compte :

  · une **identité stable** — même forme, mêmes couleurs à chaque plan ;
  · des **expressions** qui suivent l'émotion de la réplique ;
  · une **bouche qui bouge** quand le personnage parle ;
  · un léger **balancement** pour que ce ne soit pas figé.

C'est exactement ce que fera la vraie chaîne : une fiche de personnage fixe,
déclinée en situations. Ici la fiche est du code plutôt qu'une image FLUX.
"""

from __future__ import annotations

import math
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

L, H = 1080, 1920


@dataclass(frozen=True)
class Apparence:
    """La « fiche de personnage » : ce qui ne change jamais."""

    corps: tuple[int, int, int]
    ombre: tuple[int, int, int]
    accent: tuple[int, int, int]
    forme: str                       # fraise | banane | avocat
    fond_haut: tuple[int, int, int]
    fond_bas: tuple[int, int, int]


CASTING = {
    "strawberina": Apparence((222, 40, 78), (168, 20, 52), (74, 160, 72),
                             "fraise", (255, 170, 190), (140, 30, 60)),
    "bananito": Apparence((250, 208, 70), (198, 150, 30), (120, 84, 30),
                          "banane", (255, 236, 170), (170, 120, 30)),
    "avocado": Apparence((92, 148, 78), (52, 96, 46), (140, 96, 44),
                         "avocat", (186, 214, 160), (40, 78, 46)),
}


def _fond(d: ImageDraw.ImageDraw, ap: Apparence) -> None:
    for y in range(0, H, 4):
        t = y / H
        d.rectangle(
            [0, y, L, y + 4],
            fill=tuple(round(a + (b - a) * t)
                       for a, b in zip(ap.fond_haut, ap.fond_bas, strict=True)),
        )


def _yeux(d: ImageDraw.ImageDraw, cx: int, cy: int, emotion: str,
          clignement: float) -> None:
    ecart, rayon = 92, 46
    hauteur = max(0.08, 1.0 - clignement)     # 0 = fermé

    for cote in (-1, 1):
        x = cx + cote * ecart
        ry = round(rayon * hauteur)
        d.ellipse([x - rayon, cy - ry, x + rayon, cy + ry], fill=(255, 255, 255))
        if hauteur > 0.4:
            # La pupille regarde vers l'autre personnage selon l'émotion.
            dx = 12 if emotion in ("mepris", "calme") else 0
            dy = -8 if emotion == "surprise" else 6
            d.ellipse([x - 20 + dx, cy - 20 + dy, x + 20 + dx, cy + 20 + dy],
                      fill=(28, 24, 30))

    # Les sourcils portent presque toute l'expression.
    # Convention : cote=-1 est l'œil gauche, dont le côté INTERNE est à droite.
    # En colère le sourcil descend vers le nez ; inquiet, il remonte.
    for cote in (-1, 1):
        x = cx + cote * ecart
        if emotion in ("colere", "mepris"):
            interne, externe = cy - 58, cy - 98
        elif emotion in ("peur", "tristesse", "gene"):
            interne, externe = cy - 102, cy - 66
        elif emotion == "surprise":
            interne = externe = cy - 108
        else:
            interne = externe = cy - 86
        # Le point interne est du côté opposé à `cote`.
        y_gauche = externe if cote < 0 else interne
        y_droite = interne if cote < 0 else externe
        d.line([x - 52, y_gauche, x + 52, y_droite], fill=(40, 30, 34), width=13)


def _bouche(d: ImageDraw.ImageDraw, cx: int, cy: int, emotion: str,
            ouverture: float) -> None:
    largeur = 86
    if emotion == "surprise":
        r = round(26 + 34 * ouverture)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(70, 22, 32))
        return
    if ouverture < 0.12:
        courbe = 26 if emotion in ("joie", "calme") else -22
        d.arc([cx - largeur, cy - 34, cx + largeur, cy + 34],
              start=0 if courbe > 0 else 180, end=180 if courbe > 0 else 360,
              fill=(70, 22, 32), width=12)
        return
    h = round(18 + 46 * ouverture)
    d.ellipse([cx - largeur, cy - h // 2, cx + largeur, cy + h // 2],
              fill=(70, 22, 32))
    d.chord([cx - largeur, cy - h // 2, cx + largeur, cy + h // 2],
            0, 180, fill=(180, 60, 80))


def _corps(d: ImageDraw.ImageDraw, ap: Apparence, cx: int, cy: int,
           echelle: float) -> tuple[int, int]:
    """Dessine le corps, renvoie le centre du visage."""
    demi_largeur = round(300 * echelle)
    h = round(360 * echelle)

    if ap.forme == "fraise":
        d.ellipse([cx - demi_largeur, cy - h + 40, cx + demi_largeur, cy + h - 40], fill=ap.corps)
        # Pointe du bas : plus étroite que l'ellipse, sinon elle en dépasse
        # sur les côtés et donne des « oreilles ».
        d.polygon([(cx - round(demi_largeur * 0.94), cy),
                   (cx, cy + h + 40),
                   (cx + round(demi_largeur * 0.94), cy)], fill=ap.corps)
        # Akènes sur le bas du corps uniquement : sur le visage, ça fait sale.
        for rangee in range(3):
            y = cy + 150 + rangee * 70
            largeur = round(demi_largeur * (0.72 - rangee * 0.22))
            for k in range(-2 + rangee, 3 - rangee):
                x = cx + round(k * largeur / 2.2)
                d.ellipse([x - 8, y - 13, x + 8, y + 13], fill=(255, 232, 150))
        # Couronne de feuilles, symétrique
        for k in (-1.6, -0.8, 0, 0.8, 1.6):
            d.polygon([(cx - 40, cy - h + 40),
                       (cx + round(k * 92), cy - h - 100),
                       (cx + 40, cy - h + 40)], fill=ap.accent)
        d.rectangle([cx - 16, cy - h - 30, cx + 16, cy - h + 40], fill=(90, 130, 60))
        visage_y = cy - 40

    elif ap.forme == "banane":
        # Croissant : deux courbes décalées, remplies entre elles.
        # Croissant ouvert vers le HAUT (les deux bouts pointent en l'air),
        # épais au milieu et effilé aux extrémités — sinon on obtient un citron.
        pts_bas, pts_haut = [], []
        for i in range(49):
            u = i / 48
            angle = math.pi * (0.12 + 0.76 * u)
            x = cx + round(math.cos(angle) * demi_largeur * 0.98)
            # Courbe volontairement douce : trop marquée, le fruit devient un
            # bol et le visage n'a plus de place dessus.
            y = cy + round(math.sin(angle) * h * 0.22) - 20
            effile = math.sin(math.pi * u) ** 0.42        # fin aux extrémités
            demi = round(demi_largeur * 0.56 * effile)
            pts_bas.append((x, y + demi))
            pts_haut.append((x, y - demi))
        d.polygon(pts_haut + pts_bas[::-1], fill=ap.corps)
        d.line(pts_bas, fill=ap.ombre, width=14)          # volume sous le fruit
        bout = pts_haut[0]
        d.rectangle([bout[0] - 20, bout[1] - 110, bout[0] + 22, bout[1] + 40],
                    fill=ap.accent)
        visage_y = cy + 10

    else:  # avocat
        d.ellipse([cx - demi_largeur, cy - h + 110, cx + demi_largeur, cy + h], fill=ap.corps)
        d.ellipse([cx - demi_largeur + 90, cy - h, cx + demi_largeur - 90, cy + 60], fill=ap.corps)
        d.ellipse([cx - 88, cy + 190, cx + 88, cy + 350], fill=ap.accent)
        visage_y = cy - 70

    return cx, visage_y


def dessiner(perso: str, emotion: str, *, ouverture_bouche: float = 0.0,
             balancement: float = 0.0, clignement: float = 0.0,
             echelle: float = 1.0) -> Image.Image:
    """Un plan du personnage. Même appel = même image : c'est la constance."""
    ap = CASTING[perso]
    img = Image.new("RGB", (L, H))
    d = ImageDraw.Draw(img)
    _fond(d, ap)

    cx = L // 2 + round(math.sin(balancement) * 18)
    cy = round(H * 0.54) + round(math.cos(balancement * 1.7) * 14)

    d.ellipse([cx - 320, cy + 300, cx + 320, cy + 400], fill=ap.ombre)  # ombre au sol
    fx, fy = _corps(d, ap, cx, cy, echelle)
    _yeux(d, fx, fy - 60, emotion, clignement)
    _bouche(d, fx, fy + 90, emotion, ouverture_bouche)
    return img


def clip_parle(perso: str, emotion: str, duree_s: float, sortie: Path, *,
               fps: int = 24, echelle: float = 1.0, travail: Path | None = None) -> Path:
    """Génère un clip animé : la bouche bouge, le corps se balance.

    C'est le remplaçant de Kling. La vraie chaîne enverra l'image de départ à
    un modèle image-to-video ; ici on anime nous-mêmes.
    """
    dossier = travail or sortie.parent / f"_frames_{sortie.stem}"
    dossier.mkdir(parents=True, exist_ok=True)

    total = max(1, round(duree_s * fps))
    for i in range(total):
        t = i / fps
        # Bouche : deux oscillations superposées → rythme irrégulier, plus
        # crédible qu'une ouverture régulière.
        ouverture = max(0.0, 0.5 + 0.5 * math.sin(t * 13) * math.sin(t * 4.3))
        clignement = 1.0 if (i % (fps * 3)) < 3 else 0.0
        img = dessiner(perso, emotion, ouverture_bouche=ouverture,
                       balancement=t * 2.2, clignement=clignement,
                       echelle=echelle)
        img.save(dossier / f"{i:04d}.jpg", quality=88)

    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-framerate", str(fps), "-i", str(dossier / "%04d.jpg"),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
         "-pix_fmt", "yuv420p", "-r", str(fps), str(sortie)],
        check=True,
    )
    for f in dossier.glob("*.jpg"):
        f.unlink()
    dossier.rmdir()
    return sortie
