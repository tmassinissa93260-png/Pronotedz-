"""Un plan trop chargé devient plusieurs plans exécutables.

── La règle qui interdit tout le reste ──────────────────────────────────

**Jamais sans conserver la fonction narrative.** Chaque plan issu d'une
décomposition hérite du `but`, du `porte`, de la continuité et de la relation
causale de son parent. Une décomposition qui perd le pourquoi produit trois
plans corrects qui ne racontent plus rien — et le récit ne s'en aperçoit
qu'au montage, quand il est trop tard.

── Ce qu'on découpe, et dans quel ordre ─────────────────────────────────

On retire les difficultés une par une, du facteur DOMINANT vers les autres :

    un plan chargé  →  ÉTABLIR (le sujet, seul)
                    →  AGIR    (l'événement, sans le décor à tenir)
                    →  RÉVÉLER (le reste, une fois le sujet acquis)

Chaque plan issu du découpage est plus simple que l'original, et leur SOMME
raconte la même chose. C'est ce que fait déjà un monteur devant un plan
impossible.
"""

from __future__ import annotations

from pdz.contracts.shot import ShotSpec
from pdz.renderability.analyse import SEUIL_DECOMPOSITION, Complexite, analyser

# En dessous de cette durée, découper produirait des plans que le cerveau
# traite comme du bruit. Le dépôt documente déjà ce repère : sous ~1,2 s,
# une coupe n'est plus lue comme un changement.
DUREE_MINIMALE_PAR_PLAN_S = 1.2


def doit_decomposer(plan: ShotSpec, complexite: Complexite) -> bool:
    """Décomposer, ou fabriquer tel quel ?

    Deux conditions, et la seconde compte autant que la première : le plan
    doit être trop chargé, ET assez long pour que le découpage produise des
    plans encore lisibles. Découper 1,5 s en trois ne fabrique pas trois
    plans, ça fabrique du clignotement.
    """
    if complexite.score >= SEUIL_DECOMPOSITION:
        return False
    return plan.duree_s >= 2 * DUREE_MINIMALE_PAR_PLAN_S


def decomposer(plan: ShotSpec, complexite: Complexite | None = None,
               *, mouvement_attendu: str = "") -> tuple[ShotSpec, ...]:
    """Découpe un plan chargé — ou le rend tel quel s'il n'y a rien à gagner.

    Rend TOUJOURS au moins un plan. Un appelant ne doit jamais avoir à
    distinguer « décomposé » de « pas décomposé » : il reçoit une liste de
    plans à fabriquer, c'est tout.
    """
    complexite = complexite or analyser(plan, mouvement_attendu=mouvement_attendu)
    if not doit_decomposer(plan, complexite):
        return (plan,)

    morceaux = _decouper(plan, complexite)
    if len(morceaux) < 2:
        return (plan,)

    duree = round(plan.duree_s / len(morceaux), 3)
    if duree < DUREE_MINIMALE_PAR_PLAN_S:
        # Le découpage était possible sur le papier et ne l'est pas dans le
        # temps disponible. Mieux vaut un plan chargé qu'une rafale illisible.
        return (plan,)

    return tuple(
        morceau.model_copy(update={
            "id": f"{plan.id}_{i}" if plan.id else "",
            "numero": plan.numero,
            "duree_s": duree,
            # ── L'HÉRITAGE NARRATIF, non négociable ─────────────────────
            # Sans lui, on obtient trois plans corrects qui ne racontent
            # plus rien.
            "but": plan.but,
            "porte": plan.porte,
            "fonction": plan.fonction,
            "ancres": plan.ancres,
            "emotion": plan.emotion,
            "registre_visuel": plan.registre_visuel,
            # L'état final du DERNIER morceau est celui du plan d'origine :
            # la décomposition ne change pas où l'on arrive.
            "etat_apres": plan.etat_apres if i == len(morceaux) - 1 else "",
            "etat_avant": plan.etat_avant if i == 0 else "",
        })
        for i, morceau in enumerate(morceaux)
    )


def _decouper(plan: ShotSpec, complexite: Complexite) -> list[ShotSpec]:
    """Les morceaux, selon ce qui rendait le plan difficile.

    On attaque le facteur DOMINANT — celui qui coûte le plus — plutôt que
    de découper mécaniquement. Simplifier ce qui n'était pas le problème ne
    rendrait le plan ni plus faisable, ni plus lisible.
    """
    dominant = complexite.facteur_dominant

    if dominant == "duree":
        # Rien à simplifier : le plan est juste trop long pour ce backend.
        # Deux moitiés identiques, chacune dans les clous.
        return [plan, plan]

    if dominant == "entites":
        # ÉTABLIR le sujet seul, puis RÉVÉLER le reste. C'est le découpage
        # qu'un monteur ferait : on ne demande pas au spectateur d'identifier
        # six éléments d'un coup.
        etablir = plan.model_copy(update={
            "entites_secondaires": (),
            "elements_obligatoires": plan.elements_obligatoires[:1],
            "evenement": "",
        })
        reveler = plan.model_copy(update={
            "elements_obligatoires": plan.elements_obligatoires[1:],
        })
        return [etablir, reveler]

    if dominant == "mouvement" and plan.evenement:
        # POSER l'état de départ, puis JOUER l'événement. Un plan qui doit
        # à la fois montrer une situation et la faire changer demande deux
        # choses au même clip.
        poser = plan.model_copy(update={"evenement": "", "etat_apres": ""})
        jouer = plan.model_copy(update={"etat_avant": plan.etat_avant})
        return [poser, jouer]

    return [plan]
