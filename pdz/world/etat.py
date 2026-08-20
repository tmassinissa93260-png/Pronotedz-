"""Construire, faire évoluer et confronter l'état du monde.

Purement déterministe, **zéro appel IA** : tout vient de ce que le
`ShotGraph` porte déjà. Un modèle à qui l'on demanderait « quel est l'état du
monde ? » redirait, moins bien, ce qui est écrit dans le plan.
"""

from __future__ import annotations

from pdz.contracts.world import Entite, Etat, Position, WorldState


def etat_initial(decor: str = "", entites: tuple[str, ...] = ()) -> WorldState:
    """Le monde avant le premier plan.

    Les entités existent sans état décrit : on sait QUI est là, pas encore ce
    qu'ils font. Leur donner un état inventé ferait croire à une mise en
    scène qui n'a pas eu lieu.
    """
    return WorldState(
        id="world_initial", decor=decor,
        entites=tuple(Entite(id=e, nature="personnage") for e in entites),
    )


def appliquer(monde: WorldState, plan) -> WorldState:
    """L'état du monde APRÈS ce plan — tel que le plan l'annonce.

    C'est l'état ATTENDU, pas l'observé : rien n'a encore été rendu. La
    distinction est tout l'intérêt du module — sans elle, on ne peut jamais
    constater qu'un rendu n'a pas fait ce qu'il devait.

    Un plan qui ne dit rien de nouveau laisse le monde intact. Il n'y a pas
    d'« état par défaut » : ne rien savoir et savoir que rien ne change sont
    deux choses différentes, et la seconde s'écrit `etat_apres`.
    """
    connues = {e.id: e for e in monde.entites}

    sujet = getattr(plan, "sujet", "") or ""
    if sujet:
        precedente = connues.get(sujet)
        # `etat_apres` s'il est écrit, sinon l'événement, sinon on garde
        # l'état précédent. Jamais une description fabriquée.
        description = (getattr(plan, "etat_apres", "")
                       or getattr(plan, "evenement", "")
                       or (precedente.attendu.description if precedente else ""))
        connues[sujet] = Entite(
            id=sujet,
            nature=precedente.nature if precedente else "personnage",
            apparence=precedente.apparence if precedente else "",
            materiau=precedente.materiau if precedente else "",
            attendu=Etat(description=description,
                         position=_position(plan, sujet)),
            # L'observation d'un plan précédent ne dit rien de celui-ci :
            # la remettre à `None` est exact, la conserver serait un mensonge.
            observe=None,
        )

    for secondaire in getattr(plan, "entites_secondaires", ()):
        if secondaire not in connues:
            connues[secondaire] = Entite(id=secondaire, nature="objet",
                                         attendu=Etat(position=_position(plan, secondaire)))

    return WorldState(
        id=f"world_{getattr(plan, 'id', '') or getattr(plan, 'numero', '')}",
        shot_id=getattr(plan, "id", ""),
        # Un décor absent du plan ne réinitialise rien : c'est exactement ce
        # que `continuite.porter_le_decor()` fait déjà, et pour la même
        # raison — une réplique sans décor reste dans la scène en cours.
        decor=getattr(plan, "decor", "") or monde.decor,
        entites=tuple(connues[k] for k in sorted(connues)),
        relations=monde.relations,
    )


def depuis_plans(plans, *, decor: str = "") -> tuple[WorldState, ...]:
    """La suite des états attendus, un par plan.

    Utile telle quelle : elle rend visible ce que la vidéo prétend faire
    changer, et permet de repérer un plan qui ne fait rien avancer.
    """
    monde = etat_initial(decor=decor)
    etats = []
    for plan in plans:
        monde = appliquer(monde, plan)
        etats.append(monde)
    return tuple(etats)


def observer(monde: WorldState, constats: dict[str, str],
             confiance: float = 1.0) -> WorldState:
    """Reporte ce qu'une sonde a MESURÉ sur les entités concernées.

    `constats` est `{entite_id: description observée}`. Les entités absentes
    du dictionnaire gardent `observe = None` : elles n'ont pas été regardées,
    et c'est une information distincte de « conformes ».
    """
    return monde.model_copy(update={"entites": tuple(
        entite.model_copy(update={
            "observe": Etat(description=constats[entite.id],
                            position=entite.attendu.position,
                            confiance=confiance),
        }) if entite.id in constats else entite
        for entite in monde.entites
    )})


def delta(monde: WorldState) -> tuple[tuple[str, str, str], ...]:
    """(entité, attendu, observé) — seulement pour ce qui a été REGARDÉ.

    Une entité jamais observée n'apparaît pas : la faire figurer avec un
    observé vide la ferait passer pour une divergence, alors que c'est un
    angle mort.
    """
    return tuple(
        (e.id, e.attendu.description, e.observe.description)
        for e in monde.entites_derivees
    )


def _position(plan, entite: str) -> Position:
    """La position qualitative écrite par le plan, si elle existe.

    `geometrie` porte `{entite, zone, profondeur}` — jamais une coordonnée.
    Le dépôt a déjà tranché : donner des coordonnées à un modèle d'image ne
    les fait pas respecter, et les stocker ferait croire à une précision que
    rien ne tient.
    """
    for placement in getattr(plan, "geometrie", ()) or ():
        if isinstance(placement, dict) and placement.get("entite") == entite:
            return Position(zone=str(placement.get("zone", "")),
                            profondeur=str(placement.get("profondeur", "")))
    return Position()
