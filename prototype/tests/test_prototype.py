"""Contrat JSON, conditions du prompt, cerveau, reprise, CLI.

Rien ici n'appelle OpenAI ni fal.ai.
"""

import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import prompts  # noqa: E402
from app.models import (  # noqa: E402
    MOTION_INTENTS,
    AnimationPlan,
    ImageAnalysis,
    Storyboard,
    StoryboardError,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_validator import board  # noqa: E402


class TestContratStoryboard(unittest.TestCase):
    def test_lecture_complete(self):
        sb = Storyboard.from_dict(board())
        self.assertEqual(sb.shot_count, 4)
        self.assertEqual(sb.total_duration, 16)
        self.assertEqual(sb.shot(3).id, 3)
        self.assertEqual(sb.shots[0].slug, "shot_01")
        self.assertEqual(sb.visual_bible.vehicle[:5], "White")

    def test_la_bible_est_injectable_telle_quelle(self):
        bloc = Storyboard.from_dict(board()).visual_bible.as_block()
        for champ in ("Vehicle:", "Environment:", "Materials:", "Lighting:",
                      "Colour palette:", "Camera language:"):
            self.assertIn(champ, bloc)

    def test_bible_incomplete_refusee(self):
        for champ in ("vehicle", "environment", "materials", "lighting",
                      "color_palette", "camera_language"):
            with self.subTest(champ=champ):
                raw = board()
                raw["visual_bible"][champ] = "  "
                with self.assertRaises(StoryboardError) as ctx:
                    Storyboard.from_dict(raw)
                self.assertIn(champ, str(ctx.exception))

    def test_bible_absente_refusee(self):
        raw = board()
        del raw["visual_bible"]
        with self.assertRaises(StoryboardError):
            Storyboard.from_dict(raw)

    def test_champ_de_plan_manquant_refuse(self):
        for champ in ("voice", "visual_description", "educational_function", "image_prompt"):
            with self.subTest(champ=champ):
                raw = board()
                raw["shots"][0][champ] = " "
                with self.assertRaises(StoryboardError) as ctx:
                    Storyboard.from_dict(raw)
                self.assertIn(champ, str(ctx.exception))

    def test_score_non_numerique_refuse(self):
        raw = board()
        raw["shots"][0]["semantic_alignment_score"] = "élevé"
        with self.assertRaises(StoryboardError):
            Storyboard.from_dict(raw)

    def test_debit_de_parole_calcule(self):
        sb = Storyboard.from_dict(board())
        shot = sb.shots[0]
        self.assertEqual(shot.word_count, len(shot.voice.split()))
        self.assertAlmostEqual(shot.words_per_second,
                               shot.word_count / shot.duration_seconds, places=6)

    def test_aller_retour_disque(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "project.json"
            original = Storyboard.from_dict(board())
            original.save(path)
            self.assertEqual(Storyboard.load(path).to_dict(), original.to_dict())

    def test_fichier_absent_ou_casse(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(StoryboardError):
                Storyboard.load(Path(tmp) / "absent.json")
            casse = Path(tmp) / "project.json"
            casse.write_text("{cassé", encoding="utf-8")
            with self.assertRaises(StoryboardError):
                Storyboard.load(casse)


class TestContratAnalyseImage(unittest.TestCase):
    def analyse(self, **over):
        base = {
            "visible_subjects": ["white electric sedan", "battery pack"],
            "composition": "Low macro framing, pack centre, floor receding",
            "camera": "Low angle, close, 50mm feel",
            "lighting": "Cool key upper left, volumetric haze",
            "important_components": ["prismatic cells", "copper busbars"],
            "preserve": ["cell geometry", "vehicle identity"],
            "possible_motion": ["energy pulse along busbars", "macro tracking"],
        }
        base.update(over)
        return base

    def test_lecture_complete(self):
        a = ImageAnalysis.from_dict(self.analyse())
        self.assertEqual(len(a.visible_subjects), 2)
        self.assertIn("prismatic cells", a.as_block())

    def test_une_chaine_seule_est_acceptee_comme_liste(self):
        a = ImageAnalysis.from_dict(self.analyse(preserve="cell geometry"))
        self.assertEqual(a.preserve, ["cell geometry"])

    def test_champ_vide_refuse(self):
        for champ in ("visible_subjects", "composition", "camera", "lighting",
                      "important_components", "preserve", "possible_motion"):
            with self.subTest(champ=champ):
                with self.assertRaises(StoryboardError) as ctx:
                    ImageAnalysis.from_dict(self.analyse(**{champ: []}))
                self.assertIn(champ, str(ctx.exception))


class TestContratAnimation(unittest.TestCase):
    def plan(self, **over):
        base = {
            "animation_prompt": (
                "Electrical energy pulses travel progressively along the copper busbars "
                "from the battery pack toward the motor while every cell stays fixed."),
            "motion_intent": "energy_follow",
            "camera_motion": "Slow controlled macro tracking from left to right",
            "mechanical_motion": "none: nothing rotates in this framing",
            "energy_motion": "Pulses from the pack forward to the motor",
            "preserve": ["cell geometry", "vehicle identity"],
            "forbidden": ["deformation", "added objects", "text"],
        }
        base.update(over)
        return base

    def test_lecture_complete(self):
        p = AnimationPlan.from_dict(self.plan())
        self.assertEqual(p.motion_intent, "energy_follow")
        self.assertIn("busbars", p.animation_prompt)

    def test_intention_hors_vocabulaire_refusee(self):
        with self.assertRaises(StoryboardError) as ctx:
            AnimationPlan.from_dict(self.plan(motion_intent="zoom_in"))
        self.assertIn("hors vocabulaire", str(ctx.exception))

    def test_zoom_in_n_est_pas_dans_le_vocabulaire(self):
        self.assertNotIn("zoom_in", MOTION_INTENTS)
        self.assertIn("mechanical_rotation", MOTION_INTENTS)
        self.assertIn("energy_follow", MOTION_INTENTS)

    def test_prompt_trop_court_refuse(self):
        with self.assertRaises(StoryboardError) as ctx:
            AnimationPlan.from_dict(self.plan(animation_prompt="slow zoom in"))
        self.assertIn("trop court", str(ctx.exception))

    def test_chaque_facette_du_mouvement_est_exigee(self):
        for champ in ("camera_motion", "mechanical_motion", "energy_motion"):
            with self.subTest(champ=champ):
                with self.assertRaises(StoryboardError) as ctx:
                    AnimationPlan.from_dict(self.plan(**{champ: ""}))
                self.assertIn(champ, str(ctx.exception))

    def test_preserver_et_interdire_sont_obligatoires(self):
        for champ in ("preserve", "forbidden"):
            with self.subTest(champ=champ):
                with self.assertRaises(StoryboardError):
                    AnimationPlan.from_dict(self.plan(**{champ: []}))


class TestConditionsDuPrompt(unittest.TestCase):
    def setUp(self):
        self.texte = prompts.storyboard_user("Fonctionnement d'une voiture électrique", 16, 4)

    def test_les_conditions_sont_toutes_presentes(self):
        for condition in ("CONDITION 1", "CONDITION 2", "CONDITION 3",
                          "CONDITION 4", "CONDITION 5", "CONDITION 6", "CONDITION 10"):
            self.assertIn(condition, self.texte)

    def test_condition_1_exige_une_chaine_causale(self):
        self.assertIn("CAUSAL CHAIN", self.texte)
        self.assertIn("Do not list components", self.texte)
        self.assertIn("battery → electrical energy → accelerator pedal", self.texte)

    def test_condition_2_donne_la_cible_en_mots(self):
        self.assertIn("sum to EXACTLY 16", self.texte)
        self.assertIn("roughly 10 French words", self.texte)
        self.assertIn("Never write a tiny sentence", self.texte)

    def test_condition_5_interdit_le_prompt_vague(self):
        self.assertIn('"Electric motor in a car" is rejected', self.texte)
        for exigence in ("framing", "camera angle", "depth", "lighting",
                         "materials", "unmistakably visible"):
            self.assertIn(exigence, self.texte)

    def test_condition_6_impose_le_seuil_de_score(self):
        self.assertIn("below 0.8", self.texte)
        self.assertIn("Never narrate a component that the image does not show", self.texte)

    def test_direction_artistique_verbatim(self):
        self.assertIn(prompts.STYLE_DIRECTIVE, self.texte)
        self.assertIn("VERBATIM", self.texte)

    def test_prompt_animation_refuse_le_simple_mouvement_de_camera(self):
        texte = prompts.animation_user("La batterie alimente le moteur.",
                                       "Montre le premier maillon.",
                                       "Visible subjects: battery", MOTION_INTENTS)
        self.assertIn('"slow zoom in"', texte)
        self.assertIn("A camera move alone is rejected", texte)
        self.assertIn("stator stays fixed", prompts.ANIMATION_SYSTEM)
        self.assertIn("energy_follow", texte)
        self.assertIn("La batterie alimente le moteur.", texte)

    def test_analyse_interdit_de_deviner(self):
        self.assertIn("ONLY what is actually visible", prompts.ANALYSIS_USER)
        self.assertIn("Do not use the brief that produced it", prompts.ANALYSIS_USER)

    def test_enforce_style_ajoute_sans_dupliquer(self):
        self.assertIn(prompts.STYLE_DIRECTIVE, prompts.enforce_style("A white car"))
        deja = f"A white car. {prompts.STYLE_DIRECTIVE}"
        self.assertEqual(prompts.enforce_style(deja).count(prompts.STYLE_FINGERPRINT), 1)


class TestCerveau(unittest.TestCase):
    def config_avec(self, **env):
        from app import config as module

        garde = {k: os.environ.pop(k, None)
                 for k in ("OPENAI_API_KEY", "GROQ_API_KEY", "OPENAI_MODEL",
                           "OPENAI_BASE_URL", "OPENAI_VISION_MODEL", "GROQ_MODEL")}
        os.environ.update({k: v for k, v in env.items() if v is not None})
        self.addCleanup(importlib.reload, module)

        def restaurer():
            for k in env:
                os.environ.pop(k, None)
            for k, v in garde.items():
                if v is not None:
                    os.environ[k] = v

        self.addCleanup(restaurer)
        return importlib.reload(module)

    def test_variable_vide_compte_comme_absente(self):
        """Regression : GitHub envoie "" pour une variable de depot non definie.

        os.getenv(nom, defaut) rend "" dans ce cas, donc le defaut n'etait
        jamais applique et model="" partait a l'API — l'erreur 400
        « you must provide a model parameter » vue en production.
        """
        c = self.config_avec(GROQ_API_KEY="gsk-x", OPENAI_VISION_MODEL="")
        self.assertEqual(c.OPENAI_VISION_MODEL, "openai/gpt-oss-120b")

    def test_variable_faite_d_espaces(self):
        c = self.config_avec(OPENAI_API_KEY="sk-a", OPENAI_MODEL="   ")
        self.assertEqual(c.OPENAI_MODEL, "gpt-4o")

    def test_openai_prioritaire_sur_groq(self):
        c = self.config_avec(OPENAI_API_KEY="sk-abc", GROQ_API_KEY="gsk-def")
        self.assertFalse(c.USING_GROQ)
        self.assertIsNone(c.OPENAI_BASE_URL)
        self.assertIn("OpenAI", c.cerveau())

    def test_bascule_sur_groq(self):
        c = self.config_avec(GROQ_API_KEY="gsk-def")
        self.assertTrue(c.USING_GROQ)
        self.assertEqual(c.OPENAI_BASE_URL, "https://api.groq.com/openai/v1")

    def test_aucune_cle(self):
        self.assertIn("aucune cle", self.config_avec().cerveau())

    def test_message_sans_cle_cite_le_fichier_env(self):
        self.config_avec()
        from app import openai_client
        importlib.reload(openai_client)
        with self.assertRaises(openai_client.OpenAIError) as ctx:
            openai_client.client()
        self.assertIn("OPENAI_API_KEY manquante dans .env", str(ctx.exception))

    def test_modele_vide_refuse_avant_l_appel(self):
        self.config_avec(OPENAI_API_KEY="sk-a")
        from app import openai_client
        importlib.reload(openai_client)
        with self.assertRaises(openai_client.OpenAIError) as ctx:
            openai_client.chat_json("", [{"role": "user", "content": "x"}])
        self.assertIn("aucun modele nomme", str(ctx.exception))


class TestReprise(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        from app import config

        self.config = config
        garde = config.STATUS_FILE
        config.STATUS_FILE = Path(self._tmp.name) / "status.json"
        self.addCleanup(lambda: setattr(config, "STATUS_FILE", garde))

    def test_tout_pending_au_depart(self):
        from app.main import load_status

        self.assertEqual(set(load_status(4).values()), {"pending"})

    def test_les_plans_termines_sont_conserves(self):
        from app.main import load_status, save_status

        save_status({"shot_01": "completed", "shot_02": "completed",
                     "shot_03": "pending", "shot_04": "pending"})
        self.assertEqual(load_status(4)["shot_02"], "completed")

    def test_fichier_corrompu_repart_proprement(self):
        from app.main import load_status

        self.config.STATUS_FILE.write_text("{cassé", encoding="utf-8")
        self.assertEqual(set(load_status(4).values()), {"pending"})

    def test_cles_inconnues_ignorees(self):
        from app.main import load_status

        self.config.STATUS_FILE.write_text(
            json.dumps({"shot_01": "completed", "shot_99": "completed"}), encoding="utf-8")
        status = load_status(4)
        self.assertNotIn("shot_99", status)
        self.assertEqual(status["shot_01"], "completed")


class TestConfigEtCli(unittest.TestCase):
    def test_les_trois_valeurs_d_entree(self):
        from app import config

        self.assertEqual(config.DURATION, 16)
        self.assertEqual(config.SHOT_COUNT, 4)
        self.assertTrue(config.TEST_MODE)
        self.assertIn("voiture", config.SUBJECT)

    def test_aucune_cle_en_dur(self):
        for path in (Path(__file__).resolve().parent.parent / "app").glob("*.py"):
            texte = path.read_text(encoding="utf-8")
            self.assertNotIn("sk-proj", texte, f"cle en dur dans {path.name}")
            self.assertNotRegex(texte, r'OPENAI_API_KEY\s*=\s*"sk-')

    def test_python_main_py_sans_argument_lance_le_storyboard(self):
        from app.main import build_parser

        args = build_parser().parse_args(["storyboard"])
        self.assertEqual(args.func.__name__, "cmd_storyboard")

    def test_les_commandes_existent(self):
        from app.main import build_parser

        parser = build_parser()
        for commande in ("storyboard", "analyser", "produire", "comparer",
                         "valider", "status", "selfcheck"):
            with self.subTest(commande=commande):
                self.assertTrue(callable(parser.parse_args(
                    [commande] + (["--shot", "1", "--image", "a.png"]
                                  if commande == "analyser" else [])).func))

    def test_analyser_exige_le_plan_et_l_image(self):
        from app.main import build_parser

        for incomplet in (["analyser"], ["analyser", "--shot", "1"]):
            with self.subTest(argv=incomplet), self.assertRaises(SystemExit):
                build_parser().parse_args(incomplet)


if __name__ == "__main__":
    unittest.main()
