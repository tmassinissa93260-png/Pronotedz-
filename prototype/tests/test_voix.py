"""La voix de reperage. espeak-ng est optionnel : ce qui se teste sans lui l'est."""

import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import voix  # noqa: E402
from app.models import Storyboard  # noqa: E402
from fixtures import board  # noqa: E402


class TestCaler(unittest.TestCase):
    """« La voix est la reference temporelle » : enfin pour de vrai."""

    def setUp(self):
        self.sb = Storyboard.from_dict(board())

    def test_les_durees_viennent_de_la_voix(self):
        voix.caler(self.sb, {1: 5.0, 2: 3.0, 3: 4.0, 4: 2.0})
        self.assertEqual([s.duration_seconds for s in self.sb.shots], [5.0, 3.0, 4.0, 2.0])
        self.assertEqual(self.sb.duration_seconds, 14.0)

    def test_un_plan_non_mesure_garde_sa_duree(self):
        avant = self.sb.shots[3].duration_seconds
        voix.caler(self.sb, {1: 5.0})
        self.assertEqual(self.sb.shots[3].duration_seconds, avant)

    def test_le_rapport_dit_l_ecart(self):
        texte = voix.rapport(self.sb, {1: 5.0})
        self.assertIn("+2.0s", texte)          # 3.0 prevu, 5.0 dit
        self.assertIn("Total dit", texte)

    def test_le_rapport_ignore_les_plans_non_mesures(self):
        self.assertEqual(voix.rapport(self.sb, {}).count("\n| 0"), 0)


@unittest.skipUnless(shutil.which("espeak-ng") and shutil.which("ffprobe"),
                     "espeak-ng ou ffprobe absent")
class TestDire(unittest.TestCase):
    def test_une_phrase_dite_a_une_duree(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            wav = voix.dire("Ta voiture peut être volée en trente secondes.",
                            Path(tmp) / "t.wav")
            self.assertTrue(wav.is_file())
            self.assertGreater(voix.duree(wav), 1.0)

    def test_une_phrase_longue_dure_plus_longtemps(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            court = voix.duree(voix.dire("Bonjour.", Path(tmp) / "a.wav"))
            long = voix.duree(voix.dire(
                "Un premier complice capte le signal de ta clé à travers ta porte "
                "d'entrée et le retransmet à un second boîtier près du véhicule.",
                Path(tmp) / "b.wav"))
            self.assertGreater(long, court * 3)


class TestEspeakAbsent(unittest.TestCase):
    def test_le_message_dit_comment_l_installer(self):
        import unittest.mock as mock
        with mock.patch("shutil.which", return_value=None):
            with self.assertRaises(voix.VoixError) as ctx:
                voix.exiger_espeak()
        self.assertIn("apt install espeak-ng", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
