"""Analyse du son — courbe d'énergie, silences, tempo, débit de parole.

Tout est **mesuré**, pas estimé par un modèle. On extrait le PCM brut avec
ffmpeg et on calcule. Coût : zéro.

C'est ce qui donne les chiffres les plus fiables de toute l'analyse (voir
docs/02-faisabilite.md, niveau 1) — et ce sont précisément ceux dont le
générateur a besoin : le rythme, les pauses, l'énergie.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from pdz.moteur.erreurs import ErreurPdz

TAUX = 22050          # suffisant pour l'enveloppe et le tempo, 2× plus rapide
FENETRE_MS = 25


@dataclass
class AnalyseSon:
    duree_s: float
    courbe_energie: list[float]      # normalisée 0-1, une valeur par fenêtre
    fenetre_ms: int
    silences: list[tuple[float, float]]
    lufs_estime: float
    tempo_bpm: float | None
    confiance_tempo: float

    @property
    def energie_moyenne(self) -> float:
        return float(np.mean(self.courbe_energie)) if self.courbe_energie else 0.0

    @property
    def ratio_silence(self) -> float:
        total = sum(f - d for d, f in self.silences)
        return total / max(0.001, self.duree_s)

    def courbe_reduite(self, points: int = 12) -> list[float]:
        """Ré-échantillonne la courbe pour la stocker dans une structure.

        Douze points suffisent à décrire l'arc d'énergie d'une vidéo courte,
        et restent lisibles dans un prompt.
        """
        if not self.courbe_energie:
            return []
        a = np.array(self.courbe_energie)
        idx = np.linspace(0, len(a) - 1, points)
        return [round(float(v), 3) for v in np.interp(idx, np.arange(len(a)), a)]


def _pcm(chemin: Path) -> np.ndarray:
    """Extrait le son en mono 16 bits, via un tube — aucun fichier temporaire."""
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(chemin),
         "-vn", "-ac", "1", "-ar", str(TAUX), "-f", "s16le", "-"],
        capture_output=True, timeout=600,
    )
    if r.returncode != 0 or not r.stdout:
        raise ErreurPdz(
            f"Impossible d'extraire le son de {chemin.name} : "
            f"{r.stderr.decode(errors='replace')[-300:]}"
        )
    return np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def _silences(rms: np.ndarray, fenetre_s: float, *,
              seuil_relatif: float = 0.10,
              duree_min_s: float = 0.20) -> list[tuple[float, float]]:
    """Passages sous 10 % de l'énergie médiane, tenus au moins 200 ms.

    Le seuil est relatif : un enregistrement globalement faible ne doit pas
    être vu comme un silence continu.
    """
    if rms.size == 0:
        return []
    seuil = float(np.median(rms)) * seuil_relatif
    bas = rms < seuil

    silences, debut = [], None
    for i, calme in enumerate(bas):
        if calme and debut is None:
            debut = i
        elif not calme and debut is not None:
            if (i - debut) * fenetre_s >= duree_min_s:
                silences.append((debut * fenetre_s, i * fenetre_s))
            debut = None
    if debut is not None and (len(bas) - debut) * fenetre_s >= duree_min_s:
        silences.append((debut * fenetre_s, len(bas) * fenetre_s))
    return silences


def _tempo(rms: np.ndarray, fenetre_s: float) -> tuple[float | None, float]:
    """Estime le tempo par autocorrélation de la fonction d'attaque.

    Pas de librosa : on dérive l'enveloppe, on garde les montées (les attaques),
    et on cherche la période qui se répète le plus. Sur de la musique franche
    c'est fiable ; sur de la voix seule, la confiance chute — et c'est bien
    qu'elle chute, plutôt que de renvoyer un chiffre inventé.
    """
    if rms.size < 40:
        return None, 0.0

    attaque = np.diff(rms, prepend=rms[0])
    attaque = np.maximum(attaque, 0)            # seules les montées comptent
    attaque -= attaque.mean()
    if not np.any(attaque):
        return None, 0.0

    corr = np.correlate(attaque, attaque, mode="full")[attaque.size - 1:]
    if corr[0] <= 0:
        return None, 0.0
    corr = corr / corr[0]

    # 60 à 200 BPM → périodes correspondantes, en fenêtres.
    lag_min = max(1, int(60.0 / 200.0 / fenetre_s))
    lag_max = min(corr.size - 1, int(60.0 / 60.0 / fenetre_s))
    if lag_max <= lag_min:
        return None, 0.0

    zone = corr[lag_min:lag_max]
    lag = int(np.argmax(zone)) + lag_min
    pic = float(zone.max())

    bpm = 60.0 / (lag * fenetre_s)
    # La hauteur du pic d'autocorrélation sert directement de confiance.
    return round(bpm, 1), round(max(0.0, min(1.0, pic)), 2)


def analyser(chemin: Path) -> AnalyseSon:
    pcm = _pcm(chemin)
    taille = max(1, int(TAUX * FENETRE_MS / 1000))
    n = pcm.size // taille
    if n == 0:
        raise ErreurPdz("Piste audio trop courte pour être analysée.")

    trames = pcm[: n * taille].reshape(n, taille)
    rms = np.sqrt(np.mean(trames ** 2, axis=1))
    fenetre_s = taille / TAUX
    duree = pcm.size / TAUX

    crete = float(rms.max()) or 1.0
    courbe = (rms / crete).tolist()

    # Approximation de la loudness : le vrai LUFS demande le filtre K et une
    # intégration par blocs. Ici on veut juste savoir si c'est trop faible.
    moyenne = float(np.sqrt(np.mean(pcm ** 2))) or 1e-9
    lufs = round(20 * np.log10(moyenne) - 0.7, 1)

    bpm, confiance = _tempo(rms, fenetre_s)

    return AnalyseSon(
        duree_s=round(duree, 2),
        courbe_energie=[round(v, 4) for v in courbe],
        fenetre_ms=FENETRE_MS,
        silences=[(round(d, 2), round(f, 2)) for d, f in _silences(rms, fenetre_s)],
        lufs_estime=lufs,
        tempo_bpm=bpm,
        confiance_tempo=confiance,
    )
