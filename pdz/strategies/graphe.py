"""Le graphe de stratégies : choisir COMMENT, avant de choisir AVEC QUOI.

Remplace `RenderSpec → ModelRouter → Kling` par :

    ContexteRendu
        ↓
    candidates()            toutes les stratégies évaluent, GRATUITEMENT
        ↓
    coût / risque / garantie / importance narrative
        ↓
    choisir()               une stratégie, avec sa raison écrite

── Ce que le classement met en avant, et pourquoi ───────────────────────

La cascade en dur essayait toujours le modèle payant d'abord, puis retombait.
Ce n'est pas absurde — mais ce n'est pas toujours juste : un plan secondaire
de deux secondes n'a aucune raison de coûter 0,09 € pour un mouvement que la
parallaxe locale rendrait **à coup sûr** et gratuitement.

D'où l'arbitrage : le coûteux n'est proposé en tête que lorsque l'importance
narrative le justifie. C'est la formule que le dépôt appliquait déjà à moitié
(`animation.noter()` classe les plans par ce que l'animation leur
apporterait) — ici elle décide aussi de la STRATÉGIE, pas seulement du
nombre de plans animés.
"""

from __future__ import annotations

import logging

from pdz.strategies.base import Candidate, ContexteRendu, StrategieRendu
from pdz.strategies.locales import (
    StrategieDirectI2V,
    StrategieImageFixe,
    StrategieProcedurale,
    StrategieTwoPointFiveD,
)

log = logging.getLogger(__name__)

# Ce qu'un plan PARFAITEMENT réussi vaut, en euros, à importance maximale.
#
# Calibré sur ce que le dépôt PAIE DÉJÀ, pas sur une intuition : un épisode
# animé coûte 1,56 € (README), dont l'essentiel part en animation — 0,046 €/s
# chez Kling, soit 0,23 € pour un clip de 5 s, et `plans_animes_max: 6`.
# Autrement dit, le projet accepte aujourd'hui de payer ~0,23 € pour animer
# un plan qui compte.
#
# La valeur doit donc dépasser nettement ce prix, sans quoi le modèle payant
# ne serait jamais retenu — et le dépôt fait manifestement le choix inverse.
# 1,00 € : le plan qui porte l'épisode vaut environ deux tiers de son budget
# total. Au-delà, un seul plan justifierait de dépasser le plafond.
#
# Un choix EXPLICITE, pas une mesure — isolé ici pour être remplaçable le
# jour où `ExperienceMemory` dira ce qu'un plan réussi rapporte vraiment.
# C'est le paramètre le plus discutable de ce module, et c'est voulu qu'il
# soit le plus visible.
VALEUR_PLAN_MAXIMALE_EUR = 1.00

# L'ordre de déclaration ne décide rien — il ne sert qu'à rendre le journal
# lisible quand deux stratégies obtiennent le même score.
TOUTES: tuple[StrategieRendu, ...] = (
    StrategieDirectI2V(),
    StrategieTwoPointFiveD(),
    StrategieProcedurale(),
    StrategieImageFixe(),
)


def candidates(contexte: ContexteRendu,
               strategies: tuple[StrategieRendu, ...] = TOUTES) -> list[Candidate]:
    """Ce que chaque stratégie propose pour ce plan — sans rien exécuter.

    Une stratégie qui rend `None` refuse le plan : hors de son domaine. Ce
    n'est pas un échec, c'est exactement son travail. Une stratégie qui rend
    une candidature à confiance nulle, elle, s'est prononcée : elle dit
    « je peux, mais ça ne donnera rien », et sa raison l'explique.
    """
    proposees = []
    for strategie in strategies:
        if (candidate := strategie.evaluer(contexte)) is not None:
            proposees.append(candidate)
    return proposees


def valeur_du_plan_eur(importance: float) -> float:
    """Ce qu'on accepte de payer pour que CE plan soit réussi."""
    return max(0.0, min(1.0, importance)) * VALEUR_PLAN_MAXIMALE_EUR


def _score(candidate: Candidate, importance: float) -> float:
    """Le gain espéré, en euros. Voir `Candidate.utilite()`.

    Ce que ce classement produit, et qui est le comportement voulu :

      · mouvement d'AMBIANCE, plan critique  → parallaxe locale.
        Elle sait le faire, gratuitement et à coup sûr. Payer un modèle
        pour ça reviendrait à acheter une espérance là où on avait une
        garantie — l'erreur exacte du run #66.
      · mouvement de SUJET, plan critique    → modèle génératif.
        Seul à savoir inventer un personnage qui tourne la tête. Sa
        confiance moindre est compensée par le fait qu'aucune alternative
        ne rend ce que le plan exige.
      · mouvement de SUJET, plan secondaire  → parallaxe locale.
        Le plan n'en vaut pas le prix. Il bougera sans montrer exactement
        ce qui était demandé, et c'est un compromis assumé, tracé dans la
        raison du choix.
    """
    return candidate.utilite(valeur_du_plan_eur(importance))


def choisir(contexte: ContexteRendu,
            strategies: tuple[StrategieRendu, ...] = TOUTES) -> tuple[Candidate, str]:
    """La stratégie retenue, et POURQUOI — la raison est écrite, pas déduite.

    Un choix dont on a perdu la raison ne peut être ni contesté, ni appris.
    C'est aussi ce qui alimentera `ExperienceMemory` : sans la raison, une
    ligne d'expérience ne dit pas ce qu'on croyait au moment de décider.
    """
    proposees = candidates(contexte, strategies)
    if not proposees:
        # Ne peut pas arriver tant qu'`IMAGE_FIXE` est dans la liste — elle
        # accepte tout. Le dire plutôt que de rendre `None` : un appelant
        # forcé de gérer un cas impossible finit par mal le gérer.
        raise ValueError(
            f"Aucune stratégie ne se propose pour {contexte.shot_id}. "
            f"`StrategieImageFixe` accepte pourtant tout — a-t-elle été "
            f"retirée de la liste passée à `choisir()` ?"
        )

    retenue = max(proposees, key=lambda c: _score(c, contexte.importance))
    raison = (
        f"{retenue.strategie.value} : {retenue.raison or 'sans commentaire'} "
        f"(coût {retenue.cout_eur:.3f} €, confiance {retenue.confiance:.0%}, "
        f"{'garanti' if retenue.garanti else 'espéré'}, "
        f"importance du plan {contexte.importance:.0%})"
    )
    log.debug("Stratégie retenue pour %s — %s", contexte.shot_id, raison)
    return retenue, raison


def executer(contexte: ContexteRendu,
             strategies: tuple[StrategieRendu, ...] = TOUTES):
    """Choisit puis exécute. Le point d'entrée du métier.

    Aucun appelant ne nomme jamais une stratégie ni un fournisseur : il
    décrit son plan, et le graphe décide.
    """
    retenue, raison = choisir(contexte, strategies)
    strategie = next(s for s in strategies if s.nom is retenue.strategie)
    resultat = strategie.executer(contexte)
    resultat.meta["raison_strategie"] = raison
    return resultat
