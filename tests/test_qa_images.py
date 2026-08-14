"""Les fonctions pures de qa_images.py : gating et correction déterministe.

Le comportement en conditions réelles (nombre d'appels, régénération,
NEEDS_REVIEW) est couvert par tests/test_qa_images_gating.py, à travers le
pipeline complet.
"""

from __future__ import annotations

from pdz.production import qa_images
from pdz.production.storyboard import PlanScript
from pdz.prompts import charger


def _plan(numero=0, corrections_fidelite=None):
    return PlanScript(
        numero=numero, replique_numero=numero, personnage="x",
        action="a", emotion="calme",
        corrections_fidelite=corrections_fidelite or [],
    )


def test_un_plan_sans_signal_nest_pas_a_verifier():
    plans = [_plan(0)]
    assert qa_images.plans_a_verifier(plans, numeros_realisme=set()) == set()


def test_un_plan_corrige_par_fidelite_visuelle_est_a_verifier():
    plans = [_plan(0, corrections_fidelite=["submarine cable"]), _plan(1)]
    assert qa_images.plans_a_verifier(plans, numeros_realisme=set()) == {0}


def test_un_plan_passe_par_realisme_est_a_verifier():
    plans = [_plan(0), _plan(1)]
    assert qa_images.plans_a_verifier(plans, numeros_realisme={1}) == {1}


def test_les_deux_signaux_se_cumulent_sans_doublon():
    plans = [_plan(0, corrections_fidelite=["x"]), _plan(1), _plan(2)]
    assert qa_images.plans_a_verifier(plans, numeros_realisme={1, 2}) == {0, 1, 2}


def test_corriger_prompt_rajoute_les_manquants():
    prompt = qa_images.corriger_prompt("a generic hologram", ["submarine cable"], [], [])
    assert "submarine cable" in prompt


def test_corriger_prompt_exclut_les_incorrects_et_en_trop():
    prompt = qa_images.corriger_prompt(
        "a wide shot", [], ["male character"], ["laptop"],
    )
    assert "no male character" in prompt
    assert "no laptop" in prompt


def test_corriger_prompt_combine_les_trois():
    prompt = qa_images.corriger_prompt(
        "a generic hologram", ["submarine cable"], ["male character"], ["laptop"],
    )
    assert "submarine cable" in prompt
    assert "no male character" in prompt
    assert "no laptop" in prompt


# ── Le verdict ne se fie plus SEULEMENT à la checklist auto-rapportée ────

def test_le_prompt_actif_verifie_aussi_contre_la_replique():
    """Bug structurel trouvé par l'audit data-flow : `elements_obligatoires`
    est écrit par ShotPromptWriter DANS LE MÊME APPEL que `prompt_image` —
    un oubli s'y répète presque toujours (même modèle, même angle mort).
    `replique` vient d'un appel séparé (ScriptWriter) : la seule référence
    réellement indépendante déjà disponible, zéro appel IA de plus."""
    p = charger("analyse/qa_image")
    texte = p.systeme_stable.lower()
    assert "réplique" in texte
    assert "manque" in texte  # le manquant évident doit rejoindre `manquants`
    stable, _, message = p.rendre(
        action="a wide shot", replique="Une mère regarde un message sur son téléphone.",
        elements_obligatoires=[], elements_a_exclure=[],
    )
    assert "Une mère regarde un message sur son téléphone." in message
