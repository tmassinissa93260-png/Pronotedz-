"""Le `DirectorState`, projeté en consigne pour le scénariste.

── Pourquoi une projection, et pas un passage direct ────────────────────

Le contrat est la source de vérité ; le texte envoyé au modèle en est une
**projection temporaire**. Ce module est cette projection, et il vit à un
seul endroit pour une raison précise : c'est le point où une information
sourcée peut se transformer en affirmation. Le laisser se reconstruire dans
trois appelants garantirait qu'un des trois oublie la nuance.

── Ce que la projection garantit ────────────────────────────────────────

**Seuls les énoncés affirmables entrent comme des faits.** Le reste — non
sourcé, contredit, périmé — est soit énoncé comme incertain, soit exclu. Un
scénariste à qui l'on donne dix énoncés sans distinction en fera dix
affirmations : c'est le mécanisme exact par lequel une vidéo devient
assurée sur du vide.

Les lacunes sont dites, pas tues. « On ne sait pas » est une consigne
utilisable ; son absence produit une invention.
"""

from __future__ import annotations

from pdz.contracts.director import DirectorState
from pdz.contracts.research import ResearchState

__all__ = ["projeter_en_situation"]


def projeter_en_situation(etat: DirectorState,
                          recherche: ResearchState | None = None) -> str:
    """`DirectorState` → la consigne que reçoit le scénariste.

    Rend une chaîne, parce que c'est ce que `produire()` attend — mais
    aucune décision n'est prise ici : tout vient du contrat. Changer la
    formulation ne change pas ce que la vidéo a le droit d'affirmer ; seul
    un changement du `ResearchState` le peut.
    """
    morceaux: list[str] = []

    if etat.intention.these:
        morceaux.append(f"Sujet : {etat.intention.these}")

    if recherche is not None:
        morceaux += _blocs_de_recherche(recherche, etat)

    if etat.spectateur.audience:
        morceaux.append(f"Public : {etat.spectateur.audience}.")

    if etat.intention.accroche:
        morceaux.append(f"Accroche voulue : {etat.intention.accroche}")

    return "\n\n".join(m for m in morceaux if m.strip())


def _blocs_de_recherche(recherche: ResearchState,
                        etat: DirectorState) -> list[str]:
    """Les énoncés, séparés par ce qu'on en sait.

    La séparation EST la fonctionnalité. Mélanger les trois catégories dans
    une seule liste rendrait la projection inutile — c'est la distinction
    qui empêche d'affirmer ce qui n'est pas établi.
    """
    promis = set(etat.intention.points_a_porter)
    blocs: list[str] = []

    if (affirmables := [c for c in recherche.claims if c.id in promis]):
        blocs.append(
            "CE QUE TU PEUX AFFIRMER — chaque point est sourcé et non contredit :\n"
            + "\n".join(f"- {c.enonce}" for c in affirmables)
        )

    # Non promis mais pas faux pour autant : utilisables NUANCÉS. Les
    # supprimer appauvrirait la vidéo ; les laisser passer pour des faits la
    # rendrait mensongère.
    if (nuances := [c for c in recherche.claims if c.id not in promis]):
        blocs.append(
            "À NE JAMAIS AFFIRMER — ces points ne sont pas établis. Tu peux "
            "les évoquer, mais uniquement en les attribuant ou en les "
            "présentant comme incertains :\n"
            + "\n".join(f"- {c.enonce} ({_pourquoi(c)})" for c in nuances)
        )

    if recherche.lacunes:
        blocs.append(
            "CE QUE LA RECHERCHE N'A PAS ÉTABLI — n'invente rien pour combler "
            "ces trous, préfère ne pas en parler :\n"
            + "\n".join(f"- {lacune}" for lacune in recherche.lacunes)
        )

    return blocs


def _pourquoi(claim) -> str:
    """La raison exacte du déclassement. « non établi » sans raison invite à
    passer outre ; « aucune source » ne s'argumente pas."""
    if claim.conflits:
        return "des sources se contredisent"
    if claim.statut_temporel == "obsolete":
        return "information périmée"
    if not claim.sources:
        return "aucune source"
    return "non vérifié"
