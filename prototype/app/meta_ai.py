"""Pilotage de l'interface Meta AI.

Aucun selecteur n'est suppose exister. Chaque etape essaie plusieurs pistes,
et si aucune ne marche : message clair, capture d'ecran, pause, reprise manuelle.

Ce module ne contourne aucune protection. Il ne saisit jamais d'identifiant,
de mot de passe ni de code : quand Meta demande une connexion ou une
verification, il rend la main a l'utilisateur.
"""

from __future__ import annotations

import base64
import re
import time
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Locator, Page

from . import browser, config


class MetaAIError(RuntimeError):
    """Un element attendu de l'interface Meta AI est introuvable."""


LOGIN_MESSAGE = (
    "Connexion Meta requise. Connecte-toi manuellement dans le navigateur "
    "puis appuie sur Entrée."
)

# Signes d'une page de connexion / verification. Volontairement larges.
LOGIN_HINTS = (
    "log in",
    "log into",
    "sign in",
    "se connecter",
    "connexion",
    "continue with facebook",
    "continuer avec facebook",
    "continue with instagram",
    "enter the code",
    "saisis le code",
    "code de securite",
    "security code",
    "two-factor",
    "authentification a deux facteurs",
    "verify",
    "verification",
    "confirme qu'il s'agit bien de toi",
)

# Pistes successives pour trouver la zone de saisie du prompt.
COMPOSER_STRATEGIES = (
    ("role textbox", lambda p: p.get_by_role("textbox")),
    ("placeholder Meta AI", lambda p: p.get_by_placeholder(re.compile(r"meta ai", re.I))),
    ("placeholder ask/message", lambda p: p.get_by_placeholder(
        re.compile(r"ask|message|demand|pose|ecris|écris|type", re.I))),
    ("contenteditable", lambda p: p.locator('div[contenteditable="true"]')),
    ("textarea", lambda p: p.locator("textarea")),
)

# Pistes successives pour le bouton d'envoi.
SUBMIT_STRATEGIES = (
    ("aria-label send", lambda p: p.get_by_label(re.compile(r"^(send|envoyer)", re.I))),
    ("role button send", lambda p: p.get_by_role("button", name=re.compile(r"send|envoyer", re.I))),
    ("data-testid", lambda p: p.locator('[data-testid*="send" i]')),
    ("bouton type submit", lambda p: p.locator('button[type="submit"]')),
)


# ---------------------------------------------------------------------------
# Ouverture et connexion
# ---------------------------------------------------------------------------


def open_prompt_page(page: Page) -> None:
    """Ouvre directement l'URL fixe du prototype."""
    browser.goto(page, config.META_AI_URL)
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except PlaywrightError:
        pass  # une page vivante n'atteint jamais networkidle : ce n'est pas une erreur


def needs_login(page: Page) -> bool:
    """Vrai si la page ressemble a une connexion ou une verification."""
    try:
        text = (page.inner_text("body") or "").lower()
    except PlaywrightError:
        return False

    url = page.url.lower()
    if any(part in url for part in ("/login", "facebook.com/login", "checkpoint", "/two_step")):
        return True

    # Une page de chat contient beaucoup de texte ; on ne regarde que le debut
    # pour eviter les faux positifs sur un mot isole au milieu d'une reponse.
    head = text[:1500]
    return any(hint in head for hint in LOGIN_HINTS)


def ensure_ready(page: Page) -> None:
    """Si Meta demande une connexion : pause, puis reprise automatique."""
    for attempt in range(1, 4):
        if not needs_login(page) and find_composer(page, timeout=5000) is not None:
            return
        if needs_login(page):
            browser.save_debug_state(page, "connexion-requise")
            browser.pause(LOGIN_MESSAGE)
            try:
                page.wait_for_load_state("domcontentloaded", timeout=15000)
            except PlaywrightError:
                pass
            continue
        if attempt == 1:
            open_prompt_page(page)
            continue
        browser.pause(
            "La zone de saisie Meta AI n'est pas visible.\n"
            "Ouvre la conversation manuellement dans le navigateur, "
            "puis appuie sur Entrée."
        )

    if find_composer(page, timeout=5000) is None:
        shot = browser.save_debug_state(page, "composer-introuvable")
        raise MetaAIError(
            "zone de saisie Meta AI toujours introuvable apres intervention manuelle.\n"
            f"  Capture : {shot}"
        )


# ---------------------------------------------------------------------------
# Zone de saisie
# ---------------------------------------------------------------------------


def find_composer(page: Page, timeout: int = 20000) -> Locator | None:
    """Cherche la zone de saisie en essayant chaque piste tour a tour."""
    deadline = time.monotonic() + timeout / 1000
    while True:
        for _label, strategy in COMPOSER_STRATEGIES:
            try:
                candidates = strategy(page)
                count = candidates.count()
            except PlaywrightError:
                continue
            # La zone de saisie est en general la derniere du DOM (bas de page).
            for index in range(count - 1, -1, -1):
                node = candidates.nth(index)
                try:
                    if node.is_visible() and node.is_enabled():
                        return node
                except PlaywrightError:
                    continue
        if time.monotonic() >= deadline:
            return None
        page.wait_for_timeout(500)


def paste_prompt(page: Page, text: str) -> None:
    """Colle le prompt dans la zone de saisie et verifie qu'il est bien arrive."""
    composer = find_composer(page)
    if composer is None:
        shot = browser.save_debug_state(page, "collage-composer-introuvable")
        raise MetaAIError(f"zone de saisie introuvable pour le collage.\n  Capture : {shot}")

    try:
        composer.click()
    except PlaywrightError as exc:
        shot = browser.save_debug_state(page, "collage-clic-impossible")
        raise MetaAIError(f"clic impossible sur la zone de saisie: {exc}\n  Capture : {shot}") from exc

    _clear(page, composer)

    # 1. vrai copier/coller par le presse-papier
    if _paste_via_clipboard(page, text) and _composer_contains(composer, text):
        return

    # 2. repli : insertion directe du texte (equivalent d'un collage)
    try:
        page.keyboard.insert_text(text)
    except PlaywrightError:
        pass
    if _composer_contains(composer, text):
        return

    # 3. dernier repli : fill()
    try:
        composer.fill(text)
    except PlaywrightError:
        pass
    if _composer_contains(composer, text):
        return

    shot = browser.save_debug_state(page, "collage-echoue")
    raise MetaAIError(
        "le prompt n'a pas pu etre colle dans la zone de saisie.\n"
        f"  Capture : {shot}\n"
        "  Le prompt reste disponible dans le fichier image_prompt.txt du plan."
    )


def _clear(page: Page, composer: Locator) -> None:
    try:
        composer.press("Control+a")
        composer.press("Delete")
    except PlaywrightError:
        pass


def _paste_via_clipboard(page: Page, text: str) -> bool:
    try:
        page.evaluate("t => navigator.clipboard.writeText(t)", text)
        page.keyboard.press("Control+V")
        page.wait_for_timeout(300)
        return True
    except PlaywrightError:
        return False


def _composer_contains(composer: Locator, text: str) -> bool:
    """Le debut du prompt doit etre lisible dans la zone de saisie."""
    probe = text[:40]
    for reader in ("input_value", "inner_text"):
        try:
            value = getattr(composer, reader)()
        except PlaywrightError:
            continue
        if value and probe in value:
            return True
    return False


def submit(page: Page) -> None:
    """Envoie le prompt : bouton d'envoi si on le trouve, sinon Entree."""
    for _label, strategy in SUBMIT_STRATEGIES:
        try:
            button = strategy(page).last
            if button.is_visible() and button.is_enabled():
                button.click()
                return
        except PlaywrightError:
            continue
    try:
        page.keyboard.press("Enter")
    except PlaywrightError as exc:
        shot = browser.save_debug_state(page, "envoi-impossible")
        raise MetaAIError(f"envoi impossible: {exc}\n  Capture : {shot}") from exc


# ---------------------------------------------------------------------------
# Attente et recuperation du resultat
# ---------------------------------------------------------------------------


def count_media(page: Page, kind: str) -> int:
    selector = "img" if kind == "image" else "video"
    try:
        return page.locator(selector).count()
    except PlaywrightError:
        return 0


def wait_for_new_media(page: Page, kind: str, before: int, timeout_s: int | None = None) -> bool:
    """Attend qu'un media de plus apparaisse. Retourne False si rien n'arrive."""
    timeout_s = config.GENERATION_TIMEOUT_S if timeout_s is None else timeout_s
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if count_media(page, kind) > before:
            page.wait_for_timeout(2000)  # laisse le media finir de se charger
            return True
        page.wait_for_timeout(1500)
    return False


def download_latest_media(page: Page, kind: str, dest_dir: Path, stem: str) -> Path | None:
    """Tente d'enregistrer le dernier media. Retourne None sans lever si impossible.

    Volontairement non bloquant : pour le premier prototype, l'objectif est de
    prouver le copier/coller, pas de garantir le telechargement.
    """
    selector = "img" if kind == "image" else "video"
    try:
        nodes = page.locator(selector)
        for index in range(nodes.count() - 1, -1, -1):
            src = nodes.nth(index).get_attribute("src") or ""
            if not src or src.startswith("blob:"):
                continue
            if src.startswith("data:"):
                header, _, payload = src.partition(",")
                ext = ".png" if "png" in header else ".jpg"
                target = dest_dir / f"{stem}{ext}"
                target.write_bytes(base64.b64decode(payload))
                return target
            if src.startswith("http"):
                response = page.request.get(src)
                if not response.ok:
                    continue
                body = response.body()
                if len(body) < 8000:
                    continue  # icone d'interface, pas un resultat
                ext = _extension_for(response.headers.get("content-type", ""), kind)
                target = dest_dir / f"{stem}{ext}"
                target.write_bytes(body)
                return target
    except PlaywrightError:
        return None
    return None


def _extension_for(content_type: str, kind: str) -> str:
    content_type = content_type.lower()
    for needle, ext in (("png", ".png"), ("jpeg", ".jpg"), ("jpg", ".jpg"),
                        ("webp", ".webp"), ("mp4", ".mp4"), ("webm", ".webm")):
        if needle in content_type:
            return ext
    return ".png" if kind == "image" else ".mp4"


# ---------------------------------------------------------------------------
# Ajout d'une image (etape 7)
# ---------------------------------------------------------------------------


def attach_image(page: Page, image_path: Path) -> bool:
    """Joint une image au prochain message. Retourne False si aucun champ trouve."""
    try:
        inputs = page.locator('input[type="file"]')
        if inputs.count():
            inputs.last.set_input_files(str(image_path))
            page.wait_for_timeout(1500)
            return True
    except PlaywrightError:
        pass
    return False
