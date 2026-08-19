"""Fabrique la bande voix complète d'un épisode, automatiquement.

Ce module est le chaînon qui manquait. `pdz.ia.elevenlabs` sait dire UNE
phrase ; ici on part d'un script dialogué et d'un univers, et on obtient :

  · un fichier audio unique, prêt pour le montage ;
  · **la bonne voix pour chaque personnage**, la même d'un épisode à l'autre ;
  · les timings exacts de chaque mot, **recalés sur la piste complète** ;
  · la durée réelle de chaque réplique, qui pilotera la durée des plans.

Trois choses qu'on ne peut pas faire à la main sans se tromper :

1. **Le recalage.** Chaque réplique est synthétisée séparément et renvoie des
   timings qui repartent de zéro. Il faut les décaler de la position atteinte
   dans la piste — sinon tous les sous-titres sauf le premier sont faux.
2. **Le cache.** ElevenLabs facture au caractère et la formule gratuite en
   donne 10 000 par mois. Refaire une réplique déjà dite est du gaspillage
   pur : le même texte avec la même voix est réutilisé.
3. **Les respirations.** Un dialogue sans silence entre les répliques est
   inécoutable ; il faut insérer une pause, et en tenir compte dans les timings.
"""

from __future__ import annotations

import hashlib
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from pdz.backends import backend_voix
from pdz.config import config
from pdz.moteur.erreurs import ErreurConfig, ErreurPdz
from pdz.univers import Univers, Voix
from pdz.video.soustitres import Mot

log = logging.getLogger(__name__)

# Silence inséré entre deux répliques. 280 ms : assez pour respirer, assez
# court pour garder le rythme du format vertical.
PAUSE_MS = 280

# Pause plus longue quand la parole change de personnage : c'est ce qui rend
# un échange lisible à l'oreille.
PAUSE_CHANGEMENT_MS = 420

# (stabilite, style) qu'une émotion suggère chez ElevenLabs : stabilite basse
# + style haut = plus dynamique et expressif ; l'inverse = plus posé, plus
# constant. Mélangées à la base du personnage dans `_reglages_avec_emotion`,
# jamais substituées — la voix reste reconnaissable, mais varie vraiment
# d'une réplique à l'autre selon ce que ScriptWriter a écrit.
EMOTIONS_VOIX = {
    "colere": (0.25, 0.75),
    "surprise": (0.25, 0.70),
    "peur": (0.30, 0.65),
    "joie": (0.35, 0.60),
    "tristesse": (0.65, 0.30),
    "mepris": (0.55, 0.40),
    "gene": (0.55, 0.35),
    "calme": (0.60, 0.25),
}


def _reglages_avec_emotion(voix: Voix, emotion: str) -> tuple[float, float, float]:
    """(stabilite, style, vitesse) à utiliser pour CETTE réplique précise.

    `emotion` est déjà écrit par ScriptWriter pour chaque réplique, mais
    n'était jusqu'ici jamais lu par la synthèse vocale : chaque personnage
    gardait le même débit et la même expressivité du hook au payoff — le
    genre de « débit monotone » qu'une bonne narration évite. Mélanger
    (moitié-moitié) la base du personnage — sa personnalité vocale, fixe
    d'un épisode à l'autre — avec ce que suggère son émotion à ce moment
    précis fait varier la voix sans la rendre méconnaissable.
    """
    stabilite_e, style_e = EMOTIONS_VOIX.get(emotion, (voix.stabilite, voix.style))
    stabilite = round((voix.stabilite + stabilite_e) / 2, 3)
    style = round((voix.style + style_e) / 2, 3)
    return stabilite, style, voix.vitesse


@dataclass
class RepliqueDite:
    numero: int
    personnage: str
    texte: str
    fichier: Path
    debut_ms: int
    duree_ms: int
    mots: list[Mot]
    depuis_cache: bool = False

    @property
    def fin_ms(self) -> int:
        return self.debut_ms + self.duree_ms


@dataclass
class BandeVoix:
    fichier: Path
    duree_ms: int
    repliques: list[RepliqueDite] = field(default_factory=list)
    caracteres_factures: int = 0
    caracteres_evites: int = 0

    @property
    def mots(self) -> list[Mot]:
        """Tous les mots de l'épisode, datés sur la piste complète."""
        return [m for r in self.repliques for m in r.mots]

    @property
    def debuts_de_replique(self) -> frozenset[int]:
        """Les millisecondes où une nouvelle réplique commence.

        Sert aux sous-titres : une carte qui enjambe cette frontière mêle
        les paroles de deux personnages sur la même ligne.
        """
        return frozenset(r.mots[0].debut_ms for r in self.repliques if r.mots)

    @property
    def durees_repliques_s(self) -> list[float]:
        """Le temps de parole pur, silences exclus."""
        return [r.duree_ms / 1000 for r in self.repliques]

    @property
    def durees_couvrantes_s(self) -> list[float]:
        """Les durées qui pilotent le montage : **silences compris**.

        La différence entre les deux propriétés vaut une correction de bug.
        Le temps de parole seul ne couvre pas la piste : il manque les
        respirations entre répliques, soit 280 à 420 ms chacune. Sur douze
        répliques, ça fait quatre secondes d'image en moins que de son —
        la vidéo s'arrête, la voix continue.

        Ici, chaque réplique s'étend jusqu'au début de la suivante. La somme
        vaut exactement la durée de la piste, par construction.
        """
        bornes = [r.debut_ms for r in self.repliques] + [self.duree_ms]
        return [(b - a) / 1000
                for a, b in zip(bornes, bornes[1:], strict=False)]

    def resume(self) -> str:
        eco = ""
        if self.caracteres_evites:
            eco = f" · {self.caracteres_evites} caractères évités par le cache"
        return (f"{len(self.repliques)} répliques · {self.duree_ms / 1000:.1f} s "
                f"· {len(self.mots)} mots datés · "
                f"{self.caracteres_factures} caractères facturés{eco}")


def _empreinte(texte: str, voice_id: str, reglages: tuple) -> str:
    brut = f"{texte}|{voice_id}|{reglages}"
    return hashlib.sha256(brut.encode()).hexdigest()[:20]


def duree_ms(fichier: Path) -> int:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(fichier)],
        capture_output=True, text=True, timeout=60,
    )
    if r.returncode != 0 or not r.stdout.strip():
        raise ErreurPdz(f"Durée illisible pour {fichier.name}")
    return round(float(r.stdout.strip()) * 1000)


def _decaler(mots: list[Mot], decalage_ms: int) -> list[Mot]:
    """Recale des timings qui repartaient de zéro sur la piste complète."""
    return [Mot(m.texte, m.debut_ms + decalage_ms, m.fin_ms + decalage_ms)
            for m in mots]


def _repartir_faute_de_timings(texte: str, debut_ms: int, duree_ms: int) -> list[Mot]:
    """Repli si l'alignement est absent : on estime au prorata.

    Moins bon que les timings réels (mesuré : jusqu'à 271 ms de dérive sur une
    phrase à pauses), mais préférable à des sous-titres absents.
    """
    from pdz.video.soustitres import mots_depuis_texte
    return mots_depuis_texte(texte, debut_ms, duree_ms)


# Débit de parole retenu pour ESTIMER une durée sans rien synthétiser.
# 165 mots/minute est déjà la valeur que `pdz.analyse.adn` prend par défaut
# quand aucun profil de voix n'a été mesuré : la reprendre ici évite
# d'inventer un second chiffre pour exactement la même chose.
DEBIT_ESTIME_WPM = 165


def _duree_estimee_ms(texte: str, debit_wpm: int) -> int:
    """Combien de temps cette réplique prendrait à dire. Estimé, jamais mesuré."""
    mots = len(texte.split())
    return max(600, round(mots / max(1, debit_wpm) * 60_000))


def _silence(sortie: Path, duree_ms: int) -> Path:
    sortie.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
         "-t", f"{duree_ms / 1000:.3f}", "-c:a", "aac", "-b:a", "128k",
         str(sortie)],
        capture_output=True, text=True, timeout=120,
    )
    if r.returncode != 0:
        raise ErreurPdz(f"Piste muette impossible :\n{r.stderr[-500:]}")
    return sortie


def dire_muet(repliques: list[dict], univers: Univers, sortie: Path, *,
              debit_wpm: int = DEBIT_ESTIME_WPM) -> BandeVoix:
    """La même `BandeVoix`, sans appeler le moindre fournisseur de voix.

    À quoi ça sert : la voix est le PREMIER poste de l'épisode, et c'est elle
    qui fixe la durée de chaque plan. Quand ElevenLabs refuse de répondre
    (crédits épuisés, palier gratuit coupé sur une IP de runner — voir
    `pdz.ia.elevenlabs`), l'épisode s'arrête avant les images, avant
    l'animation, avant le montage : impossible de voir le résultat visuel
    d'un travail qui n'a rien à voir avec le son.

    Ici, les durées sont ESTIMÉES au débit de parole plutôt que mesurées sur
    un fichier audio, et la piste est un silence de la bonne longueur. Tout
    l'aval — découpage, sous-titres, montage — reçoit exactement le même
    contrat qu'avec une vraie voix et n'a rien à savoir de la différence.

    Ce n'est pas un remplaçant d'ElevenLabs : la vidéo est MUETTE, et les
    sous-titres dérivent de ce que la parole aurait duré. C'est un moyen de
    voir l'image, pas de livrer un épisode.
    """
    dites: list[RepliqueDite] = []
    curseur_ms = 0
    precedent: str | None = None

    for r in repliques:
        perso = univers.personnage(r["personnage"])
        # Aucune exigence de `voice_id` ici : c'est tout l'intérêt du mode.
        identite = perso.id if perso else r["personnage"]
        texte = r["replique"]

        if dites:
            curseur_ms += (PAUSE_CHANGEMENT_MS if identite != precedent
                           else PAUSE_MS)

        duree = _duree_estimee_ms(texte, debit_wpm)
        dites.append(RepliqueDite(
            numero=r.get("numero", len(dites) + 1),
            personnage=identite, texte=texte, fichier=sortie,
            debut_ms=curseur_ms, duree_ms=duree,
            mots=_repartir_faute_de_timings(texte, curseur_ms, duree),
        ))
        curseur_ms += duree
        precedent = identite

    if not dites:
        raise ErreurPdz("Aucune réplique : rien à mettre en musique, même muet.")

    # Une seule piste pour tout l'épisode : il n'y a rien à assembler quand
    # chaque morceau est du silence. `RepliqueDite.fichier` pointe donc vers
    # elle pour toutes les répliques — un détail assumé de ce mode.
    _silence(sortie, curseur_ms)

    bande = BandeVoix(fichier=sortie, duree_ms=curseur_ms, repliques=dites)
    log.warning(
        "Bande voix MUETTE — aucune synthèse, durées estimées à %d mots/min : %s",
        debit_wpm, bande.resume(),
    )
    return bande


def dire(repliques: list[dict], univers: Univers, sortie: Path, *,
         cache: bool = True, job_id: str | None = None) -> BandeVoix:
    """Synthétise tout un dialogue et assemble la bande son.

    `repliques` : la sortie du ScriptWriter — une liste de dictionnaires avec
    au moins `numero`, `personnage`, `replique`.
    """
    cfg = config()
    dossier = sortie.parent / f"_voix_{sortie.stem}"
    dossier.mkdir(parents=True, exist_ok=True)
    dossier_cache = cfg.dossier_cache / "voix"
    dossier_cache.mkdir(parents=True, exist_ok=True)

    dites: list[RepliqueDite] = []
    curseur_ms = 0
    factures = evites = 0
    precedent: str | None = None

    for r in repliques:
        perso = univers.personnage(r["personnage"])
        if perso is None:
            raise ErreurConfig(
                f"Réplique {r.get('numero')} : personnage « {r['personnage']} » "
                f"absent de l'univers « {univers.nom} »."
            )
        if not perso.voix.voice_id:
            raise ErreurConfig(
                f"{perso.nom} n'a pas de voix. Renseigne `voix.voice_id` dans "
                f"univers/{univers.id}.yaml — c'est ce qui le rend reconnaissable "
                "d'un épisode à l'autre."
            )

        texte = r["replique"]
        stabilite, style, vitesse = _reglages_avec_emotion(
            perso.voix, r.get("emotion", "calme")
        )
        reglages = (stabilite, style, vitesse)
        emp = _empreinte(texte, perso.voix.voice_id, reglages)
        garde = dossier_cache / f"{emp}.mp3"

        # Pause avant la réplique — plus longue si on change de bouche.
        if dites:
            curseur_ms += (PAUSE_CHANGEMENT_MS if perso.id != precedent
                           else PAUSE_MS)

        if cache and garde.exists():
            fichier = dossier / f"{r['numero']:03d}.mp3"
            fichier.write_bytes(garde.read_bytes())
            duree = duree_ms(fichier)
            # Le cache ne conserve pas l'alignement : on estime pour ce cas.
            mots = _repartir_faute_de_timings(texte, curseur_ms, duree)
            evites += len(texte)
            depuis_cache = True
        else:
            fichier, mots_bruts = backend_voix().synthetiser(
                texte, dossier / f"{r['numero']:03d}.mp3",
                voice_id=perso.voix.voice_id,
                stabilite=stabilite,
                style=style,
                vitesse=vitesse,
            )
            duree = duree_ms(fichier)
            mots = (_decaler(mots_bruts, curseur_ms) if mots_bruts
                    else _repartir_faute_de_timings(texte, curseur_ms, duree))
            factures += len(texte)
            depuis_cache = False
            if cache:
                garde.write_bytes(fichier.read_bytes())

        dites.append(RepliqueDite(
            numero=r.get("numero", len(dites) + 1),
            personnage=perso.id, texte=texte, fichier=fichier,
            debut_ms=curseur_ms, duree_ms=duree, mots=mots,
            depuis_cache=depuis_cache,
        ))
        curseur_ms += duree
        precedent = perso.id

    _assembler(dites, sortie)
    bande = BandeVoix(
        fichier=sortie, duree_ms=curseur_ms, repliques=dites,
        caracteres_factures=factures, caracteres_evites=evites,
    )
    log.info("Bande voix : %s", bande.resume())
    return bande


def _assembler(dites: list[RepliqueDite], sortie: Path) -> Path:
    """Colle les répliques avec leurs silences, en une seule passe ffmpeg.

    Chaque réplique est placée à sa position exacte plutôt que concaténée :
    les positions viennent déjà d'être calculées, autant s'en servir et
    éviter que les arrondis ne s'accumulent.
    """
    if not dites:
        raise ErreurPdz("Aucune réplique à assembler.")

    entrees, filtres, etiquettes = [], [], []
    for i, d in enumerate(dites):
        entrees += ["-i", str(d.fichier)]
        filtres.append(f"[{i}:a]adelay={d.debut_ms}|{d.debut_ms}[d{i}]")
        etiquettes.append(f"[d{i}]")

    chaine = (";".join(filtres) + ";" + "".join(etiquettes) +
              f"amix=inputs={len(dites)}:duration=longest:normalize=0,"
              "loudnorm=I=-14:TP=-1.5:LRA=11[out]")

    sortie.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *entrees,
         "-filter_complex", chaine, "-map", "[out]",
         "-c:a", "aac", "-b:a", "192k", str(sortie)],
        capture_output=True, text=True, timeout=300,
    )
    if r.returncode != 0:
        raise ErreurPdz(f"Assemblage de la voix impossible :\n{r.stderr[-800:]}")
    return sortie
