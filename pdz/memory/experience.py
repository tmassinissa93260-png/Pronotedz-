"""La mémoire d'expérience : ce que chaque tentative a réellement donné.

**Le composant dont le retard coûte le plus cher.** Tant que ces lignes ne
sont pas écrites, aucun routage empirique n'est possible — pas parce que
l'algorithme manque, mais parce que la donnée n'existe pas. Chaque production
faite sans enregistrer son expérience est une observation perdue pour
toujours.

D'où l'ordre imposé, et qu'il ne faut pas inverser :

    collecter → stocker → requêter → analyser → (un jour) router

Ce module fait les quatre premiers. **Il ne route rien.** Construire un
routeur avant d'avoir les données produirait un modèle entraîné sur rien,
avec l'assurance d'un modèle entraîné sur beaucoup.

── Une seule base, un seul cache, une seule reprise ─────────────────────

Écrit dans la table `experiences` de `pdz/db.py` — la base du projet, pas
une seconde. L'architecture interdit explicitement de dupliquer la
persistance, et une mémoire qui vivrait à part serait la première à diverger.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass

from pdz import db
from pdz.contracts.experience import ExperienceRecord

log = logging.getLogger(__name__)

# En dessous, une moyenne ne mesure que le hasard. Le seuil ne bloque rien :
# il décide seulement si une statistique a le droit de se présenter comme
# telle — voir `Performance.significative`.
ECHANTILLON_MINIMAL = 5


@dataclass(frozen=True)
class Performance:
    """Ce qu'on sait d'une stratégie ou d'un modèle, avec sa taille d'échantillon.

    `echantillon` n'est pas décoratif : une réussite sur une tentative et
    quarante sur quarante donnent le même taux, et l'une ne vaut rien.
    Séparer les deux est ce qui empêche de router sur du bruit.
    """

    cle: str
    echantillon: int
    reussites: int
    echecs: int
    incertains: int
    cout_total_eur: float
    latence_moyenne_ms: float

    @property
    def taux_de_reussite(self) -> float | None:
        """`None` quand rien n'a été observé — jamais `0.0`.

        Un taux de zéro dit « ça a échoué à chaque fois » ; l'absence de
        donnée dit « on n'a jamais essayé ». Les confondre ferait éliminer
        pour toujours une stratégie qu'on n'a jamais tentée.
        """
        return self.reussites / self.echantillon if self.echantillon else None

    @property
    def cout_par_reussite_eur(self) -> float | None:
        return self.cout_total_eur / self.reussites if self.reussites else None

    @property
    def significative(self) -> bool:
        return self.echantillon >= ECHANTILLON_MINIMAL


class ExperienceMemory:
    """Écrit et relit les tentatives. Ne décide rien."""

    def enregistrer(self, record: ExperienceRecord) -> str:
        """Consigne une tentative. Idempotent sur (job, plan, tentative).

        L'unicité porte sur le triplet et non sur un identifiant tiré au
        hasard : reprendre un job ne doit pas dupliquer ses expériences, ce
        qui gonflerait les échantillons sans qu'aucune tentative de plus
        n'ait eu lieu.
        """
        identifiant = record.id or self._identifiant(record)
        with db.connexion() as conn:
            conn.execute(
                "INSERT INTO experiences (id, job_id, shot_id, tentative, strategie,"
                " backend, modele, fournisseur, signature_entrees, cout_estime,"
                " cout_reel, latence_ms, diagnostic, reparation, resultat, qualite,"
                " certitude, verifie_humain, contrat, cree_le)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(id) DO UPDATE SET"
                "   resultat = excluded.resultat, cout_reel = excluded.cout_reel,"
                "   latence_ms = excluded.latence_ms, diagnostic = excluded.diagnostic,"
                "   reparation = excluded.reparation, qualite = excluded.qualite,"
                "   certitude = excluded.certitude,"
                "   verifie_humain = excluded.verifie_humain,"
                "   contrat = excluded.contrat",
                (
                    identifiant, record.job_id, record.shot_id, record.tentative,
                    record.strategie.value if record.strategie else None,
                    record.backend or None, record.modele or None,
                    record.fournisseur or None, record.signature_entrees or None,
                    record.cout_estime_eur, record.cout_reel_eur, record.latence_ms,
                    record.diagnostic.value if record.diagnostic else None,
                    record.reparation.value if record.reparation else None,
                    record.resultat or None, record.qualite,
                    record.certitude.value, int(record.verifie_humain),
                    record.en_json(), db.maintenant(),
                ),
            )
        return identifiant

    def lire(self, identifiant: str) -> ExperienceRecord | None:
        with db.connexion() as conn:
            ligne = conn.execute(
                "SELECT contrat FROM experiences WHERE id = ?", (identifiant,)
            ).fetchone()
        return ExperienceRecord.depuis_json(ligne["contrat"]) if ligne else None

    def tentatives(self, job_id: str, shot_id: str = "") -> list[ExperienceRecord]:
        """Toutes les tentatives d'un plan, dans l'ordre — l'histoire d'une
        réparation se lit ainsi, tentative par tentative."""
        requete = "SELECT contrat FROM experiences WHERE job_id = ?"
        parametres: list[object] = [job_id]
        if shot_id:
            requete += " AND shot_id = ?"
            parametres.append(shot_id)
        requete += " ORDER BY shot_id, tentative"

        with db.connexion() as conn:
            lignes = conn.execute(requete, parametres).fetchall()
        return [ExperienceRecord.depuis_json(x["contrat"]) for x in lignes]

    def toutes(self, limite: int = 1000) -> list[ExperienceRecord]:
        with db.connexion() as conn:
            lignes = conn.execute(
                "SELECT contrat FROM experiences ORDER BY cree_le DESC LIMIT ?",
                (limite,),
            ).fetchall()
        return [ExperienceRecord.depuis_json(x["contrat"]) for x in lignes]

    @staticmethod
    def _identifiant(record: ExperienceRecord) -> str:
        return f"exp_{record.job_id}_{record.shot_id}_{record.tentative}"


# ── Analyse : décrire ce qui s'est passé, jamais prédire ────────────────

def performance_par_strategie(records: Iterable[ExperienceRecord]) -> dict[str, Performance]:
    """Ce que chaque stratégie a donné, en pratique."""
    return _agreger(records, lambda r: r.strategie.value if r.strategie else "")


def performance_par_modele(records: Iterable[ExperienceRecord]) -> dict[str, Performance]:
    """Ce que chaque modèle a donné, en pratique.

    Séparé de la stratégie volontairement : `2.5D` peut être rendu par
    plusieurs moteurs, et un modèle peut servir plusieurs stratégies. Les
    agréger ensemble masquerait lequel des deux est en cause.
    """
    return _agreger(records, lambda r: r.modele)


def _agreger(records: Iterable[ExperienceRecord],
             cle) -> dict[str, Performance]:
    """N'agrège que les lignes EXPLOITABLES.

    Une tentative sans conclusion (`resultat` vide) est du bruit : la
    compter ferait bouger des moyennes sans rien signifier, et gonflerait
    l'échantillon — donc la confiance qu'on accorde au chiffre.
    """
    seaux: dict[str, dict] = {}
    for r in records:
        if not r.exploitable or not (k := cle(r)):
            continue
        seau = seaux.setdefault(k, {"n": 0, "ok": 0, "ko": 0, "?": 0,
                                    "cout": 0.0, "latence": 0})
        seau["n"] += 1
        seau["cout"] += r.cout_reel_eur
        seau["latence"] += r.latence_ms
        if r.resultat == "PASS":
            seau["ok"] += 1
        elif r.resultat == "FAIL":
            seau["ko"] += 1
        else:
            seau["?"] += 1

    return {
        k: Performance(
            cle=k, echantillon=s["n"], reussites=s["ok"], echecs=s["ko"],
            incertains=s["?"], cout_total_eur=s["cout"],
            latence_moyenne_ms=s["latence"] / s["n"],
        )
        for k, s in sorted(seaux.items())
    }
