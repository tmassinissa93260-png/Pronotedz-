"""Les verifications imposees avant de rendre un storyboard.

Chaque probleme porte sa consigne de correction, adressee a OpenAI : le
validateur ne dit pas seulement non, il dit quoi refaire.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import COLOR_NOTION, EXPLICATION_FIELDS, QUALITY_AXES, Storyboard
from .prompts import STYLE_FINGERPRINT

MIN_WORDS_PER_SECOND = 1.8
MAX_WORDS_PER_SECOND = 4.0
MIN_QUALITY = 0.8
MIN_IMAGE_PROMPT_CHARS = 260
MIN_ANIMATION_PROMPT_CHARS = 120
DURATION_TOLERANCE_S = 0.5

# CONDITION : le prompt photo doit dire ou est quoi, comment c'est cadre,
# sous quelle lumiere, en quels materiaux.
SPECIFICITY_FAMILIES = {
    "cadrage": ("shot", "framing", "close-up", "closeup", "wide", "medium", "macro", "view"),
    "camera": ("camera", "angle", "lens", "perspective", "eye level", "low angle", "high angle"),
    "position": ("left", "right", "centre", "center", "beneath", "under", "above", "behind",
                 "front", "rear", "between", "along", "inside", "mounted", "positioned",
                 "toward", "towards", "into", "around"),
    "lumiere": ("light", "lighting", "lit", "illuminat", "volumetric", "backlight", "rim"),
    "materiaux": ("material", "metal", "aluminium", "aluminum", "copper", "composite",
                  "matte", "paint", "plastic", "steel", "glass", "rubber"),
}

# Mots qui signalent un phenomene invisible rendu visible.
PHENOMENE = ("energy", "current", "electric", "flow", "stream", "pulse", "particle",
             "field", "charge", "power", "signal", "heat")

# Verbes de mouvement qui font vraiment bouger la chose.
MOUVEMENT = ("flow", "travel", "move", "pulse", "circulat", "rotat", "spin", "turn",
             "illuminat", "light up", "glow", "advance", "progress", "accelerat",
             "reverse", "enter", "exit", "rise", "propagat", "sweep")

# Un flux doit aller QUELQUE PART : sans direction lisible, le spectateur ne
# peut pas savoir dans quel sens l'energie circule.
DIRECTION = ("toward", "towards", "into", "out of", "from", "back to", "along",
             "through", "up to", "down to", "reverses", "reversing", "outward",
             "inward", "forward", "returns", "leaving", "entering")

# Mouvements de camera : ils ne comptent pas comme mouvement pedagogique.
CAMERA = ("camera", "zoom", "dolly", "pan", "tilt", "orbit", "push in", "pull out",
          "tracking shot")

# Composant nomme -> mouvement attendu si l'image le met en avant.
COMPOSANT_MOUVEMENT = {
    "rotor": ("rotat", "spin", "turn"),
    "stator": ("rotat", "spin", "turn", "stationary", "fixed", "still"),
    "crankshaft": ("rotat", "spin", "turn"),
    "piston": ("move", "travel", "stroke", "down", "up"),
    "gear": ("rotat", "mesh", "turn"),
    "transmission": ("rotat", "turn", "transmit", "carr"),
    "wheel": ("rotat", "spin", "turn"),
    "cell": ("illuminat", "light", "glow", "charge", "flow"),
}

# CONDITION : ce qui est dit doit etre montre.
SEMANTIQUE = {
    "batterie": ("battery", "cell", "pack", "module"),
    "cellule": ("cell",),
    "moteur": ("motor", "engine", "rotor", "stator", "winding"),
    "rotor": ("rotor",),
    "stator": ("stator",),
    "roue": ("wheel", "tyre", "tire", "hub"),
    "câble": ("cable", "wiring", "busbar", "harness"),
    "cable": ("cable", "wiring", "busbar", "harness"),
    "onduleur": ("inverter", "power electronics"),
    "électronique": ("electronic", "inverter", "controller", "module"),
    "electronique": ("electronic", "inverter", "controller", "module"),
    "accélérateur": ("pedal", "accelerator", "throttle"),
    "accelerateur": ("pedal", "accelerator", "throttle"),
    "pédale": ("pedal",),
    "pedale": ("pedal",),
    "transmission": ("transmission", "gear", "drivetrain", "axle"),
    "engrenage": ("gear",),
    "piston": ("piston",),
    "vilebrequin": ("crankshaft",),
    "freinage": ("brake", "regenerat"),
}


@dataclass
class Problem:
    code: str
    where: str
    message: str
    fix: str

    def __str__(self) -> str:
        return f"[{self.code}] {self.where} : {self.message}"


def validate(sb: Storyboard, duration: float, shot_count: int) -> list[Problem]:
    problems: list[Problem] = []
    problems += _plans(sb, shot_count)
    problems += _duree(sb, duration)
    problems += _debit(sb)
    problems += _fonction(sb)
    problems += _style(sb)
    problems += _precision(sb)
    problems += _continuite(sb)
    problems += _alignement(sb)
    problems += _progression(sb)
    problems += _grammaire_visuelle(sb)
    problems += _correspondance(sb)
    problems += _explication(sb)
    problems += _qualite(sb)
    return problems


# --- nombre de plans, duree, debit ------------------------------------------


def _plans(sb: Storyboard, attendu: int) -> list[Problem]:
    if len(sb.shots) == attendu:
        return []
    return [Problem("PLANS", "storyboard", f"{len(sb.shots)} plan(s) au lieu de {attendu}",
                    f"Return exactly {attendu} shots, ids 1 to {attendu}.")]


def _duree(sb: Storyboard, attendue: float) -> list[Problem]:
    out = []
    if abs(sb.total_duration - attendue) > DURATION_TOLERANCE_S:
        out.append(Problem("DUREE", "storyboard",
                           f"somme des plans = {sb.total_duration}s au lieu de {attendue}s",
                           f"The durations must sum to exactly {attendue}."))
    for s in sb.shots:
        if s.duration_seconds <= 0:
            out.append(Problem("DUREE", s.slug, f"duree invalide : {s.duration_seconds}",
                               f"Shot {s.id} needs a positive duration_seconds."))
    return out


def _debit(sb: Storyboard) -> list[Problem]:
    out = []
    for s in sb.shots:
        taux = s.words_per_second
        cible = int(s.duration_seconds * 2.7)
        if taux < MIN_WORDS_PER_SECOND:
            out.append(Problem("DEBIT", s.slug,
                               f"{s.word_count} mots pour {s.duration_seconds}s "
                               f"({taux:.1f} mot/s) : le plan serait vide",
                               f"Shot {s.id}: write about {cible} words, not {s.word_count}. "
                               f"Say more about the causal link, do not pad."))
        elif taux > MAX_WORDS_PER_SECOND:
            out.append(Problem("DEBIT", s.slug,
                               f"{s.word_count} mots pour {s.duration_seconds}s "
                               f"({taux:.1f} mot/s) : impossible a prononcer",
                               f"Shot {s.id}: shorten the narration to about {cible} words."))
    return out


def _fonction(sb: Storyboard) -> list[Problem]:
    out = []
    ids = [s.id for s in sb.shots]
    if ids != list(range(1, len(sb.shots) + 1)):
        out.append(Problem("IDS", "storyboard", f"ids non contigus : {ids}",
                           f"Number the shots 1 to {len(sb.shots)} in order."))
    for s in sb.shots:
        if len(s.educational_function) < 20:
            out.append(Problem("FONCTION", s.slug,
                               "educational_function trop vague pour justifier le plan",
                               f"Shot {s.id}: state in one full sentence what the viewer "
                               f"understands after this shot that no other shot provides."))
    return out


def _style(sb: Storyboard) -> list[Problem]:
    return [Problem("STYLE", s.slug, "direction artistique absente du prompt photo",
                    f"Shot {s.id}: end image_prompt with the mandatory art direction "
                    f"sentence, copied verbatim.")
            for s in sb.shots if STYLE_FINGERPRINT.lower() not in s.image_prompt.lower()]


# --- precision et continuite ------------------------------------------------


def own_part(image_prompt: str) -> str:
    """Le prompt photo prive de la direction artistique commune.

    On COUPE a la signature : la supprimer d'abord rendrait la coupe
    introuvable et laisserait la fin de la phrase de style passer pour du
    contenu propre au plan.
    """
    debut = image_prompt.lower().find(STYLE_FINGERPRINT.lower())
    return image_prompt if debut < 0 else image_prompt[:debut]


def _precision(sb: Storyboard) -> list[Problem]:
    out = []
    for s in sb.shots:
        propre = own_part(s.image_prompt)
        bas = propre.lower()
        if len(propre.strip()) < MIN_IMAGE_PROMPT_CHARS:
            out.append(Problem("PRECISION", s.slug,
                               f"prompt photo trop general ({len(propre.strip())} caracteres "
                               f"hors direction artistique)",
                               f"Shot {s.id}: state the subject, the phenomenon shown, the "
                               f"pedagogical elements and their colour, where each sits, the "
                               f"framing, the camera angle, the depth, the lighting, the "
                               f"materials, what to preserve and what is forbidden."))
        absentes = [nom for nom, mots in SPECIFICITY_FAMILIES.items()
                    if not any(m in bas for m in mots)]
        if absentes:
            out.append(Problem("PRECISION", s.slug,
                               f"le prompt photo ne dit rien sur : {', '.join(absentes)}",
                               f"Shot {s.id}: the image_prompt must explicitly state "
                               f"{', '.join(absentes)}."))
        if len(s.animation_prompt.strip()) < MIN_ANIMATION_PROMPT_CHARS:
            out.append(Problem("PRECISION", s.slug,
                               f"prompt d'animation trop court "
                               f"({len(s.animation_prompt.strip())} caracteres)",
                               f"Shot {s.id}: say which element moves, in which direction, at "
                               f"what speed, what stays still, and what must not deform."))
    return out


def _continuite(sb: Storyboard) -> list[Problem]:
    ancres = _ancres(sb)
    if not ancres:
        return []
    return [Problem("CONTINUITE", s.slug,
                    "le prompt photo ne reprend rien de la visual_bible",
                    f"Shot {s.id}: restate the subject, the environment and the materials "
                    f"fixed by visual_bible, so every shot shows the same object.")
            for s in sb.shots if not any(a in own_part(s.image_prompt).lower() for a in ancres)]


def _ancres(sb: Storyboard) -> list[str]:
    source = " ".join([sb.visual_bible.vehicle, sb.visual_bible.main_subject,
                       sb.visual_bible.environment]).lower()
    candidats = ("white", "silver", "black", "sedan", "hatchback", "compact", "suv", "coupe",
                 "studio", "dark", "grey", "gray", "blue", "navy", "concrete")
    return [c for c in candidats if c in source]


def _alignement(sb: Storyboard) -> list[Problem]:
    out = []
    for s in sb.shots:
        # own_part et pas le prompt entier : la direction artistique contient
        # « 3D engineering visualization », dont le « engine » suffisait a faire
        # croire qu'un moteur etait montre.
        manquants = _non_montres(s.voice, own_part(s.image_prompt))
        if manquants:
            out.append(Problem("ALIGNEMENT", s.slug,
                               f"la voix parle de {', '.join(manquants)} — "
                               f"invisible dans le prompt photo",
                               f"Shot {s.id}: the voice mentions {', '.join(manquants)}, so the "
                               f"image_prompt must show it clearly and name it."))
    return out


def _non_montres(voix: str, image: str) -> list[str]:
    """Les composants nommes par la voix et absents du prompt photo.

    Recherche sur les mots entiers : « engine » ne doit pas etre trouve dans
    « engineering », ni « cell » dans « excellent ».
    """
    v, i = voix.lower(), image.lower()
    return [fr for fr, en in SEMANTIQUE.items()
            if fr in v and not any(_mot_present(a, i) for a in en)]


def _mot_present(mot: str, texte: str) -> bool:
    """Mot entier, pluriel tolere. « engine » ne matche pas « engineering »,
    mais « winding » matche bien « windings »."""
    return re.search(rf"\b{re.escape(mot)}(s|es)?\b", texte) is not None


def _progression(sb: Storyboard) -> list[Problem]:
    out = []
    vues: dict[str, int] = {}
    for s in sb.shots:
        cle = _normalise(s.voice)
        if cle in vues:
            out.append(Problem("PROGRESSION", s.slug,
                               f"narration identique au plan {vues[cle]}",
                               f"Shot {s.id}: advance the causal chain instead of repeating "
                               f"what shot {vues[cle]} already said."))
        vues[cle] = s.id
    fonctions = [_normalise(s.educational_function) for s in sb.shots]
    if len(set(fonctions)) < len(fonctions):
        out.append(Problem("PROGRESSION", "storyboard",
                           "deux plans revendiquent la meme fonction pedagogique",
                           "Give each shot a distinct educational_function: one link of the "
                           "causal chain each, in order."))
    return out


def _normalise(texte: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", texte.lower()).strip()


# --- LA REGLE CENTRALE : grammaire visuelle et correspondance ---------------


def notions_pedagogiques(texte: str) -> set[str]:
    """Les NOTIONS du code couleur portees par le texte.

    On raisonne en notions et pas en teintes : l'energie electrique est
    jaune/orange, donc un flux annonce en jaune dans l'image et repris en
    orange dans l'animation reste le meme flux.

    « yellow energy streams » compte ; « yellow paint » ne compte pas : la
    couleur doit etre attachee a un phenomene, pas a un objet.
    """
    bas = texte.lower()
    trouvees = set()
    for couleur, notion in COLOR_NOTION.items():
        if notion in trouvees:
            continue
        for m in re.finditer(re.escape(couleur), bas):
            fenetre = bas[max(0, m.start() - 60):m.end() + 90]
            if any(p in fenetre for p in PHENOMENE):
                trouvees.add(notion)
                break
    return trouvees


def _mouvement_non_camera(texte: str) -> bool:
    """Vrai s'il reste un mouvement une fois les phrases de camera retirees."""
    phrases = re.split(r"[.;]", texte.lower())
    utiles = [p for p in phrases if not any(c in p for c in CAMERA)]
    return any(v in " ".join(utiles) for v in MOUVEMENT)


def _grammaire_visuelle(sb: Storyboard) -> list[Problem]:
    """Un phenomene invisible nomme par la voix doit etre rendu visible."""
    out = []
    for s in sb.shots:
        parle_invisible = any(mot in s.voice.lower() for mot in
                              ("énergie", "energie", "électricité", "electricite", "courant",
                               "champ", "signal", "puissance", "chaleur", "récupér", "recuper"))
        if parle_invisible and not notions_pedagogiques(s.image_prompt):
            out.append(Problem("GRAMMAIRE", s.slug,
                               "la voix nomme un phenomene invisible, "
                               "aucune representation coloree dans le prompt photo",
                               f"Shot {s.id}: the narration names something the eye cannot see. "
                               f"Create a visible representation of it and name its colour "
                               f"from the colour code — for example controlled yellow luminous "
                               f"streams for electrical energy."))
    return out


def _correspondance(sb: Storyboard) -> list[Problem]:
    """Ce que l'image introduit, l'animation doit le faire bouger."""
    out = []
    for s in sb.shots:
        image, anim = own_part(s.image_prompt), s.animation_prompt
        bas_anim = anim.lower()

        notions_image = notions_pedagogiques(image)
        perdues = notions_image - notions_pedagogiques(anim)
        if perdues:
            out.append(Problem("CORRESPONDANCE", s.slug,
                               f"l'image introduit une representation « {', '.join(sorted(perdues))} », "
                               f"l'animation ne la fait pas bouger",
                               f"Shot {s.id}: the image carries a {'/'.join(sorted(perdues))} "
                               f"representation of an invisible phenomenon. The animation must "
                               f"make that same element travel, pulse or circulate — not just "
                               f"move the camera."))

        # LE FLUX N'EST JAMAIS STATIQUE : il doit aller quelque part.
        if "energie" in notions_image and not any(d in bas_anim for d in DIRECTION):
            out.append(Problem("FLUX", s.slug,
                               "le flux d'energie n'a pas de direction lisible dans l'animation",
                               f"Shot {s.id}: the energy flow must never be static. State where "
                               f"it comes from and where it goes — for example from the battery "
                               f"toward the motor windings — so the viewer reads the direction "
                               f"of the transfer."))

        if not _mouvement_non_camera(anim):
            out.append(Problem("CORRESPONDANCE", s.slug,
                               "l'animation ne contient qu'un mouvement de camera",
                               f"Shot {s.id}: a camera move alone is rejected. Name the element "
                               f"that moves and how, and keep the camera secondary."))

        concept = s.visual_concept.lower()
        for composant, verbes in COMPOSANT_MOUVEMENT.items():
            if composant in concept and composant in image.lower():
                if composant not in bas_anim or not any(v in bas_anim for v in verbes):
                    out.append(Problem("CORRESPONDANCE", s.slug,
                                       f"l'image met en avant « {composant} », "
                                       f"l'animation ne le fait pas bouger",
                                       f"Shot {s.id}: the animation must name the {composant} "
                                       f"and describe its motion "
                                       f"({', '.join(verbes)})."))
    return out


def _explication(sb: Storyboard) -> list[Problem]:
    """Chaque phrase de narration traduite en information visuelle."""
    out = []
    for s in sb.shots:
        courts = [f for f in EXPLICATION_FIELDS
                  if len(s.visual_explanation.get(f, "").strip()) < 15]
        if courts:
            out.append(Problem("EXPLICATION", s.slug,
                               f"visual_explanation trop vague : {', '.join(courts)}",
                               f"Shot {s.id}: spell out the four steps — what the voice "
                               f"explains, the physical element that carries it, the visual "
                               f"behaviour that makes it readable, and the movement that shows "
                               f"it."))
            continue

        mouvement = s.visual_explanation["animation_movement"].lower()
        if not any(v in mouvement for v in MOUVEMENT):
            out.append(Problem("EXPLICATION", s.slug,
                               "animation_movement ne decrit aucun mouvement reel",
                               f"Shot {s.id}: animation_movement must name a real motion — a "
                               f"flow travelling, a part rotating, a light spreading — not a "
                               f"mood or a camera position."))
    return out


def _qualite(sb: Storyboard) -> list[Problem]:
    out = []
    for axe in QUALITY_AXES:
        note = sb.quality_check.get(axe)
        if note is None:
            continue
        if not 0.0 <= note <= 1.0:
            out.append(Problem("QUALITE", "storyboard", f"{axe} hors bornes : {note}",
                               f"quality_check.{axe} must be between 0 and 1."))
        elif note < MIN_QUALITY:
            out.append(Problem("QUALITE", "storyboard",
                               f"{axe} = {note} < {MIN_QUALITY}",
                               f"Rework the storyboard until {axe} honestly reaches "
                               f"{MIN_QUALITY}, then re-score."))
    return out


# ---------------------------------------------------------------------------


def correction_request(problems: list[Problem]) -> str:
    lignes = [
        "Your previous JSON was rejected by an automatic validator.",
        "Fix every point below and return the SAME JSON shape, corrected.",
        "Do not explain, do not apologise, return only the JSON.",
        "",
    ]
    lignes += [f"- {p.where}: {p.fix}" for p in problems]
    return "\n".join(lignes)
