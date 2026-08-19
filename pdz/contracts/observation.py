"""Ce qu'on a MESURÉ sur un rendu — jamais ce qu'on en pense.

Le dépôt possède déjà de vraies sondes, et de bonnes : différence
inter-frames en niveaux de gris avec un seuil calibré sur des mesures réelles
(`verification_mouvement.py`), mouvement par plan sur le master monté
(`qa_video_finale.py`), cohérence voix/vidéo (`coherence_duree.py`), variété
de cadrage (`cadrage.py`), et un agent de vision qui rend `PASS`/`FAIL`/
`UNCERTAIN` sans jamais donner de score.

Ce contrat ne les remplace pas : il leur donne une forme commune, pour que
leurs verdicts puissent enfin PILOTER quelque chose au lieu d'être journalisés.

── La règle qui tient tout ──────────────────────────────────────────────

Un axe non mesuré vaut `INCERTAIN`, **jamais** `REUSSI`. Un système qui
traite « pas regardé » comme « bon » finit par livrer un clip statique de la
bonne durée en le déclarant conforme — c'est exactement ce qui est arrivé,
et c'est ce que ce contrat rend impossible à répéter en silence.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict

from pdz.contracts.base import Contrat
from pdz.contracts.communs import Verdict


class Axe(str, Enum):
    """Les six familles de mesure. Aucune ne vaut pour une autre."""

    TECHNIQUE = "technical"      # durée, fps, résolution, codec, intégrité
    TEMPOREL = "temporal"        # coupes, gels, scintillement
    MOUVEMENT = "motion"         # caméra, sujet, environnement, amplitude
    SEMANTIQUE = "semantic"      # présence, identité, événement accompli
    CONTINUITE = "continuity"    # couleur, géométrie, état, position
    AUDIO = "audio"              # synchronisation, loudness, crêtes


class Mesure(BaseModel):
    """Un constat, avec sa source et ce qui le justifie.

    `sonde` n'est pas décoratif : c'est ce qui permet de savoir qu'un axe
    est `INCERTAIN` parce que personne ne sait le mesurer, et non parce que
    la mesure a échoué. Les deux appellent des actions opposées.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    axe: Axe
    nom: str                             # « mouvement_sujet », « duree_s »…
    verdict: Verdict = Verdict.INCERTAIN
    sonde: str = ""
    # La valeur brute mesurée, telle quelle. Texte : une diff de pixels, une
    # durée et un booléen n'ont pas le même type, et les forcer dans un
    # `float` commun ferait perdre le sens de chacun.
    valeur: str = ""
    attendu: str = ""
    # Le seuil appliqué, quand il y en a un. Le porter ici rend le verdict
    # RELISIBLE plus tard, y compris après un recalibrage — sans lui, un
    # ancien rapport devient ininterprétable.
    seuil: str = ""
    detail: str = ""


class ObservationReport(Contrat):
    """Tout ce qu'on sait d'un rendu, après l'avoir regardé."""

    VERSION = "1.0.0"

    shot_id: str = ""
    artefact: str = ""
    mesures: tuple[Mesure, ...] = ()

    def par_axe(self, axe: Axe) -> tuple[Mesure, ...]:
        return tuple(m for m in self.mesures if m.axe is axe)

    def verdict_axe(self, axe: Axe) -> Verdict:
        """Le verdict d'un axe : un seul échec suffit à le faire échouer.

        Un axe sans aucune mesure est `INCERTAIN` — pas `REUSSI`. C'est la
        règle centrale du module, et elle est appliquée ici plutôt que
        laissée à chaque appelant.
        """
        mesures = self.par_axe(axe)
        if not mesures:
            return Verdict.INCERTAIN
        if any(m.verdict is Verdict.ECHOUE for m in mesures):
            return Verdict.ECHOUE
        if any(m.verdict is Verdict.INCERTAIN for m in mesures):
            return Verdict.INCERTAIN
        return Verdict.REUSSI

    @property
    def verdict(self) -> Verdict:
        """Le verdict global, sur les six axes — mesurés ou non."""
        par_axe = [self.verdict_axe(a) for a in Axe]
        if Verdict.ECHOUE in par_axe:
            return Verdict.ECHOUE
        return Verdict.REUSSI if all(v is Verdict.REUSSI for v in par_axe) else Verdict.INCERTAIN

    @property
    def echecs(self) -> tuple[Mesure, ...]:
        return tuple(m for m in self.mesures if m.verdict is Verdict.ECHOUE)

    @property
    def axes_non_mesures(self) -> tuple[Axe, ...]:
        """Ce que le système ne sait pas encore regarder. Sa propre carte
        des angles morts — utile telle quelle, et honnête."""
        return tuple(a for a in Axe if not self.par_axe(a))
