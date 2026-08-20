"""Ce qu'on a MESURÉ sur un rendu — jamais ce qu'on en pense.

Le dépôt possède déjà de vraies sondes, et de bonnes :

  · `verification_mouvement` — différence inter-frames en niveaux de gris,
    seuil calibré sur des mesures réelles (0,509 statique vs 1,723 en
    mouvement → seuil 1,0) ;
  · `qa_video_finale`        — mouvement par plan sur le master MONTÉ ;
  · `coherence_duree`        — la vidéo dure-t-elle aussi longtemps que la voix ;
  · `cadrage`                — variété d'un plan à l'autre ;
  · `qa_image`               — PASS / FAIL / **UNCERTAIN**, jamais un score.

Aucune n'est remplacée. Ce paquet leur donne une forme commune, pour que
leurs verdicts puissent enfin PILOTER quelque chose au lieu d'être
journalisés puis oubliés.

── La règle qui tient tout ──────────────────────────────────────────────

**Un axe non mesuré vaut `INCERTAIN`, jamais `REUSSI`.** Un système qui
traite « pas regardé » comme « bon » finit par livrer un clip statique de la
bonne durée en le déclarant conforme — c'est exactement ce qui est arrivé au
run #66.

`ObservationReport.axes_non_mesures` expose la carte des angles morts. Elle
est grande aujourd'hui, et c'est une information, pas une faiblesse du module.
"""

from pdz.observation.sondes import (
    depuis_verdict,
    observer_clip,
    observer_master,
    sonde_cadrage,
    sonde_coherence_duree,
    sonde_mouvement,
)

__all__ = [
    "observer_clip", "observer_master", "depuis_verdict",
    "sonde_mouvement", "sonde_coherence_duree", "sonde_cadrage",
]
