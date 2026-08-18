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


def test_le_retry_after_vient_de_len_tete_si_present():
    r = _reponse(429, {"error": {"message": "Please try again in 26.085s."}})
    r.headers["retry-after"] = "5"
    with pytest.raises(ErreurQuota) as e:
        _lever_si_erreur(r)
    assert e.value.retry_after == 5.0


def test_le_retry_after_se_lit_dans_le_texte_si_len_tete_manque():
    """Mesuré à l'écran : Groq ne renvoie pas toujours l'en-tête
    `Retry-After`. Sans lire le délai dans le texte de l'erreur, le moteur
    retombait sur un backoff générique d'environ 1 s, bien trop court pour
    une vraie limite par minute qui demandait 26 s pour se libérer — les 3
    tentatives étaient grillées avant que la fenêtre ne se libère."""
    r = _reponse(429, {"error": {
        "message": "Rate limit reached ... Please try again in 26.085s. "
                   "Need more tokens? Upgrade to Dev Tier today.",
    }})
    with pytest.raises(ErreurQuota) as e:
        _lever_si_erreur(r)
    assert e.value.retry_after == pytest.approx(26.085)


def test_un_delai_enorme_est_plafonne():
    """Mesuré à l'écran : Groq a répondu « try again in 2396s » (~40 min,
    un quota plus large que la limite par minute) et le job est resté
    silencieux tout ce temps. Attendre la durée complète bloquerait le job
    pendant potentiellement des heures — le délai doit être plafonné, pour
    que les tentatives s'épuisent vite avec un message clair plutôt que de
    faire patienter sans le dire."""
    r = _reponse(429, {"error": {"message": "Please try again in 2396.0s."}})
    with pytest.raises(ErreurQuota) as e:
        _lever_si_erreur(r)
    assert e.value.retry_after == groq.RETRY_AFTER_MAX_S


def test_un_en_tete_enorme_est_aussi_plafonne():
    r = _reponse(429, {"error": {"message": "x"}})
    r.headers["retry-after"] = "3600"
    with pytest.raises(ErreurQuota) as e:
        _lever_si_erreur(r)
    assert e.value.retry_after == groq.RETRY_AFTER_MAX_S


def test_un_delai_sous_le_plafond_reste_intact():
    r = _reponse(429, {"error": {"message": "Please try again in 26.085s."}})
    with pytest.raises(ErreurQuota) as e:
        _lever_si_erreur(r)
    assert e.value.retry_after == pytest.approx(26.085)


def test_le_message_ne_pretend_plus_que_la_limite_est_toujours_journaliere():
    """Groq limite par minute (RPM/TPM) ET par jour (RPD/TPD) — affirmer
    « journalier » en dur sur une limite par minute a fait croire à une
    attente d'un jour là où 26 s suffisaient."""
    r = _reponse(429, {"error": {"message": "tokens per minute (TPM): Limit 12000"}})
    with pytest.raises(ErreurQuota) as e:
        _lever_si_erreur(r)
    assert "journalier" not in str(e.value)
    assert "tokens per minute" in str(e.value)


# ── Fenêtre de jetons épuisée par un appel qui a échoué quand même ───────
#
# Le défaut mesuré (run #73), qui a fait échouer l'épisode entier :
#
#   19:49:46  429  → attente 44 s   (Groq disait ~48 s)
#   19:50:35  400  → attente 2,4 s  ← l'appel a atteint le modèle, donc vidé
#                                     la fenêtre ; rejouer si vite est perdu
#   19:50:37  429  → attente 50 s   ← une tentative TRANSITOIRE grillée
#   19:51:32  400  → attente 3,3 s  ← même piège
#   19:51:36  429  → fatal
#
# Le 400 était récupérable, mais il n'a jamais eu de seconde vraie chance :
# chaque relance rapide se transformait en 429, et les trois tentatives
# transitoires y sont passées.

def _reponse_400(reste: str, limite: str = "8000", reinit: str = "59.5s"):
    r = _reponse(400, {"error": {"message": "Failed to parse tool call arguments"}})
    r.headers["x-ratelimit-remaining-tokens"] = reste
    r.headers["x-ratelimit-limit-tokens"] = limite
    r.headers["x-ratelimit-reset-tokens"] = reinit
    return r


def test_un_400_qui_a_vide_la_fenetre_fait_attendre_sa_recharge():
    """Le correctif : un 400 reste une erreur de contenu (donc rejouable
    vite), sauf quand la fenêtre de jetons est vide — là, rejouer vite ne
    peut produire qu'un 429."""
    with pytest.raises(ErreurValidation) as e:
        _lever_si_erreur(_reponse_400(reste="323"))
    assert e.value.retry_after == pytest.approx(59.5)


def test_un_400_avec_du_budget_restant_se_rejoue_sans_attendre():
    """L'inverse compte autant : ne pas imposer une minute d'attente à une
    erreur de contenu ordinaire quand la fenêtre est encore large."""
    with pytest.raises(ErreurValidation) as e:
        _lever_si_erreur(_reponse_400(reste="7000"))
    assert e.value.retry_after is None


def test_un_400_sans_en_tetes_de_fenetre_garde_lancien_comportement():
    """Non-régression : sans ces en-têtes (autre fournisseur, réponse
    tronquée), le moteur retombe sur son backoff générique."""
    with pytest.raises(ErreurValidation) as e:
        _lever_si_erreur(_reponse(400, {"error": {"message": "x"}}))
    assert e.value.retry_after is None


def test_lattente_de_fenetre_est_plafonnee_comme_le_reste():
    with pytest.raises(ErreurValidation) as e:
        _lever_si_erreur(_reponse_400(reste="0", reinit="2m30s"))
    assert e.value.retry_after == groq.RETRY_AFTER_MAX_S


@pytest.mark.parametrize("valeur, attendu", [
    ("7.66s", 7.66),
    ("59.5s", 59.5),
    ("1m", 60.0),
    ("2m30s", 150.0),
    ("2m59.56s", 179.56),
    ("", None),
    ("bientot", None),
])
def test_le_format_de_duree_des_en_tetes_est_bien_lu(valeur, attendu):
    """`x-ratelimit-reset-tokens` n'est pas un nombre de secondes : c'est
    « 7.66s » ou « 2m59.56s ». Le lire comme un float rendrait le correctif
    silencieusement inopérant."""
    assert groq._duree_groq(valeur) == (
        pytest.approx(attendu) if attendu is not None else None)


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

# ── Booléens rendus en texte ─────────────────────────────────────────────
# Llama écrit « "true" » là où le schéma demande `true`. Groq valide le
# schéma sur son serveur : un seul champ de travers et toute la réponse est
# refusée (400), après avoir été écrite. On assouplit à l'envoi et on rend
# leur type à la lecture, sans toucher au schéma du domaine.

def _schema_avec_booleen():
    return {
        "type": "object",
        "properties": {
            "repliques": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "numero": {"type": "integer"},
                        "relance": {"type": "boolean"},
                    },
                },
            },
        },
    }


def test_le_schema_envoye_accepte_aussi_une_chaine():
    assoupli = groq._assouplir_booleens(_schema_avec_booleen())
    relance = assoupli["properties"]["repliques"]["items"]["properties"]["relance"]
    assert relance["type"] == ["boolean", "string"]


def test_le_schema_du_domaine_nest_pas_modifie():
    """L'assouplissement est un pansement propre à Groq : Anthropic doit
    continuer à recevoir le schéma exact."""
    base = _schema_avec_booleen()
    groq._assouplir_booleens(base)
    relance = base["properties"]["repliques"]["items"]["properties"]["relance"]
    assert relance["type"] == "boolean"


@pytest.mark.parametrize("brut,attendu", [
    ("true", True), ("True", True), ("vrai", True), ("oui", True), ("1", True),
    ("false", False), ("False", False), ("non", False), ("", False),
])
def test_les_booleens_en_texte_retrouvent_leur_type(brut, attendu):
    sortie = groq._durcir_booleens(
        {"repliques": [{"numero": 1, "relance": brut}]}, _schema_avec_booleen(),
    )
    assert sortie["repliques"][0]["relance"] is attendu


def test_un_vrai_booleen_traverse_intact():
    sortie = groq._durcir_booleens(
        {"repliques": [{"numero": 1, "relance": True}]}, _schema_avec_booleen(),
    )
    assert sortie["repliques"][0]["relance"] is True


def test_les_autres_champs_ne_sont_pas_touches():
    sortie = groq._durcir_booleens(
        {"repliques": [{"numero": 3, "relance": "true"}]}, _schema_avec_booleen(),
    )
    assert sortie["repliques"][0]["numero"] == 3


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


# ── « Failed to parse tool call arguments as JSON » : lequel des deux ? ───
#
# Mesuré (run #76) : `shot_prompts` a pris ce 400 trois fois de suite, et
# l'épisode est mort dessus. Le message ne dit pas si le modèle a écrit
# n'importe quoi ou s'il a été COUPÉ en plein milieu — deux pannes opposées.
# Groq met pourtant le texte fautif dans `error.failed_generation`, et le
# code le jetait.

def _400_json(fragment: str | None) -> httpx.Response:
    erreur = {"message": "Failed to parse tool call arguments as JSON"}
    if fragment is not None:
        erreur["failed_generation"] = fragment
    return _reponse(400, {"error": erreur})


def test_une_sortie_coupee_est_reconnue_comme_tronquee():
    """Un JSON coupé s'arrête au milieu d'une chaîne : pas d'accolade
    fermante. Le rejouer à l'identique le fera couper au même endroit."""
    with pytest.raises(ErreurValidation) as e:
        _lever_si_erreur(_400_json('{"plans": [{"numero": 1, "action": "un long text'))
    assert "TRONQUÉE" in str(e.value)
    assert "MOINS DE TEXTE" in str(e.value), \
        "le texte repart au modèle : il doit porter une consigne, pas un constat"


def test_un_json_complet_mais_invalide_nest_pas_dit_tronque():
    """L'inverse compte autant : accuser `max_tokens` là où le modèle s'est
    juste trompé de format enverrait chercher le mauvais problème."""
    with pytest.raises(ErreurValidation) as e:
        _lever_si_erreur(_400_json('{"plans": [{"numero": "un"},]}'))
    assert "TRONQUÉE" not in str(e.value)
    assert "malformé mais COMPLET" in str(e.value)


def test_le_texte_fautif_est_resume_pas_recrache_en_entier():
    """La fin suffit à trancher, et le message finit dans un journal."""
    with pytest.raises(ErreurValidation) as e:
        _lever_si_erreur(_400_json('{"x": "' + "a" * 5000))
    message = str(e.value)
    assert "5007 caractères produits" in message
    assert len(message) < 700, "un journal ne doit pas recevoir 5000 caractères"


def test_un_400_sans_failed_generation_garde_son_message():
    """Non-régression : les autres 400 (schéma refusé, outil inconnu) ne
    doivent hériter d'aucun diagnostic inventé."""
    with pytest.raises(ErreurValidation) as e:
        _lever_si_erreur(_400_json(None))
    assert "TRONQUÉE" not in str(e.value)
    assert "COMPLET" not in str(e.value)
    assert "Failed to parse tool call arguments" in str(e.value)
