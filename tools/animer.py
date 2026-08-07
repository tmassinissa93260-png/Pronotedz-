"""Faire bouger une image fixe — sans modèle de génération vidéo.

Ce n'est PAS un remplaçant de Kling ou Veo : ces modèles inventent du
mouvement réel (un personnage qui tourne la tête, de la fumée qui s'échappe).
Ici on ne crée rien de nouveau, on donne de la vie à ce qui existe déjà.

Trois effets, tous gratuits :

  1. **Travelling en perspective** — les quatre coins de l'image se déplacent
     à des vitesses différentes. Le cerveau lit ça comme de la profondeur,
     là où un simple zoom reste plat.
  2. **Particules** — poussières qui dérivent. C'est l'effet qui fait le plus
     pour un coût nul : l'œil voit du mouvement indépendant de la caméra.
  3. **Scintillement local** — une zone lumineuse (flamme, écran, néon) qui
     pulse légèrement.

Sur une photo, ça donne 60 à 70 % de l'effet d'une vraie animation.
Sur un personnage qui doit parler, ça ne remplace rien.
"""

from __future__ import annotations

import math
import random
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw

L, H = 1080, 1920


@dataclass
class Particule:
    x: float
    y: float
    vx: float
    vy: float
    taille: float
    lumiere: int

    y_min: float = 0.0
    y_max: float = float(H)

    def avancer(self, dt: float) -> None:
        self.x += self.vx * dt
        self.y += self.vy * dt
        if self.y < self.y_min - 20:
            self.y = self.y_max + 20
        if self.x < -20:
            self.x = L + 20
        elif self.x > L + 20:
            self.x = -20


@dataclass
class Effets:
    """Réglages d'animation d'un plan."""

    # Travelling : de combien les coins se déplacent, en part de l'image.
    dolly: float = 0.06
    # Sens : 1 = on avance, -1 = on recule.
    sens: int = 1
    # Inclinaison latérale, pour éviter un mouvement purement frontal.
    derive_x: float = 0.02

    particules: int = 90
    vitesse_particules: float = 26.0     # pixels par seconde
    # Bande verticale où vivent les particules, en fraction de la hauteur.
    # Sans ça, elles dérivent aussi dans les bandes noires du cadre.
    zone_particules: tuple[float, float] = (0.0, 1.0)
    # Zone qui scintille : (x, y, rayon) en fraction de l'image. None = aucune.
    scintillement: tuple[float, float, float] | None = None
    force_scintillement: float = 0.16

    graine: int = 0
    _particules: list[Particule] = field(default_factory=list, repr=False)

    def preparer(self) -> None:
        r = random.Random(self.graine)
        y0, y1 = (v * H for v in self.zone_particules)
        self._particules = [
            Particule(
                x=r.uniform(0, L), y=r.uniform(y0, y1),
                vx=r.uniform(-0.5, 0.5) * self.vitesse_particules,
                vy=-r.uniform(0.3, 1.0) * self.vitesse_particules,
                taille=r.uniform(1.2, 3.6),
                lumiere=r.randint(120, 255),
                y_min=y0, y_max=y1,
            )
            for _ in range(self.particules)
        ]


def _travelling(img: Image.Image, e: Effets, t: float) -> Image.Image:
    """Déplace les quatre coins → sensation de profondeur.

    Un zoom déplace tous les pixels proportionnellement : l'image reste plate.
    Ici les coins bougent différemment, ce qui simule un changement de point
    de vue plutôt qu'un simple grossissement.
    """
    a = e.dolly * t * e.sens
    dx = e.derive_x * t * L

    # Coins de la zone source à prélever, dans l'image d'origine.
    gauche = a * L
    droite = L - a * L * 0.6          # asymétrie : la profondeur se lit mieux
    haut = a * H * 0.7
    bas = H - a * H

    quad = (
        gauche + dx, haut,
        gauche + dx * 0.4, bas,
        droite + dx * 0.4, bas,
        droite + dx, haut,
    )
    return img.transform((L, H), Image.QUAD, quad, Image.BILINEAR)


def _particules(img: Image.Image, e: Effets, dt: float) -> None:
    if not e._particules:
        return
    d = ImageDraw.Draw(img, "RGBA")
    for p in e._particules:
        p.avancer(dt)
        r = p.taille
        d.ellipse([p.x - r, p.y - r, p.x + r, p.y + r],
                  fill=(255, 255, 255, min(255, p.lumiere)))


def _scintiller(img: Image.Image, e: Effets, t: float) -> None:
    if e.scintillement is None:
        return
    fx, fy, fr = e.scintillement
    cx, cy, r = fx * L, fy * H, fr * L

    # Deux oscillations de périodes incommensurables : le battement paraît
    # naturel, là où une sinusoïde unique fait « clignotant ».
    intensite = (math.sin(t * 17.0) * 0.6 + math.sin(t * 6.3) * 0.4)
    alpha = int(abs(intensite) * e.force_scintillement * 255)
    if alpha <= 0:
        return

    halo = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(halo)
    for k in range(6, 0, -1):                    # dégradé par cercles
        rk = r * k / 6
        d.ellipse([cx - rk, cy - rk, cx + rk, cy + rk],
                  fill=(255, 220, 170, alpha // 6))
    img.alpha_composite(halo) if img.mode == "RGBA" else \
        img.paste(Image.alpha_composite(img.convert("RGBA"), halo).convert("RGB"))


def animer(source: Path | Image.Image, duree_s: float, sortie: Path, *,
           effets: Effets | None = None, fps: int = 25) -> Path:
    """Produit un clip animé à partir d'une image fixe."""
    e = effets or Effets()
    e.preparer()

    img = (Image.open(source) if isinstance(source, (str, Path)) else source)
    img = img.convert("RGB")
    if img.size != (L, H):
        img = img.resize((L, H), Image.LANCZOS)

    dossier = sortie.parent / f"_a_{sortie.stem}"
    dossier.mkdir(parents=True, exist_ok=True)

    total = max(1, round(duree_s * fps))
    dt = 1.0 / fps
    for i in range(total):
        t = i / max(1, total - 1)
        cadre = _travelling(img, e, t)
        _scintiller(cadre, e, i * dt)
        _particules(cadre, e, dt)
        cadre.save(dossier / f"{i:04d}.jpg", quality=90)

    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-framerate", str(fps), "-i", str(dossier / "%04d.jpg"),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
         "-pix_fmt", "yuv420p", "-r", str(fps), str(sortie)],
        check=True)

    for f in dossier.glob("*.jpg"):
        f.unlink()
    dossier.rmdir()
    return sortie
