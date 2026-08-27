"""Test d'integration du collage, contre une FAUSSE page de chat locale.

Ce test ne touche pas Meta AI (inaccessible sans compte). Il verifie que
find_composer / paste_prompt / submit fonctionnent reellement dans un vrai
Chromium, sur une page qui reproduit la forme d'un composer de chat :
un div contenteditable et un bouton d'envoi.

    CHROMIUM_PATH=/chemin/vers/chrome HEADLESS=1 python -m unittest tests.test_browser_paste
"""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FAKE_CHAT = """
<!doctype html><meta charset="utf-8"><title>faux chat</title>
<body style="font-family:sans-serif">
  <div id="messages"></div>
  <div contenteditable="true" role="textbox" aria-label="Ask Meta AI"
       id="composer"
       style="border:1px solid #888;min-height:40px;padding:8px"></div>
  <button aria-label="Send" id="send">Send</button>
  <script>
    document.getElementById('send').onclick = () => {
      const c = document.getElementById('composer');
      const m = document.createElement('p');
      m.className = 'sent';
      m.textContent = c.innerText;
      document.getElementById('messages').appendChild(m);
      c.innerText = '';
    };
    document.getElementById('composer').addEventListener('keydown', e => {
      if (e.key === 'Enter') { e.preventDefault(); document.getElementById('send').click(); }
    });
  </script>
</body>
"""


def chromium_path():
    return os.getenv("CHROMIUM_PATH") or None


class TestCollageReel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:  # pragma: no cover
            raise unittest.SkipTest("playwright absent") from None
        cls._pw = sync_playwright().start()
        try:
            cls.browser = cls._pw.chromium.launch(headless=True,
                                                  executable_path=chromium_path())
        except Exception as exc:  # pragma: no cover
            cls._pw.stop()
            raise unittest.SkipTest(f"chromium indisponible: {exc}") from exc

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls._pw.stop()

    def setUp(self):
        self.page = self.browser.new_page()
        self.page.set_content(FAKE_CHAT)
        self.addCleanup(self.page.close)

    def test_composer_trouve(self):
        from app import meta_ai

        self.assertIsNotNone(meta_ai.find_composer(self.page, timeout=5000))

    def test_prompt_colle_puis_envoye(self):
        from app import meta_ai
        from app.prompts import STYLE_DIRECTIVE

        prompt = ("Macro shot of a white electric car battery pack, copper busbars "
                  f"visible. {STYLE_DIRECTIVE}")
        meta_ai.paste_prompt(self.page, prompt)
        self.assertIn("Macro shot", self.page.inner_text("#composer"))

        meta_ai.submit(self.page)
        self.page.wait_for_selector("p.sent", timeout=5000)
        envoye = self.page.inner_text("p.sent")
        self.assertIn("Macro shot of a white electric car battery pack", envoye)
        self.assertIn("no text, no labels, no logos, no watermark", envoye)
        self.assertEqual(self.page.inner_text("#composer").strip(), "")

    def test_deux_prompts_successifs_ne_se_melangent_pas(self):
        from app import meta_ai

        meta_ai.paste_prompt(self.page, "PREMIER prompt photo")
        meta_ai.submit(self.page)
        self.page.wait_for_selector("p.sent", timeout=5000)
        meta_ai.paste_prompt(self.page, "DEUXIEME prompt photo")
        self.assertNotIn("PREMIER", self.page.inner_text("#composer"))
        meta_ai.submit(self.page)
        self.page.wait_for_function("document.querySelectorAll('p.sent').length === 2")
        textes = self.page.locator("p.sent").all_inner_texts()
        self.assertEqual([t.strip() for t in textes],
                         ["PREMIER prompt photo", "DEUXIEME prompt photo"])

    def test_composer_absent_donne_une_erreur_claire(self):
        from app import meta_ai

        self.page.set_content("<body><p>page sans zone de saisie</p></body>")
        with self.assertRaises(meta_ai.MetaAIError) as ctx:
            meta_ai.paste_prompt(self.page, "peu importe")
        self.assertIn("zone de saisie introuvable", str(ctx.exception))
        self.assertIn("Capture", str(ctx.exception))

    def test_page_de_connexion_detectee(self):
        from app import meta_ai

        self.page.set_content("<body><h1>Log in to continue</h1>"
                              "<button>Continue with Facebook</button></body>")
        self.assertTrue(meta_ai.needs_login(self.page))

    def test_page_de_chat_non_prise_pour_une_connexion(self):
        from app import meta_ai

        self.page.set_content(FAKE_CHAT)
        self.assertFalse(meta_ai.needs_login(self.page))

    def test_comptage_des_medias(self):
        from app import meta_ai

        self.assertEqual(meta_ai.count_media(self.page, "image"), 0)
        self.page.evaluate("document.body.appendChild(document.createElement('img'))")
        self.assertEqual(meta_ai.count_media(self.page, "image"), 1)
