"""Groq (l'alternative gratuite à Claude) et le dispatcher `pdz.ia.texte`.

Comme pour fal.ai, l'appel réseau lui-même n'est pas testable ici (la
politique réseau bloque api.groq.com). Ce qui est vérifié intégralement :
la forme de la requête, la lecture de la réponse, le classement des erreurs,
et — le point qui compte le plus — que le dispatcher envoie bien chaque
alias résolu vers le bon fournisseur sans qu'aucun agent n'ait à le savoir.
"""

from __future__ import annotations

import json

import httpx
import pytest

from pdz.ia import groq, texte
from pdz.ia.groq import _extraire_outil, _lever_si_erreur
from pdz.moteur.erreurs import (
    ErreurConfig,
    ErreurFournisseur,
    ErreurQuota,
    ErreurRefus,
    ErreurValidation,
)


def _reponse(code: int, json_body: dict | None = None, texte_brut: str = "") -> httpx.Response:
    return httpx.Response(
        code, json=json_body, text=texte_brut if json_body is None else None,
        request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"),
    )


# ── Classement des erreurs ───────────────────────────────────────────────

@pytest.mark.parametrize("code,attendu", [
    (401, ErreurRefus),
    (403, ErreurRefus),
    (429, ErreurQuota),
    (500, ErreurFournisseur),
    (503, ErreurFournisseur),
    (422, ErreurValidation),
])
def test_chaque_code_http_donne_la_bonne_categorie(code, attendu):
    with pytest.raises(attendu):
        _lever_si_erreur(_reponse(code, {"error": {"message": "x"}}))


def test_un_modele_renomme_est_signale_comme_config_a_corriger():
    """Si Groq change le nom du modèle, l'erreur doit dire quoi faire —
    pas ressembler à une clé cassée."""
    with pytest.raises(ErreurConfig) as e:
        _lever_si_erreur(_reponse(404, {"error": {"message": "model not found"}}))
    assert "modeles.yaml" in str(e.value)


def test_un_404_sans_rapport_avec_le_modele_reste_generique():
    with pytest.raises(ErreurValidation):
        _lever_si_erreur(_reponse(404, {"error": {"message": "route inconnue"}}))


def test_une_reponse_valide_ne_leve_rien():
    _lever_si_erreur(_reponse(200))


# ── Lecture de la réponse (format OpenAI, différent d'Anthropic) ─────────

def test_loutil_appele_est_extrait():
    charge = {
        "choices": [{
            "finish_reason": "tool_calls",
            "message": {"tool_calls": [{
                "function": {"name": "reponse",
                            "arguments": json.dumps({"titre": "Le titre"})},
            }]},
        }],
    }
    assert _extraire_outil(charge, "reponse") == {"titre": "Le titre"}


def test_un_appel_dun_autre_outil_nest_pas_pris():
    charge = {"choices": [{"finish_reason": "tool_calls",
                          "message": {"tool_calls": [
                              {"function": {"name": "autre_chose", "arguments": "{}"}},
                          ]}}]}
    with pytest.raises(ErreurValidation):
        _extraire_outil(charge, "reponse")


def test_un_json_darguments_invalide_est_signale():
    charge = {"choices": [{"finish_reason": "tool_calls",
                          "message": {"tool_calls": [
                              {"function": {"name": "reponse", "arguments": "{pas du json"}},
                          ]}}]}
    with pytest.raises(ErreurValidation) as e:
        _extraire_outil(charge, "reponse")
    assert "JSON" in str(e.value)


def test_une_reponse_coupee_par_max_tokens_est_reconnue():
    charge = {"choices": [{"finish_reason": "length", "message": {}}]}
    with pytest.raises(ErreurValidation) as e:
        _extraire_outil(charge, "reponse")
    assert "max_tokens" in str(e.value)


def test_aucun_tool_call_du_tout_est_signale():
    charge = {"choices": [{"finish_reason": "stop", "message": {"content": "du texte libre"}}]}
    with pytest.raises(ErreurValidation):
        _extraire_outil(charge, "reponse")


# ── Coût, toujours nul ────────────────────────────────────────────────────

def test_le_modele_gratuit_coute_zero():
    from pdz.ia.registre import registre

    modele = registre().resoudre("qualite", profil="gratuit").modele
    reponse = groq.ReponseGroq(
        donnees={}, usage={"prompt_tokens": 50_000, "completion_tokens": 20_000},
        modele=modele, duree_ms=100,
    )
    assert reponse.cout == 0.0
    assert reponse.economie_cache == 0.0


# ── Vision ───────────────────────────────────────────────────────────────
# `charte` lit des images ; le modèle d'écriture gratuit n'en est pas
# capable, un autre modèle Groq l'est. Le registre choisit, l'adaptateur
# encode.

def test_sans_image_le_message_reste_une_simple_chaine():
    """La forme « liste de blocs » n'est pas acceptée par tous les modèles :
    on ne la sort que quand il y a vraiment des images."""
    assert groq._contenu_utilisateur("bonjour", None) == "bonjour"
    assert groq._contenu_utilisateur("bonjour", []) == "bonjour"


def test_les_images_partent_en_blocs_typees_apres_le_texte(tmp_path):
    from PIL import Image

    chemins = []
    for i in range(3):
        p = tmp_path / f"i{i}.jpg"
        Image.new("RGB", (32, 32), (i * 40, 60, 90)).save(p)
        chemins.append(p)

    contenu = groq._contenu_utilisateur("décris", chemins)
    assert contenu[0] == {"type": "text", "text": "décris"}
    assert len(contenu) == 4
    for bloc in contenu[1:]:
        assert bloc["type"] == "image_url"
        assert bloc["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_pas_plus_de_cinq_images(tmp_path):
    """Groq plafonne à 5 images ; l'analyse visuelle en extrait 6. Écarter
    la sixième vaut mieux que voir toute la requête refusée."""
    from PIL import Image

    chemins = []
    for i in range(6):
        p = tmp_path / f"i{i}.jpg"
        Image.new("RGB", (32, 32), (i * 30, 60, 90)).save(p)
        chemins.append(p)

    contenu = groq._contenu_utilisateur("décris", chemins)
    assert sum(1 for b in contenu if b["type"] == "image_url") == groq.IMAGES_MAX


# ── Le dispatcher : chaque alias va au bon fournisseur ───────────────────

def test_le_profil_par_defaut_va_chez_anthropic(monkeypatch):
    appele = {}

    async def faux_claude(**kwargs):
        appele["fournisseur"] = "anthropic"
        return "reponse-claude"

    async def faux_groq(**kwargs):
        appele["fournisseur"] = "groq"
        return "reponse-groq"

    monkeypatch.setattr(texte, "ADAPTATEURS", {"anthropic": faux_claude, "groq": faux_groq})

    import asyncio
    resultat = asyncio.run(texte.appeler(
        alias="qualite", systeme_stable="x", message="y", schema_sortie={},
    ))
    assert appele["fournisseur"] == "anthropic"
    assert resultat == "reponse-claude"


def test_le_profil_gratuit_va_chez_groq(monkeypatch):
    appele = {}

    async def faux_claude(**kwargs):
        appele["fournisseur"] = "anthropic"

    async def faux_groq(**kwargs):
        appele["fournisseur"] = "groq"
        return "reponse-groq"

    monkeypatch.setattr(texte, "ADAPTATEURS", {"anthropic": faux_claude, "groq": faux_groq})

    import asyncio
    resultat = asyncio.run(texte.appeler(
        alias="qualite", profil="gratuit",
        systeme_stable="x", message="y", schema_sortie={},
    ))
    assert appele["fournisseur"] == "groq"
    assert resultat == "reponse-groq"


def test_un_fournisseur_sans_adaptateur_de_texte_est_signale(monkeypatch):
    """Si demain un alias de texte pointe vers un modèle fal.ai par erreur
    de configuration, le message doit dire pourquoi — pas planter en KeyError."""
    monkeypatch.setattr(texte, "ADAPTATEURS", {})

    import asyncio
    with pytest.raises(ErreurConfig) as e:
        asyncio.run(texte.appeler(
            alias="qualite", systeme_stable="x", message="y", schema_sortie={},
        ))
    assert "modeles.yaml" in str(e.value)
