"""Le plan traduit en 8 questions : qui, quoi, qui-fait-quoi-avec-quoi, où,
dans quel état, dans quel registre visuel, ce qui ne doit pas apparaître.

Compilé depuis des champs qui existent déjà sur `PlanScript`/`Personnage`/
`Univers` — jamais un nouvel appel IA, jamais une nouvelle table de saisie.
Sert à la fois de forme typée pour la compilation du prompt (voir
`pdz.production.images.prompt_plan_depuis_contrat`) et de trace journalisée
(voir `pdz.production.episode`) — c'est le même contrat dans les deux cas,
compilé une seule fois par plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pdz.production.storyboard import PlanScript
from pdz.univers import Personnage, Univers


@dataclass(frozen=True)
class ContratVisuel:
    qui: str
    qui_apparence: str
    quoi: str
    avec_quoi: list[str] = field(default_factory=list)
    # Ce qui peut légitimement partager le cadre sans être ce que le plan
    # cherche à montrer en premier — la hiérarchie visuelle entre PRIMARY
    # (avec_quoi) et SECONDARY. Vient de `plan.elements_secondaires`
    # (plans@1.10.0) — vide si ShotPromptWriter n'en a désigné aucun.
    avec_quoi_secondaire: list[str] = field(default_factory=list)
    # Mots hors du vocabulaire propre de l'univers, signal déterministe de
    # marque potentielle (voir `risque_prompt.mots_hors_vocabulaire`) — déjà
    # calculé par l'appelant, jamais recalculé ici (voir `compiler()`).
    risques_marque: list[str] = field(default_factory=list)
    # `{cible, etat}`, écrit directement par ShotPromptWriter (voir
    # plans@1.11.0) — plus une supposition par position sur le texte déjà
    # écrit (`_relations()`, retiré : le modèle qui rédige la phrase sait
    # déjà qui fait quoi avec quoi, pas besoin de le redeviner après coup).
    relations: list[dict] = field(default_factory=list)
    # `{concept, representation}` : un concept narratif à risque (marque…)
    # et son substitut visuel choisi par ShotPromptWriter dans le même
    # appel — déjà consommé dans le prompt par `fusionner()`, porté ici
    # pour la traçabilité/QA (voir `registre_contradictions`, plan §5).
    abstractions: list[dict] = field(default_factory=list)
    # `{risque, mitigation}` : un défaut connu du générateur anticipé par
    # ShotPromptWriter, avec sa formulation d'évitement — PRÉDICTION
    # textuelle, jamais une preuve (voir architecture PRÉDICTION/
    # GÉNÉRATION/VÉRIFICATION).
    risques_predits: list[dict] = field(default_factory=list)
    # Vocabulaire qualitatif fixe (voir `cadrage.DISPOSITIONS`) — jamais une
    # coordonnée physique, jamais premier-plan/arrière-plan.
    disposition: str = ""
    # `{entite, zone, profondeur}`, écrit directement par ShotPromptWriter
    # (voir plans@1.12.0) — où se place chaque objet nommé, jamais une
    # coordonnée physique. Distinct de la priorité perceptuelle
    # (`avec_quoi`/`avec_quoi_secondaire`) : la position spatiale et
    # l'importance narrative sont deux décisions différentes.
    geometrie: list[dict] = field(default_factory=list)
    # Décisions de mouvement pour un clip animé — jamais consommées par
    # `prompt_plan_depuis_contrat()` (le prompt d'IMAGE), seulement par
    # `pdz.production.animation._prompt_mouvement()`, qui les lit
    # directement sur le `PlanScript`. Portées ici pour la même raison que
    # `relations`/`geometrie` : traçabilité et vérification déterministe
    # (voir `pdz.production.decision_visuelle`), pas pour être recompilées.
    mouvement_sujet: str = ""
    mouvement_camera: str = ""
    mouvement_environnement: str = ""
    intensite_mouvement: str = ""
    # `ou_id` : l'identifiant brut du décor (`plan.decor`), nécessaire pour
    # que `prompt_plan_depuis_contrat()` reproduise EXACTEMENT la résolution
    # (et le repli anime-only) de `prompt_plan()`. `ou` est la description
    # déjà résolue, lisible pour la journalisation — les deux coexistent.
    ou_id: str = ""
    ou: str = ""
    # `emotion`/`fonction` : les valeurs brutes, nécessaires pour reproduire
    # exactement `prompt_plan()` (EXPRESSIONS[emotion], « shot chosen to »).
    # `etat_moment` est leur résumé lisible pour la journalisation — les
    # deux coexistent, l'un n'est pas dérivé au prix de l'autre.
    emotion: str = ""
    fonction: str = ""
    etat_moment: str = ""
    cadrage: str = ""
    # `registre` : le plancher non négociable — jamais vide, le registre du
    # plan s'il en précise un, sinon celui de l'univers (voir constrainte
    # « le registre visuel ne doit jamais dériver silencieusement »). Pour
    # la journalisation/QA. `registre_visuel_plan` est la valeur BRUTE du
    # plan (peut être vide) : c'est elle qui va dans `prompt_plan()`, dont
    # l'assemblage ajoute déjà `univers.style.rendu` sans condition plus
    # loin — y remettre le plancher doublonnerait ce texte dans le prompt.
    registre: str = ""
    registre_visuel_plan: str = ""
    registre_univers: str = ""
    ne_doit_pas_apparaitre: list[str] = field(default_factory=list)


def _lieu(plan: PlanScript, univers: Univers) -> str:
    if plan.decor and (d := univers.decor(plan.decor)):
        return d.description
    if univers.anime and univers.decors:
        return univers.decors[0].description
    return ""


def _etat_moment(plan: PlanScript) -> str:
    morceaux = [plan.emotion]
    if plan.fonction:
        morceaux.append(plan.fonction)
    if plan.reaction:
        morceaux.append("réaction")
    return " · ".join(m for m in morceaux if m)


def compiler(plan: PlanScript, personnage: Personnage, univers: Univers, *,
            risques_marque: list[str] | None = None) -> ContratVisuel:
    """Compile un `ContratVisuel` depuis des données déjà écrites ailleurs
    dans le pipeline — zéro appel IA, zéro donnée inventée.

    `risques_marque` est optionnel et vient de l'appelant (voir
    `pdz.production.images.fabriquer()`) : le calculer demande le
    vocabulaire propre de l'univers, construit une fois par épisode — pas
    une donnée que ce compilateur pur devrait recalculer lui-même.
    """
    registre = plan.registre_visuel.strip() or univers.style.rendu.strip()
    return ContratVisuel(
        qui=plan.personnage,
        qui_apparence=personnage.apparence,
        quoi=plan.action,
        avec_quoi=list(plan.elements_obligatoires),
        avec_quoi_secondaire=list(plan.elements_secondaires),
        risques_marque=list(risques_marque or []),
        relations=list(plan.relations),
        abstractions=list(plan.abstractions),
        risques_predits=list(plan.risques_predits),
        disposition=plan.disposition,
        geometrie=list(plan.geometrie),
        mouvement_sujet=plan.mouvement_sujet,
        mouvement_camera=plan.mouvement_camera,
        mouvement_environnement=plan.mouvement_environnement,
        intensite_mouvement=plan.intensite_mouvement,
        ou_id=plan.decor,
        ou=_lieu(plan, univers),
        emotion=plan.emotion,
        fonction=plan.fonction,
        etat_moment=_etat_moment(plan),
        cadrage=plan.cadrage,
        registre=registre,
        registre_visuel_plan=plan.registre_visuel,
        registre_univers=univers.style.rendu,
        ne_doit_pas_apparaitre=list(plan.elements_a_exclure),
    )
