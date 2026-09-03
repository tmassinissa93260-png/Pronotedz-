"""Ce qu'on peut verifier d'une video rendue SANS payer un seul jeton.

L'analyse par un modele de vision coute cher et le compte est a sec. Mais
trois des defauts les plus couteux ne demandent aucun modele :

  · le FORMAT — une video qui n'est pas en 9:16 est a refaire, point.
  · la DUREE — dix secondes pour un plan qui en demandait trois, c'est le
    montage entier qui saute.
  · la COULEUR — le code couleur est la moitie de la pedagogie du systeme.
    Si le plan annonce du rouge et que la video sort en cyan, la notion n'est
    plus portee par rien, et personne ne s'en apercevra avant le montage.

ffmpeg sait tout ca. On lui demande les pixels, on compte, et on rend un
verdict. Aucun appel reseau, aucune cle.
"""

from __future__ import annotations

import colorsys
import json
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from . import validator
from .models import Storyboard

#: Le 9:16, et la tolerance qu'on accorde a un encodeur.
RATIO_CIBLE = 9 / 16
TOLERANCE_RATIO = 0.02
#: Au-dela, la duree rendue ne tient plus dans le plan.
TOLERANCE_DUREE = 0.5
#: En dessous, une couleur annoncee n'est pas vraiment a l'ecran.
PART_MINIMALE = 0.10

#: Un pixel ne compte que s'il est franchement colore ET lumineux : le reste
#: est du decor sombre, et il noierait la mesure.
SATURATION_MIN = 0.45
LUMINOSITE_MIN = 0.35

#: Les bornes de teinte, en degres. Le cyan a sa propre case : c'est la
#: couleur que rendent les generateurs quand on leur demande du bleu, et la
#: confondre avec du bleu ferait passer pour juste un plan qui ne l'est pas.
TEINTES = (("rouge", 330, 20), ("orange", 20, 45), ("vert", 45, 165),
           ("cyan", 165, 200), ("bleu", 200, 265), ("violet", 265, 330))

#: Les noms anglais du code couleur, ramenes aux cases ci-dessus.
FRANCAIS = {"red": "rouge", "orange": "orange", "yellow": "orange",
            "green": "vert", "cyan": "cyan", "blue": "bleu", "purple": "violet",
            "violet": "violet", "grey": None, "gray": None, "white": None,
            "black": None}


@dataclass
class Mesure:
    """Une video rendue, mesuree contre le plan qui l'a demandee."""

    shot_id: int
    fichier: Path
    largeur: int = 0
    hauteur: int = 0
    duree: float = 0.0
    attendue: float = 0.0
    couleurs: Counter = field(default_factory=Counter)
    voulues: list[str] = field(default_factory=list)
    manques: list[str] = field(default_factory=list)

    @property
    def ratio(self) -> float:
        return self.largeur / self.hauteur if self.hauteur else 0.0

    @property
    def ok(self) -> bool:
        return not self.manques


def sonder(video: Path) -> dict:
    """Largeur, hauteur et duree, telles que ffprobe les lit."""
    sortie = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-show_entries", "format=duration",
         "-of", "json", str(video)],
        capture_output=True, text=True, timeout=60)
    if sortie.returncode != 0:
        raise RuntimeError(f"ffprobe a refuse {video.name} : {sortie.stderr.strip()}")
    brut = json.loads(sortie.stdout or "{}")
    flux = (brut.get("streams") or [{}])[0]
    return {"largeur": int(flux.get("width") or 0),
            "hauteur": int(flux.get("height") or 0),
            "duree": float((brut.get("format") or {}).get("duration") or 0.0)}


def pixels(video: Path, par_seconde: int = 2, largeur: int = 64) -> bytes:
    """Les images de la video, minuscules et en RGB brut."""
    sortie = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(video), "-vf",
         f"fps={par_seconde},scale={largeur}:-2,format=rgb24", "-f", "rawvideo", "-"],
        capture_output=True, timeout=300)
    if sortie.returncode != 0:
        raise RuntimeError(f"ffmpeg a refuse {video.name} : "
                           f"{sortie.stderr.decode(errors='replace').strip()[:200]}")
    return sortie.stdout


def teintes(brut: bytes) -> Counter:
    """La part de chaque teinte parmi les pixels lumineux et colores."""
    compte: Counter = Counter()
    vifs = 0
    for i in range(0, len(brut) - 2, 3):
        h, s, v = colorsys.rgb_to_hsv(brut[i] / 255, brut[i + 1] / 255, brut[i + 2] / 255)
        if s < SATURATION_MIN or v < LUMINOSITE_MIN:
            continue
        vifs += 1
        compte[nommer(h * 360)] += 1
    if not vifs:
        return Counter()
    return Counter({nom: n / vifs for nom, n in compte.items()})


def nommer(degres: float) -> str:
    for nom, debut, fin in TEINTES:
        if debut > fin:                      # le rouge enjambe le zero
            if degres >= debut or degres < fin:
                return nom
        elif debut <= degres < fin:
            return nom
    return "rouge"


def couleurs_du_plan(sb: Storyboard, shot) -> list[str]:
    """Les couleurs du code que CE plan annonce dans son prompt photo.

    On lit le prompt tel qu'il part chez le generateur, direction artistique
    coupee : ce que la video doit rendre est ce que le plan a demande.
    """
    image = validator.own_part(shot.image_prompt, sb.empreinte()).lower()
    voulues = []
    for entree in sb.code_couleur():
        # Mots entiers : « vert » vit dans « vertical », et le tout premier
        # essai a reclame du vert a cinq plans sur cinq pour cette seule raison.
        if entree.moving and validator.presents(entree.couleurs, image):
            nom = next((FRANCAIS.get(c) for c in entree.couleurs if FRANCAIS.get(c)), None)
            if nom and nom not in voulues:
                voulues.append(nom)
    return voulues


def mesurer(sb: Storyboard, videos: dict) -> list[Mesure]:
    """Chaque video rendue, face au plan qui l'a demandee."""
    out = []
    for shot in sb.shots:
        fichier = videos.get(shot.id)
        if fichier is None:
            continue
        forme = sonder(fichier)
        m = Mesure(shot_id=shot.id, fichier=fichier, attendue=shot.duration_seconds,
                   **forme)
        m.couleurs = teintes(pixels(fichier))
        m.voulues = couleurs_du_plan(sb, shot)
        m.manques = juger(m)
        out.append(m)
    return out


def juger(m: Mesure) -> list[str]:
    """Ce qui, dans cette video, ne tient pas le plan."""
    manques = []
    if abs(m.ratio - RATIO_CIBLE) > TOLERANCE_RATIO:
        manques.append(f"format {m.largeur}x{m.hauteur} ({m.ratio:.3f}) au lieu de "
                       f"9:16 ({RATIO_CIBLE:.3f})")
    if abs(m.duree - m.attendue) > TOLERANCE_DUREE:
        manques.append(f"{m.duree:.1f}s rendues pour {m.attendue:g}s prévues "
                       f"({m.duree - m.attendue:+.1f}s)")
    if not m.couleurs:
        manques.append("aucun pixel lumineux coloré : le phénomène n'est pas à l'écran")
    for voulue in m.voulues:
        part = m.couleurs.get(voulue, 0.0)
        if part < PART_MINIMALE:
            manques.append(f"le plan annonce du {voulue}, la vidéo en porte "
                           f"{part * 100:.1f}% — la notion n'est portée par rien")
    return manques


def rapport(mesures: list[Mesure]) -> str:
    """La feuille a lire depuis un telephone."""
    lignes = ["## Mesure des vidéos rendues", "",
              "*Aucun appel réseau : ffmpeg et un compteur de pixels.*", "",
              "| plan | format | durée | attendue | couleurs à l'écran | verdict |",
              "|---|---|---|---|---|---|"]
    for m in mesures:
        vues = " · ".join(f"{nom} {part * 100:.0f}%"
                          for nom, part in m.couleurs.most_common(3)
                          if part >= 0.05) or "—"
        lignes.append(f"| {m.shot_id:02d} | {m.largeur}×{m.hauteur} | {m.duree:.1f}s | "
                      f"{m.attendue:g}s | {vues} | "
                      f"{'OK' if m.ok else f'{len(m.manques)} point(s)'} |")
    lignes.append("")
    for m in mesures:
        if m.manques:
            lignes.append(f"**Plan {m.shot_id:02d}** — {m.fichier.name}")
            lignes += [f"  · {x}" for x in m.manques]
            lignes.append("")
    return "\n".join(lignes)
