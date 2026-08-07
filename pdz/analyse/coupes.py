"""Détection des coupes — avec calibrage automatique du seuil.

⚠️ Le point qui fait toute la différence, et que la plupart des outils ratent :
**il n'existe pas de bon seuil unique.**

Mesuré sur ce projet, sur une vraie vidéo TikTok en style filaire blanc sur
noir :

    seuil 0,25  →   3 coupes en 77 s   ❌ l'image est presque noire, deux
                                          plans successifs se ressemblent trop
    seuil 0,10  →  20 coupes           ✅ le bon chiffre
    seuil 0,06  →  55 coupes           ❌ il compte les changements de TEXTE
    seuil 0,04  → 141 coupes           ❌ n'importe quoi

Un seuil fixe donne donc un résultat faux d'un facteur 7 dans un sens ou
dans l'autre, **sans aucun signe d'erreur**. Ce module essaie plusieurs
seuils et retient celui dont la distribution des durées est plausible.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median

from pdz.moteur.erreurs import ErreurPdz

# Du plus sévère au plus permissif.
SEUILS = (0.30, 0.22, 0.16, 0.12, 0.09, 0.06, 0.04)

# Un plan sous ce seuil n'est pas un plan : c'est un flash, une incrustation
# de texte qui change, ou un fondu compté deux fois.
DUREE_MINIMALE_PLAN = 0.25

MOTIF_TEMPS = re.compile(r"pts_time:([0-9.]+)")


@dataclass
class Decoupage:
    """Le découpage retenu, et pourquoi."""

    seuil: float
    coupes: list[float]
    durees: list[float]
    duree_totale: float
    confiance: float = 1.0
    candidats: list[dict] = field(default_factory=list)

    @property
    def nb_plans(self) -> int:
        return len(self.durees)

    @property
    def duree_moyenne(self) -> float:
        return self.duree_totale / max(1, self.nb_plans)

    @property
    def duree_mediane(self) -> float:
        return median(self.durees) if self.durees else 0.0

    @property
    def coupes_par_minute(self) -> float:
        return len(self.coupes) / max(0.001, self.duree_totale) * 60

    @property
    def percentiles(self) -> tuple[float, float]:
        """p10 et p90 des durées : dit si le montage est régulier ou contrasté."""
        if not self.durees:
            return (0.0, 0.0)
        tri = sorted(self.durees)
        return (tri[len(tri) // 10], tri[-max(1, len(tri) // 10)])

    def resume(self) -> str:
        p10, p90 = self.percentiles
        return (f"{self.nb_plans} plans · {self.duree_moyenne:.2f} s en moyenne "
                f"(médiane {self.duree_mediane:.2f} s, p10 {p10:.2f} / p90 {p90:.2f}) "
                f"· {self.coupes_par_minute:.1f} coupes/min "
                f"· seuil {self.seuil:.2f} · confiance {self.confiance:.2f}")


def _detecter(chemin: Path, seuil: float, duree_totale: float) -> list[float]:
    """Une passe de détection à un seuil donné."""
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(chemin),
         "-filter:v", f"select='gt(scene,{seuil})',showinfo", "-f", "null", "-"],
        capture_output=True, text=True, timeout=600,
    )
    temps = [float(m) for m in MOTIF_TEMPS.findall(r.stderr)]
    return [t for t in temps if 0.05 < t < duree_totale - 0.05]


def _durees(coupes: list[float], duree_totale: float) -> list[float]:
    bornes = [0.0, *coupes, duree_totale]
    return [b - a for a, b in zip(bornes, bornes[1:], strict=False)]


def _noter(durees: list[float], duree_totale: float) -> tuple[float, dict]:
    """Note la plausibilité d'un découpage. Plus haut = plus crédible.

    Trois défauts sont pénalisés :
      · trop de micro-plans → le seuil attrape des flashs ou du texte ;
      · un plan qui couvre presque toute la vidéo → le seuil est trop sévère ;
      · une médiane hors du domaine du format court.
    """
    if not durees:
        return 0.0, {}

    n = len(durees)
    micro = sum(1 for d in durees if d < DUREE_MINIMALE_PLAN) / n
    plus_long = max(durees) / duree_totale
    med = median(durees)

    note = 1.0
    note *= max(0.0, 1.0 - micro * 3.0)          # 33 % de micro-plans → 0
    note *= max(0.0, 1.0 - max(0.0, plus_long - 0.35) * 2.0)

    # Le court format vit entre ~0,4 s et ~8 s par plan. En dehors, on doute.
    if med < 0.4:
        note *= med / 0.4
    elif med > 8.0:
        note *= 8.0 / med

    return note, {"micro": micro, "plus_long": plus_long, "mediane": med}


def detecter(chemin: Path, duree_totale: float, *,
             seuil_force: float | None = None) -> Decoupage:
    """Trouve les coupes, en calibrant le seuil sur la vidéo elle-même."""
    if not chemin.exists():
        raise ErreurPdz(f"Vidéo introuvable : {chemin}")
    if duree_totale <= 0:
        raise ErreurPdz("Durée de vidéo inconnue : impossible de calibrer.")

    if seuil_force is not None:
        coupes = _detecter(chemin, seuil_force, duree_totale)
        return Decoupage(seuil_force, coupes, _durees(coupes, duree_totale),
                         duree_totale)

    candidats = []
    for seuil in SEUILS:
        coupes = _detecter(chemin, seuil, duree_totale)
        durees = _durees(coupes, duree_totale)
        note, detail = _noter(durees, duree_totale)
        candidats.append({
            "seuil": seuil, "plans": len(durees), "note": round(note, 3),
            "mediane": round(detail.get("mediane", 0), 2),
            "micro": round(detail.get("micro", 0), 2),
            "_coupes": coupes, "_durees": durees,
        })
        # Un seuil très permissif qui produit déjà une majorité de micro-plans
        # ne fera qu'empirer : inutile de descendre plus bas.
        if detail.get("micro", 0) > 0.5:
            break

    # Départage des ex æquo : on prend le seuil le PLUS PERMISSIF.
    #
    # Les deux erreurs ne se valent pas. Un seuil trop sévère fusionne
    # silencieusement deux plans distincts — la vidéo paraît alors deux fois
    # plus lente qu'elle n'est, et rien ne le signale. Un seuil un peu trop
    # permissif ajoute une coupe visible, que la pénalité « micro-plans »
    # attrape déjà. Mesuré sur une vidéo réelle : 0,22 donnait 11 plans et
    # 0,16 en donnait 17, pour la même note — 11 était faux.
    note_max = max(c["note"] for c in candidats)
    exaequo = [c for c in candidats if c["note"] >= note_max - 1e-9]
    meilleur = min(exaequo, key=lambda c: c["seuil"])

    # Confiance : à quel point les seuils crédibles s'accordent sur le nombre
    # de plans. Deux résultats qui varient du simple au double méritent d'être
    # signalés plutôt que présentés comme un fait.
    plausibles = [c["plans"] for c in candidats if c["note"] >= note_max * 0.8]
    if len(plausibles) > 1 and max(plausibles):
        dispersion = (max(plausibles) - min(plausibles)) / max(plausibles)
        confiance = round(max(0.0, 1.0 - dispersion), 2)
    else:
        confiance = 1.0

    return Decoupage(
        seuil=meilleur["seuil"],
        coupes=meilleur["_coupes"],
        durees=meilleur["_durees"],
        duree_totale=duree_totale,
        confiance=confiance,
        candidats=[{k: v for k, v in c.items() if not k.startswith("_")}
                   for c in candidats],
    )
