"""Backends de test — ce qui rend la chaîne vérifiable sans réseau ni euro.

Sans eux, aucun test d'intégration du compilateur ne serait ni gratuit, ni
déterministe, ni exécutable en CI. Ils ne sont pas un artefact de test
secondaire : ils sont la preuve que l'architecture tient sa promesse
d'indépendance vis-à-vis des fournisseurs. Si un mock ne peut pas remplacer
un vrai backend, c'est que le métier connaît encore le fournisseur.

Ils **n'imitent pas la qualité** — un mock rend un fichier valide, pas une
belle vidéo. Ce qu'ils reproduisent fidèlement, ce sont les CONTRATS : les
durées, les coûts, les timings mot à mot, et les modes d'échec.
"""

from __future__ import annotations

from pathlib import Path

from pdz.backends.base import ArtefactRendu, EstimationCout, Validation
from pdz.contracts.capabilities import Capacite, ModeleCapacites
from pdz.contracts.communs import StatutCapacite
from pdz.contracts.render import RenderSpecExecutable


class BackendVideoMock:
    """Rend un fichier, note ce qu'on lui a demandé, ne facture rien.

    `echoue_sur` permet de reproduire un échec de fournisseur sans en
    provoquer un vrai — c'est ce qui rendra les tests de diagnostic et de
    réparation possibles en PHASES 15 et 16.
    """

    nom = "mock"

    def __init__(self, *, durees_s: tuple[int, ...] = (5, 10),
                 cout_par_seconde: float = 0.046, echoue_sur: str = ""):
        self.durees_s = durees_s
        self.cout_par_seconde = cout_par_seconde
        self.echoue_sur = echoue_sur
        self.appels: list[RenderSpecExecutable] = []

    def capabilities(self, profil: str = "equilibre") -> ModeleCapacites:
        return ModeleCapacites(
            modele="mock-video", fournisseur=self.nom, durees_s=self.durees_s,
            capacites=(
                Capacite(nom="image_to_video", statut=StatutCapacite.MESURE,
                         valeur=True, methode="mock"),
                # Volontairement INCONNU, comme le vrai : un mock qui
                # promettrait plus que fal.ai ferait passer des tests que la
                # production ne tiendrait pas.
                Capacite(nom="camera_control", statut=StatutCapacite.INCONNU),
            ),
        )

    def valider(self, spec: RenderSpecExecutable) -> Validation:
        bloquants = []
        if not spec.image_depart:
            bloquants.append("aucune image de départ")
        if spec.duree_s <= 0:
            bloquants.append(f"durée invalide : {spec.duree_s} s")
        if self.durees_s and spec.duree_s > max(self.durees_s):
            bloquants.append(f"{spec.duree_s} s > {max(self.durees_s)} s")
        return Validation(tuple(bloquants))

    def estimer(self, spec: RenderSpecExecutable) -> EstimationCout:
        return EstimationCout(eur=spec.duree_s * self.cout_par_seconde,
                              latence_ms=1, sur=True, detail="mock")

    def executer(self, spec: RenderSpecExecutable) -> ArtefactRendu:
        from pdz.moteur.erreurs import ErreurFournisseur

        self.appels.append(spec)
        if self.echoue_sur and self.echoue_sur in spec.shot_id:
            raise ErreurFournisseur(f"échec simulé sur {spec.shot_id}")

        destination = Path(spec.parametres["destination"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"\x00mock-video")
        return ArtefactRendu(
            fichier=destination, cout_eur=spec.duree_s * self.cout_par_seconde,
            latence_ms=1, modele="mock-video", fournisseur=self.nom,
        )


class BackendVoixMock:
    """Rend un fichier et des timings mot à mot PLAUSIBLES.

    Les timings sont répartis au prorata de la longueur des mots — une
    approximation, mais elle a la bonne FORME : durée totale cohérente,
    mots contigus, aucun chevauchement. C'est ce dont tout l'aval a besoin
    pour être testé (découpage, sous-titres, cohérence de durée).
    """

    nom = "mock"

    def __init__(self, *, secondes_par_caractere: float = 0.06):
        self.secondes_par_caractere = secondes_par_caractere
        self.appels: list[tuple[str, str]] = []

    def capabilities(self) -> ModeleCapacites:
        return ModeleCapacites(
            modele="mock-tts", fournisseur=self.nom,
            capacites=(
                Capacite(nom="text_to_speech", statut=StatutCapacite.MESURE, valeur=True),
                Capacite(nom="word_timestamps", statut=StatutCapacite.MESURE, valeur=True),
            ),
        )

    def voix_disponibles(self) -> list:
        return []

    def synthetiser(self, texte: str, sortie: Path, *, voice_id: str,
                    stabilite: float = 0.5, style: float = 0.4,
                    vitesse: float = 1.0) -> tuple[Path, list]:
        from pdz.video.soustitres import Mot

        self.appels.append((voice_id, texte))
        sortie.parent.mkdir(parents=True, exist_ok=True)
        sortie.write_bytes(b"\x00mock-audio")

        mots, curseur = [], 0.0
        for brut in texte.split():
            duree = max(0.12, len(brut) * self.secondes_par_caractere / max(vitesse, 0.1))
            mots.append(Mot(texte=brut, debut_ms=round(curseur * 1000),
                            fin_ms=round((curseur + duree) * 1000)))
            curseur += duree
        return sortie, mots


class BackendMusiqueMock:
    """Ne reconnaît rien par défaut — le cas le PLUS fréquent en vrai.

    Un mock qui reconnaîtrait toujours ferait passer des tests qui ne
    couvrent jamais le chemin « musique inconnue », lequel est justement
    celui que la production rencontre le plus souvent.
    """

    nom = "mock"

    def __init__(self, morceau=None):
        self.morceau = morceau
        self.appels: list[Path] = []

    def capabilities(self) -> ModeleCapacites:
        return ModeleCapacites(
            modele="mock-audio-id", fournisseur=self.nom,
            capacites=(Capacite(nom="identification_musicale",
                                statut=StatutCapacite.MESURE, valeur=True),),
        )

    def identifier(self, extrait: Path, *, job_id: str | None = None):
        self.appels.append(Path(extrait))
        return self.morceau
