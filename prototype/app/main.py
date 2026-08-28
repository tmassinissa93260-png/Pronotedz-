"""Prototype semi-automatique.

    python main.py                              le storyboard complet
    python -m app.main elements                 tout exporter pour produire
    python -m app.main affiner --shot 1 --image X   image reelle -> animation
    python -m app.main analyser-videos          les videos rendues -> analyses
    python -m app.main timeline                 timeline + sous-titres
    python -m app.main montage                  MP4 final
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "app"

from . import analyzer, config, montage, validator  # noqa: E402
from .models import EXPLICATION_FIELDS, Storyboard, StoryboardError  # noqa: E402
from .openai_client import OpenAIError, generate_storyboard  # noqa: E402

EXTENSIONS_VIDEO = (".mp4", ".mov", ".webm", ".m4v")


def log(tag: str, message: str = "") -> None:
    print(f"[{tag}] {message}".rstrip(), flush=True)


def montrer_problemes(problems: list) -> None:
    for p in problems:
        print(f"  ! {p}", flush=True)


# ---------------------------------------------------------------------------
# ETAPE 1 : script, storyboard, visual bible, prompts
# ---------------------------------------------------------------------------


def construire(subject: str, duration: float, shot_count: int) -> Storyboard:
    log("INPUT")
    print(f"  {subject}\n  {duration:g} secondes\n  {shot_count} plans\n", flush=True)

    log("OPENAI", "Écriture du script...")
    log("OPENAI", "Storyboard, visual bible et prompts...")

    def a_chaque_tentative(numero: int, problems: list) -> None:
        log("VALIDATION", f"Vérification... (tentative {numero})")
        if problems:
            log("CORRECTION", f"{len(problems)} point(s) à corriger, renvoi à OpenAI")
            montrer_problemes(problems)

    sb, problems = generate_storyboard(subject, duration, shot_count,
                                       on_attempt=a_chaque_tentative)
    config.ensure_dirs(len(sb.shots))
    sb.save(config.PROJECT_FILE)

    if problems:
        log("ATTENTION", f"{len(problems)} point(s) non corrigé(s) après "
                         f"{config.MAX_REPAIR_ATTEMPTS} tentative(s) :")
        montrer_problemes(problems)
    else:
        log("OK", f"{len(sb.shots)} plans validés")
    log("OUTPUT", str(config.PROJECT_FILE))
    return sb


def charger() -> Storyboard:
    return Storyboard.load(config.PROJECT_FILE)


# ---------------------------------------------------------------------------
# ETAPE 2 : tout remettre a l'utilisateur
# ---------------------------------------------------------------------------


def ecrire_elements(sb: Storyboard) -> Path:
    """Une feuille unique : script, bible, et pour chaque plan les deux prompts."""
    lignes = [
        f"# {sb.subject}",
        "",
        f"{sb.duration_seconds:g} secondes · {sb.shot_count} plans",
        "",
        "## Script",
        "",
        sb.script,
        "",
        "## Visual bible",
        "",
        "À réutiliser dans **chaque** image. Les couleurs ont un sens fixe.",
        "",
    ]
    lignes += [f"- **{c.replace('_', ' ')}** : {getattr(sb.visual_bible, c)}"
               for c in sb.visual_bible.__dataclass_fields__]
    lignes += ["", "## Contrôle qualité", ""]
    lignes += [f"- {axe.replace('_', ' ')} : {note}" for axe, note in sb.quality_check.items()]

    for s in sb.shots:
        lignes += [
            "", "---", "",
            f"## Plan {s.id:02d} — {s.duration_seconds:g}s",
            "",
            f"**Voix** : {s.voice}",
            "",
            f"**Fonction** : {s.educational_function}",
            "",
            f"**Élément pédagogique** : {s.visual_concept}",
            "",
            f"**Intention de mouvement** : `{s.motion_intent}`",
            "",
            "### Le raisonnement, avant le prompt",
            "",
        ]
        lignes += [f"{n}. **{champ.replace('_', ' ')}** : "
                   f"{s.visual_explanation.get(champ, '')}"
                   for n, champ in enumerate(EXPLICATION_FIELDS, start=1)]
        lignes += [
            "",
            "### Prompt image", "", "```", s.image_prompt, "```",
            "",
            "### Prompt animation", "", "```", s.animation_prompt, "```",
        ]

    lignes += [
        "", "---", "",
        "## Ce que tu fais maintenant",
        "",
        "1. Génère chaque **image** avec l'outil de ton choix, à partir du prompt image.",
        "2. Génère chaque **animation** à partir de ton image, avec le prompt animation.",
        f"3. Dépose les vidéos dans `{config.VIDEOS_DIR}` nommées `shot_01.mp4`, "
        "`shot_02.mp4`…",
        "4. Reviens : `analyser-videos`, puis `timeline`, puis `montage`.",
        "",
    ]
    config.ELEMENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.ELEMENTS_FILE.write_text("\n".join(lignes), encoding="utf-8")

    for s in sb.shots:
        d = config.shot_dir(s.id)
        d.mkdir(parents=True, exist_ok=True)
        (d / "image_prompt.txt").write_text(s.image_prompt + "\n", encoding="utf-8")
        (d / "animation_prompt.txt").write_text(s.animation_prompt + "\n", encoding="utf-8")
        (d / "voice.txt").write_text(s.voice + "\n", encoding="utf-8")
    return config.ELEMENTS_FILE


# ---------------------------------------------------------------------------
# Videos deposees par l'utilisateur
# ---------------------------------------------------------------------------


def trouver_videos(sb: Storyboard) -> dict[int, Path]:
    trouvees: dict[int, Path] = {}
    if not config.VIDEOS_DIR.is_dir():
        return trouvees
    for s in sb.shots:
        for ext in EXTENSIONS_VIDEO:
            for motif in (f"shot_{s.id:02d}{ext}", f"{s.id:02d}{ext}", f"{s.id}{ext}"):
                candidat = config.VIDEOS_DIR / motif
                if candidat.is_file():
                    trouvees[s.id] = candidat
                    break
            if s.id in trouvees:
                break
    return trouvees


def charger_analyses(sb: Storyboard) -> dict:
    from .models import VideoAnalysis

    analyses = {}
    for s in sb.shots:
        fichier = config.shot_dir(s.id) / "video_analysis.json"
        if fichier.is_file():
            brut = json.loads(fichier.read_text(encoding="utf-8"))
            analyses[s.id] = VideoAnalysis(**brut)
    return analyses


# ---------------------------------------------------------------------------
# Commandes
# ---------------------------------------------------------------------------


def cmd_storyboard(args) -> int:
    sb = construire(args.subject, args.duration, args.shots)
    chemin = ecrire_elements(sb)
    print()
    print("VISUAL BIBLE")
    for ligne in sb.visual_bible.as_block().splitlines():
        print(f"  {ligne}")
    print()
    print("SCRIPT")
    print(f"  {sb.script}")
    for s in sb.shots:
        print()
        print(f"  ── PLAN {s.id:02d} ── {s.duration_seconds:g}s · {s.word_count} mots "
              f"· {s.words_per_second:.1f} mot/s · {s.motion_intent}")
        print(f"  Voix     : {s.voice}")
        print(f"  Concept  : {s.visual_concept}")
        print(f"  Fonction : {s.educational_function}")
    print()
    log("OUTPUT", str(chemin))
    log("TEST_MODE", "aucune image, aucune vidéo générée — c'est toi qui produis")
    return 0


def cmd_elements(args) -> int:
    sb = charger()
    log("OUTPUT", str(ecrire_elements(sb)))
    for s in sb.shots:
        print(f"  plan {s.id:02d} : {config.shot_dir(s.id)}")
    return 0


def cmd_affiner(args) -> int:
    """Une image REELLE -> ce qu'elle contient -> prompt d'animation ajuste."""
    sb = charger()
    shot = sb.shot(args.shot)
    image = args.image if str(args.image).startswith(("http://", "https://")) \
        else Path(args.image)
    dossier = config.shot_dir(shot.id)
    dossier.mkdir(parents=True, exist_ok=True)

    log("OPENAI", f"Analyse de l'image du plan {shot.id:02d}...")
    analyse = analyzer.analyze_image(image, shot.visual_concept)
    (dossier / "image_analysis.json").write_text(
        json.dumps(analyse, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    visible = analyse.get("pedagogical_element_visible")
    log("OK", f"Élément pédagogique visible : {visible}")
    if visible is False:
        log("ATTENTION", analyse.get("pedagogical_element_note", ""))

    log("OPENAI", "Prompt d'animation ajusté à cette image...")
    plan = analyzer.refine_animation(shot, analyse)
    (dossier / "animation.json").write_text(
        json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (dossier / "animation_prompt.txt").write_text(
        plan["animation_prompt"] + "\n", encoding="utf-8")
    log("OK", f"Intention : {plan['motion_intent']}")
    print()
    print(plan["animation_prompt"])
    return 0


def cmd_analyser_videos(args) -> int:
    sb = charger()
    videos = trouver_videos(sb)
    if not videos:
        log("STOP", f"aucune vidéo trouvée dans {config.VIDEOS_DIR}")
        print("  Nomme-les shot_01.mp4, shot_02.mp4, … puis relance.")
        return 1

    echecs = []
    for s in sb.shots:
        video = videos.get(s.id)
        if video is None:
            log("MANQUE", f"plan {s.id:02d} : aucune vidéo")
            continue
        dossier = config.shot_dir(s.id)
        dossier.mkdir(parents=True, exist_ok=True)
        log("OPENAI", f"Analyse de la vidéo {s.id:02d} ({video.name})...")
        try:
            analyse = analyzer.analyze_video(s, video, dossier)
        except OpenAIError as exc:
            log("ERREUR", str(exc).splitlines()[0])
            echecs.append((s.id, str(exc)))
            continue
        (dossier / "video_analysis.json").write_text(
            json.dumps(analyse.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
        etat = "conforme" if analyse.matches_plan else "NON CONFORME"
        log("OK", f"Vidéo {s.id:02d} — {analyse.measured_duration or '?'}s — {etat}")
        for defaut in analyse.defects:
            print(f"      défaut : {defaut}")
    return 6 if echecs else 0


def cmd_timeline(args) -> int:
    sb = charger()
    videos = trouver_videos(sb)
    manquants = [s.id for s in sb.shots if s.id not in videos]
    if manquants:
        log("STOP", f"vidéo manquante pour le(s) plan(s) : "
                    f"{', '.join(f'{i:02d}' for i in manquants)}")
        print(f"  Dépose-les dans {config.VIDEOS_DIR}")
        return 1

    entrees = montage.construire_timeline(sb, videos, charger_analyses(sb))
    montage.sauver_timeline(entrees, config.TIMELINE_FILE)
    config.SRT_FILE.write_text(montage.sous_titres(entrees), encoding="utf-8")

    print()
    print("  Plan   Début     Fin      Durée   Ajustement")
    for e in entrees:
        print(f"  {e.shot_id:02d}     {e.start:6.2f}s  {e.end:6.2f}s  "
              f"{e.duration:5.2f}s  {e.ajustement}")
        for r in e.remarques:
            print(f"           ! {r}")
    print()
    log("OUTPUT", str(config.TIMELINE_FILE))
    log("OUTPUT", str(config.SRT_FILE))
    return 0


def cmd_montage(args) -> int:
    sb = charger()
    videos = trouver_videos(sb)
    manquants = [s.id for s in sb.shots if s.id not in videos]
    if manquants:
        log("STOP", f"vidéo manquante pour le(s) plan(s) : "
                    f"{', '.join(f'{i:02d}' for i in manquants)}")
        return 1

    entrees = montage.construire_timeline(sb, videos, charger_analyses(sb))
    montage.sauver_timeline(entrees, config.TIMELINE_FILE)
    config.SRT_FILE.write_text(montage.sous_titres(entrees), encoding="utf-8")

    voix = config.VOICE_FILE if config.VOICE_FILE.is_file() else None
    musique = config.MUSIC_FILE if config.MUSIC_FILE.is_file() else None
    log("MONTAGE", f"{len(entrees)} plans · voix : {'oui' if voix else 'non'} · "
                   f"musique : {'oui' if musique else 'non'} · sous-titres : oui")
    sortie = montage.assembler(entrees, config.FINAL_FILE, voix, musique,
                               config.SRT_FILE if not args.sans_sous_titres else None)
    log("OK", f"MP4 final -> {sortie}")
    return 0


def cmd_valider(args) -> int:
    sb = charger()
    log("VALIDATION", f"Vérification de {config.PROJECT_FILE}...")
    problems = validator.validate(sb, args.duration, args.shots)
    if problems:
        log("ÉCHEC", f"{len(problems)} point(s) :")
        montrer_problemes(problems)
        return 1
    log("OK", f"{len(sb.shots)} plans validés")
    return 0


def cmd_selfcheck(args) -> int:
    ok = True
    print("Configuration")
    print(f"  SUBJECT     : {config.SUBJECT}")
    print(f"  DURATION    : {config.DURATION}s")
    print(f"  SHOT_COUNT  : {config.SHOT_COUNT}")
    print(f"  cerveau     : {config.cerveau()}")
    print(f"  vision      : {config.OPENAI_VISION_MODEL}")
    print(f"  corrections : {config.MAX_REPAIR_ATTEMPTS} au plus")
    print(f"  vidéos      : {config.VIDEOS_DIR}")

    print("\nCerveau")
    if config.OPENAI_API_KEY:
        source = "GROQ_API_KEY" if config.USING_GROQ else "OPENAI_API_KEY"
        print(f"  {source} présente ({len(config.OPENAI_API_KEY)} caractères)")
    else:
        print("  OPENAI_API_KEY manquante dans .env")
        ok = False

    print("\nffmpeg (montage et analyse vidéo)")
    try:
        montage.exiger_ffmpeg()
        print("  ffmpeg et ffprobe présents")
    except montage.MontageError as exc:
        print(f"  {str(exc).splitlines()[0]}")
        print("  storyboard et prompts fonctionnent sans ; montage et analyse vidéo non.")

    print("\n=> selfcheck", "OK" if ok else "INCOMPLET")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Sujet -> script, storyboard, prompts -> tu produis -> montage")
    sub = parser.add_subparsers(dest="command")

    def commun(p):
        p.add_argument("--subject", default=config.SUBJECT)
        p.add_argument("--duration", type=float, default=config.DURATION)
        p.add_argument("--shots", type=int, default=config.SHOT_COUNT)
        return p

    commun(sub.add_parser("storyboard", help="script, bible, plans, prompts")
           ).set_defaults(func=cmd_storyboard)
    sub.add_parser("elements", help="tout réexporter pour produire"
                   ).set_defaults(func=cmd_elements)

    p_aff = sub.add_parser("affiner", help="image réelle -> prompt d'animation ajusté")
    p_aff.add_argument("--shot", type=int, required=True)
    p_aff.add_argument("--image", required=True, help="fichier local ou URL http(s)")
    p_aff.set_defaults(func=cmd_affiner)

    sub.add_parser("analyser-videos", help="analyser les vidéos déposées"
                   ).set_defaults(func=cmd_analyser_videos)
    sub.add_parser("timeline", help="timeline + sous-titres").set_defaults(func=cmd_timeline)

    p_mon = sub.add_parser("montage", help="assembler le MP4 final")
    p_mon.add_argument("--sans-sous-titres", dest="sans_sous_titres", action="store_true")
    p_mon.set_defaults(func=cmd_montage)

    commun(sub.add_parser("valider", help="rejouer les vérifications")
           ).set_defaults(func=cmd_valider)
    sub.add_parser("selfcheck", help="état de la configuration").set_defaults(func=cmd_selfcheck)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0].startswith("-"):
        argv = ["storyboard", *argv]
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except OpenAIError as exc:
        print(f"\n[ERREUR OPENAI] {exc}", file=sys.stderr)
        return 2
    except montage.MontageError as exc:
        print(f"\n[ERREUR MONTAGE] {exc}", file=sys.stderr)
        return 3
    except StoryboardError as exc:
        print(f"\n[ERREUR STORYBOARD] {exc}", file=sys.stderr)
        return 5
    except KeyError as exc:
        print(f"\n[ERREUR] {exc.args[0] if exc.args else exc}", file=sys.stderr)
        return 5
    except KeyboardInterrupt:
        print("\n[STOP] interrompu.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
