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

from dataclasses import dataclass, field

from pdz.moteur.erreurs import ErreurConfig
from pdz.production.continuite import indices_de_scene
from pdz.univers import Univers
from pdz.video.soustitres import Mot

# Un plan sous cette durée passe inaperçu : le spectateur voit un clignotement,
# pas un changement de point de vue. En dessous, on ne découpe pas la réplique.
DUREE_PLAN_MINIMALE_S = 0.9

# Part de la réplique laissée à la réaction. 35 % : le repli quand aucune
# pause naturelle n'est trouvée dans la voix (voir `point_de_coupe`) — assez
# pour exister, pas assez pour qu'on se demande pourquoi on ne voit plus
# celui qui parle.
PART_REACTION = 0.35

# Le point de coupe naturel n'est cherché que près de la cible à 35 % — pas
# n'importe où dans la réplique. Une pause en tout début ou toute fin de
# réplique n'est pas une frontière parlant/réaction, juste une respiration.
FENETRE_RECHERCHE_PCT = 0.15


def point_de_coupe(mots_replique: list[Mot], duree_ms: float,
                   cible_pct: float = PART_REACTION) -> float:
    """La part de la réplique (0-1) à laisser à la réaction.

    Un pourcentage fixe coupe parfois en plein milieu d'un mot. La voix
    porte déjà l'information d'un meilleur endroit : une vraie pause (fin de
    proposition, respiration) proche de la cible. Sans mots exploitables —
    reprise sans timings détaillés, réplique d'un seul mot — on retombe sur
    `cible_pct`, exactement le comportement d'avant.
    """
    if len(mots_replique) < 2:
        return cible_pct

    debut = mots_replique[0].debut_ms
    cible_ms = duree_ms * (1 - cible_pct)
    fenetre = duree_ms * FENETRE_RECHERCHE_PCT

    meilleure_pause_ms = -1.0
    position_ms = None
    for avant, apres in zip(mots_replique, mots_replique[1:]):
        pause_ms = apres.debut_ms - avant.fin_ms
        if pause_ms <= 0:
            continue
        position = avant.fin_ms - debut
        if abs(position - cible_ms) > fenetre:
            continue
        if pause_ms > meilleure_pause_ms:
            meilleure_pause_ms, position_ms = pause_ms, position

    if position_ms is None:
        return cible_pct
    return max(0.0, min(1.0, 1 - (position_ms / duree_ms)))


def grouper_mots_par_replique(mots: list[Mot],
                              debuts_de_replique: frozenset[int]) -> list[list[Mot]]:
    """Retrouve, pour chaque réplique, les mots qui lui appartiennent.

    `mots` est daté sur la piste complète (voir `BandeVoix.mots`) ;
    `debuts_de_replique` donne seulement les frontières. Nécessaire aussi
    bien à la production réelle (juste après synthèse) qu'à une reprise, où
    seule la forme aplatie est relue depuis la base.
    """
    limites = sorted(debuts_de_replique)
    if not limites:
        return []
    groupes: list[list[Mot]] = [[] for _ in limites]
    idx = 0
    for mot in sorted(mots, key=lambda m: m.debut_ms):
        while idx + 1 < len(limites) and mot.debut_ms >= limites[idx + 1]:
            idx += 1
        groupes[idx].append(mot)
    return groupes


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
    # Pourquoi ce plan existe dans l'histoire (« révèle une information »,
    # « fait monter la tension ») — jamais ce qu'il montre littéralement.
    # Vide sur un script écrit sans empreinte créative : le montage reste
    # identique, voir `ecriture/script`.
    fonction: str = ""
    # Le type de cadrage (gros_plan, plan_large...) — écrit par
    # ShotPromptWriter, voir pdz/production/cadrage.py. Vide tant que cette
    # étape n'a pas encore enrichi le plan.
    cadrage: str = ""
    # Le registre visuel imposé pour CE plan (ex: « abstract wireframe
    # visualization, not a realistic map »). Distinct de `cadrage` : le
    # cadrage dit COMMENT filmer, le registre dit à quel VOCABULAIRE visuel
    # appartient l'image — mesuré à l'écran : un objet présent dans le
    # prompt (« océans ») n'empêche pas Flux de choisir un registre entier
    # différent (carte géographique réaliste au lieu d'un wireframe
    # abstrait). Voir pdz/production/images.py::prompt_plan().
    registre_visuel: str = ""
    # La checklist écrite par ShotPromptWriter pour ce plan précis : ce que
    # l'image DOIT montrer, et ce qu'elle ne doit surtout PAS montrer — voir
    # `pdz/production/fidelite_visuelle.py`. Sert à la fois à corriger le
    # prompt texte et, pour les plans à risque, à vérifier l'image RÉELLEMENT
    # produite (`pdz/production/qa_images.py`).
    elements_obligatoires: list[str] = field(default_factory=list)
    elements_a_exclure: list[str] = field(default_factory=list)
    # Ce que le plan peut montrer en plus, sans que ce soit ce qui doit
    # attirer l'œil en premier — la hiérarchie visuelle entre PRIMARY
    # (elements_obligatoires, doit apparaître) et SECONDARY (ici, peut
    # apparaître). Optionnel : liste vide si ShotPromptWriter n'a rien
    # jugé utile à préciser, jamais un oubli qui bloque quoi que ce soit.
    elements_secondaires: list[str] = field(default_factory=list)
    # Qui fait quoi avec quoi, écrit DIRECTEMENT par ShotPromptWriter (il
    # vient d'écrire la phrase, il sait déjà la réponse) — chaque élément
    # est {"cible": ..., "etat": ...}, `etat` déjà formulé prêt à l'emploi
    # (« visibly pressed »), pas un verbe brut à conjuguer côté Python.
    # Voir `pdz.agents.ecriture.plans.ShotPromptWriter.fusionner()`.
    relations: list[dict] = field(default_factory=list)
    # Un concept narratif à risque (marque, présence interdite...) et sa
    # représentation visuelle compatible avec l'univers — {"concept": ...,
    # "representation": ...}. Le concept brut ne doit jamais rester dans le
    # prompt final si une représentation existe (voir `fusionner()`).
    abstractions: list[dict] = field(default_factory=list)
    # Un défaut connu du générateur anticipé PAR ShotPromptWriter lui-même,
    # avec sa formulation de mitigation — {"risque": ..., "mitigation":
    # ...}. Complète (ne remplace pas) la détection après-coup de
    # `pdz.production.risque_prompt`.
    risques_predits: list[dict] = field(default_factory=list)
    # Une disposition QUALITATIVE (« ce qui domine perceptuellement »),
    # vocabulaire fixe et court comme `cadrage` — jamais une position
    # spatiale. Voir `pdz.production.cadrage.PHRASES_DISPOSITION`.
    disposition: str = ""
    # Où se place chaque objet nommé l'un par rapport à l'autre — {"entite":
    # ..., "zone": "top"/"bottom"/"left"/"right"/"center", "profondeur":
    # "background"/"midground"/"foreground"}, jamais une coordonnée
    # physique. Distinct de la priorité perceptuelle (`elements_
    # obligatoires`/`elements_secondaires`) : une position spatiale n'est
    # jamais déduite d'une importance narrative, ni l'inverse. Vide sauf
    # quand plusieurs objets ont une position relative qui compte
    # vraiment — voir `pdz.production.geometrie.phrase()`.
    geometrie: list[dict] = field(default_factory=list)
    # Les éléments de `elements_obligatoires` que ShotPromptWriter avait
    # d'abord OUBLIÉS dans son propre prompt, et que `fidelite_visuelle.
    # renforcer()` a dû rajouter après coup. Vide dans le cas normal (le
    # prompt les avait déjà). Non vide, c'est le signal qu'un plan mérite
    # une vérification visuelle après génération — le modèle qui a déjà
    # raté une fois est le plus probable à rater encore une fois.
    corrections_fidelite: list[str] = field(default_factory=list)
    # `relance` : ScriptWriter marque déjà la réplique qui installe un temps
    # fort de rétention (contrainte de script.py, positions calculées exprès
    # toutes les 15-20 s) — mais ce booléen n'était relu par personne après
    # sa propre validation (voir pdz/agents/ecriture/script.py). Porté ici
    # pour que l'animation puisse enfin en tenir compte — voir
    # `pdz/production/animation.py::noter()`.
    relance: bool = False
    # Le verdict de `pdz.production.qa_images` quand il finit à NEEDS_REVIEW
    # après regénération : un défaut visuel déjà constaté, gardé tel quel
    # plutôt que bloquer l'épisode. Vide/False par défaut — c'est le cas
    # normal, la vérification ciblée ne tourne que sur les plans à risque.
    besoin_revue: bool = False

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
            "fonction": self.fonction,
            "cadrage": self.cadrage,
            "registre_visuel": self.registre_visuel,
            "elements_obligatoires": self.elements_obligatoires,
            "elements_a_exclure": self.elements_a_exclure,
            "elements_secondaires": self.elements_secondaires,
            "relations": self.relations,
            "abstractions": self.abstractions,
            "risques_predits": self.risques_predits,
            "disposition": self.disposition,
            "geometrie": self.geometrie,
            "corrections_fidelite": self.corrections_fidelite,
            "relance": self.relance,
            "besoin_revue": self.besoin_revue,
        }


def decouper(repliques: list[dict], durees_s: list[float], univers: Univers, *,
             plans_par_replique: int = 2,
             mots_par_replique: list[list[Mot]] | None = None) -> list[PlanScript]:
    """Transforme les répliques en plans, avec leurs durées réelles.

    `durees_s` vient de la bande voix : ce sont les durées **mesurées** des
    répliques synthétisées. C'est ce qui garantit que l'image change quand la
    parole change, et pas 400 ms plus tard.

    Une réplique n'est coupée en deux que si trois conditions sont réunies :
    le script demande une réaction, le personnage qui réagit existe, et la
    réplique est assez longue pour que la coupe se voie.

    `mots_par_replique`, s'il est fourni (voir `grouper_mots_par_replique`),
    affine le POINT de coupe sur une vraie pause de la voix plutôt qu'un
    pourcentage fixe — voir `point_de_coupe`. Optionnel et positionnel par
    réplique : une valeur manquante ou `None` retombe sur `PART_REACTION`.
    """
    if len(repliques) != len(durees_s):
        raise ErreurConfig(
            f"{len(repliques)} répliques mais {len(durees_s)} durées mesurées. "
            "La bande voix et le script ne décrivent pas le même épisode."
        )

    plans: list[PlanScript] = []
    for i, (replique, duree) in enumerate(zip(repliques, durees_s, strict=True)):
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

        fonction = replique.get("fonction_plan", "")

        relance = bool(replique.get("relance"))

        if not coupable:
            plans.append(PlanScript(
                numero=len(plans),
                replique_numero=replique.get("numero", len(plans) + 1),
                personnage=parlant.id,
                action=replique.get("action", ""),
                emotion=replique.get("emotion", "calme"),
                decor=replique.get("decor", ""),
                duree_s=round(duree, 3),
                fonction=fonction,
                relance=relance,
            ))
            continue

        part_reaction = PART_REACTION
        if mots_par_replique is not None and i < len(mots_par_replique):
            part_reaction = point_de_coupe(mots_par_replique[i], duree * 1000)
            # Garde-fou : la coupe naturelle ne doit jamais produire un plan
            # sous le minimum lisible — dans ce cas, on retombe sur le repli.
            if (duree * part_reaction < DUREE_PLAN_MINIMALE_S
                    or duree * (1 - part_reaction) < DUREE_PLAN_MINIMALE_S):
                part_reaction = PART_REACTION

        plans.append(PlanScript(
            numero=len(plans),
            replique_numero=replique.get("numero", len(plans) + 1),
            personnage=parlant.id,
            action=replique.get("action", ""),
            emotion=replique.get("emotion", "calme"),
            decor=replique.get("decor", ""),
            duree_s=round(duree * (1 - part_reaction), 3),
            fonction=fonction,
            relance=relance,
        ))
        plans.append(PlanScript(
            numero=len(plans),
            replique_numero=replique.get("numero", len(plans)),
            personnage=reagit.id,
            action=f"reacting to what {parlant.nom} just said, listening",
            emotion=emotion_de_reaction(replique.get("emotion", "calme")),
            decor=replique.get("decor", ""),
            reaction=True,
            duree_s=round(duree * part_reaction, 3),
            fonction=f"réaction : {fonction}" if fonction else "",
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
    scenes = len(set(indices_de_scene([p.decor for p in plans])))
    resume = (f"{len(plans)} plans · {total:.1f} s · "
             f"{total / len(plans):.2f} s par plan · "
             f"{reactions} plans de réaction · {scenes} scène(s)")

    # Visible seulement quand le script a été écrit avec une empreinte
    # créative — c'est ce qui permet de vérifier, sans ouvrir le YAML, que
    # les plans ne se contentent pas d'illustrer littéralement chaque phrase.
    fonctions = [p.fonction for p in plans if p.fonction]
    if fonctions:
        resume += "\n" + "\n".join(f"  · plan {p.numero} : {p.fonction}"
                                   for p in plans if p.fonction)
    return resume
