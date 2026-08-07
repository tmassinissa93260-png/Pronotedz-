"""Métadonnées d'une vidéo — la base de toute l'analyse."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from pdz.moteur.erreurs import ErreurConfig, ErreurPdz


@dataclass
class Metadonnees:
    duree_s: float
    largeur: int
    hauteur: int
    fps: float
    a_du_son: bool
    codec: str
    octets: int

    @property
    def ratio(self) -> str:
        if not self.hauteur:
            return "?"
        r = self.largeur / self.hauteur
        for nom, valeur in (("9:16", 0.5625), ("1:1", 1.0), ("16:9", 1.7778),
                            ("4:5", 0.8)):
            if abs(r - valeur) < 0.03:
                return nom
        return f"{r:.2f}"

    @property
    def vertical(self) -> bool:
        return self.hauteur > self.largeur


def sonder(chemin: Path) -> Metadonnees:
    if not Path(chemin).exists():
        raise ErreurPdz(f"Fichier introuvable : {chemin}")

    r = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", str(chemin)],
        capture_output=True, text=True, timeout=120,
    )
    if r.returncode != 0:
        raise ErreurConfig(
            f"ffprobe a échoué sur {Path(chemin).name}. "
            f"Le fichier est-il bien une vidéo ? {r.stderr[-200:]}"
        )

    d = json.loads(r.stdout)
    flux = d.get("streams", [])
    video = next((s for s in flux if s.get("codec_type") == "video"), None)
    if video is None:
        raise ErreurPdz(f"Aucune piste vidéo dans {Path(chemin).name}.")

    num, _, den = (video.get("r_frame_rate") or "0/1").partition("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 0.0

    return Metadonnees(
        duree_s=round(float(d.get("format", {}).get("duration", 0)), 2),
        largeur=int(video.get("width", 0)),
        hauteur=int(video.get("height", 0)),
        fps=round(fps, 2),
        a_du_son=any(s.get("codec_type") == "audio" for s in flux),
        codec=video.get("codec_name", "?"),
        octets=int(d.get("format", {}).get("size", 0)),
    )
