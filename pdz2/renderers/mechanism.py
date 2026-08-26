"""Grammaire de mouvement dessinée : ce qui bouge **dans** le cadre.

Le §17 du cahier des charges demande « une bibliothèque de primitives de
mouvement, chaque primitive ayant une représentation mathématique ». Le
contrat en déclare dix. Deux étaient honorées, et par une rotation du calque
entier — ce qui fait tourner l'image, pas le mécanisme.

Le reste du renderer déplace la **caméra** : un recadrage progressif, des
calques qui glissent. C'est du mouvement d'appareil sur une image fixe. Le
spectateur du run #7 l'a dit sans détour : « moteur qui tourne, électricité
qui bouge » — et rien de tel n'existait.

Ce module dessine ce mouvement-là. Il ne décide rien : il reçoit un
`MotionProgram` déjà tranché, une palette déjà fixée par la bible visuelle, et
un instant normalisé. Il rend des pixels.

## Ce qu'il n'est pas

Ce n'est pas un moteur de simulation physique, et il ne prétend pas l'être. Il
ne sait pas ce qu'est un rotor : il sait qu'on lui demande une ROTATION, et il
dessine une rotation lisible — repères qui tournent autour du centre du cadre.
Il ne sait pas ce qu'est un courant : il sait qu'on lui demande un FLUX dans
une direction, et il fait défiler des marqueurs dans cette direction.

La justesse scientifique de l'association « ce mécanisme se démontre par une
rotation » appartient au compilateur de plans, qui la tire du type
d'affirmation. Ce module exécute, il ne juge pas.

## Déterminisme

Aucun aléa, aucune horloge. Le même programme au même instant donne les mêmes
octets — sans quoi l'observateur mesurerait le bruit du rendu et le prendrait
pour du mouvement.
"""

from __future__ import annotations

import math

from PIL import Image, ImageDraw

from pdz2.contracts.motion import MotionPrimitive, MotionProgram

__all__ = ["draw_mechanism", "ANIMATED_PRIMITIVES", "MARKERS"]

ANIMATED_PRIMITIVES: frozenset[MotionPrimitive] = frozenset(
    {
        MotionPrimitive.ROTATE,
        MotionPrimitive.ORBIT,
        MotionPrimitive.FLOW,
        MotionPrimitive.OSCILLATE,
        MotionPrimitive.LINEAR,
        MotionPrimitive.ARC,
        MotionPrimitive.SPIRAL,
        MotionPrimitive.SCALE,
        MotionPrimitive.JITTER,
    }
)
"""Primitives que ce module sait réellement dessiner.

`STATIC` en est absent, et c'est une réponse : un sujet immobile n'a rien à
animer. Toute autre absence serait une lacune, et le routeur la déclarerait.
"""

MARKERS = 7
"""Nombre de marqueurs sur un flux ou une orbite.

Assez pour lire une direction sans compter, assez peu pour ne pas masquer
l'image qu'ils commentent."""

_STROKE = 0.006
"""Épaisseur des traits, en fraction de la largeur du cadre."""

_INSET = 0.16
"""Marge entre les indicateurs et le bord, en fraction du cadre."""

_ALPHA = 216
"""Opacité des indicateurs. Assez présents pour se lire, assez discrets pour
ne pas devenir le sujet."""


def _rgba(couleur: tuple[int, int, int], alpha: int = _ALPHA) -> tuple[int, ...]:
    return (*couleur, alpha)


def _teintes(palette: list[tuple[int, int, int]]) -> tuple[tuple, tuple]:
    """Trait principal et rappel. L'accent de la bible passe devant.

    La palette est ordonnée : la dominante en tête. Un indicateur peint dans
    la dominante disparaîtrait dans l'image ; on prend donc l'accent le plus
    éloigné disponible.
    """
    if not palette:
        return ((255, 255, 255), (255, 255, 255))
    accent = palette[min(2, len(palette) - 1)]
    rappel = palette[min(3, len(palette) - 1)]
    return (accent, rappel)


def draw_mechanism(
    frame: Image.Image,
    motion: MotionProgram,
    t: float,
    *,
    palette: list[tuple[int, int, int]],
) -> Image.Image:
    """Dessine le mouvement du sujet sur l'image, à l'instant `t` ∈ [0, 1].

    Rend l'image inchangée quand le programme ne demande aucun mouvement de
    sujet, ou quand la primitive demandée n'est pas dessinable ici — dans ce
    second cas le routeur a déjà inscrit la dégradation, et rien ne serait
    gagné à inventer un mouvement approchant.
    """
    primitive = motion.subject_motion.primitive
    if primitive not in ANIMATED_PRIMITIVES:
        return frame

    largeur, hauteur = frame.size
    calque = Image.new("RGBA", (largeur, hauteur), (0, 0, 0, 0))
    dessin = ImageDraw.Draw(calque)
    accent, rappel = _teintes(palette)
    trait = max(2, int(largeur * _STROKE))
    intensite = max(0.15, min(1.0, motion.subject_motion.magnitude or 0.5))

    if primitive in {MotionPrimitive.ROTATE, MotionPrimitive.ORBIT}:
        _rotation(dessin, largeur, hauteur, t, trait, accent, rappel, intensite,
                  motion.subject_motion.trajectory.amplitude)
    elif primitive in {MotionPrimitive.FLOW, MotionPrimitive.LINEAR}:
        _flux(dessin, largeur, hauteur, t, trait, accent, rappel, intensite,
              motion.subject_motion.direction.x, motion.subject_motion.direction.y)
    elif primitive is MotionPrimitive.OSCILLATE:
        _pulsation(dessin, largeur, hauteur, t, trait, accent, intensite)
    elif primitive is MotionPrimitive.SCALE:
        _echelle(dessin, largeur, hauteur, t, trait, accent, intensite)
    elif primitive in {MotionPrimitive.ARC, MotionPrimitive.SPIRAL}:
        _spirale(dessin, largeur, hauteur, t, trait, accent, rappel, intensite)
    elif primitive is MotionPrimitive.JITTER:
        _tremblement(dessin, largeur, hauteur, t, trait, accent, intensite)

    return Image.alpha_composite(frame.convert("RGBA"), calque).convert(frame.mode)


# ------------------------------------------------------------- les primitives


def _rotation(dessin, w, h, t, trait, accent, rappel, intensite, amplitude) -> None:
    """Repères tournant autour du centre : un mécanisme se démontre en tournant.

    L'amplitude vient de la trajectoire du contrat, en degrés. Le mouvement
    est continu et non bouclé : à `t = 1` le repère a parcouru exactement
    l'amplitude demandée, ce qui rend la mesure de l'observateur comparable à
    l'intention.
    """
    cx, cy = w / 2, h / 2
    rayon = min(w, h) * (0.5 - _INSET)
    depart = math.radians(amplitude * t)
    for index in range(MARKERS):
        angle = depart + index * (2 * math.pi / MARKERS)
        couleur = accent if index % 2 == 0 else rappel
        longueur = rayon * (0.18 if index % 2 == 0 else 0.11)
        x0 = cx + math.cos(angle) * (rayon - longueur)
        y0 = cy + math.sin(angle) * (rayon - longueur)
        x1 = cx + math.cos(angle) * rayon
        y1 = cy + math.sin(angle) * rayon
        dessin.line([(x0, y0), (x1, y1)], fill=_rgba(couleur), width=trait)
    dessin.ellipse(
        [cx - rayon, cy - rayon, cx + rayon, cy + rayon],
        outline=_rgba(accent, int(_ALPHA * 0.45)),
        width=max(1, trait // 2),
    )


def _flux(dessin, w, h, t, trait, accent, rappel, intensite, dx, dy) -> None:
    """Marqueurs défilant dans une direction : le courant qui circule.

    La direction vient du contrat. Sans direction utilisable, le flux part de
    la gauche vers la droite — le sens de lecture, qui ne surprend personne.
    """
    norme = math.hypot(dx, dy)
    if norme < 1e-6:
        dx, dy, norme = 1.0, 0.0, 1.0
    dx, dy = dx / norme, dy / norme

    marge = min(w, h) * _INSET
    cx, cy = w / 2, h / 2
    portee = (min(w, h) / 2 - marge) * 1.8
    perpendiculaire = (-dy, dx)

    for voie in (-1, 0, 1):
        decalage = voie * min(w, h) * 0.14
        ox = cx + perpendiculaire[0] * decalage
        oy = cy + perpendiculaire[1] * decalage
        for index in range(MARKERS):
            # Progression cyclique : chaque marqueur avance, et celui qui sort
            # réapparaît de l'autre côté. Le flux est continu, pas saccadé.
            avance = ((index / MARKERS) + t * intensite * 2.0) % 1.0
            position = (avance - 0.5) * portee
            x = ox + dx * position
            y = oy + dy * position
            taille = trait * 2.2
            # Une pointe orientée dans le sens du flux, pas un simple point :
            # un point ne dit pas dans quel sens l'énergie va.
            pointe = (x + dx * taille * 1.6, y + dy * taille * 1.6)
            gauche = (x - dx * taille + perpendiculaire[0] * taille,
                      y - dy * taille + perpendiculaire[1] * taille)
            droite = (x - dx * taille - perpendiculaire[0] * taille,
                      y - dy * taille - perpendiculaire[1] * taille)
            couleur = accent if voie == 0 else rappel
            dessin.polygon([pointe, gauche, droite], fill=_rgba(couleur))


def _pulsation(dessin, w, h, t, trait, accent, intensite) -> None:
    """Anneaux concentriques qui respirent : un champ qui s'établit et retombe."""
    cx, cy = w / 2, h / 2
    base = min(w, h) * (0.5 - _INSET)
    for index in range(3):
        phase = math.sin(2 * math.pi * (t * 2.0 * intensite + index / 3.0))
        rayon = base * (0.45 + 0.18 * index + 0.10 * phase)
        opacite = int(_ALPHA * (0.35 + 0.4 * (phase * 0.5 + 0.5)))
        dessin.ellipse(
            [cx - rayon, cy - rayon, cx + rayon, cy + rayon],
            outline=_rgba(accent, opacite),
            width=trait,
        )


def _echelle(dessin, w, h, t, trait, accent, intensite) -> None:
    """Un cadre qui s'ouvre : une grandeur qui croît."""
    cx, cy = w / 2, h / 2
    base = min(w, h) * (0.5 - _INSET)
    rayon = base * (0.35 + 0.6 * t * intensite)
    dessin.rectangle(
        [cx - rayon, cy - rayon, cx + rayon, cy + rayon],
        outline=_rgba(accent),
        width=trait,
    )


def _spirale(dessin, w, h, t, trait, accent, rappel, intensite) -> None:
    """Une trajectoire courbe qui se déroule : un parcours, pas un point."""
    cx, cy = w / 2, h / 2
    base = min(w, h) * (0.5 - _INSET)
    points = []
    tours = 2.5
    pas = 90
    for index in range(pas + 1):
        part = index / pas
        angle = 2 * math.pi * tours * part + t * 2 * math.pi * intensite
        rayon = base * (0.15 + 0.85 * part)
        points.append((cx + math.cos(angle) * rayon, cy + math.sin(angle) * rayon))
    dessin.line(points, fill=_rgba(accent), width=trait, joint="curve")
    tete = points[min(len(points) - 1, int(pas * (0.3 + 0.7 * t)))]
    dessin.ellipse(
        [tete[0] - trait * 2, tete[1] - trait * 2,
         tete[0] + trait * 2, tete[1] + trait * 2],
        fill=_rgba(rappel),
    )


def _tremblement(dessin, w, h, t, trait, accent, intensite) -> None:
    """Une agitation bornée. Déterministe : une somme de sinus, pas un tirage."""
    cx, cy = w / 2, h / 2
    base = min(w, h) * (0.5 - _INSET) * 0.5
    for index in range(MARKERS):
        phase = index * 1.7
        dx = math.sin(2 * math.pi * (t * 6.0 + phase)) * base * 0.12 * intensite
        dy = math.cos(2 * math.pi * (t * 5.0 + phase)) * base * 0.12 * intensite
        angle = index * (2 * math.pi / MARKERS)
        x = cx + math.cos(angle) * base + dx
        y = cy + math.sin(angle) * base + dy
        dessin.ellipse(
            [x - trait, y - trait, x + trait, y + trait], fill=_rgba(accent)
        )
