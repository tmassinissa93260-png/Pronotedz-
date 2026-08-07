"""Analyse **visuelle** d'une vidéo : mesurer son style pour pouvoir le refaire.

Ce module répond à une question précise : « à quoi ressemble cette vidéo,
chiffres à l'appui ? » — pour qu'on puisse ensuite produire des images qui
lui ressemblent au lieu de deviner.

Tout ce qui est ici est **mesuré** localement, sans IA et sans coût. C'est le
niveau 1 de docs/02-faisabilite.md : ce qui sort d'un traitement du signal est
fiable à 90-99 %, contrairement à ce qu'un modèle *croit voir*.

Ce qu'on mesure, et pourquoi :

  · **la palette** — les 6 couleurs dominantes et leur poids. C'est ce qui rend
    deux vidéos « de la même série » avant même qu'on ait regardé le contenu.
  · **la luminosité, le contraste, la saturation** — un rendu pastel doux et un
    rendu néon saturé demandent deux prompts opposés.
  · **la température** — chaud/froid, l'axe qui porte l'essentiel de l'ambiance.
  · **la netteté et le grain** — distingue le rendu 3D lisse du film granuleux.
  · **le cadrage** — sujet centré ou décalé, et quelle part de l'écran il occupe.
  · **la densité de mouvement** — plan fixe, léger flottement, ou action.

Ce qu'on ne mesure PAS ici : ce que représentent les images. Reconnaître un
personnage, décrire un décor, nommer un style graphique — c'est le travail de
l'agent `analyse/charte`, qui regarde les images-clés extraites ci-dessous.
La séparation est volontaire : on sait toujours quelle partie est mesurée et
quelle partie est interprétée.
"""

from __future__ import annotations

import colorsys
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from pdz.moteur.erreurs import ErreurPdz

# Taille de travail. 192 px de large suffit pour la couleur, le contraste et
# le cadrage ; au-delà on paie du temps de calcul pour rien.
LARGEUR_TRAVAIL = 192

# Nombre d'images-clés extraites par défaut. Six couvre l'arc visuel d'un
# format court sans saturer un prompt de vision (chaque image coûte des jetons).
IMAGES_CLES = 6


@dataclass
class Couleur:
    hex: str
    part: float          # part de l'image occupée, 0-1
    teinte: float        # 0-360°
    saturation: float    # 0-1
    valeur: float        # 0-1

    @property
    def chaude(self) -> bool:
        return self.teinte < 90 or self.teinte > 300


@dataclass
class AnalyseVisuelle:
    """Le style visuel d'une vidéo, en chiffres."""

    images_cles: list[Path]
    palette: list[Couleur]

    luminosite: float          # 0-1, moyenne
    contraste: float           # 0-1, écart-type des luminances
    saturation: float          # 0-1
    temperature: float         # -1 (froid) … +1 (chaud)

    nettete: float             # 0-1, variance du laplacien normalisée
    grain: float               # 0-1, énergie haute fréquence dans les zones plates

    cadrage_x: float           # 0-1, centre de masse horizontal du détail
    cadrage_y: float           # 0-1, vertical
    echelle_sujet: float       # 0-1, part de l'image occupée par du détail

    densite_mouvement: float   # 0-1, différence moyenne entre images voisines
    confiance: float = 1.0
    detail_par_image: list[dict] = field(default_factory=list)

    # ── Lectures ─────────────────────────────────────────────────────────

    @property
    def palette_hex(self) -> list[str]:
        return [c.hex for c in self.palette]

    @property
    def cadrage(self) -> str:
        """Nomme le cadrage plutôt que de livrer deux flottants bruts."""
        if abs(self.cadrage_x - 0.5) < 0.08 and abs(self.cadrage_y - 0.5) < 0.10:
            return "centré"
        vertical = "haut" if self.cadrage_y < 0.42 else (
            "bas" if self.cadrage_y > 0.58 else "milieu")
        horizontal = "gauche" if self.cadrage_x < 0.42 else (
            "droite" if self.cadrage_x > 0.58 else "centre")
        return f"{horizontal}-{vertical}"

    @property
    def plan(self) -> str:
        """Traduit l'échelle du sujet en vocabulaire de cadrage."""
        if self.echelle_sujet > 0.55:
            return "gros plan"
        if self.echelle_sujet > 0.30:
            return "plan rapproché"
        if self.echelle_sujet > 0.15:
            return "plan moyen"
        return "plan large"

    @property
    def rendu_probable(self) -> str:
        """Une hypothèse sur la nature du rendu, à partir des seules mesures.

        Volontairement prudente : c'est un indice donné à l'agent de vision,
        pas une conclusion. Un rendu 3D est lisse et saturé ; un métrage filmé
        est granuleux ; un dessin au trait est net et peu saturé.
        """
        if self.grain > 0.35:
            return "métrage filmé ou texture granuleuse"
        if self.saturation < 0.18 and self.contraste > 0.28:
            return "trait graphique, aplats, peu de couleur"
        if self.nettete > 0.55 and self.saturation > 0.45:
            return "rendu synthétique lisse et saturé (3D ou illustration)"
        return "rendu indéterminé"

    def resume(self) -> str:
        return (
            f"palette {' '.join(self.palette_hex[:4])} · "
            f"lum {self.luminosite:.2f} · contraste {self.contraste:.2f} · "
            f"sat {self.saturation:.2f} · "
            f"{'chaud' if self.temperature > 0.05 else 'froid' if self.temperature < -0.05 else 'neutre'} "
            f"({self.temperature:+.2f}) · netteté {self.nettete:.2f} · "
            f"grain {self.grain:.2f} · {self.plan} {self.cadrage} · "
            f"mouvement {self.densite_mouvement:.2f}"
        )

    def bloc_pour_prompt(self) -> str:
        """Les mesures, mises en forme pour être lues par un modèle.

        Volontairement compact : ces lignes entrent dans le prompt de l'agent
        de vision, et chaque jeton y est payé.
        """
        couleurs = ", ".join(f"{c.hex} ({c.part:.0%})" for c in self.palette)
        return "\n".join([
            f"Palette dominante : {couleurs}",
            f"Luminosité {self.luminosite:.2f}/1 · contraste {self.contraste:.2f} "
            f"· saturation {self.saturation:.2f}",
            f"Température : {self.temperature:+.2f} "
            f"({'dominante chaude' if self.temperature > 0.05 else 'dominante froide' if self.temperature < -0.05 else 'neutre'})",
            f"Netteté {self.nettete:.2f} · grain {self.grain:.2f} "
            f"→ {self.rendu_probable}",
            f"Cadrage type : {self.plan}, sujet {self.cadrage}",
            f"Densité de mouvement : {self.densite_mouvement:.2f}/1",
        ])


# ── Extraction des images ────────────────────────────────────────────────

def extraire_images(chemin: Path, instants_s: list[float],
                    dossier: Path) -> list[tuple[Path, float]]:
    """Sort une image PNG à chaque instant demandé, avec son instant.

    On renvoie les couples (fichier, instant) et non deux listes séparées :
    une extraction peut échouer — fin de fichier, image corrompue — et les
    deux listes se décalent alors silencieusement. Le rapport annoncerait
    ensuite les mesures de l'image 4 à la position de l'image 3.

    `-ss` est placé **avant** `-i` : ffmpeg saute alors directement à la
    position au lieu de décoder toute la vidéo depuis le début. Sur une vidéo
    de 80 s c'est la différence entre 0,2 s et 6 s par image.
    """
    dossier.mkdir(parents=True, exist_ok=True)
    sorties: list[tuple[Path, float]] = []

    for i, t in enumerate(instants_s):
        destination = dossier / f"cle_{i:02d}.png"
        r = subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
             "-ss", f"{max(0.0, t):.3f}", "-i", str(chemin),
             "-frames:v", "1", "-q:v", "2", str(destination)],
            capture_output=True, text=True, timeout=120,
        )
        if r.returncode == 0 and destination.exists() and destination.stat().st_size:
            sorties.append((destination, t))

    if not sorties:
        raise ErreurPdz(
            f"Aucune image n'a pu être extraite de {Path(chemin).name}. "
            "Le fichier est-il lisible par ffmpeg ?"
        )
    return sorties


def instants_representatifs(duree_s: float, coupes: list[float] | None = None,
                            combien: int = IMAGES_CLES) -> list[float]:
    """Choisit *quand* regarder la vidéo.

    Avec les coupes, on prend le **milieu** des plans les plus longs : c'est
    là que l'image est stable et représentative. Sans coupes, on répartit
    régulièrement en évitant les bords (générique de début, fondu de fin).
    """
    if coupes:
        bornes = [0.0, *coupes, duree_s]
        plans = [(a, b) for a, b in zip(bornes, bornes[1:], strict=False)
                 if b - a > 0.35]
        plans.sort(key=lambda p: p[1] - p[0], reverse=True)
        milieux = sorted((a + b) / 2 for a, b in plans[:combien])
        if milieux:
            return milieux

    marge = duree_s * 0.06
    utile = max(0.1, duree_s - 2 * marge)
    return [marge + utile * (i + 0.5) / combien for i in range(combien)]


# ── Mesures sur une image ────────────────────────────────────────────────

def _charger(chemin: Path, largeur: int = LARGEUR_TRAVAIL) -> np.ndarray:
    """Image en tableau (H, W, 3) de flottants 0-1, réduite à `largeur`."""
    from PIL import Image

    img = Image.open(chemin).convert("RGB")
    hauteur = max(1, round(img.height * largeur / img.width))
    img = img.resize((largeur, hauteur), Image.BILINEAR)
    return np.asarray(img, dtype=np.float32) / 255.0


def _luminance(rgb: np.ndarray) -> np.ndarray:
    """Luminance perçue (Rec. 601) — pas la moyenne des canaux.

    Le vert pèse six fois le bleu dans la perception ; une moyenne naïve
    juge une image bleue « aussi claire » qu'une image verte, ce qui fausse
    contraste et netteté.
    """
    return rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114


def _laplacien(gris: np.ndarray) -> np.ndarray:
    """Laplacien 4-voisins, écrit à la main pour éviter une dépendance."""
    p = np.pad(gris, 1, mode="edge")
    return (p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]
            - 4.0 * p[1:-1, 1:-1])


def _flou_boite(gris: np.ndarray, rayon: int = 2) -> np.ndarray:
    """Moyenne locale par image intégrale : O(1) par pixel, quel que soit le rayon."""
    p = np.pad(gris, rayon + 1, mode="edge")
    somme = p.cumsum(0).cumsum(1)
    k = 2 * rayon + 1
    h, w = gris.shape
    bloc = (somme[k:k + h, k:k + w] - somme[:h, k:k + w]
            - somme[k:k + h, :w] + somme[:h, :w])
    return bloc / (k * k)


def _mesurer_image(rgb: np.ndarray) -> dict:
    gris = _luminance(rgb)
    maxi = rgb.max(axis=2)
    mini = rgb.min(axis=2)

    # Saturation HSV : (max - min) / max, indéfinie sur le noir pur.
    sat = np.where(maxi > 1e-4, (maxi - mini) / np.maximum(maxi, 1e-4), 0.0)

    lap = _laplacien(gris)
    # La variance du laplacien est la mesure de netteté classique. On la
    # comprime par une saturation douce : elle varie sur plusieurs ordres de
    # grandeur, une échelle 0-1 linéaire n'aurait aucune lisibilité.
    v = float(lap.var())
    nettete = v / (v + 0.0012)

    # Grain : énergie haute fréquence là où l'image est PLATE. Sur un contour,
    # la haute fréquence est du dessin, pas du bruit — d'où le masque.
    detail = np.abs(gris - _flou_boite(gris, 2))
    plat = detail < np.quantile(detail, 0.55)
    bruit = float(detail[plat].mean()) if plat.any() else 0.0
    grain = min(1.0, bruit / 0.012)

    # Cadrage : centre de masse du gradient. Là où il y a du détail, il y a
    # le sujet — bien plus robuste qu'une détection de visage sur du dessin.
    poids = np.abs(lap)
    seuil = float(np.quantile(poids, 0.80))
    masque = poids >= max(seuil, 1e-6)
    if masque.any():
        total = float(poids[masque].sum()) or 1.0
        ys, xs = np.nonzero(masque)
        cx = float((poids[masque] * xs).sum() / total / max(1, rgb.shape[1] - 1))
        cy = float((poids[masque] * ys).sum() / total / max(1, rgb.shape[0] - 1))
        echelle = float(masque.mean()) / 0.20
    else:
        # Image entièrement plate (aplat de couleur, fondu au noir) : il n'y a
        # pas de sujet. Annoncer « sujet en haut à gauche » serait faux ;
        # on renvoie le centre et une échelle nulle, ce qui est vérifiable.
        cx, cy, echelle = 0.5, 0.5, 0.0

    # Température : rouge contre bleu, pondéré par la saturation (une zone
    # grise n'est ni chaude ni froide, quel que soit son écart R-B).
    ecart = (rgb[..., 0] - rgb[..., 2]) * sat
    temperature = float(np.clip(ecart.mean() * 4.0, -1.0, 1.0))

    return {
        "luminosite": float(gris.mean()),
        "contraste": float(gris.std()),
        "saturation": float(sat.mean()),
        "temperature": temperature,
        "nettete": round(nettete, 3),
        "grain": round(grain, 3),
        "cadrage_x": round(cx, 3),
        "cadrage_y": round(cy, 3),
        "echelle_sujet": round(echelle, 3),
    }


# ── Palette ──────────────────────────────────────────────────────────────

def palette_dominante(images: list[np.ndarray], combien: int = 6) -> list[Couleur]:
    """Les couleurs qui structurent la vidéo, toutes images confondues.

    Choix : un regroupement par **teinte et clarté** plutôt qu'un k-means.
    Sur des images d'un même univers, le k-means renvoie six nuances d'une
    même couleur dominante (six bleus légèrement différents) et rate les
    accents rares mais identitaires — le rouge d'un logo, le jaune d'un néon.
    Regrouper par teinte les sépare par construction.
    """
    if not images:
        return []

    pixels = np.concatenate([im.reshape(-1, 3) for im in images], axis=0)
    # Échantillonnage : au-delà de ~40 000 pixels, la palette ne bouge plus.
    if pixels.shape[0] > 40000:
        pas = pixels.shape[0] // 40000
        pixels = pixels[::pas]

    maxi, mini = pixels.max(axis=1), pixels.min(axis=1)
    sat = np.where(maxi > 1e-4, (maxi - mini) / np.maximum(maxi, 1e-4), 0.0)
    val = maxi

    # 12 secteurs de teinte + 3 paniers de clarté pour les gris.
    teintes = np.zeros(pixels.shape[0], dtype=np.float32)
    delta = np.maximum(maxi - mini, 1e-6)
    r, g, b = pixels[:, 0], pixels[:, 1], pixels[:, 2]
    est_r, est_g = (maxi == r), (maxi == g)
    teintes = np.where(est_r, ((g - b) / delta) % 6,
                       np.where(est_g, (b - r) / delta + 2, (r - g) / delta + 4)) * 60.0

    colore = sat > 0.16
    cles = np.where(
        colore,
        (teintes / 30.0).astype(np.int32) % 12,          # 0-11 : secteurs colorés
        12 + np.clip((val * 3).astype(np.int32), 0, 2),  # 12-14 : gris
    )

    groupes: list[Couleur] = []
    for cle in np.unique(cles):
        masque = cles == cle
        part = float(masque.mean())
        if part < 0.012:                                  # bruit, pas une couleur
            continue
        moyenne = pixels[masque].mean(axis=0)
        h, s, v = colorsys.rgb_to_hsv(*(float(c) for c in moyenne))
        groupes.append(Couleur(
            hex="#{:02X}{:02X}{:02X}".format(*(int(round(c * 255)) for c in moyenne)),
            part=round(part, 4), teinte=round(h * 360, 1),
            saturation=round(s, 3), valeur=round(v, 3),
        ))

    groupes.sort(key=lambda c: c.part, reverse=True)
    return groupes[:combien]


# ── Analyse complète ─────────────────────────────────────────────────────

def analyser(chemin: Path, duree_s: float, *, coupes: list[float] | None = None,
             dossier_images: Path | None = None,
             combien: int = IMAGES_CLES) -> AnalyseVisuelle:
    """Mesure le style visuel d'une vidéo. Aucune IA, aucun coût."""
    chemin = Path(chemin)
    if not chemin.exists():
        raise ErreurPdz(f"Vidéo introuvable : {chemin}")

    dossier = dossier_images or chemin.parent / f"_visuel_{chemin.stem}"
    demandes = instants_representatifs(duree_s, coupes, combien)
    extraites = extraire_images(chemin, demandes, dossier)
    fichiers = [f for f, _ in extraites]
    instants = [t for _, t in extraites]

    tableaux = [_charger(f) for f in fichiers]
    mesures = [_mesurer_image(t) for t in tableaux]

    def med(cle: str) -> float:
        # Médiane et non moyenne : une seule image-clé tombée sur un fondu au
        # noir suffirait à tirer une moyenne vers le bas.
        return round(float(np.median([m[cle] for m in mesures])), 3)

    # Densité de mouvement : écart entre images-clés consécutives, ramené à
    # l'intervalle de temps qui les sépare. Sans cette normalisation, deux
    # images prises à 10 s d'écart paraîtraient toujours « très animées ».
    diffs = []
    paires = list(zip(tableaux, instants, strict=True))
    for (a, ta), (b, tb) in zip(paires, paires[1:], strict=False):
        if a.shape != b.shape:
            continue
        ecart = float(np.abs(_luminance(a) - _luminance(b)).mean())
        diffs.append(ecart / max(0.5, tb - ta) * 2.0)
    mouvement = round(min(1.0, float(np.median(diffs))) if diffs else 0.0, 3)

    # Confiance : la dispersion des mesures entre images. Une vidéo au style
    # constant donne des mesures serrées ; un montage qui mélange trois styles
    # donne une moyenne qui ne décrit aucune de ses parties — il vaut mieux
    # le dire que de livrer un chiffre unique trompeur.
    dispersions = [
        float(np.std([m[c] for m in mesures]))
        for c in ("luminosite", "saturation", "temperature")
    ]
    confiance = round(max(0.0, 1.0 - float(np.mean(dispersions)) * 3.0), 2)

    return AnalyseVisuelle(
        images_cles=fichiers,
        palette=palette_dominante(tableaux),
        luminosite=med("luminosite"),
        contraste=med("contraste"),
        saturation=med("saturation"),
        temperature=med("temperature"),
        nettete=med("nettete"),
        grain=med("grain"),
        cadrage_x=med("cadrage_x"),
        cadrage_y=med("cadrage_y"),
        echelle_sujet=min(1.0, med("echelle_sujet")),
        densite_mouvement=mouvement,
        confiance=confiance,
        detail_par_image=[
            {"instant_s": round(t, 2), "image": f.name, **m}
            for t, f, m in zip(instants, fichiers, mesures, strict=True)
        ],
    )
