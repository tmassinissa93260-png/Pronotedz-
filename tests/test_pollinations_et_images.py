"""Pollinations.ai (images gratuites, sans clé) et le dispatcheur d'images.

Même principe que tests/test_groq_et_texte.py côté texte : l'appel réseau
réel n'est pas exécutable ici (image.pollinations.ai est bloqué par la
politique réseau de cet environnement), mais tout ce qui ne dépend pas du
réseau — classement des erreurs, écriture du fichier, choix du fournisseur —
est testé sans réseau.
"""

from __future__ import annotations

import httpx
import pytest

from pdz.ia import images as ia_images
from pdz.ia.pollinations import _lever, generer_image
from pdz.moteur.erreurs import (
    ErreurConfig,
    ErreurFournisseur,
    ErreurQuota,
    ErreurValidation,
)


def _reponse(code: int) -> httpx.Response:
    return httpx.Response(
        code, request=httpx.Request("GET", "https://image.pollinations.ai/prompt/x"),
    )


# ── Classement des erreurs ───────────────────────────────────────────────

@pytest.mark.parametrize("code,attendu", [
    (429, ErreurQuota),
    (500, ErreurFournisseur),
    (503, ErreurFournisseur),
    (422, ErreurValidation),
])
def test_chaque_code_http_donne_la_bonne_categorie(code, attendu):
    with pytest.raises(attendu):
        _lever(_reponse(code))


def test_une_reponse_valide_ne_leve_rien():
    _lever(_reponse(200))


# ── Génération ────────────────────────────────────────────────────────────

class _FauxFlux:
    """Un contexte `httpx.stream(...)` factice : status + octets à écrire."""

    def __init__(self, code: int, octets: bytes):
        self.status_code = code
        self._octets = octets

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def iter_bytes(self, taille):
        yield self._octets


def test_une_image_recue_est_ecrite_sur_le_disque(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "httpx.stream", lambda *a, **k: _FauxFlux(200, b"x" * 2000),
    )
    destination = tmp_path / "plan_001.jpg"
    chemin, cout = generer_image("un chat", destination, profil="gratuit")
    assert chemin == destination
    assert destination.read_bytes() == b"x" * 2000
    assert cout == 0.0


def test_une_reponse_trop_petite_nest_pas_une_image(monkeypatch, tmp_path):
    """Une image réelle pèse au minimum quelques kilo-octets : un corps de
    quelques octets est une erreur déguisée en succès (page HTML, message
    vide), pas une image utilisable."""
    monkeypatch.setattr("httpx.stream", lambda *a, **k: _FauxFlux(200, b"x"))
    with pytest.raises(ErreurValidation, match="aucune image"):
        generer_image("un chat", tmp_path / "p.jpg", profil="gratuit")


def test_le_filtre_de_contenu_est_toujours_active(monkeypatch, tmp_path):
    """Mesuré en conditions réelles : un prompt de personnage cartoon
    (« fraise 3D, bras et jambes de cartoon ») a produit une image d'humain
    dénudé. Sans `safe=true`, rien n'empêche ça de se reproduire — et
    `enhance=false` empêche Pollinations de réécrire le prompt à sa façon
    avant de le respecter ou non."""
    appels = {}

    def _faux_stream(methode, url, params=None, **k):
        appels["params"] = params
        return _FauxFlux(200, b"x" * 2000)

    monkeypatch.setattr("httpx.stream", _faux_stream)
    generer_image("une fraise cartoon", tmp_path / "p.jpg", profil="gratuit")
    assert appels["params"]["safe"] == "true"
    assert appels["params"]["enhance"] == "false"


# ── Le dispatcheur (pdz.ia.images) ───────────────────────────────────────

def test_le_profil_par_defaut_illustre_avec_fal():
    assert ia_images.ADAPTATEURS.get(
        _fournisseur_resolu("images", "equilibre")
    ) is ia_images.fal.generer_image


def test_le_profil_gratuit_illustre_avec_pollinations():
    assert ia_images.ADAPTATEURS.get(
        _fournisseur_resolu("images", "gratuit")
    ) is ia_images.pollinations.generer_image


def test_le_profil_hybride_ecrit_gratuit_et_illustre_avec_fal():
    """Écriture Groq (gratuite) + images fal.ai (payantes) : pour qui a du
    crédit fal.ai mais pas encore de crédit Anthropic."""
    reg = ia_images.registre()
    assert reg.resoudre("qualite", profil="hybride").modele.fournisseur == "groq"
    assert _fournisseur_resolu("images", "hybride") == "fal"


def test_un_fournisseur_dimage_inconnu_est_signale(monkeypatch):
    monkeypatch.setattr(ia_images, "ADAPTATEURS", {})
    with pytest.raises(ErreurConfig, match="modeles.yaml"):
        ia_images.generer_image("prompt", "dest", profil="gratuit")


def _fournisseur_resolu(alias: str, profil: str) -> str:
    return ia_images.registre().resoudre(alias, profil=profil).modele.fournisseur
