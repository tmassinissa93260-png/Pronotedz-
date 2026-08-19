"""Ce qu'on sait des modèles — et la différence entre le savoir et le croire.

`modeles.yaml` portait déjà les capacités, mais toutes au même titre :
`fait: [animation, vision]` mélangeait sans distinction ce que la
documentation annonce et ce qu'on a réellement constaté. Les mesures
existaient pourtant — elles vivaient en COMMENTAIRES :

    « MESURÉ (runs #57, #65, #66) : ce endpoint rend ~4,84 s qu'on lui
      demande 5 ou 10 »
    « ANNONCÉES par fal, pas encore mesurées ici »

Un commentaire ne se requête pas, ne s'agrège pas, et ne peut pas empêcher
une décision. Ce module les transforme en données.

── La règle de conversion ───────────────────────────────────────────────

    `fait:`      → ANNONCE. C'est une déclaration de configuration : elle
                   sert à ROUTER, jamais à garantir. Le dépôt s'en sert
                   depuis toujours pour choisir un modèle, et c'est très
                   bien — mais choisir n'est pas promettre.

    `capacites:` → le statut écrit, tel quel. C'est le seul endroit où
                   MESURE peut apparaître.

Conséquence assumée : **presque tout est ANNONCE aujourd'hui.** Ce n'est pas
un défaut de ce module, c'est l'état réel de la connaissance du dépôt. Le
faire apparaître est précisément ce qui permettra de le corriger.
"""

from __future__ import annotations

from functools import lru_cache

from pdz.contracts.capabilities import CapabilityGraph, Capacite, ModeleCapacites
from pdz.contracts.communs import StatutCapacite
from pdz.ia.registre import registre

__all__ = ["capacites_du_modele", "graphe", "mesures_manquantes"]

_STATUTS = {
    "MESURE": StatutCapacite.MESURE,
    "ANNONCE": StatutCapacite.ANNONCE,
    "INCONNU": StatutCapacite.INCONNU,
}


def _capacite(nom: str, brut: dict | None) -> Capacite:
    """Une entrée de `capacites:` → un `Capacite` typé.

    Un statut absent ou inconnu retombe sur INCONNU, jamais sur MESURE : une
    faute de frappe dans la configuration ne doit pas pouvoir promouvoir une
    capacité au rang de mesure.
    """
    brut = brut or {}
    statut = _STATUTS.get(str(brut.get("statut", "")).upper(), StatutCapacite.INCONNU)
    valeur = brut.get("valeur")
    return Capacite(
        nom=nom,
        statut=statut,
        # `None` reste `None` sous INCONNU : « on ne sait pas » n'est pas
        # « on a vérifié que non ».
        valeur=bool(valeur) if valeur is not None else None,
        mesure_le=str(brut.get("le", "")),
        methode=str(brut.get("methode", "")),
        note=str(brut.get("note", "")),
    )


def capacites_du_modele(modele_id: str) -> ModeleCapacites:
    """Le profil complet d'un modèle : `fait:` annoncé + `capacites:` qualifié.

    Les deux sources fusionnent, et `capacites:` gagne toujours : c'est la
    seule qui peut porter une mesure, et écraser une mesure par une annonce
    serait exactement l'inverse de ce qu'on cherche.
    """
    reg = registre()
    modele = reg.modeles.get(modele_id)
    if modele is None:
        return ModeleCapacites(modele=modele_id)

    # `fait:` d'abord — tout y est ANNONCE, sans exception.
    connues: dict[str, Capacite] = {
        nom: Capacite(nom=nom, statut=StatutCapacite.ANNONCE, valeur=True,
                      note="déclaré dans `fait:` — routage, pas garantie")
        for nom in modele.fait
    }

    brut = next((m for m in reg._brut.get("modeles", []) if m.get("id") == modele_id), {})
    for nom, details in (brut.get("capacites") or {}).items():
        connues[nom] = _capacite(nom, details)

    return ModeleCapacites(
        id=f"capacites_{modele_id}",
        modele=modele_id,
        fournisseur=modele.fournisseur,
        capacites=tuple(connues[nom] for nom in sorted(connues)),
        durees_s=tuple(modele.durees_s),
    )


@lru_cache(maxsize=1)
def graphe() -> CapabilityGraph:
    """Tous les modèles connus, avec ce qu'on sait de chacun."""
    return CapabilityGraph(
        id="capability_graph",
        modeles=tuple(capacites_du_modele(m) for m in sorted(registre().modeles)),
    )


def mesures_manquantes() -> tuple[tuple[str, str], ...]:
    """(modèle, capacité) qu'il faudrait mesurer — la liste de travail.

    Utile telle quelle : c'est la carte de ce que le système croit sans
    l'avoir vérifié. Une capacité ANNONCÉE sur laquelle on s'appuie souvent
    mérite d'être mesurée avant de le découvrir en production.
    """
    return tuple(
        (m.modele, c.nom)
        for m in graphe().modeles for c in m.capacites
        if c.statut is not StatutCapacite.MESURE
    )
