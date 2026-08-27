"""Navigateur local : profil persistant, pauses manuelles, captures de debug.

Rien ici ne contourne quoi que ce soit. Quand une connexion ou une verification
est demandee, le programme s'arrete et te rend la main.
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright

from . import config


class BrowserError(RuntimeError):
    """Le navigateur n'a pas pu demarrer ou naviguer."""


@contextmanager
def open_browser(headless: bool | None = None):
    """Ouvre Chromium avec un profil persistant et rend la premiere page."""
    headless = config.HEADLESS if headless is None else headless
    config.BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    launch_kwargs = {
        "user_data_dir": str(config.BROWSER_PROFILE_DIR),
        "headless": headless,
        "args": ["--disable-blink-features=AutomationControlled"],
    }
    # executable_path et channel s'excluent : un chemin explicite l'emporte.
    if config.CHROMIUM_PATH:
        launch_kwargs["executable_path"] = config.CHROMIUM_PATH
    elif config.BROWSER_CHANNEL:
        launch_kwargs["channel"] = config.BROWSER_CHANNEL
    if not headless:
        launch_kwargs["no_viewport"] = True

    with sync_playwright() as pw:
        try:
            context = pw.chromium.launch_persistent_context(**launch_kwargs)
        except PlaywrightError as exc:
            raise BrowserError(
                f"le navigateur n'a pas pu demarrer: {exc}\n"
                "  Installe Chromium une fois : python -m playwright install chromium\n"
                "  Si tu vises ton propre Chrome (BROWSER_PROFILE_DIR vers ton profil),\n"
                "  FERME COMPLETEMENT Chrome d'abord : il verrouille son profil.\n"
                "  Sur une machine sans ecran, ajoute HEADLESS=1 dans .env."
            ) from exc

        # Le presse-papier sert au vrai copier/coller dans Meta AI.
        try:
            context.grant_permissions(["clipboard-read", "clipboard-write"])
        except PlaywrightError:
            pass  # non bloquant : on retombera sur la saisie directe

        context.set_default_timeout(config.PAGE_TIMEOUT_MS)
        page = context.pages[0] if context.pages else context.new_page()
        try:
            yield page
        finally:
            context.close()


def goto(page: Page, url: str) -> None:
    try:
        page.goto(url, wait_until="domcontentloaded")
    except PlaywrightError as exc:
        raise BrowserError(f"impossible d'ouvrir {url}: {exc}") from exc


# ---------------------------------------------------------------------------
# Pause manuelle
# ---------------------------------------------------------------------------


def pause(message: str) -> None:
    """Met le processus en pause et attend Entree."""
    print()
    print("=" * 70)
    print(message)
    print("=" * 70)
    if not sys.stdin.isatty():
        raise BrowserError(
            "Une intervention manuelle est necessaire mais l'entree standard n'est pas "
            "un terminal. Relance le programme depuis un vrai terminal."
        )
    input(">>> Appuie sur Entree pour reprendre... ")
    print()


# ---------------------------------------------------------------------------
# Debug : capture d'ecran + etat de la page
# ---------------------------------------------------------------------------


def save_debug_state(page: Page, name: str) -> Path:
    """Capture d'ecran + HTML + URL. Retourne le chemin de la capture."""
    config.SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = config.SCREENSHOT_DIR / f"{stamp}_{name}"
    shot = base.with_suffix(".png")

    try:
        page.screenshot(path=str(shot), full_page=False)
    except PlaywrightError as exc:
        print(f"[WARN] capture d'ecran impossible: {exc}")

    try:
        base.with_suffix(".html").write_text(page.content(), encoding="utf-8")
        base.with_suffix(".url.txt").write_text(page.url, encoding="utf-8")
    except PlaywrightError:
        pass

    return shot
