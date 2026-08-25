"""Fabrique une vraie vidéo sans appeler aucune IA.

Sert à vérifier la chaîne de montage — mouvement, coupes, sous-titres
karaoké, audio — avant de dépenser un centime en génération d'images.
Les images sont des dégradés colorés fabriqués sur place.

    python tools/demo_montage.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402

from pdz.video import (  # noqa: E402
    Montage,
    Mouvement,
    Plan,
    generer_ass,
    mots_depuis_texte,
)
from pdz.video.montage import MARGE_MOUVEMENT  # noqa: E402

SORTIE = Path("donnees/sorties")
TRAVAIL = Path("donnees/travail/demo")

# Un extrait de « Fruit Island » : ce que le Script Writer produirait.
REPLIQUES = [
    ("strawberina", "Tu savais depuis le début.", "colere"),
    ("bananito", "Attends, c'est pas ce que tu crois.", "peur"),
    ("avocado", "Mmh. On va dire ça.", "mepris"),
    ("strawberina", "Trois semaines à me mentir en face.", "colere"),
    ("bananito", "J'y peux rien si elle m'a parlé.", "gene"),
    ("avocado", "Il vient de se griller tout seul.", "calme"),
]

COULEURS = {
    "strawberina": ((220, 30, 70), (120, 10, 40)),
    "bananito": ((250, 210, 60), (180, 130, 20)),
    "avocado": ((60, 130, 70), (20, 60, 35)),
}


def fabriquer_image(perso: str, texte: str, chemin: Path) -> Path:
    """Un dégradé aux couleurs du personnage — remplace l'image FLUX."""
    haut, bas = COULEURS[perso]
    # Agrandies dès la fabrication : c'est ce qui donne à la fenêtre de crop
    # la place de bouger, sans que ffmpeg ait à rééchantillonner par image.
    L, H = round(1080 * MARGE_MOUVEMENT), round(1920 * MARGE_MOUVEMENT)
    img = Image.new("RGB", (L, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line(
            [(0, y), (L, y)],
            fill=tuple(round(h + (b - h) * t) for h, b in zip(haut, bas, strict=True)),
        )
    d.ellipse([L * 0.22, H * 0.29, L * 0.78, H * 0.60], outline=(255, 255, 255), width=10)
    d.text((90, 180), perso.upper(), fill=(255, 255, 255))
    d.text((90, 240), texte[:44], fill=(255, 255, 255))
    chemin.parent.mkdir(parents=True, exist_ok=True)
    img.save(chemin, quality=92)
    return chemin


def fabriquer_voix(duree_s: float, chemin: Path) -> Path:
    """Un bourdonnement de la bonne durée — remplace ElevenLabs."""
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", f"sine=frequency=180:duration={duree_s:.3f}",
         "-af", "volume=-24dB", str(chemin)],
        check=True,
    )
    return chemin


def main() -> int:
    TRAVAIL.mkdir(parents=True, exist_ok=True)
    SORTIE.mkdir(parents=True, exist_ok=True)

    duree_replique = 3.0
    duree_totale = duree_replique * len(REPLIQUES)

    print(f"\n  Épisode de démonstration — {len(REPLIQUES)} répliques, "
          f"{duree_totale:.0f} s\n")

    # 1. Les images (une par personnage qui parle)
    images = [
        fabriquer_image(perso, texte, TRAVAIL / f"plan_{i:02d}.jpg")
        for i, (perso, texte, _) in enumerate(REPLIQUES)
    ]
    print(f"  ✓ {len(images)} images fabriquées")

    # 2. Les plans : 2 par réplique (celui qui parle, puis la réaction),
    #    avec des mouvements alternés.
    plans: list[Plan] = []
    for i in range(len(REPLIQUES)):
        for moitie in range(2):
            plans.append(Plan(
                image=images[(i + moitie) % len(images)],
                duree_s=duree_replique / 2,
                mouvement=Mouvement.alterne(len(plans)),
            ))
    print(f"  ✓ {len(plans)} plans de {plans[0].duree_s:.2f} s "
          f"({duree_totale / len(plans):.2f} s par changement visuel)")

    # 3. Les sous-titres karaoké
    mots = []
    for i, (_, texte, _) in enumerate(REPLIQUES):
        mots += mots_depuis_texte(
            texte, round(i * duree_replique * 1000), round(duree_replique * 1000)
        )
    ass = TRAVAIL / "soustitres.ass"
    ass.write_text(generer_ass(mots), encoding="utf-8")
    print(f"  ✓ {len(mots)} mots karaoké")

    # 4. L'audio
    voix = fabriquer_voix(duree_totale, TRAVAIL / "voix.wav")
    print("  ✓ piste audio")

    # 5. Le montage
    montage = Montage(plans=plans, voix=voix, sous_titres=ass)
    fichier = SORTIE / "demo-fruit-island.mp4"
    print("\n  Rendu en cours…")

    import time
    debut = time.perf_counter()
    montage.rendre(fichier)
    duree_rendu = time.perf_counter() - debut

    taille = fichier.stat().st_size / 1024
    print(f"\n  ✓ {fichier}")
    print(f"    {taille:.0f} Ko · rendu en {duree_rendu:.1f} s "
          f"pour {duree_totale:.0f} s de vidéo "
          f"(×{duree_rendu / duree_totale:.1f} le temps réel)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
