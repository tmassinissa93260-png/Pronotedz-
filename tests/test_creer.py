"""`pdz creer` — le profil explicatif, atteignable depuis la ligne de commande.

Ce que ces tests protègent, et qui est toute la valeur du profil :

  · **seuls les énoncés sourcés sont affirmables.** Un scénariste à qui l'on
    donne dix énoncés sans distinction en fera dix affirmations — c'est le
    mécanisme exact par lequel une vidéo devient assurée sur du vide ;
  · **les lacunes sont dites**, pas tues. « On ne sait pas » est une consigne
    utilisable ; son absence produit une invention ;
  · **rien n'est bloqué**, mais rien n'est caché : produire sur un sujet non
    vérifié reste possible, et l'utilisateur le sait.
"""

from __future__ import annotations

import json

import pytest

from pdz.contracts import Profil, TopicRequest
from pdz.director import compiler, projeter_en_situation
from pdz.research import RechercheMock, construire

SOURCES = [
    {"enonce": "Le courant dans la bobine crée un champ magnétique",
     "sources": [{"url": "ex://physique"}, {"url": "ex://manuel"}]},
    {"enonce": "Le champ fait tourner le rotor", "sources": [{"url": "ex://physique"}]},
    {"enonce": "Le rendement dépasse toujours 95 %", "sources": []},
    {"enonce": "Inventé en 1821", "sources": [{"url": "ex://histoire"}],
     "statut_temporel": "obsolete"},
    {"enonce": "Le cuivre est le seul conducteur utilisable",
     "sources": [{"url": "ex://a"}], "conflits": ["claim_001"]},
]


def _projection(sources=SOURCES, sujet="Comment fonctionne un moteur électrique ?"):
    topic = TopicRequest(sujet=sujet, profil=Profil.EXPLICATIF)
    recherche = construire(topic.sujet, RechercheMock(sources))
    return projeter_en_situation(compiler(topic, recherche), recherche), recherche


# ── La séparation, qui EST la fonctionnalité ────────────────────────────

def test_les_enonces_sources_sont_affirmables():
    projection, _ = _projection()
    bloc = projection.split("À NE JAMAIS AFFIRMER")[0]
    assert "champ magnétique" in bloc
    assert "fait tourner le rotor" in bloc


def test_un_enonce_sans_source_n_est_jamais_affirmable():
    projection, _ = _projection()
    affirmable = projection.split("À NE JAMAIS AFFIRMER")[0]
    assert "95 %" not in affirmable
    assert "95 %" in projection, "il reste évocable, nuancé"


def test_une_information_perimee_n_est_pas_affirmable():
    projection, _ = _projection()
    assert "1821" not in projection.split("À NE JAMAIS AFFIRMER")[0]


def test_un_enonce_contredit_n_est_pas_affirmable():
    """Le système ne tranche pas un désaccord tout seul."""
    projection, _ = _projection()
    assert "cuivre" not in projection.split("À NE JAMAIS AFFIRMER")[0]


@pytest.mark.parametrize("extrait,raison", [
    ("95 %", "aucune source"),
    ("1821", "information périmée"),
    ("cuivre", "des sources se contredisent"),
])
def test_chaque_declassement_porte_sa_raison(extrait, raison):
    """« Non établi » sans raison invite à passer outre ; « aucune source »
    ne s'argumente pas."""
    projection, _ = _projection()
    ligne = next(x for x in projection.splitlines() if extrait in x)
    assert raison in ligne


def test_les_lacunes_sont_dites_pas_tues():
    projection, _ = _projection()
    assert "N'A PAS ÉTABLI" in projection
    assert "n'invente rien" in projection


# ── Sans recherche ──────────────────────────────────────────────────────

def test_sans_source_rien_n_est_affirmable_et_c_est_dit():
    """La réponse honnête, pas un graphe de claims inventés."""
    projection, recherche = _projection(sources=[])
    assert "CE QUE TU PEUX AFFIRMER" not in projection
    assert "rien n'est vérifié" in projection


def test_sans_source_le_sujet_reste_present():
    """La production doit rester possible : ne rien savoir n'est pas ne rien
    pouvoir raconter."""
    projection, _ = _projection(sources=[])
    assert projection.strip(), "une projection vide bloquerait la production"


# ── La projection ne décide rien ────────────────────────────────────────

def test_la_projection_ne_change_pas_ce_qui_est_affirmable():
    """Changer la formulation ne change pas les droits ; seul un changement
    du ResearchState le peut."""
    topic = TopicRequest(sujet="x", profil=Profil.EXPLICATIF)
    recherche = construire("x", RechercheMock(SOURCES))
    etat = compiler(topic, recherche)
    assert set(etat.intention.points_a_porter) == {"claim_001", "claim_002"}


def test_sans_recherche_la_projection_reste_lisible():
    """`projeter_en_situation` doit fonctionner sans `ResearchState` — une
    fiction en passe par la même fonction."""
    topic = TopicRequest(sujet="x", profil=Profil.EXPLICATIF)
    projection = projeter_en_situation(compiler(topic, construire("x")))
    assert "Sujet" in projection or projection.strip() == "" or "Public" in projection


# ── La commande ─────────────────────────────────────────────────────────

def test_la_commande_existe_et_est_documentee():
    from typer.testing import CliRunner

    from pdz.cli import app

    resultat = CliRunner().invoke(app, ["creer", "--help"])
    assert resultat.exit_code == 0
    assert "--sujet" in resultat.stdout
    assert "--sources" in resultat.stdout


def test_un_fichier_de_sources_illisible_est_refuse_clairement(tmp_path):
    from typer.testing import CliRunner

    from pdz.cli import app

    mauvais = tmp_path / "sources.json"
    mauvais.write_text("{ceci n'est pas du json", encoding="utf-8")
    resultat = CliRunner().invoke(
        app, ["creer", "--sujet", "x", "--sources", str(mauvais)])
    assert resultat.exit_code == 1
    assert "illisible" in resultat.stdout


def test_un_fichier_de_sources_valide_est_relu(tmp_path):
    """Le format documenté dans l'aide doit être celui que le code accepte."""
    fichier = tmp_path / "sources.json"
    fichier.write_text(json.dumps(SOURCES, ensure_ascii=False), encoding="utf-8")
    backend = RechercheMock(json.loads(fichier.read_text(encoding="utf-8")))
    recherche = construire("moteur", backend)
    assert len(recherche.claims) == len(SOURCES)
    assert len(recherche.affirmables) == 2


# ── Les contrats voyagent avec la production ────────────────────────────

def test_produire_accepte_les_contrats_amont():
    """Sans eux, on ne saurait plus quelles sources ont autorisé quelle
    affirmation dans la vidéo livrée."""
    import inspect

    from pdz.production.episode import produire

    assert "contrats_amont" in inspect.signature(produire).parameters
