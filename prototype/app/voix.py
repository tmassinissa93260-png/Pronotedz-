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

    morceaux = []
    silence = dossier / "_pause.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "anullsrc=r=22050:cl=mono", "-t", str(PAUSE), str(silence)],
                   check=True, capture_output=True, timeout=60)
    for shot in sb.shots:
        morceaux.append(dossier / f"shot_{shot.id:02d}.wav")
        morceaux.append(silence)

    liste = dossier / "_piste.txt"
    liste.write_text("".join(f"file '{m.resolve()}'\n" for m in morceaux), encoding="utf-8")
    sortie.parent.mkdir(parents=True, exist_ok=True)
    resultat = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(liste),
         "-c:a", "libmp3lame", "-b:a", "128k", str(sortie)],
        capture_output=True, text=True, timeout=300)
    if resultat.returncode != 0:
        raise VoixError(f"ffmpeg a refusé l'assemblage : {resultat.stderr.strip()[:200]}")
    return sortie, mesurees


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
