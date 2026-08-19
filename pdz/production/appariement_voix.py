"""Retrouver, parmi les voix disponibles, celle qui ressemble à une voix donnée.

Le problème, posé simplement : j'entends une voix dans une vidéo, je veux la
même — ou la plus proche — pour mon personnage. ElevenLabs propose des
centaines de voix décrites par des mots (« warm », « narrative », « young »).
Ces mots ne permettent de choisir entre rien.

La méthode ici est directe, et c'est ce qui la rend fiable :

  1. **mesurer la voix cible** (pdz.analyse.voix) — hauteur, timbre, étendue,
     débit ;
  2. **faire dire la même phrase** à chaque voix candidate ;
  3. **mesurer les candidates exactement pareil** ;
  4. prendre la plus proche dans cet espace de mesures.

Comparer des mesures à des mesures, jamais une mesure à un adjectif. La phrase
sonde est identique pour tout le monde : sans ça, on comparerait autant les
textes que les voix.

Coût : environ 110 caractères par voix essayée, une seule fois — les sondes
sont mises en cache sur le disque. Douze candidates, c'est un millième du
quota mensuel gratuit.

⚠️ Cette page ne clone pas une voix, et ne le peut pas : elle **choisit** dans
un catalogue existant. Cloner la voix d'une personne réelle demande son
accord — ce n'est pas une limite technique, c'en est une tout court.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from pdz.analyse import voix as mesure_voix
from pdz.analyse.voix import ProfilVoix
from pdz.backends import backend_voix
from pdz.backends.base import VoixDisponible
from pdz.config import config
from pdz.moteur.erreurs import ErreurConfig, ErreurPdz
from pdz.univers import Univers

log = logging.getLogger(__name__)

# La phrase sonde. Ses qualités, dans l'ordre d'importance :
#   · elle contient les voyelles françaises usuelles (a, é, i, o, u, ou, an,
#     on, in) — le timbre mesuré ne dépend donc pas d'un son particulier ;
#   · elle alterne consonnes sourdes et sonores, ce qui donne des syllabes
#     bien découpées et un débit mesurable ;
#   · elle est neutre de ton : rien n'y invite à jouer la colère ou la joie,
#     ce qui fausserait l'étendue mélodique ;
#   · elle fait 108 caractères, soit environ 7 secondes — assez pour une
#     médiane stable, assez peu pour ne rien coûter.
PHRASE_SONDE = (
    "Bonjour, on tourne demain matin. J'ai relu tout le dossier, "
    "et franchement, ça change beaucoup de choses."
)

# Réglages neutres pour les sondes. On mesure la voix, pas l'interprétation :
# un `style` élevé ferait varier la mesure d'une voix à l'autre pour des
# raisons qui n'ont rien à voir avec son timbre.
SONDE_STABILITE = 0.5
SONDE_STYLE = 0.0
SONDE_VITESSE = 1.0


@dataclass
class Candidat:
    voix: VoixDisponible
    profil: ProfilVoix        # ce que la voix candidate fait naturellement
    cible: ProfilVoix         # ce qu'on cherche à obtenir
    distance: float
    fichier: Path

    def resume(self) -> str:
        return (f"{self.voix.nom:<22} d={self.distance:>5.2f}  "
                f"{self.profil.hauteur_hz:>5.0f} Hz  "
                f"timbre {self.profil.timbre_hz:>6.0f} Hz  "
                f"{self.profil.expressivite}")

    def reglages(self) -> dict[str, float]:
        """Les réglages à appliquer à CETTE voix pour approcher la cible.

        Le détail qui change tout : `stability` et `style` décrivent le jeu
        voulu, ils viennent donc de la **cible**. `speed`, lui, est une
        correction — il faut savoir de combien la candidate parle trop vite
        ou trop lentement, ce qui demande les deux mesures. Reprendre
        aveuglément la vitesse de la cible reviendrait à corriger une erreur
        qui n'existait pas.
        """
        voulu = self.cible.vers_reglages()
        naturel = self.profil.debit_syllabes_s

        if naturel > 0.5 and self.cible.debit_syllabes_s > 0.5:
            rapport = self.cible.debit_syllabes_s / naturel
        else:
            rapport = 1.0

        # ±25 % : au-delà, ElevenLabs étire la voix et ça s'entend.
        voulu["vitesse"] = round(float(min(1.25, max(0.75, rapport))), 2)
        return voulu


def profil_cible(source: Path, *, debut_s: float = 0.0,
                 duree_s: float = 30.0) -> ProfilVoix:
    """Mesure la voix à retrouver, à partir d'un fichier audio ou vidéo.

    `debut_s` sert quand plusieurs personnes parlent : on isole à l'oreille
    un passage où une seule s'exprime. Ce module ne sépare pas les locuteurs —
    le faire correctement demande un modèle de diarisation, et le faire mal
    donnerait une moyenne de deux voix, c'est-à-dire personne.
    """
    profil = mesure_voix.analyser(source, debut_s=debut_s, duree_max_s=duree_s)
    if profil.confiance < 0.4:
        log.warning(
            "Voix mesurée avec une confiance de %.2f : le passage est bruité "
            "ou mélange plusieurs locuteurs. Choisis un extrait plus propre "
            "avec --debut.", profil.confiance,
        )
    return profil


def _sonde(voix: VoixDisponible, dossier: Path) -> Path:
    """Fait dire la phrase sonde à une voix. Une seule fois dans la vie."""
    fichier = dossier / f"{voix.id}.mp3"
    if fichier.exists() and fichier.stat().st_size > 1000:
        return fichier

    backend_voix().synthetiser(
        PHRASE_SONDE, fichier, voice_id=voix.id,
        stabilite=SONDE_STABILITE, style=SONDE_STYLE, vitesse=SONDE_VITESSE,
    )
    return fichier


def apparier(cible: ProfilVoix, *, langue: str = "fr", maximum: int = 12,
             exclure: set[str] | None = None,
             poids: np.ndarray | None = None) -> list[Candidat]:
    """Classe les voix disponibles de la plus proche à la plus lointaine.

    `maximum` borne la dépense : chaque candidate coûte une synthèse. Les
    candidates sont pré-triées sur ce qu'on peut savoir gratuitement (langue
    et genre annoncés par le catalogue), puis mesurées pour de vrai.
    """
    disponibles = backend_voix().voix_disponibles()
    if not disponibles:
        raise ErreurConfig(
            "Aucune voix dans ton compte ElevenLabs. Ajoute-en depuis "
            "elevenlabs.io → Voices → Voice Library."
        )

    exclure = exclure or set()
    retenues = [v for v in disponibles if v.id not in exclure]

    # Pré-tri gratuit : la langue annoncée, puis le genre déduit de la hauteur
    # cible. Ce n'est qu'un ordre de passage — aucune voix n'est écartée sur
    # cette base, elles sont seulement essayées plus tard.
    genre_probable = "male" if cible.hauteur_hz < 165 else "female"

    def priorite(v: VoixDisponible) -> tuple[int, int]:
        bonne_langue = 0 if (not v.langue or langue in v.langue.lower()) else 1
        bon_genre = 0 if (not v.genre or genre_probable in v.genre.lower()) else 1
        return (bonne_langue, bon_genre)

    retenues.sort(key=priorite)
    retenues = retenues[:maximum]

    dossier = config().dossier_cache / "sondes_voix"
    dossier.mkdir(parents=True, exist_ok=True)

    candidats: list[Candidat] = []
    for v in retenues:
        try:
            fichier = _sonde(v, dossier)
            profil = mesure_voix.analyser(fichier)
        except ErreurPdz as e:
            # Une voix qui échoue ne doit pas faire tomber tout l'appariement :
            # il en reste onze.
            log.warning("Voix « %s » écartée : %s", v.nom, e)
            continue
        candidats.append(Candidat(
            voix=v, profil=profil, cible=cible,
            distance=_distance(cible, profil, poids), fichier=fichier,
        ))

    if not candidats:
        raise ErreurPdz(
            "Aucune voix n'a pu être mesurée. Vérifie ta clé ElevenLabs et "
            "ton quota de caractères (`pdz cles`)."
        )

    candidats.sort(key=lambda c: c.distance)
    return candidats


def _distance(cible: ProfilVoix, candidat: ProfilVoix,
              poids: np.ndarray | None) -> float:
    if poids is None:
        return cible.distance(candidat)
    ecart = np.abs(cible.vecteur() - candidat.vecteur())
    return round(float(np.sqrt(((ecart * poids) ** 2).sum())), 3)


# Quand on n'a pas d'audio de référence — seulement une voix *devinée* à partir
# de l'image — seule la hauteur a du sens. Les autres axes sont neutralisés
# plutôt que devinés : une hypothèse fausse pèse plus lourd qu'une absence.
POIDS_HAUTEUR_SEULE = np.array([1.0, 0.0, 0.0, 0.0])


# Hauteur indicative par registre, en hertz. Bornes de la phonétique usuelle.
HAUTEUR_PAR_REGISTRE = {
    "tres_grave": 95.0, "très grave": 95.0,
    "grave": 125.0,
    "medium": 165.0, "médium": 165.0,
    "aigu": 210.0,
    "tres_aigu": 265.0, "très aigu": 265.0,
}


def hauteur_attendue(personnage, rang: int, total: int) -> float:
    """Quelle hauteur viser pour ce personnage, faute d'audio à mesurer.

    Deux cas. Si l'univers porte un registre — inscrit par l'analyse d'une
    vidéo, ou à la main — on le suit. Sinon on **étale** les personnages sur
    l'étendue de la voix parlée.

    L'étalement n'est pas de la coquetterie : sans lui, tous les personnages
    visent la même hauteur, obtiennent des voix voisines, et le dialogue
    devient impossible à suivre. Une répartition arbitraire mais distincte
    vaut mieux qu'une convergence involontaire.
    """
    registre = (getattr(personnage.voix, "registre_percu", "") or "").strip()
    if registre in HAUTEUR_PAR_REGISTRE:
        return HAUTEUR_PAR_REGISTRE[registre]

    if total <= 1:
        return 165.0
    return 115.0 + (250.0 - 115.0) * rang / (total - 1)


def profil_suppose(hauteur_hz: float) -> ProfilVoix:
    """Fabrique une cible à partir d'une seule hauteur estimée.

    À n'utiliser qu'avec `POIDS_HAUTEUR_SEULE` : les autres champs sont des
    valeurs de remplissage, pas des mesures, et le nom du profil le dit —
    sa confiance vaut 0.
    """
    return ProfilVoix(
        hauteur_hz=hauteur_hz, hauteur_p10=hauteur_hz * 0.85,
        hauteur_p90=hauteur_hz * 1.18, etendue_demi_tons=6.0,
        stabilite_hz=1.5, timbre_hz=1500.0, debit_syllabes_s=5.0,
        ratio_parole=0.7, dynamique_db=6.0, voisement=0.35,
        duree_s=0.0, confiance=0.0,
    )


def attribuer(univers: Univers, cibles: dict[str, ProfilVoix], *,
              maximum: int = 12) -> dict[str, Candidat]:
    """Donne une voix **différente** à chaque personnage.

    Le point qui compte : deux personnages ne peuvent pas recevoir la même
    voix, même si c'est la meilleure pour les deux. Un dialogue où les deux
    interlocuteurs ont la même voix est inécoutable — l'auditeur ne sait plus
    qui parle, et aucune qualité de synthèse ne rattrape ça.

    L'attribution est faite du personnage le **plus contraint** au moins
    contraint : celui dont la meilleure voix est nettement meilleure que sa
    deuxième choisit en premier. Servir dans l'ordre du casting donnerait au
    premier une voix qui convenait mieux à un autre.
    """
    classements = {
        pid: apparier(
            cible, langue=univers.langue, maximum=maximum,
            poids=POIDS_HAUTEUR_SEULE if cible.confiance == 0 else None,
        )
        for pid, cible in cibles.items()
    }

    def urgence(pid: str) -> float:
        liste = classements[pid]
        if len(liste) < 2:
            return 0.0
        return liste[1].distance - liste[0].distance   # ce qu'on perd à céder

    attribue: dict[str, Candidat] = {}
    prises: set[str] = set()

    for pid in sorted(classements, key=urgence, reverse=True):
        for candidat in classements[pid]:
            if candidat.voix.id not in prises:
                attribue[pid] = candidat
                prises.add(candidat.voix.id)
                break
        else:
            raise ErreurPdz(
                f"Plus de voix libre pour « {pid} » : {len(prises)} déjà "
                f"attribuées. Augmente --maximum ou ajoute des voix à ton "
                "compte ElevenLabs."
            )
    return attribue


def appliquer(univers: Univers, attribue: dict[str, Candidat],
              chemin: Path | None = None) -> Univers:
    """Écrit les voix retenues dans l'univers, réglages compris."""
    for pid, candidat in attribue.items():
        perso = univers.personnage(pid)
        if perso is None:
            raise ErreurPdz(f"Personnage « {pid} » absent de l'univers.")

        reglages = candidat.reglages()
        perso.voix.voice_id = candidat.voix.id
        perso.voix.stabilite = reglages["stabilite"]
        perso.voix.style = reglages["style"]
        perso.voix.vitesse = reglages["vitesse"]
        log.info("%s → %s (écart %.2f)", perso.nom, candidat.voix.nom,
                 candidat.distance)

    if chemin is not None:
        univers.sauver(chemin)
    return univers
