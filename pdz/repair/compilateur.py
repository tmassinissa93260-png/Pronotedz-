"""Du diagnostic au plan de réparation.

── Ce qui décide, et dans quel ordre ────────────────────────────────────

1. **Le diagnostic doit être actionnable.** Assez sûr, assez grave, avec au
   moins une piste. Réparer sur une hypothèse à pile ou face coûte plus cher
   que d'accepter le plan.
2. **La meilleure utilité espérée gagne** — pas le meilleur ratio. Voir
   `utilite_esperee` : un ratio ferait gagner « accepter » contre toute
   réparation, y compris gratuite.
3. **Ce qui a déjà échoué n'est pas reproposé.** Sans cette règle, l'arbre
   choisirait éternellement la même branche la mieux notée.

── Le catalogue est indexé par CAUSE, pas par symptôme ──────────────────

C'est toute la différence avec une relance : `CAMERA_DOMINANT` et
`STATIC_RENDER` voient tous deux « le sujet ne bouge pas assez », et
appellent des corrections opposées.
"""

from __future__ import annotations

import logging

from pdz.contracts.diagnosis import FailureDiagnosis, ModeEchec
from pdz.contracts.repair import Branche, RepairPlan, TypeReparation

log = logging.getLogger(__name__)

# Ce qu'une branche coûte et ce qu'elle promet, indépendamment du plan.
#
# `succes_attendu` = probabilité que le DÉFAUT soit corrigé. Estimation PAR
# RÈGLE, explicitement provisoire : `ExperienceMemory` la remplacera par le
# taux réel dès qu'elle aura assez de lignes (PHASE 19). Elle est ici, en
# table lisible, pour être remplaçable sans toucher à la logique.
#
# `risque` = probabilité d'AGGRAVER. Une réparation peut casser ce qui
# marchait : changer de backend peut résoudre le mouvement et perdre
# l'identité du personnage.
CATALOGUE: dict[TypeReparation, dict] = {
    TypeReparation.RECOMPILER_PROMPT: dict(
        succes_attendu=0.45, cout_eur=0.0, latence_ms=2_000, risque=0.05,
        description="réécrire le prompt de mouvement, sans changer de stratégie"),
    TypeReparation.AJUSTER_MOUVEMENT: dict(
        succes_attendu=0.50, cout_eur=0.0, latence_ms=1_000, risque=0.10,
        description="renforcer l'intensité et la cible du mouvement demandé"),
    TypeReparation.AJUSTER_CAMERA: dict(
        succes_attendu=0.55, cout_eur=0.0, latence_ms=1_000, risque=0.10,
        description="verrouiller la caméra pour que le sujet redevienne lisible"),
    TypeReparation.RENFORCER_ANCRE: dict(
        succes_attendu=0.50, cout_eur=0.0, latence_ms=1_000, risque=0.15,
        description="réaffirmer l'identité visuelle à préserver"),
    TypeReparation.REPARATION_LOCALE: dict(
        succes_attendu=0.60, cout_eur=0.02, latence_ms=20_000, risque=0.20,
        description="ne refaire que la région fautive, sous masque"),
    TypeReparation.CHANGER_STRATEGIE: dict(
        # Retomber sur la parallaxe locale garantit UN mouvement — pas CELUI
        # qui était demandé. C'est la même limite que côté stratégies : la
        # 2.5D ne sait pas inventer un personnage qui tourne la tête.
        #
        # Une première version portait 0,85 ici, en confondant « le clip
        # bougera » et « le plan montrera ce qu'il devait montrer ». Elle
        # gagnait alors contre toutes les corrections ciblées, et la
        # réparation d'un CAMERA_DOMINANT consistait à… abandonner
        # l'intention du plan. 0,60 : elle réussit quand le mouvement exact
        # n'était pas essentiel, ce qui arrive souvent mais pas toujours.
        succes_attendu=0.60, cout_eur=0.0, latence_ms=3_000, risque=0.25,
        description="changer de façon de fabriquer le plan"),
    TypeReparation.CHANGER_BACKEND: dict(
        succes_attendu=0.60, cout_eur=0.23, latence_ms=180_000, risque=0.30,
        description="refaire le rendu chez un autre moteur"),
    TypeReparation.DECOMPOSER: dict(
        succes_attendu=0.70, cout_eur=0.46, latence_ms=360_000, risque=0.35,
        description="couper le plan en plusieurs plans exécutables"),
    TypeReparation.ACCEPTER: dict(
        # `succes_attendu = 0` : accepter ne RÉPARE rien. Elle termine, ce
        # qui est autre chose. Lui donner 1.0 — première version de cette
        # table — la faisait gagner contre toutes les réparations, y compris
        # gratuites : le défaut n'était jamais corrigé, et le journal
        # affichait pourtant « réparation choisie : accepter ».
        succes_attendu=0.0, cout_eur=0.0, latence_ms=0, risque=0.0,
        description="garder le plan tel quel, en le sachant imparfait"),
    TypeReparation.DEMANDER_HUMAIN: dict(
        # Ne répare pas automatiquement non plus — mais résout, en rendant la
        # main. Choisie explicitement par le catalogue sur `INCONNU`, jamais
        # par l'arbitrage.
        succes_attendu=0.0, cout_eur=0.0, latence_ms=0, risque=0.0,
        description="rendre la main : ni un échec, ni un abandon"),
}

# Les pistes pertinentes PAR CAUSE. L'ordre est indicatif — c'est l'utilité
# espérée qui tranche.
PAR_CAUSE: dict[ModeEchec, tuple[TypeReparation, ...]] = {
    ModeEchec.RENDU_STATIQUE: (
        TypeReparation.AJUSTER_MOUVEMENT, TypeReparation.RECOMPILER_PROMPT,
        TypeReparation.CHANGER_STRATEGIE),
    ModeEchec.MOUVEMENT_FAIBLE: (
        TypeReparation.AJUSTER_MOUVEMENT, TypeReparation.CHANGER_STRATEGIE),
    ModeEchec.MOUVEMENT_SUJET_ABSENT: (
        TypeReparation.AJUSTER_MOUVEMENT, TypeReparation.RECOMPILER_PROMPT,
        TypeReparation.CHANGER_STRATEGIE),
    # La caméra mange le plan : la verrouiller AVANT de toucher au sujet.
    ModeEchec.CAMERA_DOMINANTE: (
        TypeReparation.AJUSTER_CAMERA, TypeReparation.AJUSTER_MOUVEMENT,
        TypeReparation.CHANGER_STRATEGIE),
    ModeEchec.MOUVEMENT_EXCESSIF: (
        TypeReparation.AJUSTER_MOUVEMENT, TypeReparation.AJUSTER_CAMERA),
    ModeEchec.DERIVE_IDENTITE: (
        TypeReparation.RENFORCER_ANCRE, TypeReparation.REPARATION_LOCALE,
        TypeReparation.CHANGER_BACKEND),
    ModeEchec.DERIVE_GEOMETRIE: (
        TypeReparation.RENFORCER_ANCRE, TypeReparation.CHANGER_STRATEGIE),
    ModeEchec.DERIVE_COULEUR: (
        TypeReparation.REPARATION_LOCALE, TypeReparation.RENFORCER_ANCRE),
    ModeEchec.DEFORMATION_CORPS_RIGIDE: (
        TypeReparation.CHANGER_STRATEGIE, TypeReparation.CHANGER_BACKEND),
    ModeEchec.SCINTILLEMENT: (
        TypeReparation.CHANGER_STRATEGIE, TypeReparation.REPARATION_LOCALE),
    ModeEchec.DUREE_INCORRECTE: (
        TypeReparation.CHANGER_STRATEGIE, TypeReparation.DECOMPOSER),
    ModeEchec.EVENEMENT_PRINCIPAL_ABSENT: (
        TypeReparation.DECOMPOSER, TypeReparation.RECOMPILER_PROMPT),
    ModeEchec.CAPACITE_ABSENTE: (
        TypeReparation.CHANGER_STRATEGIE, TypeReparation.CHANGER_BACKEND),
    # Un diagnostic qu'on ne sait pas nommer ne se répare pas au hasard : il
    # remonte. C'est le mécanisme de sécurité, pas un échec d'architecture.
    ModeEchec.INCONNU: (TypeReparation.DEMANDER_HUMAIN,),
}


def branches_pour(diagnostic: FailureDiagnosis,
                  deja_tentees: tuple[TypeReparation, ...] = (),
                  *, budget_restant_eur: float = 0.0) -> tuple[Branche, ...]:
    """Les réparations envisageables pour cette cause, ici et maintenant.

    Trois filtres, chacun pour une raison distincte :
      · déjà tentée  → sinon l'arbre choisirait éternellement la même ;
      · hors budget  → proposer l'impossible fait perdre un tour ;
      · `ACCEPTER` toujours ajoutée → un plan doit pouvoir se terminer.
    """
    pistes = PAR_CAUSE.get(diagnostic.mode, (TypeReparation.DEMANDER_HUMAIN,))

    branches = []
    for piste in pistes:
        if piste in deja_tentees:
            continue
        details = CATALOGUE[piste]
        if details["cout_eur"] > budget_restant_eur:
            continue
        branches.append(Branche(type=piste, **details))

    # Toujours proposée en dernier recours : sans elle, un plan dont toutes
    # les pistes sont épuisées n'aurait aucune issue, et la production
    # s'arrêterait sur un plan secondaire.
    branches.append(Branche(type=TypeReparation.ACCEPTER,
                            **CATALOGUE[TypeReparation.ACCEPTER]))
    return tuple(branches)


def compiler(diagnostic: FailureDiagnosis, *, tentative: int = 1,
             tentatives_max: int = 3,
             deja_tentees: tuple[TypeReparation, ...] = (),
             budget_restant_eur: float = 0.0,
             valeur_du_plan_eur: float = 1.0) -> RepairPlan:
    """Le plan de réparation, avec la raison de son choix écrite.

    Un choix dont on a perdu la raison ne peut être ni contesté, ni appris —
    et c'est aussi ce qui alimentera `ExperienceMemory`.
    """
    if not diagnostic.actionnable:
        # Ni assez sûr, ni assez grave, ou sans piste. Accepter est ici la
        # bonne réponse : dépenser sur une hypothèse faible coûte plus que
        # le défaut qu'on cherche à corriger.
        return _accepter(
            diagnostic, tentative, tentatives_max,
            raison=(f"diagnostic non actionnable (confiance "
                    f"{diagnostic.confiance:.0%}, sévérité "
                    f"{diagnostic.severite.value}) : le plan part tel quel"),
        )

    branches = branches_pour(diagnostic, deja_tentees,
                             budget_restant_eur=budget_restant_eur)
    plan = RepairPlan(
        id=f"reparation_{diagnostic.shot_id}",
        shot_id=diagnostic.shot_id, diagnostic=diagnostic.id,
        branches=branches, tentative=tentative, tentatives_max=tentatives_max,
    )

    if plan.epuise:
        return plan.model_copy(update={
            "choisie": TypeReparation.ACCEPTER,
            "raison": (f"tentative {tentative}/{tentatives_max} : les essais "
                       f"sont épuisés, le plan part tel quel plutôt que de "
                       f"coûter davantage"),
        })

    meilleure = plan.meilleure(valeur_du_plan_eur)
    log.info("Réparation %s : %s", diagnostic.shot_id, meilleure.type.value)
    return plan.model_copy(update={
        "choisie": meilleure.type,
        "raison": (
            f"{diagnostic.mode.value} → {meilleure.type.value} : "
            f"{meilleure.description} "
            f"(succès attendu {meilleure.succes_attendu:.0%}, "
            f"coût {meilleure.cout_eur:.3f} €, risque {meilleure.risque:.0%}, "
            f"tentative {tentative}/{tentatives_max})"
        ),
    })


def _accepter(diagnostic: FailureDiagnosis, tentative: int, tentatives_max: int,
              *, raison: str) -> RepairPlan:
    return RepairPlan(
        id=f"reparation_{diagnostic.shot_id}",
        shot_id=diagnostic.shot_id, diagnostic=diagnostic.id,
        branches=(Branche(type=TypeReparation.ACCEPTER,
                          **CATALOGUE[TypeReparation.ACCEPTER]),),
        choisie=TypeReparation.ACCEPTER, raison=raison,
        tentative=tentative, tentatives_max=tentatives_max,
    )
