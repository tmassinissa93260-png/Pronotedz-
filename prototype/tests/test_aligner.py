"""L'agent d'alignement, sans reseau : on ne teste que ce qu'il verifie."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import aligner  # noqa: E402
from app.models import EXPLICATION_FIELDS, Storyboard  # noqa: E402
from app.openai_client import OpenAIError  # noqa: E402
from app.prompts import STYLE_DIRECTIVE  # noqa: E402
from fixtures import board  # noqa: E402

IMAGE = (
    "Close-up shot on the copper busbars where the yellow energy stream reaches the "
    "stator "
    "windings, the pack behind them at the left of the frame, the motor housing "
    "opening at the right. Camera at eye level with the busbars, 50mm feel, the "
    "windings sharp and the pack falling off. Cool key light from the upper left, "
    "brushed aluminium and dark composite materials, dark studio. "
    f"{STYLE_DIRECTIVE}"
)

ANIMATION = (
    "The yellow stream travels steadily along the busbars and reaches the stator "
    "windings, which gradually light up as it arrives; the rotor then begins to "
    "turn. Everything else stays rigid."
)


def reponse(**over):
    base = {
        "understanding": "que l'énergie part de la batterie et fait tourner le rotor",
        "candidates": [
            {"action": "the stream reaches the windings and the rotor turns",
             "explains": "the cause and its effect in one frame",
             "misses": "where the energy came from"},
            {"action": "the whole car seen from outside", "explains": "the subject",
             "misses": "everything the sentence says"},
            {"action": "a close-up on the pack alone", "explains": "where it starts",
             "misses": "what it produces"},
        ],
        "chosen": "the yellow stream reaches the stator windings and the rotor turns",
        "why_chosen": "it shows a cause producing an effect, readable without sound",
        "mute_test": 0.9,
        "image_prompt": IMAGE,
        "animation_prompt": ANIMATION,
        "visual_explanation": {
            "information": "que l'énergie stockée quitte la batterie et rejoint le moteur",
            "physical_element": "les busbars en cuivre reliant le pack au stator",
            "secondary_elements": "le pack de cellules, le stator et son rotor",
            "visual_behavior": "un flux jaune lumineux parcourt les busbars vers l'avant",
            "animation_movement": "le flux jaune travels along the busbars toward the "
                                  "stator, puis le rotor commence à tourner",
            "camera_position": "macro en contre-plongée, assez près pour lire "
                               "tout le trajet dans un seul cadre",
            "composition": "le pack à gauche, le moteur à droite, les busbars "
                           "entre les deux au centre du cadre",
        },
    }
    base.update(over)
    return base


class TestForme(unittest.TestCase):
    def test_une_reponse_complete_passe(self):
        plan = aligner._normaliser(reponse())
        self.assertEqual(plan["mute_test"], 0.9)
        self.assertEqual(len(plan["candidates"]), 3)

    def test_une_seule_piste_n_est_pas_un_choix(self):
        with self.assertRaises(OpenAIError) as ctx:
            aligner._normaliser(reponse(candidates=[{
                "action": "a", "explains": "b", "misses": "c"}]))
        self.assertIn("pistes", str(ctx.exception))

    def test_une_piste_incomplete_est_refusee(self):
        with self.assertRaises(OpenAIError) as ctx:
            aligner._normaliser(reponse(candidates=[
                {"action": "a", "explains": "b", "misses": ""},
                {"action": "a", "explains": "b", "misses": "c"},
                {"action": "a", "explains": "b", "misses": "c"}]))
        self.assertIn("misses", str(ctx.exception))

    def test_la_note_doit_etre_un_nombre(self):
        with self.assertRaises(OpenAIError):
            aligner._normaliser(reponse(mute_test="très bien"))

    def test_la_note_reste_entre_0_et_1(self):
        with self.assertRaises(OpenAIError) as ctx:
            aligner._normaliser(reponse(mute_test=1.4))
        self.assertIn("bornes", str(ctx.exception))

    def test_un_champ_vide_est_refuse(self):
        for champ in ("understanding", "chosen", "why_chosen",
                      "image_prompt", "animation_prompt"):
            with self.subTest(champ=champ), self.assertRaises(OpenAIError):
                aligner._normaliser(reponse(**{champ: "  "}))

    def test_la_direction_artistique_est_remise_si_elle_manque(self):
        nu = IMAGE.replace(STYLE_DIRECTIVE, "").strip()
        plan = aligner._normaliser(reponse(image_prompt=nu))
        self.assertIn(STYLE_DIRECTIVE, plan["image_prompt"])


class TestControles(unittest.TestCase):
    """L'agent est juge par LE validateur du storyboard, pas par une copie."""

    def verifier(self, **over):
        sb = Storyboard.from_dict(board())
        return aligner._problemes(sb, sb.shots[0],
                                  aligner._normaliser(reponse(**over)))

    def test_une_reponse_conforme_ne_leve_rien(self):
        self.assertEqual(self.verifier(), [])

    def test_une_note_trop_basse(self):
        problemes = self.verifier(mute_test=0.5)
        self.assertTrue(any("mute test" in p for p in problemes))

    def test_un_prompt_photo_trop_court(self):
        problemes = self.verifier(image_prompt=f"A close-up. {STYLE_DIRECTIVE}")
        self.assertTrue(any("state the subject" in p for p in problemes))

    def test_l_agent_ne_doit_pas_laisser_tomber_la_precision(self):
        """Run 36 : les prompts realignes avaient perdu materiaux et cadrage."""
        sans_camera = IMAGE.replace(
            "Camera at eye level with the busbars, 50mm feel, the "
            "windings sharp and the pack falling off. ", "")
        problemes = self.verifier(image_prompt=sans_camera)
        self.assertTrue(any("must explicitly state" in p and "camera" in p
                            for p in problemes))

    def test_l_agent_ne_doit_pas_casser_le_raisonnement(self):
        """Run 37 : les prompts changeaient, visual_explanation restait vieille."""
        vieux = dict(reponse()["visual_explanation"])
        vieux["animation_movement"] = "une ambiance calme et technique"
        problemes = self.verifier(visual_explanation=vieux)
        self.assertTrue(any("real motion" in p for p in problemes))

    def test_le_raisonnement_est_exige(self):
        with self.assertRaises(OpenAIError) as ctx:
            aligner._normaliser(reponse(visual_explanation=None))
        self.assertIn("visual_explanation", str(ctx.exception))

    def test_un_champ_du_raisonnement_vide(self):
        for champ in EXPLICATION_FIELDS:
            with self.subTest(champ=champ):
                vieux = dict(reponse()["visual_explanation"])
                vieux[champ] = ""
                with self.assertRaises(OpenAIError) as ctx:
                    aligner._normaliser(reponse(visual_explanation=vieux))
                self.assertIn(champ, str(ctx.exception))

    def test_l_action_choisie_doit_etre_dans_l_image(self):
        problemes = self.verifier(
            chosen="the pilot pulls the sidestick and the landing gear retracts")
        self.assertTrue(any("does not show the action" in p for p in problemes))

    def test_l_animation_doit_progresser_dans_le_temps(self):
        problemes = self.verifier(
            animation_prompt="The yellow stream travels along the busbars and the "
                             "rotor turns. Everything else stays rigid in place.")
        self.assertTrue(any("progresses over the" in p for p in problemes))

    def test_chaque_manquement_part_en_consigne(self):
        problemes = self.verifier(mute_test=0.4)
        message = aligner._correction(problemes)
        self.assertIn("rejected by an automatic check", message)
        for probleme in problemes:
            self.assertIn(probleme, message)


class TestNeJamaisDegrader(unittest.TestCase):
    """Run 37 : l'agent gagnait sur son axe en cassant tout le reste."""

    def setUp(self):
        self.sb = Storyboard.from_dict(board())
        self.shot = self.sb.shots[0]

    def test_un_plan_conforme_n_a_rien_a_se_reprocher(self):
        self.assertEqual(aligner.problemes_valides(self.sb, self.shot), [])

    def test_une_proposition_qui_degrade_est_mesurable(self):
        casse = reponse(image_prompt=f"A close-up. {STYLE_DIRECTIVE}")
        avant = aligner.problemes_valides(self.sb, self.shot)
        apres = aligner.problemes_valides(self.sb, self.shot,
                                          aligner._normaliser(casse))
        self.assertGreater(len(apres), len(avant))

    def test_la_mesure_ne_regarde_que_ce_plan(self):
        raw = board()
        raw["shots"][1]["image_prompt"] = f"A close-up. {STYLE_DIRECTIVE}"
        sb = Storyboard.from_dict(raw)
        self.assertEqual(aligner.problemes_valides(sb, sb.shots[0]), [])
        self.assertTrue(aligner.problemes_valides(sb, sb.shots[1]))


class TestCodeCouleurTransmis(unittest.TestCase):
    def test_l_agent_recoit_le_code_du_sujet(self):
        sb = Storyboard.from_dict(board())
        bloc = aligner._code_couleur(sb)
        self.assertIn("energie", bloc)
        self.assertIn("se deplace", bloc)


if __name__ == "__main__":
    unittest.main()
