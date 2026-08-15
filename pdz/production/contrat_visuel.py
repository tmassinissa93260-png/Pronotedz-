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

import re
from dataclasses import dataclass, field

from pdz.production.storyboard import PlanScript
from pdz.univers import Personnage, Univers

# Détecte, dans un texte déjà écrit (action + elements_obligatoires), un
# verbe qui relie explicitement un personnage à un objet — « qui fait quoi
# avec quoi », minimal et volontairement pas un scene-graph : même
# technique que `pdz.production.risque_prompt` (un motif = une façon
# d'exprimer une relation), pas une nouvelle architecture.
_MOTIFS_RELATION = [
    r"\btouches?\b", r"\btouching\b", r"\btouched\b",
    r"\bholds?\b", r"\bholding\b", r"\bheld\b",
    r"\bcarr(y|ies|ying)\b", r"\bpress(es|ing|ed)?\b", r"\btaps?\b",
    r"\btient\b", r"\btouche(nt)?\b", r"\bporte(nt)?\b", r"\btapote(nt)?\b",
]


@dataclass(frozen=True)
class ContratVisuel:
    qui: str
    qui_apparence: str
    quoi: str
    avec_quoi: list[str] = field(default_factory=list)
    relations: list[str] = field(default_factory=list)
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


def _relations(action: str, elements_obligatoires: list[str]) -> list[str]:
    texte = " ".join([action, *elements_obligatoires]).lower()
    trouvees = []
    for motif in _MOTIFS_RELATION:
        if m := re.search(motif, texte):
            trouvees.append(m.group(0))
    return trouvees


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


def compiler(plan: PlanScript, personnage: Personnage, univers: Univers) -> ContratVisuel:
    """Compile un `ContratVisuel` depuis des données déjà écrites ailleurs
    dans le pipeline — zéro appel IA, zéro donnée inventée."""
    registre = plan.registre_visuel.strip() or univers.style.rendu.strip()
    return ContratVisuel(
        qui=plan.personnage,
        qui_apparence=personnage.apparence,
        quoi=plan.action,
        avec_quoi=list(plan.elements_obligatoires),
        relations=_relations(plan.action, plan.elements_obligatoires),
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
