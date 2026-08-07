"""Reproduit la FORME d'une vidéo de référence, avec un SUJET différent.

C'est la promesse du produit, exercée pour de vrai :

    forme (mesurée sur la vidéo de référence)   +   sujet à moi
    ────────────────────────────────────────────────────────────
    · style filaire blanc sur noir                  Spoutnik
    · plans lents (~3,9 s) mais caméra qui dérive   (la référence
    · UN mot à la fois, énorme, à 75 % de hauteur    parlait de voitures)
    · annotations techniques
    · narration documentaire

    python tools/demo_blueprint.py
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from blueprint import clip  # noqa: E402

from pdz.video import Montage, Plan, mots_depuis_texte  # noqa: E402
from pdz.video.soustitres import StyleSousTitres, generer_ass  # noqa: E402

SORTIE = Path("donnees/sorties")
TRAVAIL = Path("donnees/travail/blueprint")

# ── Le style, relevé sur la vidéo de référence ───────────────────────────
STYLE = StyleSousTitres(
    taille=150,             # mesuré : lettres ≈ 17 % de la hauteur
    position_ratio=0.75,    # mesuré : centre du texte à 75 % de la hauteur
    mots_par_carte=1,       # UN mot à la fois — la signature du format
    epaisseur_contour=6.0,
    couleur_active="&H00FFFFFF",     # tout blanc : pas de karaoké coloré ici
    couleur="&H00FFFFFF",
    majuscules=True,                 # relevé sur la référence
)

# ── Le script : même forme documentaire, sujet totalement différent ──────
NARRATION = [
    ("fusee",     "Le quatre octobre mille neuf cent cinquante-sept"),
    ("fusee",     "une sphère de cinquante-huit centimètres quitte la Terre."),
    ("satellite", "Spoutnik pèse quatre-vingt-trois kilos."),
    ("satellite", "Il ne sait faire qu'une seule chose."),
    ("satellite", "Émettre un bip."),
    ("globe",     "Un bip toutes les trois dixièmes de seconde."),
    ("globe",     "N'importe quel radioamateur peut l'entendre."),
    ("globe",     "Vingt et un jours plus tard, ses batteries meurent."),
    ("espace",    "Il continue de tourner. Silencieux. Pendant trois mois."),
    ("espace",    "Puis il brûle en rentrant dans l'atmosphère."),
    ("ville",     "Aujourd'hui, dix mille satellites passent au-dessus de toi."),
    ("ville",     "Tout ça a commencé par un bip."),
]

DEBIT_WPM = 155          # documentaire posé, pas TikTok survolté


def voix_factice(duree_s: float, chemin: Path) -> Path:
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", f"anoisesrc=d={duree_s:.3f}:c=brown:a=0.03",
         str(chemin)], check=True)
    return chemin


def main() -> int:
    TRAVAIL.mkdir(parents=True, exist_ok=True)
    SORTIE.mkdir(parents=True, exist_ok=True)

    # La durée de chaque plan découle du texte à dire, pas d'une valeur choisie.
    durees = [max(2.0, len(t.split()) / DEBIT_WPM * 60) for _, t in NARRATION]
    total = sum(durees)

    print("\n  FORME reprise de la référence · SUJET : Spoutnik")
    print(f"  {len(NARRATION)} segments · {total:.0f} s · "
          f"{total / len(NARRATION):.1f} s par plan\n")

    debut = time.perf_counter()
    plans: list[Plan] = []
    for i, ((scene, texte), duree) in enumerate(zip(NARRATION, durees, strict=True)):
        fichier = clip(scene, duree, TRAVAIL / f"{i:02d}.mp4")
        plans.append(Plan(image=fichier, duree_s=duree, anime=True))
        print(f"  ✓ plan {i + 1:2d}/{len(NARRATION)}  {scene:9s} {duree:4.1f} s  "
              f"« {texte[:44]}… »")

    print(f"\n  {len(plans)} plans rendus en {time.perf_counter() - debut:.0f} s")

    # Sous-titres : un mot à la fois, calé sur le texte réellement dit.
    mots, curseur = [], 0.0
    for (_, texte), duree in zip(NARRATION, durees, strict=True):
        mots += mots_depuis_texte(texte, round(curseur * 1000), round(duree * 1000))
        curseur += duree
    ass = TRAVAIL / "st.ass"
    ass.write_text(generer_ass(mots, style=STYLE), encoding="utf-8")
    print(f"  ✓ {len(mots)} mots, affichés un par un")

    fichier = SORTIE / "blueprint-spoutnik.mp4"
    print("\n  Montage…")
    t = time.perf_counter()
    Montage(plans=plans, voix=voix_factice(total, TRAVAIL / "voix.wav"),
            sous_titres=ass).rendre(fichier)

    print(f"\n  ✓ {fichier}")
    print(f"    {fichier.stat().st_size / 1024:.0f} Ko · "
          f"monté en {time.perf_counter() - t:.1f} s pour {total:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
