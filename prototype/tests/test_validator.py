"""Les 10 verifications, une par une, sans jamais appeler OpenAI."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import validator  # noqa: E402
from app.models import Storyboard  # noqa: E402
from app.prompts import STYLE_DIRECTIVE  # noqa: E402

# Un prompt photo qui satisfait les 5 familles de specificite exigees.
BON_PROMPT = (
    "Macro shot of the battery pack beneath the floor of the white compact electric "
    "sedan, positioned centre frame with the prismatic cells running left to right and "
    "the copper busbars visible above them, running forward to the electric motor "
    "mounted at the front axle. Camera at low angle, 50mm lens feel, shallow depth so "
    "the nearest module is sharp and the rear of the pack falls off. Lighting is a cool "
    "key from the upper left with soft volumetric haze in the dark studio. Materials: "
    "matte white paint, brushed aluminium casing, dark composite tray. The cells, the "
    "motor housing, the transmission casing and the near wheel hub must all be "
    f"unmistakably visible. {STYLE_DIRECTIVE}"
)


VOIX = [
    "La batterie stocke l'énergie et alimente ensuite le moteur électrique.",
    "Le moteur reçoit ce courant continu et le convertit en rotation utile.",
    "Cette rotation traverse la transmission avant d'atteindre chaque roue motrice.",
    "Les roues transmettent enfin cette rotation au sol et le véhicule avance.",
]


def shot(i=1, **over):
    base = {
        "id": i,
        "duration_seconds": 4.0,
        "voice": VOIX[i - 1],
        "visual_description": f"Battery pack of the white sedan, shot {i}.",
        "educational_function": f"Montre le maillon {i} de la chaîne causale, "
                               f"et pourquoi il alimente le suivant.",
        "image_prompt": BON_PROMPT,
        "semantic_alignment_score": 0.95,
    }
    base.update(over)
    return base


def board(n=4, **over):
    base = {
        "subject": "Fonctionnement d'une voiture électrique",
        "duration_seconds": 16,
        "shot_count": n,
        "visual_bible": {
            "vehicle": "White compact electric sedan, modern design, realistic proportions",
            "environment": "Dark technical studio, night-blue grey backdrop",
            "materials": "Matte white body, brushed aluminium, dark composite, visible copper",
            "lighting": "Cinematic key light, high contrast, subtle volumetric haze",
            "color_palette": "White, graphite, night blue, copper accents",
            "camera_language": "Slow controlled moves, 35-85mm feel",
        },
        "shots": [shot(i) for i in range(1, n + 1)],
    }
    base.update(over)
    return base


def valider(raw, duration=16, shots=4):
    return validator.validate(Storyboard.from_dict(raw), duration, shots)


def codes(problems):
    return sorted({p.code for p in problems})


class TestStoryboardAcceptable(unittest.TestCase):
    def test_un_storyboard_conforme_ne_leve_aucun_probleme(self):
        self.assertEqual(valider(board()), [])


class TestVerification1NombreDePlans(unittest.TestCase):
    def test_trop_peu_de_plans(self):
        p = valider(board(n=3))
        self.assertIn("PLANS", codes(p))
        self.assertIn("3 plan(s) au lieu de 4", str(p[0]))


class TestVerification2Duree(unittest.TestCase):
    def test_somme_des_durees_differente_du_total(self):
        raw = board()
        raw["shots"][0]["duration_seconds"] = 8.0
        self.assertIn("DUREE", codes(valider(raw)))

    def test_duree_negative(self):
        raw = board(n=2)
        raw["shots"][0]["duration_seconds"] = -1
        raw["shots"][1]["duration_seconds"] = 17
        self.assertIn("DUREE", codes(valider(raw, shots=2)))

    def test_repartition_libre_acceptee_si_le_total_tient(self):
        raw = board()
        raw["shots"][0]["duration_seconds"] = 5.0
        raw["shots"][0]["voice"] = ("La batterie stocke l'énergie chimique puis la "
                                    "libère vers le moteur électrique du véhicule.")
        raw["shots"][1]["duration_seconds"] = 3.0
        raw["shots"][1]["voice"] = "Le moteur transforme cette énergie en rotation."
        self.assertNotIn("DUREE", codes(valider(raw)))


class TestVerification2bisDebit(unittest.TestCase):
    def test_phrase_trop_courte_pour_la_duree(self):
        raw = board(n=1)
        raw["shots"][0].update(duration_seconds=16, voice="La batterie.")
        p = valider(raw, shots=1)
        self.assertIn("DEBIT", codes(p))
        self.assertIn("trop courte", str(p[0]))

    def test_phrase_impossible_a_prononcer(self):
        raw = board(n=1)
        raw["shots"][0].update(
            duration_seconds=16,
            voice=" ".join(["batterie moteur roue câble énergie rotation"] * 15))
        p = valider(raw, shots=1)
        self.assertIn("DEBIT", codes(p))
        self.assertIn("impossible", str([x for x in p if x.code == "DEBIT"][0]))

    def test_le_conseil_donne_un_nombre_de_mots_cible(self):
        raw = board(n=1)
        raw["shots"][0].update(duration_seconds=16, voice="La batterie.")
        fix = [x for x in valider(raw, shots=1) if x.code == "DEBIT"][0].fix
        self.assertIn("43 words", fix)


class TestVerification3Fonction(unittest.TestCase):
    def test_fonction_pedagogique_trop_vague(self):
        raw = board()
        raw["shots"][0]["educational_function"] = "Montre la batterie."
        self.assertIn("FONCTION", codes(valider(raw)))

    def test_ids_non_contigus(self):
        raw = board(n=2)
        raw["shots"][1]["id"] = 7
        raw["shots"][0]["duration_seconds"] = 8
        raw["shots"][1]["duration_seconds"] = 8
        self.assertIn("IDS", codes(valider(raw, shots=2)))


class TestVerification6DirectionArtistique(unittest.TestCase):
    def test_direction_artistique_absente(self):
        raw = board()
        raw["shots"][2]["image_prompt"] = BON_PROMPT.replace(STYLE_DIRECTIVE, "")
        p = [x for x in valider(raw) if x.code == "STYLE"]
        self.assertEqual(len(p), 1)
        self.assertEqual(p[0].where, "shot_03")

    def test_presente_dans_les_quatre(self):
        self.assertEqual([x for x in valider(board()) if x.code == "STYLE"], [])


class TestVerification5Specificite(unittest.TestCase):
    def test_prompt_photo_trop_general(self):
        raw = board()
        raw["shots"][0]["image_prompt"] = f"Electric motor in a car. {STYLE_DIRECTIVE}"
        p = [x for x in valider(raw) if x.code == "PRECISION"]
        self.assertTrue(p)
        self.assertIn("trop general", " ".join(str(x) for x in p))

    def test_la_direction_artistique_ne_compte_pas_comme_de_la_precision(self):
        """Sinon un prompt vide passerait, porte par la seule phrase commune."""
        raw = board()
        raw["shots"][0]["image_prompt"] = f"A car. {STYLE_DIRECTIVE}"
        self.assertIn("PRECISION", codes(valider(raw)))

    def test_signale_les_familles_manquantes(self):
        raw = board()
        raw["shots"][0]["image_prompt"] = (
            "A very long description of the white sedan battery pack repeated at "
            "length so that the character count is comfortably above the minimum "
            "threshold, mentioning the pack and the sedan and the studio again and "
            "again without ever saying how it is framed or lit or made of what. "
            f"{STYLE_DIRECTIVE}")
        message = str([x for x in valider(raw) if x.code == "PRECISION"][0])
        self.assertTrue(any(f in message for f in ("cadrage", "camera", "lumiere", "materiaux")))


class TestVerification7Continuite(unittest.TestCase):
    def test_prompt_qui_ne_reprend_rien_de_la_bible(self):
        raw = board()
        raw["shots"][1]["image_prompt"] = (
            "Macro shot of the cells and the motor housing, positioned centre frame, "
            "camera at low angle with a 50mm lens feel and shallow depth of field, lit "
            "by a cool key from the upper left, brushed aluminium and copper materials "
            "clearly readable, everything unmistakably visible in the frame. "
            f"{STYLE_DIRECTIVE}")
        self.assertIn("CONTINUITE", codes(valider(raw)))

    def test_bible_reprise_partout(self):
        self.assertEqual([x for x in valider(board()) if x.code == "CONTINUITE"], [])


class TestVerification8Alignement(unittest.TestCase):
    def test_score_sous_le_seuil(self):
        raw = board()
        raw["shots"][0]["semantic_alignment_score"] = 0.6
        p = [x for x in valider(raw) if x.code == "ALIGNEMENT"]
        self.assertIn("0.6", str(p[0]))

    def test_score_hors_bornes(self):
        raw = board()
        raw["shots"][0]["semantic_alignment_score"] = 1.4
        self.assertIn("ALIGNEMENT", codes(valider(raw)))

    def test_la_voix_parle_d_un_composant_invisible(self):
        """WHAT IS SAID = WHAT IS SHOWN, verifie et pas seulement demande."""
        raw = board()
        raw["shots"][0]["image_prompt"] = (
            "Macro shot of the white compact sedan battery pack in the dark studio, "
            "cells centre frame, camera at low angle, 50mm lens feel, shallow depth, "
            "cool key light from the upper left, brushed aluminium and dark composite "
            f"materials, the cells clearly visible. {STYLE_DIRECTIVE}")
        p = [x for x in valider(raw) if x.code == "ALIGNEMENT"]
        self.assertTrue(p)
        self.assertIn("moteur", str(p[0]))

    def test_composant_nomme_et_montre_passe(self):
        raw = board(n=1)
        raw["shots"][0].update(
            duration_seconds=16,
            voice=("La batterie alimente le moteur, dont le rotor entraîne "
                   "ensuite les roues du véhicule en rotation continue."),
            image_prompt=BON_PROMPT.replace(
                "the motor housing,", "the motor housing with its rotor and stator,"))
        self.assertEqual([x for x in valider(raw, shots=1) if x.code == "ALIGNEMENT"], [])


class TestVerification9Progression(unittest.TestCase):
    def test_deux_plans_disent_la_meme_chose(self):
        raw = board()
        raw["shots"][1]["voice"] = raw["shots"][0]["voice"]
        self.assertIn("PROGRESSION", codes(valider(raw)))

    def test_deux_plans_revendiquent_la_meme_fonction(self):
        raw = board()
        raw["shots"][1]["educational_function"] = raw["shots"][0]["educational_function"]
        self.assertIn("PROGRESSION", codes(valider(raw)))


class TestDemandeDeCorrection(unittest.TestCase):
    def test_le_message_liste_chaque_correction(self):
        raw = board(n=3)
        raw["shots"][0]["semantic_alignment_score"] = 0.2
        problems = valider(raw)
        message = validator.correction_request(problems)
        self.assertIn("rejected by an automatic validator", message)
        for p in problems:
            self.assertIn(p.fix, message)

    def test_le_message_est_en_anglais_et_sans_bavardage(self):
        message = validator.correction_request(valider(board(n=2)))
        self.assertIn("return only the JSON", message)


if __name__ == "__main__":
    unittest.main()
