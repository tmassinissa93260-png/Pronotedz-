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

    def test_un_panneau_n_est_pas_un_panoramique(self):
        """« pan » vit dans « panel ». Une animation qui nommait les joints de
        carrosserie etait lue comme un mouvement de camera, donc comme vide."""
        self.assertTrue(validator._mouvement_non_camera(
            "The red glow travels up the flank and settles along the panel seams."))
        self.assertFalse(validator._mouvement_non_camera(
            "The camera pans slowly across the bodywork."))

    def test_du_verre_fume_n_est_pas_de_la_fumee(self):
        """« smoke » vit dans « smoked glass », qui est un materiau."""
        raw = board()
        raw["shots"][0]["image_prompt"] = IMAGE.replace(
            "brushed aluminium casing", "brushed aluminium casing, smoked glass")
        self.assertEqual([x for x in valider(raw) if x.code == "PHYSIQUE"], [])

    def test_mais_la_vraie_fumee_est_toujours_refusee(self):
        raw = board()
        raw["shots"][0]["animation_prompt"] = ANIMATION.replace(
            "The camera performs", "The energy drifts as smoke. The camera performs")
        p = [x for x in valider(raw) if x.code == "PHYSIQUE"]
        self.assertIn("decor", str(p[0]))

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

    def test_un_mouvement_ecrit_en_francais_est_un_mouvement(self):
        """Le champ est le seul du raisonnement que le schema ne demande pas en
        anglais. Il etait juge sur un vocabulaire anglais : une phrase francaise
        ne passait que si elle portait par hasard une racine anglaise."""
        raw = board()
        raw["shots"][0]["visual_explanation"]["animation_movement"] = (
            "les impulsions bleues parcourent la paire torsadée jusqu'au "
            "calculateur, dont les broches s'allument à leur arrivée")
        self.assertEqual([x for x in valider(raw) if x.code == "EXPLICATION"], [])

    def test_une_preposition_n_est_pas_un_mouvement(self):
        """« entre » est ecarte du vocabulaire francais : c'est d'abord une
        preposition, et « entre le pack et le moteur » ne bouge rien."""
        raw = board()
        raw["shots"][0]["visual_explanation"]["animation_movement"] = (
            "une vue calme entre le pack et le moteur, sans rien d'autre")
        p = [x for x in valider(raw) if x.code == "EXPLICATION"]
        self.assertIn("aucun mouvement reel", str(p[0]))

    def test_une_explication_complete_passe(self):
        self.assertEqual([x for x in valider(board()) if x.code == "EXPLICATION"], [])


class TestAncrage(unittest.TestCase):
    """L'image est le premier plan de l'animation, pas une illustration."""

    def test_l_objet_nomme_en_anglais_est_trouve_directement(self):
        """Le champ est un pointeur dans le prompt photo, qui est en anglais.

        Le dictionnaire francais->anglais ne couvre que les pieces d'une
        voiture electrique : sur tout autre sujet — un barillet, un boitier,
        une aile — il ne traduit rien et le controle s'allume sur chaque plan.
        Le prompt demande donc ce champ EN ANGLAIS, nomme comme dans l'image.
        """
        raw = board()
        raw["shots"][0]["visual_explanation"]["physical_element"] = "the copper busbars"
        self.assertEqual([x for x in valider(raw) if x.code == "ANCRAGE"], [])

    def test_un_objet_absent_de_l_image_est_toujours_refuse(self):
        raw = board()
        raw["shots"][0]["visual_explanation"]["physical_element"] = "the brake caliper"
        p = [x for x in valider(raw) if x.code == "ANCRAGE"]
        self.assertIn("brake caliper", str(p[0]))

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
    def test_le_pluriel_en_ies(self):
        """Run 41 : « red batteries » six fois, batterie declaree absente."""
        self.assertTrue(validator.mot_present("battery", "the red batteries glow"))
        self.assertTrue(validator.mot_present("battery", "a single battery"))
        self.assertTrue(validator.mot_present("body", "translucent bodies"))
        self.assertTrue(validator.mot_present("assembly", "the assemblies turn"))

    def test_le_y_precede_d_une_voyelle_garde_le_pluriel_simple(self):
        self.assertTrue(validator.mot_present("key", "two keys"))
        self.assertFalse(validator.mot_present("key", "the kies"))

    """« braking » est bien « brake »."""

    def test_le_gerondif_compte(self):
        from app.validator import mot_present
        self.assertTrue(mot_present("brake", "emphasize braking mechanics"))
        self.assertTrue(mot_present("winding", "the stator windings"))
        self.assertTrue(mot_present("rotate", "the rotor is rotating"))

    def test_mais_engine_ne_se_cache_toujours_pas_dans_engineering(self):
        from app.validator import mot_present
        self.assertFalse(mot_present("engine", "3D engineering visualization"))
        self.assertFalse(mot_present("cell", "cellular structure"))


class TestPhysique(unittest.TestCase):
    """L'energie ne tourne pas en rond, et ce n'est pas de la fumee."""

    def test_l_energie_ne_boucle_pas(self):
        """Le plan 6 du run 18 : « energy flows cyclically », « a continuous
        loop », « a synchronized energy cycle ». Scientifiquement faux : la
        chaine est a sens unique, et le freinage la remonte."""
        raw = board()
        raw["shots"][0]["animation_prompt"] = (
            "Synchronize the yellow energy circulating through the battery, motor, "
            "transmission and wheels, creating a continuous loop. The flow activates "
            "the motor, resulting in rotation of the transmission and the wheels.")
        p = [x for x in valider(raw) if x.code == "PHYSIQUE"]
        self.assertTrue(p)
        self.assertIn("en rond", str(p[0]))

    def test_un_aller_retour_n_est_pas_une_boucle(self):
        """Le freinage regeneratif remonte la chaine : c'est un sens inverse,
        pas un cycle. Il doit passer."""
        raw = board()
        raw["shots"][0]["animation_prompt"] = (
            "The green energy flow reverses from the spinning wheels and travels back "
            "toward the battery as the vehicle decelerates, which makes the cells "
            "light up again. Preserve exact geometry. No deformation.")
        self.assertEqual([x for x in valider(raw) if x.code == "PHYSIQUE"], [])

    def test_l_energie_n_est_pas_de_la_fumee(self):
        raw = board()
        raw["shots"][0]["image_prompt"] = raw["shots"][0]["image_prompt"].replace(
            "Controlled yellow", "Yellow sparkle particles and soft smoke, plus yellow")
        p = [x for x in valider(raw) if x.code == "PHYSIQUE"]
        self.assertTrue(p)
        self.assertIn("decor", str(p[0]))


class TestVehiculeVerrouille(unittest.TestCase):
    """La meme voiture sombre, du premier au dernier plan.

    Ce controle ne s'allume que si la direction artistique nomme une voiture
    de reference. Le defaut n'en nomme plus : on le rallume ici, puisque
    c'est LUI qu'on teste.
    """

    def setUp(self):
        self.ancien = validator.VOITURE_REFERENCE
        validator.VOITURE_REFERENCE = True

    def tearDown(self):
        validator.VOITURE_REFERENCE = self.ancien

    def test_une_carrosserie_claire_est_refusee(self):
        raw = board()
        raw["shots"][0]["image_prompt"] = raw["shots"][0]["image_prompt"].replace(
            "dark near-black compact electric sedan", "white compact electric sedan")
        p = [x for x in valider(raw) if x.code == "VEHICULE"]
        self.assertTrue(p)
        self.assertIn("white", str(p[0]))

    def test_le_blanc_d_un_eclairage_ne_compte_pas(self):
        """« cinematic blue and white lighting » est la direction artistique."""
        raw = board()
        raw["shots"][0]["image_prompt"] = raw["shots"][0]["image_prompt"].replace(
            "Cool key lighting", "Cool blue and white key lighting")
        self.assertEqual([x for x in valider(raw) if x.code == "VEHICULE"], [])


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


class TestProgressionDansLeTemps(unittest.TestCase):
    """Sans progression, le generateur rend un instant fige qui derive."""

    def test_une_animation_sans_mot_de_progression(self):
        raw = board()
        raw["shots"][0]["animation_prompt"] = (
            ANIMATION.replace("progressively begins to rotate", "rotates")
                     .replace("travelling continuously along", "travelling along"))
        p = [x for x in valider(raw) if x.code == "TEMPS"]
        self.assertTrue(p)
        self.assertIn("progresse", str(p[0]))

    def test_une_animation_qui_dit_sa_progression_passe(self):
        self.assertEqual([x for x in valider(board()) if x.code == "TEMPS"], [])


class TestDernierPlan(unittest.TestCase):
    """Trois sujets de suite ont fini sur un plan de synthese, le plus faible."""

    def test_le_dernier_plan_ne_resume_pas(self):
        raw = board()
        raw["shots"][-1]["educational_function"] = (
            "récapituler la chaîne complète que le spectateur vient de voir")
        p = [x for x in valider(raw) if x.code == "FINAL"]
        self.assertTrue(p)
        self.assertEqual(p[0].where, "shot_04")

    def test_un_plan_intermediaire_qui_resume_ne_declenche_rien(self):
        raw = board()
        raw["shots"][0]["educational_function"] = "une vue d'ensemble du système"
        self.assertEqual([x for x in valider(raw) if x.code == "FINAL"], [])


class TestCodeCouleur(unittest.TestCase):
    """Le code couleur est celui du SUJET, pas celui de la voiture."""

    def test_aucun_code_couleur(self):
        raw = board()
        del raw["color_code"]
        p = [x for x in valider(raw) if x.code == "COULEUR"]
        self.assertIn("aucun code couleur", str(p[0]))
        self.assertIn("color_code", p[0].fix)

    def test_aucune_notion_mobile(self):
        raw = board()
        for entree in raw["color_code"]:
            entree["moving"] = False
        p = [x for x in valider(raw) if x.code == "COULEUR"]
        self.assertTrue(any("se deplace" in x.message for x in p))

    def test_un_phenomene_declare_et_jamais_montre(self):
        raw = board()
        raw["color_code"].append({"notion": "pression", "color": "red",
                                  "meaning": "la pression de l'air", "moving": True})
        p = [x for x in valider(raw) if x.code == "COULEUR"]
        self.assertIn("pression", str(p[0]))

    def test_une_couleur_d_identite_n_a_pas_a_etre_montree(self):
        """« blue = batterie » ne bouge pas : rien ne le reclame."""
        raw = board()
        raw["color_code"].append({"notion": "carrosserie", "color": "violet",
                                  "meaning": "la coque", "moving": False})
        self.assertEqual([x for x in valider(raw) if x.code == "COULEUR"], [])

    def test_le_code_du_sujet_remplace_celui_de_la_voiture(self):
        """Un sujet dont le flux est rouge : plus aucune notion voiture."""
        raw = board()
        raw["color_code"] = [
            {"notion": "flux", "color": "red", "meaning": "l'air comprimé",
             "moving": True},
            {"notion": "structure", "color": "grey", "meaning": "la carlingue",
             "moving": False},
            {"notion": "reacteur", "color": "blue", "meaning": "le moteur",
             "moving": False},
        ]
        for shot in raw["shots"]:
            shot["image_prompt"] = shot["image_prompt"].replace("yellow", "red")
            shot["animation_prompt"] = shot["animation_prompt"].replace("yellow", "red")
        self.assertEqual([x for x in valider(raw) if x.code == "COULEUR"], [])
        self.assertEqual([x for x in valider(raw) if x.code == "GRAMMAIRE"], [])

    def test_un_code_en_francais_reste_lisible_dans_un_prompt_anglais(self):
        """Run 34 : « rouge » declare, « red stream » ecrit — plus aveugle."""
        raw = board()
        raw["color_code"][0]["color"] = "jaune"
        sb = Storyboard.from_dict(raw)
        self.assertEqual(sb.notion_par_couleur()["yellow"], "energie")
        self.assertEqual([x for x in valider(raw) if x.code == "COULEUR"], [])

    def test_la_voix_ne_dit_pas_la_couleur(self):
        raw = board()
        raw["shots"][0]["voice"] = ("Le courant jaune quitte la batterie et "
                                    "rejoint le moteur en un instant.")
        p = [x for x in valider(raw) if x.code == "COULEUR"]
        self.assertTrue(p)
        self.assertIn("jaune", str(p[0]))

    def test_une_couleur_pour_deux_notions_est_refusee(self):
        from app.models import StoryboardError
        raw = board()
        raw["color_code"].append({"notion": "chaleur", "color": "blue",
                                  "meaning": "la chaleur", "moving": True})
        with self.assertRaises(StoryboardError) as ctx:
            Storyboard.from_dict(raw)
        self.assertIn("deux notions", str(ctx.exception))


class TestControleDesVideos(unittest.TestCase):
    """Ce que la video montre vraiment, compare a ce que le plan demandait."""

    def analyse(self, **over):
        from app.models import VideoAnalysis
        base = dict(
            shot_id=1, measured_duration=4.0,
            content="the battery pack, the copper busbars and the electric motor",
            framing="macro, low angle",
            movement="the yellow energy streams travel along the busbars and the "
                     "rotor turns",
            quality="sharp and stable",
            voice_match="what is shown matches the narration",
            pedagogical_elements=["yellow energy flow entering the stator windings"],
            defects=[], matches_plan=True)
        base.update(over)
        return VideoAnalysis(**base)

    def controle(self, **over):
        sb = Storyboard.from_dict(board())
        return validator.controler_videos(sb, {1: self.analyse(**over)})

    def test_une_video_conforme_ne_leve_rien_sur_son_plan(self):
        self.assertEqual([p for p in self.controle() if p.where == "shot_01"], [])

    def test_une_video_non_conforme(self):
        p = self.controle(matches_plan=False)
        self.assertIn("VIDEO", [x.code for x in p if x.where == "shot_01"])

    def test_seule_la_camera_bouge(self):
        p = self.controle(movement="the camera slowly zooms in on the pack")
        self.assertIn("MOUVEMENT", [x.code for x in p if x.where == "shot_01"])

    def test_l_element_pedagogique_est_absent_de_l_ecran(self):
        p = self.controle(content="a car driving on a road",
                          movement="the car moves forward",
                          pedagogical_elements=[])
        self.assertIn("ELEMENT", [x.code for x in p if x.where == "shot_01"])

    def test_un_ecart_de_duree(self):
        p = self.controle(measured_duration=6.5)
        self.assertIn("DUREE", [x.code for x in p if x.where == "shot_01"])

    def test_none_observed_n_est_pas_un_defaut(self):
        p = self.controle(defects=["None observed", "aucun"])
        self.assertEqual([x for x in p if x.code == "DEFAUT"], [])

    def test_un_vrai_defaut_est_signale(self):
        p = self.controle(defects=["the rotor morphs into a second wheel"])
        self.assertIn("DEFAUT", [x.code for x in p])

    def test_une_video_absente(self):
        sb = Storyboard.from_dict(board())
        p = validator.controler_videos(sb, {})
        self.assertEqual(len(p), 4)
        self.assertTrue(all(x.code == "VIDEO" for x in p))

    def test_les_plans_a_refaire(self):
        p = self.controle(matches_plan=False)
        self.assertEqual(validator.a_refaire(p),
                         ["shot_01", "shot_02", "shot_03", "shot_04"])


class TestRythme(unittest.TestCase):
    """Le spectateur tranche vers trois secondes ; les durées doivent décider."""

    def durees(self, valeurs):
        raw = board(n=len(valeurs))
        for shot, d in zip(raw["shots"], valeurs, strict=True):
            shot["duration_seconds"] = d
        return [x for x in valider(raw, duration=sum(valeurs), shots=len(valeurs))
                if x.code == "RYTHME"]

    def test_un_plan_d_ouverture_qui_s_etale(self):
        p = self.durees([5.0, 3.0, 4.0, 4.0])
        self.assertTrue(any("decision se prend" in x.message for x in p))

    def test_un_plan_d_ouverture_court_passe(self):
        p = self.durees([2.5, 4.5, 4.0, 5.0])
        self.assertEqual(p, [])

    def test_des_durees_toutes_identiques(self):
        p = self.durees([3.0, 3.0, 3.0, 3.0])
        self.assertTrue(any("durent tous" in x.message for x in p))

    def test_un_plan_unique_n_a_pas_de_rythme(self):
        raw = board(n=1)
        self.assertEqual([x for x in valider(raw, duration=4, shots=1)
                          if x.code == "RYTHME"], [])


class TestCorrectionPartielle(unittest.TestCase):
    """Réécrire huit plans pour en corriger trois coûte huit plans en sortie."""

    def probleme(self, ou):
        return validator.Problem("PRECISION", ou, "message", "fix")

    def test_les_plans_fautifs_sont_reperes(self):
        p = [self.probleme("shot_03"), self.probleme("shot_01"),
             self.probleme("shot_03")]
        self.assertEqual(validator.plans_fautifs(p), [1, 3])

    def test_un_manquement_du_plateau_impose_un_tour_complet(self):
        p = [self.probleme("shot_03"), self.probleme("storyboard")]
        self.assertEqual(validator.plans_fautifs(p), [])

    def test_la_consigne_ne_demande_que_les_plans_fautifs(self):
        p = [self.probleme("shot_02"), self.probleme("shot_05")]
        consigne = validator.correction_partielle([2, 5], p)
        self.assertIn("#2, #5", consigne)
        self.assertIn("Return ONLY those shots", consigne)
        self.assertIn("do not return it", consigne)
        for x in p:
            self.assertIn(x.fix, consigne)


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
