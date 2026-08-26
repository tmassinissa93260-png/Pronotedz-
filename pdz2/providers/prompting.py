"""Compilation d'un contrat en prompt — dans un seul sens.

    ImageSpec  →  prompt

Jamais l'inverse. Le prompt est une **compilation secondaire** : il se
reconstruit à tout moment depuis le contrat, il n'est stocké nulle part comme
autorité, et aucune décision ne le relit. Si un fournisseur comprend mal une
phrase, on corrige la traduction ici — le contrat, lui, ne bouge pas.

C'est la frontière que le §sur les prompts protège : un modèle qui reçoit du
texte libre finit par devenir la source de vérité du système. Ici il reçoit la
projection d'un contrat, et rien d'autre.
"""

from __future__ import annotations

from pdz2.contracts.visual import ImageSpec, VisualBible

__all__ = ["image_prompt", "negative_prompt", "animation_prompt"]


def image_prompt(spec: ImageSpec, bible: VisualBible, layer=None) -> str:
    """Traduit une demande d'image en une phrase pour un moteur génératif.

    L'ordre compte : ce que l'image doit **prouver** vient en tête, avant
    l'esthétique. Un moteur qui lit d'abord trois lignes de style et de
    matières traite le mécanisme comme un détail de fin de phrase.

    Cette fonction récitait la bible une seconde fois — registre, lumière,
    matières, graphisme — alors que `spec.intent` la porte déjà en entier.
    Mesuré sur un plan réel : le registre visuel apparaissait quatre fois
    dans un prompt de 1 187 caractères, la lumière et les matières deux fois
    chacune. Une consigne répétée n'est pas une consigne appuyée : c'est une
    consigne diluée.
    """
    morceaux = []
    if spec.evidence_required:
        # La raison d'être de l'image, en premier et dite comme telle.
        morceaux.append(f"L'image doit rendre visible : {spec.evidence_required}")
    morceaux.append(spec.intent)
    if layer is not None:
        morceaux.append(f"Plan {layer.role.value} : {layer.description}")
    # `intent` ne porte ni le graphisme ni la palette : eux seuls s'ajoutent.
    if bible.graphics:
        morceaux.append(f"Graphisme : {bible.graphics}")
    palette = ", ".join(bible.color.palette[:4])
    if palette:
        morceaux.append(f"Palette : {palette}")
    return ". ".join(part.strip().rstrip(".") for part in morceaux if part) + "."


def negative_prompt(spec: ImageSpec, bible: VisualBible) -> str:
    """Ce que l'image ne doit pas contenir, tel que les contrats le disent."""
    interdits = [*spec.forbidden, *bible.forbidden]
    return ", ".join(dict.fromkeys(interdits))


def animation_prompt(executable, motion) -> str:
    """Traduit un MotionProgram en consigne de mouvement.

    Le mouvement reste décidé par le `MotionProgram` : cette phrase le
    décrit, elle ne l'invente pas. Un fournisseur qui l'ignorerait produirait
    un plan que l'observateur mesurerait comme non conforme.
    """
    morceaux = [f"mouvement de caméra : {executable.execution_camera.value}"]
    if motion is not None:
        morceaux.append(
            f"énergie de mouvement visée {motion.perceptual_target.motion_energy:.2f}"
        )
        if getattr(motion, "subject_motion", None) is not None:
            description = getattr(motion.subject_motion, "description", "")
            if description:
                morceaux.append(f"sujet : {description}")
    morceaux.append("aucune coupe, un seul plan continu")
    return ". ".join(morceaux)
