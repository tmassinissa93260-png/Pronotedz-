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
     plus court que prévu, un souci ffmpeg).
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
