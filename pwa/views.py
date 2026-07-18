from pathlib import Path

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render


def service_worker(request):
    """Serves the service worker from the site root (rather than under
    /static/) so its default scope covers the whole app instead of just
    /static/ — that's what lets it intercept navigation requests."""
    js_path = Path(settings.BASE_DIR) / "static" / "js" / "service_worker.js"
    return HttpResponse(js_path.read_text(), content_type="application/javascript")


def offline(request):
    return render(request, "pwa/offline.html")
