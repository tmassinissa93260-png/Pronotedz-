"""Les quatre stratégies que le dépôt sait déjà exécuter — enfin nommées.

Aucune n'est nouvelle. Toutes existaient, en `if/else`, sans nom :

  · `DIRECT_I2V`       l'appel au modèle payant (`animation.animer()`)
  · `TWO_POINT_FIVE_D` la parallaxe locale (`pdz/video/vie.py`)
  · `PROCEDURAL`       le recadrage glissant du montage (Ken Burns)
  · `STILL`            ne rien animer

Les nommer suffit à rendre visible ce que la cascade masquait : **deux
d'entre elles garantissent le mouvement, la troisième l'espère.**
"""

from __future__ import annotations

import logging
import time

from pdz.contracts.render import Strategie
from pdz.strategies.base import Candidate, ContexteRendu, ResultatStrategie

log = logging.getLogger(__name__)


class StrategieDirectI2V:
    """Image → vidéo par un modèle génératif. Le seul poste qui coûte.

    Et le seul dont le résultat n'est pas garanti : « API 200 » et « fichier
    livré » ne prouvent jamais qu'une image a changé d'une frame à l'autre.
    Le run #66 a mesuré un clip payé 0,046 €/s, valide, de la bonne durée, et
    parfaitement statique.
    """

    nom = Strategie.DIRECT_I2V

    # Mesuré, run #66 : sur les plans tentés au modèle, une part non
    # négligeable revient statique. `0.7` est une estimation par RÈGLE,
    # explicitement provisoire — `ExperienceMemory` la remplacera par le
    # taux réel dès qu'elle aura assez de lignes (PHASE 19).
    CONFIANCE_PAR_DEFAUT = 0.7

    # La seule stratégie capable d'INVENTER du mouvement : un personnage qui
    # tourne la tête, de la fumée qui s'échappe. Aucun traitement local ne
    # sait le faire, et c'est ce qui justifie sa dépense.
    SAIT_INVENTER = ("sujet", "ambiance", "camera", "")

    def evaluer(self, contexte: ContexteRendu) -> Candidate | None:
        from pdz.backends import backend_video
        from pdz.moteur.erreurs import ErreurPdz

        try:
            backend = backend_video(contexte.profil)
        except ErreurPdz as e:
            return Candidate(self.nom, 0.0, 0, 0.0, False,
                             raison=f"aucun backend vidéo : {e}")

        spec = self._spec(contexte)
        if not (validation := backend.valider(spec)).ok:
            # Refusée AVANT toute dépense — c'est tout l'intérêt d'avoir
            # séparé `valider()` d'`executer()`.
            return Candidate(self.nom, 0.0, 0, 0.0, False,
                             raison=" ; ".join(validation.bloquants))

        estimation = backend.estimer(spec)
        if estimation.eur > contexte.budget_restant_eur:
            return Candidate(self.nom, estimation.eur, estimation.latence_ms, 0.0,
                             False, raison=f"budget insuffisant "
                                           f"({estimation.eur:.3f} € > "
                                           f"{contexte.budget_restant_eur:.3f} €)")

        return Candidate(
            self.nom, estimation.eur, estimation.latence_ms,
            confiance=self.CONFIANCE_PAR_DEFAUT,
            # Jamais garanti. C'est la propriété la plus importante de cette
            # stratégie, et celle que la cascade en dur ne disait nulle part.
            garanti=False,
            raison=estimation.detail,
        )

    def executer(self, contexte: ContexteRendu) -> ResultatStrategie:
        from pdz.backends import backend_video

        debut = time.perf_counter()
        artefact = backend_video(contexte.profil).executer(self._spec(contexte))
        return ResultatStrategie(
            fichier=artefact.fichier, strategie=self.nom,
            cout_eur=artefact.cout_eur,
            latence_ms=int((time.perf_counter() - debut) * 1000),
            clip_produit=True,
            meta={"modele": artefact.modele, "fournisseur": artefact.fournisseur},
        )

    @staticmethod
    def _spec(contexte: ContexteRendu):
        from pdz.contracts.render import RenderSpecExecutable

        return RenderSpecExecutable(
            shot_id=contexte.shot_id,
            strategie=Strategie.DIRECT_I2V,
            duree_s=contexte.duree_s,
            prompt=contexte.prompt,
            image_depart=str(contexte.image),
            parametres={
                "destination": str(contexte.destination),
                "profil": contexte.profil,
                "budget_restant_pct": "100.0" if contexte.budget_restant_eur > 0 else "0.0",
                "job_id": contexte.job_id,
                "agent": "animation",
            },
        )


class StrategieTwoPointFiveD:
    """Parallaxe et particules calculées sur la machine — `pdz/video/vie.py`.

    Gratuit, et surtout **garanti** : c'est du calcul, pas une espérance. Ce
    n'est pas un remplaçant de Kling — ça n'invente aucun mouvement nouveau,
    ça donne de la vie à ce qui existe. Mais le mouvement, lui, est là à coup
    sûr, ce qu'aucun modèle génératif ne promet.

    Aucune limite de durée : le clip est fabriqué image par image. Le plafond
    qui existait autrefois ici avait tronqué cinq plans d'un épisode (#57) et
    fait échouer la vérification finale de durée.
    """

    nom = Strategie.DEUX_ET_DEMI_D

    # Ce qu'elle sait RÉELLEMENT rendre. Absent de cette liste : le
    # mouvement de SUJET. Faire tourner la tête d'un personnage demande
    # d'inventer des pixels qui n'existent pas dans l'image de départ.
    SAIT_RENDRE = ("ambiance", "camera", "")

    def evaluer(self, contexte: ContexteRendu) -> Candidate | None:
        if not contexte.image.exists():
            return None

        sait = contexte.mouvement_attendu in self.SAIT_RENDRE
        return Candidate(
            self.nom, cout_eur=0.0,
            # Quelques secondes de CPU par plan — réel, mais sans commune
            # mesure avec les ~180 s d'attente d'un modèle en file.
            latence_ms=3_000,
            # Face à un mouvement de sujet, elle produira quelque chose qui
            # BOUGE sans montrer ce qui était demandé. Le dire (confiance
            # basse) plutôt que de laisser croire au succès est exactement
            # ce que le contrat perceptuel exige : « ça bouge » n'est pas
            # « ça montre l'accélération ».
            confiance=0.95 if sait else 0.25,
            garanti=sait,
            raison=("parallaxe locale : gratuite, et le mouvement est calculé"
                    if sait else
                    "parallaxe locale : elle fera bouger l'image, mais ne sait "
                    "pas inventer un mouvement de sujet"),
        )

    def executer(self, contexte: ContexteRendu) -> ResultatStrategie:
        from pdz.video.vie import Effets
        from pdz.video.vie import animer as animer_localement

        debut = time.perf_counter()
        try:
            animer_localement(
                contexte.image, contexte.duree_s, contexte.destination,
                effets=Effets(sens=1 if contexte.index % 2 == 0 else -1,
                              graine=contexte.index),
            )
        except Exception as e:  # PIL, ffmpeg, disque plein…  # noqa: BLE001
            # Retombe sur le procédural plutôt que d'échouer : le montage
            # sait faire bouger une image fixe, et perdre le plan entier
            # pour un souci de disque serait disproportionné.
            log.warning("Parallaxe impossible sur le plan %d : %s", contexte.index, e)
            return StrategieProcedurale().executer(contexte)

        return ResultatStrategie(
            fichier=contexte.destination, strategie=self.nom, cout_eur=0.0,
            latence_ms=int((time.perf_counter() - debut) * 1000), clip_produit=True,
        )


class StrategieProcedurale:
    """Le recadrage glissant du montage — Ken Burns.

    Gratuit, instantané, garanti, et **sans aucun fichier intermédiaire** :
    c'est FFmpeg qui l'applique au moment du montage. D'où `clip_produit =
    False` — il n'y a rien à produire ici, seulement une décision à porter.
    """

    nom = Strategie.PROCEDURAL

    # Un recadrage glissant ne rend qu'un mouvement de CAMÉRA. C'est
    # exactement ce qu'il fait, et rien d'autre.
    SAIT_RENDRE = ("camera", "")

    def evaluer(self, contexte: ContexteRendu) -> Candidate | None:
        sait = contexte.mouvement_attendu in self.SAIT_RENDRE
        return Candidate(
            self.nom, cout_eur=0.0, latence_ms=0,
            confiance=0.9 if sait else 0.15,
            garanti=sait,
            raison=("recadrage appliqué par le montage, sans clip intermédiaire"
                    if sait else
                    f"recadrage seul : ne rend pas un mouvement "
                    f"« {contexte.mouvement_attendu} »"),
        )

    def executer(self, contexte: ContexteRendu) -> ResultatStrategie:
        return ResultatStrategie(
            fichier=contexte.image, strategie=self.nom, cout_eur=0.0,
            latence_ms=0, clip_produit=False,
        )


class StrategieImageFixe:
    """Ne rien animer du tout.

    Une décision LÉGITIME, pas un échec — et il faut pouvoir la distinguer
    d'une animation qui a raté. Un plan de deux secondes sur un personnage
    calme n'a rien à gagner à bouger.

    Toujours applicable, et toujours dernière au classement : sa confiance
    de `0.0` dit qu'aucun mouvement ne sera perçu, ce qui est exact.
    """

    nom = Strategie.IMAGE_FIXE

    def evaluer(self, contexte: ContexteRendu) -> Candidate | None:
        return Candidate(
            self.nom, cout_eur=0.0, latence_ms=0, confiance=0.0, garanti=True,
            raison="aucun mouvement — le dernier recours, jamais un échec",
        )

    def executer(self, contexte: ContexteRendu) -> ResultatStrategie:
        return ResultatStrategie(
            fichier=contexte.image, strategie=self.nom, cout_eur=0.0,
            latence_ms=0, clip_produit=False,
        )
