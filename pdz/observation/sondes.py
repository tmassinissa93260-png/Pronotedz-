"""Les sondes existantes, traduites en `Mesure`.

Chaque fonction ici est une TRADUCTION, pas une réimplémentation : elle
appelle la sonde du dépôt et enveloppe son verdict. Les seuils calibrés sur
données réelles sont conservés tels quels — les rejouer autrement reviendrait
à jeter le travail de mesure qui les a produits.

`seuil` est reporté dans chaque `Mesure` : sans lui, un ancien rapport
devient ininterprétable après un recalibrage.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pdz.contracts.communs import Verdict
from pdz.contracts.observation import Axe, Mesure, ObservationReport

log = logging.getLogger(__name__)


def sonde_mouvement(clip: Path, *, fenetre_s: float | None = None,
                    attendu: str = "") -> tuple[Mesure, ...]:
    """Ce clip bouge-t-il vraiment ? — et le fichier est-il seulement lisible ?

    Deux mesures et non une : « le fichier est valide » et « l'image change »
    sont deux constats indépendants, et le run #66 a montré qu'un clip peut
    parfaitement tenir le premier en ratant le second.
    """
    from pdz.production import verification_mouvement

    verdict = verification_mouvement.verifier(clip, fenetre_s=fenetre_s)

    technique = Mesure(
        axe=Axe.TECHNIQUE, nom="fichier_valide",
        verdict=Verdict.REUSSI if verdict.fichier_valide else Verdict.ECHOUE,
        sonde="verification_mouvement",
        valeur=f"{verdict.duree_s:.2f} s à {verdict.fps:.1f} fps",
        detail=verdict.raison,
    )

    if not verdict.fichier_valide:
        # Sans fichier lisible, le mouvement n'est pas « absent » : il est
        # INCONNU. Le déclarer échoué accuserait le modèle d'un problème de
        # fichier, et ferait chercher au mauvais endroit.
        return (technique, Mesure(
            axe=Axe.MOUVEMENT, nom="mouvement_percu", verdict=Verdict.INCERTAIN,
            sonde="verification_mouvement", attendu=attendu,
            detail="fichier illisible : le mouvement n'a pas pu être mesuré",
        ))

    return (technique, Mesure(
        axe=Axe.MOUVEMENT, nom="mouvement_percu",
        verdict=Verdict.REUSSI if verdict.mouvement_detecte else Verdict.ECHOUE,
        sonde="verification_mouvement",
        valeur=f"{verdict.diff_moyenne:.3f}/255 sur {verdict.frames_echantillonnees} frames",
        attendu=attendu,
        seuil=f"{verification_mouvement.SEUIL_MOUVEMENT}/255",
        detail=verdict.raison,
    ))


def sonde_coherence_duree(attendu_s: float, mesure_s: float, *,
                          tolerance_s: float = 0.5) -> Mesure:
    """La vidéo dure-t-elle aussi longtemps que la voix qui la porte ?

    Mesuré sur un épisode réel : 42,7 s d'audio, 28,1 s de vidéo — les 14
    dernières secondes de narration n'avaient plus aucune image, et rien ne
    le signalait.
    """
    from pdz.production import coherence_duree

    ecart = coherence_duree.ecart(attendu_s, mesure_s)
    return Mesure(
        axe=Axe.TEMPOREL, nom="duree_couvre_la_parole",
        verdict=Verdict.REUSSI if abs(ecart) <= tolerance_s else Verdict.ECHOUE,
        sonde="coherence_duree",
        valeur=f"{mesure_s:.2f} s", attendu=f"{attendu_s:.2f} s",
        seuil=f"±{tolerance_s} s",
        detail=f"écart de {ecart:+.2f} s",
    )


def sonde_cadrage(cadrages: list[str]) -> Mesure:
    """Deux plans consécutifs ne partagent pas le même cadrage.

    En DIAGNOSTIC seulement, comme dans le module d'origine : une répétition
    n'est pas toujours une faute — deux gros plans qui se suivent peuvent
    être le bon choix pour une scène précise. Ce qui compte est de le SAVOIR.
    D'où `INCERTAIN` plutôt qu'`ECHOUE` : ce n'est pas à la traduction de
    durcir un choix que le module d'origine a explicitement refusé de faire.
    """
    from pdz.production import cadrage

    avertissements = cadrage.verifier_diversite(cadrages)
    return Mesure(
        axe=Axe.CONTINUITE, nom="diversite_cadrage",
        verdict=Verdict.REUSSI if not avertissements else Verdict.INCERTAIN,
        sonde="cadrage",
        valeur=f"{len(avertissements)} répétition(s)",
        detail=" ; ".join(avertissements),
    )


def observer_clip(clip: Path, *, shot_id: str = "", fenetre_s: float | None = None,
                  attendu: str = "") -> ObservationReport:
    """Le rapport d'un clip isolé, avant montage."""
    return ObservationReport(
        id=f"observation_{shot_id}" if shot_id else "",
        shot_id=shot_id, artefact=str(clip),
        mesures=sonde_mouvement(clip, fenetre_s=fenetre_s, attendu=attendu),
    )


def observer_master(video: Path, plans, *, duree_voix_s: float = 0.0,
                    cadrages: list[str] | None = None) -> ObservationReport:
    """Le rapport de la vidéo FINALE, celle qui part au spectateur.

    Distinct d'`observer_clip` : ici les bornes de chaque plan sont connues
    exactement (durées cumulées), il n'y a pas à deviner les coupes. Un clip
    accepté avant montage peut très bien être immobile sur la fenêtre que le
    montage garde réellement.
    """
    from pdz.analyse.sonde import sonder
    from pdz.production import qa_video_finale

    mesures: list[Mesure] = []

    metadonnees = sonder(video)
    mesures.append(Mesure(
        axe=Axe.TECHNIQUE, nom="master_lisible",
        verdict=Verdict.REUSSI if metadonnees.duree_s > 0 else Verdict.ECHOUE,
        sonde="sonde", valeur=f"{metadonnees.duree_s:.2f} s",
    ))

    if duree_voix_s > 0:
        mesures.append(sonde_coherence_duree(duree_voix_s, metadonnees.duree_s))

    for resultat in qa_video_finale.verifier(video, plans):
        bouge = bool(resultat.get("mouvement_detecte"))
        mesures.append(Mesure(
            axe=Axe.MOUVEMENT,
            nom=f"mouvement_plan_{resultat.get('plan', '?')}",
            # Un plan qui ne devait PAS bouger n'échoue pas parce qu'il ne
            # bouge pas. Ce module ne connaît pas l'intention du plan : il
            # RAPPORTE, et c'est le diagnostic qui confronte à l'attendu.
            verdict=Verdict.REUSSI if bouge else Verdict.INCERTAIN,
            sonde="qa_video_finale",
            valeur=f"{resultat.get('diff_moyenne', 0):.3f}/255",
            detail="mesuré sur le master monté",
        ))

    if cadrages:
        mesures.append(sonde_cadrage(cadrages))

    return ObservationReport(
        id="observation_master", shot_id="master", artefact=str(video),
        mesures=tuple(mesures),
    )
