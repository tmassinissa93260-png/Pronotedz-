"""Analyse de la **musique** d'une vidéo : la mesurer, et l'identifier.

Deux choses différentes, et il faut les séparer parce qu'elles n'ont ni le
même coût ni la même fiabilité :

  · **mesurer** la musique — tempo, tonalité, énergie, où elle joue seule.
    Local, gratuit, exact. Marche toujours, y compris sur une musique
    obscure ou faite maison.
  · **l'identifier** — « c'est *Sunset Drive* de Machinedrum ». Ça demande
    une base d'empreintes de dizaines de millions de titres, donc un service
    extérieur (`pdz.ia.audd`). Ça coûte un demi-centime et ça échoue parfois.

Le module rend toujours les mesures. L'identification vient en plus quand
elle marche. Une commande qui ne dit rien parce que le titre est introuvable
serait inutile : le tempo et la tonalité, eux, suffisent déjà à retrouver une
musique libre de droits qui sonne pareil.

## Le point qui change tout : isoler la musique de la voix

Un service de reconnaissance à qui on envoie « voix + musique » se trompe
beaucoup plus souvent. Ici, on repère d'abord les passages où **personne ne
parle**, et on n'envoie que ceux-là. C'est gratuit, ça ne demande aucun modèle
de séparation de sources, et ça règle l'essentiel du problème : dans un format
court, il y a presque toujours une intro ou une fin sans parole.

Reste à savoir reconnaître la parole. Le détecteur de voisement de
`pdz.analyse.voix` **ne convient pas** ici, et c'est mesuré : un accord tenu
est parfaitement périodique, sa fondamentale tombe dans le domaine de la voix
parlée, et il est donc déclaré « voisé ». Sur une musique mélodique, ce
détecteur ne trouve aucun passage instrumental — il les voit tous comme de la
parole.

Le critère retenu est celui de la discrimination parole/musique classique :
**l'énergie de modulation autour de 4 Hz**. La parole ouvre et ferme la bouche
au rythme des syllabes, entre 3 et 7 fois par seconde ; son enveloppe
d'énergie porte donc un pic marqué dans cette bande. La musique, elle, module
au rythme de la mesure — 2 Hz à 120 BPM — ou pas du tout sur une nappe tenue.
Un seul nombre par fenêtre d'une seconde suffit à les séparer.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from pdz.analyse.son import pcm
from pdz.analyse.voix import TAILLE_TRAME, _trames
from pdz.moteur.erreurs import ErreurPdz

log = logging.getLogger(__name__)

TAUX = 22050

# Les douze noms de notes, dans l'ordre des classes de hauteur.
NOTES = ["Do", "Do#", "Ré", "Ré#", "Mi", "Fa", "Fa#", "Sol", "Sol#",
         "La", "La#", "Si"]

# Profils de Krumhansl-Kessler : la « signature » d'une gamme majeure et
# d'une gamme mineure, mesurée expérimentalement sur des auditeurs. On
# corrèle le chroma de la musique aux douze rotations de chacun ; la
# meilleure corrélation donne la tonalité.
PROFIL_MAJEUR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
                          2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
PROFIL_MINEUR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
                          2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

# Un passage instrumental plus court que ça ne sert à rien : ni pour écouter,
# ni pour une empreinte de reconnaissance.
DUREE_MIN_INSTRUMENTAL_S = 1.5

# ── Réglages de la discrimination parole / musique ──────────────────────
# L'enveloppe est échantillonnée à 100 Hz : largement assez pour observer
# des modulations de 20 Hz, et 220 fois plus léger que le signal brut.
ENVELOPPE_HZ = 100

# Une seconde de contexte pour décider. En dessous, on n'a pas assez de
# périodes de 4 Hz pour que la mesure veuille dire quelque chose.
FENETRE_DECISION_S = 1.0
PAS_DECISION_S = 0.25

# La bande des syllabes. Le français parlé tient autour de 5 syllabes par
# seconde ; 3 à 7 Hz couvre du débit lent au débit pressé.
BANDE_PAROLE = (3.0, 7.0)
BANDE_TOTALE = (0.5, 20.0)

# Seuil de repli, quand la vidéo est homogène et qu'il n'y a rien à séparer.
# Mesuré sur des signaux à cadence connue : la musique seule tombe entre 0,43
# et 0,46 quel que soit son tempo, la parole entre 0,51 et 0,66 selon le débit.
SEUIL_PAROLE = 0.50

# En dessous de cet écart entre le bas et le haut de la distribution, la
# vidéo ne contient qu'une seule chose : découper serait inventer une
# frontière là où il n'y en a pas.
ECART_MINIMAL = 0.10

# Un passage plus court que la fenêtre de décision n'est pas une observation,
# c'est une hésitation entre deux fenêtres voisines.
DUREE_MIN_PASSAGE_S = 0.8


@dataclass
class Passage:
    """Un morceau de la piste où personne ne parle."""

    debut_s: float
    fin_s: float
    energie: float

    @property
    def duree_s(self) -> float:
        return self.fin_s - self.debut_s


@dataclass
class AnalyseMusique:
    """Ce qu'on sait de la musique, mesuré."""

    tempo_bpm: float | None
    confiance_tempo: float
    tonalite: str                    # « Fa# mineur », ou « indéterminée »
    confiance_tonalite: float
    energie_musique: float           # 0-1, niveau de la musique seule
    part_instrumentale: float        # part de la vidéo sans parole
    passages: list[Passage] = field(default_factory=list)
    y_a_de_la_musique: bool = True
    duree_s: float = 0.0
    # Écart mesuré entre les fenêtres parlées et les fenêtres instrumentales.
    # Faible = la séparation n'est pas nette, les passages sont à prendre
    # avec précaution.
    separation: float = 0.0

    @property
    def meilleur_passage(self) -> Passage | None:
        """Le passage instrumental le plus utile pour une reconnaissance.

        Le plus long d'abord, l'énergie ensuite : une empreinte a besoin de
        durée avant d'avoir besoin de volume.
        """
        assez_longs = [p for p in self.passages
                       if p.duree_s >= DUREE_MIN_INSTRUMENTAL_S]
        if not assez_longs:
            return max(self.passages, key=lambda p: p.duree_s, default=None)
        return max(assez_longs, key=lambda p: (round(p.duree_s, 1), p.energie))

    def resume(self) -> str:
        if not self.y_a_de_la_musique:
            return "aucune musique détectée sous la voix"
        tempo = (f"{self.tempo_bpm:.0f} BPM (confiance {self.confiance_tempo:.2f})"
                 if self.tempo_bpm else "tempo indéterminé")
        doute = ("  ⚠ séparation parole/musique peu nette"
                 if self.separation and self.separation < ECART_MINIMAL else "")
        return (f"{tempo} · tonalité {self.tonalite} "
                f"(confiance {self.confiance_tonalite:.2f}) · "
                f"{len(self.passages)} passage(s) sans parole "
                f"({self.part_instrumentale:.0%} de la vidéo){doute}")

    def pour_chercher_une_musique_libre(self) -> str:
        """Ce qu'il faut taper sur une banque de musique libre de droits.

        Utile même quand l'identification échoue — et c'est justement là
        qu'elle sert : on ne peut pas réutiliser un titre commercial dans une
        vidéo monétisée, mais on peut en chercher un qui sonne pareil.
        """
        morceaux = []
        if self.tempo_bpm:
            morceaux.append(f"{self.tempo_bpm:.0f} BPM")
        if self.confiance_tonalite > 0.5 and self.tonalite != "indéterminée":
            morceaux.append(self.tonalite)
        if self.energie_musique > 0.55:
            morceaux.append("énergique")
        elif self.energie_musique < 0.25:
            morceaux.append("calme, ambiance")
        return " · ".join(morceaux) or "aucun critère fiable"


# ── Séparer les moments parlés des moments instrumentaux ─────────────────

def enveloppe(signal: np.ndarray) -> np.ndarray:
    """Courbe d'énergie échantillonnée à 100 Hz — le support de la mesure."""
    taille = max(1, int(TAUX / ENVELOPPE_HZ))
    n = signal.size // taille
    if n == 0:
        return np.zeros(0)
    trames = signal[: n * taille].reshape(n, taille)
    return np.sqrt((trames ** 2).mean(axis=1))


def taux_modulation_parole(bloc: np.ndarray) -> float:
    """Part de l'énergie de modulation qui tombe dans la bande syllabique.

    Proche de 1 : ça module au rythme des syllabes, c'est de la parole.
    Proche de 0 : ça module au rythme de la mesure, ou pas du tout.
    """
    if bloc.size < 16:
        return 0.0

    centre = bloc - bloc.mean()
    if not np.any(centre):
        return 0.0

    spectre = np.abs(np.fft.rfft(centre * np.hanning(centre.size)))
    freqs = np.fft.rfftfreq(centre.size, 1.0 / ENVELOPPE_HZ)

    dans_bande = (freqs >= BANDE_PAROLE[0]) & (freqs <= BANDE_PAROLE[1])
    dans_total = (freqs >= BANDE_TOTALE[0]) & (freqs <= BANDE_TOTALE[1])

    total = float(spectre[dans_total].sum())
    if total <= 0:
        return 0.0
    return float(spectre[dans_bande].sum()) / total


def seuil_adaptatif(taux: np.ndarray) -> tuple[float, float]:
    """Calibre le seuil parole/musique **sur la vidéo elle-même**.

    Il n'existe pas de bon seuil universel, et c'est mesuré : de la musique
    seule donne 0,43 à 0,46 selon son tempo, de la parole 0,51 à 0,66 selon
    son débit. Un seuil fixe placé au milieu se trompe sur les extrêmes.

    Sur une vidéo qui contient les deux, la distribution est à deux bosses :
    on coupe entre elles. Sur une vidéo homogène — que de la parole, ou que
    de la musique — il n'y a pas de frontière à trouver, et en inventer une
    couperait le fichier en deux au hasard. On retombe alors sur le seuil de
    référence, et l'écart mesuré sert de confiance.

    Renvoie (seuil, écart). Un écart faible veut dire « je ne sais pas
    séparer », pas « il n'y a rien à séparer ».
    """
    if taux.size < 4:
        return SEUIL_PAROLE, 0.0

    bas, haut = float(np.percentile(taux, 20)), float(np.percentile(taux, 80))
    ecart = haut - bas
    if ecart < ECART_MINIMAL:
        return SEUIL_PAROLE, round(ecart, 3)
    return (bas + haut) / 2, round(ecart, 3)


def passages_sans_parole(signal: np.ndarray, *, marge_s: float = 0.15,
                         seuil: float | None = None) -> tuple[list[Passage], float]:
    """Repère les fenêtres où il y a du son mais **pas de parole**.

    Renvoie (passages, écart de séparation). La marge retire un peu de chaque
    bord : la fin d'un mot déborde toujours sur la fenêtre suivante, et on ne
    veut pas de reste de parole dans l'extrait envoyé à la reconnaissance.
    """
    env = enveloppe(signal)
    if env.size == 0:
        return [], 0.0

    largeur = min(int(FENETRE_DECISION_S * ENVELOPPE_HZ), env.size)
    pas = max(1, int(PAS_DECISION_S * ENVELOPPE_HZ))

    instants, blocs = [], []
    for debut in range(0, max(1, env.size - largeur + 1), pas):
        instants.append(debut / ENVELOPPE_HZ)
        blocs.append(env[debut:debut + largeur])

    taux = np.array([taux_modulation_parole(b) for b in blocs])
    seuil_retenu, ecart = (seuil, 0.0) if seuil is not None else seuil_adaptatif(taux)

    seuil_audible = max(float(np.median(env)) * 0.25, 1e-4)
    brut = np.array([
        float(b.mean()) > seuil_audible and t <= seuil_retenu
        for b, t in zip(blocs, taux, strict=True)
    ])

    # Lissage par vote majoritaire sur trois fenêtres. Une seule fenêtre
    # ambiguë au milieu d'un passage parlé — une respiration, une fin de
    # phrase — ouvrirait sinon un faux passage instrumental d'une seconde.
    lisse = _vote_majoritaire(brut)

    decisions = [
        (instant, bool(dedans), float(bloc.mean()))
        for instant, dedans, bloc in zip(instants, lisse, blocs, strict=True)
    ]
    return _assembler_passages(decisions, marge_s), ecart


def _vote_majoritaire(valeurs: np.ndarray, largeur: int = 3) -> np.ndarray:
    if valeurs.size < largeur:
        return valeurs
    noyau = np.ones(largeur)
    somme = np.convolve(valeurs.astype(float), noyau, mode="same")
    presents = np.convolve(np.ones_like(valeurs, dtype=float), noyau, mode="same")
    return somme > presents / 2


def _assembler_passages(decisions: list[tuple[float, bool, float]],
                        marge_s: float) -> list[Passage]:
    """Recolle les fenêtres instrumentales voisines en passages continus.

    Les bornes sont **prudentes**. Une fenêtre qui commence en `t` parle de
    l'intervalle [t, t+1 s], mais la fenêtre suivante commence en t+0,25 s et
    peut, elle, être parlée. Étendre le passage jusqu'à t+1 s ferait donc
    déborder de trois quarts de seconde sur la parole — et ce reste de voix
    part ensuite à la reconnaissance, qui échoue.
    """
    passages: list[Passage] = []
    debut: float | None = None
    dernier: float = 0.0
    energies: list[float] = []

    for instant, instrumental, energie in decisions:
        if instrumental:
            if debut is None:
                debut, energies = instant, []
            dernier = instant
            energies.append(energie)
        elif debut is not None:
            passages.append(_passage(debut, dernier + PAS_DECISION_S,
                                     energies, marge_s))
            debut, energies = None, []

    if debut is not None:
        # Le dernier passage va jusqu'au bout du fichier : là, rien ne suit
        # qui puisse déborder, la fenêtre entière est acquise.
        passages.append(_passage(debut, dernier + FENETRE_DECISION_S,
                                 energies, marge_s))

    return _fusionner([p for p in passages if p.duree_s >= DUREE_MIN_PASSAGE_S])


def _fusionner(passages: list[Passage], ecart_max_s: float = 0.5) -> list[Passage]:
    """Recolle deux passages séparés par un trou plus court qu'une respiration."""
    if not passages:
        return []

    fusionnes = [passages[0]]
    for suivant in passages[1:]:
        precedent = fusionnes[-1]
        if suivant.debut_s - precedent.fin_s <= ecart_max_s:
            fusionnes[-1] = Passage(
                debut_s=precedent.debut_s,
                fin_s=suivant.fin_s,
                energie=round((precedent.energie + suivant.energie) / 2, 4),
            )
        else:
            fusionnes.append(suivant)
    return fusionnes


def _passage(debut_s: float, fin_s: float, energies: list[float],
             marge_s: float) -> Passage:
    debut = debut_s + marge_s
    fin = max(debut, fin_s - marge_s)
    return Passage(
        debut_s=round(debut, 3),
        fin_s=round(fin, 3),
        energie=round(float(np.mean(energies)) if energies else 0.0, 4),
    )


# ── Tonalité ─────────────────────────────────────────────────────────────

def chroma(signal: np.ndarray) -> np.ndarray:
    """Répartit l'énergie du signal sur les douze notes de la gamme.

    On somme l'énergie de chaque fréquence dans la classe de hauteur qui lui
    correspond — un La à 220 Hz et un La à 440 Hz comptent tous deux comme
    « La ». C'est ce repliement qui rend la mesure indépendante de l'octave,
    donc de l'arrangement.
    """
    trames = _trames(signal)
    if trames.size == 0:
        return np.zeros(12)

    fenetre = np.hanning(TAILLE_TRAME).astype(np.float32)
    spectre = np.abs(np.fft.rfft(trames * fenetre, axis=1))
    freqs = np.fft.rfftfreq(TAILLE_TRAME, 1.0 / TAUX)

    # 65 Hz à 2 000 Hz : en dessous la résolution fréquentielle ne suffit plus
    # à distinguer deux demi-tons, au-dessus on ne capte que des harmoniques.
    utile = (freqs > 65.0) & (freqs < 2000.0)
    freqs, spectre = freqs[utile], spectre[:, utile]

    # Numéro MIDI, puis classe de hauteur. 69 = La 440.
    midi = 69 + 12 * np.log2(freqs / 440.0)
    classes = np.round(midi).astype(int) % 12

    energie = spectre.sum(axis=0)
    resultat = np.zeros(12)
    for c in range(12):
        resultat[c] = energie[classes == c].sum()

    total = resultat.sum()
    return resultat / total if total > 0 else resultat


def tonalite(chroma_mesure: np.ndarray) -> tuple[str, float]:
    """Corrèle le chroma aux 24 tonalités possibles. Renvoie (nom, confiance).

    La confiance est l'écart entre la meilleure corrélation et la deuxième.
    C'est plus honnête que la corrélation brute : un chroma plat corrèle
    correctement avec tout, et une confiance basse le dit.
    """
    if not chroma_mesure.any():
        return "indéterminée", 0.0

    scores: list[tuple[float, str]] = []
    for tonique in range(12):
        for profil, mode in ((PROFIL_MAJEUR, "majeur"), (PROFIL_MINEUR, "mineur")):
            tourne = np.roll(profil, tonique)
            correlation = float(np.corrcoef(chroma_mesure, tourne)[0, 1])
            if not np.isnan(correlation):
                scores.append((correlation, f"{NOTES[tonique]} {mode}"))

    if not scores:
        return "indéterminée", 0.0

    scores.sort(reverse=True)
    meilleur, second = scores[0], scores[1] if len(scores) > 1 else (0.0, "")
    confiance = round(min(1.0, max(0.0, (meilleur[0] - second[0]) * 4.0)), 2)
    return meilleur[1], confiance


# ── Analyse complète ─────────────────────────────────────────────────────

def analyser(chemin: Path) -> AnalyseMusique:
    """Mesure la musique d'une vidéo ou d'un fichier audio. Aucun coût."""
    chemin = Path(chemin)
    if not chemin.exists():
        raise ErreurPdz(f"Fichier introuvable : {chemin}")

    signal = pcm(chemin, TAUX)
    if signal.size < TAILLE_TRAME * 4:
        raise ErreurPdz(f"{chemin.name} : piste audio trop courte.")

    duree = signal.size / TAUX
    passages, separation = passages_sans_parole(signal)
    part = sum(p.duree_s for p in passages) / max(0.001, duree)

    # La tonalité et le tempo se mesurent sur la musique SEULE quand on en a
    # assez : mesurés sur la voix, ils décrivent la voix.
    echantillon = _concatener(signal, passages) if part > 0.12 else signal
    chroma_mesure = chroma(echantillon)
    nom_tonalite, confiance_tonalite = tonalite(chroma_mesure)

    tempo_bpm, confiance_tempo = _tempo(echantillon)

    energie = float(np.sqrt((echantillon ** 2).mean())) if echantillon.size else 0.0
    # Rapporté au niveau global : une musique deux fois moins forte que la
    # voix reste de la musique, il ne s'agit pas de mesurer le volume absolu.
    reference = float(np.sqrt((signal ** 2).mean())) or 1e-9

    # Décider s'il y a de la musique du tout. Une piste de voix seule laisse
    # bien des trames non voisées — consonnes, respirations — mais elles sont
    # brèves et sans structure harmonique : le chroma y est plat.
    y_a_musique = bool(
        passages
        and part > 0.04
        and float(chroma_mesure.max()) > 0.11      # 0,083 = parfaitement plat
    )

    return AnalyseMusique(
        tempo_bpm=tempo_bpm,
        confiance_tempo=confiance_tempo,
        tonalite=nom_tonalite if y_a_musique else "indéterminée",
        confiance_tonalite=confiance_tonalite if y_a_musique else 0.0,
        energie_musique=round(min(1.0, energie / reference), 3),
        part_instrumentale=round(part, 3),
        passages=passages,
        y_a_de_la_musique=y_a_musique,
        duree_s=round(duree, 2),
        separation=separation,
    )


def _concatener(signal: np.ndarray, passages: list[Passage]) -> np.ndarray:
    morceaux = [signal[int(p.debut_s * TAUX):int(p.fin_s * TAUX)] for p in passages]
    morceaux = [m for m in morceaux if m.size > 0]
    return np.concatenate(morceaux) if morceaux else signal


def _tempo(signal: np.ndarray) -> tuple[float | None, float]:
    """Tempo par autocorrélation de la fonction d'attaque.

    Même principe que `pdz.analyse.son`, mais appliqué à la musique isolée :
    sur un mélange voix + musique, les attaques de la parole polluent la
    mesure et le tempo trouvé est celui du débit, pas celui du morceau.
    """
    taille = max(1, int(TAUX * 0.025))
    n = signal.size // taille
    if n < 40:
        return None, 0.0

    trames = signal[: n * taille].reshape(n, taille)
    rms = np.sqrt((trames ** 2).mean(axis=1))
    fenetre_s = taille / TAUX

    attaque = np.maximum(np.diff(rms, prepend=rms[0]), 0)
    attaque = attaque - attaque.mean()
    if not np.any(attaque):
        return None, 0.0

    corr = np.correlate(attaque, attaque, mode="full")[attaque.size - 1:]
    if corr[0] <= 0:
        return None, 0.0
    corr = corr / corr[0]

    lag_min = max(1, int(60.0 / 200.0 / fenetre_s))
    lag_max = min(corr.size - 1, int(60.0 / 60.0 / fenetre_s))
    if lag_max <= lag_min:
        return None, 0.0

    zone = corr[lag_min:lag_max]
    lag = int(np.argmax(zone)) + lag_min
    pic = float(zone.max())
    return round(60.0 / (lag * fenetre_s), 1), round(max(0.0, min(1.0, pic)), 2)


# ── Extraire l'échantillon à envoyer à la reconnaissance ─────────────────

def extraire_echantillon(chemin: Path, destination: Path,
                         analyse: AnalyseMusique, *,
                         duree_max_s: float = 12.0) -> tuple[Path, str]:
    """Découpe le meilleur bout à faire écouter. Renvoie (fichier, raison).

    Trois cas, du meilleur au moins bon :
      1. un passage instrumental assez long → la reconnaissance a toutes ses
         chances ;
      2. un passage instrumental court → on l'envoie quand même, en le disant ;
      3. aucun passage → on prend le milieu de la vidéo, voix comprise. Le
         taux d'échec monte nettement, et l'appel reste facturé.
    """
    passage = analyse.meilleur_passage

    if passage is not None and passage.duree_s >= DUREE_MIN_INSTRUMENTAL_S:
        debut, duree = passage.debut_s, min(duree_max_s, passage.duree_s)
        raison = f"passage sans parole de {passage.duree_s:.1f} s à {debut:.1f} s"
    elif passage is not None:
        debut, duree = passage.debut_s, max(3.0, passage.duree_s)
        raison = (f"seulement {passage.duree_s:.1f} s sans parole — "
                  "la reconnaissance peut échouer")
    else:
        debut = max(0.0, analyse.duree_s / 2 - duree_max_s / 2)
        duree = min(duree_max_s, analyse.duree_s)
        raison = ("aucun passage sans parole : la voix part avec la musique, "
                  "l'identification est nettement moins fiable")

    destination.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-ss", f"{debut:.3f}", "-i", str(chemin), "-t", f"{duree:.3f}",
         "-vn", "-ac", "1", "-ar", "44100", "-b:a", "128k", str(destination)],
        capture_output=True, text=True, timeout=120,
    )
    if r.returncode != 0 or not destination.exists():
        raise ErreurPdz(f"Extraction de l'échantillon impossible :\n{r.stderr[-400:]}")
    return destination, raison


# ── Mesurer, puis identifier ─────────────────────────────────────────────

@dataclass
class Resultat:
    """Ce que rend la commande : les mesures, et le titre si on l'a."""

    analyse: AnalyseMusique
    morceau: object | None = None        # pdz.ia.audd.Morceau
    extrait: Path | None = None
    raison_extrait: str = ""
    echec_identification: str = ""

    @property
    def identifie(self) -> bool:
        return self.morceau is not None


def reconnaitre(chemin: Path, *, dossier: Path | None = None,
                identifier: bool = True,
                job_id: str | None = None) -> Resultat:
    """Mesure la musique, puis tente de l'identifier.

    L'ordre est le point du module. On mesure **toujours** — c'est gratuit et
    ça ne peut pas échouer. On identifie ensuite, et seulement si on a trouvé
    un passage exploitable : envoyer un extrait plein de voix, c'est payer
    pour un échec probable.

    Une identification qui rate n'est pas une erreur : la réponse contient
    alors les mesures et la raison, pas une exception.
    """
    analyse = analyser(chemin)

    resultat = Resultat(analyse=analyse)
    if not identifier:
        return resultat

    if not analyse.y_a_de_la_musique:
        resultat.echec_identification = (
            "Aucune musique détectée : rien à identifier, et l'appel aurait "
            "été facturé pour rien."
        )
        return resultat

    chemin = Path(chemin)
    dossier = dossier or chemin.parent
    extrait, raison = extraire_echantillon(
        chemin, dossier / f"_extrait_{chemin.stem}.mp3", analyse
    )
    resultat.extrait, resultat.raison_extrait = extrait, raison

    from pdz.ia import audd
    from pdz.moteur.erreurs import ErreurPdz as _Erreur

    try:
        resultat.morceau = audd.identifier(extrait, job_id=job_id)
        if resultat.morceau is None:
            resultat.echec_identification = (
                "Morceau absent de la base AudD. C'est le cas le plus courant "
                "pour une musique libre de droits ou faite maison — les "
                "mesures ci-dessus restent valables."
            )
    except _Erreur as e:
        # Une identification impossible ne doit pas emporter les mesures :
        # elles sont le vrai contenu de la commande.
        resultat.echec_identification = f"{e.categorie} — {e}"
        log.info("Identification impossible : %s", e)

    return resultat
