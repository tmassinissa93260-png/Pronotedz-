"""Un épisode complet de « Fruit Island », entièrement animé.

Chaîne exercée de bout en bout, sans appeler aucune IA :

    script dialogué  →  clips animés  →  découpage en plans
                     →  sous-titres karaoké  →  montage  →  MP4

Les clips sont dessinés par tools/personnages.py au lieu d'être générés par
FLUX puis animés par Kling. Tout le reste est le vrai code du projet.

    python tools/demo_episode_anime.py
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from personnages import clip_parle  # noqa: E402

from pdz.univers import Univers  # noqa: E402
from pdz.video import Montage, Plan, generer_ass, mots_depuis_texte  # noqa: E402

SORTIE = Path("donnees/sorties")
TRAVAIL = Path("donnees/travail/episode")

# Ce que le ScriptWriter produirait : des répliques, pas des plans.
SCRIPT = [
    ("strawberina", "Tu savais depuis le début.", "colere"),
    ("bananito", "Attends. C'est pas ce que tu crois.", "peur"),
    ("avocado", "Mmh. On va dire ça.", "mepris"),
    ("strawberina", "Trois semaines à me mentir en face.", "colere"),
    ("bananito", "J'y peux rien si elle m'a parlé.", "gene"),
    ("avocado", "Il vient de se griller tout seul.", "calme"),
]

DUREE_REPLIQUE = 2.6
PART_PARLANT = 0.6      # 60 % sur celui qui parle, 40 % sur la réaction


def voix_factice(duree_s: float, chemin: Path) -> Path:
    """Remplace ElevenLabs — un souffle de la bonne durée."""
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", f"anoisesrc=d={duree_s:.3f}:c=pink:a=0.05",
         str(chemin)],
        check=True,
    )
    return chemin


def main() -> int:
    TRAVAIL.mkdir(parents=True, exist_ok=True)
    SORTIE.mkdir(parents=True, exist_ok=True)

    univers = Univers.charger(Path("univers/fruit-island.yaml"))
    casting = [p.id for p in univers.personnages]
    total_s = DUREE_REPLIQUE * len(SCRIPT)

    print(f"\n  {univers.nom} — épisode animé")
    print(f"  {len(SCRIPT)} répliques · {total_s:.0f} s · casting : {', '.join(casting)}\n")

    # ── 1. Les clips animés (remplace FLUX + Kling) ──────────────────────
    debut = time.perf_counter()
    plans: list[Plan] = []

    for i, (perso, _texte, emotion) in enumerate(SCRIPT):
        # Plan A — celui qui parle, bouche animée.
        d_parle = DUREE_REPLIQUE * PART_PARLANT
        clip_a = clip_parle(perso, emotion, d_parle, TRAVAIL / f"{i:02d}a.mp4")
        plans.append(Plan(image=clip_a, duree_s=d_parle, anime=True))

        # Plan B — la réaction de l'autre. C'est ce contre-champ qui donne le
        # rythme de montage sans allonger le dialogue.
        temoin = casting[(casting.index(perso) + 1) % len(casting)]
        d_reaction = DUREE_REPLIQUE - d_parle
        clip_b = clip_parle(temoin, "surprise" if emotion == "colere" else "calme",
                            d_reaction, TRAVAIL / f"{i:02d}b.mp4", echelle=1.25)
        plans.append(Plan(image=clip_b, duree_s=d_reaction, anime=True))

        print(f"  ✓ réplique {i + 1}/{len(SCRIPT)} — {perso} ({emotion}) "
              f"puis réaction de {temoin}")

    print(f"\n  {len(plans)} plans animés en {time.perf_counter() - debut:.0f} s "
          f"({total_s / len(plans):.2f} s par changement visuel)")

    # ── 2. Sous-titres karaoké ───────────────────────────────────────────
    mots = []
    for i, (_, texte, _) in enumerate(SCRIPT):
        mots += mots_depuis_texte(texte, round(i * DUREE_REPLIQUE * 1000),
                                  round(DUREE_REPLIQUE * 1000))
    ass = TRAVAIL / "soustitres.ass"
    ass.write_text(generer_ass(mots), encoding="utf-8")
    print(f"  ✓ {len(mots)} mots karaoké")

    # ── 3. Montage ───────────────────────────────────────────────────────
    voix = voix_factice(total_s, TRAVAIL / "voix.wav")
    fichier = SORTIE / "episode-anime.mp4"

    print("\n  Montage…")
    t = time.perf_counter()
    Montage(plans=plans, voix=voix, sous_titres=ass).rendre(fichier)
    rendu = time.perf_counter() - t

    print(f"\n  ✓ {fichier}")
    print(f"    {fichier.stat().st_size / 1024:.0f} Ko · monté en {rendu:.1f} s "
          f"pour {total_s:.0f} s de vidéo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
