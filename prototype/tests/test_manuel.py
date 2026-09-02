"""Le mode manuel : le meme prompt, les memes controles, zero appel reseau."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import aligner, manuel, prompts, redacteur, validator  # noqa: E402
from app.models import Storyboard  # noqa: E402
from app.openai_client import OpenAIError  # noqa: E402
from fixtures import board  # noqa: E402
from test_redacteur import SCRIPT, reponse  # noqa: E402


class TestPrompts(unittest.TestCase):
    """Le prompt manuel doit etre CELUI de l'API, pas une version simplifiee."""

    def test_le_prompt_texte_contient_les_deux_moities(self):
        p = manuel.prompt_texte("Comment vole un avion", 32.0, 8)
        self.assertIn(prompts.SCRIPT_SYSTEM.strip(), p)
        self.assertIn(prompts.script_user("Comment vole un avion", 32.0, 8).strip(), p)

    def test_le_prompt_storyboard_porte_le_script_deja_ecrit(self):
        p = manuel.prompt_storyboard("Sujet", 16.0, 4, SCRIPT)
        self.assertIn(SCRIPT, p)
        self.assertIn(prompts.STORYBOARD_SYSTEM.strip(), p)

    def test_le_prompt_d_alignement_est_celui_de_l_agent(self):
        sb = Storyboard.from_dict(board())
        shot = sb.shots[0]
        self.assertIn(aligner.demande(sb, shot).strip(),
                      manuel.prompt_alignement(sb, shot))

    def test_le_format_de_sortie_est_rappele(self):
        # L'API imposait le JSON par response_format ; l'interface web, non.
        self.assertIn("JSON object only", manuel.prompt_texte("S", 16.0, 4))


class TestFiche(unittest.TestCase):
    def test_le_bloc_survit_a_des_accents_graves(self):
        fiche = manuel.fiche("Titre", "un prompt avec ``` dedans", "colle ça")
        self.assertIn("````", fiche)
        self.assertIn("un prompt avec ``` dedans", fiche)

    def test_un_prompt_ordinaire_garde_trois_accents(self):
        self.assertIn("\n```\n", manuel.fiche("T", "un prompt normal", "colle"))


class TestJsonColle(unittest.TestCase):
    """Personne ne nettoie une reponse a la main sur un telephone."""

    def test_les_clotures_markdown_sont_ignorees(self):
        self.assertEqual(manuel.json_colle('```json\n{"a": 1}\n```'), {"a": 1})

    def test_une_phrase_de_politesse_est_ignoree(self):
        colle = 'Bien sûr ! Voici le JSON :\n{"a": 1}\nDis-moi si ça convient.'
        self.assertEqual(manuel.json_colle(colle), {"a": 1})

    def test_une_copie_coupee_le_dit(self):
        with self.assertRaises(OpenAIError) as ctx:
            manuel.json_colle('{"a": {"b": 1}, "c": ')
        self.assertIn("continue", str(ctx.exception))

    def test_rien_de_colle(self):
        with self.assertRaises(OpenAIError):
            manuel.json_colle("   ")

    def test_du_texte_sans_json(self):
        with self.assertRaises(OpenAIError) as ctx:
            manuel.json_colle("je ne peux pas répondre à cette demande")
        self.assertIn("aucun objet JSON", str(ctx.exception))


class TestRelire(unittest.TestCase):
    """Une reponse collee passe EXACTEMENT les controles de la boucle."""

    def test_un_texte_conforme_passe(self):
        texte, problemes = manuel.relire_texte(reponse(), 24.0, 6)
        self.assertEqual(problemes, [])
        self.assertEqual(texte["script"], SCRIPT)

    def test_un_texte_fautif_rend_les_memes_points_que_la_boucle(self):
        brut = reponse()
        attendus = redacteur._problemes(redacteur._normaliser(brut), 16.0, 3)
        _, problemes = manuel.relire_texte(brut, 16.0, 3)
        self.assertEqual(problemes, attendus)
        self.assertTrue(problemes)

    def test_un_storyboard_conforme_passe(self):
        sb, problemes = manuel.relire_storyboard(board(), 16.0, 4)
        self.assertEqual(problemes, [])
        self.assertEqual(len(sb.shots), 4)

    def test_le_storyboard_colle_est_juge_par_le_validateur(self):
        brut = board()
        brut["shots"][1]["voice"] = brut["shots"][0]["voice"]
        _, problemes = manuel.relire_storyboard(brut, 16.0, 4)
        self.assertTrue(problemes)
        self.assertEqual([p.code for p in problemes],
                         [p.code for p in validator.validate(
                             Storyboard.from_dict(brut), 16.0, 4)])

    def test_la_direction_artistique_est_reimposee_sur_le_prompt_colle(self):
        brut = board()
        brut["shots"][0]["image_prompt"] = "A battery pack."
        sb, _ = manuel.relire_storyboard(brut, 16.0, 4)
        self.assertIn(prompts.STYLE_DIRECTIVE, sb.shots[0].image_prompt)

    def test_un_storyboard_de_forme_invalide_est_refuse(self):
        from app.models import StoryboardError
        with self.assertRaises(StoryboardError):
            manuel.relire_storyboard({"subject": "x"}, 16.0, 4)


class TestConsigne(unittest.TestCase):
    """La correction a recoller est celle que la boucle renvoyait."""

    def test_texte(self):
        problemes = ["the script has 6 sentences, 3 were asked for"]
        self.assertEqual(manuel.consigne("texte", problemes),
                         redacteur.consigne(problemes))

    def test_storyboard(self):
        problemes = validator.validate(Storyboard.from_dict(board()), 99.0, 4)
        self.assertTrue(problemes)
        self.assertEqual(manuel.consigne("storyboard", problemes),
                         validator.correction_request(problemes))

    def test_aligner(self):
        problemes = ["the mute test scores 0.2"]
        self.assertEqual(manuel.consigne("aligner", problemes),
                         aligner.consigne(problemes))

    def test_la_consigne_dit_de_ne_rendre_que_le_json(self):
        self.assertIn("only the JSON", manuel.consigne("texte", ["x"]))


class TestBoutABout(unittest.TestCase):
    """Le tour complet : prompt -> reponse collee -> fichier ecrit."""

    def test_le_texte_colle_devient_texte_json(self):
        import tempfile

        from app import config, main
        with tempfile.TemporaryDirectory() as tmp:
            ancien_out, ancien_txt = config.OUTPUT_DIR, config.TEXTE_FILE
            ancien_man, ancien_rep = config.MANUEL_DIR, config.REPONSE_FILE
            config.OUTPUT_DIR = Path(tmp)
            config.TEXTE_FILE = Path(tmp) / "texte.json"
            config.MANUEL_DIR = Path(tmp) / "manuel"
            config.REPONSE_FILE = config.MANUEL_DIR / "reponse.json"
            try:
                config.MANUEL_DIR.mkdir()
                config.REPONSE_FILE.write_text(
                    "```json\n" + json.dumps(reponse()) + "\n```", encoding="utf-8")

                class Args:
                    etape, duration, shots = "texte", 24.0, 6
                    fichier, shot = str(config.REPONSE_FILE), 0
                    subject = "Comment on produit de l'électricité"

                self.assertEqual(main.cmd_coller(Args()), 0)
                ecrit = json.loads(config.TEXTE_FILE.read_text(encoding="utf-8"))
                self.assertEqual(ecrit["script"], SCRIPT)
            finally:
                config.OUTPUT_DIR, config.TEXTE_FILE = ancien_out, ancien_txt
                config.MANUEL_DIR, config.REPONSE_FILE = ancien_man, ancien_rep


if __name__ == "__main__":
    unittest.main()
