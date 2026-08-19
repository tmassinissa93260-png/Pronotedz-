"""Backend vidéo : enveloppe les adaptateurs, ne les réécrit pas.

`pdz/ia/fal.py` sait parler à fal.ai — file d'attente, data-URI, sondage.
Rien de tout cela ne change. Ce module ajoute ce qui manquait : une
interface que le métier peut appeler **sans savoir que fal existe**.

C'est la réparation de l'écart le plus visible de l'audit :
`production/animation.py` importait `pdz.ia.fal` en direct.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from pdz.backends.base import ArtefactRendu, EstimationCout, Validation
from pdz.contracts.capabilities import Capacite, ModeleCapacites
from pdz.contracts.communs import StatutCapacite
from pdz.contracts.render import RenderSpecExecutable
from pdz.ia.registre import registre
from pdz.moteur.erreurs import ErreurConfig, ErreurPdz

log = logging.getLogger(__name__)

# Ce que fal.ai reçoit RÉELLEMENT dans le corps de la requête :
# {prompt, image_url, duration, aspect_ratio}. Rien d'autre. Ces mesures
# viennent du code de `pdz/ia/fal.py`, pas d'une documentation — d'où
# `MESURE` sur ce qui est vérifiable en lisant l'appel, et `INCONNU` sur ce
# que personne n'a testé.
#
# Le contraste est le point : `camera_control` est ANNONCÉ par plusieurs
# fournisseurs et n'a jamais été mesuré ici. Le déclarer MESURE parce que la
# documentation l'affirme est exactement l'erreur que `StatutCapacite`
# existe pour empêcher.
_CAPACITES_FAL = (
    Capacite(nom="image_to_video", statut=StatutCapacite.MESURE, valeur=True,
             methode="corps de requête de pdz/ia/fal.py::animer_image"),
    Capacite(nom="text_to_video", statut=StatutCapacite.INCONNU,
             note="l'adaptateur n'envoie jamais de requête sans image"),
    Capacite(nom="camera_control", statut=StatutCapacite.INCONNU,
             note="aucun paramètre de caméra n'est envoyé — voir "
                  "ControleCamera.TEXTE_SEULEMENT"),
    Capacite(nom="reference_images", statut=StatutCapacite.INCONNU),
    Capacite(nom="first_frame", statut=StatutCapacite.MESURE, valeur=True,
             methode="`image_url` EST la première frame"),
    Capacite(nom="last_frame", statut=StatutCapacite.INCONNU),
    Capacite(nom="masks", statut=StatutCapacite.INCONNU),
)


class BackendVideoFal:
    """fal.ai — le seul backend vidéo réel aujourd'hui."""

    nom = "fal"

    def capabilities(self, profil: str = "equilibre") -> ModeleCapacites:
        """Les capacités du modèle RÉSOLU, pas d'un modèle codé en dur.

        `durees_s` est une capacité MESURÉE et le dépôt le savait déjà :
        « ltx-video rend ~4,84 s qu'on lui demande 5 ou 10 ». Cette mesure
        vivait en commentaire de `modeles.yaml` ; elle devient une donnée.
        """
        try:
            res = registre().resoudre("animation", profil=profil,
                                      repli_si_cle_absente=True)
        except ErreurPdz:
            return ModeleCapacites(modele="", fournisseur=self.nom)
        return ModeleCapacites(
            id=f"capacites_{res.modele.id}",
            modele=res.modele.id,
            fournisseur=res.modele.fournisseur,
            capacites=_CAPACITES_FAL,
            durees_s=tuple(res.modele.durees_s),
        )

    def valider(self, spec: RenderSpecExecutable) -> Validation:
        """Tout ce qui est refusable sans dépenser un centime."""
        bloquants: list[str] = []
        avertissements: list[str] = []

        if not spec.image_depart:
            bloquants.append(
                "aucune image de départ : ce backend ne fait que de l'image→vidéo"
            )
        elif not Path(spec.image_depart).exists():
            bloquants.append(f"image de départ introuvable : {spec.image_depart}")

        if spec.duree_s <= 0:
            bloquants.append(f"durée invalide : {spec.duree_s} s")

        capacites = self.capabilities()
        if capacites.durees_s and spec.duree_s > max(capacites.durees_s):
            bloquants.append(
                f"{spec.duree_s} s demandées, mais « {capacites.modele} » ne "
                f"livre jamais plus de {max(capacites.durees_s)} s"
            )
        if not spec.prompt.strip():
            avertissements.append("prompt vide : le modèle animera à l'aveugle")

        return Validation(tuple(bloquants), tuple(avertissements))

    def estimer(self, spec: RenderSpecExecutable) -> EstimationCout:
        """Le coût AVANT l'appel — c'est ce qui permet le garde-fou de budget.

        `sur=False` en toutes circonstances : les prix de `modeles.yaml`
        bougent tous les 2-3 mois, et le fichier le documente lui-même. Une
        estimation présentée comme certaine finirait par servir de facture.
        """
        try:
            res = registre().resoudre("animation", repli_si_cle_absente=True)
        except ErreurPdz:
            return EstimationCout(detail="modèle d'animation non résolu")

        facturee = (res.modele.duree_facturable(spec.duree_s)
                    if res.modele.durees_s else spec.duree_s)
        return EstimationCout(
            eur=res.modele.cout_unites(facturee, "seconde"),
            # Mesuré en production : 409 s d'attente pour un clip de 5 s
            # (épisode #74). Une estimation basse ferait croire à une
            # latence que ce backend n'a jamais tenue.
            latence_ms=180_000,
            sur=False,
            detail=f"{facturee} s facturées chez {res.modele.id}",
        )

    def executer(self, spec: RenderSpecExecutable) -> ArtefactRendu:
        """Délègue à l'adaptateur. Valide d'abord — toujours.

        Valider ici plutôt que de faire confiance à l'appelant : c'est le
        dernier point avant la dépense, et un appelant qui oublie de valider
        ne doit pas pouvoir engager un euro pour rien.
        """
        from pdz.ia import fal

        if not (validation := self.valider(spec)).ok:
            raise ErreurConfig(
                f"Rendu vidéo refusé avant dépense : "
                f"{' ; '.join(validation.bloquants)}"
            )
        for avertissement in validation.avertissements:
            log.warning("Rendu %s : %s", spec.shot_id, avertissement)

        debut = time.perf_counter()
        fichier, cout = fal.animer_image(
            Path(spec.image_depart), spec.prompt, Path(spec.parametres["destination"]),
            duree_s=int(spec.duree_s),
            profil=spec.parametres.get("profil", "equilibre"),
            budget_restant_pct=float(spec.parametres.get("budget_restant_pct", 100.0)),
            job_id=spec.parametres.get("job_id") or None,
            etape=spec.parametres.get("etape") or None,
            agent=spec.parametres.get("agent") or None,
        )
        return ArtefactRendu(
            fichier=fichier, cout_eur=cout,
            latence_ms=int((time.perf_counter() - debut) * 1000),
            modele=spec.modele, fournisseur=self.nom,
        )


# ── Le registre : le métier demande une capacité, jamais un fournisseur ──

# Le registre des backends. PUBLIC, et c'est voulu : c'est le point
# d'extension de l'architecture — ajouter un fournisseur, ou en substituer un
# dans un test, doit se faire sans toucher au code ni forcer une porte
# privée. Un registre caché obligerait les tests à patcher des attributs de
# module, ce qui reviendrait à contourner l'interface qu'on prétend offrir.
BACKENDS: dict[str, object] = {"fal": BackendVideoFal()}


def backend_video(profil: str = "equilibre"):
    """Le backend vidéo du modèle RÉSOLU pour ce profil.

    Aucun appelant ne nomme jamais « fal » : la résolution passe par
    `modeles.yaml`, donc changer de fournisseur vidéo ne touche pas une
    ligne du métier.
    """
    res = registre().resoudre("animation", profil=profil, repli_si_cle_absente=True)
    backend = BACKENDS.get(res.modele.fournisseur)
    if backend is None:
        raise ErreurConfig(
            f"« {res.modele.id} » relève du fournisseur "
            f"« {res.modele.fournisseur} », pour lequel aucun backend vidéo "
            f"n'existe. Connus : {', '.join(sorted(BACKENDS))}."
        )
    return backend


def enregistrer(fournisseur: str, backend) -> None:
    """Ajoute un backend vidéo. Sert aux tests et aux futurs fournisseurs."""
    BACKENDS[fournisseur] = backend
