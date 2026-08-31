"""Le texte, ecrit seul. Aucun appel reseau."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import redacteur, validator  # noqa: E402
from app.models import Storyboard  # noqa: E402
from app.openai_client import OpenAIError  # noqa: E402
from fixtures import board  # noqa: E402

OUVERTURE = ("Une centrale ne fabrique pas d'électricité : elle la déplace.")

SCRIPT = (
    "Une centrale ne fabrique pas d'électricité : elle la déplace. "
    "La vapeur sous pression frappe les aubes de la turbine et les emporte. "
    "L'arbre de la turbine entraîne un rotor couvert d'aimants. "
    "Ces aimants balaient les bobines de cuivre et arrachent leurs électrons. "
    "Le courant né dans les bobines file vers le transformateur. "
    "Les lignes le portent jusqu'à la prise où tu branches ta lampe."
)


def reponse(**over):
    base = {
        "chain": ["la vapeur pousse les aubes",
                  "l'arbre entraîne le rotor aimanté",
                  "les aimants balaient les bobines",
                  "le courant part vers les lignes"],
        "openings": [
            {"sentence": OUVERTURE, "why_it_holds": "ça contredit ce qu'on croit"},
            {"sentence": "Regarde ta prise : d'où vient ce courant ?",
             "why_it_holds": "ça part d'un objet familier"},
            {"sentence": "Il faut cinq tonnes de vapeur par seconde pour ta lampe.",
             "why_it_holds": "le chiffre surprend"},
        ],
        "chosen_opening": OUVERTURE,
        "why_chosen": "elle démonte une croyance dès la première seconde",
        "script": SCRIPT,
        "objections": [
            {"sentence": p, "objection": "aucune", "fix": "rien à changer"}
            for p in validator.phrases(SCRIPT)
        ],
    }
    base.update(over)
    return base


class TestForme(unittest.TestCase):
    def test_une_reponse_complete_passe(self):
        texte = redacteur._normaliser(reponse())
        self.assertEqual(len(texte["openings"]), 3)
        self.assertEqual(len(texte["chain"]), 4)

    def test_une_seule_ouverture_n_est_pas_un_choix(self):
        with self.assertRaises(OpenAIError) as ctx:
            redacteur._normaliser(reponse(openings=[
                {"sentence": "a", "why_it_holds": "b"}]))
        self.assertIn("ouvertures", str(ctx.exception))

    def test_une_chaine_trop_courte_est_refusee(self):
        with self.assertRaises(OpenAIError) as ctx:
            redacteur._normaliser(reponse(chain=["ça produit du courant"]))
        self.assertIn("chaine", str(ctx.exception))

    def test_un_champ_vide_est_refuse(self):
        for champ in ("script", "chosen_opening", "why_chosen"):
            with self.subTest(champ=champ), self.assertRaises(OpenAIError):
                redacteur._normaliser(reponse(**{champ: "  "}))

    def test_une_objection_incomplete_est_refusee(self):
        with self.assertRaises(OpenAIError) as ctx:
            redacteur._normaliser(reponse(objections=[
                {"sentence": "a", "objection": "b", "fix": ""}]))
        self.assertIn("fix", str(ctx.exception))


class TestControles(unittest.TestCase):
    def verifier(self, **over):
        return redacteur._problemes(redacteur._normaliser(reponse(**over)), 24, 6)

    def test_un_texte_conforme_ne_leve_rien(self):
        self.assertEqual(self.verifier(), [])

    def test_le_nombre_de_phrases_suit_le_nombre_de_plans(self):
        court = " ".join(validator.phrases(SCRIPT)[:3])
        problemes = self.verifier(
            script=court,
            objections=[{"sentence": p, "objection": "aucune", "fix": "rien"}
                        for p in validator.phrases(court)])
        self.assertTrue(any("sentences" in p for p in problemes))

    def test_l_ouverture_choisie_doit_ouvrir_le_script(self):
        problemes = self.verifier(chosen_opening="Une phrase qui n'y est pas.")
        self.assertTrue(any("does not start with the opening" in p for p in problemes))

    def test_chaque_phrase_doit_etre_relue(self):
        problemes = self.verifier(objections=[
            {"sentence": "une seule", "objection": "aucune", "fix": "rien"}])
        self.assertTrue(any("hostile engineer" in p for p in problemes))

    def test_les_controles_du_storyboard_s_appliquent_au_texte(self):
        """Le texte n'est pas juge deux fois selon deux regles."""
        plat = ("L'électricité est essentielle dans notre vie quotidienne. "
                "Elle est produite par des centrales. "
                "Cette énergie est transférée à une turbine. "
                "Ce mouvement permet de générer un champ. "
                "Le courant est ensuite transporté. "
                "Il est enfin distribué chez nous.")
        problemes = self.verifier(
            script=plat,
            objections=[{"sentence": p, "objection": "aucune", "fix": "rien"}
                        for p in validator.phrases(plat)])
        self.assertTrue(any("could open any video" in p for p in problemes))
        self.assertTrue(any("active voice" in p for p in problemes))


class TestPassif(unittest.TestCase):
    """« est ensuite transporté » est passif ; « est très chaude » non."""

    def test_ce_qui_est_passif(self):
        for phrase in ("Le courant est produit par la turbine.",
                       "Il est ensuite transporté par les lignes.",
                       "L'énergie est enfin distribuée aux maisons.",
                       "Le rotor est entraîné par la turbine.",
                       "Les aubes sont poussées par la vapeur."):
            with self.subTest(phrase=phrase):
                self.assertTrue(validator.est_passive(phrase))

    def test_ce_qui_ne_l_est_pas(self):
        for phrase in ("L'électricité est essentielle dans notre vie.",
                       "La vapeur est très chaude.",
                       "L'aimant est un rotor couvert de cuivre.",
                       "La vapeur frappe les aubes et les emporte.",
                       "Le courant file vers le transformateur."):
            with self.subTest(phrase=phrase):
                self.assertFalse(validator.est_passive(phrase))


class TestLesControlesDuTexte(unittest.TestCase):
    """Le validateur regardait dix-huit fois l'image et jamais la narration."""

    def valider(self, script):
        raw = board()
        raw["script"] = script
        return [p for p in validator._texte(Storyboard.from_dict(raw))]

    def test_une_ouverture_qui_definit(self):
        p = self.valider("L'électricité est une forme d'énergie. " + SCRIPT)
        self.assertIn("CROCHET", [x.code for x in p])

    def test_une_ouverture_generale(self):
        p = self.valider("L'électricité est essentielle au quotidien. " + SCRIPT)
        self.assertIn("CROCHET", [x.code for x in p])

    def test_une_ouverture_qui_annonce(self):
        p = self.valider("Dans cette vidéo, on va voir comment ça marche. " + SCRIPT)
        self.assertIn("CROCHET", [x.code for x in p])

    def test_une_vraie_ouverture_passe(self):
        self.assertEqual(self.valider(SCRIPT), [])

    def test_le_passif_partout(self):
        passif = ("Le courant est produit par la turbine. "
                  "Il est ensuite transporté par les lignes. "
                  "La tension est élevée par un transformateur. "
                  "L'énergie est enfin distribuée aux maisons.")
        p = self.valider(passif)
        self.assertIn("PASSIF", [x.code for x in p])

    def test_un_seul_passif_ne_declenche_rien(self):
        p = self.valider(SCRIPT.replace(
            "Les lignes le portent jusqu'à la prise où tu branches ta lampe.",
            "Il est porté jusqu'à ta prise."))
        self.assertNotIn("PASSIF", [x.code for x in p])

    def test_les_mots_qui_ne_montrent_rien(self):
        p = self.valider("La vapeur frappe les aubes et les emporte. "
                         "Cela permet de générer principalement du courant.")
        self.assertIn("VAGUE", [x.code for x in p])

    def test_un_seul_mot_vague_est_tolere(self):
        p = self.valider("La vapeur frappe les aubes et les emporte. "
                         "Cela permet de faire tourner le rotor aimanté.")
        self.assertNotIn("VAGUE", [x.code for x in p])


if __name__ == "__main__":
    unittest.main()
