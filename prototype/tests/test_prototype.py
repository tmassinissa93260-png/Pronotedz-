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

    def test_l_image_et_l_animation_sont_separees(self):
        self.assertIn("SEPARATE THE IMAGE FROM THE ANIMATION", self.texte)
        self.assertIn("describes what EXISTS", self.texte)
        self.assertIn("describes what CHANGES", self.texte)
        self.assertIn("THE PRESERVATION RULE", self.texte)
        self.assertIn("CAMERA VOCABULARY", self.texte)
        # Le vocabulaire precis, et le vague interdit.
        for mot in ("dolly push-in", "tracking shot", "orbit", "pedestal"):
            self.assertIn(mot, self.texte)
        self.assertIn('Never "cinematic movement"', self.texte)

    def test_la_physique_du_mouvement(self):
        self.assertIn("THE PHYSICS OF MOVEMENT", self.texte)
        self.assertIn("Nothing starts instantaneously", self.texte)
        self.assertIn("The rotor spins rapidly", self.texte)
        self.assertIn("TRIGGER", self.texte)

    def test_le_test_de_la_camera(self):
        """« Si je retirais la camera, comprendrait-on encore ? »"""
        self.assertIn("THE CAMERA TEST", self.texte)
        self.assertIn("would the\nviewer still understand the mechanism", self.texte)

    def test_les_trois_animations_classees(self):
        self.assertIn("THREE ANIMATIONS, RANKED", self.texte)
        self.assertIn("COMPLETE causal", self.texte)
        self.assertIn("never animate everything at once without logic", self.texte)

    def test_la_regeneration_plutot_que_le_rafistolage(self):
        """Une mauvaise animation vient souvent d'une image mal concue."""
        from app.prompts import correction_user
        avec = correction_user({"shots": []},
                               "- shot_01: one movement is not enough. Answer WHAT IS "
                               "MOVING IN THE WORLD", True)
        self.assertIn("go back to the motion design", avec)
        self.assertIn("badly designed image", avec)
        # Un manquement de forme n'entraine pas une refonte.
        sans = correction_user({"shots": []}, "- storyboard: durations must sum to 16.", False)
        self.assertNotIn("go back to the motion design", sans)

    def test_les_deux_regles_au_sommet(self):
        self.assertIn("NEVER optimise only for the beauty of an image", self.texte)
        self.assertIn("WHAT CHANGES during these few seconds", self.texte)

    def test_l_animation_dit_son_debut_et_sa_fin(self):
        for temps in ("INITIAL STATE", "PRIMARY MOTION", "SECONDARY MOTION",
                      "CAUSAL RELATION", "FINAL STATE"):
            self.assertIn(temps, self.texte)
        self.assertIn("IS THIS IMAGE WORTH ANIMATING?", self.texte)

    def test_les_retours_de_l_auteur_entrent_dans_le_prompt(self):
        """Une regle apprise une fois ne doit pas etre reapprise."""
        self.assertIn("WHAT THE AUTHOR HAS ALREADY REJECTED", self.texte)
        self.assertIn("camera-only movement is not an animation", self.texte)

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
        self.assertIn("THE SAME REASONING, WORKED THROUGH", self.texte)

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


class TestBoucleDeCorrection(unittest.TestCase):
    """Un tour de correction ne renvoie pas tout le storyboard a chaque fois."""

    def test_seuls_les_plans_fautifs_repartent(self):
        from app.openai_client import _demande_de_correction
        from app.validator import Problem
        from fixtures import board

        brut = board(4)
        problemes = [Problem("DYNAMIQUE", "shot_02", "message", "fix pour le plan 2"),
                     Problem("ETAT", "shot_04", "message", "fix pour le plan 4")]
        messages, partielle = _demande_de_correction(brut, problemes)
        self.assertTrue(partielle)
        charge = messages[-1]["content"]
        self.assertIn("fix pour le plan 2", charge)
        # Les quatre autres plans ne sont pas renvoyes.
        self.assertEqual(charge.count('"animation_prompt"'), 2)

    def test_un_manquement_global_fait_repartir_l_ensemble(self):
        from app.openai_client import _demande_de_correction
        from app.validator import Problem
        from fixtures import board

        messages, partielle = _demande_de_correction(
            board(4), [Problem("DUREE", "storyboard", "message", "fix global"),
                       Problem("ETAT", "shot_04", "message", "fix plan 4")])
        self.assertFalse(partielle)
        self.assertEqual(messages[-1]["content"].count('"animation_prompt"'), 4)

    def test_les_plans_corriges_reprennent_leur_place(self):
        from app.openai_client import _fusionner
        from fixtures import board

        brut = board(4)
        corriges = {"shots": [{"id": 3, "voice": "corrigé"}]}
        fusion = _fusionner(brut, corriges)
        self.assertEqual(len(fusion["shots"]), 4)
        self.assertEqual(fusion["shots"][2]["voice"], "corrigé")
        self.assertEqual(fusion["shots"][0], brut["shots"][0])


class TestLaBoucleGardeLeMeilleur(unittest.TestCase):
    """Un tour de correction peut degrader : il ne doit pas gagner pour autant."""

    def _faux_client(self, reponses):
        """Remplace l'appel reseau par une liste de reponses successives."""
        from app import openai_client
        suite = iter(reponses)
        d_origine = openai_client.chat_json
        openai_client.chat_json = lambda model, messages: next(suite)
        self.addCleanup(setattr, openai_client, "chat_json", d_origine)

    def test_une_correction_qui_perd_des_plans_est_refusee(self):
        from app.openai_client import generate_storyboard
        from fixtures import board

        complet = board(4)
        ampute = board(4)
        ampute["shots"] = ampute["shots"][:1]      # le modele « corrige » en abregeant
        # Le premier jet est bon mais fautif sur un point, le second ampute,
        # le troisieme repare vraiment.
        casse = board(4)
        casse["shots"][0]["visual_explanation"]["composition"] = "plan large"
        self._faux_client([casse, ampute, complet])

        sb, problemes = generate_storyboard("sujet", 16, 4)
        self.assertEqual(len(sb.shots), 4)
        self.assertEqual(problemes, [])

    def test_le_meilleur_est_garde_et_pas_le_dernier(self):
        from app.openai_client import generate_storyboard
        from fixtures import board

        bon = board(4)
        mauvais = board(4)
        for s in mauvais["shots"]:
            s["visual_explanation"]["composition"] = "flou"
            s["visual_explanation"]["camera_position"] = "vague"
        # Le bon arrive en premier, puis quatre reponses degradees.
        self._faux_client([bon] + [mauvais] * 4)

        sb, problemes = generate_storyboard("sujet", 16, 4)
        self.assertEqual(problemes, [])
        self.assertEqual(sb.shots[0].visual_explanation["composition"],
                         bon["shots"][0]["visual_explanation"]["composition"])


class TestDossiersDesPlans(unittest.TestCase):
    """Un run plus court ne laisse pas les plans du precedent derriere lui."""

    def test_les_dossiers_en_trop_partent(self):
        import tempfile
        from pathlib import Path as P

        from app import config

        with tempfile.TemporaryDirectory() as tmp:
            racine = P(tmp)
            for nom in ("OUTPUT_DIR", "SHOTS_DIR", "SCREENSHOT_DIR"):
                setattr(config, nom, racine / nom.lower())
            config.ensure_dirs(6)
            (config.SHOTS_DIR / "shot_06" / "image_prompt.txt").write_text("vieux")

            config.ensure_dirs(4)
            restants = sorted(d.name for d in config.SHOTS_DIR.glob("shot_*"))
            self.assertEqual(restants, ["shot_01", "shot_02", "shot_03", "shot_04"])

    def test_un_run_plus_long_cree_ce_qu_il_faut(self):
        import tempfile
        from pathlib import Path as P

        from app import config

        with tempfile.TemporaryDirectory() as tmp:
            racine = P(tmp)
            for nom in ("OUTPUT_DIR", "SHOTS_DIR", "SCREENSHOT_DIR"):
                setattr(config, nom, racine / nom.lower())
            config.ensure_dirs(2)
            config.ensure_dirs(5)
            self.assertEqual(len(list(config.SHOTS_DIR.glob("shot_*"))), 5)


class TestLimiteDeSortie(unittest.TestCase):
    """Un storyboard conforme depasse la limite par defaut de gpt-4o."""

    def test_la_limite_est_fixee_et_large(self):
        from app import config
        self.assertGreaterEqual(config.MAX_OUTPUT_TOKENS, 8000)

    def test_une_reponse_coupee_est_une_erreur(self):
        from app import openai_client

        class FauxChoix:
            finish_reason = "length"
            message = type("m", (), {"content": '{"partiel": true}'})()

        class FausseReponse:
            choices = [FauxChoix()]

        def faux_create(**kwargs):
            return FausseReponse()

        class FauxClient:
            chat = type("c", (), {"completions": type("cc", (), {"create": staticmethod(faux_create)})()})()

        d_origine = openai_client.client
        openai_client.client = lambda: FauxClient()
        self.addCleanup(setattr, openai_client, "client", d_origine)

        with self.assertRaises(openai_client.OpenAIError) as ctx:
            openai_client.chat_json("gpt-4o", [])
        self.assertIn("coupee", str(ctx.exception))

    def test_un_storyboard_ampute_ne_gagne_jamais(self):
        """Moins de plans veut mecaniquement dire moins de manquements : le
        run 23 a garde UN plan avec six manquements plutot que quatre."""
        from app.models import Storyboard
        from app.openai_client import _rang
        from fixtures import board

        complet = Storyboard.from_dict(board(4))
        ampute = Storyboard.from_dict(board(1))
        self.assertLess(_rang(complet, ["a"] * 12, 4), _rang(ampute, ["a"] * 6, 4))


class TestConfigEtCli(unittest.TestCase):
    def test_les_trois_valeurs_d_entree(self):
        from app import config

        self.assertEqual(config.DURATION, 16)
        # 20 plans par defaut : le nombre reste une contrainte, pas un but.
        self.assertEqual(config.SHOT_COUNT, 20)
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
