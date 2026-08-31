"""Le contrat : storyboard, visual bible, analyse video, timeline.

Tout ce qu'OpenAI doit rendre est decrit ici, et nulle part ailleurs.
`validator.py` verifie que le contrat est tenu.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# MOTION INTENT - vocabulaire ferme. « zoom » n'y figure pas, volontairement.
# ---------------------------------------------------------------------------

MOTION_INTENTS = (
    "energy_flow",
    "energy_storage",
    "energy_transfer",
    "mechanical_rotation",
    "electromagnetic_rotation",
    "cause_effect",
    "reveal",
    "tracking",
    "macro_travel",
    "acceleration",
    "deceleration",
    "regenerative_braking",
    "energy_return",
)

# ---------------------------------------------------------------------------
# CODE COULEUR
#
# Une NOTION peut porter plusieurs couleurs — l'energie electrique est
# jaune/orange — mais une couleur ne porte jamais deux notions. Les controles
# raisonnent donc sur la notion, pas sur la teinte : un flux annonce en jaune
# dans l'image et repris en orange dans l'animation reste le meme flux.
# ---------------------------------------------------------------------------

COLOR_NOTION = {
    "yellow": "energie",
    "orange": "energie",
    "blue": "batterie",
    "green": "recuperation",
    "grey": "mecanique",
    "gray": "mecanique",
}

# Deux notions representent un PHENOMENE INVISIBLE, qui se deplace : c'est a
# elles seules que s'applique « ce que l'image introduit, l'animation doit le
# faire bouger ». Les deux autres sont des couleurs d'IDENTITE — la batterie
# est bleue, la mecanique est grise — et exiger qu'un gris se deplace n'a
# aucun sens.
NOTIONS_EN_MOUVEMENT = ("energie", "recuperation")

NOTION_SENS = {
    "energie": "électricité, courant, flux d'énergie — jaune/orange lumineux",
    "batterie": "batterie, système électrique, technologie — bleu",
    "recuperation": "énergie récupérée, efficacité, recharge — vert",
    "mecanique": "mécanique, structure, composants — gris",
}

# ---------------------------------------------------------------------------
# CODE COULEUR PROPRE AU SUJET
#
# La table ci-dessus est celle d'une voiture electrique. Sur un avion, « vert
# = recuperation » ne veut rien dire. Le modele produit donc SON code couleur
# en meme temps que la visual bible, et les controles lisent celui-la. La
# table figee reste le defaut : un ancien project.json continue de s'ouvrir.
# ---------------------------------------------------------------------------

COLOR_CODE_FIELDS = ("notion", "color", "meaning")

# Les prompts sont en anglais, le script en francais : au run 34 le modele a
# declare « jaune » et « rouge » pendant qu'il ecrivait « yellow pulse » et
# « red stream ». Le code couleur devenait aveugle. On accepte donc les deux
# langues et on cherche les deux formes dans le texte.
TRADUCTION_COULEUR = {
    "jaune": "yellow", "orange": "orange", "rouge": "red", "bleu": "blue",
    "vert": "green", "gris": "grey", "blanc": "white", "noir": "black",
    "violet": "purple", "rose": "pink", "cyan": "cyan", "ambre": "amber",
    "turquoise": "turquoise", "magenta": "magenta", "dore": "gold",
    "doré": "gold", "argente": "silver", "argenté": "silver",
}

#: L'equivalence marche dans les deux sens : le code peut etre declare en
#: anglais et la voix parler francais, ou l'inverse.
EQUIVALENCE_COULEUR: dict[str, tuple[str, ...]] = {}
for _fr, _en in TRADUCTION_COULEUR.items():
    EQUIVALENCE_COULEUR.setdefault(_fr, ()) 
    EQUIVALENCE_COULEUR[_fr] += (_en,)
    EQUIVALENCE_COULEUR.setdefault(_en, ())
    EQUIVALENCE_COULEUR[_en] += (_fr,)

MIN_COLOR_NOTIONS = 3
MAX_COLOR_NOTIONS = 6


@dataclass
class ColorEntry:
    notion: str
    color: str
    meaning: str
    moving: bool

    @property
    def couleurs(self) -> tuple[str, ...]:
        """« yellow/orange » -> ('yellow', 'orange') ; « jaune » -> les deux."""
        mots = [c for c in re.split(r"[^a-zà-ÿ]+", self.color.lower()) if c]
        toutes = list(mots)
        for mot in mots:
            for equivalent in EQUIVALENCE_COULEUR.get(mot, ()):
                if equivalent not in toutes:
                    toutes.append(equivalent)
        return tuple(toutes)

    @classmethod
    def from_dict(cls, index: int, raw: object) -> ColorEntry:
        label = f"color_code #{index + 1}"
        if not isinstance(raw, dict):
            raise StoryboardError(f"{label} : doit etre un objet JSON")
        vides = [f for f in COLOR_CODE_FIELDS if not str(raw.get(f) or "").strip()]
        if vides:
            raise StoryboardError(f"{label} : champ(s) vide(s) : {', '.join(vides)}")
        entree = cls(notion=str(raw["notion"]).strip().lower(),
                     color=str(raw["color"]).strip().lower(),
                     meaning=str(raw["meaning"]).strip(),
                     moving=bool(raw.get("moving", False)))
        if not entree.couleurs:
            raise StoryboardError(f"{label} : 'color' ne nomme aucune couleur")
        return entree


DEFAULT_COLOR_CODE = tuple(
    ColorEntry(notion=notion,
               color="/".join(c for c, n in COLOR_NOTION.items()
                              if n == notion and c != "gray"),
               meaning=sens,
               moving=notion in NOTIONS_EN_MOUVEMENT)
    for notion, sens in NOTION_SENS.items()
)

VISUAL_BIBLE_FIELDS = (
    "main_subject",
    "characters_objects",
    "vehicle",
    "colors",
    "environment",
    "materials",
    "lighting",
    "camera",
    "style_3d",
    "realism",
    "invisible_phenomena",
)

SHOT_TEXT_FIELDS = (
    "voice",
    "visual_description",
    "educational_function",
    "visual_concept",
    "image_prompt",
    "animation_prompt",
)

# REGLE « VISUAL EXPLANATION » : chaque phrase de narration est traduite en
# information visuelle. Ces sept temps sont le RAISONNEMENT qui precede le
# prompt, pas son resume : on ne part jamais d'une belle image, on part de
# l'information a faire comprendre et on remonte jusqu'au cadre.
EXPLICATION_FIELDS = (
    "information",          # 1. ce que la voix explique
    "physical_element",     # 2. l'objet physique principal qui la porte
    "secondary_elements",   # 3. les objets secondaires qui la rendent lisible
    "visual_behavior",      # 4. le phenomene visible qui la represente
    "animation_movement",   # 5. le mouvement qui l'anime
    "camera_position",      # 6. la camera qui laisse voir tout cela
    "composition",          # 7. le cadre que ce mouvement exige
)

# Les sept axes du controle qualite.
QUALITY_AXES = (
    "narrative_quality",
    "visual_quality",
    "scientific_accuracy",
    "voice_visual_alignment",
    "visual_continuity",
    "pedagogical_clarity",
    "animation_potential",
)


class StoryboardError(ValueError):
    """Le JSON recu n'a pas la forme du contrat."""


@dataclass
class VisualBible:
    main_subject: str
    characters_objects: str
    vehicle: str
    colors: str
    environment: str
    materials: str
    lighting: str
    camera: str
    style_3d: str
    realism: str
    invisible_phenomena: str

    def as_block(self) -> str:
        return "\n".join(f"{champ.replace('_', ' ').capitalize()}: {getattr(self, champ)}"
                         for champ in VISUAL_BIBLE_FIELDS)

    @classmethod
    def from_dict(cls, raw: object) -> VisualBible:
        if not isinstance(raw, dict):
            raise StoryboardError("'visual_bible' manquante ou invalide")
        manquants = [f for f in VISUAL_BIBLE_FIELDS if not str(raw.get(f) or "").strip()]
        if manquants:
            raise StoryboardError(f"visual_bible : champ(s) vide(s) : {', '.join(manquants)}")
        return cls(**{f: str(raw[f]).strip() for f in VISUAL_BIBLE_FIELDS})


@dataclass
class Shot:
    id: int
    duration_seconds: float
    voice: str
    visual_description: str
    educational_function: str
    visual_concept: str
    image_prompt: str
    animation_prompt: str
    motion_intent: str
    visual_explanation: dict

    @property
    def slug(self) -> str:
        return f"shot_{self.id:02d}"

    @property
    def word_count(self) -> int:
        return len([m for m in self.voice.split() if m.strip()])

    @property
    def words_per_second(self) -> float:
        return self.word_count / self.duration_seconds if self.duration_seconds else 0.0

    @classmethod
    def from_dict(cls, index: int, raw: object) -> Shot:
        label = f"plan #{index + 1}"
        if not isinstance(raw, dict):
            raise StoryboardError(f"{label} : doit etre un objet JSON")

        manquants = [f for f in SHOT_TEXT_FIELDS if not str(raw.get(f) or "").strip()]
        if manquants:
            raise StoryboardError(f"{label} : champ(s) vide(s) : {', '.join(manquants)}")

        intent = str(raw.get("motion_intent") or "").strip()
        if intent not in MOTION_INTENTS:
            raise StoryboardError(
                f"{label} : motion_intent '{intent}' hors vocabulaire.\n"
                f"  Valeurs admises : {', '.join(MOTION_INTENTS)}")

        explication = raw.get("visual_explanation")
        if not isinstance(explication, dict):
            raise StoryboardError(f"{label} : 'visual_explanation' manquante")
        vides = [f for f in EXPLICATION_FIELDS if not str(explication.get(f) or "").strip()]
        if vides:
            raise StoryboardError(
                f"{label} : visual_explanation, champ(s) vide(s) : {', '.join(vides)}")

        return cls(
            id=_entier(raw.get("id"), f"{label} 'id'"),
            duration_seconds=_nombre(raw.get("duration_seconds"),
                                     f"{label} 'duration_seconds'"),
            voice=str(raw["voice"]).strip(),
            visual_description=str(raw["visual_description"]).strip(),
            educational_function=str(raw["educational_function"]).strip(),
            visual_concept=str(raw["visual_concept"]).strip(),
            image_prompt=str(raw["image_prompt"]).strip(),
            animation_prompt=str(raw["animation_prompt"]).strip(),
            motion_intent=intent,
            visual_explanation={f: str(explication[f]).strip() for f in EXPLICATION_FIELDS},
        )


@dataclass
class Storyboard:
    subject: str
    duration_seconds: float
    shot_count: int
    script: str
    visual_bible: VisualBible
    shots: list[Shot] = field(default_factory=list)
    quality_check: dict = field(default_factory=dict)
    color_code: list[ColorEntry] = field(default_factory=list)

    @property
    def total_duration(self) -> float:
        return round(sum(s.duration_seconds for s in self.shots), 3)

    def code_couleur(self) -> tuple[ColorEntry, ...]:
        """Le code du sujet, ou celui de la voiture si le fichier est ancien."""
        return tuple(self.color_code) or DEFAULT_COLOR_CODE

    def notion_par_couleur(self) -> dict[str, str]:
        table: dict[str, str] = {}
        for entree in self.code_couleur():
            for couleur in entree.couleurs:
                table.setdefault(couleur, entree.notion)
        return table

    def notions_mobiles(self) -> tuple[str, ...]:
        """Les notions qui representent un phenomene qui SE DEPLACE.

        Une couleur d'identite — la batterie est bleue — n'a pas a bouger ;
        exiger qu'un gris se deplace n'aurait aucun sens.
        """
        return tuple(e.notion for e in self.code_couleur() if e.moving)

    def shot(self, shot_id: int) -> Shot:
        for s in self.shots:
            if s.id == shot_id:
                return s
        raise KeyError(f"plan {shot_id} absent du storyboard")

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> Storyboard:
        try:
            return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except FileNotFoundError:
            raise StoryboardError(f"project.json introuvable : {path}") from None
        except json.JSONDecodeError as exc:
            raise StoryboardError(f"project.json illisible : {exc}") from exc

    @classmethod
    def from_dict(cls, raw: object) -> Storyboard:
        if not isinstance(raw, dict):
            raise StoryboardError("la reponse doit etre un objet JSON")
        for champ in ("subject", "script"):
            if not str(raw.get(champ) or "").strip():
                raise StoryboardError(f"champ '{champ}' vide ou manquant")

        shots_raw = raw.get("shots")
        if not isinstance(shots_raw, list) or not shots_raw:
            raise StoryboardError("champ 'shots' vide ou manquant")

        qualite = raw.get("quality_check")
        if not isinstance(qualite, dict):
            raise StoryboardError("'quality_check' manquant")
        manquants = [a for a in QUALITY_AXES if a not in qualite]
        if manquants:
            raise StoryboardError(f"quality_check : axe(s) manquant(s) : {', '.join(manquants)}")

        return cls(
            subject=str(raw["subject"]).strip(),
            duration_seconds=_nombre(raw.get("duration_seconds"), "'duration_seconds'"),
            shot_count=_entier(raw.get("shot_count"), "'shot_count'"),
            script=str(raw["script"]).strip(),
            visual_bible=VisualBible.from_dict(raw.get("visual_bible")),
            shots=[Shot.from_dict(i, s) for i, s in enumerate(shots_raw)],
            quality_check={a: _nombre(qualite.get(a), f"quality_check.{a}") for a in QUALITY_AXES},
            color_code=_code_couleur(raw.get("color_code")),
        )


# ---------------------------------------------------------------------------
# Analyse des videos renvoyees par l'utilisateur
# ---------------------------------------------------------------------------

VIDEO_TEXT_FIELDS = ("content", "framing", "movement", "quality", "voice_match")
VIDEO_LIST_FIELDS = ("pedagogical_elements", "defects")


@dataclass
class VideoAnalysis:
    shot_id: int
    measured_duration: float
    content: str
    framing: str
    movement: str
    quality: str
    voice_match: str
    pedagogical_elements: list[str]
    defects: list[str]
    matches_plan: bool

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, shot_id: int, measured: float, raw: object) -> VideoAnalysis:
        if not isinstance(raw, dict):
            raise StoryboardError("l'analyse video doit etre un objet JSON")
        manquants = [f for f in VIDEO_TEXT_FIELDS if not str(raw.get(f) or "").strip()]
        if manquants:
            raise StoryboardError(f"analyse video : champ(s) vide(s) : {', '.join(manquants)}")
        return cls(
            shot_id=shot_id,
            measured_duration=measured,
            content=str(raw["content"]).strip(),
            framing=str(raw["framing"]).strip(),
            movement=str(raw["movement"]).strip(),
            quality=str(raw["quality"]).strip(),
            voice_match=str(raw["voice_match"]).strip(),
            pedagogical_elements=_liste(raw.get("pedagogical_elements")),
            defects=_liste(raw.get("defects")),
            matches_plan=bool(raw.get("matches_plan", False)),
        )


# ---------------------------------------------------------------------------


def _code_couleur(raw: object) -> list[ColorEntry]:
    """Absent = ancien fichier : on retombera sur DEFAULT_COLOR_CODE.

    Present mais incoherent = erreur de contrat, corrigee par la boucle.
    """
    if raw is None:
        return []
    if not isinstance(raw, list) or not raw:
        raise StoryboardError("'color_code' doit etre une liste non vide")
    entrees = [ColorEntry.from_dict(i, e) for i, e in enumerate(raw)]

    vues: dict[str, str] = {}
    for entree in entrees:
        for couleur in entree.couleurs:
            if vues.get(couleur, entree.notion) != entree.notion:
                raise StoryboardError(
                    f"color_code : « {couleur} » porte deux notions "
                    f"(« {vues[couleur]} » et « {entree.notion} »)")
            vues[couleur] = entree.notion

    notions = [e.notion for e in entrees]
    if len(set(notions)) != len(notions):
        raise StoryboardError("color_code : deux entrees portent la meme notion")
    return entrees


def _nombre(valeur: object, label: str) -> float:
    try:
        return float(valeur)
    except (TypeError, ValueError):
        raise StoryboardError(f"{label} absent ou non numerique") from None


def _entier(valeur: object, label: str) -> int:
    try:
        return int(valeur)
    except (TypeError, ValueError):
        raise StoryboardError(f"{label} absent ou non numerique") from None


def _liste(valeur: object) -> list[str]:
    if isinstance(valeur, str):
        valeur = [valeur]
    if not isinstance(valeur, list):
        return []
    return [str(v).strip() for v in valeur if str(v).strip()]
