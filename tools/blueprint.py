"""Rendu « plan technique » — traits blancs sur fond noir.

Style relevé sur la vidéo de référence : monochrome pur (saturation mesurée
à 0,1/255), 61 % de noir, 2 % de blanc, caméra qui dérive lentement dans des
scènes filaires en 3D.

Ce module remplace FLUX : il dessine les scènes par projection 3D plutôt que
de les générer. La vraie chaîne enverra la même description de style à un
modèle d'images ; la structure du montage, elle, est identique.
"""

from __future__ import annotations

import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

L, H = 1080, 1920
BLANC = (255, 255, 255)
GRIS = (120, 120, 120)
SOMBRE = (55, 55, 55)


# ── Projection 3D minimale ───────────────────────────────────────────────

def projeter(p: tuple[float, float, float], cam: tuple[float, float, float],
             rot_y: float, focale: float = 900.0) -> tuple[float, float] | None:
    """Point 3D → point écran. Renvoie None si le point est derrière la caméra."""
    x, y, z = p[0] - cam[0], p[1] - cam[1], p[2] - cam[2]
    c, s = math.cos(rot_y), math.sin(rot_y)
    x, z = x * c - z * s, x * s + z * c
    if z <= 12:
        return None
    return (L / 2 + x * focale / z, H / 2 + y * focale / z)


def trait(d: ImageDraw.ImageDraw, a, b, cam, rot, couleur=BLANC, epais=2) -> None:
    pa, pb = projeter(a, cam, rot), projeter(b, cam, rot)
    if pa and pb:
        d.line([pa, pb], fill=couleur, width=epais)


# ── Scènes ───────────────────────────────────────────────────────────────

def sol(d, cam, rot, pas: int = 120, portee: int = 22) -> None:
    """Grille de sol en perspective — l'élément signature du style."""
    for i in range(-portee, portee + 1):
        trait(d, (i * pas, 300, -portee * pas), (i * pas, 300, portee * pas),
              cam, rot, SOMBRE, 1)
        trait(d, (-portee * pas, 300, i * pas), (portee * pas, 300, i * pas),
              cam, rot, SOMBRE, 1)


def boite(d, centre, dims, cam, rot, couleur=BLANC, epais=2) -> None:
    cx, cy, cz = centre
    dx, dy, dz = (v / 2 for v in dims)
    coins = [(cx + sx * dx, cy + sy * dy, cz + sz * dz)
             for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    aretes = [(0, 1), (0, 2), (0, 4), (1, 3), (1, 5), (2, 3),
              (2, 6), (3, 7), (4, 5), (4, 6), (5, 7), (6, 7)]
    for i, j in aretes:
        trait(d, coins[i], coins[j], cam, rot, couleur, epais)


def sphere(d, centre, rayon, cam, rot, meridiens=14, paralleles=8) -> None:
    """Globe filaire : méridiens et parallèles."""
    cx, cy, cz = centre
    for m in range(meridiens):
        a = m * math.pi / meridiens
        pts = []
        for k in range(25):
            t = k * math.pi / 24 - math.pi / 2
            pts.append((cx + rayon * math.cos(t) * math.cos(a),
                        cy + rayon * math.sin(t),
                        cz + rayon * math.cos(t) * math.sin(a)))
        for p, q in zip(pts, pts[1:], strict=False):
            trait(d, p, q, cam, rot, BLANC, 1)
    for p_ in range(1, paralleles):
        t = p_ * math.pi / paralleles - math.pi / 2
        r = rayon * math.cos(t)
        y = cy + rayon * math.sin(t)
        pts = [(cx + r * math.cos(a * math.pi / 12), y, cz + r * math.sin(a * math.pi / 12))
               for a in range(25)]
        for p, q in zip(pts, pts[1:], strict=False):
            trait(d, p, q, cam, rot, BLANC, 1)


def orbite(d, centre, rayon, inclinaison, cam, rot, couleur=GRIS) -> None:
    cx, cy, cz = centre
    pts = []
    for k in range(65):
        a = k * math.tau / 64
        x, z = rayon * math.cos(a), rayon * math.sin(a)
        y = z * math.sin(inclinaison)
        z = z * math.cos(inclinaison)
        pts.append((cx + x, cy + y, cz + z))
    for p, q in zip(pts, pts[1:], strict=False):
        trait(d, p, q, cam, rot, couleur, 1)


def ville(d, cam, rot, graine: int = 7) -> None:
    """Blocs d'immeubles filaires — la scène la plus reconnaissable du style."""
    import random
    r = random.Random(graine)
    for gx in range(-5, 6):
        for gz in range(-3, 12):
            if abs(gx) < 1:                      # l'avenue centrale reste vide
                continue
            haut = r.uniform(260, 1100)
            larg = r.uniform(140, 230)
            boite(d, (gx * 320, 300 - haut / 2, gz * 340),
                  (larg, haut, larg), cam, rot, BLANC, 1)


def fusee(d, base, hauteur, cam, rot) -> None:
    bx, by, bz = base
    r = hauteur * 0.09
    for k in range(12):                          # fuselage
        a1, a2 = k * math.tau / 12, (k + 1) * math.tau / 12
        p1 = (bx + r * math.cos(a1), by, bz + r * math.sin(a1))
        p2 = (bx + r * math.cos(a2), by, bz + r * math.sin(a2))
        trait(d, p1, p2, cam, rot, BLANC, 1)
        trait(d, p1, (p1[0], by - hauteur * 0.72, p1[2]), cam, rot, BLANC, 1)
        trait(d, (p1[0], by - hauteur * 0.72, p1[2]),
              (bx, by - hauteur, bz), cam, rot, BLANC, 1)   # coiffe
        trait(d, (p1[0], by - hauteur * 0.72, p1[2]),
              (p2[0], by - hauteur * 0.72, p2[2]), cam, rot, BLANC, 1)
    for k in range(3):                           # ailerons
        a = k * math.tau / 3
        p = (bx + r * math.cos(a), by, bz + r * math.sin(a))
        trait(d, p, (bx + r * 2.4 * math.cos(a), by + hauteur * 0.06,
                     bz + r * 2.4 * math.sin(a)), cam, rot, BLANC, 2)
        trait(d, (bx + r * 2.4 * math.cos(a), by + hauteur * 0.06,
                  bz + r * 2.4 * math.sin(a)),
              (p[0], by - hauteur * 0.22, p[2]), cam, rot, BLANC, 2)


def satellite(d, centre, taille, cam, rot) -> None:
    boite(d, centre, (taille, taille, taille), cam, rot, BLANC, 2)
    cx, cy, cz = centre
    for cote in (-1, 1):                         # panneaux solaires
        px = cx + cote * taille * 2.1
        boite(d, (px, cy, cz), (taille * 2.6, taille * 0.12, taille * 0.9),
              cam, rot, BLANC, 1)
        trait(d, (cx + cote * taille / 2, cy, cz), (px, cy, cz), cam, rot, BLANC, 2)
    for k in range(4):                           # antennes
        a = k * math.tau / 4
        trait(d, centre, (cx + taille * 1.5 * math.cos(a), cy - taille * 1.2,
                          cz + taille * 1.5 * math.sin(a)), cam, rot, GRIS, 1)


def etoiles(d, graine: int = 3, nombre: int = 120) -> None:
    import random
    r = random.Random(graine)
    for _ in range(nombre):
        x, y = r.randrange(L), r.randrange(H)
        t = r.choice([1, 1, 1, 2])
        v = r.randrange(90, 230)
        d.ellipse([x, y, x + t, y + t], fill=(v, v, v))


# ── Annotations techniques ───────────────────────────────────────────────

def _police(taille: int):
    for c in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if Path(c).exists():
            return ImageFont.truetype(c, taille)
    return ImageFont.load_default()


def annotation(d, xy, texte: str, ancre_xy=None) -> None:
    """Petit cartouche technique, comme sur un plan d'ingénieur.

    C'est un détail, mais c'est lui qui fait « plan technique » plutôt que
    « dessin filaire ».
    """
    f = _police(20)
    x, y = xy
    lignes = texte.upper().split("\n")
    larg = max(d.textlength(ligne, font=f) for ligne in lignes) + 20
    haut = len(lignes) * 26 + 12
    d.rectangle([x, y, x + larg, y + haut], outline=GRIS, width=1)
    for i, ligne in enumerate(lignes):
        d.text((x + 10, y + 6 + i * 26), ligne, fill=BLANC, font=f)
    if ancre_xy:
        d.line([x, y + haut / 2, *ancre_xy], fill=SOMBRE, width=1)
        d.ellipse([ancre_xy[0] - 4, ancre_xy[1] - 4,
                   ancre_xy[0] + 4, ancre_xy[1] + 4], outline=BLANC, width=2)


def cadre(d) -> None:
    """Réticule d'écran technique : coins + repères latéraux."""
    m, t = 40, 60
    for cx, cy, sx, sy in ((m, m, 1, 1), (L - m, m, -1, 1),
                           (m, H - m, 1, -1), (L - m, H - m, -1, -1)):
        d.line([cx, cy, cx + sx * t, cy], fill=SOMBRE, width=2)
        d.line([cx, cy, cx, cy + sy * t], fill=SOMBRE, width=2)
    for k in range(1, 8):
        y = H * k / 8
        d.line([m, y, m + 14, y], fill=SOMBRE, width=1)
        d.line([L - m - 14, y, L - m, y], fill=SOMBRE, width=1)


# ── Assemblage d'un plan ─────────────────────────────────────────────────

def rendre_plan(scene: str, avance: float, *, notes: list[tuple] = ()) -> Image.Image:
    """Une image du plan. `avance` va de 0 à 1 : c'est le mouvement de caméra."""
    img = Image.new("RGB", (L, H), (0, 0, 0))
    d = ImageDraw.Draw(img)
    t = avance

    if scene == "ville":
        cam = (0, -120 - t * 120, -1500 + t * 700)
        rot = -0.25 + t * 0.12
        sol(d, cam, rot)
        ville(d, cam, rot)
        annotation(d, (70, 300), "densite urbaine\nreleve 01", (540, 700))

    elif scene == "globe":
        cam = (0, 0, -2100)
        rot = t * 0.9
        etoiles(d)
        sphere(d, (0, 0, 0), 520, cam, rot)
        orbite(d, (0, 0, 0), 760, 0.42, cam, rot)
        orbite(d, (0, 0, 0), 980, -0.30, cam, rot)
        annotation(d, (70, 1300), "orbite basse\n+ 215 km", (540, 1100))

    elif scene == "satellite":
        cam = (0, 0, -900 + t * 260)
        rot = -0.6 + t * 1.1
        etoiles(d, graine=11)
        satellite(d, (0, 0, 0), 150, cam, rot)
        annotation(d, (70, 260), "emetteur radio\n20,005 mhz", (620, 820))

    elif scene == "fusee":
        cam = (0, -260 + t * 220, -1500)
        rot = -0.3 + t * 0.5
        sol(d, cam, rot, pas=200, portee=16)
        fusee(d, (0, 300, 0), 1500, cam, rot)
        annotation(d, (70, 1420), "etage unique\npoussee 3,9 mn", (520, 1150))

    elif scene == "espace":
        cam = (0, 0, -1200)
        rot = t * 0.35
        etoiles(d, graine=21, nombre=200)
        for k in range(5):
            orbite(d, (0, 0, 0), 300 + k * 190, 0.3 + k * 0.14, cam, rot, SOMBRE)
        satellite(d, (260, -180, 120), 70, cam, rot)

    else:  # grille nue
        cam = (0, -200, -1400 + t * 500)
        sol(d, cam, t * 0.2, pas=150, portee=20)

    cadre(d)
    return img


def clip(scene: str, duree_s: float, sortie: Path, *, fps: int = 24) -> Path:
    """Rend un plan animé : la caméra dérive pendant toute la durée."""
    dossier = sortie.parent / f"_f_{sortie.stem}"
    dossier.mkdir(parents=True, exist_ok=True)
    total = max(1, round(duree_s * fps))
    for i in range(total):
        rendre_plan(scene, i / max(1, total - 1)).save(
            dossier / f"{i:04d}.jpg", quality=88)
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-framerate", str(fps), "-i", str(dossier / "%04d.jpg"),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
         "-pix_fmt", "yuv420p", "-r", str(fps), str(sortie)],
        check=True,
    )
    for f in dossier.glob("*.jpg"):
        f.unlink()
    dossier.rmdir()
    return sortie
