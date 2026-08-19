"""Les backends : tout ce qui parle à un fournisseur, et rien d'autre.

Le métier importe CE paquet, jamais `pdz.ia.<fournisseur>`. La règle est
vérifiée par `tests/test_architecture.py`, et elle a une raison simple :
tant qu'un module de production nomme fal.ai, changer de fournisseur vidéo
demande de modifier le métier.

    métier  →  backends  →  pdz/ia/<fournisseur>  →  HTTP

`pdz/ia/*` reste inchangé : ce sont les clients HTTP, écrits et éprouvés.
Ce paquet les ENVELOPPE — il n'en réécrit aucun.

Chaque famille a son mock, et ce n'est pas un détail de test : si un mock ne
peut pas remplacer un vrai backend, c'est que le métier connaît encore le
fournisseur.
"""

from pdz.backends.base import (
    ArtefactRendu,
    EstimationCout,
    ReconnaissanceAudioBackend,
    TTSBackend,
    Validation,
    VideoBackend,
)
from pdz.backends.mock import BackendMusiqueMock, BackendVideoMock, BackendVoixMock
from pdz.backends.musique import backend_musique
from pdz.backends.video import backend_video
from pdz.backends.voix import backend_voix

__all__ = [
    # interfaces
    "VideoBackend", "TTSBackend", "ReconnaissanceAudioBackend",
    "Validation", "EstimationCout", "ArtefactRendu",
    # résolution — le métier n'appelle que ça
    "backend_video", "backend_voix", "backend_musique",
    # tests
    "BackendVideoMock", "BackendVoixMock", "BackendMusiqueMock",
]
