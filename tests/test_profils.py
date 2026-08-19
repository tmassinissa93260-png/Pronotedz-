"""Deux profils, une seule sortie — et aucun des deux forcé dans l'autre.

Ce que ces tests protègent, c'est la décision de docs/GAP_ANALYSIS.md § 1 :

  · une fiction n'a JAMAIS à produire de claims ni de sources ;
  · un explicatif n'affirme QUE ce qui est sourcé ;
  · les deux produisent le MÊME `DirectorState`, si bien que tout ce qui
    suit dans le compilateur est écrit une seule fois.

Le jour où l'un des trois lâche, la divergence sera rentrée dans le
compilateur — l'erreur exacte que cette architecture existe pour éviter.
"""

from __future__ import annotations

import pytest
import yaml

from pdz.contracts import (
    Certitude,
    DirectorState,
    LangageVisuel,
    NarrativeState,
    Profil,
    ResearchState,
    TopicRequest,
)
from pdz.director import PALIERS_EXPLICATIFS, PALIERS_FICTION, compiler
from pdz.narrative import depuis_univers
from pdz.research import RechercheMock, SansRecherche, construire, qualifier
from pdz.univers import Univers

RACINE = __import__("pathlib").Path(__file__).resolve().parent.parent

BRIEF = {
    "strategie": {"mecanisme_hook": "une accusation directe"},
    "beats": [
        {"position_pct": 0, "role": "hook", "quoi": "accusation"},
        {"position_pct": 60, "role": "montée de tension", "quoi": "déni"},
        {"position_pct": 90, "role": "payoff", "quoi": "aveu"},
    ],
    "relances": [2, 5],
}

SCRIPT = {
    "promesse": "une trahison va éclater",
    "repliques": [
        {"numero": 1, "personnage": "strawberina", "action": "s'avance",
         "fonction_plan": "pose le conflit", "reaction_de": "bananito"},
        {"numero": 2, "personnage": "bananito", "action": "recule",
         "fonction_plan": "nie"},
        {"numero": 3, "personnage": "strawberina", "action": "sourit en coin",
         "fonction_plan": "relance"},
    ],
}


@pytest.fixture
def univers() -> Univers:
    donnees = yaml.safe_load((RACINE / "univers" / "fruit-island.yaml").read_text(encoding="utf-8"))
    return Univers.model_validate(donnees)


def _fiction(univers, script=SCRIPT) -> DirectorState:
    topic = TopicRequest(sujet="Strawberina trahit Bananito", profil=Profil.FICTION)
    return compiler(topic, depuis_univers(univers, topic.sujet, script), brief=BRIEF)


def _explicatif(resultats) -> DirectorState:
    topic = TopicRequest(sujet="Comment fonctionne un moteur électrique ?",
                         profil=Profil.EXPLICATIF)
    return compiler(topic, construire(topic.sujet, RechercheMock(resultats)), brief=BRIEF)


# ── La convergence ───────────────────────────────────────────────────────

def test_les_deux_profils_produisent_le_meme_contrat(univers):
    """Tout ce qui suit dans le compilateur est écrit UNE FOIS."""
    fiction = _fiction(univers)
    explicatif = _explicatif([{"enonce": "le rotor tourne", "sources": [{"url": "a"}]}])
    assert type(fiction) is type(explicatif) is DirectorState
    assert fiction.reference() == explicatif.reference()


def test_le_profil_est_porte_par_l_etat(univers):
    assert _fiction(univers).profil is Profil.FICTION
    assert _explicatif([]).profil is Profil.EXPLICATIF


def test_le_routage_suit_le_type_de_la_source_pas_un_drapeau(univers):
    """Un `ResearchState` ne peut pas être compilé en fiction. Laisser un
    booléen décider ouvrirait cette possibilité pour rien."""
    topic_fiction = TopicRequest(sujet="x", profil=Profil.FICTION)
    # Le topic dit « fiction », la source est une recherche : c'est la
    # source qui gagne, et le profil de l'état reflète la réalité.
    etat = compiler(topic_fiction, ResearchState(id="r"))
    assert etat.profil is Profil.EXPLICATIF


def test_la_partie_commune_vient_du_brief_dans_les_deux_cas(univers):
    """`BriefWriter` produit une structure narrative sans savoir si le sujet
    est réel ou inventé — et c'est très bien ainsi."""
    fiction = _fiction(univers)
    explicatif = _explicatif([])
    assert fiction.intention.beats == explicatif.intention.beats
    assert fiction.intention.accroche == explicatif.intention.accroche == "une accusation directe"
    assert fiction.emotion.relances == explicatif.emotion.relances == (2, 5)


# ── Ce qui reste PROPRE à chaque profil ─────────────────────────────────

def test_la_fiction_n_a_ni_claim_ni_source(univers):
    """Demander ses preuves à « Strawberina trahit Bananito » produirait une
    abstraction vide."""
    narration = depuis_univers(univers, "Strawberina trahit Bananito", SCRIPT)
    assert isinstance(narration, NarrativeState)
    assert not hasattr(narration, "claims")
    assert narration.conflit == "une trahison va éclater"


def test_l_explicatif_n_a_ni_personnage_ni_decor():
    recherche = construire("moteur", RechercheMock([{"enonce": "e", "sources": [{"url": "u"}]}]))
    assert isinstance(recherche, ResearchState)
    assert not hasattr(recherche, "personnages")


def test_les_paliers_different_car_on_ne_comprend_pas_une_trahison(univers):
    """En fiction, l'acquisition n'est pas un savoir mais une tension. Les
    six paliers explicatifs y seraient un contresens."""
    assert _fiction(univers).spectateur.paliers == PALIERS_FICTION
    assert _explicatif([]).spectateur.paliers == PALIERS_EXPLICATIFS
    assert PALIERS_FICTION != PALIERS_EXPLICATIFS


def test_la_fiction_ancre_les_personnages_qui_jouent(univers):
    ancres = _fiction(univers).continuite.ancres
    assert "strawberina" in ancres and "bananito" in ancres
    # `avocado` existe dans l'univers mais ne parle pas dans cet épisode :
    # il n'a pas de rôle, donc rien à tenir.
    assert "avocado" not in ancres


# ── L'honnêteté de l'explicatif ─────────────────────────────────────────

def test_seuls_les_claims_sources_sont_promis():
    """Un heuristique peut apparaître dans la vidéo, nuancé — il ne fait pas
    partie de ce qu'elle PROMET. Confondre les deux produit une vidéo
    assurée sur du vide."""
    etat = _explicatif([
        {"enonce": "sourcé", "sources": [{"url": "a"}]},
        {"enonce": "non sourcé", "sources": []},
    ])
    assert etat.intention.points_a_porter == ("claim_001",)


def test_un_claim_contredit_n_est_pas_promis():
    etat = _explicatif([
        {"enonce": "contesté", "sources": [{"url": "a"}], "conflits": ["autre"]},
    ])
    assert etat.intention.points_a_porter == ()


def test_les_lacunes_de_recherche_remontent_en_continuite_non_resolue():
    """Une lacune énoncée est utilisable ; une lacune silencieuse produit
    une vidéo assurée sur du vide."""
    etat = _explicatif([{"enonce": "non sourcé", "sources": []}])
    assert any("sans source" in x for x in etat.continuite.non_resolues)


def test_la_these_est_le_claim_le_plus_solide():
    etat = _explicatif([
        {"enonce": "une seule source", "sources": [{"url": "a"}]},
        {"enonce": "trois sources", "sources": [{"url": "a"}, {"url": "b"}, {"url": "c"}]},
    ])
    assert etat.intention.these == "trois sources"


def test_sans_claim_affirmable_la_these_reste_vide():
    """Mieux vaut aucune thèse qu'une thèse inventée."""
    assert _explicatif([{"enonce": "rien de sourcé", "sources": []}]).intention.these == ""


# ── La qualification : la règle d'honnêteté, testée à la source ─────────

def test_un_enonce_sans_source_reste_heuristique():
    certitude, _ = qualifier([])
    assert certitude is Certitude.HEURISTIQUE


def test_une_contradiction_empeche_le_fait_quel_que_soit_le_nombre_de_sources():
    """Le système ne tranche pas un désaccord tout seul."""
    certitude, _ = qualifier([{"url": i} for i in range(10)], conflits=("autre",))
    assert certitude is Certitude.HEURISTIQUE


def test_une_information_perimee_n_est_pas_un_fait():
    """Vraie en 2019 et fausse aujourd'hui n'est pas une erreur de source."""
    certitude, _ = qualifier([{"url": "a"}], statut_temporel="obsolete")
    assert certitude is Certitude.HEURISTIQUE


def test_des_sources_concordantes_font_un_fait():
    certitude, confiance = qualifier([{"url": "a"}, {"url": "b"}])
    assert certitude is Certitude.FAIT and confiance > 0.5


def test_la_confiance_ne_touche_jamais_un():
    """Aucune recherche automatique ne mérite la certitude absolue —
    et laisser le nombre atteindre 1 inviterait à confondre confiance et statut."""
    _, confiance = qualifier([{"url": i} for i in range(100)])
    assert confiance < 1.0


# ── Sans recherche : dire qu'on ne sait pas ─────────────────────────────

def test_sans_backend_le_graphe_est_vide_et_la_lacune_est_nommee():
    """La réponse honnête quand aucune recherche n'est configurée — pas un
    graphe de claims inventés par un modèle à qui on aurait demandé « ce que
    tu sais »."""
    etat = construire("moteur électrique")
    assert etat.claims == ()
    assert len(etat.lacunes) == 1
    assert "rien n'est vérifié" in etat.lacunes[0]


def test_le_backend_par_defaut_ne_cherche_rien_et_le_dit():
    assert SansRecherche().chercher("n'importe quoi") == []


def test_un_director_sans_recherche_ne_promet_rien():
    topic = TopicRequest(sujet="moteur", profil=Profil.EXPLICATIF)
    etat = compiler(topic, construire(topic.sujet))
    assert etat.intention.points_a_porter == ()
    assert etat.intention.these == ""
    assert etat.continuite.non_resolues


# ── Le Director n'invente rien ──────────────────────────────────────────

def test_rien_n_est_suppose_connu_du_spectateur(univers):
    """Supposer à la place du spectateur est le meilleur moyen de sauter
    l'explication dont il avait besoin."""
    assert _fiction(univers).spectateur.connaissances_supposees == ()


def test_sans_brief_l_intention_reste_vide_plutot_que_devinee(univers):
    topic = TopicRequest(sujet="x", profil=Profil.FICTION)
    etat = compiler(topic, depuis_univers(univers, "x", SCRIPT))
    assert etat.intention.beats == ()
    assert etat.intention.accroche == ""
    assert etat.emotion.courbe == ()


def test_le_payoff_est_cherche_par_son_role_pas_pris_comme_dernier(univers):
    """Une vidéo peut se terminer sur une boucle : le payoff n'est alors pas
    le dernier élément de la liste."""
    brief = {"beats": [
        {"position_pct": 70, "role": "payoff", "quoi": "la révélation"},
        {"position_pct": 95, "role": "boucle", "quoi": "retour au début"},
    ]}
    topic = TopicRequest(sujet="x", profil=Profil.FICTION)
    etat = compiler(topic, depuis_univers(univers, "x", SCRIPT), brief=brief)
    assert etat.intention.payoff == "la révélation"


def test_les_contraintes_viennent_du_topic(univers):
    topic = TopicRequest(sujet="x", profil=Profil.FICTION, duree_cible_s=90,
                         langue="en", plateformes=("shorts",))
    etat = compiler(topic, depuis_univers(univers, "x"), budget_max_eur=0.6)
    assert etat.contraintes.duree_cible_s == 90
    assert etat.contraintes.langue == "en"
    assert etat.contraintes.plateformes == ("shorts",)
    assert etat.contraintes.budget_max_eur == 0.6


def test_le_langage_visuel_est_recu_jamais_fabrique(univers):
    """Le Director assemble une décision de mise en scène — il ne génère
    aucun contenu visuel."""
    visuel = LangageVisuel(registre="wireframe", ambiance="tendue")
    topic = TopicRequest(sujet="x", profil=Profil.FICTION)
    etat = compiler(topic, depuis_univers(univers, "x"), visuel=visuel)
    assert etat.visuel.registre == "wireframe"
    assert compiler(topic, depuis_univers(univers, "x")).visuel.registre == ""


# ── La narration ne devine pas non plus ─────────────────────────────────

def test_un_personnage_muet_n_a_pas_de_role(univers):
    narration = depuis_univers(univers, "x", SCRIPT)
    muets = [p.id for p in narration.personnages if not p.role]
    assert "avocado" in muets


def test_seules_les_repliques_avec_action_deviennent_des_evenements(univers):
    """Une réplique sans action est une prise de parole, pas un fait du monde."""
    script = {"repliques": [
        {"numero": 1, "personnage": "strawberina", "action": "s'avance"},
        {"numero": 2, "personnage": "bananito", "action": ""},
    ]}
    assert len(depuis_univers(univers, "x", script).evenements) == 1


def test_sans_script_la_narration_ne_fabrique_ni_conflit_ni_evenement(univers):
    narration = depuis_univers(univers, "x")
    assert narration.conflit == "" and narration.evenements == ()
    assert narration.regles_du_monde, "les règles du monde viennent de l'univers"


def test_les_etats_font_l_aller_retour_json(univers):
    for etat in (_fiction(univers), _explicatif([{"enonce": "e", "sources": [{"url": "u"}]}])):
        assert DirectorState.depuis_json(etat.en_json()) == etat
