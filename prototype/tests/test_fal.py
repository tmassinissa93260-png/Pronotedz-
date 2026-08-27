"""Tests du client fal.ai, sans jamais appeler fal.ai.

httpx.MockTransport joue le role du service : on verifie la charge utile
reellement envoyee, la lecture de la reponse, le telechargement du fichier
et le comportement sur chaque code d'erreur.

    python -m unittest tests.test_fal
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, fal_client  # noqa: E402
from app.fal_client import FalError  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 4000
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"0" * 9000


class FauxFal:
    """Enregistre les requetes et rend des reponses controlees."""

    def __init__(self, post_json=None, status=200, body=PNG):
        self.requests = []
        self.post_json = post_json or {}
        self.status = status
        self.body = body

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.method == "POST":
            if self.status >= 400:
                return httpx.Response(self.status, text="refuse par le service")
            return httpx.Response(200, json=self.post_json)
        return httpx.Response(200, content=self.body)


class FalCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self._saved_key = config.FAL_KEY
        config.FAL_KEY = "cle-de-test"
        self.addCleanup(lambda: setattr(config, "FAL_KEY", self._saved_key))

    def brancher(self, faux: FauxFal):
        transport = httpx.MockTransport(faux.handler)
        real_client = httpx.Client

        def client(*a, **kw):
            kw["transport"] = transport
            return real_client(*a, **kw)

        patches = [
            mock.patch.object(httpx, "post", self._post_via(transport)),
            mock.patch.object(httpx, "stream", self._stream_via(transport)),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    @staticmethod
    def _post_via(transport):
        def post(url, **kw):
            with httpx.Client(transport=transport) as c:
                return c.post(url, **kw)
        return post

    @staticmethod
    def _stream_via(transport):
        def stream(method, url, **kw):
            kw.pop("timeout", None)
            kw.pop("follow_redirects", None)
            return httpx.Client(transport=transport).stream(method, url, **kw)
        return stream


class TestImage(FalCase):
    def test_charge_utile_et_fichier_rendu(self):
        faux = FauxFal(post_json={"images": [{"url": "https://fal.test/i.png"}]})
        self.brancher(faux)

        dest = fal_client.generate_image("un prompt photo", self.root / "image.png")

        self.assertTrue(dest.is_file())
        self.assertEqual(dest.read_bytes(), PNG)

        post = faux.requests[0]
        self.assertEqual(post.headers["authorization"], "Key cle-de-test")
        self.assertIn(config.FAL_IMAGE_MODEL, str(post.url))
        import json
        charge = json.loads(post.content)
        self.assertEqual(charge["prompt"], "un prompt photo")
        self.assertEqual(charge["image_size"],
                         {"width": config.IMAGE_WIDTH, "height": config.IMAGE_HEIGHT})
        self.assertEqual(charge["num_images"], 1)

    def test_reste_sous_le_megapixel_ou_flux_est_entraine(self):
        """1080x1920 valait 2,07 Mpx : hors du domaine de FLUX, d'ou les
        geometries incoherentes et le texte halluciné observes en production."""
        megapixels = config.IMAGE_WIDTH * config.IMAGE_HEIGHT / 1_000_000
        self.assertLess(megapixels, 1.3)
        self.assertAlmostEqual(config.IMAGE_HEIGHT / config.IMAGE_WIDTH, 16 / 9, places=1)

    def test_guidance_envoyee_a_dev_pas_a_schnell(self):
        import json

        for modele, attendue in (("fal-ai/flux/dev", True),
                                 ("fal-ai/flux/schnell", False)):
            with self.subTest(modele=modele):
                garde = config.FAL_IMAGE_MODEL
                config.FAL_IMAGE_MODEL = modele
                self.addCleanup(lambda g=garde: setattr(config, "FAL_IMAGE_MODEL", g))
                faux = FauxFal(post_json={"images": [{"url": "https://fal.test/i.png"}]})
                self.brancher(faux)
                fal_client.generate_image("x", self.root / f"{modele[-6:]}.png")
                charge = json.loads(faux.requests[0].content)
                self.assertEqual("guidance_scale" in charge, attendue)

    def test_reponse_sans_image(self):
        self.brancher(FauxFal(post_json={"images": []}))
        with self.assertRaises(FalError) as ctx:
            fal_client.generate_image("x", self.root / "a.png")
        self.assertIn("reponse sans image", str(ctx.exception))

    def test_fichier_vide_refuse(self):
        self.brancher(FauxFal(post_json={"images": [{"url": "https://fal.test/i.png"}]},
                              body=b""))
        with self.assertRaises(FalError) as ctx:
            fal_client.generate_image("x", self.root / "a.png")
        self.assertIn("fichier vide", str(ctx.exception))

    def test_codes_d_erreur_traduits(self):
        for code, attendu in ((401, "refusee"), (402, "credit"), (500, "code 500")):
            with self.subTest(code=code):
                self.brancher(FauxFal(status=code))
                with self.assertRaises(FalError) as ctx:
                    fal_client.generate_image("x", self.root / "a.png")
                self.assertIn(attendu, str(ctx.exception))


class TestAnimation(FalCase):
    def test_charge_utile_et_video_rendue(self):
        faux = FauxFal(post_json={"video": {"url": "https://fal.test/v.mp4"}}, body=MP4)
        self.brancher(faux)
        image = self.root / "image.png"
        image.write_bytes(PNG)

        dest = fal_client.animate(image, "prompt d'animation", 4.0, self.root / "video.mp4")

        self.assertEqual(dest.read_bytes(), MP4)
        import json
        charge = json.loads(faux.requests[0].content)
        self.assertTrue(charge["image_url"].startswith("data:image/png;base64,"))
        self.assertEqual(charge["prompt"], "prompt d'animation")
        self.assertEqual(charge["duration"], "5")  # 4s remonte au minimum accepte

    def test_image_absente(self):
        self.brancher(FauxFal())
        with self.assertRaises(FalError) as ctx:
            fal_client.animate(self.root / "absent.png", "p", 4.0, self.root / "v.mp4")
        self.assertIn("image introuvable", str(ctx.exception))

    def test_reponse_sans_video(self):
        self.brancher(FauxFal(post_json={"video": {}}))
        image = self.root / "i.png"
        image.write_bytes(PNG)
        with self.assertRaises(FalError) as ctx:
            fal_client.animate(image, "p", 4.0, self.root / "v.mp4")
        self.assertIn("reponse sans video", str(ctx.exception))


class TestDuree(unittest.TestCase):
    def test_ramenee_a_ce_que_le_modele_accepte(self):
        self.assertEqual(fal_client.clamp_duration(1), 5)
        self.assertEqual(fal_client.clamp_duration(4), 5)
        self.assertEqual(fal_client.clamp_duration(8), 10)
        self.assertEqual(fal_client.clamp_duration(30), 10)


class TestCle(unittest.TestCase):
    def test_message_sans_cle(self):
        saved = config.FAL_KEY
        config.FAL_KEY = ""
        try:
            with self.assertRaises(FalError) as ctx:
                fal_client._key()
            message = str(ctx.exception)
            self.assertIn("FAL_KEY absente", message)
            self.assertIn("Secrets and variables", message)
        finally:
            config.FAL_KEY = saved


if __name__ == "__main__":
    unittest.main()
