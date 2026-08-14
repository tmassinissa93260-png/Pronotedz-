"""Garantit que la vidéo produite dure aussi longtemps que la voix qui la porte.

Mesuré sur un épisode réel : la piste audio durait 42,7 s mais la piste
vidéo s'arrêtait à 28,1 s — les 14 dernières secondes de narration
n'avaient plus aucune image, sans qu'aucune erreur ne le signale. Deux
vérifications, toutes les deux gratuites (ffprobe, zéro appel IA) :

  1. **avant le montage** — les plans découpés couvrent-ils vraiment la
     durée réelle de la voix ? Un job repris (`--reprendre`) peut relire
     des durées mises en cache pendant qu'un fichier voix plus récent, plus
     long, a été régénéré à côté : les deux ne se recoupent plus. Détecté
     ici, ça coûte une erreur claire. Détecté nulle part, ça coûte une
     vidéo tronquée après avoir déjà payé images et animation.
  2. **après le montage** — le fichier rendu dure-t-il vraiment ce qu'on
     attendait ? Dernier filet avant de livrer un épisode cassé, pour des
     causes que la vérification d'avant ne peut pas voir (un clip animé
     plus court que prévu, un souci ffmpeg). Compare la durée du flux VIDÉO
     et celle du flux AUDIO séparément (`message_si_video_finale_incoherente`)
     — jamais `format.duration`, qui a longtemps laissé passer exactement ce
     défaut : un fichier où la vidéo s'arrêtait avant l'audio faisait quand
     même remonter `format.duration` = la durée de l'audio, le flux le plus
     long, donc « cohérent » avec la durée attendue alors que la vidéo était
     réellement tronquée de 4,5 s. Voir `pdz/analyse/sonde.py`.
"""

from __future__ import annotations

TOLERANCE_S = 1.0


def ecart(attendu_s: float, mesure_s: float) -> float:
    return abs(mesure_s - attendu_s)


def message_si_incoherent(attendu_s: float, mesure_s: float, *,
                          contexte: str) -> str | None:
    """None si `mesure_s` colle à `attendu_s` (± TOLERANCE_S) ; sinon, un
    message prêt à journaliser ou à lever.

    Ne décide pas quoi en faire : un écart avant montage (rien n'est encore
    payé) n'a pas la même gravité qu'un écart après (tout est déjà payé) —
    c'est à l'appelant de choisir entre lever et journaliser fort.
    """
    e = ecart(attendu_s, mesure_s)
    if e <= TOLERANCE_S:
        return None
    return (
        f"{contexte} : {mesure_s:.1f} s mesurées pour {attendu_s:.1f} s "
        f"attendues (écart de {e:.1f} s)."
    )


def message_si_video_finale_incoherente(attendu_s: float, video_s: float,
                                        audio_s: float) -> str | None:
    """Le dernier filet, sur le fichier livré : compare séparément la durée
    du flux VIDÉO et celle du flux AUDIO — jamais `format.duration`, qui
    rapporte la durée du flux le plus long (voir pdz/analyse/sonde.py et la
    docstring du module). None si tout concorde.

    Deux façons distinctes d'être en écart, jamais confondues dans un seul
    nombre : la vidéo peut être plus courte que prévu (un clip animé
    insuffisant), ou l'audio peut dépasser la vidéo (même défaut, vu de
    l'autre bout). Les deux veulent dire la même chose pour le spectateur :
    du son sans image.
    """
    if video_s < attendu_s - TOLERANCE_S:
        return (
            f"Piste vidéo trop courte : {video_s:.1f} s pour {attendu_s:.1f} s "
            f"attendues (écart de {attendu_s - video_s:.1f} s)."
        )
    if audio_s > video_s + TOLERANCE_S:
        return (
            f"Voix plus longue que l'image : {audio_s:.1f} s de son pour "
            f"{video_s:.1f} s de vidéo (écart de {audio_s - video_s:.1f} s)."
        )
    return None
