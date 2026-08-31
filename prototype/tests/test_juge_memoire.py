"""Le juge aveugle et la memoire, sans reseau ni fichier du projet."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import config, juge, memoire, prompts  # noqa: E402
from app.models import Storyboard  # noqa: E402
from fixtures import board  # noqa: E402


class TestEtatDuPlan(unittest.TestCase):
    def test_les_trois_etats(self):
        self.assertEqual(juge.etat(0.9), "compris")
        self.assertEqual(juge.etat(juge.COMPRIS), "compris")
        self.assertEqual(juge.etat(0.5), "à retoucher")
        self.assertEqual(juge.etat(0.2), "à refaire")


class TestIntention(unittest.TestCase):
    def setUp(self):
        self.shot = Storyboard.from_dict(board()).shots[0]

    def test_l_alignement_dit_ce_qu_il_fallait_comprendre(self):
        intention = juge.intention_du_plan(
            self.shot, {"understanding": "que l'énergie fait tourner le rotor"})
        self.assertEqual(intention, "que l'énergie fait tourner le rotor")

    def test_sans_alignement_la_fonction_pedagogique_sert(self):
        self.assertEqual(juge.intention_du_plan(self.shot, None),
                         self.shot.educational_function)
        self.assertEqual(juge.intention_du_plan(self.shot, {"understanding": " "}),
                         self.shot.educational_function)


class TestLeRegardEstAveugle(unittest.TestCase):
    """Ce qui est donne a regarder ne doit rien reveler."""

    def test_le_prompt_du_regard_ne_dit_ni_la_voix_ni_le_sujet(self):
        texte = " ".join((prompts.BLIND_USER + prompts.BLIND_SYSTEM).split())
        for interdit in ("narration", "subject", "voice"):
            self.assertNotIn(f"THE {interdit.upper()}", texte)
        self.assertIn("You do not know what the video is about", texte)
        self.assertIn("nothing readable", texte)

    def test_le_verdict_lui_connait_l_intention(self):
        texte = prompts.verdict_user("faire comprendre X", "la voix dit Y", "il a vu Z")
        self.assertIn("faire comprendre X", texte)
        self.assertIn("il a vu Z", texte)


class TestMemoire(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        garde = config.OUTPUT_DIR
        config.OUTPUT_DIR = Path(self._tmp.name)
        self.addCleanup(lambda: setattr(config, "OUTPUT_DIR", garde))

    def souvenir(self, **over):
        base = dict(subject="voiture électrique",
                    voice="Le courant quitte la batterie et rejoint le moteur.",
                    educational_function="montrer le départ de l'énergie",
                    understanding="que l'énergie part de la batterie",
                    chosen="the stream reaches the windings and the rotor turns",
                    mute_test=0.9, understood=0.9)
        base.update(over)
        return memoire.Souvenir(**base)

    def test_rien_a_retenir_au_depart(self):
        self.assertEqual(memoire.charger(), [])
        self.assertEqual(memoire.exemples("une phrase", "une fonction"), [])
        self.assertEqual(memoire.bloc([]), "")

    def test_un_plan_compris_est_retenu(self):
        memoire.retenir([self.souvenir()])
        self.assertEqual(len(memoire.charger()), 1)

    def test_un_plan_mal_compris_n_apprend_rien_a_personne(self):
        memoire.retenir([self.souvenir(understood=0.3)])
        self.assertEqual(memoire.charger(), [])

    def test_le_meme_plan_n_entre_pas_deux_fois(self):
        memoire.retenir([self.souvenir()])
        memoire.retenir([self.souvenir()])
        self.assertEqual(len(memoire.charger()), 1)

    def test_un_plan_ne_se_recopie_pas_lui_meme(self):
        memoire.retenir([self.souvenir()])
        proches = memoire.exemples(
            "Le courant quitte la batterie et rejoint le moteur.",
            "montrer le départ de l'énergie", sujet_courant="voiture électrique")
        self.assertEqual(proches, [])

    def test_un_plan_apprend_d_une_autre_video(self):
        memoire.retenir([self.souvenir()])
        proches = memoire.exemples(
            "Le courant quitte la batterie et rejoint le moteur.",
            "montrer le départ de l'énergie", sujet_courant="capteur de mouvement")
        self.assertEqual(len(proches), 1)
        self.assertIn("rotor turns", memoire.bloc(proches))

    def test_une_phrase_sans_rapport_ne_ramene_rien(self):
        memoire.retenir([self.souvenir()])
        self.assertEqual(memoire.exemples("zzz qqq", "www", "autre sujet"), [])

    def test_les_mieux_compris_passent_devant(self):
        memoire.retenir([
            self.souvenir(voice="Le courant quitte la batterie.", understood=0.75,
                          chosen="piste faible"),
            self.souvenir(voice="Le courant quitte la batterie et va au moteur.",
                          understood=0.98, chosen="piste forte"),
        ])
        proches = memoire.exemples("Le courant quitte la batterie et va au moteur.",
                                   "montrer le départ", "capteur")
        self.assertEqual(proches[0].chosen, "piste forte")

    def test_un_fichier_illisible_ne_fait_pas_tomber_le_systeme(self):
        chemin = memoire.fichier()
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text("{pas du json", encoding="utf-8")
        self.assertEqual(memoire.charger(), [])

    def test_une_entree_incomplete_est_ignoree(self):
        chemin = memoire.fichier()
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(json.dumps([{"subject": "x"}]), encoding="utf-8")
        self.assertEqual(memoire.charger(), [])

    def test_la_moisson_ne_garde_que_les_plans_juges(self):
        sb = Storyboard.from_dict(board())
        alignements = {1: {"understanding": "u", "chosen": "c", "mute_test": 0.9}}
        verdicts = {1: {"understood": 0.9}}
        recolte = memoire.moisson(sb.subject, sb.shots, alignements, verdicts)
        self.assertEqual(len(recolte), 1)
        self.assertEqual(recolte[0].voice, sb.shots[0].voice)


class TestFichesPerimees(unittest.TestCase):
    """Run 40 : quatre plans sur six portaient l'alignement du sujet precedent."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        garde = (config.OUTPUT_DIR, config.SHOTS_DIR)
        racine = Path(self._tmp.name)
        config.OUTPUT_DIR = racine
        config.SHOTS_DIR = racine / "shots"
        self.addCleanup(
            lambda: (setattr(config, "OUTPUT_DIR", garde[0]),
                     setattr(config, "SHOTS_DIR", garde[1])))

    def poser(self, shot_id, voice):
        dossier = config.shot_dir(shot_id)
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / "alignment.json").write_text(
            json.dumps({"voice": voice, "understanding": "u", "chosen": "c"}),
            encoding="utf-8")

    def test_une_fiche_qui_parle_du_bon_plan_est_lue(self):
        from app.main import lire_alignement

        self.poser(1, "Le courant quitte la batterie.")
        fiche = lire_alignement(1, "Le courant quitte la batterie.")
        self.assertEqual(fiche["understanding"], "u")

    def test_une_fiche_d_un_autre_sujet_est_ignoree(self):
        from app.main import lire_alignement

        self.poser(1, "Les capteurs détectent votre présence.")
        self.assertIsNone(lire_alignement(1, "L'électricité arrive dans nos maisons."))

    def test_une_fiche_sans_phrase_reste_lisible(self):
        """Les fiches ecrites avant ce garde-fou n'ont pas de phrase."""
        from app.main import lire_alignement

        dossier = config.shot_dir(1)
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / "alignment.json").write_text(
            json.dumps({"understanding": "u"}), encoding="utf-8")
        self.assertEqual(lire_alignement(1, "une phrase")["understanding"], "u")

    def test_un_nouveau_storyboard_ne_garde_rien_de_l_ancien(self):
        self.poser(5, "un plan d'un run plus long")
        self.assertTrue(config.shot_dir(5).is_dir())
        config.reset_shots()
        self.assertFalse(config.SHOTS_DIR.exists())
        config.ensure_dirs(3)
        self.assertTrue(config.shot_dir(3).is_dir())
        self.assertFalse(config.shot_dir(5).exists())


class TestFicheIdentite(unittest.TestCase):
    def test_le_plan_le_plus_large_verrouille_l_objet(self):
        from app.main import plan_maitre

        raw = board()
        raw["shots"][2]["image_prompt"] = raw["shots"][2]["image_prompt"].replace(
            "Macro shot of", "Wide establishing view of the entire")
        sb = Storyboard.from_dict(raw)
        self.assertEqual(plan_maitre(sb).id, 3)

    def test_la_fiche_derive_les_autres_plans(self):
        sb = Storyboard.from_dict(board())
        fiche = prompts.fiche_identite(sb, sb.shots[0])
        self.assertIn("L'image maitresse", fiche)
        self.assertIn(sb.shots[0].image_prompt, fiche)
        for s in sb.shots[1:]:
            self.assertIn(f"Plan {s.id:02d}", fiche)
        self.assertIn("Same object as the reference image", fiche)


if __name__ == "__main__":
    unittest.main()
