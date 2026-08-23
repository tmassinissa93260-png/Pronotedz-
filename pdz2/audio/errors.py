"""Défaillances audio, nommées une par une.

Le cahier des charges exige que l'échec de synthèse, l'audio corrompu, la
durée incohérente et la timeline invalide soient **refusés explicitement et
journalisés**. Chacun a donc son exception : le motif écrit dans la machine à
états est le message de l'exception, pas une catégorie floue.
"""

from __future__ import annotations

__all__ = [
    "AudioError",
    "SynthesisFailed",
    "SynthesiserUnavailable",
    "AudioCorrupt",
    "AudioSilent",
    "AudioFormatMismatch",
    "DurationInconsistent",
]


class AudioError(RuntimeError):
    """Racine des défaillances de la chaîne audio."""


class SynthesiserUnavailable(AudioError):
    """Le moteur de synthèse n'est pas joignable sur cette machine."""


class SynthesisFailed(AudioError):
    """Le moteur a été appelé et n'a pas rendu d'audio exploitable."""


class AudioCorrupt(AudioError):
    """Le fichier n'est pas un WAV lisible, ou ne contient aucune trame."""


class AudioSilent(AudioError):
    """Le fichier est lisible mais muet : la synthèse n'a rien dit."""


class AudioFormatMismatch(AudioError):
    """Deux fragments audio n'ont pas le même format et ne peuvent être assemblés."""


class DurationInconsistent(AudioError):
    """La durée mesurée ne concorde pas avec ce que l'assemblage annonce."""
