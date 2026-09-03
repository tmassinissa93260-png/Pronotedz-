"""Ce qu'on verifie d'une video sans payer un jeton. Aucun appel reseau."""

import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import mesures, prompts  # noqa: E402
from app.models import Storyboard  # noqa: E402
from fixtures import board  # noqa: E402


def rgb(*pixels) -> bytes:
    return bytes(v for p in pixels for v in p)


class TestTeintes(unittest.TestCase):
    def test_chaque_couleur_tombe_dans_sa_case(self):
        for pixel, attendu in (((255, 0, 0), "rouge"), ((255, 150, 0), "orange"),
                               ((0, 255, 0), "vert"), ((0, 255, 230), "cyan"),
                               ((0, 60, 255), "bleu"), ((160, 0, 255), "violet")):
            with self.subTest(pixel=pixel):
                self.assertEqual(list(mesures.teintes(rgb(pixel))), [attendu])

    def test_le_decor_sombre_ne_compte_pas(self):
        """Sans ce filtre, le fond de nuit noierait la mesure."""
        self.assertEqual(mesures.teintes(rgb((12, 8, 9), (30, 28, 28))), Counter())

    def test_le_gris_clair_ne_compte_pas_non_plus(self):
        self.assertEqual(mesures.teintes(rgb((200, 198, 199))), Counter())

    def test_les_parts_font_un(self):
        parts = mesures.teintes(rgb((255, 0, 0), (255, 0, 0), (0, 255, 0)))
        self.assertAlmostEqual(parts["rouge"], 2 / 3)
        self.assertAlmostEqual(parts["vert"], 1 / 3)

    def test_une_video_sans_aucun_pixel_vif(self):
        self.assertEqual(mesures.teintes(b""), Counter())


class TestJuger(unittest.TestCase):
    def base(self, **over):
        m = mesures.Mesure(shot_id=1, fichier=Path("shot_01.mp4"),
                           largeur=1080, hauteur=1920, duree=4.0, attendue=4.0,
                           couleurs=Counter({"rouge": 0.4, "bleu": 0.3}),
                           voulues=["rouge"])
        for k, v in over.items():
            setattr(m, k, v)
        return m

    def test_une_video_conforme_ne_leve_rien(self):
        self.assertEqual(mesures.juger(self.base()), [])

    def test_le_format_horizontal_est_refuse(self):
        m = self.base(largeur=1920, hauteur=1080)
        self.assertIn("9:16", mesures.juger(m)[0])

    def test_une_duree_qui_deborde_est_refusee(self):
        m = self.base(duree=10.2, attendue=4.5)
        self.assertIn("+5.7s", mesures.juger(m)[0])

    def test_un_demi_dixieme_de_seconde_passe(self):
        self.assertEqual(mesures.juger(self.base(duree=4.3)), [])

    def test_une_couleur_annoncee_mais_absente(self):
        m = self.base(couleurs=Counter({"cyan": 0.9}), voulues=["rouge"])
        self.assertIn("rouge", mesures.juger(m)[0])
        self.assertIn("0.0%", mesures.juger(m)[0])

    def test_le_cyan_ne_passe_pas_pour_du_bleu(self):
        """C'est ce que rendent les generateurs quand on demande du bleu."""
        m = self.base(couleurs=Counter({"cyan": 0.95}), voulues=["bleu"])
        self.assertTrue(mesures.juger(m))

    def test_un_ecran_noir_est_signale(self):
        m = self.base(couleurs=Counter(), voulues=[])
        self.assertIn("aucun pixel", mesures.juger(m)[0])


class TestCouleursDuPlan(unittest.TestCase):
    def test_la_couleur_annoncee_par_le_plan_est_lue(self):
        sb = Storyboard.from_dict(board())
        # Le plateau des tests annonce du jaune pour l'energie.
        self.assertIn("orange", mesures.couleurs_du_plan(sb, sb.shots[0]))

    def test_vertical_ne_reclame_pas_du_vert(self):
        """« vert » vit dans « vertical » : le premier jet a réclamé du vert
        à cinq plans sur cinq pour cette seule raison."""
        sb = Storyboard.from_dict(board())
        shot = sb.shots[0]
        shot.image_prompt = "A vertical frame of the battery pack. " + prompts.STYLE_DIRECTIVE
        self.assertNotIn("vert", mesures.couleurs_du_plan(sb, shot))

    def test_la_direction_artistique_du_plateau_est_coupee(self):
        """Une direction qui nomme une couleur ne doit pas la faire réclamer
        à chaque plan : elle est commune, elle n'est pas le plan."""
        brut = board()
        brut["style_directive"] = ("Green-tinted cinematic look, deep shadows, "
                                   "vertical 9:16, no text.")
        brut["shots"][0]["image_prompt"] = (
            "A battery pack with yellow energy streams. "
            + brut["style_directive"])
        sb = Storyboard.from_dict(brut)
        self.assertNotIn("vert", mesures.couleurs_du_plan(sb, sb.shots[0]))


if __name__ == "__main__":
    unittest.main()
