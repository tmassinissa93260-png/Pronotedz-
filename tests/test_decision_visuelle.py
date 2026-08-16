"""decision_visuelle.verifier() : recoupe les champs du Visual Contract
entre eux, avant toute génération — jamais l'image, jamais un score.
"""

from __future__ import annotations

from pdz.production import decision_visuelle
from pdz.production.contrat_visuel import ContratVisuel


def _contrat(**kwargs) -> ContratVisuel:
    base = dict(qui="strawberina", qui_apparence="...", quoi="elle sourit")
    base.update(kwargs)
    return ContratVisuel(**base)


def test_sujet_et_action_absents_produisent_deux_faits():
    contrat = _contrat(qui="", quoi="")
    faits = decision_visuelle.verifier(contrat)
    assert "sujet manquant" in faits
    assert "action manquante" in faits


def test_sujet_et_action_presents_ne_produisent_rien():
    assert decision_visuelle.verifier(_contrat()) == []


def test_objet_non_positionne_est_signale_quand_geometrie_est_deja_utilisee():
    contrat = _contrat(
        avec_quoi=["airliner", "runway"],
        geometrie=[{"entite": "airliner", "zone": "center", "profondeur": "foreground"}],
    )
    faits = decision_visuelle.verifier(contrat)
    assert any("runway" in f and "positionné" in f for f in faits)


def test_geometrie_vide_ne_declenche_aucune_verification_de_position():
    """Un plan simple, à un seul sujet, n'a pas besoin de geometrie — pas
    de faux positif juste parce qu'il n'en a pas."""
    contrat = _contrat(avec_quoi=["golden trophy"])
    assert decision_visuelle.verifier(contrat) == []


def test_tous_les_objets_positionnes_ne_produit_rien():
    contrat = _contrat(
        avec_quoi=["airliner"],
        geometrie=[{"entite": "airliner", "zone": "center", "profondeur": "foreground"}],
    )
    assert decision_visuelle.verifier(contrat) == []


def test_relation_orpheline_est_signalee():
    contrat = _contrat(
        avec_quoi=["airliner"],
        relations=[{"cible": "flight path", "etat": "curves upward"}],
    )
    faits = decision_visuelle.verifier(contrat)
    assert any("flight path" in f and "orpheline" in f for f in faits)


def test_relation_avec_cible_connue_ne_produit_rien():
    contrat = _contrat(
        avec_quoi=["airliner"],
        relations=[{"cible": "airliner", "etat": "climbing steadily"}],
    )
    assert decision_visuelle.verifier(contrat) == []


def test_relation_vers_un_element_secondaire_ne_produit_rien():
    contrat = _contrat(
        avec_quoi_secondaire=["distant fish"],
        relations=[{"cible": "distant fish", "etat": "swimming past"}],
    )
    assert decision_visuelle.verifier(contrat) == []


def test_risque_de_marque_non_traite_est_signale():
    contrat = _contrat(risques_marque=["Tesla"])
    faits = decision_visuelle.verifier(contrat)
    assert any("Tesla" in f and "non traité" in f for f in faits)


def test_risque_de_marque_couvert_par_une_abstraction_ne_produit_rien():
    contrat = _contrat(
        risques_marque=["Tesla"],
        abstractions=[{"concept": "Tesla", "representation": "generic unbranded vehicle component"}],
    )
    assert decision_visuelle.verifier(contrat) == []


def test_risque_de_marque_couvert_par_une_exclusion_ne_produit_rien():
    contrat = _contrat(
        risques_marque=["Tesla"],
        ne_doit_pas_apparaitre=["Tesla"],
    )
    assert decision_visuelle.verifier(contrat) == []


def test_sans_risques_marque_aucune_verification_de_traitement():
    assert decision_visuelle.verifier(_contrat()) == []


def test_un_contrat_coherent_et_complet_ne_produit_aucun_fait():
    contrat = _contrat(
        avec_quoi=["airliner", "runway"],
        avec_quoi_secondaire=["fog"],
        relations=[{"cible": "flight path", "etat": "curves upward"},
                  {"cible": "airliner", "etat": "climbing"}],
        geometrie=[{"entite": "airliner", "zone": "center", "profondeur": "foreground"},
                  {"entite": "runway", "zone": "bottom", "profondeur": "foreground"}],
        risques_marque=["Tesla"],
        abstractions=[{"concept": "Tesla", "representation": "generic unbranded vehicle component"}],
    )
    # "flight path" reste orpheline volontairement : une trajectoire n'est
    # jamais un objet nommé dans avec_quoi — vérifie que CE fait précis
    # reste isolé et ne cache pas les autres vérifications déjà passées.
    faits = decision_visuelle.verifier(contrat)
    assert faits == ["relation(s) orpheline(s) : flight path"]
