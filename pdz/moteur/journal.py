"""L'autorité unique sur la reprise, le journal et le cache.

Le dépôt en avait DEUX implémentations, et c'était son principal défaut
structurel :

  · `moteur/pipeline.py` — cache par empreinte, reprise, budget, validation ;
  · `production/episode.py` — sa propre reprise (`_fait`/`_noter`), écrivant
    dans la même table `etapes` sans jamais passer par `Moteur`.

Le second produit les vidéos. Autrement dit, le chemin réel de production
n'avait **aucun accès au cache du moteur**, et deux mécanismes de reprise
devaient rester d'accord pour toujours — ce qui n'arrive jamais.

Ce module est désormais le seul endroit qui sait lire et écrire un point de
reprise. `Moteur` et `episode` l'appellent tous les deux.

── Ce qu'`episode.py` savait faire de mieux, et qui monte ici ───────────

`_fait()` revérifiait que les FICHIERS cités par une étape terminée existent
encore. Une étape marquée faite dont le `.mp4` a été supprimé doit être
refaite, sinon le montage échoue trente secondes plus tard sur une erreur
incompréhensible. `Moteur` ne le faisait pas. C'est un acquis né d'un échec
réel : il devient la règle commune, pas une particularité de l'un des deux.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pdz import db

log = logging.getLogger(__name__)

# Les extensions qui désignent un fichier produit. Volontairement une liste
# fermée : tester `Path(x).exists()` sur toute chaîne contenant « / »
# ferait des accès disque sur des prompts, des URL et des identifiants.
EXTENSIONS_PRODUITES = (".mp3", ".mp4", ".jpg", ".jpeg", ".png", ".ass", ".wav", ".srt")

# Les statuts qui comptent comme « cette étape est faite ».
# `ignore_cache` en fait partie : une étape servie par le cache est terminée,
# elle n'a simplement rien coûté.
STATUTS_TERMINES = ("termine", "ignore_cache")


def fichiers_cites(valeur: Any) -> list[str]:
    """Tous les chemins de fichiers mentionnés dans un résultat d'étape.

    Descend récursivement : les résultats imbriquent listes et dicts, et un
    chemin oublié au troisième niveau produit exactement le bug que la
    revérification existe pour empêcher.
    """
    trouves: list[str] = []
    if isinstance(valeur, str):
        if "/" in valeur and Path(valeur).suffix.lower() in EXTENSIONS_PRODUITES:
            trouves.append(valeur)
    elif isinstance(valeur, dict):
        for v in valeur.values():
            trouves += fichiers_cites(v)
    elif isinstance(valeur, list):
        for v in valeur:
            trouves += fichiers_cites(v)
    return trouves


def etape_faite(job_id: str, cle: str) -> dict | None:
    """Le résultat d'une étape terminée, ou `None` s'il faut la refaire.

    `None` dans trois cas, tous des « à refaire » : l'étape n'a jamais
    tourné, son résultat est illisible, ou l'un des fichiers qu'elle cite a
    disparu. Le troisième est celui qui a coûté une production entière.
    """
    with db.connexion() as conn:
        ligne = conn.execute(
            f"SELECT resultat FROM etapes WHERE job_id = ? AND cle = ? "  # noqa: S608
            f"AND statut IN ({','.join('?' * len(STATUTS_TERMINES))})",
            (job_id, cle, *STATUTS_TERMINES),
        ).fetchone()

    if ligne is None:
        return None
    if (resultat := db.charger(ligne["resultat"], None)) is None:
        return None

    for chemin in fichiers_cites(resultat):
        if not Path(chemin).exists():
            log.info("Étape « %s » à refaire : %s a disparu", cle, chemin)
            return None
    return resultat


def etapes_faites(job_id: str) -> dict[str, Any]:
    """Toutes les étapes terminées d'un job, revérification comprise.

    Le moteur ne mémorise jamais « où il en était » : il relit ce qui est
    fait et en déduit ce qui reste. Reprendre après un plantage, un
    redémarrage ou trois jours est donc exactement la même opération.
    """
    with db.connexion() as conn:
        lignes = conn.execute(
            f"SELECT cle FROM etapes WHERE job_id = ? "  # noqa: S608
            f"AND statut IN ({','.join('?' * len(STATUTS_TERMINES))})",
            (job_id, *STATUTS_TERMINES),
        ).fetchall()

    faites: dict[str, Any] = {}
    for ligne in lignes:
        if (resultat := etape_faite(job_id, ligne["cle"])) is not None:
            faites[ligne["cle"]] = resultat
    return faites


def noter_etape(job_id: str, cle: str, agent: str, resultat: dict, *,
                cout: float = 0.0, duree_ms: int = 0, empreinte: str | None = None,
                statut: str = "termine") -> None:
    """Écrit le point de reprise.

    **L'opération la plus importante du système.** Tout le reste — reprise,
    coût, cache, journal — en découle. `tentative` s'incrémente sur conflit :
    c'est ce qui rend visible qu'une étape a été refaite, plutôt que de le
    masquer sous une simple mise à jour.
    """
    with db.connexion() as conn:
        conn.execute(
            "INSERT INTO etapes (id, job_id, cle, agent, statut, empreinte,"
            " resultat, cout, duree_ms, cree_le, fini_le)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(job_id, cle) DO UPDATE SET"
            "   statut = excluded.statut, empreinte = excluded.empreinte,"
            "   resultat = excluded.resultat, cout = excluded.cout,"
            "   duree_ms = excluded.duree_ms, fini_le = excluded.fini_le,"
            "   tentative = etapes.tentative + 1",
            (db.nouvel_id("etp"), job_id, cle, agent, statut, empreinte,
             db.vider(resultat), cout, duree_ms, db.maintenant(), db.maintenant()),
        )
        if cout > 0:
            conn.execute(
                "UPDATE jobs SET cout_total = cout_total + ?, maj_le = ? WHERE id = ?",
                (cout, db.maintenant(), job_id),
            )


def reecrire_etape(job_id: str, cle: str, resultat: dict) -> None:
    """Remplace le résultat d'une étape — après une correction humaine.

    L'empreinte est effacée : le contenu ne correspond plus à ce que
    l'agent avait produit, et le laisser servirait un jour ce résultat
    corrigé comme s'il venait du modèle.
    """
    with db.connexion() as conn:
        conn.execute(
            "UPDATE etapes SET resultat = ?, empreinte = NULL "
            "WHERE job_id = ? AND cle = ?",
            (db.vider(resultat), job_id, cle),
        )


# ── Le cache par empreinte : une seule implémentation ────────────────────
#
# Distinct de la reprise, et il faut les garder distincts :
#   · la REPRISE est par JOB — « cette étape de CE job est déjà faite » ;
#   · le CACHE est par EMPREINTE — « ce calcul exact a déjà été fait, par
#     n'importe quel job ».
# Les confondre ferait resservir à un job les fichiers d'un autre.

def lire_cache(empreinte: str) -> dict | None:
    """Le résultat mis en cache pour cette empreinte, s'il est encore valide.

    Une entrée dont les fichiers ont disparu est REJETÉE et supprimée : la
    servir ferait échouer le montage plus tard, avec une erreur qui ne
    ressemblerait plus du tout à sa cause. Même règle que pour la reprise,
    et c'est bien le même acquis.
    """
    with db.connexion() as conn:
        ligne = conn.execute(
            "SELECT valeur, expire_le FROM cache WHERE empreinte = ?", (empreinte,)
        ).fetchone()
        if ligne is None:
            return None
        if ligne["expire_le"] and ligne["expire_le"] < db.maintenant():
            conn.execute("DELETE FROM cache WHERE empreinte = ?", (empreinte,))
            return None
        valeur = db.charger(ligne["valeur"])

    if valeur is not None:
        for chemin in fichiers_cites(valeur):
            if not Path(chemin).exists():
                log.info("Cache %s ignoré : %s a disparu", empreinte[:12], chemin)
                with db.connexion() as conn:
                    conn.execute("DELETE FROM cache WHERE empreinte = ?", (empreinte,))
                return None
    return valeur


def ecrire_cache(empreinte: str, valeur: dict, cout_evite: float,
                 ttl_s: int = 7 * 86400) -> None:
    with db.connexion() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO cache (empreinte, valeur, cout_evite, cree_le, expire_le)"
            " VALUES (?,?,?,?,?)",
            (empreinte, db.vider(valeur), cout_evite,
             db.maintenant(), db.maintenant() + ttl_s),
        )
