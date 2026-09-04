"""La voix de repérage : dire le texte pour savoir combien de temps il dure.

Tout le systeme repose sur une phrase : « la voix off est la reference
temporelle ». Sauf qu'elle n'existait pas. Les durees de plan venaient d'une
estimation — 2,7 mots par seconde — et le montage calait des videos sur une
voix imaginaire.

espeak-ng dit le texte. Le rendu est robotique et ne se publie pas : ce n'est
pas ce qu'on lui demande. On lui demande une DUREE, phrase par phrase, et une
piste de reperage pour verifier que l'image tombe au bon moment. La vraie voix
— la tienne, ou celle d'un service — vient se poser dessus ensuite, et le
montage n'a rien a rejouer.

Aucun appel reseau, aucune cle : espeak-ng tourne sur la machine.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .models import Storyboard

#: Un debit francais tenable a l'oral, sans etre mou.
VITESSE = 145
#: Le souffle entre deux phrases, qu'aucune machine ne prend toute seule.
PAUSE = 0.25
VOIX_ESPEAK = "fr-fr"


class VoixError(RuntimeError):
    """La voix de reperage n'a pas pu etre produite."""


def exiger_espeak() -> None:
    if not shutil.which("espeak-ng"):
        raise VoixError(
            "espeak-ng absent du PATH.\n"
            "  Linux   : sudo apt install espeak-ng\n"
            "  macOS   : brew install espeak-ng\n"
            "  C'est une voix de REPÉRAGE : elle sert à mesurer les durées,\n"
            "  pas à être publiée.")


def dire(texte: str, wav: Path, vitesse: int = VITESSE) -> Path:
    """Une phrase, dite, ecrite en WAV."""
    exiger_espeak()
    wav.parent.mkdir(parents=True, exist_ok=True)
    sortie = subprocess.run(
        ["espeak-ng", "-v", VOIX_ESPEAK, "-s", str(vitesse), "-w", str(wav), texte],
        capture_output=True, text=True, timeout=120)
    if sortie.returncode != 0 or not wav.is_file():
        raise VoixError(f"espeak-ng a refusé la phrase : {sortie.stderr.strip()[:200]}")
    return wav


def duree(media: Path) -> float:
    sortie = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(media)],
        capture_output=True, text=True, timeout=60)
    if sortie.returncode != 0:
        raise VoixError(f"ffprobe a refusé {media.name}")
    return round(float(sortie.stdout.strip() or 0.0), 3)


def par_plan(sb: Storyboard, dossier: Path, vitesse: int = VITESSE) -> dict[int, float]:
    """Chaque phrase dite dans son coin, et sa duree reelle."""
    mesurees = {}
    for shot in sb.shots:
        wav = dossier / f"shot_{shot.id:02d}.wav"
        dire(shot.voice, wav, vitesse)
        mesurees[shot.id] = round(duree(wav) + PAUSE, 3)
    return mesurees


def piste(sb: Storyboard, dossier: Path, sortie: Path,
          vitesse: int = VITESSE) -> tuple[Path, dict[int, float]]:
    """La piste entiere, phrase apres phrase, avec le souffle entre elles."""
    mesurees = par_plan(sb, dossier, vitesse)
    fichiers = [dossier / f"shot_{s.id:02d}.wav" for s in sb.shots]
    return assembler(fichiers, dossier, sortie), mesurees


def assembler(fichiers: list[Path], dossier: Path, sortie: Path) -> Path:
    """Les phrases bout a bout, avec le souffle entre elles.

    La meme pause qui est comptee dans la duree de chaque plan : la piste et
    la timeline finissent donc a la meme seconde.
    """
    silence = dossier / "_pause.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "anullsrc=r=44100:cl=mono", "-t", str(PAUSE), str(silence)],
                   check=True, capture_output=True, timeout=60)

    morceaux = []
    for fichier in fichiers:
        morceaux += [fichier, silence]

    liste = dossier / "_piste.txt"
    liste.write_text("".join(f"file '{m.resolve()}'\n" for m in morceaux), encoding="utf-8")
    sortie.parent.mkdir(parents=True, exist_ok=True)
    resultat = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(liste),
         "-c:a", "libmp3lame", "-b:a", "128k", str(sortie)],
        capture_output=True, text=True, timeout=300)
    if resultat.returncode != 0:
        raise VoixError(f"ffmpeg a refusé l'assemblage : {resultat.stderr.strip()[:200]}")
    return sortie


# ---------------------------------------------------------------------------
# UNE VRAIE VOIX, POSEE SUR LE PLATEAU
#
# La voix de reperage donne des durees plausibles. Une vraie voix — la tienne,
# ou celle d'un service comme ElevenLabs — donne les VRAIES. Encore faut-il
# savoir ou finit chaque phrase dans une piste de soixante-quinze secondes.
#
# On ne fait pas de reconnaissance de parole pour ca : entre deux phrases, une
# voix se tait. ffmpeg sait entendre le silence. On garde les N-1 plus longs
# silences interieurs, on coupe au milieu de chacun, et chaque morceau est la
# duree reelle de sa phrase.
# ---------------------------------------------------------------------------

#: En dessous de ce niveau, c'est du silence et pas de la parole.
SEUIL_SILENCE_DB = -35.0
#: Plus court que ca, c'est une respiration au milieu d'une phrase.
SILENCE_MIN = 0.22
#: Il faut au moins ca de parole de chaque cote d'une frontiere de phrase.
PAROLE_MIN = 0.5


def silences(media: Path, seuil_db: float = SEUIL_SILENCE_DB,
             duree_min: float = SILENCE_MIN) -> list[tuple[float, float]]:
    """Les plages de silence de la piste, en secondes."""
    sortie = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(media), "-af",
         f"silencedetect=noise={seuil_db}dB:d={duree_min}", "-f", "null", "-"],
        capture_output=True, text=True, timeout=300)
    plages, debut = [], None
    for ligne in sortie.stderr.splitlines():
        if "silence_start:" in ligne:
            debut = float(ligne.split("silence_start:")[1].split()[0])
        elif "silence_end:" in ligne and debut is not None:
            plages.append((debut, float(ligne.split("silence_end:")[1].split()[0])))
            debut = None
    return plages


def decouper(media: Path, poids: list[float], seuil_db: float = SEUIL_SILENCE_DB,
             duree_min: float = SILENCE_MIN) -> list[float]:
    """Les durees des morceaux que la voix separe elle-meme.

    `poids` dit combien chaque morceau PESE — le nombre de mots de sa phrase.
    Prendre simplement les N-1 plus longs silences ne marche pas : sur la
    piste de reperage, le silence de fin de piste etait le plus long de tous,
    il a pris la place d'une vraie fin de phrase, et tout le decoupage a
    glisse d'un plan. On sait ou CHAQUE frontiere devrait tomber, au prorata
    des mots ; on prend donc le silence le plus proche de cet endroit-la.
    """
    if not poids:
        raise VoixError("il faut au moins un plan a caler")
    totale = duree(media)
    if len(poids) == 1:
        return [totale]

    # Une frontiere a de la parole DES DEUX COTES. Le silence de fin de piste
    # n'en a pas : il finissait a 75,42 s d'une piste de 75,49 s, passait la
    # tolerance, et volait la place d'une vraie fin de phrase — tout le
    # decoupage glissait d'un plan a partir de la.
    interieurs = [(d, f) for d, f in silences(media, seuil_db, duree_min)
                  if d > PAROLE_MIN and totale - f > PAROLE_MIN]
    if len(interieurs) < len(poids) - 1:
        raise VoixError(
            f"{len(interieurs)} silence(s) trouve(s) dans la piste, il en faut "
            f"{len(poids) - 1} pour separer {len(poids)} phrases.\n"
            f"  Soit la voix enchaine sans respirer, soit le seuil est trop bas.\n"
            f"  Reessaie avec --seuil -30, ou depose une piste par plan dans "
            f"output/voix/shot_01.mp3, shot_02.mp3, ...")

    # Une respiration au milieu d'une phrase est plus courte qu'une fin de
    # phrase. Quand il y a plus de silences que de frontieres a poser, on ne
    # garde que les longs — sauf si ca n'en laisse pas assez.
    if len(interieurs) > len(poids) - 1:
        longs = _les_longs(interieurs, len(poids) - 1)
        if longs:
            interieurs = longs

    milieux = sorted((d + f) / 2 for d, f in interieurs)
    total_poids = sum(poids) or 1.0
    cumul, coupes, depart = 0.0, [], 0
    for rang, part in enumerate(poids[:-1]):
        cumul += part
        cible = totale * cumul / total_poids
        # Il faut laisser un silence a chacune des frontieres suivantes : on
        # ne choisit donc que parmi ceux qui en laissent assez derriere.
        restants = len(poids) - 2 - rang
        candidats = milieux[depart:len(milieux) - restants]
        if not candidats:
            raise VoixError("plus assez de silences pour separer les phrases restantes")
        choisi = min(range(len(candidats)), key=lambda i: abs(candidats[i] - cible))
        coupes.append(candidats[choisi])
        depart += choisi + 1

    bornes = [0.0, *coupes, totale]
    return [round(bornes[i + 1] - bornes[i], 3) for i in range(len(poids))]


def _les_longs(plages: list[tuple[float, float]],
               minimum: int) -> list[tuple[float, float]]:
    """Les silences de fin de phrase, separes des respirations.

    Les deux familles ne se recouvrent pas : sur la piste de reperage, les
    respirations font 0,25 a 0,32 s et les fins de phrase 0,66 a 0,75 s. On
    cherche donc le plus grand ECART entre deux longueurs consecutives, et on
    garde tout ce qui est au-dessus. Une mediane ne marchait pas : elle
    coupait au milieu des fins de phrase et en jetait la moitie.
    """
    longueurs = sorted(f - d for d, f in plages)
    if len(longueurs) < 2:
        return []
    saut = max(range(len(longueurs) - 1),
               key=lambda i: longueurs[i + 1] / max(longueurs[i], 1e-6))
    seuil = longueurs[saut + 1]
    longs = [(d, f) for d, f in plages if f - d >= seuil]
    return longs if len(longs) >= minimum else []


def caler_sur(sb: Storyboard, media: Path, seuil_db: float = SEUIL_SILENCE_DB,
              duree_min: float = SILENCE_MIN) -> dict[int, float]:
    """Les durees que CETTE piste donne a chaque plan."""
    if not media.is_file():
        raise VoixError(f"piste introuvable : {media}")
    poids = [float(len(shot.voice.split()) or 1) for shot in sb.shots]
    morceaux = decouper(media, poids, seuil_db, duree_min)
    return {shot.id: duree for shot, duree in zip(sb.shots, morceaux, strict=True)}


def a_coller(sb: Storyboard) -> str:
    """Le texte a coller dans ElevenLabs, phrase par phrase.

    Une ligne vide entre les phrases : le service y pose une vraie pause, et
    c'est cette pause qui permettra de retrouver la fin de chaque plan.
    """
    return "\n\n".join(s.voice for s in sb.shots)


def caler(sb: Storyboard, mesurees: dict[int, float]) -> None:
    """Poser sur chaque plan la duree que sa phrase prend vraiment a dire."""
    for shot in sb.shots:
        if shot.id in mesurees:
            shot.duration_seconds = mesurees[shot.id]
    sb.duration_seconds = round(sum(s.duration_seconds for s in sb.shots), 3)


def rapport(sb: Storyboard, mesurees: dict[int, float]) -> str:
    lignes = ["## La voix, mesurée phrase par phrase", "",
              "*espeak-ng en local. Voix de repérage : elle donne la durée, "
              "pas le rendu.*", "",
              "| plan | prévu | dit | écart | mots/s | phrase |",
              "|---|---|---|---|---|---|"]
    for shot in sb.shots:
        dite = mesurees.get(shot.id)
        if dite is None:
            continue
        mots = len(shot.voice.split())
        lignes.append(
            f"| {shot.id:02d} | {shot.duration_seconds:g}s | {dite:g}s | "
            f"{dite - shot.duration_seconds:+.1f}s | {mots / dite:.1f} | "
            f"{shot.voice[:44]}{'…' if len(shot.voice) > 44 else ''} |")
    total = round(sum(mesurees.values()), 1)
    lignes += ["", f"**Total dit : {total:g} s** pour {sb.duration_seconds:g} s prévues."]
    return "\n".join(lignes)
