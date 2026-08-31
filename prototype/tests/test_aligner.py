"""L'agent d'alignement, sans reseau : on ne teste que ce qu'il verifie."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import aligner  # noqa: E402
from app.models import Storyboard  # noqa: E402
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
    def verifier(self, **over):
        return aligner._verifier(aligner._normaliser(reponse(**over)))

    def test_une_reponse_conforme_ne_leve_rien(self):
        self.assertEqual(self.verifier(), [])

    def test_une_note_trop_basse(self):
        problemes = self.verifier(mute_test=0.5)
        self.assertTrue(any("mute test" in p for p in problemes))

    def test_un_prompt_photo_trop_court(self):
        problemes = self.verifier(image_prompt=f"A close-up. {STYLE_DIRECTIVE}")
        self.assertTrue(any("too short" in p for p in problemes))

    def test_l_agent_ne_doit_pas_laisser_tomber_la_precision(self):
        """Run 36 : les prompts realignes avaient perdu materiaux et cadrage."""
        sans_camera = IMAGE.replace(
            "Camera at eye level with the busbars, 50mm feel, the "
            "windings sharp and the pack falling off. ", "")
        problemes = self.verifier(image_prompt=sans_camera)
        self.assertTrue(any("says nothing about" in p and "camera" in p
                            for p in problemes))

    def test_l_action_choisie_doit_etre_dans_l_image(self):
        problemes = self.verifier(
            chosen="the pilot pulls the sidestick and the landing gear retracts")
        self.assertTrue(any("does not show the action" in p for p in problemes))

    def test_l_animation_doit_progresser_dans_le_temps(self):
        problemes = self.verifier(
            animation_prompt="The yellow stream travels along the busbars and the "
                             "rotor turns. Everything else stays rigid in place.")
        self.assertTrue(any("progresses in time" in p for p in problemes))

    def test_chaque_manquement_part_en_consigne(self):
        problemes = self.verifier(mute_test=0.4)
        message = aligner._correction(problemes)
        self.assertIn("rejected by an automatic check", message)
        for probleme in problemes:
            self.assertIn(probleme, message)


class TestCodeCouleurTransmis(unittest.TestCase):
    def test_l_agent_recoit_le_code_du_sujet(self):
        sb = Storyboard.from_dict(board())
        bloc = aligner._code_couleur(sb)
        self.assertIn("energie", bloc)
        self.assertIn("se deplace", bloc)


if __name__ == "__main__":
    unittest.main()
