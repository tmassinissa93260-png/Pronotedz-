"""Vocabulaire partagé des contrats.

Aucun de ces énumérés ne nomme un fournisseur : le cœur du système reste
provider-agnostic. Les noms de fournisseurs n'apparaissent que dans les
adaptateurs et la matrice de capacités (phases ultérieures).
"""

from __future__ import annotations

from enum import Enum

__all__ = [
    "AspectRatio",
    "Platform",
    "Tone",
    "Pacing",
    "NarrativeFunction",
    "Emotion",
    "TransitionKind",
    "Framing",
    "CameraAngle",
    "ScreenPosition",
    "AudioEventKind",
    "ArtifactKind",
    "Severity",
]


class AspectRatio(str, Enum):
    VERTICAL = "9:16"
    HORIZONTAL = "16:9"
    SQUARE = "1:1"
    CLASSIC = "4:5"


class Platform(str, Enum):
    TIKTOK = "tiktok"
    SHORTS = "shorts"
    REELS = "reels"
    YOUTUBE = "youtube"
    GENERIC = "generic"


class Tone(str, Enum):
    DOCUMENTARY = "documentary"
    EXPLANATORY = "explanatory"
    CINEMATIC = "cinematic"
    URGENT = "urgent"
    CONTEMPLATIVE = "contemplative"
    PLAYFUL = "playful"


class Pacing(str, Enum):
    SLOW = "slow"
    MEASURED = "measured"
    BRISK = "brisk"
    RAPID = "rapid"


class NarrativeFunction(str, Enum):
    """Rôle d'une réplique ou d'un plan dans la démonstration."""

    HOOK = "hook"
    SETUP = "setup"
    QUESTION = "question"
    MECHANISM = "mechanism"
    EVIDENCE = "evidence"
    CONTRAST = "contrast"
    CONSEQUENCE = "consequence"
    PAYOFF = "payoff"
    TRANSITION = "transition"
    CTA = "cta"


class Emotion(str, Enum):
    NEUTRAL = "neutral"
    CURIOUS = "curious"
    WONDER = "wonder"
    SERIOUS = "serious"
    URGENT = "urgent"
    TENSE = "tense"
    WARM = "warm"
    PLAYFUL = "playful"


class TransitionKind(str, Enum):
    CUT = "cut"
    DISSOLVE = "dissolve"
    FADE_IN = "fade_in"
    FADE_OUT = "fade_out"
    MATCH_CUT = "match_cut"
    WHIP = "whip"
    WIPE = "wipe"


class Framing(str, Enum):
    EXTREME_WIDE = "extreme_wide"
    WIDE = "wide"
    MEDIUM_WIDE = "medium_wide"
    MEDIUM = "medium"
    MEDIUM_CLOSE = "medium_close"
    CLOSE = "close"
    EXTREME_CLOSE = "extreme_close"
    MACRO = "macro"
    CUTAWAY_DIAGRAM = "cutaway_diagram"


class CameraAngle(str, Enum):
    EYE = "eye"
    LOW = "low"
    HIGH = "high"
    TOP_DOWN = "top_down"
    DUTCH = "dutch"
    ISOMETRIC = "isometric"
    CROSS_SECTION = "cross_section"


class ScreenPosition(str, Enum):
    TOP = "top"
    UPPER_THIRD = "upper_third"
    CENTER = "center"
    LOWER_THIRD = "lower_third"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"


class AudioEventKind(str, Enum):
    SFX = "sfx"
    IMPACT = "impact"
    WHOOSH = "whoosh"
    AMBIENCE = "ambience"
    MUSIC_CUE = "music_cue"
    SILENCE = "silence"


class ArtifactKind(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    TEXT = "text"


class Severity(str, Enum):
    INFO = "info"
    MINOR = "minor"
    MAJOR = "major"
    BLOCKING = "blocking"
