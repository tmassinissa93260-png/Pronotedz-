"""Estimer ce qu'un plan demande, avant de le fabriquer.

── Pourquoi compter, plutôt que demander à un modèle ────────────────────

Tout ce qui est ici se lit sur le `ShotSpec` : combien d'entités, quelles
contraintes d'identité, quelle durée, quel mouvement. Ce sont des
comptages — la politique du dépôt est claire, ce qui est déterministe ne
passe pas par un LLM.

── Les poids ────────────────────────────────────────────────────────────

Chaque facteur porte un poids ASSUMÉ, en table lisible. Ils viennent de ce
que le dépôt a mesuré ou documenté :

  · au-delà de deux ou trois entités, un modèle d'image en oublie —
    `fidelite_visuelle.py` existe précisément parce que ça arrive ;
  · une identité à préserver est la contrainte n°1 des séries
    (`images.py` : « c'est le problème n°1 des séries générées ») ;
  · un mouvement de sujet est plus dur qu'un mouvement d'ambiance —
    c'est la même limite que côté stratégies.

Ils ne prétendent pas être exacts. Ils prétendent être **explicites**, et
remplaçables par `ExperienceMemory` quand elle saura dire quels plans
échouent vraiment.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pdz.contracts.render import Faisabilite
from pdz.contracts.shot import ShotSpec

# Au-dessous de ce score, un plan est jugé trop chargé pour partir tel quel.
# Isolé ici pour être discutable — c'est le seul nombre qui décide d'une
# décomposition.
SEUIL_DECOMPOSITION = 0.45

# Nombre d'entités au-delà duquel chaque entité supplémentaire pèse. Deux
# sujets et un décor tiennent ; à cinq objets nommés, un modèle d'image en
# oublie — c'est ce que `elements_obligatoires` sert déjà à rattraper.
ENTITES_CONFORTABLES = 3


@dataclass(frozen=True)
class Complexite:
    """Ce qui rend ce plan difficile, facteur par facteur.

    Le détail est conservé, pas seulement le score : « ce plan est LOW » ne
    dit pas quoi simplifier, « LOW à cause de six entités et d'une identité
    à préserver » si.
    """

    score: float
    facteurs: dict[str, float] = field(default_factory=dict)
    raisons: tuple[str, ...] = ()

    @property
    def faisabilite(self) -> Faisabilite:
        if self.score >= 0.7:
            return Faisabilite.HAUTE
        if self.score >= SEUIL_DECOMPOSITION:
            return Faisabilite.MOYENNE
        return Faisabilite.BASSE

    @property
    def facteur_dominant(self) -> str:
        """Ce qui coûte le plus — donc ce qu'il faut simplifier en premier."""
        if not self.facteurs:
            return ""
        return min(self.facteurs, key=lambda k: self.facteurs[k])


def analyser(plan: ShotSpec, *, mouvement_attendu: str = "",
             duree_max_backend_s: float = 0.0) -> Complexite:
    """Le score de faisabilité d'un plan, entre 0 et 1.

    Part de 1,0 (parfaitement faisable) et RETIRE pour chaque difficulté.
    Dans ce sens plutôt que l'inverse : un plan sans aucune contrainte doit
    valoir 1, et c'est le cas nominal — la majorité des plans du dépôt.
    """
    facteurs: dict[str, float] = {}
    raisons: list[str] = []

    # ── Le nombre d'entités à tenir ensemble ────────────────────────────
    entites = 1 + len(plan.entites_secondaires) + len(plan.elements_obligatoires)
    if entites > ENTITES_CONFORTABLES:
        surplus = entites - ENTITES_CONFORTABLES
        facteurs["entites"] = max(0.3, 1.0 - 0.15 * surplus)
        raisons.append(f"{entites} éléments à faire coexister dans le cadre")

    # ── L'identité à préserver ──────────────────────────────────────────
    if plan.ancres:
        facteurs["identite"] = 0.75
        raisons.append(f"identité à tenir : {', '.join(plan.ancres)}")

    # ── Le mouvement ────────────────────────────────────────────────────
    if mouvement_attendu == "sujet":
        # Seul un modèle génératif sait le rendre, et il n'y arrive pas
        # toujours — c'est ce que le run #66 a mesuré.
        facteurs["mouvement"] = 0.65
        raisons.append("mouvement de sujet : aucun traitement local ne sait le rendre")
    elif mouvement_attendu in ("ambiance", "camera"):
        facteurs["mouvement"] = 0.95

    # ── La durée ────────────────────────────────────────────────────────
    if duree_max_backend_s and plan.duree_s > duree_max_backend_s:
        # Pas une difficulté : une IMPOSSIBILITÉ. Le score s'effondre pour
        # que la décomposition soit la seule issue raisonnable.
        facteurs["duree"] = 0.2
        raisons.append(
            f"{plan.duree_s:.1f} s demandées, le backend n'en livre que "
            f"{duree_max_backend_s:.1f}"
        )

    # ── Ce qu'il faut EMPÊCHER d'apparaître ─────────────────────────────
    if plan.elements_a_exclure:
        # Un interdit n'est jamais garanti par un prompt — le dépôt le
        # documente depuis `risque_prompt.py`. Ça ne rend pas le plan
        # infaisable, ça rend son contrôle nécessaire.
        facteurs["exclusions"] = 0.9
        raisons.append(f"{len(plan.elements_a_exclure)} interdit(s) à tenir")

    # Produit et non moyenne : les difficultés se CUMULENT. Six entités ET
    # une identité à tenir ET un mouvement de sujet est bien plus dur que
    # chacun séparément, ce qu'une moyenne lisserait.
    score = 1.0
    for valeur in facteurs.values():
        score *= valeur

    return Complexite(score=round(score, 3), facteurs=facteurs,
                      raisons=tuple(raisons))


def valider_statiquement(plan: ShotSpec, *, prompt: str = "",
                         visage_interdit: bool = False) -> tuple[str, ...]:
    """Ce qui est refusable AVANT génération, sans rien dépenser.

    Réutilise `risque_prompt.raisons_de_correction()` tel quel : ce filtre
    déterministe existe depuis longtemps, tourne sans appel IA, et sait déjà
    repérer le texte lisible, les logos et les visages interdits par
    l'univers. Le réimplémenter serait le dégrader.

    `visage_interdit` est passé plutôt que déduit : la contrainte vient de
    l'univers, et ce module ne connaît pas l'univers — c'est la même règle
    qui interdit au diagnostic de relire le `MotionProgram`.
    """
    from pdz.production import risque_prompt

    problemes: list[str] = []

    if plan.duree_s <= 0:
        problemes.append(f"durée invalide : {plan.duree_s} s")
    if not plan.sujet:
        problemes.append("aucun sujet : le plan ne dit pas ce qu'il montre")

    # Les deux listes ne doivent pas se contredire : demander ET interdire
    # la même chose produit une image qui échouera quoi qu'il arrive.
    if (contradiction := set(plan.elements_obligatoires) & set(plan.elements_a_exclure)):
        problemes.append(
            f"exigé et interdit à la fois : {', '.join(sorted(contradiction))}"
        )

    if prompt and (raisons := risque_prompt.raisons_de_correction(
            prompt, visage_interdit=visage_interdit)):
        problemes.append(
            "le prompt demande ce qu'un modèle d'image rate systématiquement : "
            + ", ".join(raisons)
        )

    return tuple(problemes)
