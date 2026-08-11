"""Le harnais pour comparer plusieurs vidéos de référence privées.

Aucune vidéo de référence ne vit dans ce dépôt — la plupart proviennent de
tiers (scraping, achat), et les y commettre serait distribuer un contenu
protégé sur un dépôt public. Ce module ne contient donc aucune vidéo : il
définit seulement comment en charger depuis un dossier LOCAL, ignoré par
git (`donnees/` l'est déjà — voir `.gitignore`), que chacun remplit avec
ses propres fichiers.

Emplacement par défaut : `donnees/references/`. Redirigeable avec la
variable d'environnement `PDZ_DOSSIER_REFERENCES` — utile pour pointer vers
un dossier monté depuis un stockage privé, hors de ce dépôt, sur une
machine de test.

À côté de chaque vidéo, un fichier YAML de même nom peut porter une
annotation écrite à la main AVANT toute analyse :

    # donnees/references/exemple.yaml
    mecanique_attendue: >
      Pose une question dans les 2 premières secondes, jamais répondue
      avant la fin. Chaque plan ajoute une info sans la résoudre.
    sujet_original: une IA qui explique la physique quantique avec un hologramme
    notes: trouvée sur TikTok, format "explication mystère"

`mecanique_attendue` est la moitié « attendu » du rapport avant/après (voir
`pdz.analyse.diversite` pour la moitié « obtenu », et
`pdz.analyse.rapport_transfert` pour le rapport lui-même). `sujet_original`
sert à une vérification différente : de quoi parlait vraiment la vidéo, en
quelques mots-clés — utilisé pour repérer si un script généré à partir de
son empreinte recopie ce sujet au lieu de transférer seulement le
mécanisme.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

EXTENSIONS_VIDEO = {".mp4", ".mov", ".webm", ".mkv", ".m4v"}


def dossier_references() -> Path:
    brut = os.environ.get("PDZ_DOSSIER_REFERENCES")
    return Path(brut) if brut else Path("donnees/references")


@dataclass
class VideoReference:
    """Une vidéo de référence privée, avec son annotation humaine optionnelle."""

    id: str
    chemin: Path
    mecanique_attendue: str = ""
    sujet_original: str = ""
    notes: str = ""


def _charger_annotation(chemin_video: Path) -> dict:
    chemin_yaml = chemin_video.with_suffix(".yaml")
    if not chemin_yaml.exists():
        return {}
    brut = yaml.safe_load(chemin_yaml.read_text(encoding="utf-8")) or {}
    return brut if isinstance(brut, dict) else {}


def lister_references(dossier: Path | None = None) -> list[VideoReference]:
    """Toutes les vidéos de référence trouvées localement, triées par id.

    Un dossier absent ou vide donne une liste vide — ce n'est pas une
    erreur : c'est l'état normal de ce dépôt tant que personne n'a déposé
    de vidéo en local. Le fichier `.univers.yaml` qu'une charte produit à
    côté n'est jamais confondu avec une vidéo : seules les extensions
    vidéo sont retenues.
    """
    d = dossier or dossier_references()
    if not d.is_dir():
        return []

    refs = []
    for chemin in sorted(d.iterdir()):
        if chemin.suffix.lower() not in EXTENSIONS_VIDEO:
            continue
        annotation = _charger_annotation(chemin)
        refs.append(VideoReference(
            id=chemin.stem,
            chemin=chemin,
            mecanique_attendue=str(annotation.get("mecanique_attendue", "")),
            sujet_original=str(annotation.get("sujet_original", "")),
            notes=str(annotation.get("notes", "")),
        ))
    return refs
