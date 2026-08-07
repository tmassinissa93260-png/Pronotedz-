"""Le découpage : des répliques vers des plans.

Une seule responsabilité, et c'est important qu'elle soit à un seul endroit :
décider combien de plans compte l'épisode, ce que montre chacun, et combien
de temps il dure. Trois modules en dépendent — les images, l'animation, le
montage — et le jour où ils ne sont plus d'accord sur le nombre de plans,
l'épisode sort avec des images décalées d'un cran par rapport au son.

Rappel de la distinction qui structure tout le projet :

    RÉPLIQUE : une prise de parole. Sa durée est **mesurée** sur l'audio
               réellement synthétisé, jamais estimée.
    PLAN     : un changement d'image. Une réplique en occupe une ou deux —
               celui qui parle, puis la réaction de l'autre.
"""

from __future__ import annotations

from dataclasses import dataclass

from pdz.moteur.erreurs import ErreurConfig
from pdz.univers import Univers

# Un plan sous cette durée passe inaperçu : le spectateur voit un clignotement,
# pas un changement de point de vue. En dessous, on ne découpe pas la réplique.
DUREE_PLAN_MINIMALE_S = 0.9

# Part de la réplique laissée à la réaction. 35 % : assez pour exister, pas
# assez pour qu'on se demande pourquoi on ne voit plus celui qui parle.
PART_REACTION = 0.35


@dataclass
class PlanScript:
    """Un plan, tel que les images, l'animation et le montage le voient."""

    numero: int
    replique_numero: int
    personnage: str
    action: str
    emotion: str
    decor: str = ""
    reaction: bool = False
    duree_s: float = 1.75

    def en_dict(self) -> dict:
        """La forme attendue par `pdz.production.animation`."""
        return {
            "numero": self.numero,
            "personnage": self.personnage,
            "action": self.action,
            "emotion": self.emotion,
            "decor": self.decor,
            "reaction": self.reaction,
            "duree_s": self.duree_s,
        }


def decouper(repliques: list[dict], durees_s: list[float], univers: Univers, *,
             plans_par_replique: int = 2) -> list[PlanScript]:
    """Transforme les répliques en plans, avec leurs durées réelles.

    `durees_s` vient de la bande voix : ce sont les durées **mesurées** des
    répliques synthétisées. C'est ce qui garantit que l'image change quand la
    parole change, et pas 400 ms plus tard.

    Une réplique n'est coupée en deux que si trois conditions sont réunies :
    le script demande une réaction, le personnage qui réagit existe, et la
    réplique est assez longue pour que la coupe se voie.
    """
    if len(repliques) != len(durees_s):
        raise ErreurConfig(
            f"{len(repliques)} répliques mais {len(durees_s)} durées mesurées. "
            "La bande voix et le script ne décrivent pas le même épisode."
        )

    plans: list[PlanScript] = []
    for replique, duree in zip(repliques, durees_s, strict=True):
        parlant = univers.personnage(replique["personnage"])
        if parlant is None:
            raise ErreurConfig(
                f"Réplique {replique.get('numero')} : personnage "
                f"« {replique['personnage']} » absent de l'univers."
            )

        reagit = None
        if plans_par_replique > 1 and replique.get("reaction_de"):
            candidat = univers.personnage(replique["reaction_de"])
            if candidat is not None and candidat.id != parlant.id:
                reagit = candidat

        coupable = (reagit is not None
                    and duree * PART_REACTION >= DUREE_PLAN_MINIMALE_S)

        if not coupable:
            plans.append(PlanScript(
                numero=len(plans),
                replique_numero=replique.get("numero", len(plans) + 1),
                personnage=parlant.id,
                action=replique.get("action", ""),
                emotion=replique.get("emotion", "calme"),
                decor=replique.get("decor", ""),
                duree_s=round(duree, 3),
            ))
            continue

        plans.append(PlanScript(
            numero=len(plans),
            replique_numero=replique.get("numero", len(plans) + 1),
            personnage=parlant.id,
            action=replique.get("action", ""),
            emotion=replique.get("emotion", "calme"),
            decor=replique.get("decor", ""),
            duree_s=round(duree * (1 - PART_REACTION), 3),
        ))
        plans.append(PlanScript(
            numero=len(plans),
            replique_numero=replique.get("numero", len(plans)),
            personnage=reagit.id,
            action=f"reacting to what {parlant.nom} just said, listening",
            emotion=emotion_de_reaction(replique.get("emotion", "calme")),
            decor=replique.get("decor", ""),
            reaction=True,
            duree_s=round(duree * PART_REACTION, 3),
        ))

    return plans


def emotion_de_reaction(emotion_parlee: str) -> str:
    """Quelle tête fait celui qui écoute.

    Une réaction n'est pas un écho : quand l'un hurle, l'autre encaisse. La
    table est volontairement courte et lisible — elle décrit un rapport de
    forces, pas une théorie des émotions.
    """
    return {
        "colere": "peur",
        "mepris": "colere",
        "surprise": "gene",
        "joie": "joie",
        "tristesse": "gene",
        "peur": "surprise",
        "gene": "mepris",
    }.get(emotion_parlee, "surprise")


def resume(plans: list[PlanScript]) -> str:
    if not plans:
        return "aucun plan"
    total = sum(p.duree_s for p in plans)
    reactions = sum(1 for p in plans if p.reaction)
    return (f"{len(plans)} plans · {total:.1f} s · "
            f"{total / len(plans):.2f} s par plan · "
            f"{reactions} plans de réaction")
