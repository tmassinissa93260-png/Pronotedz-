"""Combien de plans ont RÉELLEMENT bougé dans la vidéo finale déjà montée.

Distinct de `pdz.production.verification_mouvement.verifier()` (qui juge un
clip isolé avant le montage) : ici, le mouvement est mesuré sur le fichier
qui part réellement au spectateur, après trim/crop/concat. Les bornes de
chaque plan sont déjà connues exactement (`plan.duree_s` cumulés) — pas
besoin de deviner les coupes comme dans une analyse a posteriori.

Répond à la vraie question de production : pas « combien de requêtes
d'animation ont réussi », mais « combien de plans montrent un mouvement
perceptible dans ce qui sort ». Zéro appel IA, diagnostic seulement.
"""

from __future__ import annotations

from pathlib import Path

from pdz.production import verification_mouvement
from pdz.production.storyboard import PlanScript


def verifier(video: Path, plans: list[PlanScript]) -> list[dict]:
    """Un verdict de mouvement par plan, sur la vidéo finale."""
    resultats: list[dict] = []
    curseur = 0.0
    for plan in plans:
        verdict = verification_mouvement.verifier_segment(
            video, debut_s=curseur, duree_s=plan.duree_s)
        resultats.append({
            "numero": plan.numero,
            "mouvement_confirme": verdict.mouvement_detecte,
            "diff_moyenne": verdict.diff_moyenne,
        })
        curseur += plan.duree_s
    return resultats
