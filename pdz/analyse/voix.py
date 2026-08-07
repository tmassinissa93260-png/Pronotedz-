"""Analyse **de la voix** : mesurer une voix pour pouvoir la retrouver.

But : à partir d'un extrait audio, obtenir une fiche chiffrée de la voix —
sa hauteur, son timbre, son débit, son expressivité — pour ensuite choisir
automatiquement, parmi les voix ElevenLabs disponibles, celle qui en est la
plus proche, et régler ses paramètres au bon endroit.

Aucun modèle d'IA ici, aucun coût : c'est du traitement du signal. Et c'est
volontaire — un modèle à qui on demande « décris cette voix » répond « voix
masculine chaleureuse », ce qui ne permet de choisir entre rien. Une hauteur
médiane de 112 Hz et un centroïde de 1 480 Hz, si.

Les cinq mesures, et ce qu'elles pilotent :

  · **hauteur (f0)** — grave ou aiguë. C'est le critère n°1 de ressemblance.
  · **étendue mélodique** — combien de demi-tons la voix parcourt. C'est ce
    qui sépare une lecture plate d'un jeu expressif → règle `style`.
  · **timbre (centroïde spectral)** — voix sombre et ronde, ou claire et
    nasillarde. Deux voix de même hauteur peuvent être très différentes ici.
  · **débit syllabique** — syllabes par seconde, comptées sur l'enveloppe
    d'énergie → règle `vitesse`.
  · **stabilité** — dispersion de la hauteur trame à trame → règle `stabilite`.

⚠️ Limite honnête : ces cinq nombres décrivent la voix, ils ne l'identifient
pas. Deux voix proches sur ces axes se ressemblent ; elles ne sont pas la même
personne, et ce module ne cherche pas à cloner qui que ce soit. Cloner la voix
d'une personne réelle sans son accord n'est pas un problème technique, c'en est
un tout court — voir docs/13-les-formats.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from pdz.analyse.son import pcm
from pdz.moteur.erreurs import ErreurPdz

TAUX = 22050

# Fenêtre de 46 ms : il faut au moins deux périodes de la voix la plus grave
# (70 Hz → 14,3 ms) pour que l'autocorrélation ait un sens.
TAILLE_TRAME = 1024
PAS_TRAME = 256

# Domaine de la voix parlée. En dehors, ce n'est pas de la parole : c'est du
# bruit de fond en dessous, de la musique ou du sifflement au-dessus.
F0_MIN, F0_MAX = 70.0, 350.0

# Une trame est déclarée voisée au-dessus de ce pic d'autocorrélation.
# 0,32 : au-dessous on attrape du souffle, au-dessus on perd les fins de mots.
SEUIL_VOISEMENT = 0.32


@dataclass
class ProfilVoix:
    """La carte d'identité mesurable d'une voix."""

    hauteur_hz: float             # f0 médiane des trames voisées
    hauteur_p10: float
    hauteur_p90: float
    etendue_demi_tons: float      # p90/p10 exprimé en demi-tons
    stabilite_hz: float           # écart-type de f0, en demi-tons

    timbre_hz: float              # centroïde spectral moyen
    debit_syllabes_s: float
    ratio_parole: float           # part de l'extrait réellement parlée
    dynamique_db: float           # écart-type de l'énergie, en dB

    voisement: float              # part de trames voisées : la confiance brute
    duree_s: float
    confiance: float = 1.0

    # ── Lectures ─────────────────────────────────────────────────────────

    @property
    def registre(self) -> str:
        """Nomme la hauteur. Les bornes sont celles de la phonétique usuelle."""
        if self.hauteur_hz < 110:
            return "très grave"
        if self.hauteur_hz < 145:
            return "grave"
        if self.hauteur_hz < 190:
            return "médium"
        if self.hauteur_hz < 240:
            return "aigu"
        return "très aigu"

    @property
    def expressivite(self) -> str:
        if self.etendue_demi_tons < 4:
            return "monocorde"
        if self.etendue_demi_tons < 8:
            return "posée"
        if self.etendue_demi_tons < 13:
            return "vivante"
        return "très expressive"

    @property
    def clarte(self) -> str:
        if self.timbre_hz < 1100:
            return "sombre et ronde"
        if self.timbre_hz < 1800:
            return "neutre"
        if self.timbre_hz < 2600:
            return "claire"
        return "très claire, presque métallique"

    @property
    def debit(self) -> str:
        """Le français parlé tient autour de 5 syllabes/seconde en conversation."""
        if self.debit_syllabes_s < 3.8:
            return "lent"
        if self.debit_syllabes_s < 5.2:
            return "normal"
        if self.debit_syllabes_s < 6.5:
            return "rapide"
        return "très rapide"

    def resume(self) -> str:
        return (
            f"{self.hauteur_hz:.0f} Hz ({self.registre}) · "
            f"étendue {self.etendue_demi_tons:.1f} demi-tons ({self.expressivite}) · "
            f"timbre {self.timbre_hz:.0f} Hz ({self.clarte}) · "
            f"{self.debit_syllabes_s:.1f} syll/s ({self.debit}) · "
            f"parole {self.ratio_parole:.0%} · confiance {self.confiance:.2f}"
        )

    # ── Utilisation ──────────────────────────────────────────────────────

    def vers_reglages(self) -> dict[str, float]:
        """Traduit le profil en réglages ElevenLabs.

        Le raisonnement, explicitement :
          · une voix **stable** en hauteur veut `stability` haut — c'est le
            paramètre qui empêche le modèle de « jouer » la phrase ;
          · une voix à **grande étendue mélodique** veut `style` haut ;
          · le **débit** se reporte directement sur `speed`, borné à ±25 %
            au-delà de quoi ElevenLabs déforme audiblement la voix.
        """
        # 3 demi-tons d'écart-type = voix très mouvante → stabilité basse.
        stabilite = 1.0 - min(1.0, self.stabilite_hz / 3.0)
        style = min(1.0, max(0.0, (self.etendue_demi_tons - 3.0) / 12.0))
        vitesse = self.debit_syllabes_s / 5.0
        return {
            "stabilite": round(min(0.9, max(0.15, stabilite)), 2),
            "style": round(min(0.9, max(0.05, style)), 2),
            "vitesse": round(min(1.25, max(0.75, vitesse)), 2),
        }

    def vecteur(self) -> np.ndarray:
        """Les axes retenus pour comparer deux voix, ramenés à des unités
        comparables : demi-tons pour la hauteur et le timbre (échelle
        logarithmique, comme l'oreille), unités naturelles pour le reste.
        """
        return np.array([
            _demi_tons(self.hauteur_hz, 150.0),
            _demi_tons(max(200.0, self.timbre_hz), 1500.0),
            self.etendue_demi_tons,
            self.debit_syllabes_s,
        ], dtype=np.float64)

    def distance(self, autre: ProfilVoix) -> float:
        """Écart entre deux voix. 0 = identiques ; au-delà de ~6, sans rapport.

        Les poids disent ce qui compte pour la ressemblance perçue : la
        hauteur d'abord (on reconnaît d'abord un grave d'un aigu), le timbre
        ensuite, puis le jeu et le débit — ces deux derniers étant de toute
        façon réglables après coup sur la voix choisie.
        """
        poids = np.array([1.0, 0.6, 0.35, 0.25])
        ecart = np.abs(self.vecteur() - autre.vecteur())
        return round(float(np.sqrt(((ecart * poids) ** 2).sum())), 3)


def _demi_tons(hz: float, reference: float) -> float:
    return 12.0 * math.log2(max(1e-6, hz) / reference)


# ── Mesures ──────────────────────────────────────────────────────────────

def _trames(signal: np.ndarray) -> np.ndarray:
    """Découpe le signal en trames qui se recouvrent, sans copie inutile."""
    n = 1 + max(0, (signal.size - TAILLE_TRAME) // PAS_TRAME)
    if n <= 0:
        return np.empty((0, TAILLE_TRAME), dtype=np.float32)
    indices = np.arange(TAILLE_TRAME)[None, :] + PAS_TRAME * np.arange(n)[:, None]
    return signal[indices]


def _f0(trames: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Hauteur par autocorrélation, toutes les trames d'un coup.

    L'autocorrélation passe par la FFT : sur 5 000 trames, la boucle Python
    équivalente prend une dizaine de secondes, la version vectorisée moins
    d'un dixième. Une interpolation parabolique autour du pic donne la
    précision sous-échantillon — sans elle, la résolution plafonne à ~7 Hz
    dans l'aigu, ce qui suffit à confondre deux voix distinctes.
    """
    if trames.size == 0:
        return np.empty(0), np.empty(0, dtype=bool)

    centrees = trames - trames.mean(axis=1, keepdims=True)
    fenetre = np.hanning(TAILLE_TRAME).astype(np.float32)
    centrees = centrees * fenetre

    spectre = np.fft.rfft(centrees, n=2 * TAILLE_TRAME, axis=1)
    acf = np.fft.irfft(np.abs(spectre) ** 2, axis=1)[:, :TAILLE_TRAME]

    energie = acf[:, 0].copy()
    energie[energie <= 0] = 1e-12
    acf = acf / energie[:, None]

    lag_min = max(2, int(TAUX / F0_MAX))
    lag_max = min(TAILLE_TRAME - 2, int(TAUX / F0_MIN))
    zone = acf[:, lag_min:lag_max]

    idx = zone.argmax(axis=1)
    pics = zone[np.arange(zone.shape[0]), idx]
    lags = idx + lag_min

    # Interpolation parabolique sur les trois points autour du pic.
    gauche = acf[np.arange(acf.shape[0]), lags - 1]
    droite = acf[np.arange(acf.shape[0]), lags + 1]
    denom = gauche - 2 * pics + droite
    # `np.where` évaluerait quand même la division sur les dénominateurs nuls
    # (trames de silence) et remplirait le journal d'avertissements. `np.divide`
    # avec `where` ne calcule que là où c'est licite.
    correction = np.divide(0.5 * (gauche - droite), denom,
                           out=np.zeros_like(denom),
                           where=np.abs(denom) > 1e-9)
    correction = np.clip(correction, -0.5, 0.5)

    f0 = TAUX / np.maximum(1e-6, lags + correction)

    rms = np.sqrt((trames ** 2).mean(axis=1))
    seuil_energie = max(float(np.median(rms)) * 0.35, 1e-4)
    voise = (pics > SEUIL_VOISEMENT) & (rms > seuil_energie) & (f0 > F0_MIN) & (f0 < F0_MAX)
    return f0, voise


def _centroide(trames: np.ndarray, voise: np.ndarray) -> float:
    """Centroïde spectral : le « centre de gravité » du son, en Hz.

    Mesuré uniquement sur les trames voisées — le silence a un centroïde
    élevé et parasite (c'est du souffle, donc du haut du spectre).
    """
    if trames.size == 0 or not voise.any():
        return 0.0
    utiles = trames[voise] * np.hanning(TAILLE_TRAME).astype(np.float32)
    amplitude = np.abs(np.fft.rfft(utiles, axis=1))
    freqs = np.fft.rfftfreq(TAILLE_TRAME, 1.0 / TAUX)
    total = amplitude.sum(axis=1)
    total[total <= 0] = 1e-12
    return float(np.median((amplitude * freqs).sum(axis=1) / total))


def _debit_syllabique(rms: np.ndarray, pas_s: float) -> float:
    """Compte les syllabes par les **sommets d'énergie**.

    Une syllabe = un noyau vocalique = une bosse dans l'enveloppe d'énergie.
    La règle qui fait la différence : ne compter un sommet que s'il est séparé
    du précédent par un **creux d'au moins 4 dB**. Sans cette condition, une
    seule voyelle tenue est comptée cinq fois et le débit triple.
    """
    if rms.size < 5:
        return 0.0

    db = 20 * np.log10(np.maximum(rms, 1e-6))
    # Lissage sur ~35 ms : supprime la micro-oscillation de la période
    # fondamentale sans effacer les syllabes (~180 ms).
    k = max(3, int(0.035 / pas_s))
    noyau = np.ones(k) / k
    lisse = np.convolve(db, noyau, mode="same")

    # Plancher de parole : 25 dB sous les passages les plus forts. Un seuil
    # calé sur la médiane paraît plus naturel mais surestime le débit de 50 %
    # (mesuré sur un signal modulé à cadence connue) : il exclut du temps de
    # parole les creux entre syllabes, qui sont pourtant de la parole.
    plancher = float(np.percentile(lisse, 95)) - 25.0
    sommets: list[int] = []
    dernier_creux = lisse[0]

    for i in range(1, lisse.size - 1):
        if lisse[i] < dernier_creux:
            dernier_creux = lisse[i]
        est_sommet = lisse[i] >= lisse[i - 1] and lisse[i] > lisse[i + 1]
        if est_sommet and lisse[i] > plancher and (lisse[i] - dernier_creux) >= 4.0:
            sommets.append(i)
            dernier_creux = lisse[i]

    duree_parlee = float((lisse > plancher).sum()) * pas_s
    if duree_parlee < 0.4:
        return 0.0
    return round(len(sommets) / duree_parlee, 2)


def analyser(chemin: Path, *, debut_s: float = 0.0,
             duree_max_s: float = 60.0) -> ProfilVoix:
    """Mesure la voix contenue dans un fichier audio ou vidéo.

    `duree_max_s` borne le calcul : au-delà d'une minute de parole, les
    médianes ne bougent plus, et on paierait du temps de calcul pour rien.
    """
    chemin = Path(chemin)
    if not chemin.exists():
        raise ErreurPdz(f"Fichier introuvable : {chemin}")

    signal = pcm(chemin, TAUX)
    if signal.size < TAILLE_TRAME * 4:
        raise ErreurPdz(
            f"{chemin.name} : extrait trop court pour analyser une voix "
            "(il en faut au moins une demi-seconde de parole)."
        )

    debut = int(max(0.0, debut_s) * TAUX)
    signal = signal[debut:debut + int(duree_max_s * TAUX)]

    trames = _trames(signal)
    f0, voise = _f0(trames)
    pas_s = PAS_TRAME / TAUX

    if voise.sum() < 10:
        raise ErreurPdz(
            f"{chemin.name} : aucune voix détectée. "
            "Musique seule, silence, ou piste trop bruitée ?"
        )

    voisees = f0[voise]
    hauteur = float(np.median(voisees))
    p10, p90 = (float(np.percentile(voisees, 10)), float(np.percentile(voisees, 90)))
    etendue = _demi_tons(p90, max(1e-6, p10))

    # Stabilité mesurée en demi-tons : un écart de 10 Hz n'a pas le même sens
    # sur une voix à 90 Hz que sur une voix à 250 Hz.
    demi_tons = 12.0 * np.log2(np.maximum(voisees, 1e-6) / hauteur)
    stabilite = float(np.std(demi_tons))

    rms = np.sqrt((trames ** 2).mean(axis=1))
    db = 20 * np.log10(np.maximum(rms, 1e-6))
    parlant = rms > max(float(np.median(rms)) * 0.35, 1e-4)

    # Confiance : proportion de trames voisées, ramenée à ce qu'on observe sur
    # de la parole propre (~55 % — le reste est consonnes et silences).
    voisement = float(voise.mean())
    confiance = round(min(1.0, voisement / 0.35), 2)

    return ProfilVoix(
        hauteur_hz=round(hauteur, 1),
        hauteur_p10=round(p10, 1),
        hauteur_p90=round(p90, 1),
        etendue_demi_tons=round(etendue, 2),
        stabilite_hz=round(stabilite, 2),
        timbre_hz=round(_centroide(trames, voise), 1),
        debit_syllabes_s=_debit_syllabique(rms, pas_s),
        ratio_parole=round(float(parlant.mean()), 3),
        dynamique_db=round(float(np.std(db[parlant])) if parlant.any() else 0.0, 2),
        voisement=round(voisement, 3),
        duree_s=round(signal.size / TAUX, 2),
        confiance=confiance,
    )
