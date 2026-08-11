"""Tests du rapport avant/après (pdz.analyse.rapport_transfert).

Tout ici est pur : aucun appel IA, aucune vidéo. Les vérifications
mécaniques (SHOT_FUNCTION qui varie, chevauchement lexical) sont ce que ce
module PEUT trancher tout seul ; le reste — mécanique transférée ou
contenu recopié — reste, par construction, un jugement humain que le
rapport rend seulement plus rapide à porter.
"""

from __future__ import annotations

from pdz.analyse.rapport_transfert import (
    PlanRapporte,
    RapportTransfert,
    chevauchement_lexical,
    construire_rapport,
    mots_significatifs,
)


def _plan(numero, fonction, prompt, replique="il parle", action="il agit"):
    return PlanRapporte(
        numero=numero, personnage="p1", replique=replique, action=action,
        fonction=fonction, prompt_image=prompt,
    )


def test_mots_significatifs_ignore_les_mots_courants_et_laccentuation():
    mots = mots_significatifs("Une IA qui explique la physique quantique")
    assert "explique" in mots
    assert "physique" in mots
    assert "quantique" in mots
    # « une », « qui », « la » : trop courts ou trop communs.
    assert "une" not in mots and "qui" not in mots


def test_chevauchement_lexical_detecte_un_mot_partage_malgre_laccent():
    partages = chevauchement_lexical(
        "une IA qui révèle un secret quantique",
        "le personnage revele un mystere ancien",
    )
    assert "revele" in partages


def test_chevauchement_lexical_vide_si_reference_vide():
    assert chevauchement_lexical("", "n'importe quoi ici") == set()


def test_fonctions_consecutives_identiques_compte_les_paires():
    r = RapportTransfert(
        reference_id="ref", sujet_nouveau="x", empreinte_texte="", mecanique_attendue="",
        sujet_original="", titre_script="",
        plans=[_plan(0, "etablit l'echelle", "p0"),
               _plan(1, "etablit l'echelle", "p1"),   # répète la précédente
               _plan(2, "revele un detail", "p2")],
    )
    assert r.fonctions_consecutives_identiques() == 1
    assert r.fonctions_distinctes() == 2


def test_fonctions_consecutives_identiques_est_nul_quand_tout_varie():
    r = RapportTransfert(
        reference_id="ref", sujet_nouveau="x", empreinte_texte="", mecanique_attendue="",
        sujet_original="", titre_script="",
        plans=[_plan(0, "a", "p0"), _plan(1, "b", "p1"), _plan(2, "c", "p2")],
    )
    assert r.fonctions_consecutives_identiques() == 0


def test_prompts_distincts_compte_les_prompts_uniques():
    r = RapportTransfert(
        reference_id="ref", sujet_nouveau="x", empreinte_texte="", mecanique_attendue="",
        sujet_original="", titre_script="",
        plans=[_plan(0, "a", "meme prompt"), _plan(1, "b", "meme prompt"),
               _plan(2, "c", "prompt different")],
    )
    assert r.prompts_distincts() == 2


def test_chevauchement_avec_sujet_original_lit_repliques_et_actions():
    r = RapportTransfert(
        reference_id="ref", sujet_nouveau="dispute pour une pizza",
        empreinte_texte="", mecanique_attendue="",
        sujet_original="une IA qui explique la physique quantique",
        titre_script="",
        plans=[_plan(0, "a", "p0", replique="quelle belle pizza",
                     action="il explique la physique")],
    )
    assert "physique" in r.chevauchement_avec_sujet_original()


def test_construire_rapport_signale_une_regression_de_fonction_repetee():
    r = RapportTransfert(
        reference_id="ref", sujet_nouveau="x", empreinte_texte="hook: ...",
        mecanique_attendue="pose une question jamais résolue",
        sujet_original="une IA et un hologramme", titre_script="Titre",
        plans=[_plan(0, "meme fonction", "p0"), _plan(1, "meme fonction", "p1")],
    )
    texte = construire_rapport(r)
    assert "1 paire(s) consécutive(s) identique(s)" in texte
    assert "✗ à regarder" in texte
    assert "pose une question jamais résolue" in texte
    assert "une IA et un hologramme" in texte


def test_construire_rapport_signale_la_conformite_quand_tout_varie():
    r = RapportTransfert(
        reference_id="ref", sujet_nouveau="x", empreinte_texte="", mecanique_attendue="",
        sujet_original="", titre_script="",
        plans=[_plan(0, "a", "p0"), _plan(1, "b", "p1")],
    )
    texte = construire_rapport(r)
    assert "0 paire(s) consécutive(s) identique(s)" in texte
    assert "✓ conforme à la règle" in texte
    assert "pas de `sujet_original` noté" in texte


def test_construire_rapport_signale_un_chevauchement_avec_le_sujet_original():
    r = RapportTransfert(
        reference_id="ref", sujet_nouveau="dispute pour une pizza",
        empreinte_texte="", mecanique_attendue="", titre_script="",
        sujet_original="une IA qui explique la physique quantique",
        plans=[_plan(0, "a", "p0", replique="il parle de physique quantique")],
    )
    texte = construire_rapport(r)
    assert "mot(s) partagé(s)" in texte
    assert "quantique" in texte


def test_construire_rapport_contient_la_checklist_humaine():
    r = RapportTransfert(
        reference_id="ref", sujet_nouveau="x", empreinte_texte="", mecanique_attendue="",
        sujet_original="", titre_script="", plans=[],
    )
    texte = construire_rapport(r)
    assert "SAME FUNCTION + NEW SUBJECT + NEW STORY + NEW VISUAL EXECUTION" in texte
    assert "reste un jugement humain" in texte
