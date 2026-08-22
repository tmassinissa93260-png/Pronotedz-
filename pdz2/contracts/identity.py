"""Fabrique d'identifiants de contrats.

Un identifiant porte le nom du contrat en préfixe : lire un journal de
production sans schéma reste possible. La fabrique est remplaçable par une
fabrique déterministe, pour que deux exécutions d'un même épisode avec la
même graine produisent les mêmes identifiants — condition de la
reproductibilité exigée par le cahier des charges.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

__all__ = ["new_id", "deterministic_ids", "set_id_factory", "IdFactory"]

IdFactory = Callable[[str], str]

# Espace de noms fixe : les identifiants déterministes sont stables d'une
# machine à l'autre et d'une version de Python à l'autre.
_NAMESPACE = uuid.UUID("6f9d4b1e-0b3a-5c8f-9a21-7d2f4c6e8b10")


def _random_factory(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:20]}"


_factory: ContextVar[IdFactory] = ContextVar("pdz2_id_factory", default=_random_factory)


def new_id(prefix: str) -> str:
    """Retourne un identifiant neuf pour un contrat nommé `prefix`."""
    if not prefix:
        raise ValueError("un identifiant de contrat exige un préfixe non vide")
    return _factory.get()(prefix)


def set_id_factory(factory: IdFactory) -> object:
    """Installe une fabrique. Retourne le jeton de restauration ContextVar."""
    return _factory.set(factory)


@contextmanager
def deterministic_ids(seed: str | int) -> Iterator[None]:
    """Rend `new_id` déterministe pour la durée du bloc.

    Les identifiants sont numérotés par préfixe : le n-ième `shot_spec` d'une
    exécution donnée porte toujours le même identifiant.
    """
    counters: dict[str, int] = {}

    def factory(prefix: str) -> str:
        index = counters.get(prefix, 0)
        counters[prefix] = index + 1
        digest = uuid.uuid5(_NAMESPACE, f"{seed}|{prefix}|{index}")
        return f"{prefix}-{digest.hex[:20]}"

    token = _factory.set(factory)
    try:
        yield
    finally:
        _factory.reset(token)
