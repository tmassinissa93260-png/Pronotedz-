"""Port de bibliothèque sonore.

Le compilateur sonore ne connaît aucun catalogue : il connaît ce protocole.
Une bibliothèque déclare sa capacité — mesurée et datée, jamais annoncée — et
rend le chemin d'un fichier réel, ou rien.

État réel dans ce dépôt : **aucune bibliothèque n'est implémentée.** Il n'y a
dans cet environnement ni catalogue de bruitages, ni accès réseau vers un
service qui en fournirait, ni licence sur quoi que ce soit. Synthétiser un
« impact » ou un « souffle » au générateur de bruit produirait un son, pas une
conception sonore : ce serait une capacité fictive, ce que le cahier des
charges interdit.

Les repères sonores sont donc décidés, placés sur la timeline, et déclarés
`UNRESOLVED` avec leur raison. Le jour où un catalogue arrivera, il
implémentera ce protocole et rien en amont ne bougera.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from pdz2.contracts.capability import CapabilityState, ProviderCapability
from pdz2.contracts.enums import AudioEventKind

__all__ = ["SoundLibrary", "NO_SOUND_LIBRARIES", "no_library_capability"]


@runtime_checkable
class SoundLibrary(Protocol):
    """Interface commune des sources de sons."""

    name: str

    def get_capabilities(self) -> ProviderCapability:
        """Sonde réellement le catalogue. Ne jamais deviner son état."""

    def resolve(self, kind: AudioEventKind, duration_s: float) -> Path | None:
        """Rend le fichier d'un son adapté, ou `None` s'il n'y en a pas."""


NO_SOUND_LIBRARIES: tuple[SoundLibrary, ...] = ()
"""Aucune bibliothèque sonore n'est implémentée dans ce dépôt.

Constante explicite plutôt que liste vide anonyme : le compilateur sonore la
reçoit, la nomme dans ses constats, et le lecteur sait pourquoi ses repères
restent muets.
"""


def no_library_capability() -> ProviderCapability:
    """Capacité déclarée quand aucun catalogue n'est branché."""
    return ProviderCapability(
        provider="sound_library",
        state=CapabilityState.UNAVAILABLE,
        measured_at=datetime.now(UTC),
        measurement_method="inventaire des bibliothèques déclarées",
        detail=(
            "aucune bibliothèque sonore implémentée : ni catalogue local, ni "
            "service joignable, ni licence. Les repères sonores sont décidés "
            "et placés, mais resteront muets."
        ),
        requires_network=False,
    )
