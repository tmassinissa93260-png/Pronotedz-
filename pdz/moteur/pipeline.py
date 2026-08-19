"""Le moteur : enchaîne les étapes, sauvegarde après chacune, sait reprendre.

Principe central — le moteur ne mémorise jamais « où il en était ». À chaque
lancement il **relit** les étapes déjà terminées en base et en déduit ce qui
reste à faire. Conséquence : reprendre après un plantage, un redémarrage ou
trois jours d'interruption est exactement la même opération.

Voir docs/06-solidite.md § « Reprise après plantage ».
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

from pdz import db
from pdz.moteur import journal
from pdz.moteur.erreurs import ErreurBudget, ErreurPdz, ErreurValidation, delai_backoff

log = logging.getLogger(__name__)


class Statut(str, Enum):
    EN_ATTENTE = "en_attente"
    EN_COURS = "en_cours"
    ATTENTE_VALIDATION = "attente_validation"
    TERMINE = "termine"
    ECHOUE = "echoue"
    ANNULE = "annule"


@dataclass(frozen=True)
class Etape:
    """Une étape du pipeline.

    `validation` : si renseigné, le moteur s'arrête **après** cette étape et
    attend une décision humaine avant de continuer.
    """

    cle: str
    agent: str
    depend_de: tuple[str, ...] = ()
    validation: str | None = None
    optionnelle: bool = False


@dataclass(frozen=True)
class Pipeline:
    nom: str
    etapes: tuple[Etape, ...]

    def etape(self, cle: str) -> Etape | None:
        return next((e for e in self.etapes if e.cle == cle), None)


class Agent(Protocol):
    """Contrat minimal d'un agent. Voir docs/05-les-agents.md."""

    nom: str
    version: str

    def signature(self) -> dict[str, str]:
        """Ce qui identifie l'agent dans l'empreinte de cache
        (version d'agent, version de prompt, modèle)."""
        ...

    async def executer(self, entrees: dict[str, Any], ctx: Contexte) -> dict[str, Any]:
        ...


@dataclass
class Contexte:
    """Passé à chaque agent : qui l'appelle, avec quel budget, et où écrire."""

    job_id: str
    etape_cle: str
    profil: str
    budget_restant: float
    resultats: dict[str, Any] = field(default_factory=dict)
    cout_engage: float = 0.0

    def facturer(self, montant: float) -> None:
        self.cout_engage += montant
        self.budget_restant -= montant


async def executer_avec_relance(agent: Agent, entrees: dict[str, Any], ctx: Contexte,
                                *, max_tentatives: int = 3) -> dict[str, Any]:
    """Appelle un agent, en relançant selon la politique de l'erreur —
    en montrant l'erreur au modèle sur une ErreurValidation, voir
    Agent.executer() côté lecture de `_erreur_precedente`.

    Mesuré à l'écran : `Moteur._executer_etape()` a longtemps été le SEUL
    endroit à relancer, mais `pdz episode`, `pdz charte`, `pdz references`
    et `pdz avant-apres` appellent tous leurs agents directement, sans
    jamais passer par `Moteur`. Un `await agent.executer(...)` nu ne
    relance jamais rien — c'est cette fonction qu'il faut appeler à la
    place, partout où un agent est invoqué.

    Deux compteurs séparés, pas un seul : les ratés TRANSITOIRES (réseau,
    quota, fournisseur — jamais la faute du contenu produit) et les vraies
    tentatives de CONTENU (ErreurValidation, où le modèle voit son erreur
    et a une vraie chance de la corriger). Les compter ensemble faisait
    qu'un simple 429 mangeait une des `max_tentatives` chances de corriger
    un script — mesuré en conditions réelles : script trop long, tentative
    1 déjà ratée sur le contenu, tentative 2 perdue sur un 429 Groq sans
    lien avec le script, tentative 3 encore trop longue → plus aucune
    tentative de correction, l'épisode entier a échoué alors que le
    contenu n'avait eu qu'un seul vrai essai de correction, pas trois.
    """
    derniere: ErreurPdz | None = None
    tentative_contenu = 0
    tentative_transitoire = 0
    while True:
        try:
            return await agent.executer(entrees, ctx)
        except ErreurPdz as e:
            derniere = e
            pol = e.politique
            if isinstance(e, ErreurValidation):
                tentative_contenu += 1
                plafond = min(pol.tentatives_max, max_tentatives)
                tentative, epuise = tentative_contenu, tentative_contenu >= plafond
            else:
                tentative_transitoire += 1
                plafond = pol.tentatives_max
                tentative, epuise = tentative_transitoire, tentative_transitoire >= plafond

            if not pol.reessayer or epuise:
                raise

            attente = getattr(e, "retry_after", None) or delai_backoff(tentative)
            # Le MOTIF, pas seulement la catégorie. Mesuré en production
            # (run #70) : trois agents ont pris des « 400 Bad Request » de
            # Groq, et le journal n'affichait que « ErreurValidation » —
            # impossible de savoir ce que Groq reprochait à la requête,
            # alors que le fournisseur l'explique dans sa réponse et que
            # `_erreur_precedente` la renvoie déjà au modèle juste en
            # dessous. Tronqué : un détail de fournisseur peut être long,
            # et le message complet reste dans l'erreur finale.
            motif = str(e).replace("\n", " ")
            log.warning(
                "⟳  %s tentative %d/%d — %s : %s — nouvelle tentative dans %.1fs",
                agent.nom, tentative, plafond, e.categorie, motif[:200], attente,
            )
            await asyncio.sleep(attente)
            if isinstance(e, ErreurValidation):
                entrees = {**entrees, "_erreur_precedente": str(e)}
    raise derniere or ErreurPdz(f"Échec de l'agent « {agent.nom} »")


@dataclass
class Resultat:
    statut: Statut
    job_id: str
    etapes_faites: list[str] = field(default_factory=list)
    etapes_sautees: list[str] = field(default_factory=list)
    validation_en_attente: str | None = None
    erreur: str | None = None
    cout: float = 0.0


def empreinte(entrees: dict[str, Any], signature: dict[str, str]) -> str:
    """sha256(entrées normalisées + versions).

    La normalisation est ce qui fait vivre ou mourir le cache : sans tri des
    clés ni exclusion des champs volatils, deux appels identiques produisent
    deux empreintes différentes et le taux de réutilisation tombe à zéro.
    """
    volatils = {"cree_le", "maj_le", "job_id", "request_id", "duree_ms", "timestamp"}
    propre = {k: v for k, v in sorted(entrees.items()) if k not in volatils}
    brut = json.dumps(
        {"entrees": propre, "signature": dict(sorted(signature.items()))},
        ensure_ascii=False, sort_keys=True, default=str,
    )
    return hashlib.sha256(brut.encode("utf-8")).hexdigest()


class Moteur:
    def __init__(self, agents: dict[str, Agent]):
        self.agents = agents

    # ── API publique ──────────────────────────────────────────────────────

    async def executer(self, job_id: str, pipeline: Pipeline) -> Resultat:
        """Fait avancer le job aussi loin que possible.

        S'arrête proprement sur : validation en attente, budget épuisé, échec.
        Relancer la même commande reprend là où ça s'était arrêté.
        """
        res = Resultat(statut=Statut.EN_COURS, job_id=job_id)

        with db.connexion() as conn:
            job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if job is None:
                raise ErreurPdz(f"Job introuvable : {job_id}")
            if job["statut"] in (Statut.TERMINE, Statut.ANNULE):
                return Resultat(statut=Statut(job["statut"]), job_id=job_id)
            faites = self._etapes_terminees(conn, job_id)
            _maj_statut(conn, job_id, Statut.EN_COURS)

        contexte_resultats: dict[str, Any] = dict(faites)
        cout_total = float(job["cout_total"])
        budget_max = float(job["budget_max"])

        for etape in pipeline.etapes:
            # 1. Déjà faite ? On saute — sans rien repayer.
            if etape.cle in faites:
                res.etapes_sautees.append(etape.cle)
            else:
                if cout_total >= budget_max:
                    return self._arreter(
                        res, job_id, Statut.ECHOUE,
                        f"Budget épuisé : {cout_total:.3f} € sur {budget_max:.2f} € "
                        f"avant l'étape « {etape.cle} »",
                    )

                ctx = Contexte(
                    job_id=job_id,
                    etape_cle=etape.cle,
                    profil=job["profil"],
                    budget_restant=budget_max - cout_total,
                    resultats=contexte_resultats,
                )
                try:
                    sortie, cout = await self._executer_etape(etape, ctx)
                except ErreurBudget as e:
                    return self._arreter(res, job_id, Statut.ECHOUE, str(e))
                except ErreurPdz as e:
                    if etape.optionnelle:
                        log.warning("Étape optionnelle « %s » ignorée : %s", etape.cle, e)
                        sortie, cout = {}, 0.0
                    else:
                        return self._arreter(
                            res, job_id, Statut.ECHOUE,
                            f"[{e.categorie}] {etape.cle} : {e}",
                        )

                contexte_resultats[etape.cle] = sortie
                cout_total += cout
                res.etapes_faites.append(etape.cle)
                res.cout += cout

            # 2. Cette étape demande-t-elle mon avis ?
            if etape.validation:
                decision = self._verifier_validation(
                    job_id, etape, contexte_resultats.get(etape.cle, {})
                )
                if decision == "en_attente":
                    with db.connexion() as conn:
                        _maj_statut(conn, job_id, Statut.ATTENTE_VALIDATION)
                    res.statut = Statut.ATTENTE_VALIDATION
                    res.validation_en_attente = etape.validation
                    return res
                if decision == "rejete":
                    return self._arreter(res, job_id, Statut.ANNULE, "Rejeté à la validation")
                if isinstance(decision, dict):  # édité par l'utilisateur
                    contexte_resultats[etape.cle] = decision
                    self._reecrire_etape(job_id, etape.cle, decision)

        with db.connexion() as conn:
            _maj_statut(conn, job_id, Statut.TERMINE)
        res.statut = Statut.TERMINE
        return res

    # ── Interne ───────────────────────────────────────────────────────────

    async def _executer_etape(self, etape: Etape, ctx: Contexte) -> tuple[dict, float]:
        agent = self.agents.get(etape.agent)
        if agent is None:
            raise ErreurPdz(f"Agent inconnu : « {etape.agent} » (étape {etape.cle})")

        entrees = {cle: ctx.resultats.get(cle) for cle in etape.depend_de}
        entrees["_job"] = _entree_job(ctx.job_id)
        emp = empreinte(entrees, agent.signature())

        # Cache : même entrée + même version d'agent + même modèle → gratuit.
        if (cachee := journal.lire_cache(emp)) is not None:
            log.info("↩︎  %s : réutilisé depuis le cache", etape.cle)
            journal.noter_etape(ctx.job_id, etape.cle, etape.agent, cachee,
                                cout=0.0, duree_ms=0, empreinte=emp,
                                statut="ignore_cache")
            return cachee, 0.0

        debut = time.perf_counter()
        sortie = await executer_avec_relance(agent, entrees, ctx)
        duree_ms = int((time.perf_counter() - debut) * 1000)
        journal.noter_etape(ctx.job_id, etape.cle, etape.agent, sortie,
                            cout=ctx.cout_engage, duree_ms=duree_ms, empreinte=emp)
        journal.ecrire_cache(emp, sortie, ctx.cout_engage)
        log.info("✓  %s (%d ms, %.4f €)", etape.cle, duree_ms, ctx.cout_engage)
        return sortie, ctx.cout_engage

    def _etapes_terminees(self, conn, job_id: str) -> dict[str, Any]:
        """Délègue au journal — qui revérifie aussi que les fichiers cités
        existent encore. Le moteur ne le faisait pas ; c'est l'acquis
        d'`episode.py`, désormais commun aux deux."""
        return journal.etapes_faites(job_id)

    def _verifier_validation(self, job_id: str, etape: Etape, contenu: dict):
        """Crée la validation si elle n'existe pas, sinon lit la décision."""
        with db.connexion() as conn:
            ligne = conn.execute(
                "SELECT * FROM validations WHERE job_id = ? AND etape_cle = ?",
                (job_id, etape.cle),
            ).fetchone()

            if ligne is None:
                conn.execute(
                    "INSERT INTO validations "
                    "(id, job_id, etape_cle, type, statut, contenu, cree_le) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (db.nouvel_id("val"), job_id, etape.cle, etape.validation,
                     "en_attente", db.vider(contenu), db.maintenant()),
                )
                return "en_attente"

            if ligne["statut"] == "en_attente":
                return "en_attente"
            if ligne["statut"] == "rejete":
                return "rejete"
            if ligne["statut"] == "edite" and ligne["edits"]:
                return db.charger(ligne["edits"], contenu)
            return "approuve"

    def _reecrire_etape(self, job_id: str, cle: str, resultat: dict) -> None:
        journal.reecrire_etape(job_id, cle, resultat)

    def _arreter(self, res: Resultat, job_id: str, statut: Statut, message: str) -> Resultat:
        log.error("✗  %s : %s", job_id, message)
        with db.connexion() as conn:
            conn.execute(
                "UPDATE jobs SET statut = ?, erreur = ?, maj_le = ? WHERE id = ?",
                (statut.value, message, db.maintenant(), job_id),
            )
        res.statut = statut
        res.erreur = message
        return res


# ── Accès base ───────────────────────────────────────────────────────────
#
# La lecture, l'écriture et le cache des étapes vivent dans
# `pdz/moteur/journal.py` — la SEULE autorité, partagée avec
# `production/episode.py`. Ce qui reste ici est propre au moteur : le statut
# du job et la lecture de son entrée.

def _maj_statut(conn, job_id: str, statut: Statut) -> None:
    conn.execute(
        "UPDATE jobs SET statut = ?, maj_le = ? WHERE id = ?",
        (statut.value, db.maintenant(), job_id),
    )


def _entree_job(job_id: str) -> dict:
    with db.connexion() as conn:
        ligne = conn.execute("SELECT entree FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return db.charger(ligne["entree"], {}) if ligne else {}
