"""Le test le plus important du projet : la reprise après plantage.

Il vérifie qu'un job qui échoue à l'étape 3 repart à l'étape 3 — et pas
depuis le début. C'est ce qui évite de repayer les étapes déjà faites.
"""

import asyncio

import pytest

from pdz import db
from pdz.moteur import Etape, Moteur, Pipeline, Statut
from pdz.moteur.erreurs import ErreurReseau


class AgentFactice:
    def __init__(self, nom, compteur, doit_planter=None):
        self.nom, self.version = nom, "1.0.0"
        self.compteur = compteur
        self.doit_planter = doit_planter or (lambda: False)

    def signature(self):
        return {"agent": self.nom, "version": self.version, "modele": "factice"}

    async def executer(self, entrees, ctx):
        self.compteur[self.nom] = self.compteur.get(self.nom, 0) + 1
        if self.doit_planter():
            raise ErreurReseau("panne simulée")
        ctx.facturer(0.01)
        # Le numéro d'appel rend chaque sortie unique : sans ça, les étapes
        # chaînées auraient des entrées identiques et le cache les servirait
        # toutes gratuitement (cf. test_le_cache_evite_de_repayer).
        return {"fait": self.nom, "n": self.compteur[self.nom]}


@pytest.fixture
def job(tmp_path, monkeypatch):
    monkeypatch.setenv("DONNEES", str(tmp_path))
    from pdz.config import config
    config.cache_clear()
    with db.connexion() as conn:
        conn.execute(
            "INSERT INTO jobs (id,type,statut,entree,profil,budget_max,cree_le,maj_le)"
            " VALUES (?,?,?,?,?,?,?,?)",
            ("job_t", "video_depuis_idee", "en_attente", '{"idee":"x"}',
             "equilibre", 0.60, db.maintenant(), db.maintenant()),
        )
    return "job_t"


def test_reprise_sans_rejouer_les_etapes_faites(job):
    compteur, plante = {}, {"oui": True}
    agents = {
        "a": AgentFactice("a", compteur),
        "b": AgentFactice("b", compteur),
        "c": AgentFactice("c", compteur, lambda: plante["oui"]),
    }
    pipe = Pipeline("test", (
        Etape("etape_a", "a"),
        Etape("etape_b", "b", depend_de=("etape_a",), validation="script"),
        Etape("etape_c", "c", depend_de=("etape_b",)),
    ))
    moteur = Moteur(agents)

    # 1. S'arrête au point de validation.
    r = asyncio.run(moteur.executer(job, pipe))
    assert r.statut is Statut.ATTENTE_VALIDATION
    assert r.etapes_faites == ["etape_a", "etape_b"]

    with db.connexion() as conn:
        conn.execute("UPDATE validations SET statut='approuve' WHERE job_id=?", (job,))

    # 2. Échoue à l'étape c, sans rejouer a et b.
    r = asyncio.run(moteur.executer(job, pipe))
    assert r.statut is Statut.ECHOUE
    assert r.etapes_sautees == ["etape_a", "etape_b"]
    assert compteur["a"] == 1

    # 3. Une fois la panne corrigée, reprend exactement à l'étape c.
    plante["oui"] = False
    r = asyncio.run(moteur.executer(job, pipe))
    assert r.statut is Statut.TERMINE
    assert r.etapes_faites == ["etape_c"]
    assert compteur["a"] == 1 and compteur["b"] == 1


def test_le_budget_arrete_le_job(job):
    """Le garde-fou qui évite qu'une boucle vide le budget d'un mois."""
    compteur = {}
    agents = {"cher": AgentFactice("cher", compteur)}
    # Étapes chaînées : chaque entrée diffère de la précédente, donc aucune
    # ne peut être servie par le cache. Chacune coûte réellement 0,01 €.
    pipe = Pipeline("cher", tuple(
        Etape(f"e{i}", "cher", depend_de=((f"e{i - 1}",) if i else ()))
        for i in range(200)
    ))
    r = asyncio.run(Moteur(agents).executer(job, pipe))

    assert r.statut is Statut.ECHOUE
    assert "Budget" in (r.erreur or "")
    # Plafond 0,60 € à 0,01 €/étape → on s'arrête vers la 60e, pas la 200e.
    assert 55 <= compteur["cher"] <= 65, compteur


def test_le_cache_evite_de_repayer(job):
    """Deux étapes identiques ne sont facturées qu'une fois."""
    compteur = {}
    agents = {"stable": AgentFactice("stable", compteur)}
    # Aucune dépendance → entrées identiques → même empreinte.
    pipe = Pipeline("doublons", tuple(Etape(f"e{i}", "stable") for i in range(5)))

    r = asyncio.run(Moteur(agents).executer(job, pipe))

    assert r.statut is Statut.TERMINE
    assert compteur["stable"] == 1, "l'agent ne doit être appelé qu'une seule fois"
    assert r.cout == 0.01, "les 4 réutilisations sont gratuites"
