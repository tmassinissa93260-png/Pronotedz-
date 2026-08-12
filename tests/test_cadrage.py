"""La vérification déterministe de la diversité des cadrages.

Diagnostic seulement — jamais une relance, jamais un appel IA.
"""

from __future__ import annotations

from pdz.production import cadrage


def test_des_cadrages_tous_differents_ne_produisent_rien():
    avertissements = cadrage.verifier_diversite(
        ["plan_large", "plan_moyen", "gros_plan", "plan_detail"]
    )
    assert avertissements == []


def test_deux_cadrages_identiques_consecutifs_sont_signales():
    avertissements = cadrage.verifier_diversite(["gros_plan", "gros_plan", "plan_large"])
    assert len(avertissements) == 1
    assert "gros_plan" in avertissements[0]


def test_plusieurs_repetitions_sont_toutes_signalees():
    avertissements = cadrage.verifier_diversite(
        ["gros_plan", "gros_plan", "plan_large", "plan_large"]
    )
    assert len(avertissements) == 2


def test_des_cadrages_vides_ne_declenchent_rien():
    """Non-régression : un plan sans cadrage (ancien job repris avant cette
    version) ne doit pas être compté comme « identique » à son voisin."""
    assert cadrage.verifier_diversite(["", "", "gros_plan"]) == []


def test_le_vocabulaire_reste_court():
    """Un enum JSON Schema trop long augmente le risque qu'un modèle
    Llama/Groq renvoie une valeur hors liste et fasse rejeter toute la
    réponse (voir l'historique de script@1.4.0 sur `emotion`)."""
    assert 3 <= len(cadrage.CADRAGES) <= 8
