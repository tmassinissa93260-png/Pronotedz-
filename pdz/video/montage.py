"""Le montage FFmpeg : images fixes → vraie vidéo.

Sans mouvement, une suite d'images est un diaporama. Avec un zoom lent, des
coupes calées et des sous-titres karaoké, c'est une vidéo. C'est ici que se
joue la différence entre du « slop » et quelque chose de regardable.

Aucun coût : tout tourne sur ma machine.

Voir docs/11-etat-de-lart.md et docs/12-videos-a-personnages.md.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from pdz.moteur.erreurs import ErreurConfig, ErreurPdz


class Mouvement(str, Enum):
    """Le mouvement appliqué à une image fixe.

    Alterner les mouvements évite l'effet hypnotique et répétitif d'un zoom
    avant identique sur tous les plans — c'est ce qui trahit la génération
    automatique au premier coup d'œil.
    """

    ZOOM_AVANT = "zoom_avant"
    ZOOM_ARRIERE = "zoom_arriere"
    PAN_GAUCHE = "pan_gauche"
    PAN_DROITE = "pan_droite"
    FIXE = "fixe"

    @classmethod
    def alterne(cls, index: int) -> Mouvement:
        cycle = [cls.ZOOM_AVANT, cls.PAN_DROITE, cls.ZOOM_ARRIERE, cls.PAN_GAUCHE]
        return cycle[index % len(cycle)]


@dataclass
class Plan:
    """Un plan du montage : une image, une durée, un mouvement.

    `image` peut être une image fixe ou un clip animé. Dans le second cas le
    mouvement est ignoré — le clip bouge déjà.
    """

    image: Path
    duree_s: float
    mouvement: Mouvement = Mouvement.ZOOM_AVANT
    anime: bool = False

    @property
    def frames(self) -> int:
        return max(1, round(self.duree_s * Montage.FPS))


@dataclass
class Montage:
    """Assemble les plans, la voix, la musique et les sous-titres."""

    LARGEUR: int = 1080
    HAUTEUR: int = 1920
    FPS: int = 30

    plans: list[Plan] = field(default_factory=list)
    voix: Path | None = None
    musique: Path | None = None
    sous_titres: Path | None = None       # fichier .ass

    # Volume de la musique sous la voix. -18 dB : présente mais jamais
    # concurrente. Au-delà, la voix devient fatigante.
    musique_db: float = -18.0

    @property
    def duree_s(self) -> float:
        return sum(p.duree_s for p in self.plans)

    # ── Construction de la commande ──────────────────────────────────────

    # Amplitude du mouvement. 15 % est perceptible sans donner le mal de mer ;
    # au-delà, ça fatigue sur vingt plans d'affilée.
    AMPLITUDE: float = 0.15

    def _filtre_mouvement(self, plan: Plan, index: int) -> str:
        """Le filtre qui fait bouger une image fixe.

        ⚠️ On n'utilise PAS `zoompan`, malgré ce que suggèrent la plupart des
        tutoriels. Mesuré sur ce projet : `zoompan` coûte **8 à 14 fois le temps
        réel** parce qu'il rééchantillonne toute l'image à chaque image/seconde.
        `crop` sur une fenêtre mobile fait le même effet à **0,33 fois le temps
        réel** — 25 à 40 fois plus rapide, pour un rendu équivalent.

        Sur un épisode de 45 s, c'est 15 secondes de rendu au lieu de 10 minutes.
        """
        L, H, fps = self.LARGEUR, self.HAUTEUR, self.FPS
        d = plan.duree_s

        if plan.anime:
            # Clip déjà animé : on cadre, on ajuste la durée, rien d'autre.
            return (
                f"[{index}:v]scale={L}:{H}:force_original_aspect_ratio=increase,"
                f"crop={L}:{H},setsar=1,fps={fps},trim=duration={d:.3f},"
                f"setpts=PTS-STARTPTS[v{index}]"
            )

        a = self.AMPLITUDE
        centre_x, centre_y = f"(iw-{L})/2", f"(ih-{H})/2"

        if plan.mouvement is Mouvement.PAN_DROITE:
            # Fenêtre de taille fixe qui glisse : aucun rééchantillonnage.
            corps = f"crop={L}:{H}:x='(iw-{L})*t/{d:.3f}':y='{centre_y}'"
        elif plan.mouvement is Mouvement.PAN_GAUCHE:
            corps = f"crop={L}:{H}:x='(iw-{L})*(1-t/{d:.3f})':y='{centre_y}'"
        elif plan.mouvement is Mouvement.ZOOM_AVANT:
            # Le zoom passe par un scale animé, puis un recadrage centré.
            corps = (
                f"scale='max({L},iw*(1+{a}*t/{d:.3f}))':-2:eval=frame,"
                f"crop={L}:{H}"
            )
        elif plan.mouvement is Mouvement.ZOOM_ARRIERE:
            corps = (
                f"scale='max({L},iw*(1+{a}-{a}*t/{d:.3f}))':-2:eval=frame,"
                f"crop={L}:{H}"
            )
        else:
            corps = f"crop={L}:{H}:x='{centre_x}':y='{centre_y}'"

        # setsar APRÈS le mouvement : le scale animé avec `-2` produit des
        # hauteurs arrondies, donc un ratio de pixel légèrement faux que
        # `concat` refuse ensuite. Le forcer en sortie règle le problème.
        return f"[{index}:v]{corps},setsar=1,fps={fps}[v{index}]"

    def _chaine_filtres(self) -> str:
        etapes = [self._filtre_mouvement(p, i) for i, p in enumerate(self.plans)]

        entrees = "".join(f"[v{i}]" for i in range(len(self.plans)))
        etapes.append(f"{entrees}concat=n={len(self.plans)}:v=1:a=0[vcat]")

        derniere = "vcat"
        if self.sous_titres:
            chemin = _echapper(self.sous_titres)
            etapes.append(f"[vcat]ass='{chemin}'[vsub]")
            derniere = "vsub"

        etapes.append(f"[{derniere}]format=yuv420p[v]")

        # ── Audio ────────────────────────────────────────────────────────
        i_voix = len(self.plans) if self.voix else None
        i_musique = (i_voix + 1 if i_voix is not None else len(self.plans)) \
            if self.musique else None

        if i_voix is not None and i_musique is not None:
            etapes.append(
                f"[{i_musique}:a]volume={self.musique_db}dB,"
                f"atrim=duration={self.duree_s:.3f},afade=t=out:st={max(0, self.duree_s - 1):.3f}:d=1[mus]"
            )
            etapes.append(
                f"[{i_voix}:a][mus]amix=inputs=2:duration=first:dropout_transition=0,"
                "loudnorm=I=-14:TP=-1.5:LRA=11[a]"
            )
        elif i_voix is not None:
            etapes.append(f"[{i_voix}:a]loudnorm=I=-14:TP=-1.5:LRA=11[a]")
        elif i_musique is not None:
            etapes.append(
                f"[{i_musique}:a]volume={self.musique_db}dB,"
                f"atrim=duration={self.duree_s:.3f},loudnorm=I=-14:TP=-1.5:LRA=11[a]"
            )

        return ";".join(etapes)

    def commande(self, sortie: Path) -> list[str]:
        if not self.plans:
            raise ErreurPdz("Montage vide : aucun plan.")

        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]

        for plan in self.plans:
            if not plan.image.exists():
                raise ErreurPdz(f"Image introuvable : {plan.image}")
            if plan.anime:
                cmd += ["-i", str(plan.image)]
            else:
                cmd += ["-loop", "1", "-t", f"{plan.duree_s:.3f}", "-i", str(plan.image)]

        if self.voix:
            cmd += ["-i", str(self.voix)]
        if self.musique:
            cmd += ["-stream_loop", "-1", "-i", str(self.musique)]

        cmd += ["-filter_complex", self._chaine_filtres(), "-map", "[v]"]
        if self.voix or self.musique:
            cmd += ["-map", "[a]", "-c:a", "aac", "-b:a", "192k"]

        cmd += [
            "-c:v", "libx264",
            "-preset", "veryfast",   # le rendu est le seul goulot CPU du système
            "-crf", "23",
            "-r", str(self.FPS),
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(sortie),
        ]
        return cmd

    # ── Exécution ────────────────────────────────────────────────────────

    def rendre(self, sortie: Path, *, timeout_s: int = 600) -> Path:
        if shutil.which("ffmpeg") is None:
            raise ErreurConfig(
                "ffmpeg est introuvable. Installe-le : "
                "`brew install ffmpeg` sur Mac, `apt install ffmpeg` sur Linux."
            )
        sortie.parent.mkdir(parents=True, exist_ok=True)

        r = subprocess.run(
            self.commande(sortie), capture_output=True, text=True, timeout=timeout_s
        )
        if r.returncode != 0:
            raise ErreurPdz(
                f"Le montage a échoué :\n{r.stderr[-1500:]}", detail=r.returncode
            )
        if not sortie.exists() or sortie.stat().st_size == 0:
            raise ErreurPdz("ffmpeg s'est terminé sans produire de fichier.")
        return sortie


# Les images sont agrandies de 35 % avant le montage : ça donne à la fenêtre
# de `crop` la place de se déplacer. C'est fait UNE fois par image (avec PIL),
# pas à chaque image/seconde par ffmpeg — d'où le gain de vitesse.
MARGE_MOUVEMENT: float = 1.35


def preparer_image(source: Path, destination: Path, *,
                   largeur: int = 1080, hauteur: int = 1920,
                   marge: float = MARGE_MOUVEMENT) -> Path:
    """Recadre et agrandit une image pour le format vertical, une fois pour toutes."""
    from PIL import Image

    cible_l, cible_h = round(largeur * marge), round(hauteur * marge)
    img = Image.open(source).convert("RGB")

    # Recadrage centré au bon rapport, puis mise à l'échelle.
    ratio_cible = cible_l / cible_h
    ratio = img.width / img.height
    if ratio > ratio_cible:
        nouvelle_l = round(img.height * ratio_cible)
        gauche = (img.width - nouvelle_l) // 2
        img = img.crop((gauche, 0, gauche + nouvelle_l, img.height))
    else:
        nouvelle_h = round(img.width / ratio_cible)
        haut = (img.height - nouvelle_h) // 2
        img = img.crop((0, haut, img.width, haut + nouvelle_h))

    img = img.resize((cible_l, cible_h), Image.LANCZOS)
    destination.parent.mkdir(parents=True, exist_ok=True)
    img.save(destination, quality=92)
    return destination


def repartir_plans(repliques: list[dict], durees_s: list[float],
                   images: list[Path], plans_par_replique: int = 2) -> list[Plan]:
    """Découpe les répliques en plans visuels, avec mouvements alternés.

    Une réplique = ~2 plans : celui qui parle, puis la réaction. C'est ce
    découpage qui donne le rythme de 2026 (un changement toutes les 1,5-2 s)
    sans écrire des répliques de cinq mots.
    """
    plans: list[Plan] = []
    curseur = 0

    for replique, duree in zip(repliques, durees_s, strict=True):
        nb = plans_par_replique if replique.get("reaction_de") else 1
        part = duree / nb
        for _ in range(nb):
            plans.append(Plan(
                image=images[curseur % len(images)],
                duree_s=part,
                mouvement=Mouvement.alterne(curseur),
            ))
            curseur += 1
    return plans


def _echapper(chemin: Path) -> str:
    """FFmpeg interprète `:` et `\\` dans les chemins de filtres."""
    return str(chemin).replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\'")
