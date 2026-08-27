"""Verifications hors ligne : parsing, validation, style, etat de reprise.

Ces tests ne touchent NI a OpenAI NI a Meta AI. Ils verifient la partie du
prototype qui est verifiable sans reseau ni compte.

    python -m unittest discover -s tests
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import prompts  # noqa: E402
from app.models import Storyboard, StoryboardError  # noqa: E402


def shot(i=1, **over):
    base = {
        "id": i,
        "duration": "4s",
        "voice": f"Voix du plan {i}.",
        "visual_description": f"Description visuelle du plan {i}.",
        "image_prompt": f"White electric car, shot {i}. {prompts.STYLE_DIRECTIVE}",
    }
    base.update(over)
    return base


def storyboard_dict(n=4, **over):
    base = {
        "subject": "Fonctionnement d'une voiture électrique",
        "duration": 16,
        "visual_style": "Premium 3D engineering visualization.",
        "visual_continuity": "Same white electric car, same dark studio.",
        "shots": [shot(i) for i in range(1, n + 1)],
    }
    base.update(over)
    return base


class TestStoryboardParsing(unittest.TestCase):
    def test_reponse_valide(self):
        sb = Storyboard.from_dict(storyboard_dict(), expected_shots=4)
        self.assertEqual(sb.duration, 16)
        self.assertEqual(len(sb.shots), 4)
        self.assertEqual(sb.shot(3).id, 3)
        self.assertEqual(sb.shots[0].slug, "shot_01")

    def test_mauvais_nombre_de_plans_refuse(self):
        with self.assertRaises(StoryboardError) as ctx:
            Storyboard.from_dict(storyboard_dict(n=3), expected_shots=4)
        self.assertIn("3 plan(s) recu(s), 4 attendu(s)", str(ctx.exception))

    def test_ids_non_contigus_refuses(self):
        raw = storyboard_dict(n=2)
        raw["shots"][1]["id"] = 5
        with self.assertRaises(StoryboardError) as ctx:
            Storyboard.from_dict(raw)
        self.assertIn("id doivent aller de 1 a 2", str(ctx.exception))

    def test_champ_de_plan_manquant_refuse(self):
        for champ in ("voice", "visual_description", "image_prompt", "duration"):
            with self.subTest(champ=champ):
                raw = storyboard_dict(n=1)
                raw["shots"][0][champ] = "   "
                with self.assertRaises(StoryboardError) as ctx:
                    Storyboard.from_dict(raw)
                self.assertIn(champ, str(ctx.exception))

    def test_champ_racine_manquant_refuse(self):
        for champ in ("subject", "visual_style", "visual_continuity"):
            with self.subTest(champ=champ):
                raw = storyboard_dict(n=1)
                raw[champ] = ""
                with self.assertRaises(StoryboardError):
                    Storyboard.from_dict(raw)

    def test_shots_vide_refuse(self):
        with self.assertRaises(StoryboardError):
            Storyboard.from_dict(storyboard_dict(shots=[]))

    def test_reponse_non_objet_refusee(self):
        with self.assertRaises(StoryboardError):
            Storyboard.from_dict(["pas", "un", "objet"])

    def test_aller_retour_disque(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "project.json"
            original = Storyboard.from_dict(storyboard_dict())
            original.save(path)
            relu = Storyboard.load(path)
            self.assertEqual(relu.to_dict(), original.to_dict())

    def test_project_json_illisible(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "project.json"
            path.write_text("{cassé", encoding="utf-8")
            with self.assertRaises(StoryboardError):
                Storyboard.load(path)
            with self.assertRaises(StoryboardError):
                Storyboard.load(Path(tmp) / "absent.json")


class TestStyle(unittest.TestCase):
    def test_directive_ajoutee_si_oubliee(self):
        result = prompts.enforce_style("A white electric car in a dark studio")
        self.assertIn(prompts.STYLE_DIRECTIVE, result)

    def test_directive_non_dupliquee(self):
        deja = f"A white car. {prompts.STYLE_DIRECTIVE}"
        self.assertEqual(prompts.enforce_style(deja).count(prompts.STYLE_FINGERPRINT), 1)

    def test_directive_dans_le_prompt_storyboard(self):
        texte = prompts.storyboard_user("Sujet", 16, 4)
        self.assertIn(prompts.STYLE_DIRECTIVE, texte)
        self.assertIn("SAME white electric car", texte)
        self.assertIn("exactly 4 objects", texte)
        self.assertIn("16 seconds", texte)

    def test_prompt_animation_interdit_le_simple_zoom(self):
        texte = prompts.animation_user("La batterie alimente le moteur.", "Batterie visible.")
        self.assertIn("PEDAGOGICAL", texte)
        self.assertIn('"zoom in"', texte)
        self.assertIn("WHAT MUST STAY PERFECTLY STILL", texte)
        self.assertIn("La batterie alimente le moteur.", texte)


class TestStatus(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        from app import config

        self.config = config
        self._saved = config.STATUS_FILE
        config.STATUS_FILE = Path(self._tmp.name) / "status.json"
        self.addCleanup(lambda: setattr(config, "STATUS_FILE", self._saved))

    def test_status_par_defaut_tout_pending(self):
        from app.main import load_status

        self.assertEqual(
            load_status(4),
            {"shot_01": "pending", "shot_02": "pending",
             "shot_03": "pending", "shot_04": "pending"},
        )

    def test_reprise_conserve_les_plans_termines(self):
        from app.main import load_status, save_status

        save_status({"shot_01": "completed", "shot_02": "completed",
                     "shot_03": "pending", "shot_04": "pending"})
        status = load_status(4)
        self.assertEqual(status["shot_02"], "completed")
        self.assertEqual(status["shot_03"], "pending")

    def test_status_corrompu_repart_proprement(self):
        from app.main import load_status

        self.config.STATUS_FILE.write_text("{cassé", encoding="utf-8")
        self.assertTrue(all(v == "pending" for v in load_status(4).values()))

    def test_cles_inconnues_ignorees(self):
        from app.main import load_status

        self.config.STATUS_FILE.write_text(
            json.dumps({"shot_01": "completed", "shot_99": "completed"}), encoding="utf-8"
        )
        status = load_status(4)
        self.assertNotIn("shot_99", status)
        self.assertEqual(status["shot_01"], "completed")


class TestFeuilleDePrompts(unittest.TestCase):
    """La feuille lue au telephone et collee a la main dans Meta AI."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        from app import config

        self._saved = config.PASTE_SHEET
        config.PASTE_SHEET = Path(self._tmp.name) / "prompts_a_coller.txt"
        self.addCleanup(lambda: setattr(config, "PASTE_SHEET", self._saved))
        self.config = config

    def test_contient_chaque_plan_et_son_prompt(self):
        from app.main import write_paste_sheet

        sb = Storyboard.from_dict(storyboard_dict())
        texte = write_paste_sheet(sb).read_text(encoding="utf-8")

        for i in range(1, 5):
            self.assertIn(f"SHOT {i:02d}", texte)
            self.assertIn(f"White electric car, shot {i}.", texte)
            self.assertIn(f"Voix du plan {i}.", texte)
        self.assertEqual(texte.count("--- PROMPT PHOTO"), 4)

    def test_rappelle_le_lien_meta_ai(self):
        from app.main import write_paste_sheet

        texte = write_paste_sheet(Storyboard.from_dict(storyboard_dict())).read_text("utf-8")
        self.assertIn(self.config.META_AI_URL, texte)

    def test_la_direction_artistique_est_dans_chaque_bloc(self):
        from app.main import write_paste_sheet

        texte = write_paste_sheet(Storyboard.from_dict(storyboard_dict())).read_text("utf-8")
        self.assertEqual(texte.count(prompts.STYLE_FINGERPRINT), 4)


class TestCerveau(unittest.TestCase):
    """Quel service repond aux appels, selon les cles presentes."""

    def config_avec(self, **env):
        import importlib
        import os

        from app import config as module

        efface = {k: os.environ.pop(k, None)
                  for k in ("OPENAI_API_KEY", "GROQ_API_KEY", "OPENAI_MODEL",
                            "OPENAI_BASE_URL", "OPENAI_VISION_MODEL", "GROQ_MODEL")}
        os.environ.update({k: v for k, v in env.items() if v is not None})
        self.addCleanup(importlib.reload, module)

        def restaurer():
            for k in env:
                os.environ.pop(k, None)
            for k, v in efface.items():
                if v is not None:
                    os.environ[k] = v

        self.addCleanup(restaurer)
        return importlib.reload(module)

    def test_openai_prioritaire_sur_groq(self):
        c = self.config_avec(OPENAI_API_KEY="sk-abc", GROQ_API_KEY="gsk-def")
        self.assertFalse(c.USING_GROQ)
        self.assertEqual(c.OPENAI_API_KEY, "sk-abc")
        self.assertIsNone(c.OPENAI_BASE_URL)
        self.assertIn("OpenAI", c.cerveau())

    def test_bascule_sur_groq_si_openai_absente(self):
        c = self.config_avec(GROQ_API_KEY="gsk-def")
        self.assertTrue(c.USING_GROQ)
        self.assertEqual(c.OPENAI_API_KEY, "gsk-def")
        self.assertEqual(c.OPENAI_BASE_URL, "https://api.groq.com/openai/v1")
        self.assertIn("Groq", c.cerveau())

    def test_aucune_cle(self):
        c = self.config_avec()
        self.assertEqual(c.OPENAI_API_KEY, "")
        self.assertFalse(c.USING_GROQ)
        self.assertIn("aucune cle", c.cerveau())

    def test_modele_par_defaut_suit_le_service(self):
        self.assertEqual(self.config_avec(OPENAI_API_KEY="sk-a").OPENAI_MODEL, "gpt-4o")
        self.assertEqual(self.config_avec(GROQ_API_KEY="g").OPENAI_MODEL,
                         "openai/gpt-oss-120b")

    def test_base_url_explicite_respectee(self):
        c = self.config_avec(OPENAI_API_KEY="sk-a", OPENAI_BASE_URL="https://ailleurs.test/v1")
        self.assertEqual(c.OPENAI_BASE_URL, "https://ailleurs.test/v1")
        self.assertIn("ailleurs.test", c.cerveau())

    def test_message_d_erreur_cite_les_deux_cles(self):
        self.config_avec()
        import importlib

        from app import openai_client
        importlib.reload(openai_client)
        with self.assertRaises(openai_client.OpenAIError) as ctx:
            openai_client._client()
        message = str(ctx.exception)
        self.assertIn("OPENAI_API_KEY", message)
        self.assertIn("GROQ_API_KEY", message)


class TestConfigEtCli(unittest.TestCase):
    def test_valeurs_de_l_etape_1(self):
        from app import config

        self.assertEqual(config.DURATION, 16)
        self.assertEqual(config.SHOT_COUNT, 4)
        self.assertTrue(config.TEST_MODE)
        self.assertEqual(
            config.META_AI_URL,
            "https://www.meta.ai/prompt/f1da6c85-fb08-433d-b203-04cc41e575c6",
        )

    def test_aucune_cle_api_en_dur_dans_le_code(self):
        for path in (Path(__file__).resolve().parent.parent / "app").glob("*.py"):
            texte = path.read_text(encoding="utf-8")
            self.assertNotIn("sk-proj", texte, f"cle en dur dans {path.name}")
            self.assertNotRegex(texte, r'OPENAI_API_KEY\s*=\s*"sk-')

    def test_dossiers_de_plans(self):
        from app import config

        self.assertEqual(config.shot_dir(1).name, "shot_01")
        self.assertEqual(config.shot_dir(4).name, "shot_04")

    def test_cli_expose_les_commandes(self):
        from app.main import build_parser

        parser = build_parser()
        for cmd in ("storyboard", "run", "status", "selfcheck"):
            with self.subTest(cmd=cmd):
                args = parser.parse_args([cmd])
                self.assertTrue(callable(args.func))

    def test_commande_animation(self):
        from app.main import build_parser

        args = build_parser().parse_args(
            ["animation", "--shot", "2", "--image", "https://x.test/a.png"])
        self.assertEqual(args.shot, 2)
        self.assertEqual(args.image, "https://x.test/a.png")

    def test_animation_exige_shot_et_image(self):
        from app.main import build_parser

        for incomplet in (["animation"], ["animation", "--shot", "1"],
                          ["animation", "--image", "a.png"]):
            with self.subTest(argv=incomplet), self.assertRaises(SystemExit):
                build_parser().parse_args(incomplet)

    def test_test_mode_pilotable_en_ligne_de_commande(self):
        from app.main import build_parser

        parser = build_parser()
        self.assertIsNone(parser.parse_args(["run"]).test_mode)
        self.assertTrue(parser.parse_args(["run", "--test-mode"]).test_mode)
        self.assertFalse(parser.parse_args(["run", "--no-test-mode"]).test_mode)


if __name__ == "__main__":
    unittest.main()
