"""Orchestrateur du prototype.

    python -m app.main storyboard   # ETAPE 2+3 : OpenAI seul, aucun navigateur
    python -m app.main run          # boucle complete (TEST_MODE decide de l'arret)
    python -m app.main selfcheck    # verifications hors ligne
    python -m app.main status       # ou en est-on
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import browser, config, fal_client, meta_ai, openai_client
from .models import Shot, Storyboard, StoryboardError

PENDING, GENERATED, COMPLETED = "pending", "generated", "completed"


# ---------------------------------------------------------------------------
# Logs (ETAPE 8)
# ---------------------------------------------------------------------------


def log(tag: str, message: str = "") -> None:
    print(f"[{tag}] {message}".rstrip(), flush=True)


def shot_header(shot_id: int) -> None:
    print(flush=True)
    print(f"[SHOT {shot_id:02d}]", flush=True)


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
    """image.* ou video.* deja presents dans le dossier du plan."""
    for path in sorted(config.shot_dir(shot_id).glob(f"{stem}.*")):
        if path.is_file() and path.suffix != ".txt":
            return path
    return None


# ---------------------------------------------------------------------------
# ETAPE 2 + 3 : storyboard et sauvegarde
# ---------------------------------------------------------------------------


def build_storyboard(subject: str, duration: int, shot_count: int) -> Storyboard:
    log("OPENAI", "Génération du storyboard...")
    storyboard = openai_client.generate_storyboard(subject, duration, shot_count)

    config.ensure_dirs(shot_count)
    storyboard.save(config.PROJECT_FILE)
    for shot in storyboard.shots:
        (config.shot_dir(shot.id) / "image_prompt.txt").write_text(
            shot.image_prompt + "\n", encoding="utf-8"
        )
        (config.shot_dir(shot.id) / "voice.txt").write_text(shot.voice + "\n", encoding="utf-8")

    write_paste_sheet(storyboard)

    log("OK", "Storyboard créé")
    print(f"      -> {config.PROJECT_FILE}", flush=True)
    print(f"      -> {config.PASTE_SHEET}", flush=True)
    return storyboard


def write_paste_sheet(storyboard: Storyboard) -> Path:
    """Une feuille unique a lire au telephone et a coller dans Meta AI."""
    lines = [
        "PROMPTS A COLLER DANS META AI",
        f"Sujet  : {storyboard.subject}",
        f"Duree  : {storyboard.duration}s en {len(storyboard.shots)} plans",
        f"Lien   : {config.META_AI_URL}",
        "",
        "Colle chaque bloc PROMPT PHOTO dans Meta AI, un par un.",
        "",
    ]
    for shot in storyboard.shots:
        lines += [
            "=" * 70,
            f"SHOT {shot.id:02d}  ({shot.duration})",
            "=" * 70,
            "",
            f"VOIX : {shot.voice}",
            "",
            "--- PROMPT PHOTO -------------------------------------------------",
            shot.image_prompt,
            "------------------------------------------------------------------",
            "",
        ]
    config.PASTE_SHEET.parent.mkdir(parents=True, exist_ok=True)
    config.PASTE_SHEET.write_text("\n".join(lines), encoding="utf-8")
    return config.PASTE_SHEET


def load_or_build_storyboard(args) -> Storyboard:
    """Reprend project.json s'il existe, sinon interroge OpenAI."""
    if config.PROJECT_FILE.is_file() and not args.regenerate:
        try:
            storyboard = Storyboard.load(config.PROJECT_FILE)
            log("OK", f"Storyboard repris depuis {config.PROJECT_FILE}")
            return storyboard
        except StoryboardError as exc:
            log("WARN", f"project.json inutilisable ({exc}), regeneration")
    return build_storyboard(args.subject, args.duration, args.shots)


# ---------------------------------------------------------------------------
# ETAPE 5 : prompt photo -> Meta AI
# ---------------------------------------------------------------------------


def do_photo(page, shot: Shot, stop_after_submit: bool = False) -> Path | None:
    log("PHOTO", "Préparation du prompt...")
    directory = config.shot_dir(shot.id)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "image_prompt.txt").write_text(shot.image_prompt + "\n", encoding="utf-8")

    log("META AI", "Ouverture de la page...")
    meta_ai.open_prompt_page(page)
    meta_ai.ensure_ready(page)

    before = meta_ai.count_media(page, "image")

    log("META AI", "Collage du prompt...")
    meta_ai.paste_prompt(page, shot.image_prompt)
    meta_ai.submit(page)

    if stop_after_submit:
        # TEST_MODE : l'objectif est de prouver le copier/coller, rien de plus.
        return None

    log("META AI", "Génération...")
    if not meta_ai.wait_for_new_media(page, "image", before):
        log("WARN", "aucune nouvelle image detectee automatiquement")

    saved = meta_ai.download_latest_media(page, "image", directory, "image")
    if saved:
        log("OK", f"Image {shot.id:02d}  -> {saved}")
        return saved

    # Le telechargement automatique ne doit jamais bloquer le prototype.
    log("WARN", "telechargement automatique impossible depuis l'interface")
    browser.pause(
        f"Enregistre l'image du plan {shot.id:02d} a la main dans :\n"
        f"    {directory / 'image.png'}\n"
        "puis appuie sur Entrée (ou Entrée seule pour marquer le plan comme "
        "'generated' sans fichier)."
    )
    saved = find_existing(shot.id, "image")
    if saved:
        log("OK", f"Image {shot.id:02d}  -> {saved}")
    else:
        log("OK", f"Image {shot.id:02d} marquee 'generated' (pas de fichier local)")
    return saved


# ---------------------------------------------------------------------------
# ETAPE 6 : analyse de l'image -> prompt d'animation
# ---------------------------------------------------------------------------


def do_animation_prompt(shot: Shot, image: Path | str) -> str:
    log("OPENAI", f"Analyse image {shot.id:02d}...")
    animation_prompt = openai_client.build_animation_prompt(image, shot)
    target = config.shot_dir(shot.id) / "animation_prompt.txt"
    target.write_text(animation_prompt + "\n", encoding="utf-8")
    log("OK", f"Prompt animation {shot.id:02d}")
    return animation_prompt


# ---------------------------------------------------------------------------
# ETAPE 7 : image + prompt d'animation -> Meta AI
# ---------------------------------------------------------------------------


def do_animation(page, shot: Shot, image_path: Path, animation_prompt: str) -> Path | None:
    directory = config.shot_dir(shot.id)

    log("META AI", f"Ajout image {shot.id:02d}...")
    meta_ai.open_prompt_page(page)
    meta_ai.ensure_ready(page)
    if not meta_ai.attach_image(page, image_path):
        browser.save_debug_state(page, f"shot{shot.id:02d}-ajout-image")
        browser.pause(
            f"Aucun champ d'import de fichier trouve dans l'interface.\n"
            f"Ajoute l'image a la main dans Meta AI :\n    {image_path}\n"
            "puis appuie sur Entrée."
        )

    before = meta_ai.count_media(page, "video")

    log("META AI", "Collage prompt animation...")
    meta_ai.paste_prompt(page, animation_prompt)
    meta_ai.submit(page)

    log("META AI", "Génération...")
    if not meta_ai.wait_for_new_media(page, "video", before):
        log("WARN", "aucune nouvelle video detectee automatiquement")

    saved = meta_ai.download_latest_media(page, "video", directory, "video")
    if saved:
        log("OK", f"Vidéo {shot.id:02d}  -> {saved}")
        return saved

    log("WARN", "telechargement automatique impossible depuis l'interface")
    browser.pause(
        f"Enregistre la video du plan {shot.id:02d} a la main dans :\n"
        f"    {directory / 'video.mp4'}\n"
        "puis appuie sur Entrée."
    )
    saved = find_existing(shot.id, "video")
    if saved:
        log("OK", f"Vidéo {shot.id:02d}  -> {saved}")
    return saved


# ---------------------------------------------------------------------------
# Commandes
# ---------------------------------------------------------------------------


def cmd_storyboard(args) -> int:
    """ETAPE 2+3 seules : OpenAI, aucun navigateur ouvert."""
    storyboard = build_storyboard(args.subject, args.duration, args.shots)
    print(flush=True)
    for shot in storyboard.shots:
        print(f"  --- SHOT {shot.id:02d} ({shot.duration}) ---")
        print(f"  voix   : {shot.voice}")
        print(f"  visuel : {shot.visual_description[:110]}...")
        print(f"  photo  : {shot.image_prompt[:110]}...")
        print()
    return 0


def cmd_run(args) -> int:
    test_mode = config.TEST_MODE if args.test_mode is None else args.test_mode

    storyboard = load_or_build_storyboard(args)
    config.ensure_dirs(len(storyboard.shots))
    status = load_status(len(storyboard.shots))

    shots = storyboard.shots[:1] if test_mode else storyboard.shots
    if test_mode:
        print(flush=True)
        log("TEST_MODE", "on s'arrete apres le collage du prompt photo du SHOT 01")

    with browser.open_browser() as page:
        for shot in shots:
            key = shot.slug
            if status.get(key) == COMPLETED and not args.force:
                shot_header(shot.id)
                log("SKIP", "deja termine (status.json)")
                continue

            shot_header(shot.id)

            if test_mode:
                do_photo(page, shot, stop_after_submit=True)
                status[key] = GENERATED
                save_status(status)
                print(flush=True)
                log("OK", "Prompt du SHOT 01 collé et envoyé dans Meta AI")
                browser.pause(
                    "Vérifie dans le navigateur que le prompt est bien collé et envoyé.\n"
                    "Le prototype n'ira PAS plus loin tant que TEST_MODE vaut True.\n"
                    "Pour enchaîner les 4 plans : TEST_MODE = False dans app/config.py,\n"
                    "ou lance    python -m app.main run --no-test-mode\n"
                    "Appuie sur Entrée pour fermer le navigateur."
                )
                return 0

            image_path = find_existing(shot.id, "image")
            if image_path and not args.force:
                log("SKIP", f"image deja presente: {image_path}")
            else:
                image_path = do_photo(page, shot)

            if image_path is None:
                status[key] = GENERATED
                save_status(status)
                log("STOP", "pas d'image locale : analyse et animation impossibles")
                log("INFO", "relance la commande une fois l'image enregistree")
                continue

            animation_prompt = do_animation_prompt(shot, image_path)
            do_animation(page, shot, image_path, animation_prompt)

            status[key] = COMPLETED
            save_status(status)

    print(flush=True)
    log("OK", "Terminé")
    return 0


def cmd_produire(args) -> int:
    """Chaine 100% automatique : OpenAI + fal.ai, aucun navigateur.

    Utilisable sur une machine sans ecran, donc sur GitHub Actions.
    """
    storyboard = load_or_build_storyboard(args)
    config.ensure_dirs(len(storyboard.shots))
    status = load_status(len(storyboard.shots))

    animations_left = 0 if args.sans_video else args.max_animations
    if args.sans_video:
        log("INFO", "images seules : aucune depense video")
    else:
        log("COUT", f"jusqu'a {animations_left} animation(s) payante(s) fal.ai")

    echecs = []
    for shot in storyboard.shots:
        key = shot.slug
        directory = config.shot_dir(shot.id)
        shot_header(shot.id)

        if status.get(key) == COMPLETED and not args.force:
            log("SKIP", "deja termine (status.json)")
            continue

        try:
            # --- image ---
            image_path = find_existing(shot.id, "image")
            if image_path and not args.force:
                log("SKIP", f"image deja presente: {image_path}")
            else:
                (directory / "image_prompt.txt").write_text(
                    shot.image_prompt + "\n", encoding="utf-8")
                log("FAL", f"Génération image {shot.id:02d}...")
                image_path = fal_client.generate_image(
                    shot.image_prompt, directory / "image.png")
                log("OK", f"Image {shot.id:02d}  -> {image_path}")

            # Sans budget d'animation, l'analyse d'image ne sert a rien :
            # on ne la paie pas, et elle n'exige donc aucun modele vision.
            if animations_left <= 0:
                status[key] = GENERATED
                save_status(status)
                log("OK", "image seule (aucun budget d'animation)")
                continue

            # --- prompt d'animation, a partir de l'image REELLE ---
            animation_file = directory / "animation_prompt.txt"
            if animation_file.is_file() and not args.force:
                animation_prompt = animation_file.read_text(encoding="utf-8").strip()
                log("SKIP", "prompt d'animation deja present")
            else:
                animation_prompt = do_animation_prompt(shot, image_path)

            # --- animation ---
            log("FAL", f"Animation {shot.id:02d}...")
            video = fal_client.animate(
                image_path, animation_prompt,
                _seconds(shot, storyboard), directory / "video.mp4")
            animations_left -= 1
            log("OK", f"Vidéo {shot.id:02d}  -> {video}")

            status[key] = COMPLETED
            save_status(status)

        except (fal_client.FalError, openai_client.OpenAIError) as exc:
            # Un plan en echec ne doit pas emporter les trois autres.
            log("ERREUR", str(exc).splitlines()[0])
            echecs.append((shot.id, str(exc)))
            status[key] = status.get(key, PENDING)
            save_status(status)

    print(flush=True)
    if echecs:
        log("STOP", f"{len(echecs)} plan(s) en echec :")
        for shot_id, message in echecs:
            print(f"      SHOT {shot_id:02d} : {message}", flush=True)
        return 6
    log("OK", "Terminé")
    return 0


def _seconds(shot: Shot, storyboard: Storyboard) -> float:
    """La duree du plan, lue depuis le storyboard, sinon repartie egalement."""
    chiffres = "".join(c for c in shot.duration if c.isdigit() or c == ".")
    try:
        return float(chiffres)
    except ValueError:
        return storyboard.duration / max(len(storyboard.shots), 1)


def cmd_animation(args) -> int:
    """ETAPE 6 seule : une image existante -> son prompt d'animation.

    Ne demande aucun navigateur : utilisable sur une machine sans ecran.
    """
    storyboard = Storyboard.load(config.PROJECT_FILE)
    shot = storyboard.shot(args.shot)

    image = args.image
    if not str(image).startswith(("http://", "https://")):
        image = Path(image)

    config.ensure_dirs(len(storyboard.shots))
    animation_prompt = do_animation_prompt(shot, image)

    print(flush=True)
    print("--- PROMPT ANIMATION ---")
    print(animation_prompt)
    return 0


def cmd_status(args) -> int:
    status = load_status(args.shots)
    print(json.dumps(status, indent=2, ensure_ascii=False))
    return 0


def cmd_selfcheck(args) -> int:
    """Verifications qui ne demandent ni cle OpenAI ni reseau."""
    ok = True

    print("Configuration")
    print(f"  SUBJECT      : {config.SUBJECT}")
    print(f"  DURATION     : {config.DURATION}s")
    print(f"  SHOT_COUNT   : {config.SHOT_COUNT}")
    print(f"  TEST_MODE    : {config.TEST_MODE}")
    print(f"  META_AI_URL  : {config.META_AI_URL}")
    print(f"  cerveau      : {config.cerveau()}")
    print(f"  vision       : {config.OPENAI_VISION_MODEL}")
    print(f"  output       : {config.OUTPUT_DIR}")
    print(f"  profil nav.  : {config.BROWSER_PROFILE_DIR}")

    print("\nCerveau")
    if config.OPENAI_API_KEY:
        source = "GROQ_API_KEY" if config.USING_GROQ else "OPENAI_API_KEY"
        print(f"  {source} presente ({len(config.OPENAI_API_KEY)} caracteres)")
        print(f"  les appels partiront vers : {config.cerveau()}")
        if config.USING_GROQ:
            print("  NOTE : pour l'analyse d'image, nomme un modele vision Groq")
            print("         via OPENAI_VISION_MODEL=... sinon l'etape 6 echouera.")
    else:
        print("  AUCUNE CLE -> 'storyboard', 'run' et 'produire' echoueront")
        print("               mets OPENAI_API_KEY ou GROQ_API_KEY dans .env")
        ok = False

    print("\nfal.ai (commande 'produire')")
    print(f"  FAL_KEY : {'presente' if config.FAL_KEY else 'absente'}")

    print("\nChromium (Playwright)")
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            path = config.CHROMIUM_PATH or pw.chromium.executable_path
            print(f"  binaire : {path}")
            b = pw.chromium.launch(headless=True, executable_path=config.CHROMIUM_PATH or None)
            page = b.new_page()
            page.set_content("<title>ok</title><h1>ok</h1>")
            print(f"  lancement headless : OK ({page.title()})")
            b.close()
    except Exception as exc:  # noqa: BLE001 - on veut afficher n'importe quel echec
        print(f"  ECHEC : {exc}")
        print("  installe-le avec : python -m playwright install chromium")
        ok = False

    print("\nAcces reseau")
    print("  non teste ici : le prototype parle a api.openai.com et www.meta.ai")
    print("  au moment de l'execution.")

    print("\n=> selfcheck", "OK" if ok else "INCOMPLET")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="app.main",
        description="Prototype : sujet -> OpenAI -> prompts -> navigateur -> Meta AI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p):
        p.add_argument("--subject", default=config.SUBJECT)
        p.add_argument("--duration", type=int, default=config.DURATION)
        p.add_argument("--shots", type=int, default=config.SHOT_COUNT)
        return p

    p_story = common(sub.add_parser("storyboard", help="OpenAI seul, sans navigateur"))
    p_story.set_defaults(func=cmd_storyboard)

    p_run = common(sub.add_parser("run", help="boucle complete"))
    p_run.add_argument("--regenerate", action="store_true",
                       help="ignorer project.json et redemander le storyboard")
    p_run.add_argument("--force", action="store_true",
                       help="refaire les plans deja marques termines")
    p_run.add_argument("--test-mode", dest="test_mode", action="store_true", default=None)
    p_run.add_argument("--no-test-mode", dest="test_mode", action="store_false")
    p_run.set_defaults(func=cmd_run)

    p_prod = common(sub.add_parser(
        "produire", help="chaine 100%% automatique : OpenAI + fal.ai, sans navigateur"))
    p_prod.add_argument("--regenerate", action="store_true")
    p_prod.add_argument("--force", action="store_true")
    p_prod.add_argument("--sans-video", dest="sans_video", action="store_true",
                        help="images et prompts seulement, aucune depense video")
    p_prod.add_argument("--max-animations", type=int, default=config.SHOT_COUNT,
                        help="plafond d'animations payantes (defaut: nombre de plans)")
    p_prod.set_defaults(func=cmd_produire)

    p_anim = sub.add_parser(
        "animation", help="ETAPE 6 seule : une image -> son prompt d'animation")
    p_anim.add_argument("--shot", type=int, required=True, help="numero du plan (1..N)")
    p_anim.add_argument("--image", required=True,
                        help="chemin d'un fichier local OU URL http(s) directe")
    p_anim.set_defaults(func=cmd_animation)

    p_status = sub.add_parser("status", help="afficher status.json")
    p_status.add_argument("--shots", type=int, default=config.SHOT_COUNT)
    p_status.set_defaults(func=cmd_status)

    p_check = sub.add_parser("selfcheck", help="verifications hors ligne")
    p_check.set_defaults(func=cmd_selfcheck)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except openai_client.OpenAIError as exc:
        print(f"\n[ERREUR OPENAI] {exc}", file=sys.stderr)
        return 2
    except fal_client.FalError as exc:
        print(f"\n[ERREUR FAL] {exc}", file=sys.stderr)
        return 7
    except meta_ai.MetaAIError as exc:
        print(f"\n[ERREUR META AI] {exc}", file=sys.stderr)
        return 3
    except browser.BrowserError as exc:
        print(f"\n[ERREUR NAVIGATEUR] {exc}", file=sys.stderr)
        return 4
    except StoryboardError as exc:
        print(f"\n[ERREUR STORYBOARD] {exc}", file=sys.stderr)
        return 5
    except KeyError as exc:
        print(f"\n[ERREUR] {exc.args[0] if exc.args else exc}", file=sys.stderr)
        return 5
    except KeyboardInterrupt:
        print("\n[STOP] interrompu. status.json conserve la progression.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
