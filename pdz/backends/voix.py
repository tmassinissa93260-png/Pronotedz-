"""Backend de synthèse vocale — enveloppe `pdz/ia/elevenlabs.py`.

Répare deux écarts de l'audit d'un coup : `production/voix.py` et
`production/appariement_voix.py` importaient tous deux `pdz.ia.elevenlabs`
en direct.

Ce que ce backend garantit et qui compte plus que tout le reste :
**l'alignement mot à mot**. La chronologie officielle de la production en
dépend — un backend qui ne rendrait que l'audio ferait retomber le karaoké
sur une estimation au prorata des longueurs, et la synchronisation
dériverait de quelques dixièmes sur chaque phrase longue.
"""

from __future__ import annotations

from pathlib import Path

from pdz.contracts.capabilities import Capacite, ModeleCapacites
from pdz.contracts.communs import StatutCapacite
from pdz.ia.registre import registre
from pdz.moteur.erreurs import ErreurConfig, ErreurPdz

# Mesurées en lisant l'appel réel : l'adaptateur interroge
# `/with-timestamps`, qui rend l'alignement caractère par caractère.
_CAPACITES_ELEVENLABS = (
    Capacite(nom="text_to_speech", statut=StatutCapacite.MESURE, valeur=True,
             methode="pdz/ia/elevenlabs.py::synthetiser"),
    Capacite(nom="word_timestamps", statut=StatutCapacite.MESURE, valeur=True,
             methode="endpoint /with-timestamps, alignement caractère par caractère"),
    Capacite(nom="catalogue_de_voix", statut=StatutCapacite.MESURE, valeur=True,
             methode="pdz/ia/elevenlabs.py::lister_voix"),
    Capacite(nom="clonage_de_voix", statut=StatutCapacite.INCONNU,
             note="jamais appelé par ce dépôt"),
)


class BackendVoixElevenLabs:
    nom = "elevenlabs"

    def capabilities(self) -> ModeleCapacites:
        try:
            res = registre().resoudre("voix", repli_si_cle_absente=True)
            modele, fournisseur = res.modele.id, res.modele.fournisseur
        except ErreurPdz:
            modele, fournisseur = "", self.nom
        return ModeleCapacites(
            id=f"capacites_{modele or self.nom}",
            modele=modele, fournisseur=fournisseur,
            capacites=_CAPACITES_ELEVENLABS,
        )

    def voix_disponibles(self) -> list:
        from pdz.ia import elevenlabs
        return elevenlabs.lister_voix()

    def synthetiser(self, texte: str, sortie: Path, *, voice_id: str,
                    stabilite: float = 0.5, style: float = 0.4,
                    vitesse: float = 1.0) -> tuple[Path, list]:
        from pdz.ia import elevenlabs
        return elevenlabs.synthetiser(
            texte, sortie, voice_id=voice_id, stabilite=stabilite,
            style=style, vitesse=vitesse,
        )

    def quota(self) -> dict:
        from pdz.ia import elevenlabs
        return elevenlabs.quota()


# Le registre des backends. PUBLIC, et c'est voulu : c'est le point
# d'extension de l'architecture — ajouter un fournisseur, ou en substituer un
# dans un test, doit se faire sans toucher au code ni forcer une porte
# privée. Un registre caché obligerait les tests à patcher des attributs de
# module, ce qui reviendrait à contourner l'interface qu'on prétend offrir.
BACKENDS: dict[str, object] = {"elevenlabs": BackendVoixElevenLabs()}


def backend_voix(profil: str = "equilibre"):
    """Le backend de voix du modèle résolu — jamais nommé par l'appelant."""
    res = registre().resoudre("voix", profil=profil, repli_si_cle_absente=True)
    backend = BACKENDS.get(res.modele.fournisseur)
    if backend is None:
        raise ErreurConfig(
            f"« {res.modele.id} » relève de « {res.modele.fournisseur} », "
            f"pour lequel aucun backend de voix n'existe. "
            f"Connus : {', '.join(sorted(BACKENDS))}."
        )
    return backend


def enregistrer(fournisseur: str, backend) -> None:
    BACKENDS[fournisseur] = backend
