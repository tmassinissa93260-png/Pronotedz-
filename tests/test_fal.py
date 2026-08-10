"""fal.ai — tout ce qui est vérifiable sans réseau.

L'appel HTTP lui-même ne peut pas être exécuté ici (la politique réseau de
l'environnement bloque fal.run). En revanche la lecture des réponses, le
classement des erreurs et le calcul du coût sont testés intégralement : ce
sont eux qui cassent en production, pas le POST.
"""

import httpx
import pytest

from pdz.ia.fal import _data_uri, _lever, base_file, url_video
from pdz.ia.registre import registre
from pdz.moteur.erreurs import (
    ErreurFournisseur,
    ErreurQuota,
    ErreurRefus,
    ErreurValidation,
)


def _reponse(code: int, texte: str = "") -> httpx.Response:
    return httpx.Response(code, text=texte,
                          request=httpx.Request("POST", "https://fal.run/x"))


# ── Classement des erreurs ───────────────────────────────────────────────
# La catégorie décide du réessai : se tromper ici, c'est soit s'acharner sur
# une erreur définitive, soit abandonner une panne passagère.

@pytest.mark.parametrize("code,attendu", [
    (401, ErreurRefus),         # clé invalide → inutile de réessayer
    (403, ErreurRefus),
    (402, ErreurRefus),         # plus de crédit → inutile aussi
    (429, ErreurQuota),         # débit → attendre puis réessayer
    (500, ErreurFournisseur),   # panne → repli
    (503, ErreurFournisseur),
    (422, ErreurValidation),    # requête mal formée → réparer et relancer
])
def test_chaque_code_http_donne_la_bonne_categorie(code, attendu):
    with pytest.raises(attendu):
        _lever(_reponse(code, "détail"), "test")


def test_le_manque_de_credit_est_explicite():
    with pytest.raises(ErreurRefus, match="Billing"):
        _lever(_reponse(402), "image")


def test_une_reponse_valide_ne_leve_rien():
    _lever(_reponse(200), "image")


# ── Lecture des réponses ─────────────────────────────────────────────────
# La forme varie d'un modèle à l'autre : c'est exactement le genre de
# détail qui casse silencieusement quand on change de modèle dans le YAML.

@pytest.mark.parametrize("charge", [
    {"video": {"url": "https://x/v.mp4"}},
    {"video": "https://x/v.mp4"},
    {"videos": [{"url": "https://x/v.mp4"}]},
])
def test_toutes_les_formes_de_reponse_video_sont_lues(charge):
    assert url_video(charge) == "https://x/v.mp4"


def test_une_reponse_video_vide_est_signalee():
    with pytest.raises(ErreurValidation, match="Aucune vidéo"):
        url_video({"detail": "rien"})


# ── URL de suivi de file ─────────────────────────────────────────────────
# fal.ai documente que le sous-chemin d'un modèle sert à SOUMETTRE mais pas
# à suivre : `fal-ai/flux/dev` se suit sur `fal-ai/flux`. Se tromper ici
# donnait un 404 à chaque interrogation — et comme une animation ratée est
# rattrapée en image fixe, l'épisode sortait sans animation ni erreur.

@pytest.mark.parametrize("modele_id,attendu", [
    ("fal-ai/flux/dev", "https://queue.fal.run/fal-ai/flux"),
    ("fal-ai/kling-video/v2.1/standard/image-to-video",
     "https://queue.fal.run/fal-ai/kling-video"),
    ("fal-ai/ltx-video-v097/image-to-video",
     "https://queue.fal.run/fal-ai/ltx-video-v097"),
    # Un identifiant déjà court reste inchangé.
    ("fal-ai/flux-general", "https://queue.fal.run/fal-ai/flux-general"),
])
def test_lurl_de_file_ignore_le_sous_chemin(modele_id, attendu):
    assert base_file(modele_id) == attendu


def test_les_url_renvoyees_par_fal_ont_la_priorite(monkeypatch):
    """fal.ai renvoie `status_url` et `response_url` à la soumission : les
    suivre vaut mieux que les reconstruire, elles restent justes même si
    leur forme change."""
    from pdz.ia import fal

    vues = []

    def _faux_get(url, **k):
        vues.append(url)
        charge = ({"status": "COMPLETED"} if url.endswith("/status")
                  else {"video": {"url": "https://x/v.mp4"}})
        return httpx.Response(200, json=charge,
                              request=httpx.Request("GET", url))

    monkeypatch.setattr("httpx.get", _faux_get)
    monkeypatch.setattr(fal, "_entetes", lambda: {})
    monkeypatch.setattr(fal.time, "sleep", lambda _: None)

    url = fal._attendre(
        "fal-ai/kling-video/v2.1/standard/image-to-video", "req1", 60,
        url_statut="https://queue.fal.run/donne/par/fal/status",
        url_resultat="https://queue.fal.run/donne/par/fal",
    )
    assert url == "https://x/v.mp4"
    assert vues[0] == "https://queue.fal.run/donne/par/fal/status"


def test_sans_url_donnee_le_suivi_retombe_sur_lurl_reconstruite(monkeypatch):
    from pdz.ia import fal

    vues = []

    def _faux_get(url, **k):
        vues.append(url)
        charge = ({"status": "COMPLETED"} if url.endswith("/status")
                  else {"video": {"url": "https://x/v.mp4"}})
        return httpx.Response(200, json=charge,
                              request=httpx.Request("GET", url))

    monkeypatch.setattr("httpx.get", _faux_get)
    monkeypatch.setattr(fal, "_entetes", lambda: {})
    monkeypatch.setattr(fal.time, "sleep", lambda _: None)

    fal._attendre("fal-ai/kling-video/v2.1/standard/image-to-video", "req1", 60)
    assert vues[0] == (
        "https://queue.fal.run/fal-ai/kling-video/requests/req1/status"
    )


def test_lurl_de_file_du_modele_danimation_reellement_utilise():
    """Non-régression sur le modèle exact de modeles.yaml : c'est celui-ci
    qui a produit des épisodes sans animation."""
    modele = registre().resoudre("animation").modele
    base = base_file(modele.id)
    assert base.count("/") == 4, f"sous-chemin non retiré : {base}"
    assert "standard" not in base


def test_lendpoint_danimation_mort_nest_plus_reference():
    """`v2/standard/image-to-video` n'a jamais été publié par fal.ai : la
    soumission partait en 404 et l'épisode sortait en images fixes, sans
    erreur visible. Versions réelles : v1, v2.1, v2.6."""
    mort = "fal-ai/kling-video/v2/standard/image-to-video"
    assert mort not in registre().modeles
    assert registre().resoudre("animation").modele.id != mort


# ── Image de référence ───────────────────────────────────────────────────

def test_limage_de_reference_est_encodee(tmp_path):
    """C'est ce qui garantit la constance des personnages d'un plan à l'autre."""
    from PIL import Image
    p = tmp_path / "fiche.jpg"
    Image.new("RGB", (64, 64), (200, 60, 80)).save(p)

    uri = _data_uri(p)
    assert uri.startswith("data:image/jpeg;base64,")
    assert len(uri) > 200


# ── Coût ─────────────────────────────────────────────────────────────────

def test_le_cout_de_lanimation_suit_la_duree():
    """L'animation est le poste le plus cher : le calcul doit être juste."""
    m = registre().modeles["fal-ai/kling-video/v2.1/standard/image-to-video"]
    assert m.cout_unites(5, "seconde") == pytest.approx(m.prix.par_seconde * 5)
    # Un clip de 5 s doit coûter nettement plus qu'une image.
    img = registre().modeles["fal-ai/flux/schnell"]
    assert m.cout_unites(5, "seconde") > img.cout_unites(1, "image") * 50


def test_le_profil_premium_prend_le_modele_dimage_plus_fin():
    eco = registre().resoudre("images", profil="economique").modele
    prem = registre().resoudre("images", profil="premium").modele
    assert prem.prix.par_image > eco.prix.par_image
