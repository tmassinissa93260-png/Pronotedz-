"""Backend de reconnaissance musicale — enveloppe `pdz/ia/audd.py`.

Répare le dernier écart de l'audit : `analyse/musique.py` importait
`pdz.ia.audd` en direct.

`identifier()` peut rendre `None`, et ce n'est **pas** une erreur : c'est le
résultat normal quand la musique n'est pas dans la base, ce qui arrive
souvent avec les musiques libres de droits. L'appel reste facturé — d'où
l'importance que ce cas soit un retour explicite plutôt qu'une exception
qu'on serait tenté d'avaler.
"""

from __future__ import annotations

from pathlib import Path

from pdz.contracts.capabilities import Capacite, ModeleCapacites
from pdz.contracts.communs import StatutCapacite
from pdz.ia.registre import registre
from pdz.moteur.erreurs import ErreurConfig, ErreurPdz

_CAPACITES_AUDD = (
    Capacite(nom="identification_musicale", statut=StatutCapacite.MESURE, valeur=True,
             methode="pdz/ia/audd.py::identifier"),
    # Une limite MESURÉE, et qui vivait déjà en commentaire du code : AudD
    # s'arrête à 10 Mo, l'adaptateur lève avant l'envoi.
    Capacite(nom="extrait_10Mo_max", statut=StatutCapacite.MESURE, valeur=True,
             methode="TAILLE_MAX_OCTETS, vérifié avant envoi"),
    Capacite(nom="separation_de_pistes", statut=StatutCapacite.INCONNU),
)


class BackendMusiqueAudd:
    nom = "audd"

    def capabilities(self) -> ModeleCapacites:
        try:
            res = registre().resoudre("musique", repli_si_cle_absente=True)
            modele, fournisseur = res.modele.id, res.modele.fournisseur
        except ErreurPdz:
            modele, fournisseur = "", self.nom
        return ModeleCapacites(
            id=f"capacites_{modele or self.nom}",
            modele=modele, fournisseur=fournisseur, capacites=_CAPACITES_AUDD,
        )

    def identifier(self, extrait: Path, *, job_id: str | None = None):
        from pdz.ia import audd
        return audd.identifier(extrait, job_id=job_id)


# Le registre des backends. PUBLIC, et c'est voulu : c'est le point
# d'extension de l'architecture — ajouter un fournisseur, ou en substituer un
# dans un test, doit se faire sans toucher au code ni forcer une porte
# privée. Un registre caché obligerait les tests à patcher des attributs de
# module, ce qui reviendrait à contourner l'interface qu'on prétend offrir.
BACKENDS: dict[str, object] = {"audd": BackendMusiqueAudd()}


def backend_musique(profil: str = "equilibre"):
    res = registre().resoudre("musique", profil=profil, repli_si_cle_absente=True)
    backend = BACKENDS.get(res.modele.fournisseur)
    if backend is None:
        raise ErreurConfig(
            f"« {res.modele.id} » relève de « {res.modele.fournisseur} », pour "
            f"lequel aucun backend de reconnaissance musicale n'existe. "
            f"Connus : {', '.join(sorted(BACKENDS))}."
        )
    return backend


def enregistrer(fournisseur: str, backend) -> None:
    BACKENDS[fournisseur] = backend
