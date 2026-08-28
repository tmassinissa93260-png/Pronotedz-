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
        """Un champ qui DECRIT ne peut pas tenir en trois mots."""
        raw = board()
        raw["shots"][0]["visual_explanation"]["composition"] = "plan large"
        p = [x for x in valider(raw) if x.code == "EXPLICATION"]
        self.assertIn("composition", str(p[0]))

    def test_un_champ_qui_nomme_a_le_droit_d_etre_court(self):
        """« Battery cells » nomme un objet precis : c'est une bonne reponse."""
        raw = board()
        raw["shots"][0]["visual_explanation"]["physical_element"] = "battery cells"
        self.assertEqual([x for x in valider(raw) if x.code == "EXPLICATION"], [])

    def test_mais_pas_le_droit_d_etre_vide_de_sens(self):
        raw = board()
        raw["shots"][0]["visual_explanation"]["physical_element"] = "le tout"
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


class TestAncrage(unittest.TestCase):
    """L'image est le premier plan de l'animation, pas une illustration."""

    def test_une_destination_ne_met_rien_dans_le_cadre(self):
        """Le defaut vu en production sur le plan du freinage regeneratif :
        l'animation ramene l'energie « vers la batterie », le prompt photo ne
        nomme la batterie que comme destination, et la video montre un flux
        vert qui sort du cadre."""
        raw = board()
        raw["shots"][0]["image_prompt"] = (
            "Side view of the wheels and gear assembly of the white compact electric "
            "sedan during braking, the hub and the brake disc at centre frame, the drive "
            "gears behind them. Green luminous energy streams leave the wheels and travel "
            "back to the battery, representing the recovered energy. Camera at wheel "
            "height, 50mm lens feel, shallow depth. Cool key lighting from the upper left "
            "in the dark studio. Materials: brushed aluminium, dark composite, rubber. "
            "Preserve the wheel geometry. No text. " + IMAGE[IMAGE.find(STYLE_DIRECTIVE):])
        raw["shots"][0]["animation_prompt"] = (
            "The green energy flow reverses direction from the spinning wheels and travels "
            "back towards the battery. The wheels keep rotating while the flow returns. "
            "The chassis, the gears and the hub stay perfectly rigid. Slow secondary "
            "camera tracking along the flow. Preserve exact geometry. No deformation.")
        raw["shots"][0]["visual_explanation"]["physical_element"] = "the drive wheels and hub"
        p = [x for x in valider(raw) if x.code == "ANCRAGE"]
        self.assertTrue(p)
        self.assertIn("destination", str(p[0]))
        self.assertIn("battery", str(p[0]))

    def test_un_objet_jamais_nomme_dans_l_image(self):
        raw = board()
        raw["shots"][0]["animation_prompt"] = (
            raw["shots"][0]["animation_prompt"]
            + " The brake calipers clamp the discs as the vehicle slows.")
        p = [x for x in valider(raw) if x.code == "ANCRAGE"]
        self.assertTrue(p)
        self.assertIn("absent du prompt photo", str(p[0]))

    def test_le_moteur_est_dans_le_cadre_par_ses_pieces(self):
        """Un prompt qui cadre le stator et le rotor montre bien le moteur."""
        self.assertEqual([x for x in valider(board()) if x.code == "ANCRAGE"], [])

    def test_l_objet_principal_doit_etre_dans_le_prompt_photo(self):
        raw = board()
        raw["shots"][0]["visual_explanation"]["physical_element"] = (
            "le pédalier et son capteur de position")
        p = [x for x in valider(raw) if x.code == "ANCRAGE"]
        self.assertIn("pas dans le prompt photo", str(p[0]))

    def test_le_vehicule_entier_n_est_pas_un_objet(self):
        raw = board()
        raw["shots"][0]["visual_explanation"]["physical_element"] = "the whole car"
        p = [x for x in valider(raw) if x.code == "ANCRAGE"]
        self.assertIn("aucun objet precis", str(p[0]))

    def test_l_ancrage_traverse_les_langues(self):
        """Le raisonnement peut dire « le moteur » quand le prompt dit « motor »."""
        raw = board()
        raw["shots"][0]["visual_explanation"]["physical_element"] = "le moteur électrique"
        self.assertEqual([x for x in valider(raw) if x.code == "ANCRAGE"], [])

    def test_une_image_qui_porte_tout_passe(self):
        self.assertEqual([x for x in valider(board()) if x.code == "ANCRAGE"], [])


class TestCouleursDIdentite(unittest.TestCase):
    """Une couleur d'identite n'a pas a se deplacer."""

    def test_l_eclairage_bleu_n_est_pas_une_notion_pedagogique(self):
        """« cinematic blue lighting » est impose par la direction artistique.
        Le run 18 le comptait comme une representation de la batterie, et
        reclamait ensuite qu'elle bouge."""
        from app.validator import notions_pedagogiques
        self.assertNotIn("batterie", notions_pedagogiques(
            "The cinematic blue lighting enhances the energy glow inside the cells"))
        self.assertIn("energie", notions_pedagogiques(
            "controlled yellow energy streams travel along the busbars"))

    def test_le_gris_de_la_mecanique_n_a_pas_a_bouger(self):
        raw = board()
        raw["shots"][0]["image_prompt"] = raw["shots"][0]["image_prompt"].replace(
            "dark composite tray.",
            "dark composite tray, grey mechanical power transfer housing.")
        self.assertEqual([x for x in valider(raw)
                          if x.code == "CORRESPONDANCE" and "mecanique" in x.message], [])

    def test_un_flux_jaune_doit_toujours_bouger(self):
        raw = board()
        raw["shots"][0]["animation_prompt"] = (
            "The central rotor progressively begins to rotate as the transmission "
            "gears turn with it, and the wheels follow. Everything else stays rigid. "
            "Preserve exact geometry, proportions and materials. No deformation.")
        p = [x for x in valider(raw) if x.code == "CORRESPONDANCE"]
        self.assertTrue(p)
        self.assertIn("energie", str(p[0]))


class TestFlexions(unittest.TestCase):
    """« braking » est bien « brake »."""

    def test_le_gerondif_compte(self):
        from app.validator import _mot_present
        self.assertTrue(_mot_present("brake", "emphasize braking mechanics"))
        self.assertTrue(_mot_present("winding", "the stator windings"))
        self.assertTrue(_mot_present("rotate", "the rotor is rotating"))

    def test_mais_engine_ne_se_cache_toujours_pas_dans_engineering(self):
        from app.validator import _mot_present
        self.assertFalse(_mot_present("engine", "3D engineering visualization"))
        self.assertFalse(_mot_present("cell", "cellular structure"))


class TestAnimationDynamique(unittest.TestCase):
    """Le zoom n'est jamais le mouvement principal."""

    def test_un_seul_mouvement_laisse_la_place_a_la_camera(self):
        """Le defaut du plan 2 : le prompt ne dit pas « zoom », mais il ne
        propose qu'une chose a faire bouger, et la video rendue est un
        travelling."""
        raw = board()
        raw["shots"][0]["animation_prompt"] = (
            "The yellow/orange energy flow travels rapidly along the cables in a "
            "directional motion heading from the battery toward the motor. The focus "
            "remains on this movement, ensuring the clear path and dynamic progression "
            "of the flow through the cables, with nothing else changing in the frame.")
        p = [x for x in valider(raw) if x.code == "DYNAMIQUE"]
        self.assertTrue(p)
        self.assertIn("un seul mouvement", str(p[0]))

    def test_un_zoom_ne_compte_pas_comme_mouvement(self):
        raw = board()
        raw["shots"][0]["animation_prompt"] = (
            "Slow cinematic zoom toward the motor, the camera pushing in steadily on "
            "the stator windings while the composition tightens around them, holding "
            "the premium studio atmosphere throughout the shot.")
        p = [x for x in valider(raw) if x.code == "DYNAMIQUE"]
        self.assertIn("aucun mouvement", str(p[0]))

    def test_des_mouvements_juxtaposes_sans_lien(self):
        raw = board()
        raw["shots"][0]["animation_prompt"] = (
            "The yellow energy streams travel along the copper busbars. The central "
            "rotor rotates steadily. The cells, the busbars and the chassis stay "
            "perfectly rigid. Preserve exact geometry, proportions and materials.")
        p = [x for x in valider(raw) if x.code == "DYNAMIQUE"]
        self.assertTrue(p)
        self.assertIn("juxtaposes", str(p[0]))

    def test_une_chaine_mecanique_de_rotations_passe(self):
        """Rotor puis transmission puis roues : une seule famille, mais bien
        plusieurs mouvements coordonnes. Le run 17 avait ete refuse a tort."""
        raw = board()
        raw["shots"][0]["animation_prompt"] = (
            "The motor rotor's turn sets off a chain reaction: the transmission gears "
            "begin rotating, subsequently causing the wheels to spin. The chassis and "
            "the bodywork stay perfectly rigid throughout. Preserve exact geometry, "
            "proportions and materials. No deformation, no floating parts.")
        self.assertEqual([x for x in valider(raw) if x.code == "DYNAMIQUE"], [])

    def test_une_piece_traversee_par_un_flux_ne_bouge_pas(self):
        """« along the cables from the battery toward the motor » ne fait
        bouger que le flux : trois pieces nommees, aucune en mouvement."""
        from app.validator import _composants_en_mouvement
        self.assertEqual(_composants_en_mouvement(
            "the flow travels along the cables from the battery toward the motor"), [])
        self.assertEqual(_composants_en_mouvement(
            "the central rotor begins to rotate"), ["rotor"])

    def test_une_chaine_causale_passe(self):
        """« As the pulses reach the windings, the rotor begins to rotate »."""
        self.assertEqual([x for x in valider(board()) if x.code == "DYNAMIQUE"], [])


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
