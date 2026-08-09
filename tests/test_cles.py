"""`pdz cles` — les vérificateurs, sans réseau.

Chaque fonction `verifier_*` reçoit une réponse HTTP construite à la main et
doit en tirer le bon verdict. C'est ce qui a cassé en silence sur fal.ai :
l'ancien endpoint renvoyait 405 (mauvaise méthode) et le code le lisait comme
une simple panne, sans jamais dire que le contrôle lui-même était mal écrit.
"""

from __future__ import annotations

import httpx
import pytest

from pdz.cles import GABARITS, SERVICES, _renseignee, verifier_fal


def _reponse(code: int, json: dict | None = None) -> httpx.Response:
    return httpx.Response(
        code, json=json or {},
        request=httpx.Request("GET", "https://api.fal.ai/v1/account/billing"),
    )


# ── fal.ai ───────────────────────────────────────────────────────────────

def test_le_solde_est_lu_et_affiche(monkeypatch):
    monkeypatch.setattr(
        "httpx.get",
        lambda *a, **k: _reponse(200, {"credits": {"current_balance": 12.5,
                                                    "currency": "USD"}}),
    )
    ok, detail = verifier_fal("cle")
    assert ok
    assert "12.5" in detail and "USD" in detail


def test_succes_sans_champ_credits_ne_casse_pas(monkeypatch):
    """La forme exacte de la réponse peut varier ; l'absence du solde ne doit
    pas faire échouer une clé qui fonctionne."""
    monkeypatch.setattr("httpx.get", lambda *a, **k: _reponse(200, {}))
    ok, detail = verifier_fal("cle")
    assert ok


def test_401_est_une_cle_refusee(monkeypatch):
    monkeypatch.setattr("httpx.get", lambda *a, **k: _reponse(401))
    ok, detail = verifier_fal("cle")
    assert not ok and "refusée" in detail


def test_403_nest_pas_annonce_comme_une_cle_cassee(monkeypatch):
    """La doc fal.ai réserve cet endpoint aux clés Admin : la plupart des
    clés créées depuis le tableau de bord reçoivent 403 ici tout en
    fonctionnant très bien pour générer des images. Mesuré en conditions
    réelles : annoncer « échec » ici a fait échouer `pdz cles` pour un
    utilisateur dont la clé marchait — d'où `ok=True` malgré le refus."""
    monkeypatch.setattr("httpx.get", lambda *a, **k: _reponse(403))
    ok, detail = verifier_fal("cle")
    assert ok
    assert "Admin" in detail


def test_une_panne_est_rapportee_avec_son_code(monkeypatch):
    monkeypatch.setattr("httpx.get", lambda *a, **k: _reponse(500))
    ok, detail = verifier_fal("cle")
    assert not ok and "500" in detail


def test_lendpoint_nest_plus_lancien_qui_renvoyait_405(monkeypatch):
    """Non-régression : l'ancien endpoint (`rest.alpha.fal.ai/tokens/`)
    n'acceptait pas GET et faisait échouer toute clé valide."""
    appelee = {}

    def _faux_get(url, **k):
        appelee["url"] = url
        return _reponse(200)

    monkeypatch.setattr("httpx.get", _faux_get)
    verifier_fal("cle")
    assert "rest.alpha.fal.ai" not in appelee["url"]
    assert appelee["url"] == "https://api.fal.ai/v1/account/billing"


# ── Reconnaissance des gabarits non renseignés ────────────────────────────

@pytest.mark.parametrize("brut", [
    "", "  ", "sk-ant-...", "your_key_here", "XXX", "changeme", '"sk_..."',
])
def test_une_valeur_de_gabarit_nest_pas_une_cle(brut):
    assert not _renseignee(brut)


def test_une_vraie_cle_est_reconnue():
    assert _renseignee("sk-ant-api03-abcdef1234567890")


def test_gabarits_couvre_les_formats_des_quatre_services():
    for prefixe in ("sk-ant-...", "sk_...", "..."):
        assert prefixe in GABARITS


# ── Ce qui est réellement indispensable ──────────────────────────────────

def test_anthropic_nest_plus_obligatoire():
    """Le profil `gratuit` (Groq) écrit sans elle : l'absence d'Anthropic ne
    doit plus faire échouer `pdz cles` à elle seule."""
    obligatoire = {nom: o for nom, _, _, _, o in SERVICES}
    assert obligatoire["Anthropic"] is False


def test_fal_nest_plus_obligatoire():
    """Le profil « gratuit » illustre avec Pollinations (aucune clé) : fal.ai
    manquant ne doit plus faire échouer `pdz cles` à lui seul."""
    obligatoire = {nom: o for nom, _, _, _, o in SERVICES}
    assert obligatoire["fal.ai"] is False


def test_elevenlabs_reste_obligatoire():
    """Aucune alternative gratuite n'existe pour la voix."""
    obligatoire = {nom: o for nom, _, _, _, o in SERVICES}
    assert obligatoire["ElevenLabs"] is True
