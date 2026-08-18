"""Le test le plus important du projet : la reprise après plantage.

Il vérifie qu'un job qui échoue à l'étape 3 repart à l'étape 3 — et pas
depuis le début. C'est ce qui évite de repayer les étapes déjà faites.
"""

import asyncio

import pytest

from pdz import db
from pdz.moteur import Etape, Moteur, Pipeline, Statut
from pdz.moteur.erreurs import ErreurQuota, ErreurReseau, ErreurValidation


class AgentFactice:
    def __init__(self, nom, compteur, doit_planter=None):
        self.nom, self.version = nom, "1.0.0"
        self.compteur = compteur
        self.doit_planter = doit_planter or (lambda: False)
        # Les `entrees` reçues à chaque appel — permet de vérifier que la
        # relance après ErreurValidation porte bien la correction promise.
        self.entrees_recues: list[dict] = []

    def signature(self):
        return {"agent": self.nom, "version": self.version, "modele": "factice"}

    async def executer(self, entrees, ctx):
        self.entrees_recues.append(entrees)
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


def test_une_relance_apres_erreur_de_validation_porte_la_correction(job):
    """La docstring d'ErreurValidation promet une relance qui montre son
    erreur au modèle. Mesuré en conditions réelles : ce n'était vrai nulle
    part — un script trop court restait trop court trois fois de suite
    avec Llama, faute de ce fil. Vérifié ici au niveau du moteur : le 2e
    appel doit recevoir `_erreur_precedente` avec le message exact du 1er
    échec (Agent.executer(), lui, se charge de l'ajouter au message envoyé
    au modèle — voir tests/test_ia_et_prompts.py)."""
    compteur = {}
    rate_une_fois = {"fait": False}

    class AgentValidationRatee(AgentFactice):
        async def executer(self, entrees, ctx):
            self.entrees_recues.append(entrees)
            self.compteur[self.nom] = self.compteur.get(self.nom, 0) + 1
            if not rate_une_fois["fait"]:
                rate_une_fois["fait"] = True
                raise ErreurValidation("Script trop court : ajoute 18 mots.")
            ctx.facturer(0.01)
            return {"fait": self.nom}

    agent = AgentValidationRatee("script", compteur)
    pipe = Pipeline("test", (Etape("etape_script", "script"),))
    r = asyncio.run(Moteur({"script": agent}).executer(job, pipe))

    assert r.statut is Statut.TERMINE
    assert len(agent.entrees_recues) == 2
    assert "_erreur_precedente" not in agent.entrees_recues[0]
    assert agent.entrees_recues[1]["_erreur_precedente"] == (
        "Script trop court : ajoute 18 mots."
    )


def test_une_relance_apres_erreur_reseau_ne_porte_aucune_correction(job):
    """Une panne réseau n'est pas de la faute du modèle : rien à lui
    montrer, contrairement à ErreurValidation ci-dessus."""
    compteur = {}
    rate_une_fois = {"fait": False}

    class AgentReseauRate(AgentFactice):
        async def executer(self, entrees, ctx):
            self.entrees_recues.append(entrees)
            self.compteur[self.nom] = self.compteur.get(self.nom, 0) + 1
            if not rate_une_fois["fait"]:
                rate_une_fois["fait"] = True
                raise ErreurReseau("panne simulée")
            ctx.facturer(0.01)
            return {"fait": self.nom}

    agent = AgentReseauRate("script", compteur)
    pipe = Pipeline("test", (Etape("etape_script", "script"),))
    r = asyncio.run(Moteur({"script": agent}).executer(job, pipe))

    assert r.statut is Statut.TERMINE
    assert len(agent.entrees_recues) == 2
    assert "_erreur_precedente" not in agent.entrees_recues[1]


def test_une_panne_transitoire_ne_grignote_pas_les_tentatives_de_correction(job):
    """Mesuré en conditions réelles : un 429 Groq — pas la faute du contenu
    — et deux « script trop long » consécutifs partageaient le même compteur
    de tentatives. Résultat vu à l'écran : la panne réseau mangeait une des
    3 chances, il n'en restait qu'une seule pour corriger le contenu, et le
    job entier échouait après une seule vraie tentative de correction. Le
    contenu doit avoir droit à ses 3 tentatives, quel que soit le nombre de
    pannes transitoires essuyées en chemin."""
    compteur = {}
    appels = {"n": 0}

    class AgentPanneEtContenuRates(AgentFactice):
        async def executer(self, entrees, ctx):
            self.entrees_recues.append(entrees)
            appels["n"] += 1
            self.compteur[self.nom] = self.compteur.get(self.nom, 0) + 1
            if appels["n"] == 1:
                raise ErreurQuota("429 simulé")
            if appels["n"] in (2, 3):
                raise ErreurValidation("Script trop long : resserre.")
            ctx.facturer(0.01)
            return {"fait": self.nom}

    agent = AgentPanneEtContenuRates("script", compteur)
    pipe = Pipeline("test", (Etape("etape_script", "script"),))
    r = asyncio.run(Moteur({"script": agent}).executer(job, pipe))

    assert r.statut is Statut.TERMINE
    # 1 panne transitoire + 2 tentatives de contenu ratées + 1 réussie :
    # sans la séparation des compteurs, le job aurait échoué au 3e appel.
    assert appels["n"] == 4


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


def test_une_relance_journalise_le_motif_pas_seulement_la_categorie(caplog):
    """Mesuré en production (run #70) : trois agents ont pris des « 400 Bad
    Request » de Groq, et le journal n'affichait que « ErreurValidation ».
    Impossible de savoir ce que Groq reprochait à la requête, alors que le
    fournisseur l'explique dans sa réponse — et que cette même explication
    était déjà renvoyée au modèle via `_erreur_precedente`. Le motif doit
    apparaître dans le journal de relance, pas seulement la classe."""
    import logging

    from pdz.moteur.pipeline import Contexte, executer_avec_relance

    detail = "Requête refusée par Groq (400). json_schema: unsupported keyword"
    essais = {"n": 0}

    class AgentQuiRateUneFois:
        nom = "agent_test"

        async def executer(self, entrees, ctx):
            essais["n"] += 1
            if essais["n"] == 1:
                raise ErreurValidation(detail)
            return {"ok": True}

    ctx = Contexte(job_id="j", etape_cle="e", profil="equilibre", budget_restant=1.0)
    with caplog.at_level(logging.WARNING):
        resultat = asyncio.run(executer_avec_relance(AgentQuiRateUneFois(), {}, ctx))

    assert resultat == {"ok": True}
    assert any("json_schema: unsupported keyword" in m for m in caplog.messages), \
        "le motif renvoyé par le fournisseur doit être journalisé"
    assert any("ErreurValidation" in m for m in caplog.messages), \
        "la catégorie reste utile, elle ne doit pas disparaître"


def test_le_delai_annonce_par_le_fournisseur_prime_sur_le_backoff(monkeypatch):
    """Mesuré en production (run #73) : un 400 rejoué 2,4 s plus tard prenait
    systématiquement un 429, parce que l'appel qui venait d'échouer avait déjà
    vidé la fenêtre de jetons. Quand le fournisseur dit combien de temps
    attendre — même sur une erreur de CONTENU — c'est lui qui a raison, pas le
    backoff générique."""
    from pdz.moteur.pipeline import Contexte, executer_avec_relance

    dormi = []

    async def faux_sleep(secondes):
        dormi.append(secondes)

    monkeypatch.setattr(asyncio, "sleep", faux_sleep)
    essais = {"n": 0}

    class AgentQuiRateUneFois:
        nom = "agent_test"

        async def executer(self, entrees, ctx):
            essais["n"] += 1
            if essais["n"] == 1:
                raise ErreurValidation("400 refusé", retry_after=59.5)
            return {"ok": True}

    ctx = Contexte(job_id="j", etape_cle="e", profil="equilibre", budget_restant=1.0)
    assert asyncio.run(executer_avec_relance(AgentQuiRateUneFois(), {}, ctx)) == {"ok": True}
    assert dormi == [59.5], "le backoff générique (~2 s) ne doit pas l'emporter"
