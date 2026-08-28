"""Les verifications, une par une. Aucun appel reseau."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import validator  # noqa: E402
from app.models import Storyboard  # noqa: E402
from app.prompts import STYLE_DIRECTIVE  # noqa: E402
from fixtures import ANIMATION, IMAGE, board  # noqa: E402


def valider(raw, duration=16, shots=4):
    return validator.validate(Storyboard.from_dict(raw), duration, shots)


def codes(problems):
    return sorted({p.code for p in problems})


class TestConforme(unittest.TestCase):
    def test_un_storyboard_conforme_ne_leve_rien(self):
        self.assertEqual(valider(board()), [])


class TestGrammaireVisuelle(unittest.TestCase):
    """LA regle : rendre visible ce que la voix nomme et qu'on ne voit pas."""

    def test_phenomene_invisible_sans_representation_coloree(self):
        raw = board()
        raw["shots"][0]["image_prompt"] = IMAGE.replace(
            "Controlled yellow luminous energy streams travel along the busbars, clearly "
            "representing the electrical current leaving the pack. ", "")
        p = [x for x in valider(raw) if x.code == "GRAMMAIRE"]
        self.assertTrue(p)
        self.assertIn("phenomene invisible", str(p[0]))

    def test_la_couleur_doit_porter_un_phenomene_pas_un_objet(self):
        """« yellow paint » n'est pas une representation de l'electricite."""
        self.assertEqual(validator.notions_pedagogiques("a car with yellow paint"), set())
        self.assertEqual(
            validator.notions_pedagogiques("yellow energy streams along the cable"),
            {"energie"})

    def test_jaune_et_orange_portent_la_meme_notion(self):
        """L'energie est jaune/orange : un flux annonce en jaune et repris en
        orange reste le meme flux, l'animation ne doit pas etre refusee."""
        self.assertEqual(validator.notions_pedagogiques("yellow energy pulses"), {"energie"})
        self.assertEqual(validator.notions_pedagogiques("orange energy pulses"), {"energie"})
        raw = board()
        raw["shots"][0]["animation_prompt"] = ANIMATION.replace("yellow", "orange")
        self.assertEqual([x for x in valider(raw) if x.code == "CORRESPONDANCE"], [])

    def test_chaque_notion_du_code_est_reconnue(self):
        for couleur, notion in (("yellow", "energie"), ("orange", "energie"),
                                ("blue", "batterie"), ("green", "recuperation"),
                                ("grey", "mecanique")):
            with self.subTest(couleur=couleur):
                self.assertEqual(
                    validator.notions_pedagogiques(f"{couleur} energy flow"), {notion})


class TestCorrespondance(unittest.TestCase):
    """Ce que l'image introduit, l'animation doit le faire bouger."""

    def test_element_pedagogique_perdu_entre_image_et_animation(self):
        raw = board()
        raw["shots"][0]["animation_prompt"] = (
            "Animate the rotor rotating progressively while the stator stays fixed. "
            "The camera performs a slow controlled macro tracking movement. Preserve exact "
            "geometry and materials. No deformation, no floating parts.")
        p = [x for x in valider(raw) if x.code == "CORRESPONDANCE"]
        self.assertTrue(p)
        self.assertIn("energie", str(p[0]))

    def test_animation_reduite_a_un_mouvement_de_camera(self):
        raw = board()
        raw["shots"][0]["animation_prompt"] = (
            "The camera slowly zooms in on the battery pack. Slow cinematic camera push in "
            "toward the cells, holding the framing steady throughout the shot duration.")
        p = [x for x in valider(raw) if x.code == "CORRESPONDANCE"]
        self.assertTrue(any("camera" in str(x) for x in p))

    def test_composant_mis_en_avant_mais_immobile(self):
        raw = board()
        raw["shots"][0]["animation_prompt"] = (
            "Animate the yellow energy streams travelling along the copper busbars toward "
            "the motor housing. Everything else stays perfectly rigid. The camera holds. "
            "Preserve exact geometry, proportions and materials. No deformation.")
        p = [x for x in valider(raw) if x.code == "CORRESPONDANCE"]
        self.assertTrue(any("rotor" in str(x) for x in p))

    def test_une_animation_complete_passe(self):
        self.assertEqual([x for x in valider(board()) if x.code == "CORRESPONDANCE"], [])

    def test_mouvement_hors_camera_detecte(self):
        self.assertTrue(validator._mouvement_non_camera(
            "The rotor rotates. The camera slowly pushes in."))
        self.assertFalse(validator._mouvement_non_camera(
            "The camera slowly zooms in. Camera pushes forward."))


class TestFluxDirectionnel(unittest.TestCase):
    """Le flux n'est jamais statique : le spectateur doit lire son sens."""

    def test_flux_sans_direction_refuse(self):
        raw = board()
        raw["shots"][0]["animation_prompt"] = (
            "The yellow energy streams pulse and shimmer around the copper busbars while "
            "the rotor rotates in place. Everything else stays perfectly rigid. Preserve "
            "exact geometry, proportions and materials. No deformation, no floating parts.")
        p = [x for x in valider(raw) if x.code == "FLUX"]
        self.assertTrue(p)
        self.assertIn("direction", str(p[0]))

    def test_flux_avec_direction_accepte(self):
        self.assertEqual([x for x in valider(board()) if x.code == "FLUX"], [])

    def test_une_inversion_compte_comme_direction(self):
        raw = board()
        raw["shots"][0]["animation_prompt"] = (
            "The yellow energy flow reverses and pulses back to the battery pack as the "
            "wheels keep rotating. The chassis stays rigid. Preserve exact geometry and "
            "materials. No deformation, no floating parts, no invented components.")
        self.assertEqual([x for x in valider(raw) if x.code == "FLUX"], [])


class TestExplicationVisuelle(unittest.TestCase):
    """Chaque phrase de narration traduite en information visuelle."""

    def test_les_quatre_temps_sont_exiges(self):
        from app.models import EXPLICATION_FIELDS, StoryboardError
        for champ in EXPLICATION_FIELDS:
            with self.subTest(champ=champ):
                raw = board()
                raw["shots"][0]["visual_explanation"][champ] = " "
                with self.assertRaises(StoryboardError) as ctx:
                    Storyboard.from_dict(raw)
                self.assertIn(champ, str(ctx.exception))

    def test_explication_trop_vague(self):
        raw = board()
        raw["shots"][0]["visual_explanation"]["physical_element"] = "le moteur"
        p = [x for x in valider(raw) if x.code == "EXPLICATION"]
        self.assertIn("physical_element", str(p[0]))

    def test_le_mouvement_doit_etre_un_vrai_mouvement(self):
        raw = board()
        raw["shots"][0]["visual_explanation"]["animation_movement"] = (
            "une ambiance premium et contemplative sur le composant")
        p = [x for x in valider(raw) if x.code == "EXPLICATION"]
        self.assertIn("aucun mouvement reel", str(p[0]))

    def test_une_explication_complete_passe(self):
        self.assertEqual([x for x in valider(board()) if x.code == "EXPLICATION"], [])


class TestQualite(unittest.TestCase):
    def test_un_axe_sous_le_seuil(self):
        raw = board()
        raw["quality_check"]["scientific_accuracy"] = 0.5
        p = [x for x in valider(raw) if x.code == "QUALITE"]
        self.assertIn("scientific_accuracy", str(p[0]))

    def test_axe_hors_bornes(self):
        raw = board()
        raw["quality_check"]["visual_quality"] = 1.4
        self.assertIn("QUALITE", codes(valider(raw)))

    def test_les_sept_axes_sont_exiges(self):
        from app.models import QUALITY_AXES, StoryboardError
        for axe in QUALITY_AXES:
            with self.subTest(axe=axe):
                raw = board()
                del raw["quality_check"][axe]
                with self.assertRaises(StoryboardError) as ctx:
                    Storyboard.from_dict(raw)
                self.assertIn(axe, str(ctx.exception))


class TestPlansEtDuree(unittest.TestCase):
    def test_mauvais_nombre_de_plans(self):
        self.assertIn("PLANS", codes(valider(board(n=3))))

    def test_somme_des_durees(self):
        raw = board()
        raw["shots"][0]["duration_seconds"] = 8.0
        self.assertIn("DUREE", codes(valider(raw)))

    def test_phrase_trop_courte_pour_la_duree(self):
        raw = board(n=1)
        raw["shots"][0].update(duration_seconds=16, voice="La batterie.")
        p = [x for x in valider(raw, shots=1) if x.code == "DEBIT"]
        self.assertIn("trop courte", str(p[0]).replace("le plan serait vide", "trop courte"))

    def test_phrase_impossible_a_prononcer(self):
        raw = board(n=1)
        raw["shots"][0].update(
            duration_seconds=16,
            voice=" ".join(["batterie moteur roue câble énergie rotation"] * 15))
        self.assertIn("DEBIT", codes(valider(raw, shots=1)))


class TestPrecisionEtStyle(unittest.TestCase):
    def test_direction_artistique_absente(self):
        raw = board()
        raw["shots"][2]["image_prompt"] = IMAGE.replace(STYLE_DIRECTIVE, "")
        p = [x for x in valider(raw) if x.code == "STYLE"]
        self.assertEqual(p[0].where, "shot_03")

    def test_prompt_photo_trop_general(self):
        raw = board()
        raw["shots"][0]["image_prompt"] = f"Electric motor in a car. {STYLE_DIRECTIVE}"
        self.assertIn("PRECISION", codes(valider(raw)))

    def test_la_direction_artistique_ne_compte_pas_comme_precision(self):
        """La couper, pas la supprimer : sinon la fin de la phrase passerait
        pour du contenu propre au plan."""
        propre = validator.own_part(f"A car. {STYLE_DIRECTIVE}")
        self.assertEqual(propre.strip(), "A car.")

    def test_prompt_animation_trop_court(self):
        raw = board()
        raw["shots"][0]["animation_prompt"] = "The yellow energy flows."
        self.assertIn("PRECISION", codes(valider(raw)))


class TestAlignementEtContinuite(unittest.TestCase):
    def test_la_voix_parle_d_un_composant_invisible(self):
        raw = board()
        # Une image qui ne montre QUE la batterie, alors que la voix du plan 1
        # nomme le moteur.
        raw["shots"][0]["image_prompt"] = (
            "Macro shot of the battery pack beneath the floor of the white compact electric "
            "sedan, prismatic cells at centre frame with yellow luminous energy streams "
            "travelling between them. Camera at low angle, 50mm lens feel, shallow depth. "
            "Cool key lighting from the upper left in the dark studio. Materials: matte "
            "white paint, brushed aluminium casing, dark composite tray. Preserve the cell "
            f"geometry. {STYLE_DIRECTIVE}")
        p = [x for x in valider(raw) if x.code == "ALIGNEMENT"]
        self.assertIn("moteur", str(p[0]))

    def test_prompt_qui_ne_reprend_rien_de_la_bible(self):
        raw = board()
        raw["shots"][1]["image_prompt"] = (
            "Macro shot of the cells and the motor housing at centre frame, camera at low "
            "angle with a 50mm lens feel and shallow depth of field, lit by a cool key from "
            "the upper left, brushed aluminium and copper materials clearly readable, with "
            "yellow energy streams travelling toward the rotor. "
            f"{STYLE_DIRECTIVE}")
        self.assertIn("CONTINUITE", codes(valider(raw)))

    def test_deux_plans_qui_disent_la_meme_chose(self):
        raw = board()
        raw["shots"][1]["voice"] = raw["shots"][0]["voice"]
        self.assertIn("PROGRESSION", codes(valider(raw)))


class TestDemandeDeCorrection(unittest.TestCase):
    def test_chaque_manquement_porte_sa_consigne(self):
        raw = board(n=3)
        raw["quality_check"]["pedagogical_clarity"] = 0.3
        problems = valider(raw)
        message = validator.correction_request(problems)
        self.assertIn("rejected by an automatic validator", message)
        for p in problems:
            self.assertIn(p.fix, message)


if __name__ == "__main__":
    unittest.main()
