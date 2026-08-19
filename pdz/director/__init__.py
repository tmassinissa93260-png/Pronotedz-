"""Le Director Core — là où les deux profils cessent de diverger.

`ResearchState` (explicatif) et `NarrativeState` (fiction) entrent ; un seul
`DirectorState` sort. Tout ce qui suit dans le compilateur — plans,
perception, mouvement, rendu, observation, réparation — est écrit **une
seule fois** et ne sait plus de quel profil vient la production.

C'est la décision de docs/GAP_ANALYSIS.md § 1, rendue exécutable : la
divergence s'arrête AVANT le compilateur, pas dedans.

── Ce que ce module ne fait pas ─────────────────────────────────────────

**Aucun appel IA, aucun prompt.** Le Director assemble une décision de mise
en scène à partir de matière déjà écrite (l'univers, le brief, le script, le
graphe de connaissance). Le jour où un champ de `DirectorState` ressemble à
un prompt, c'est que la frontière a bougé au mauvais endroit.

Il ne connaît évidemment aucun fournisseur — vérifié par
`tests/test_architecture.py`.
"""

from __future__ import annotations

from typing import Any

from pdz.contracts.base import Provenance
from pdz.contracts.communs import Profil
from pdz.contracts.director import (
    Continuite,
    ContraintesProduction,
    DirectorState,
    EtatEmotionnel,
    EtatSpectateur,
    LangageVisuel,
    NarrativeIntention,
)
from pdz.contracts.narrative import NarrativeState
from pdz.contracts.research import ResearchState
from pdz.contracts.topic import TopicRequest

__all__ = ["compiler", "depuis_narration", "depuis_recherche"]

# Les paliers de compréhension, dans l'ordre. Le Director doit savoir ce que
# le spectateur est censé avoir acquis à chaque étape — sans quoi un plan ne
# peut pas savoir s'il EXPLIQUE ou s'il RAPPELLE, et le montage répète ce
# qui est acquis ou saute ce qui ne l'est pas.
PALIERS_EXPLICATIFS = (
    "T0 le spectateur ignore le sujet",
    "T1 il se pose la question",
    "T2 il reçoit une première explication",
    "T3 il voit le mécanisme",
    "T4 il comprend la chaîne causale",
    "T5 il repart avec la thèse",
)
# En fiction, l'acquisition n'est pas un savoir mais une TENSION. Les mêmes
# six paliers seraient un contresens : on ne « comprend » pas une trahison,
# on la voit venir puis éclater.
PALIERS_FICTION = (
    "T0 le spectateur découvre la situation",
    "T1 il perçoit l'enjeu",
    "T2 il prend parti",
    "T3 la tension monte",
    "T4 le retournement a lieu",
    "T5 il en mesure la conséquence",
)


def compiler(topic: TopicRequest, source: ResearchState | NarrativeState,
             *, brief: dict[str, Any] | None = None,
             visuel: LangageVisuel | None = None,
             budget_max_eur: float = 0.0) -> DirectorState:
    """Le point d'entrée unique. Route sur le TYPE de la source, pas sur un
    drapeau : un `ResearchState` ne peut pas être compilé en fiction, et
    laisser un booléen décider ouvrirait cette possibilité pour rien."""
    if isinstance(source, ResearchState):
        return depuis_recherche(topic, source, brief=brief, visuel=visuel,
                                budget_max_eur=budget_max_eur)
    return depuis_narration(topic, source, brief=brief, visuel=visuel,
                            budget_max_eur=budget_max_eur)


def depuis_recherche(topic: TopicRequest, recherche: ResearchState, *,
                     brief: dict[str, Any] | None = None,
                     visuel: LangageVisuel | None = None,
                     budget_max_eur: float = 0.0) -> DirectorState:
    """Profil EXPLICATIF : les claims deviennent ce que la vidéo s'engage à porter.

    **Seuls les claims affirmables** entrent dans `points_a_porter`. Un
    énoncé heuristique ou contredit peut parfaitement apparaître dans la
    vidéo — nuancé, attribué — mais il ne fait pas partie de ce qu'elle
    promet. Confondre les deux est exactement ce qui produit une vidéo
    assurée sur du vide.
    """
    affirmables = recherche.affirmables
    # La thèse est le claim le plus solide, à confiance égale le premier —
    # l'ordre du graphe reflète celui de la recherche, il n'est pas aléatoire.
    these = max(affirmables, key=lambda c: c.confiance, default=None)

    return _assembler(
        topic, brief, visuel, budget_max_eur,
        profil=Profil.EXPLICATIF,
        these=these.enonce if these else "",
        points=tuple(c.id for c in affirmables),
        paliers=PALIERS_EXPLICATIFS,
        # Une lacune de recherche est une continuité NON RÉSOLUE au sens du
        # Director : quelque chose que la mise en scène devra contourner ou
        # assumer, et qu'on ne peut pas se contenter d'oublier.
        non_resolues=recherche.lacunes,
        producteur="director.depuis_recherche",
        entrees=(recherche.id,),
    )


def depuis_narration(topic: TopicRequest, narration: NarrativeState, *,
                     brief: dict[str, Any] | None = None,
                     visuel: LangageVisuel | None = None,
                     budget_max_eur: float = 0.0) -> DirectorState:
    """Profil FICTION : le conflit devient la thèse, les événements les points.

    Aucun claim, aucune source — et c'est le point. Demander ses preuves à
    « Strawberina trahit Bananito » produirait une abstraction vide.
    """
    return _assembler(
        topic, brief, visuel, budget_max_eur,
        profil=Profil.FICTION,
        these=narration.conflit,
        points=tuple(e.id for e in narration.evenements),
        paliers=PALIERS_FICTION,
        # Les règles du monde sont des invariants à tenir d'un plan à
        # l'autre : c'est exactement le rôle des ancres de continuité.
        ancres=tuple(p.id for p in narration.personnages if p.role),
        non_resolues=(),
        producteur="director.depuis_narration",
        entrees=(narration.id,),
    )


def _assembler(topic: TopicRequest, brief: dict[str, Any] | None,
               visuel: LangageVisuel | None, budget_max_eur: float, *,
               profil: Profil, these: str, points: tuple[str, ...],
               paliers: tuple[str, ...], producteur: str,
               entrees: tuple[str, ...], ancres: tuple[str, ...] = (),
               non_resolues: tuple[str, ...] = ()) -> DirectorState:
    """La partie COMMUNE aux deux profils — écrite une seule fois.

    Ce qui vient du brief (accroche, arc, temps forts) est identique dans
    les deux cas : `BriefWriter` produit déjà une structure narrative sans
    savoir si le sujet est réel ou inventé, et c'est très bien ainsi.
    """
    brief = brief or {}
    strategie = brief.get("strategie") or {}
    beats = brief.get("beats") or []

    return DirectorState(
        id="director_state",
        profil=profil,
        dependances=entrees,
        provenance=Provenance(producteur=producteur, entrees=entrees),
        intention=NarrativeIntention(
            these=these,
            accroche=str(strategie.get("mecanisme_hook", "")).strip(),
            payoff=_payoff(beats),
            beats=tuple(_beat(b) for b in beats),
            points_a_porter=points,
        ),
        spectateur=EtatSpectateur(
            audience=topic.audience,
            # Rien n'est supposé connu : aucune mesure ne le dit, et
            # supposer à la place du spectateur est le meilleur moyen de
            # sauter l'explication dont il avait besoin.
            connaissances_supposees=(),
            paliers=paliers,
        ),
        emotion=EtatEmotionnel(
            courbe=tuple(str(b.get("role", "")).strip() for b in beats
                         if str(b.get("role", "")).strip()),
            relances=_relances(brief),
        ),
        visuel=visuel or LangageVisuel(),
        continuite=Continuite(ancres=ancres, non_resolues=non_resolues),
        contraintes=ContraintesProduction(
            duree_cible_s=topic.duree_cible_s,
            budget_max_eur=budget_max_eur,
            langue=topic.langue,
            plateformes=topic.plateformes,
        ),
    )


def _beat(b: dict[str, Any]) -> str:
    """« 0% hook : … » — la position ET le rôle, parce que l'un sans l'autre
    ne permet pas de savoir si un temps fort est arrivé trop tard."""
    role = str(b.get("role", "")).strip()
    quoi = str(b.get("quoi", "")).strip()
    position = b.get("position_pct")
    prefixe = f"{int(position)}% " if isinstance(position, (int, float)) else ""
    return f"{prefixe}{role} : {quoi}".strip(" :")


def _payoff(beats: list[dict[str, Any]]) -> str:
    """Le dernier temps fort dont le rôle nomme un aboutissement.

    Cherché par le rôle et non pris comme « le dernier beat » : une vidéo
    peut se terminer sur une boucle ou une relance, auquel cas le payoff
    n'est pas le dernier élément de la liste.
    """
    for b in reversed(beats):
        if any(mot in str(b.get("role", "")).lower() for mot in ("payoff", "résolution", "resolution")):
            return str(b.get("quoi", "")).strip()
    return ""


def _relances(brief: dict[str, Any]) -> tuple[int, ...]:
    """Les positions de relance décidées en amont.

    `ScriptWriter` les reçoit déjà sous forme de numéros exacts plutôt que
    d'une consigne en texte libre — mesuré : la consigne seule ne suffit
    pas, le modèle écrit un script entier sans jamais cocher `relance`.
    """
    brutes = brief.get("relances") or brief.get("positions_relance") or ()
    return tuple(int(x) for x in brutes if isinstance(x, (int, float)))
