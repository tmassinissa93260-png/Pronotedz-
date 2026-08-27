"""Prototype : SUJET -> OPENAI -> STORYBOARD VALIDE -> (images, animations).

    python main.py                      depuis app/
    python -m app.main                  depuis prototype/

    python -m app.main analyser --shot 1 --image ...   analyse + animation
    python -m app.main produire                        images/videos (fal.ai)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Permet « python main.py » depuis app/, en plus de « python -m app.main ».
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "app"

from . import config, image_analyzer, validator  # noqa: E402
from .models import Storyboard, StoryboardError  # noqa: E402
from .openai_client import OpenAIError, generate_storyboard  # noqa: E402

PENDING, GENERATED, COMPLETED = "pending", "generated", "completed"


def log(tag: str, message: str = "") -> None:
    print(f"[{tag}] {message}".rstrip(), flush=True)


# ---------------------------------------------------------------------------
# Etat / reprise
# ---------------------------------------------------------------------------


def load_status(shot_count: int) -> dict:
    default = {f"shot_{i:02d}": PENDING for i in range(1, shot_count + 1)}
    if not config.STATUS_FILE.is_file():
        return default
    try:
        saved = json.loads(config.STATUS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default
    if isinstance(saved, dict):
        default.update({k: v for k, v in saved.items() if k in default})
    return default


def save_status(status: dict) -> None:
    config.STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.STATUS_FILE.write_text(
        json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def find_existing(shot_id: int, stem: str) -> Path | None:
    for path in sorted(config.shot_dir(shot_id).glob(f"{stem}.*")):
        if path.is_file() and path.suffix != ".txt":
            return path
    return None


# ---------------------------------------------------------------------------
# Affichage
# ---------------------------------------------------------------------------


def show_input(subject: str, duration: float, shot_count: int) -> None:
    log("INPUT")
    print(f"  {subject}")
    print(f"  {duration:g} secondes")
    print(f"  {shot_count} plans")
    print(flush=True)


def show_storyboard(sb: Storyboard) -> None:
    print()
    print("VISUAL BIBLE")
    for line in sb.visual_bible.as_block().splitlines():
        print(f"  {line}")
    for shot in sb.shots:
        print()
        print(f"  ── PLAN {shot.id:02d} ── {shot.duration_seconds:g}s "
              f"· {shot.word_count} mots · {shot.words_per_second:.1f} mot/s "
              f"· alignement {shot.semantic_alignment_score}")
        print(f"  Voix     : {shot.voice}")
        print(f"  Fonction : {shot.educational_function}")
        print(f"  Visible  : {_wrap(shot.visual_description)}")
        print(f"  Photo    : {_wrap(shot.image_prompt)}")
    print(flush=True)


def _wrap(text: str, width: int = 300) -> str:
    text = " ".join(text.split())
    return text if len(text) <= width else text[:width] + "…"


def show_problems(problems: list) -> None:
    for problem in problems:
        print(f"  ! {problem}", flush=True)


# ---------------------------------------------------------------------------
# ETAPE 1 : storyboard
# ---------------------------------------------------------------------------


def build_storyboard(subject: str, duration: float, shot_count: int) -> Storyboard:
    log("OPENAI", "Génération du script...")
    log("OPENAI", "Génération du storyboard...")

    def on_attempt(attempt: int, problems: list) -> None:
        log("VALIDATION", f"Vérification... (tentative {attempt})")
        if problems:
            log("CORRECTION", f"{len(problems)} point(s) à corriger, renvoi à OpenAI")
            show_problems(problems)

    storyboard, problems = generate_storyboard(subject, duration, shot_count,
                                               on_attempt=on_attempt)

    config.ensure_dirs(len(storyboard.shots))
    storyboard.save(config.PROJECT_FILE)
    for shot in storyboard.shots:
        directory = config.shot_dir(shot.id)
        (directory / "image_prompt.txt").write_text(shot.image_prompt + "\n", encoding="utf-8")
        (directory / "voice.txt").write_text(shot.voice + "\n", encoding="utf-8")

    if problems:
        log("ATTENTION", f"{len(problems)} point(s) non corrigé(s) après "
                         f"{config.MAX_REPAIR_ATTEMPTS} tentative(s) :")
        show_problems(problems)
    else:
        log("OK", f"{len(storyboard.shots)} plans validés")

    log("OUTPUT", str(config.PROJECT_FILE))
    return storyboard


def load_or_build(args) -> Storyboard:
    if config.PROJECT_FILE.is_file() and not getattr(args, "regenerate", False):
        try:
            storyboard = Storyboard.load(config.PROJECT_FILE)
            log("OK", f"Storyboard repris depuis {config.PROJECT_FILE}")
            return storyboard
        except StoryboardError as exc:
            log("ATTENTION", f"project.json inutilisable ({exc}), régénération")
    return build_storyboard(args.subject, args.duration, args.shots)


# ---------------------------------------------------------------------------
# Commandes
# ---------------------------------------------------------------------------


def cmd_storyboard(args) -> int:
    show_input(args.subject, args.duration, args.shots)
    storyboard = build_storyboard(args.subject, args.duration, args.shots)
    show_storyboard(storyboard)
    if config.TEST_MODE if args.test_mode is None else args.test_mode:
        log("TEST_MODE", "aucune génération d'image ni de vidéo")
    return 0


def cmd_analyser(args) -> int:
    """IMAGE -> ANALYSE -> PROMPT D'ANIMATION, sans navigateur."""
    storyboard = Storyboard.load(config.PROJECT_FILE)
    shot = storyboard.shot(args.shot)
    image = args.image
    if not str(image).startswith(("http://", "https://")):
        image = Path(image)

    config.ensure_dirs(len(storyboard.shots))
    directory = config.shot_dir(shot.id)

    log("OPENAI", f"Analyse image {shot.id:02d}...")
    analysis = image_analyzer.analyze_image(image)
    (directory / "image_analysis.json").write_text(
        json.dumps(analysis.__dict__, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log("OK", f"Analyse {shot.id:02d} : {', '.join(analysis.visible_subjects[:5])}")

    log("OPENAI", f"Prompt animation {shot.id:02d}...")
    plan = image_analyzer.generate_animation_prompt(shot, analysis)
    (directory / "animation.json").write_text(
        json.dumps(plan.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (directory / "animation_prompt.txt").write_text(
        plan.animation_prompt + "\n", encoding="utf-8")
    log("OK", f"Prompt animation {shot.id:02d} — intention : {plan.motion_intent}")

    print()
    print(f"  Intention   : {plan.motion_intent}")
    print(f"  Caméra      : {plan.camera_motion}")
    print(f"  Mécanique   : {plan.mechanical_motion}")
    print(f"  Énergie     : {plan.energy_motion}")
    print(f"  Préserver   : {', '.join(plan.preserve)}")
    print(f"  Interdit    : {', '.join(plan.forbidden)}")
    print()
    print("  --- PROMPT ANIMATION ---")
    print(f"  {plan.animation_prompt}")
    return 0


def cmd_produire(args) -> int:
    """Point d'integration images/videos : fal.ai. Aucun navigateur."""
    from . import fal_client

    show_input(args.subject, args.duration, args.shots)
    storyboard = load_or_build(args)
    config.ensure_dirs(len(storyboard.shots))
    status = load_status(len(storyboard.shots))

    animations_left = 0 if args.sans_video else args.max_animations
    log("COUT", "images seules, aucune dépense vidéo" if animations_left <= 0
        else f"jusqu'à {animations_left} animation(s) payante(s)")

    echecs = []
    for shot in storyboard.shots:
        key, directory = shot.slug, config.shot_dir(shot.id)
        print(f"\n[SHOT {shot.id:02d}]", flush=True)

        if status.get(key) == COMPLETED and not args.force:
            log("SKIP", "déjà terminé (status.json)")
            continue
        try:
            image_path = find_existing(shot.id, "image")
            if image_path and not args.force:
                log("SKIP", f"image déjà présente : {image_path}")
            else:
                log("FAL", f"Génération image {shot.id:02d}...")
                image_path = fal_client.generate_image(
                    shot.image_prompt, directory / "image.png")
                log("OK", f"Image {shot.id:02d} -> {image_path}")

            if animations_left <= 0:
                status[key] = GENERATED
                save_status(status)
                log("OK", "image seule (aucun budget d'animation)")
                continue

            log("OPENAI", f"Analyse image {shot.id:02d}...")
            analysis, plan = image_analyzer.animate(shot, image_path)
            (directory / "animation.json").write_text(
                json.dumps(plan.to_dict(), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8")
            (directory / "animation_prompt.txt").write_text(
                plan.animation_prompt + "\n", encoding="utf-8")
            log("OK", f"Prompt animation {shot.id:02d} — {plan.motion_intent}")

            log("FAL", f"Animation {shot.id:02d}...")
            video = fal_client.animate(image_path, plan.animation_prompt,
                                       shot.duration_seconds, directory / "video.mp4")
            animations_left -= 1
            log("OK", f"Vidéo {shot.id:02d} -> {video}")

            status[key] = COMPLETED
            save_status(status)
        except (fal_client.FalError, OpenAIError) as exc:
            log("ERREUR", str(exc).splitlines()[0])
            echecs.append((shot.id, str(exc)))
            save_status(status)

    print()
    if echecs:
        log("STOP", f"{len(echecs)} plan(s) en échec :")
        for shot_id, message in echecs:
            print(f"      SHOT {shot_id:02d} : {message}")
        return 6
    log("OK", "Terminé")
    return 0


def cmd_valider(args) -> int:
    """Rejoue les 10 vérifications sur le project.json déjà sauvegardé."""
    storyboard = Storyboard.load(config.PROJECT_FILE)
    log("VALIDATION", f"Vérification de {config.PROJECT_FILE}...")
    problems = validator.validate(storyboard, args.duration, args.shots)
    if problems:
        log("ÉCHEC", f"{len(problems)} point(s) :")
        show_problems(problems)
        return 1
    log("OK", f"{len(storyboard.shots)} plans validés")
    return 0


def cmd_status(args) -> int:
    print(json.dumps(load_status(args.shots), indent=2, ensure_ascii=False))
    return 0


def cmd_selfcheck(args) -> int:
    ok = True
    print("Configuration")
    print(f"  SUBJECT      : {config.SUBJECT}")
    print(f"  DURATION     : {config.DURATION}s")
    print(f"  SHOT_COUNT   : {config.SHOT_COUNT}")
    print(f"  TEST_MODE    : {config.TEST_MODE}")
    print(f"  cerveau      : {config.cerveau()}")
    print(f"  vision       : {config.OPENAI_VISION_MODEL}")
    print(f"  corrections  : {config.MAX_REPAIR_ATTEMPTS} au plus")
    print(f"  output       : {config.OUTPUT_DIR}")

    print("\nCerveau")
    if config.OPENAI_API_KEY:
        source = "GROQ_API_KEY" if config.USING_GROQ else "OPENAI_API_KEY"
        print(f"  {source} présente ({len(config.OPENAI_API_KEY)} caractères)")
    else:
        print("  OPENAI_API_KEY manquante dans .env")
        ok = False

    print(f"\nfal.ai (point d'intégration images/vidéos)\n  FAL_KEY : "
          f"{'présente' if config.FAL_KEY else 'absente'}")
    print("\n=> selfcheck", "OK" if ok else "INCOMPLET")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py", description="Sujet -> OpenAI -> storyboard validé -> images")
    sub = parser.add_subparsers(dest="command")

    def common(p):
        p.add_argument("--subject", default=config.SUBJECT)
        p.add_argument("--duration", type=float, default=config.DURATION)
        p.add_argument("--shots", type=int, default=config.SHOT_COUNT)
        return p

    p_story = common(sub.add_parser("storyboard", help="cerveau seul (défaut)"))
    p_story.add_argument("--test-mode", dest="test_mode", action="store_true", default=None)
    p_story.add_argument("--no-test-mode", dest="test_mode", action="store_false")
    p_story.set_defaults(func=cmd_storyboard)

    p_an = sub.add_parser("analyser", help="image -> analyse -> prompt d'animation")
    p_an.add_argument("--shot", type=int, required=True)
    p_an.add_argument("--image", required=True, help="fichier local ou URL http(s)")
    p_an.set_defaults(func=cmd_analyser)

    p_prod = common(sub.add_parser("produire", help="images/vidéos via fal.ai"))
    p_prod.add_argument("--regenerate", action="store_true")
    p_prod.add_argument("--force", action="store_true")
    p_prod.add_argument("--sans-video", dest="sans_video", action="store_true")
    p_prod.add_argument("--max-animations", type=int, default=config.SHOT_COUNT)
    p_prod.set_defaults(func=cmd_produire)

    p_val = common(sub.add_parser("valider", help="rejouer les 10 vérifications"))
    p_val.set_defaults(func=cmd_valider)

    p_st = sub.add_parser("status", help="afficher status.json")
    p_st.add_argument("--shots", type=int, default=config.SHOT_COUNT)
    p_st.set_defaults(func=cmd_status)

    sub.add_parser("selfcheck", help="vérifications hors ligne").set_defaults(func=cmd_selfcheck)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0].startswith("-"):
        argv = ["storyboard", *argv]        # « python main.py » tout court
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except OpenAIError as exc:
        print(f"\n[ERREUR OPENAI] {exc}", file=sys.stderr)
        return 2
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
