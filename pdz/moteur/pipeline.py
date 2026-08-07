"""Le moteur : enchaîne les étapes, sauvegarde après chacune, sait reprendre.

Principe central — le moteur ne mémorise jamais « où il en était ». À chaque
lancement il **relit** les étapes déjà terminées en base et en déduit ce qui
reste à faire. Conséquence : reprendre après un plantage, un redémarrage ou
trois jours d'interruption est exactement la même opération.

Voir docs/06-solidite.md § « Reprise après plantage ».
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

from pdz import db
from pdz.moteur.erreurs import ErreurBudget, ErreurPdz, delai_backoff

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
        if (cachee := _lire_cache(emp)) is not None:
            log.info("↩︎  %s : réutilisé depuis le cache", etape.cle)
            _ecrire_etape(ctx.job_id, etape, emp, cachee, cout=0.0,
                          duree_ms=0, statut="ignore_cache")
            return cachee, 0.0

        politique_tentatives = 3
        derniere: Exception | None = None

        for tentative in range(1, politique_tentatives + 1):
            debut = time.perf_counter()
            try:
                sortie = await agent.executer(entrees, ctx)
            except ErreurPdz as e:
                derniere = e
                pol = e.politique
                if not pol.reessayer or tentative >= min(pol.tentatives_max, politique_tentatives):
                    raise
                attente = getattr(e, "retry_after", None) or delai_backoff(tentative)
                log.warning(
                    "⟳  %s tentative %d/%d — %s — nouvelle tentative dans %.1fs",
                    etape.cle, tentative, pol.tentatives_max, e.categorie, attente,
                )
                time.sleep(attente)
                continue

            duree_ms = int((time.perf_counter() - debut) * 1000)
            _ecrire_etape(ctx.job_id, etape, emp, sortie, ctx.cout_engage, duree_ms)
            _ecrire_cache(emp, sortie, ctx.cout_engage)
            _ajouter_cout(ctx.job_id, ctx.cout_engage)
            log.info("✓  %s (%d ms, %.4f €)", etape.cle, duree_ms, ctx.cout_engage)
            return sortie, ctx.cout_engage

        raise derniere or ErreurPdz(f"Échec de l'étape {etape.cle}")

    def _etapes_terminees(self, conn, job_id: str) -> dict[str, Any]:
        lignes = conn.execute(
            "SELECT cle, resultat FROM etapes "
            "WHERE job_id = ? AND statut IN ('termine', 'ignore_cache')",
            (job_id,),
        ).fetchall()
        return {ligne["cle"]: db.charger(ligne["resultat"], {}) for ligne in lignes}

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
        with db.connexion() as conn:
            conn.execute(
                "UPDATE etapes SET resultat = ?, empreinte = NULL WHERE job_id = ? AND cle = ?",
                (db.vider(resultat), job_id, cle),
            )

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


# ── Accès base, isolés pour rester lisibles ───────────────────────────────

def _maj_statut(conn, job_id: str, statut: Statut) -> None:
    conn.execute(
        "UPDATE jobs SET statut = ?, maj_le = ? WHERE id = ?",
        (statut.value, db.maintenant(), job_id),
    )


def _entree_job(job_id: str) -> dict:
    with db.connexion() as conn:
        ligne = conn.execute("SELECT entree FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return db.charger(ligne["entree"], {}) if ligne else {}


def _ecrire_etape(job_id: str, etape: Etape, emp: str, resultat: dict,
                  cout: float, duree_ms: int, statut: str = "termine") -> None:
    """Écrit le point de reprise. C'est l'opération la plus importante du moteur."""
    with db.connexion() as conn:
        conn.execute(
            "INSERT INTO etapes "
            "(id, job_id, cle, agent, statut, empreinte, resultat, cout, duree_ms, cree_le, fini_le) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(job_id, cle) DO UPDATE SET "
            "  statut = excluded.statut, empreinte = excluded.empreinte, "
            "  resultat = excluded.resultat, cout = excluded.cout, "
            "  duree_ms = excluded.duree_ms, fini_le = excluded.fini_le, "
            "  tentative = etapes.tentative + 1",
            (db.nouvel_id("etp"), job_id, etape.cle, etape.agent, statut, emp,
             db.vider(resultat), cout, duree_ms, db.maintenant(), db.maintenant()),
        )


def _ajouter_cout(job_id: str, cout: float) -> None:
    if cout <= 0:
        return
    with db.connexion() as conn:
        conn.execute(
            "UPDATE jobs SET cout_total = cout_total + ?, maj_le = ? WHERE id = ?",
            (cout, db.maintenant(), job_id),
        )


def _lire_cache(emp: str) -> dict | None:
    with db.connexion() as conn:
        ligne = conn.execute(
            "SELECT valeur, expire_le FROM cache WHERE empreinte = ?", (emp,)
        ).fetchone()
        if ligne is None:
            return None
        if ligne["expire_le"] and ligne["expire_le"] < db.maintenant():
            conn.execute("DELETE FROM cache WHERE empreinte = ?", (emp,))
            return None
        return db.charger(ligne["valeur"])


def _ecrire_cache(emp: str, valeur: dict, cout_evite: float, ttl_s: int = 7 * 86400) -> None:
    with db.connexion() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO cache (empreinte, valeur, cout_evite, cree_le, expire_le) "
            "VALUES (?,?,?,?,?)",
            (emp, db.vider(valeur), cout_evite, db.maintenant(), db.maintenant() + ttl_s),
        )
