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


class TestLesLongs(unittest.TestCase):
    """Separer les fins de phrase des respirations, sans I/O."""

    def test_les_deux_familles_se_separent(self):
        plages = [(0, 0.25), (1, 1.31), (2, 2.7), (3, 3.7), (4, 4.68), (5, 5.66)]
        longs = voix._les_longs(plages, 3)
        self.assertEqual(len(longs), 4)
        self.assertTrue(all(f - d >= 0.6 for d, f in longs))

    def test_une_mediane_aurait_coupe_les_fins_de_phrase(self):
        """Le defaut du premier jet : la mediane tombait AU MILIEU des fins de
        phrase et en jetait la moitie."""
        plages = [(0, 0.25), (1, 1.31), (2, 2.32),
                  *[(i, i + 0.7) for i in range(10, 24)]]
        self.assertEqual(len(voix._les_longs(plages, 14)), 14)

    def test_pas_assez_de_longs_on_garde_tout(self):
        plages = [(0, 0.25), (1, 1.9)]
        self.assertEqual(voix._les_longs(plages, 5), [])

    def test_une_seule_plage_ne_se_separe_pas(self):
        self.assertEqual(voix._les_longs([(0, 1.0)], 1), [])


class TestATeColler(unittest.TestCase):
    def test_une_ligne_vide_entre_les_phrases(self):
        sb = Storyboard.from_dict(board())
        texte = voix.a_coller(sb)
        self.assertEqual(texte.count("\n\n"), len(sb.shots) - 1)
        for s in sb.shots:
            self.assertIn(s.voice, texte)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "ffmpeg absent")
class TestCalerSurUnePiste(unittest.TestCase):
    """Retrouver les phrases dans une piste, par ses silences."""

    def piste(self, tmp, morceaux, silence=0.7):
        """Des sons de durees connues, separes par des silences."""
        import subprocess
        bouts = []
        for i, duree in enumerate(morceaux):
            son = Path(tmp) / f"s{i}.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                            f"sine=frequency=440:duration={duree}", str(son)],
                           check=True, capture_output=True)
            bouts.append(son)
            if i < len(morceaux) - 1:
                blanc = Path(tmp) / f"b{i}.wav"
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                                "anullsrc=r=44100:cl=mono", "-t", str(silence),
                                str(blanc)], check=True, capture_output=True)
                bouts.append(blanc)
        liste = Path(tmp) / "l.txt"
        liste.write_text("".join(f"file '{b.resolve()}'\n" for b in bouts))
        sortie = Path(tmp) / "piste.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
                        "-i", str(liste), str(sortie)], check=True, capture_output=True)
        return sortie

    def test_trois_phrases_retrouvees(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            piste = self.piste(tmp, [2.0, 4.0, 3.0])
            morceaux = voix.decouper(piste, [2.0, 4.0, 3.0])
            self.assertEqual(len(morceaux), 3)
            for trouve, attendu in zip(morceaux, [2.35, 4.7, 3.35], strict=True):
                self.assertAlmostEqual(trouve, attendu, delta=0.5)

    def test_le_silence_de_fin_ne_coupe_rien(self):
        """Il finit la piste : il n'a pas de parole apres lui."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            piste = self.piste(tmp, [3.0, 3.0])
            self.assertEqual(len(voix.decouper(piste, [1.0, 1.0])), 2)

    def test_une_piste_sans_silence_le_dit(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            piste = self.piste(tmp, [4.0])
            with self.assertRaises(voix.VoixError) as ctx:
                voix.decouper(piste, [1.0, 1.0, 1.0])
            self.assertIn("silence", str(ctx.exception))

    def test_un_seul_plan_prend_toute_la_piste(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            piste = self.piste(tmp, [2.0, 2.0])
            self.assertEqual(len(voix.decouper(piste, [1.0])), 1)


class TestEspeakAbsent(unittest.TestCase):
    def test_le_message_dit_comment_l_installer(self):
        import unittest.mock as mock
        with mock.patch("shutil.which", return_value=None):
            with self.assertRaises(voix.VoixError) as ctx:
                voix.exiger_espeak()
        self.assertIn("apt install espeak-ng", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
