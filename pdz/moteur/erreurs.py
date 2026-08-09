"""Taxonomie des erreurs.

La catégorie d'une erreur décide de trois choses, automatiquement :
  - est-ce qu'on réessaie ?
  - est-ce que ça a coûté de l'argent ?
  - est-ce qu'on peut se rabattre sur un modèle moins cher ?

Voir docs/06-solidite.md § « Quand ça plante ».
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Politique:
    reessayer: bool
    tentatives_max: int
    facturee: bool          # l'appel a consommé des tokens malgré l'échec
    repli_modele: bool      # basculer sur le modèle de secours
    bruyante: bool          # remonter à l'utilisateur


class ErreurPdz(Exception):
    """Base de toutes les erreurs du projet."""

    politique = Politique(
        reessayer=False, tentatives_max=1, facturee=False,
        repli_modele=False, bruyante=True,
    )

    def __init__(self, message: str, *, detail: object = None):
        super().__init__(message)
        self.detail = detail

    @property
    def categorie(self) -> str:
        return type(self).__name__


class ErreurReseau(ErreurPdz):
    """Timeout, connexion coupée, 502/503. On réessaie."""

    politique = Politique(True, 3, False, False, False)


class ErreurQuota(ErreurPdz):
    """429. On attend le délai indiqué, puis on bascule sur le repli."""

    politique = Politique(True, 3, False, True, False)

    def __init__(self, message: str, *, retry_after: float | None = None, detail=None):
        super().__init__(message, detail=detail)
        self.retry_after = retry_after


class ErreurFournisseur(ErreurPdz):
    """Le service est en panne. Repli immédiat, pas d'acharnement."""

    politique = Politique(True, 2, False, True, True)


class ErreurValidation(ErreurPdz):
    """La réponse ne respecte pas le schéma attendu.

    Facturée : le modèle a bien consommé des tokens. On relance en lui
    montrant son erreur — ça passe environ 8 fois sur 10 au 2e essai.
    Un modèle plus faible (Llama via le profil gratuit) rate parfois deux
    fois de suite un champ obligatoire (mesuré : `personnage` laissé vide) ;
    3 tentatives — le plafond que `pipeline.py` réserve déjà — coûte peu et
    laisse une vraie chance au profil gratuit sans toucher Claude, qui
    réussit presque toujours dès le premier essai.
    """

    politique = Politique(True, 3, True, False, False)


class ErreurRefus(ErreurPdz):
    """Le modèle refuse de répondre. Insister ne sert à rien."""

    politique = Politique(False, 1, False, False, True)


class ErreurBudget(ErreurPdz):
    """Plafond atteint. On s'arrête proprement."""

    politique = Politique(False, 1, False, False, True)


class ErreurConfig(ErreurPdz):
    """Clé d'API manquante, fichier absent, ffmpeg introuvable."""

    politique = Politique(False, 1, False, False, True)


def delai_backoff(tentative: int, base: float = 2.0, plafond: float = 120.0) -> float:
    """Exponentiel avec jitter : 2s, 4s, 8s… ±50 %.

    Le jitter évite que plusieurs étapes relancées en même temps ne repartent
    toutes à la même seconde.
    """
    brut = base * (2 ** max(0, tentative - 1))
    return min(brut * random.uniform(0.5, 1.5), plafond)
