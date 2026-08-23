"""Adaptateurs de fournisseurs.

**Aucun adaptateur n'est implémenté.** Les ports sont définis — c'est eux qui
comptent pour l'architecture — mais la politique réseau de cet environnement
refuse les hôtes de génération et aucun identifiant n'est disponible. Un
client qu'on ne peut ni joindre ni vérifier serait une capacité fictive, que
le cahier des charges interdit.

Le système fonctionne sans eux : les stratégies déterministes des phases 5 et
7 rendent réellement, et chaque dégradation qui en découle est enregistrée.

Ports disponibles :
  * `pdz2.providers.video`   — génération vidéo (phase 6)
  * `pdz2.audio.ports`       — synthèse vocale (phase 2, adaptateur eSpeak NG)
  * `pdz2.engines.research.ports`   — recherche documentaire (phase 1)
  * `pdz2.engines.direction.ports`  — raisonneur (phase 1)
"""

from pdz2.providers.video import (
    NO_VIDEO_PROVIDERS,
    ProviderUnavailable,
    VideoCapability,
    VideoJob,
    VideoProvider,
    VideoResult,
)

__all__ = [
    "VideoProvider",
    "VideoCapability",
    "VideoJob",
    "VideoResult",
    "ProviderUnavailable",
    "NO_VIDEO_PROVIDERS",
]
