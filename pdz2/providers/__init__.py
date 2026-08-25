"""Ports et adaptateurs de fournisseurs.

Ce paquet a longtemps ne porté que des ports, et le disait : « aucun
adaptateur n'est implémenté ». Ce n'est plus vrai, et la nuance qui remplace
cette phrase compte plus qu'elle :

    un adaptateur **existe** dans le dépôt ;
    il n'est **actif** que si son identifiant est présent dans l'environnement.

Sans clé, `registry.active_providers()` ne rend que les moteurs locaux — le
rendu procédural et la voix hors-ligne — et l'écrit dans ses notes. La chaîne
produit alors un épisode complet, sans réseau, avec ses dégradations
enregistrées. Avec les clés, les adaptateurs distants passent devant, et le
repli local reste derrière eux : il n'est jamais retiré de la liste.

Aucun de ces adaptateurs n'a été appelé dans l'environnement où il a été
écrit — leurs hôtes y sont injoignables. Chacun le déclare en tête de fichier.
Leur première exécution réelle a lieu en intégration continue, et leur sonde
dit la vérité dès le premier appel : `pdz2 providers`.

Ports :
  * `pdz2.providers.video`   — génération vidéo
  * `pdz2.providers.image`   — génération d'images
  * `pdz2.audio.ports`       — synthèse vocale (adaptateur local eSpeak NG)
  * `pdz2.audio.library`     — bibliothèque sonore (aucun adaptateur)
  * `pdz2.engines.research.ports`   — recherche documentaire
  * `pdz2.engines.direction.ports`  — raisonneur
"""

from pdz2.providers.image import (
    NO_IMAGE_PROVIDERS,
    ImageProvider,
    ImageProviderUnavailable,
)
from pdz2.providers.registry import ActiveProviders, active_providers
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
    "ImageProvider",
    "ImageProviderUnavailable",
    "NO_IMAGE_PROVIDERS",
    "ActiveProviders",
    "active_providers",
]
