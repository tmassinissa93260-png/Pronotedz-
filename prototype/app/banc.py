"""Le banc d'essai : chaque contrôle, rejoué sur tous les storyboards passés.

Jusqu'ici, quand j'ajoutais un contrôle, je le testais sur un plateau inventé
et sur le run du jour. Je ne savais pas s'il se déclenchait sur les vingt-sept
storyboards déjà produits — donc je ne savais pas s'il était juste ou s'il
allait refuser du bon travail.

L'historique git garde chaque `project.json` de chaque run. C'est un corpus :
cinq sujets, vingt-sept plateaux, tous produits pour de vrai. Le banc les
rejoue et compte. Un contrôle qui s'allume sur vingt-cinq d'entre eux n'est
pas un contrôle, c'est une opinion.

Aucun appel réseau : on relit ce qui existe déjà.
"""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from dataclasses import dataclass

from . import config, validator
from .models import Storyboard, StoryboardError

CHEMIN_SUIVI = "prototype/app/output/project.json"


@dataclass
class Plateau:
    """Un storyboard produit un jour, retrouvé dans l'historique."""

    commit: str
    titre: str
    subject: str
    shots: int
    problemes: list

    @property
    def codes(self) -> Counter:
        return Counter(p.code for p in self.problemes)


def commits() -> list[tuple[str, str]]:
    """Les commits qui ont touché le storyboard, du plus récent au plus ancien."""
    sortie = subprocess.run(
        ["git", "log", "--format=%h\t%s", "--", CHEMIN_SUIVI],
        cwd=config.ROOT_DIR.parent, capture_output=True, text=True, timeout=60)
    lignes = [ligne.split("\t", 1) for ligne in sortie.stdout.splitlines() if "\t" in ligne]
    return [(sha, titre) for sha, titre in lignes]


def plateau(sha: str, titre: str) -> Plateau | None:
    """Le storyboard tel qu'il était à ce commit, validé avec ses propres mesures."""
    sortie = subprocess.run(
        ["git", "show", f"{sha}:{CHEMIN_SUIVI}"],
        cwd=config.ROOT_DIR.parent, capture_output=True, text=True, timeout=60)
    if sortie.returncode != 0 or not sortie.stdout.strip():
        return None
    try:
        sb = Storyboard.from_dict(json.loads(sortie.stdout))
    except (json.JSONDecodeError, StoryboardError):
        return None

    # Ses propres durée et nombre de plans : on juge le contenu, pas l'écart
    # à une consigne qui n'était pas la sienne.
    problemes = validator.validate(sb, sb.total_duration, len(sb.shots))
    return Plateau(commit=sha, titre=titre, subject=sb.subject,
                   shots=len(sb.shots), problemes=problemes)


def passer(limite: int = 0) -> list[Plateau]:
    """Tous les plateaux retrouvables, du plus récent au plus ancien."""
    trouves = []
    vus = set()
    for sha, titre in commits():
        p = plateau(sha, titre)
        if p is None:
            continue
        # Un commit qui ne touchait pas le storyboard rend le meme fichier :
        # on ne compte pas deux fois le meme plateau.
        empreinte = (p.subject, p.shots, tuple(str(x) for x in p.problemes))
        if empreinte in vus:
            continue
        vus.add(empreinte)
        trouves.append(p)
        if limite and len(trouves) >= limite:
            break
    return trouves


def total(plateaux: list[Plateau]) -> Counter:
    """Combien de fois chaque contrôle s'est allumé, tous plateaux confondus."""
    compte: Counter = Counter()
    for p in plateaux:
        compte.update(p.codes)
    return compte


def plateaux_touches(plateaux: list[Plateau]) -> Counter:
    """Sur COMBIEN de plateaux chaque contrôle s'allume — la mesure qui compte.

    Un contrôle qui s'allume trente fois sur un seul plateau vise un défaut
    réel. Le même, allumé une fois sur chacun des vingt-sept, vise le style
    de la maison.
    """
    compte: Counter = Counter()
    for p in plateaux:
        compte.update(set(p.codes))
    return compte
