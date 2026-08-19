"""Golden tests — la compilation d'un même épisode ne doit pas dériver.

Avancés ici plutôt qu'en fin de migration, et pour une raison précise : les
phases qui suivent (compilateur de plans, stratégies de rendu, exécution)
vont RÉÉCRIRE la chaîne qui produit ces structures. Sans référence gelée, un
changement de comportement passerait pour un changement voulu.

── Ce qu'on gèle, et ce qu'on ne gèle surtout pas ───────────────────────

On gèle ce qui est **déterministe et architectural** : combien de plans, de
quelle durée, dans quel ordre, avec quelles arêtes, quelles frontières de
réplique, quelles sondes de vérification.

On ne gèle JAMAIS une sortie générative. Pas de comparaison de pixels, pas de
texte de prompt figé, pas de sortie de modèle : ces choses varient
légitimement, et les figer produirait un test qui échoue sans qu'aucune
régression n'ait eu lieu — le plus sûr moyen de faire ignorer une suite.

Le corpus est volontairement petit et lisible. Une référence qu'on ne peut
pas relire à l'œil ne sert qu'à faire passer les changements sans les
comprendre.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from pdz.adaptateurs import audio_timeline, shot_graph
from pdz.contracts import AudioTimeline, DirectorState, ShotGraph
from pdz.production.storyboard import decouper
from pdz.univers import Univers
from pdz.video.soustitres import Mot

REFERENCES = Path(__file__).parent / "golden"
RACINE = Path(__file__).resolve().parent.parent


# ── Le corpus ────────────────────────────────────────────────────────────
#
# Un cas FICTION et un cas EXPLICATIF, tous deux compilés jusqu'au
# `DirectorState`. Le second est arrivé avec la PHASE 3 : il vérifie que
# l'explicatif n'affirme QUE ce qui est sourcé, et que la même chaîne sert
# les deux profils sans en forcer aucun dans le moule de l'autre.

TRAHISON = {
    "nom": "fiction_trahison",
    "univers": "fruit-island",
    # Les durées sont MESURÉES, pas estimées — c'est tout le principe de la
    # chaîne (voix → timings réels → découpage). Ici elles sont figées pour
    # que le test soit reproductible sans appeler ElevenLabs.
    "repliques": [
        {"numero": 1, "personnage": "strawberina", "texte": "Tu m'as trahi, mon cœur.",
         "action": "s'avance lentement", "emotion": "colere", "decor": "villa",
         "reaction_de": "bananito", "fonction_plan": "pose le conflit", "relance": False},
        {"numero": 2, "personnage": "bananito", "texte": "Jamais.",
         "action": "recule d'un pas", "emotion": "surprise", "decor": "villa",
         "fonction_plan": "nie", "relance": False},
        {"numero": 3, "personnage": "strawberina", "texte": "Je dis ça je dis rien.",
         "action": "sourit en coin", "emotion": "mepris", "decor": "plage",
         "reaction_de": "bananito", "fonction_plan": "relance la tension",
         "relance": True},
    ],
    "durees_s": [3.4, 1.2, 2.8],
}


def _univers(nom: str) -> Univers:
    donnees = yaml.safe_load((RACINE / "univers" / f"{nom}.yaml").read_text(encoding="utf-8"))
    return Univers.model_validate(donnees)


def _compiler(cas: dict) -> ShotGraph:
    """La chaîne réellement exercée : répliques + durées mesurées → ShotGraph.

    Purement déterministe : `decouper()` n'appelle aucun modèle. C'est
    précisément pourquoi elle peut être gelée.
    """
    plans = decouper(cas["repliques"], cas["durees_s"], _univers(cas["univers"]))
    return shot_graph(plans)


def _reference(nom: str) -> Path:
    return REFERENCES / f"{nom}.json"


def _lire(nom: str) -> dict:
    chemin = _reference(nom)
    if not chemin.exists():
        pytest.fail(
            f"Référence absente : {chemin.relative_to(RACINE)}\n"
            f"Régénère-la avec `python -m tests.golden_regenerer`, PUIS relis le "
            f"diff : une référence acceptée sans être relue ne prouve plus rien."
        )
    return json.loads(chemin.read_text(encoding="utf-8"))


# ── Le test de référence ─────────────────────────────────────────────────

@pytest.mark.parametrize("cas", [TRAHISON], ids=lambda c: c["nom"])
def test_la_compilation_reste_identique_a_la_reference(cas):
    """Le cœur du golden test : même entrée, même graphe de plans."""
    obtenu = json.loads(_compiler(cas).en_json())
    attendu = _lire(cas["nom"])

    assert obtenu == attendu, (
        f"La compilation de « {cas['nom']} » a changé.\n"
        f"Si c'est VOULU : régénère la référence et relis le diff.\n"
        f"Si ce n'est pas voulu : c'est une régression, et c'est exactement "
        f"ce que ce test existe pour attraper."
    )


# ── Les invariants : ce qui doit rester vrai quoi qu'il arrive ──────────
#
# Distincts de la référence gelée. Une référence dit « c'était comme ça » ;
# un invariant dit « ça doit être comme ça ». Le second survit à une
# régénération volontaire de la première, et c'est ce qui le rend précieux.

@pytest.mark.parametrize("cas", [TRAHISON], ids=lambda c: c["nom"])
def test_la_duree_des_plans_couvre_exactement_celle_de_la_parole(cas):
    """L'invariant fondateur du dépôt : la voix est la chronologie officielle.

    Un écart ici, et l'image s'arrête avant la fin de la narration — le bug
    mesuré en production (42,7 s d'audio, 28,1 s de vidéo) que
    `coherence_duree.py` a été écrit pour empêcher.
    """
    graphe = _compiler(cas)
    assert graphe.duree_totale_s == pytest.approx(sum(cas["durees_s"]), abs=0.01)


@pytest.mark.parametrize("cas", [TRAHISON], ids=lambda c: c["nom"])
def test_chaque_plan_dure_assez_pour_etre_vu(cas):
    """En dessous d'environ 1,2 s, le cerveau traite la coupe comme du bruit."""
    for plan in _compiler(cas).plans:
        assert plan.duree_s >= 0.6, f"plan {plan.numero} : {plan.duree_s} s"


@pytest.mark.parametrize("cas", [TRAHISON], ids=lambda c: c["nom"])
def test_les_plans_sont_numerotes_sans_trou(cas):
    """Un trou décalerait images et son d'un cran — le montage sortirait
    des images qui ne correspondent plus aux répliques."""
    numeros = [p.numero for p in _compiler(cas).plans]
    assert numeros == list(range(len(numeros)))


@pytest.mark.parametrize("cas", [TRAHISON], ids=lambda c: c["nom"])
def test_une_reaction_produit_deux_plans_pour_une_replique(cas):
    """Réplique ≠ plan : celui qui parle, puis celui qui écoute."""
    graphe = _compiler(cas)
    assert len(graphe.plans) > len(cas["repliques"]), (
        "aucune réplique n'a été coupée en plan de réaction"
    )


@pytest.mark.parametrize("cas", [TRAHISON], ids=lambda c: c["nom"])
def test_les_aretes_ne_relient_que_des_plans_existants(cas):
    graphe = _compiler(cas)
    connus = {p.id for p in graphe.plans}
    for source, cible, _ in graphe.aretes:
        assert source in connus and cible in connus


@pytest.mark.parametrize("cas", [TRAHISON], ids=lambda c: c["nom"])
def test_le_graphe_fait_l_aller_retour_json(cas):
    origine = _compiler(cas)
    assert ShotGraph.depuis_json(origine.en_json()) == origine


@pytest.mark.parametrize("cas", [TRAHISON], ids=lambda c: c["nom"])
def test_la_compilation_est_reproductible(cas):
    """Deux compilations de la même entrée donnent le même octet.

    Sans cette propriété, le cache par empreinte ne sert à rien et le golden
    test lui-même deviendrait instable.
    """
    assert _compiler(cas).en_json() == _compiler(cas).en_json()


# ── Chronologie : le même gel, sur la bande voix ────────────────────────

def test_une_timeline_reconstruite_conserve_les_frontieres():
    """Les frontières de réplique décident où les sous-titres ont le droit
    de couper. Une dérive ici mêle deux personnages sur une même ligne."""
    from pathlib import Path as _Path

    from pdz.production.voix import BandeVoix, RepliqueDite

    bande = BandeVoix(
        fichier=_Path("/tmp/voix.mp3"), duree_ms=7400, caracteres_factures=64,
        repliques=[
            RepliqueDite(numero=1, personnage="strawberina", texte="Tu m'as trahi",
                         fichier=_Path("/tmp/1.mp3"), debut_ms=0, duree_ms=3400,
                         mots=[Mot(texte="Tu", debut_ms=0, fin_ms=280),
                               Mot(texte="m'as", debut_ms=280, fin_ms=900),
                               Mot(texte="trahi", debut_ms=900, fin_ms=3400)]),
            RepliqueDite(numero=2, personnage="bananito", texte="Jamais",
                         fichier=_Path("/tmp/2.mp3"), debut_ms=3600, duree_ms=1200,
                         mots=[Mot(texte="Jamais", debut_ms=3600, fin_ms=4800)]),
        ],
    )
    timeline = audio_timeline(bande)

    assert sorted(timeline.debuts_de_replique_ms) == [0, 3600]
    assert timeline.durees_repliques_s == (3.4, 1.2)
    assert AudioTimeline.depuis_json(timeline.en_json()) == timeline


# ── Le corpus des profils : la convergence, gelée ───────────────────────
#
# Ce que ces références protègent n'est pas une sortie créative — c'est la
# STRUCTURE de la décision de mise en scène : quels points la vidéo promet,
# quels paliers de compréhension, quelles lacunes assumées. Exactement ce
# que les phases suivantes vont réécrire.

MOTEUR = {
    "nom": "explicatif_moteur",
    "sujet": "Comment fonctionne un moteur électrique ?",
    # Résultats de recherche FIGÉS : le corpus doit tourner sans réseau, et
    # de façon identique d'une exécution à l'autre.
    "recherche": [
        {"enonce": "Le courant dans la bobine crée un champ magnétique",
         "sources": [{"url": "ex://physique", "titre": "Électromagnétisme"},
                     {"url": "ex://manuel", "titre": "Machines électriques"}]},
        {"enonce": "Le champ fait tourner le rotor",
         "sources": [{"url": "ex://physique"}]},
        # Volontairement non sourcé : la référence doit prouver qu'il est
        # EXCLU de ce que la vidéo promet, et remonté en lacune.
        {"enonce": "Le rendement dépasse toujours 95 %", "sources": []},
    ],
}


def _director_explicatif() -> DirectorState:
    from pdz.contracts import Profil, TopicRequest
    from pdz.director import compiler
    from pdz.research import RechercheMock, construire


    topic = TopicRequest(sujet=MOTEUR["sujet"], profil=Profil.EXPLICATIF,
                         duree_cible_s=45)
    recherche = construire(topic.sujet, RechercheMock(MOTEUR["recherche"]))
    return compiler(topic, recherche, brief=_BRIEF)


_BRIEF = {
    "strategie": {"mecanisme_hook": "un objet du quotidien, jamais regardé de près"},
    "beats": [
        {"position_pct": 0, "role": "hook", "quoi": "le moteur qu'on ne voit jamais"},
        {"position_pct": 45, "role": "mécanisme", "quoi": "le champ tourne"},
        {"position_pct": 85, "role": "payoff", "quoi": "pourquoi ça marche"},
    ],
}


def test_le_director_explicatif_reste_identique_a_la_reference():
    obtenu = json.loads(_director_explicatif().en_json())
    attendu = _lire(MOTEUR["nom"])
    assert obtenu == attendu, (
        "La compilation explicative a changé. Si c'est voulu : régénère et "
        "relis le diff. Sinon, c'est une régression."
    )


def test_l_explicatif_ne_promet_que_ce_qui_est_source():
    """L'invariant du profil, indépendant de la référence gelée.

    Trois énoncés cherchés, deux sourcés : la vidéo ne s'engage que sur
    ceux-là. Le troisième reste disponible, nuancé — il n'est pas promis.
    """
    etat = _director_explicatif()
    assert etat.intention.points_a_porter == ("claim_001", "claim_002")
    assert any("sans source" in x for x in etat.continuite.non_resolues)


def test_les_deux_profils_du_corpus_produisent_le_meme_contrat():
    """La convergence, vérifiée sur le corpus réel et pas sur des jouets."""
    assert isinstance(_director_explicatif(), DirectorState)
    assert _director_explicatif().reference() == "DirectorState@1.0.0"
