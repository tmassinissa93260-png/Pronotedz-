"""Timeline, sous-titres et assemblage du MP4 final.

La voix off est la reference temporelle : la timeline est calee sur elle, et
les videos sont ajustees a la duree du plan, jamais l'inverse.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from .models import Storyboard, VideoAnalysis


class MontageError(RuntimeError):
    """Le montage n'a pas pu aboutir."""


def exiger_ffmpeg() -> None:
    manquants = [outil for outil in ("ffmpeg", "ffprobe") if not shutil.which(outil)]
    if manquants:
        raise MontageError(
            f"{' et '.join(manquants)} absent(s) du PATH.\n"
            "  macOS   : brew install ffmpeg\n"
            "  Linux   : sudo apt install ffmpeg\n"
            "  Windows : winget install Gyan.FFmpeg")


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------


@dataclass
class Entree:
    shot_id: int
    start: float
    end: float
    duration: float
    video: str
    voice: str
    measured_duration: float
    ajustement: str
    remarques: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def construire_timeline(sb: Storyboard, videos: dict[int, Path],
                        analyses: dict[int, VideoAnalysis] | None = None) -> list[Entree]:
    """Enchaine les plans dans l'ordre, cales sur la duree prevue par la voix."""
    analyses = analyses or {}
    entrees, curseur = [], 0.0

    for shot in sb.shots:
        video = videos.get(shot.id)
        if video is None:
            raise MontageError(
                f"aucune video pour le plan {shot.id:02d}.\n"
                f"  Attendu : videos/shot_{shot.id:02d}.mp4 (ou .mov, .webm)")

        analyse = analyses.get(shot.id)
        mesuree = analyse.measured_duration if analyse else 0.0
        prevue = shot.duration_seconds

        if not mesuree:
            ajustement = "duree reelle inconnue : la video sera coupee a la duree prevue"
        elif mesuree < prevue - 0.15:
            ajustement = f"video plus courte de {prevue - mesuree:.2f}s : ralentie pour tenir"
        elif mesuree > prevue + 0.15:
            ajustement = f"video plus longue de {mesuree - prevue:.2f}s : coupee a {prevue}s"
        else:
            ajustement = "duree conforme"

        remarques = list(analyse.defects) if analyse else []
        if analyse and not analyse.matches_plan:
            remarques.insert(0, "la video ne correspond pas au plan prevu")

        entrees.append(Entree(shot.id, round(curseur, 3), round(curseur + prevue, 3),
                              prevue, str(video), shot.voice, mesuree, ajustement, remarques))
        curseur += prevue

    return entrees


def sauver_timeline(entrees: list[Entree], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([e.to_dict() for e in entrees], indent=2, ensure_ascii=False)
                    + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Sous-titres
# ---------------------------------------------------------------------------


def horodatage(secondes: float) -> str:
    ms = int(round(secondes * 1000))
    h, reste = divmod(ms, 3_600_000)
    m, reste = divmod(reste, 60_000)
    s, ms = divmod(reste, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def sous_titres(entrees: list[Entree]) -> str:
    """Un bloc SRT par plan, cale sur la voix off."""
    blocs = []
    for numero, e in enumerate(entrees, start=1):
        blocs.append(f"{numero}\n{horodatage(e.start)} --> {horodatage(e.end)}\n"
                     f"{_couper(e.voice)}\n")
    return "\n".join(blocs)


def _couper(texte: str, largeur: int = 42) -> str:
    """Deux lignes au plus, coupees entre les mots : lisible en vertical."""
    mots, lignes, courante = texte.split(), [], ""
    for mot in mots:
        essai = f"{courante} {mot}".strip()
        if len(essai) <= largeur:
            courante = essai
        else:
            lignes.append(courante)
            courante = mot
    if courante:
        lignes.append(courante)
    if len(lignes) <= 2:
        return "\n".join(lignes)
    milieu = len(mots) // 2
    return " ".join(mots[:milieu]) + "\n" + " ".join(mots[milieu:])


# ---------------------------------------------------------------------------
# Assemblage
# ---------------------------------------------------------------------------


def assembler(entrees: list[Entree], sortie: Path, voix: Path | None = None,
              musique: Path | None = None, srt: Path | None = None,
              travail: Path | None = None) -> Path:
    """Coupe chaque plan a sa duree, les enchaine, ajoute son et sous-titres."""
    exiger_ffmpeg()
    travail = travail or sortie.parent / "montage"
    travail.mkdir(parents=True, exist_ok=True)
    sortie.parent.mkdir(parents=True, exist_ok=True)

    morceaux = []
    for e in entrees:
        morceau = travail / f"plan_{e.shot_id:02d}.mp4"
        _normaliser(Path(e.video), e.duration, morceau)
        morceaux.append(morceau)

    liste = travail / "plans.txt"
    liste.write_text("".join(f"file '{m.resolve()}'\n" for m in morceaux), encoding="utf-8")

    muet = travail / "enchaine.mp4"
    _ffmpeg(["-f", "concat", "-safe", "0", "-i", str(liste), "-c", "copy", str(muet)])

    courant = muet
    if voix and voix.is_file():
        avec_voix = travail / "avec_voix.mp4"
        pistes = ["-i", str(courant), "-i", str(voix)]
        if musique and musique.is_file():
            pistes += ["-i", str(musique)]
            filtre = "[1:a]volume=1.0[v];[2:a]volume=0.15[m];[v][m]amix=inputs=2:duration=first[a]"
            _ffmpeg(pistes + ["-filter_complex", filtre, "-map", "0:v", "-map", "[a]",
                              "-c:v", "copy", "-c:a", "aac", "-shortest", str(avec_voix)])
        else:
            _ffmpeg(pistes + ["-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
                              "-shortest", str(avec_voix)])
        courant = avec_voix

    if srt and srt.is_file():
        avec_st = travail / "avec_sous_titres.mp4"
        style = ("FontSize=16,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                 "BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV=90")
        _ffmpeg(["-i", str(courant), "-vf",
                 f"subtitles={_echapper(srt)}:force_style='{style}'",
                 "-c:a", "copy", str(avec_st)])
        courant = avec_st

    shutil.copy2(courant, sortie)
    return sortie


def _normaliser(source: Path, duree: float, cible: Path) -> None:
    """Chaque plan sort en 1080x1920, 30 i/s, a la duree exacte du plan."""
    _ffmpeg(["-i", str(source), "-t", f"{duree}",
             "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,"
                    "crop=1080:1920,fps=30,setsar=1",
             "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
             "-pix_fmt", "yuv420p", str(cible)])


def _echapper(path: Path) -> str:
    """ffmpeg lit le chemin des sous-titres dans un filtre : il faut l'echapper."""
    return str(path.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def _ffmpeg(arguments: list[str]) -> None:
    resultat = subprocess.run(["ffmpeg", "-v", "error", "-y", *arguments],
                              capture_output=True, text=True)
    if resultat.returncode != 0:
        raise MontageError(f"ffmpeg a echoue :\n  {' '.join(arguments[:6])}...\n"
                           f"  {resultat.stderr.strip()[:400]}")
