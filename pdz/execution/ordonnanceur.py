"""L'ordonnanceur : des vagues de nœuds, exécutées en parallèle.

── Pourquoi maison, et pas Temporal / Prefect / Airflow ─────────────────

Vingt à quarante nœuds par job, sur une machine, avec la table `etapes`
comme journal de reprise déjà en place. Ces outils apporteraient un serveur,
une base et un modèle de déploiement pour un gain nul ici. Voir
docs/TARGET_ARCHITECTURE.md § 6 — chaque dépendance doit avoir une
justification, et celle-ci n'en a pas.

── L'ordre des vérifications, avant d'exécuter un nœud ──────────────────

    1. déjà fait dans CE job ?      → reprise, gratuite
    2. déjà calculé AILLEURS ?      → cache par empreinte, gratuit
    3. sinon                        → exécution, payante

Les deux premières viennent du journal, seule autorité. Les inverser ferait
préférer un résultat d'un autre job à celui de celui-ci, ce qui n'a aucun
sens : la reprise est plus spécifique que le cache.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from pdz.contracts.execution import ExecutionPlan, NoeudExecution, StatutNoeud
from pdz.moteur import journal
from pdz.moteur.erreurs import ErreurPdz, delai_backoff

log = logging.getLogger(__name__)

# Une opération reçoit le nœud et les sorties de ses dépendances, et rend un
# résultat sérialisable. Volontairement asynchrone : les nœuds coûteux
# attendent le réseau, et c'est là que la parallélisation paie.
Operation = Callable[[NoeudExecution, dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass
class ResultatExecution:
    """Ce que l'exécution d'un plan a produit — et ce qu'elle a évité."""

    plan: ExecutionPlan
    sorties: dict[str, Any] = field(default_factory=dict)
    cout_eur: float = 0.0
    # Ce que la reprise et le cache ont fait économiser. Distinct du coût
    # dépensé : sans lui, on ne sait pas si le cache sert à quelque chose.
    cout_evite_eur: float = 0.0
    reutilises: list[str] = field(default_factory=list)
    echoues: list[str] = field(default_factory=list)

    @property
    def complet(self) -> bool:
        return not self.echoues


class Ordonnanceur:
    """Exécute un `ExecutionPlan`, vague par vague.

    `job_id` sert au journal : sans lui, aucune reprise n'est possible et
    chaque relance repaie tout. C'est un paramètre obligatoire, pas une
    option — le rendre facultatif inviterait à l'oublier.
    """

    def __init__(self, operations: dict[str, Operation], *, job_id: str,
                 parallelisme_max: int = 4):
        self.operations = operations
        self.job_id = job_id
        # Un plafond, parce que dix appels vidéo simultanés chez le même
        # fournisseur se font limiter — et qu'une machine locale qui lance
        # dix ffmpeg d'un coup ne va pas plus vite.
        self.semaphore = asyncio.Semaphore(parallelisme_max)

    async def executer(self, plan: ExecutionPlan) -> ResultatExecution:
        resultat = ResultatExecution(plan=plan)
        etats: dict[str, NoeudExecution] = {n.noeud_id: n for n in plan.noeuds}

        for vague in plan.ordonnancer():
            # Une vague dont toutes les dépendances ont échoué n'a rien à
            # faire : on la saute plutôt que de la lancer pour la voir
            # échouer sur des entrées manquantes.
            executables = [n for n in vague
                           if not self._dependance_echouee(etats[n], resultat)]
            for saute in set(vague) - set(executables):
                etats[saute] = etats[saute].model_copy(
                    update={"statut": StatutNoeud.IGNORE,
                            "erreur": "dépendance en échec"})
                resultat.echoues.append(saute)

            if not executables:
                continue

            sorties = await asyncio.gather(*(
                self._noeud(etats[n], resultat) for n in executables
            ), return_exceptions=False)

            for noeud_id, noeud in zip(executables, sorties, strict=True):
                etats[noeud_id] = noeud

        resultat.plan = plan.model_copy(update={
            "noeuds": tuple(etats[n.noeud_id] for n in plan.noeuds)})
        log.info(
            "DAG terminé : %d nœud(s), %d réutilisé(s), %d échec(s), "
            "%.4f € dépensés (%.4f € évités)",
            len(plan.noeuds), len(resultat.reutilises), len(resultat.echoues),
            resultat.cout_eur, resultat.cout_evite_eur,
        )
        return resultat

    # ── Un nœud ─────────────────────────────────────────────────────────

    async def _noeud(self, noeud: NoeudExecution,
                     resultat: ResultatExecution) -> NoeudExecution:
        cle = f"{noeud.noeud_id}"

        # 1. Déjà fait dans CE job ? Le journal revérifie aussi que les
        #    fichiers cités existent encore.
        if (fait := journal.etape_faite(self.job_id, cle)) is not None:
            log.info("↩︎  %s : déjà fait", noeud.noeud_id)
            resultat.sorties[noeud.noeud_id] = fait
            resultat.reutilises.append(noeud.noeud_id)
            resultat.cout_evite_eur += noeud.cout_estime_eur
            return noeud.model_copy(update={"statut": StatutNoeud.REUTILISE})

        # 2. Déjà calculé ailleurs ?
        if noeud.cle_cache and (cachee := journal.lire_cache(noeud.cle_cache)) is not None:
            log.info("↩︎  %s : réutilisé depuis le cache", noeud.noeud_id)
            journal.noter_etape(self.job_id, cle, noeud.operation, cachee,
                                empreinte=noeud.cle_cache, statut="ignore_cache")
            resultat.sorties[noeud.noeud_id] = cachee
            resultat.reutilises.append(noeud.noeud_id)
            resultat.cout_evite_eur += noeud.cout_estime_eur
            return noeud.model_copy(update={"statut": StatutNoeud.REUTILISE})

        # 3. Exécuter.
        operation = self.operations.get(noeud.operation)
        if operation is None:
            return self._echec(noeud, resultat,
                               f"opération inconnue : « {noeud.operation} »")

        entrees = {d: resultat.sorties.get(d) for d in noeud.depend_de}
        return await self._tenter(noeud, operation, entrees, resultat, cle)

    async def _tenter(self, noeud: NoeudExecution, operation: Operation,
                      entrees: dict[str, Any], resultat: ResultatExecution,
                      cle: str) -> NoeudExecution:
        """Exécute avec les relances propres à CE nœud.

        `tentatives_max` vit sur le nœud et non sur l'ordonnanceur : une
        carte de profondeur locale et un appel vidéo en file d'attente
        n'appellent pas la même politique.
        """
        derniere: Exception | None = None

        for tentative in range(1, max(1, noeud.tentatives_max) + 1):
            debut = time.perf_counter()
            try:
                async with self.semaphore:
                    sortie = await operation(noeud, entrees)
            except ErreurPdz as e:
                derniere = e
                if not e.politique.reessayer or tentative >= noeud.tentatives_max:
                    break
                attente = getattr(e, "retry_after", None) or delai_backoff(tentative)
                log.warning("⟳  %s tentative %d/%d — %s : %s",
                            noeud.noeud_id, tentative, noeud.tentatives_max,
                            e.categorie, str(e)[:160])
                await asyncio.sleep(attente)
                continue

            duree_ms = int((time.perf_counter() - debut) * 1000)
            cout = float(sortie.get("cout_eur", 0.0) or 0.0)

            journal.noter_etape(self.job_id, cle, noeud.operation, sortie,
                                cout=cout, duree_ms=duree_ms,
                                empreinte=noeud.cle_cache or None)
            if noeud.cle_cache:
                journal.ecrire_cache(noeud.cle_cache, sortie, cout)

            resultat.sorties[noeud.noeud_id] = sortie
            resultat.cout_eur += cout
            log.info("✓  %s (%d ms, %.4f €)", noeud.noeud_id, duree_ms, cout)
            return noeud.model_copy(update={
                "statut": StatutNoeud.TERMINE, "sortie": str(sortie.get("fichier", "")),
                "cout_reel_eur": cout, "duree_reelle_ms": duree_ms,
                "tentative": tentative,
            })

        return self._echec(noeud, resultat, str(derniere or "échec sans cause"))

    def _echec(self, noeud: NoeudExecution, resultat: ResultatExecution,
               message: str) -> NoeudExecution:
        """Un nœud en échec n'arrête PAS le DAG.

        Les branches indépendantes continuent ; seules celles qui en
        dépendent sont ignorées. Tout arrêter perdrait le travail déjà payé
        des autres branches de la même vague.
        """
        log.error("✗  %s : %s", noeud.noeud_id, message)
        resultat.echoues.append(noeud.noeud_id)
        return noeud.model_copy(update={"statut": StatutNoeud.ECHOUE,
                                        "erreur": message})

    @staticmethod
    def _dependance_echouee(noeud: NoeudExecution,
                            resultat: ResultatExecution) -> bool:
        return any(d in resultat.echoues for d in noeud.depend_de)


async def executer(plan: ExecutionPlan, operations: dict[str, Operation], *,
                   job_id: str, parallelisme_max: int = 4) -> ResultatExecution:
    """Raccourci pour le cas courant."""
    return await Ordonnanceur(operations, job_id=job_id,
                              parallelisme_max=parallelisme_max).executer(plan)
