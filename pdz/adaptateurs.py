"""Le pont entre les structures existantes et les contrats — transitoire.

Règle de migration (docs/MIGRATION_PLAN.md) : quand un système fonctionne et
qu'un contrat arrive, on écrit `ANCIEN → ADAPTATEUR → NOUVEAU`, jamais
`SUPPRIMER → TOUT RÉÉCRIRE`. L'ancien disparaît le jour où il n'a plus de
consommateur, pas avant.

Ce module est donc **fait pour mourir**. Chaque fonction qu'il contient
existe parce qu'un producteur écrit encore l'ancienne forme ; quand ce
producteur écrira directement le contrat, la fonction correspondante
disparaît. C'est l'endroit où lire ce qu'il reste à migrer.

── Ce qu'un adaptateur n'a PAS le droit de faire ────────────────────────

Inventer. Un champ que l'ancienne structure ne porte pas reste vide dans le
contrat — jamais rempli d'une valeur plausible. Un `ShotSpec.but` vide dit
« ce plan n'a jamais déclaré pourquoi il existe », ce qui est exactement
l'information dont la suite a besoin. Le remplir par défaut ferait croire à
une spécification qui n'a pas eu lieu, et `ShotSpec.est_specifie`
répondrait `True` sur toute la production existante — rendant la mesure
inutile le jour même où elle est introduite.

Ce module est un consommateur des contrats, jamais l'inverse : il vit hors
de `pdz/contracts/`, qui n'importe rien (voir `tests/test_architecture.py`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pdz.contracts.audio import AudioTimeline, Mot, Replique
from pdz.contracts.camera import CameraProgram, ControleCamera, MouvementCamera
from pdz.contracts.motion import MotionProgram
from pdz.contracts.perception import PerceptualContract
from pdz.contracts.shot import Critere, ShotGraph, ShotSpec

if TYPE_CHECKING:  # pragma: no cover
    from pdz.production.contrat_visuel import ContratVisuel
    from pdz.production.motion_program import MotionProgram as MotionProgramLegacy
    from pdz.production.storyboard import PlanScript
    from pdz.production.voix import BandeVoix


# ── Plans ────────────────────────────────────────────────────────────────

def shot_spec(plan: PlanScript) -> ShotSpec:
    """`PlanScript` → `ShotSpec`.

    Les champs des questions 1, 3 et 5 (`but`, `etat_avant`/`etat_apres`,
    `criteres_reussite`) restent volontairement PARTIELS : `PlanScript` ne
    les porte pas, et les fabriquer ici les inventerait. Seul ce qui est
    réellement déductible est rempli — `fonction` existe déjà, et un
    `mouvement_sujet` décidé EST une évolution attendue, pas une supposition.
    """
    return ShotSpec(
        id=f"shot_{plan.numero:03d}",
        numero=plan.numero,
        duree_s=plan.duree_s,
        # Question 1 : ce que le plan a réellement déclaré. Vide s'il n'a
        # rien déclaré — voir l'en-tête du module.
        fonction=plan.fonction,
        # Question 2 : entièrement porté par PlanScript.
        sujet=plan.personnage,
        entites_secondaires=tuple(plan.elements_secondaires),
        decor=plan.decor,
        cadrage=plan.cadrage,
        disposition=plan.disposition,
        registre_visuel=plan.registre_visuel,
        elements_obligatoires=tuple(plan.elements_obligatoires),
        elements_a_exclure=tuple(plan.elements_a_exclure),
        # Question 3 : `mouvement_sujet` est la seule évolution qu'un plan
        # décide aujourd'hui explicitement. `etat_avant`/`etat_apres`
        # restent vides : rien ne les porte, et les déduire de l'action
        # serait une invention.
        evenement=plan.mouvement_sujet,
        emotion=plan.emotion,
        criteres_reussite=_criteres(plan),
    )


def _criteres(plan: PlanScript) -> tuple[Critere, ...]:
    """Les critères que le dépôt sait DÉJÀ vérifier pour ce plan.

    Rien d'inventé : chaque critère produit ici correspond à une sonde qui
    existe et tourne aujourd'hui. Un plan sans mouvement décidé n'obtient
    aucun critère de mouvement — la vérification de mouvement ne s'applique
    qu'aux plans animés, et lui en donner un le ferait échouer à tort.
    """
    criteres: list[Critere] = []

    if plan.mouvement_sujet or plan.intensite_mouvement:
        criteres.append(Critere(
            description="le mouvement décidé est perceptible dans le clip",
            sonde="verification_mouvement",
        ))
    if plan.elements_obligatoires:
        criteres.append(Critere(
            description="l'image montre : " + ", ".join(plan.elements_obligatoires),
            sonde="fidelite_visuelle",
        ))
    if plan.elements_a_exclure:
        criteres.append(Critere(
            description="l'image ne montre pas : " + ", ".join(plan.elements_a_exclure),
            sonde="qa_image",
            # Non bloquant : `qa_image` ne tourne que sur les plans à risque,
            # et rend `UNCERTAIN` plus souvent que `FAIL`. En faire une
            # condition obligatoire bloquerait des plans que personne n'a
            # regardés.
            obligatoire=False,
        ))
    return tuple(criteres)


def shot_graph(plans: list[PlanScript]) -> ShotGraph:
    """La liste de plans, avec les arêtes que le découpage porte déjà.

    Deux natures d'arête, toutes deux déduites de faits explicites et non
    supposées : `reaction` relie un plan de réaction au plan parlant dont il
    est né (`PlanScript.reaction`), `continuite` relie deux plans consécutifs
    dans le même décor.
    """
    specs = [shot_spec(p) for p in plans]
    aretes: list[tuple[str, str, str]] = []

    for precedent, courant in zip(plans, plans[1:], strict=False):
        source, cible = f"shot_{precedent.numero:03d}", f"shot_{courant.numero:03d}"
        if courant.reaction:
            aretes.append((source, cible, "reaction"))
        elif precedent.decor and precedent.decor == courant.decor:
            aretes.append((source, cible, "continuite"))

    return ShotGraph(plans=tuple(specs), aretes=tuple(aretes))


# ── Mouvement et caméra : un programme legacy, deux contrats ────────────

def motion_program(legacy: MotionProgramLegacy) -> MotionProgram:
    """La part MOUVEMENT D'OBJET de l'ancien programme.

    `camera` et `camera_controle` n'en font plus partie : ils partent dans
    `camera_program()`. C'est toute la raison d'être de la séparation — un
    diagnostic ne peut pas dire « ça bouge, mais c'est la caméra » tant que
    les deux vivent dans le même champ.
    """
    return MotionProgram(
        id=f"motion_{legacy.shot_id}",
        shot_id=legacy.shot_id,
        duree_s=legacy.duree_s,
        action=legacy.action,
        environnement=legacy.environnement,
        intensite=legacy.intensite,
        cible_perceptuelle=legacy.cible_perceptuelle,
        doit_preserver=tuple(legacy.doit_preserver),
        peut_changer=tuple(legacy.peut_changer),
        interdit=tuple(legacy.interdit),
        registre=legacy.registre,
        # `trajectoires`, `regions_statiques` et `priorite` restent vides :
        # aucun producteur ne les décide encore, et aucun backend ne saurait
        # les honorer. Les remplir donnerait l'illusion d'un contrôle absent.
    )


# L'ancien programme porte la caméra sous forme de PHRASE anglaise déjà
# compilée (« camera performs a slow forward push-in »), pas de son
# vocabulaire d'origine. Cette table refait le chemin inverse — elle est le
# miroir exact de `motion_program.PHRASES_CAMERA`, et son existence est
# précisément ce qui disparaîtra quand le producteur écrira le contrat
# directement au lieu d'une phrase.
_PHRASE_VERS_MOUVEMENT = {
    "camera performs a slow forward push-in": MouvementCamera.PUSH_IN_LENT,
    "camera performs a slow pull-back": MouvementCamera.PULL_BACK_LENT,
    "camera pans slowly across the scene": MouvementCamera.PAN_LENT,
    "subtle handheld camera vibration": MouvementCamera.LEGER_TREMBLEMENT,
    "camera holds steady": MouvementCamera.FIXE,
}


def camera_program(legacy: MotionProgramLegacy) -> CameraProgram:
    """La part CAMÉRA, extraite en programme distinct.

    Une phrase inconnue de la table retombe sur `FIXE`, comme le fait déjà
    `MotionProgram.camera_verrouillee` pour une caméra vide : c'est le
    comportement existant, préservé tel quel plutôt qu'amélioré au passage.
    """
    return CameraProgram(
        id=f"camera_{legacy.shot_id}",
        shot_id=legacy.shot_id,
        mouvement=_PHRASE_VERS_MOUVEMENT.get(legacy.camera, MouvementCamera.FIXE),
        # Toujours `TEXTE_SEULEMENT` aujourd'hui, et le dire est le point :
        # l'adaptateur fal.ai n'envoie aucun paramètre de caméra. La valeur
        # changera quand un backend l'acceptera ET qu'on l'aura mesuré.
        controle=ControleCamera.TEXTE_SEULEMENT,
        intensite=legacy.intensite,
    )


# ── Perception ───────────────────────────────────────────────────────────

def perceptual_contract(visuel: ContratVisuel, legacy: MotionProgramLegacy | None = None,
                        *, shot_id: str = "") -> PerceptualContract:
    """`ContratVisuel` (+ le programme de mouvement) → `PerceptualContract`.

    Les deux moitiés existantes se rejoignent ici : `ContratVisuel` sait CE
    QUI doit apparaître, `MotionProgram.cible_perceptuelle` sait CE QUI doit
    être perçu. L'ordre d'attention vient de la hiérarchie que
    ShotPromptWriter décide déjà (obligatoire d'abord, secondaire ensuite) —
    ce n'est pas une invention, c'est une hiérarchie qui existait sans être
    nommée comme telle.
    """
    attention = (visuel.qui,) if visuel.qui else ()
    attention += tuple(visuel.avec_quoi) + tuple(visuel.avec_quoi_secondaire)

    doit_percevoir = tuple(visuel.avec_quoi)
    confusions: tuple[str, ...] = ()

    if legacy is not None:
        if legacy.cible_perceptuelle:
            doit_percevoir += (legacy.cible_perceptuelle,)
        # La confusion que le dépôt sait déjà nommer : sur un plan à caméra
        # verrouillée, un mouvement de caméra est précisément la fausse
        # lecture à écarter (`CAMERA_DOMINANT`).
        if legacy.camera_verrouillee and legacy.action:
            confusions += ("camera_only_motion",)

    return PerceptualContract(
        id=f"perception_{shot_id}" if shot_id else "",
        shot_id=shot_id,
        # `quoi` est ce que le plan existe pour montrer — le champ le plus
        # proche d'un objectif principal que porte l'ancienne structure.
        objectif_principal=visuel.quoi,
        attention=attention,
        doit_percevoir=doit_percevoir,
        ne_doit_pas_etre_confondu_avec=confusions,
    )


# ── Chronologie ──────────────────────────────────────────────────────────

def audio_timeline(bande: BandeVoix, repliques: list[dict] | None = None) -> AudioTimeline:
    """`BandeVoix` → `AudioTimeline`, sans toucher aux timings.

    Les millisecondes sont recopiées telles quelles. C'est la chronologie
    officielle de la production : la moindre reconversion (arrondi, passage
    par les secondes) décalerait les sous-titres, et le dépôt a construit
    tout son découpage sur ces valeurs exactes.

    `repliques` est le script d'origine, qui porte `emotion` et `relance` —
    absents de `BandeVoix`. Optionnel : sans lui, ces champs restent à leur
    valeur neutre plutôt que d'être devinés.
    """
    par_numero = {r.get("numero", i + 1): r for i, r in enumerate(repliques or [])}

    lignes = tuple(
        Replique(
            numero=dite.numero,
            personnage=dite.personnage,
            texte=dite.texte,
            debut_ms=dite.debut_ms,
            duree_ms=dite.duree_ms,
            mots=tuple(Mot(texte=m.texte, debut_ms=m.debut_ms, fin_ms=m.fin_ms)
                       for m in dite.mots),
            emotion=str(par_numero.get(dite.numero, {}).get("emotion", "")),
            relance=bool(par_numero.get(dite.numero, {}).get("relance", False)),
        )
        for dite in bande.repliques
    )

    return AudioTimeline(
        id="audio_timeline",
        fichier_voix=str(bande.fichier),
        duree_ms=bande.duree_ms,
        repliques=lignes,
        # `caracteres_factures == 0` alors que des répliques existent : la
        # bande a été produite sans appeler le fournisseur, c'est le mode
        # muet que `voix.py` gère déjà.
        muet=bool(lignes) and bande.caracteres_factures == 0,
    )
