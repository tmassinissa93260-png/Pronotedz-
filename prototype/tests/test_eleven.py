"""ElevenLabs, sans jamais sortir de la machine.

Chaque appel passe par une fonction d'ouverture injectee : les tests rendent
ce qu'ils veulent, et aucune requete ne part.
"""

import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import config, eleven  # noqa: E402


class Reponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def repondre(donnees: bytes):
    """Une ouverture qui rend toujours la meme reponse, et note la requete."""
    vues = []

    def ouvrir(requete, timeout=None):
        vues.append(requete)
        return Reponse(donnees)

    ouvrir.vues = vues
    return ouvrir


def refuser(code: int, corps: bytes = b"non"):
    def ouvrir(requete, timeout=None):
        raise urllib.error.HTTPError(requete.full_url, code, "erreur", {},
                                     io.BytesIO(corps))
    return ouvrir


class TestCle(unittest.TestCase):
    def setUp(self):
        self.ancienne = config.ELEVENLABS_API_KEY
        config.ELEVENLABS_API_KEY = "cle-de-test"

    def tearDown(self):
        config.ELEVENLABS_API_KEY = self.ancienne

    def test_sans_cle_il_refuse_avant_tout_appel(self):
        config.ELEVENLABS_API_KEY = ""
        with self.assertRaises(eleven.ElevenError) as ctx:
            eleven.voix_disponibles(repondre(b"{}"))
        self.assertIn("ELEVENLABS_API_KEY", str(ctx.exception))
        self.assertIn("jamais dans le code", str(ctx.exception))

    def test_la_cle_part_dans_l_entete_pas_dans_l_url(self):
        ouvrir = repondre(json.dumps({"voices": []}).encode())
        eleven.voix_disponibles(ouvrir)
        requete = ouvrir.vues[0]
        self.assertEqual(requete.get_header("Xi-api-key"), "cle-de-test")
        self.assertNotIn("cle-de-test", requete.full_url)

    def test_les_voix_du_compte_sont_lues(self):
        brut = {"voices": [{"voice_id": "abc", "name": "Léa", "labels": {"a": "b"}},
                           {"name": "sans identifiant"}]}
        voix = eleven.voix_disponibles(repondre(json.dumps(brut).encode()))
        self.assertEqual([v["voice_id"] for v in voix], ["abc"])

    def test_la_voix_configuree_gagne(self):
        ancienne = config.ELEVENLABS_VOICE_ID
        config.ELEVENLABS_VOICE_ID = "choisie"
        try:
            self.assertEqual(eleven.choisir_voix(repondre(b"{}")), "choisie")
        finally:
            config.ELEVENLABS_VOICE_ID = ancienne

    def test_sans_voix_configuree_on_prend_la_premiere(self):
        brut = {"voices": [{"voice_id": "premiere", "name": "A"},
                           {"voice_id": "seconde", "name": "B"}]}
        self.assertEqual(eleven.choisir_voix(repondre(json.dumps(brut).encode())),
                         "premiere")

    def test_un_compte_sans_voix_le_dit(self):
        with self.assertRaises(eleven.ElevenError) as ctx:
            eleven.choisir_voix(repondre(json.dumps({"voices": []}).encode()))
        self.assertIn("aucune voix", str(ctx.exception))


class TestDire(unittest.TestCase):
    def setUp(self):
        self.ancienne = config.ELEVENLABS_API_KEY
        config.ELEVENLABS_API_KEY = "cle-de-test"

    def tearDown(self):
        config.ELEVENLABS_API_KEY = self.ancienne

    def test_le_mp3_est_ecrit_tel_quel(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            mp3 = Path(tmp) / "a.mp3"
            eleven.dire("Bonjour.", mp3, "voix-1", ouvrir=repondre(b"\xff\xfbdes octets"))
            self.assertEqual(mp3.read_bytes(), b"\xff\xfbdes octets")

    def test_la_phrase_et_le_modele_partent_dans_le_corps(self):
        import tempfile
        ouvrir = repondre(b"son")
        with tempfile.TemporaryDirectory() as tmp:
            eleven.dire("Ta voiture peut être volée.", Path(tmp) / "a.mp3",
                        "voix-1", ouvrir=ouvrir)
        corps = json.loads(ouvrir.vues[0].data)
        self.assertEqual(corps["text"], "Ta voiture peut être volée.")
        self.assertEqual(corps["model_id"], config.ELEVENLABS_MODEL)
        self.assertIn("voix-1", ouvrir.vues[0].full_url)

    def test_un_fichier_vide_est_refuse(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(eleven.ElevenError):
                eleven.dire("x", Path(tmp) / "a.mp3", "v", ouvrir=repondre(b""))


class TestErreurs(unittest.TestCase):
    def setUp(self):
        self.ancienne = config.ELEVENLABS_API_KEY
        config.ELEVENLABS_API_KEY = "cle-de-test"

    def tearDown(self):
        config.ELEVENLABS_API_KEY = self.ancienne

    def test_une_cle_refusee_le_dit(self):
        with self.assertRaises(eleven.ElevenError) as ctx:
            eleven.voix_disponibles(refuser(401))
        self.assertIn("clé refusée", str(ctx.exception))

    def test_un_quota_epuise_ne_ressemble_pas_a_une_panne(self):
        with self.assertRaises(eleven.ElevenError) as ctx:
            eleven.voix_disponibles(refuser(429))
        self.assertIn("quota", str(ctx.exception))
        self.assertIn("gratuit", str(ctx.exception))

    def test_une_voix_inconnue_le_dit(self):
        with self.assertRaises(eleven.ElevenError) as ctx:
            eleven.voix_disponibles(refuser(422))
        self.assertIn("voix ou modèle", str(ctx.exception))

    def test_un_service_injoignable_le_dit(self):
        def ouvrir(requete, timeout=None):
            raise urllib.error.URLError("bloqué par la politique réseau")
        with self.assertRaises(eleven.ElevenError) as ctx:
            eleven.voix_disponibles(ouvrir)
        self.assertIn("injoignable", str(ctx.exception))
        self.assertIn("runner GitHub", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
