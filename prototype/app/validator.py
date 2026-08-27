"""Les 10 verifications imposees avant de sauvegarder un storyboard.

Le validateur ne se contente pas de dire non : chaque probleme porte une
phrase adressee a OpenAI, qui sert a lui demander une correction ciblee.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Storyboard
from .prompts import STYLE_FINGERPRINT

# Debit de parole en francais. En dessous, la phrase est trop courte pour la
# duree annoncee ; au dessus, elle est impossible a prononcer dans le temps.
MIN_WORDS_PER_SECOND = 1.8
MAX_WORDS_PER_SECOND = 4.0

MIN_ALIGNMENT_SCORE = 0.8
MIN_IMAGE_PROMPT_CHARS = 220
DURATION_TOLERANCE_S = 0.5

# CONDITION 5 : un prompt photo doit dire ou est quoi, comment c'est cadre,
# et sous quelle lumiere. Chaque famille doit apparaitre au moins une fois.
SPECIFICITY_FAMILIES = {
    "cadrage": ("shot", "framing", "close-up", "closeup", "wide", "medium", "macro", "view"),
    "camera": ("camera", "angle", "lens", "perspective", "eye level", "low angle", "high angle"),
    "position": ("left", "right", "centre", "center", "beneath", "under", "above", "behind",
                 "front", "rear", "between", "along", "inside", "mounted", "positioned"),
    "lumiere": ("light", "lighting", "lit", "illuminat", "volumetric", "backlight", "rim"),
    "materiaux": ("material", "metal", "aluminium", "aluminum", "copper", "composite",
                  "matte", "paint", "plastic", "steel", "glass"),
}

# CONDITION 6 : ce qui est dit doit etre montre. Mots francais de la voix
# rapproches de leur equivalent anglais attendu dans le prompt photo.
SEMANTIC_PAIRS = {
    "batterie": ("battery", "cell", "pack", "module"),
    "cellule": ("cell",),
    "moteur": ("motor", "rotor", "stator", "winding"),
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
    "freinage": ("brake", "regenerat"),
}


@dataclass
class Problem:
    """Un manquement, avec sa consigne de correction pour OpenAI."""

    code: str
    where: str
    message: str
    fix: str

    def __str__(self) -> str:
        return f"[{self.code}] {self.where} : {self.message}"


def validate(storyboard: Storyboard, duration: float, shot_count: int) -> list[Problem]:
    """Les 10 verifications. Liste vide = storyboard acceptable."""
    problems: list[Problem] = []
    problems += _check_shot_count(storyboard, shot_count)
    problems += _check_total_duration(storyboard, duration)
    problems += _check_required_fields(storyboard)
    problems += _check_style_directive(storyboard)
    problems += _check_speech_rate(storyboard)
    problems += _check_prompt_specificity(storyboard)
    problems += _check_visual_continuity(storyboard)
    problems += _check_semantic_alignment(storyboard)
    problems += _check_narration_progression(storyboard)
    return problems


# --- 1. nombre de plans ------------------------------------------------------


def _check_shot_count(sb: Storyboard, expected: int) -> list[Problem]:
    if len(sb.shots) == expected:
        return []
    return [Problem("PLANS", "storyboard",
                    f"{len(sb.shots)} plan(s) au lieu de {expected}",
                    f"Return exactly {expected} shots, with ids 1 to {expected}.")]


# --- 2. duree totale ---------------------------------------------------------


def _check_total_duration(sb: Storyboard, expected: float) -> list[Problem]:
    problems = []
    if abs(sb.total_duration - expected) > DURATION_TOLERANCE_S:
        problems.append(Problem(
            "DUREE", "storyboard",
            f"somme des plans = {sb.total_duration}s au lieu de {expected}s",
            f"The sum of every duration_seconds must equal exactly {expected}."))
    for shot in sb.shots:
        if shot.duration_seconds <= 0:
            problems.append(Problem(
                "DUREE", shot.slug, f"duree invalide : {shot.duration_seconds}",
                f"Shot {shot.id} needs a positive duration_seconds."))
    return problems


# --- 3/4/5. champs obligatoires ---------------------------------------------


def _check_required_fields(sb: Storyboard) -> list[Problem]:
    problems = []
    ids = [s.id for s in sb.shots]
    if ids != list(range(1, len(sb.shots) + 1)):
        problems.append(Problem(
            "IDS", "storyboard", f"ids non contigus : {ids}",
            f"Number the shots 1 to {len(sb.shots)} in order."))
    for shot in sb.shots:
        if len(shot.educational_function) < 20:
            problems.append(Problem(
                "FONCTION", shot.slug,
                "educational_function trop vague pour justifier le plan",
                f"Shot {shot.id}: state in one full sentence what understanding this "
                f"shot adds that no other shot provides."))
    return problems


# --- 6. direction artistique -------------------------------------------------


def _check_style_directive(sb: Storyboard) -> list[Problem]:
    return [
        Problem("STYLE", shot.slug, "direction artistique absente du prompt photo",
                f"Shot {shot.id}: end image_prompt with the mandatory art direction "
                f"sentence, copied verbatim.")
        for shot in sb.shots
        if STYLE_FINGERPRINT.lower() not in shot.image_prompt.lower()
    ]


# --- 2 bis. narration compatible avec la duree ------------------------------


def _check_speech_rate(sb: Storyboard) -> list[Problem]:
    problems = []
    for shot in sb.shots:
        rate = shot.words_per_second
        if rate < MIN_WORDS_PER_SECOND:
            problems.append(Problem(
                "DEBIT", shot.slug,
                f"{shot.word_count} mots pour {shot.duration_seconds}s "
                f"({rate:.1f} mot/s) : phrase trop courte, le plan serait vide",
                f"Shot {shot.id}: write about "
                f"{int(shot.duration_seconds * 2.7)} words of narration, not "
                f"{shot.word_count}. Say more about the causal link, do not pad."))
        elif rate > MAX_WORDS_PER_SECOND:
            problems.append(Problem(
                "DEBIT", shot.slug,
                f"{shot.word_count} mots pour {shot.duration_seconds}s "
                f"({rate:.1f} mot/s) : impossible a prononcer",
                f"Shot {shot.id}: shorten the narration to about "
                f"{int(shot.duration_seconds * 2.7)} words."))
    return problems


# --- 5. specificite du prompt photo -----------------------------------------


def _check_prompt_specificity(sb: Storyboard) -> list[Problem]:
    problems = []
    for shot in sb.shots:
        # La direction artistique est commune a tous : elle ne compte pas
        # comme de la specificite propre au plan.
        propre = _own_part(shot.image_prompt)
        bas = propre.lower()

        if len(propre.strip()) < MIN_IMAGE_PROMPT_CHARS:
            problems.append(Problem(
                "PRECISION", shot.slug,
                f"prompt photo trop general ({len(propre.strip())} caracteres "
                f"hors direction artistique)",
                f"Shot {shot.id}: describe the subject, the visible components and "
                f"where each one sits, the framing, the camera angle, the depth, the "
                f"lighting, the materials, and what must be unmistakably visible."))

        absentes = [nom for nom, mots in SPECIFICITY_FAMILIES.items()
                    if not any(m in bas for m in mots)]
        if absentes:
            problems.append(Problem(
                "PRECISION", shot.slug,
                f"le prompt photo ne dit rien sur : {', '.join(absentes)}",
                f"Shot {shot.id}: the image_prompt must explicitly state "
                f"{', '.join(absentes)}."))
    return problems


# --- 7. continuite visuelle --------------------------------------------------


def _check_visual_continuity(sb: Storyboard) -> list[Problem]:
    """La bible doit se retrouver dans chaque prompt, pas seulement en tete."""
    ancres = _continuity_anchors(sb)
    if not ancres:
        return []
    problems = []
    for shot in sb.shots:
        # La direction artistique contient « dark studio » : elle satisferait
        # le controle a elle seule, dans tous les plans. On ne regarde donc
        # que la part propre au plan.
        bas = _own_part(shot.image_prompt).lower()
        if not any(a in bas for a in ancres):
            problems.append(Problem(
                "CONTINUITE", shot.slug,
                "le prompt photo ne reprend rien de la visual_bible",
                f"Shot {shot.id}: restate the car, the environment and the materials "
                f"described in visual_bible, so every shot shows the same vehicle."))
    return problems


def _own_part(image_prompt: str) -> str:
    """Le prompt photo prive de la direction artistique commune.

    On COUPE a la signature, on ne la supprime pas : la supprimer d'abord
    rendrait la coupe introuvable et laisserait toute la fin de la phrase de
    style (« clean dark studio environment », « cinematic lighting »...)
    passer pour du contenu propre au plan.
    """
    debut = image_prompt.lower().find(STYLE_FINGERPRINT.lower())
    return image_prompt if debut < 0 else image_prompt[:debut]


def _continuity_anchors(sb: Storyboard) -> list[str]:
    """Mots porteurs de la bible : couleur, carrosserie, decor."""
    source = f"{sb.visual_bible.vehicle} {sb.visual_bible.environment}".lower()
    candidats = ("white", "blanc", "sedan", "berline", "hatchback", "compact", "suv",
                 "studio", "dark", "sombre", "grey", "gray", "blue")
    return [c for c in candidats if c in source]


# --- 8. ce qui est dit est montre -------------------------------------------


def _check_semantic_alignment(sb: Storyboard) -> list[Problem]:
    problems = []
    for shot in sb.shots:
        if shot.semantic_alignment_score < MIN_ALIGNMENT_SCORE:
            problems.append(Problem(
                "ALIGNEMENT", shot.slug,
                f"score annonce {shot.semantic_alignment_score} < {MIN_ALIGNMENT_SCORE}",
                f"Shot {shot.id}: rework it until what the voice says is unmistakably "
                f"the thing shown, then re-score honestly."))
        if not 0.0 <= shot.semantic_alignment_score <= 1.0:
            problems.append(Problem(
                "ALIGNEMENT", shot.slug,
                f"score hors bornes : {shot.semantic_alignment_score}",
                f"Shot {shot.id}: semantic_alignment_score must be between 0 and 1."))

        manquants = _unshown_components(shot.voice, shot.image_prompt)
        if manquants:
            problems.append(Problem(
                "ALIGNEMENT", shot.slug,
                f"la voix parle de {', '.join(manquants)} — invisible dans le prompt photo",
                f"Shot {shot.id}: the voice mentions {', '.join(manquants)}, so the "
                f"image_prompt must show it clearly and name it."))
    return problems


def _unshown_components(voice: str, image_prompt: str) -> list[str]:
    voix, image = voice.lower(), image_prompt.lower()
    manquants = []
    for francais, anglais in SEMANTIC_PAIRS.items():
        if francais in voix and not any(a in image for a in anglais):
            manquants.append(francais)
    return manquants


# --- 9. narration non contradictoire, et qui progresse ----------------------


def _check_narration_progression(sb: Storyboard) -> list[Problem]:
    problems = []
    vues = {}
    for shot in sb.shots:
        cle = _normalise(shot.voice)
        if cle in vues:
            problems.append(Problem(
                "PROGRESSION", shot.slug,
                f"narration identique au plan {vues[cle]}",
                f"Shot {shot.id}: each shot must advance the causal chain, not repeat "
                f"what shot {vues[cle]} already said."))
        vues[cle] = shot.id

    fonctions = [_normalise(s.educational_function) for s in sb.shots]
    if len(set(fonctions)) < len(fonctions):
        problems.append(Problem(
            "PROGRESSION", "storyboard",
            "deux plans revendiquent la meme fonction pedagogique",
            "Give each shot a distinct educational_function: one link of the causal "
            "chain each, in order."))
    return problems


def _normalise(texte: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", texte.lower()).strip()


# ---------------------------------------------------------------------------


def correction_request(problems: list[Problem]) -> str:
    """Le message de correction envoye a OpenAI, probleme par probleme."""
    lignes = [
        "Your previous JSON was rejected by an automatic validator.",
        "Fix every point below and return the SAME JSON shape, corrected.",
        "Do not explain, do not apologise, return only the JSON.",
        "",
    ]
    lignes += [f"- {p.where}: {p.fix}" for p in problems]
    return "\n".join(lignes)
