import json

from django.conf import settings
from django.test import TestCase
from django.urls import reverse


class ManifestTests(TestCase):
    def test_manifest_json_is_valid_and_references_existing_icons(self):
        manifest_path = settings.BASE_DIR / "static" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())

        self.assertEqual(manifest["start_url"], "/")
        self.assertEqual(manifest["display"], "standalone")
        self.assertGreaterEqual(len(manifest["icons"]), 2)
        for icon in manifest["icons"]:
            icon_path = settings.BASE_DIR / icon["src"].lstrip("/")
            self.assertTrue(icon_path.exists(), f"Icône manquante : {icon_path}")


class ServiceWorkerViewTests(TestCase):
    def test_service_worker_is_served_at_root_with_js_content_type(self):
        response = self.client.get(reverse("pwa:service_worker"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/javascript")
        self.assertIn(b"CACHE_VERSION", response.content)

    def test_service_worker_accessible_without_login(self):
        response = self.client.get("/sw.js")
        self.assertEqual(response.status_code, 200)


class OfflinePageTests(TestCase):
    def test_offline_page_renders_without_login(self):
        response = self.client.get(reverse("pwa:offline"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "hors ligne")


class BaseTemplateRegistersServiceWorkerTests(TestCase):
    def test_login_page_links_the_manifest(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, 'rel="manifest"')
