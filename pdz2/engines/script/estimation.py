"""Estimation de durée de parole — **estimation, et rien d'autre**.

Ce module produit un chiffre approché à partir d'un texte. Ce chiffre sert à
deux choses, et à deux choses seulement :

  * remplir `ScriptLine.estimated_duration_s`, que le contrat désigne
    explicitement comme une estimation ;
  * signaler à l'auteur, **avant** de payer une synthèse, que son script
    semble trop long ou trop court pour la durée visée.

Il ne sert **jamais** à construire une timeline. La durée officielle vient
exclusivement de la mesure de l'audio réellement synthétisé — voir
`pdz2.audio.timeline`, qui n'importe rien d'ici et ne le peut pas : un test
d'architecture échoue si la chaîne audio touche à `estimated_duration_s`.

Le modèle est volontairement grossier — syllabes approchées et débit moyen.
Le raffiner serait du temps perdu : plus il paraîtrait juste, plus la
tentation serait grande de s'en servir comme d'une autorité.
"""

from __future__ import annotations

import re

__all__ = [
    "DEFAULT_SPEECH_RATE_WPM",
    "estimate_duration_s",
    "syllable_count",
]

DEFAULT_SPEECH_RATE_WPM = 165.0
"""Débit de référence, en mots par minute, pour une narration documentaire."""

_SYLLABLE_RATIO = 2.9
"""Syllabes par mot, moyenne du français courant. Approximation assumée."""

_VOWEL_GROUP = re.compile(r"[aeiouyàâäéèêëîïôöùûüœ]+", re.IGNORECASE)
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
_PAUSE_MARKS = re.compile(r"[,;:]")
_STOP_MARKS = re.compile(r"[.!?…]")

_PAUSE_S = 0.18
_STOP_S = 0.35


def syllable_count(text: str) -> int:
    """Nombre approché de syllabes : groupes de voyelles, au moins un par mot."""
    total = 0
    for word in _WORD.findall(text):
        groups = len(_VOWEL_GROUP.findall(word))
        total += max(1, groups)
    return total


def estimate_duration_s(text: str, rate_wpm: float = DEFAULT_SPEECH_RATE_WPM) -> float:
    """Durée approchée de lecture. **Ne jamais utiliser comme durée officielle.**"""
    if rate_wpm <= 0:
        raise ValueError("débit de parole nul ou négatif")
    syllables = syllable_count(text)
    if syllables == 0:
        return 0.0
    syllables_per_second = rate_wpm * _SYLLABLE_RATIO / 60.0
    spoken = syllables / syllables_per_second
    breathing = (
        len(_PAUSE_MARKS.findall(text)) * _PAUSE_S
        + len(_STOP_MARKS.findall(text)) * _STOP_S
    )
    return round(spoken + breathing, 3)
