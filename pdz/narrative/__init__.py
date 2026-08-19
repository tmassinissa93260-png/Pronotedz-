"""Profil FICTION : ce qui tient le récit debout, sans jamais parler de sources.

Une fiction n'a pas de claims à sourcer. Lui en demander produirait un graphe
vide de sens sur la totalité des productions actuelles du dépôt — quatre
univers, des personnages, des trahisons. Ce module extrait à la place ce qui
joue le MÊME rôle pour la mise en scène : qui veut quoi, contre qui, sous
quelles règles de monde.

**Zéro appel IA.** Tout vient de matière déjà écrite : l'`Univers` (fichier
YAML versionné) et le script produit par `ScriptWriter`. Redemander à un
modèle ce que deux structures portent déjà serait payer pour dégrader une
information qu'on avait exacte.
"""

from __future__ import annotations

from typing import Any

from pdz.contracts.narrative import Evenement, NarrativeState
from pdz.contracts.narrative import Personnage as PersonnageNarratif
from pdz.univers import Univers

__all__ = ["depuis_univers"]


def depuis_univers(univers: Univers, situation: str,
                   script: dict[str, Any] | None = None) -> NarrativeState:
    """`Univers` (+ script, s'il existe déjà) → `NarrativeState`.

    Sans script, on rend ce que l'univers sait : les personnages et les
    règles du monde. Le conflit et les événements restent vides — ils
    n'existent pas encore, et les inventer ferait croire à une narration
    qui n'a pas eu lieu.
    """
    return NarrativeState(
        id="narrative_state",
        situation=situation,
        personnages=_personnages(univers, script),
        conflit=_conflit(script),
        evenements=_evenements(script),
        regles_du_monde=tuple(univers.regles_du_monde),
    )


def _personnages(univers: Univers, script: dict[str, Any] | None) -> tuple[PersonnageNarratif, ...]:
    """Vue mise en scène des personnages — jamais leur fiche de fabrication.

    `role` vient du script : le personnage qui parle le plus est le
    protagoniste de CET épisode. C'est un fait mesurable sur le texte, pas
    une interprétation — et il change d'un épisode à l'autre, ce qu'une
    étiquette figée dans l'univers ne saurait pas exprimer.
    """
    repliques = (script or {}).get("repliques") or []
    prises = _prises_de_parole(repliques)
    plus_bavard = max(prises, key=lambda k: prises[k], default="")

    return tuple(
        PersonnageNarratif(
            id=p.id,
            role=_role(p.id, plus_bavard, prises),
            # `caractere` est ce que l'univers dit du personnage. L'objectif
            # d'UN épisode n'y figure pas : le laisser vide est exact.
            objectif="",
            obstacle="",
        )
        for p in univers.personnages
    )


def _prises_de_parole(repliques: list[dict]) -> dict[str, int]:
    compte: dict[str, int] = {}
    for r in repliques:
        if (qui := str(r.get("personnage", "")).strip()):
            compte[qui] = compte.get(qui, 0) + 1
    return compte


def _role(personnage: str, plus_bavard: str, prises: dict[str, int]) -> str:
    """« protagoniste » | « antagoniste » | « figurant » | "".

    Vide quand le script ne dit rien : un personnage de l'univers qui ne
    parle pas dans cet épisode n'a pas de rôle dans cet épisode.
    """
    if not prises:
        return ""
    if personnage == plus_bavard:
        return "protagoniste"
    if personnage in prises:
        # Celui qui parle dans un épisode sans être le plus présent porte le
        # contre-point. « antagoniste » au sens dramatique — celui qui
        # s'oppose — pas au sens moral.
        return "antagoniste" if len(prises) == 2 else "figurant"
    return ""


def _conflit(script: dict[str, Any] | None) -> str:
    """La promesse du script EST son conflit : c'est la tension posée avant
    la 5e seconde (voir `ecriture/script`). Rien à inventer."""
    return str((script or {}).get("promesse", "")).strip()


def _evenements(script: dict[str, Any] | None) -> tuple[Evenement, ...]:
    """Un événement par réplique qui FAIT quelque chose.

    Seules les répliques porteuses d'une action deviennent des événements :
    une réplique sans action est une prise de parole, pas un fait du monde.
    La distinction compte pour la suite — c'est elle qui décidera quels
    plans doivent montrer un changement d'état.
    """
    evenements = []
    for r in (script or {}).get("repliques") or []:
        if not (action := str(r.get("action", "")).strip()):
            continue
        acteurs = tuple(x for x in (str(r.get("personnage", "")).strip(),
                                    str(r.get("reaction_de", "")).strip()) if x)
        evenements.append(Evenement(
            id=f"ev_{int(r.get('numero', len(evenements) + 1)):03d}",
            description=action,
            acteurs=acteurs,
            # `fonction_plan` dit pourquoi ce moment existe dans l'histoire —
            # c'est bien sa conséquence narrative, déjà écrite.
            consequence=str(r.get("fonction_plan", "")).strip(),
        ))
    return tuple(evenements)
