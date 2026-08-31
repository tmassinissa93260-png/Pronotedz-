"""Contrat JSON, conditions du prompt, timeline, sous-titres, CLI, cerveau."""

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import montage, prompts  # noqa: E402
from app.models import (  # noqa: E402
    COLOR_NOTION,
    MOTION_INTENTS,
    NOTION_SENS,
    QUALITY_AXES,
    VISUAL_BIBLE_FIELDS,
    Storyboard,
    StoryboardError,
    VideoAnalysis,
)
from fixtures import board  # noqa: E402


class TestContrat(unittest.TestCase):
    def test_lecture_complete(self):
        sb = Storyboard.from_dict(board())
        self.assertEqual(sb.shot_count, 4)
        self.assertEqual(sb.total_duration, 16)
        self.assertTrue(sb.script)
        self.assertEqual(sb.shots[0].slug, "shot_01")
        self.assertEqual(len(sb.quality_check), len(QUALITY_AXES))

    def test_les_onze_champs_de_la_bible(self):
        self.assertEqual(len(VISUAL_BIBLE_FIELDS), 11)
        bloc = Storyboard.from_dict(board()).visual_bible.as_block()
        for champ in VISUAL_BIBLE_FIELDS:
            self.assertIn(champ.replace("_", " ").capitalize(), bloc)

    def test_bible_incomplete_refusee(self):
        for champ in VISUAL_BIBLE_FIELDS:
            with self.subTest(champ=champ):
                raw = board()
                raw["visual_bible"][champ] = "  "
                with self.assertRaises(StoryboardError) as ctx:
                    Storyboard.from_dict(raw)
                self.assertIn(champ, str(ctx.exception))

    def test_script_obligatoire(self):
        raw = board()
        raw["script"] = ""
        with self.assertRaises(StoryboardError) as ctx:
            Storyboard.from_dict(raw)
        self.assertIn("script", str(ctx.exception))

    def test_champ_de_plan_manquant(self):
        for champ in ("voice", "visual_description", "educational_function",
                      "visual_concept", "image_prompt", "animation_prompt"):
            with self.subTest(champ=champ):
                raw = board()
                raw["shots"][0][champ] = " "
                with self.assertRaises(StoryboardError) as ctx:
                    Storyboard.from_dict(raw)
                self.assertIn(champ, str(ctx.exception))

    def test_motion_intent_hors_vocabulaire(self):
        raw = board()
        raw["shots"][0]["motion_intent"] = "zoom_in"
        with self.assertRaises(StoryboardError) as ctx:
            Storyboard.from_dict(raw)
        self.assertIn("hors vocabulaire", str(ctx.exception))

    def test_zoom_absent_du_vocabulaire(self):
        self.assertNotIn("zoom_in", MOTION_INTENTS)
        self.assertNotIn("zoom", MOTION_INTENTS)
        for attendu in ("energy_flow", "energy_storage", "regenerative_braking",
                        "electromagnetic_rotation", "cause_effect", "energy_return"):
            self.assertIn(attendu, MOTION_INTENTS)

    def test_aller_retour_disque(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "project.json"
            original = Storyboard.from_dict(board())
            original.save(chemin)
            self.assertEqual(Storyboard.load(chemin).to_dict(), original.to_dict())


class TestCodeCouleur(unittest.TestCase):
    def test_l_energie_est_jaune_ET_orange(self):
        self.assertEqual(COLOR_NOTION["yellow"], "energie")
        self.assertEqual(COLOR_NOTION["orange"], "energie")
        self.assertIn("jaune/orange", NOTION_SENS["energie"])

    def test_une_couleur_ne_porte_jamais_deux_notions(self):
        for couleur, notion in COLOR_NOTION.items():
            with self.subTest(couleur=couleur):
                self.assertIsInstance(notion, str)
        self.assertEqual(set(NOTION_SENS), set(COLOR_NOTION.values()))

    def test_le_code_est_injecte_dans_le_prompt(self):
        texte = prompts.storyboard_user("Sujet", 16, 4)
        for notion in NOTION_SENS:
            self.assertIn(notion.upper(), texte)


class TestCodeCouleurDuSujet(unittest.TestCase):
    """Le code couleur vient du sujet ; la table voiture n'est que le defaut."""

    def test_un_ancien_fichier_sans_code_retombe_sur_le_defaut(self):
        from app.models import DEFAULT_COLOR_CODE

        raw = board()
        del raw["color_code"]
        sb = Storyboard.from_dict(raw)
        self.assertEqual(sb.color_code, [])
        self.assertEqual(sb.code_couleur(), DEFAULT_COLOR_CODE)
        self.assertEqual(sb.notion_par_couleur()["yellow"], "energie")

    def test_le_code_du_sujet_est_celui_qui_sert(self):
        raw = board()
        raw["color_code"] = [
            {"notion": "flux", "color": "red/crimson", "meaning": "l'air",
             "moving": True},
            {"notion": "carlingue", "color": "grey", "meaning": "la structure",
             "moving": False},
            {"notion": "reacteur", "color": "blue", "meaning": "le moteur",
             "moving": False},
        ]
        sb = Storyboard.from_dict(raw)
        self.assertEqual(sb.notion_par_couleur()["crimson"], "flux")
        self.assertNotIn("yellow", sb.notion_par_couleur())
        self.assertEqual(sb.notions_mobiles(), ("flux",))

    def test_le_prompt_demande_le_code_au_lieu_de_l_imposer(self):
        texte = prompts.storyboard_user("Sujet", 16, 4)
        self.assertIn('"color_code"', texte)
        self.assertIn("for YOUR subject", texte)

    def test_un_champ_vide_est_refuse(self):
        from app.models import StoryboardError

        raw = board()
        raw["color_code"][0]["color"] = ""
        with self.assertRaises(StoryboardError) as ctx:
            Storyboard.from_dict(raw)
        self.assertIn("color", str(ctx.exception))


class TestImagesDeposees(unittest.TestCase):
    """Les images produites par l'utilisateur, ou qu'il les pose."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        from app import config

        self.config = config
        garde = (config.OUTPUT_DIR, config.IMAGES_DIR, config.SHOTS_DIR)
        racine = Path(self._tmp.name)
        config.OUTPUT_DIR = racine
        config.IMAGES_DIR = racine / "images"
        config.SHOTS_DIR = racine / "shots"
        config.IMAGES_DIR.mkdir()

        def restaurer():
            (config.OUTPUT_DIR, config.IMAGES_DIR, config.SHOTS_DIR) = garde

        self.addCleanup(restaurer)
        self.sb = Storyboard.from_dict(board())

    def trouver(self):
        from app.main import trouver_images

        return trouver_images(self.sb)

    def test_aucune_image(self):
        self.assertEqual(self.trouver(), {})

    def test_dans_le_dossier_images(self):
        for nom in ("shot_01.png", "02.jpg", "3.webp"):
            (self.config.IMAGES_DIR / nom).write_bytes(b"x")
        self.assertEqual(sorted(self.trouver()), [1, 2, 3])

    def test_directement_dans_le_dossier_du_plan(self):
        d = self.config.shot_dir(4)
        d.mkdir(parents=True)
        (d / "image.png").write_bytes(b"x")
        self.assertEqual(list(self.trouver()), [4])

    def test_le_dossier_images_a_la_priorite(self):
        d = self.config.shot_dir(1)
        d.mkdir(parents=True)
        (d / "image.png").write_bytes(b"x")
        attendu = self.config.IMAGES_DIR / "shot_01.png"
        attendu.write_bytes(b"x")
        self.assertEqual(self.trouver()[1], attendu)


class TestConditionsDuPrompt(unittest.TestCase):
    def setUp(self):
        self.texte = prompts.storyboard_user("Fonctionnement d'une voiture électrique", 16, 4)

    def test_les_six_parties(self):
        for partie in ("PART 1", "PART 2", "PART 3", "PART 4", "PART 5", "PART 6"):
            self.assertIn(partie, self.texte)

    def test_la_grammaire_visuelle_est_la_regle_centrale(self):
        self.assertIn("PEDAGOGICAL VISUAL GRAMMAR", self.texte)
        self.assertIn("Do NOT settle for showing objects", self.texte)
        self.assertIn("is NOT decoration", self.texte)

    def test_la_correspondance_image_animation_est_exigee(self):
        self.assertIn("CORRESPONDENCE", self.texte)
        self.assertIn("image shows a rotor", self.texte)
        self.assertIn("image: battery with an electrical flow", self.texte)

    def test_le_zoom_n_est_jamais_le_mouvement_principal(self):
        self.assertIn("ABSOLUTE RULE — DYNAMIC ANIMATION", self.texte)
        self.assertIn("The camera movement is SECONDARY", self.texte)
        self.assertIn("PRIORITY OF MOVEMENTS", self.texte)
        self.assertIn('NEVER use "slow zoom in" as the only animation', self.texte)
        self.assertIn("WHAT IS MOVING IN THE WORLD?", self.texte)

    def test_plusieurs_mouvements_coordonnes(self):
        self.assertIn("MULTI-MOTION REQUIREMENT", self.texte)
        self.assertIn("synchronised and causally related", self.texte)
        # La chaine causale complete, de la batterie a la voiture qui avance.
        for maillon in ("the rotor starts turning", "the wheels turn",
                        "the car moves forward"):
            self.assertIn(maillon, self.texte)
        # Et l'interdiction d'en rajouter pour faire joli.
        self.assertIn("Never add movement just", self.texte)

    def test_le_style_de_reference_est_impose(self):
        self.assertIn("REFERENCE VISUAL LANGUAGE", self.texte)
        self.assertIn("semi-cutaway", self.texte)
        self.assertIn("blue and white lighting", self.texte)
        self.assertIn("high-end car commercial", self.texte)
        self.assertIn("same silhouette, same colour", self.texte)

    def test_la_regle_visual_explanation_et_ses_sept_temps(self):
        self.assertIn("VISUAL EXPLANATION", self.texte)
        for etape in ("information", "physical_element", "secondary_elements",
                      "visual_behavior", "animation_movement", "camera_position",
                      "composition"):
            self.assertIn(etape, self.texte)
        self.assertIn("sound off", self.texte)

    def test_on_ne_part_jamais_d_une_belle_image(self):
        """L'image est le premier plan de l'animation, pas une illustration."""
        self.assertIn("NEVER START FROM A BEAUTIFUL IMAGE", self.texte)
        self.assertIn("FIRST FRAME", self.texte)
        self.assertIn("must contain every physical element required by the animation",
                      self.texte)
        self.assertIn("Never introduce an important object or phenomenon only in the",
                      self.texte)
        # Une action claire vaut mieux qu'une composition riche et vague.
        self.assertIn("ONE clear pedagogical action", self.texte)
        # « Plus simple » veut dire moins d'objets concurrents, jamais moins
        # de mots : le run 16 avait lu l'inverse et rendu des prompts de
        # 257 caracteres remplis d'etiquettes.
        self.assertIn("SIMPLER MEANS FEWER COMPETING OBJECTS", self.texte)
        self.assertIn("It never means fewer words", self.texte)
        self.assertIn("continuous descriptive English prose", self.texte)
        # Le raisonnement precede le prompt, et l'exemple le montre en entier.
        # Le gabarit est desormais donne par l'exemple choisi par l'auteur.
        self.assertIn("THE SHAPE YOUR PROMPTS MUST HAVE", self.texte)
        self.assertIn("A CLOSE IMAGE PROMPT", self.texte)
        self.assertIn("A WIDE IMAGE PROMPT", self.texte)
        self.assertIn("the framing, the main subject and what is visible", self.texte)
        # L'animation : le phenomene d'abord, la camera en dernier.
        self.assertIn("the moving phenomenon FIRST", self.texte)
        self.assertIn("the camera LAST and discreet", self.texte)
        self.assertIn("much shorter", self.texte)

    def test_les_correspondances_concretes(self):
        for bloc in ("BATTERY", "ELECTRICITY", "MOTOR", "TRANSMISSION", "REGENERATIVE"):
            self.assertIn(bloc, self.texte)
        self.assertIn("THE FLOW IS NEVER STATIC", self.texte)

    def test_aucune_animation_decorative(self):
        self.assertIn("NEVER A DECORATIVE ANIMATION", self.texte)
        self.assertIn("logical continuation of the still image", self.texte)

    def test_les_transformations_sont_nommees(self):
        for transformation in ("electricity → motion", "energy → storage",
                               "braking → recovery", "motor → generator"):
            self.assertIn(transformation, self.texte)

    def test_le_script_doit_avoir_un_hook(self):
        self.assertIn("strong hook", self.texte)
        self.assertIn("no generic filler", self.texte)

    def test_les_sept_axes_de_qualite(self):
        for axe in QUALITY_AXES:
            self.assertIn(axe, self.texte)

    def test_direction_artistique_verbatim(self):
        self.assertIn(prompts.STYLE_DIRECTIVE, self.texte)
        self.assertIn("VERBATIM", self.texte)

    def test_analyse_image_interdit_de_deviner(self):
        texte = prompts.image_analysis_user("le flux jaune")
        self.assertIn("ONLY what is actually visible", texte)
        self.assertIn("must not pretend it is there", texte)

    def test_analyse_video_juge_ce_qui_est_livre(self):
        texte = prompts.video_analysis_user(1, "la voix", 4.0, 5.2, "flux jaune", "anim")
        self.assertIn("not what was requested", texte)
        self.assertIn("5.2", texte)
        self.assertIn("defects", texte)


class TestTimelineEtSousTitres(unittest.TestCase):
    def setUp(self):
        self.sb = Storyboard.from_dict(board())
        self.videos = {s.id: Path(f"/tmp/shot_{s.id:02d}.mp4") for s in self.sb.shots}

    def test_les_plans_s_enchainent_sans_trou(self):
        entrees = montage.construire_timeline(self.sb, self.videos)
        self.assertEqual(entrees[0].start, 0.0)
        for precedent, suivant in zip(entrees, entrees[1:], strict=False):
            self.assertEqual(precedent.end, suivant.start)
        self.assertEqual(entrees[-1].end, 16.0)

    def test_la_voix_reste_la_reference_temporelle(self):
        """Une video trop longue est coupee, pas l'inverse."""
        analyse = VideoAnalysis(1, 7.5, "c", "c", "m", "q", "v", [], [], True)
        entrees = montage.construire_timeline(self.sb, self.videos, {1: analyse})
        self.assertEqual(entrees[0].duration, 4.0)
        self.assertIn("coupee", entrees[0].ajustement)

    def test_video_trop_courte_signalee(self):
        analyse = VideoAnalysis(1, 2.0, "c", "c", "m", "q", "v", [], [], True)
        entrees = montage.construire_timeline(self.sb, self.videos, {1: analyse})
        self.assertIn("plus courte", entrees[0].ajustement)

    def test_defauts_et_non_conformite_remontent(self):
        analyse = VideoAnalysis(1, 4.0, "c", "c", "m", "q", "v", [], ["morphing"], False)
        entrees = montage.construire_timeline(self.sb, self.videos, {1: analyse})
        self.assertIn("ne correspond pas au plan", entrees[0].remarques[0])
        self.assertIn("morphing", entrees[0].remarques)

    def test_video_manquante_refusee(self):
        with self.assertRaises(montage.MontageError) as ctx:
            montage.construire_timeline(self.sb, {1: Path("/tmp/a.mp4")})
        self.assertIn("plan 02", str(ctx.exception))

    def test_horodatage_srt(self):
        self.assertEqual(montage.horodatage(0), "00:00:00,000")
        self.assertEqual(montage.horodatage(4.5), "00:00:04,500")
        self.assertEqual(montage.horodatage(3661.25), "01:01:01,250")

    def test_sous_titres_cales_sur_la_timeline(self):
        entrees = montage.construire_timeline(self.sb, self.videos)
        srt = montage.sous_titres(entrees)
        self.assertTrue(srt.startswith("1\n00:00:00,000 --> 00:00:04,000"))
        self.assertEqual(srt.count("-->"), 4)
        for s in self.sb.shots:
            self.assertIn(s.voice.split()[0], srt)

    def test_sous_titres_deux_lignes_au_plus(self):
        entrees = montage.construire_timeline(self.sb, self.videos)
        for bloc in montage.sous_titres(entrees).strip().split("\n\n"):
            lignes = bloc.splitlines()
            self.assertLessEqual(len(lignes) - 2, 2, bloc)


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
        c = self.config_avec(GROQ_API_KEY="gsk-x", OPENAI_VISION_MODEL="")
        self.assertEqual(c.OPENAI_VISION_MODEL, "openai/gpt-oss-120b")

    def test_openai_prioritaire_sur_groq(self):
        c = self.config_avec(OPENAI_API_KEY="sk-abc", GROQ_API_KEY="gsk-def")
        self.assertFalse(c.USING_GROQ)
        self.assertIn("OpenAI", c.cerveau())

    def test_bascule_sur_groq(self):
        c = self.config_avec(GROQ_API_KEY="gsk-def")
        self.assertEqual(c.OPENAI_BASE_URL, "https://api.groq.com/openai/v1")

    def test_message_sans_cle(self):
        self.config_avec()
        from app import openai_client
        importlib.reload(openai_client)
        with self.assertRaises(openai_client.OpenAIError) as ctx:
            openai_client.client()
        self.assertIn("OPENAI_API_KEY manquante dans .env", str(ctx.exception))


class TestAutreSujet(unittest.TestCase):
    """Le prompt est ecrit sur une voiture ; la methode doit se transposer."""

    def test_la_continuite_ne_nomme_plus_de_vehicule(self):
        from app.prompts import storyboard_user
        texte = storyboard_user("Fonctionnement des écouteurs sans fil", 24, 6)
        self.assertIn("SUBJECT CONTINUITY", texte)
        self.assertNotIn("VEHICLE CONTINUITY", texte)

    def test_l_exemple_est_annonce_comme_un_exemple(self):
        from app.prompts import storyboard_user
        texte = storyboard_user("Fonctionnement des écouteurs sans fil", 24, 6)
        self.assertIn("WORKED ON ONE EXAMPLE SUBJECT", texte)
        self.assertIn("Transpose the METHOD, never the components", texte)


class TestConfigEtCli(unittest.TestCase):
    def test_les_trois_valeurs_d_entree(self):
        from app import config

        self.assertEqual(config.DURATION, 16)
        self.assertEqual(config.SHOT_COUNT, 4)
        self.assertIn("voiture", config.SUBJECT)

    def test_aucune_cle_en_dur(self):
        for chemin in (Path(__file__).resolve().parent.parent / "app").glob("*.py"):
            texte = chemin.read_text(encoding="utf-8")
            self.assertNotIn("sk-proj", texte, f"cle en dur dans {chemin.name}")
            self.assertNotRegex(texte, r'OPENAI_API_KEY\s*=\s*"sk-')

    def test_plus_aucune_generation_automatique(self):
        """Le systeme ne fabrique plus ni image ni video."""
        app = Path(__file__).resolve().parent.parent / "app"
        self.assertFalse((app / "fal_client.py").exists())
        for chemin in app.glob("*.py"):
            texte = chemin.read_text(encoding="utf-8").lower()
            self.assertNotIn("fal.run", texte, chemin.name)
            self.assertNotIn("meta.ai", texte, chemin.name)
            self.assertNotIn("playwright", texte, chemin.name)

    def test_les_commandes_existent(self):
        from app.main import build_parser

        parser = build_parser()
        extra = {"affiner": ["--shot", "1", "--image", "a.png"]}
        for commande in ("storyboard", "elements", "affiner", "analyser-videos",
                         "timeline", "montage", "valider", "selfcheck"):
            with self.subTest(commande=commande):
                args = parser.parse_args([commande] + extra.get(commande, []))
                self.assertTrue(callable(args.func))

    def test_main_sans_argument_lance_le_storyboard(self):
        from app.main import build_parser

        self.assertEqual(build_parser().parse_args(["storyboard"]).func.__name__,
                         "cmd_storyboard")


class TestElements(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        from app import config

        self.config = config
        garde = (config.OUTPUT_DIR, config.ELEMENTS_FILE, config.SHOTS_DIR)
        racine = Path(self._tmp.name)
        config.OUTPUT_DIR = racine
        config.ELEMENTS_FILE = racine / "elements.md"
        config.SHOTS_DIR = racine / "shots"

        def restaurer():
            (config.OUTPUT_DIR, config.ELEMENTS_FILE, config.SHOTS_DIR) = garde

        self.addCleanup(restaurer)

    def test_la_feuille_contient_tout_ce_qu_il_faut_pour_produire(self):
        from app.main import ecrire_elements

        sb = Storyboard.from_dict(board())
        texte = ecrire_elements(sb).read_text(encoding="utf-8")
        self.assertIn("## Script", texte)
        self.assertIn("## Visual bible", texte)
        for s in sb.shots:
            self.assertIn(f"## Plan {s.id:02d}", texte)
            self.assertIn(s.image_prompt, texte)
            self.assertIn(s.animation_prompt, texte)
            self.assertIn(s.visual_concept, texte)
            self.assertIn(f"`{s.motion_intent}`", texte)
        self.assertIn("Ce que tu fais maintenant", texte)
        self.assertIn("## Code couleur", texte)
        for entree in sb.code_couleur():
            self.assertIn(entree.notion, texte)
        # L'etape qui reecrit les animations sur les images reelles.
        self.assertIn("affiner-tout", texte)

    def test_chaque_plan_a_ses_fichiers(self):
        from app.main import ecrire_elements

        sb = Storyboard.from_dict(board())
        ecrire_elements(sb)
        for s in sb.shots:
            d = self.config.shot_dir(s.id)
            for nom in ("image_prompt.txt", "animation_prompt.txt", "voice.txt"):
                self.assertTrue((d / nom).is_file(), f"{s.slug}/{nom}")


if __name__ == "__main__":
    unittest.main()
