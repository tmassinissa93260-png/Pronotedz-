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


def image_prompt(spec: ImageSpec, bible: VisualBible) -> str:
    """Traduit une demande d'image en une phrase pour un moteur génératif."""
    morceaux = [
        spec.subject,
        spec.intent,
        f"registre visuel : {bible.style}",
        f"cadrage {spec.composition.framing.value}",
        f"lumière {bible.lighting}",
        f"matières {bible.materials}",
        f"graphisme {bible.graphics}",
    ]
    calques = [
        f"{layer.role.value} : {layer.description}"
        for layer in sorted(spec.layers, key=lambda item: item.depth)
    ]
    if calques:
        morceaux.append("plans successifs — " + " ; ".join(calques))
    palette = ", ".join(bible.color.palette[:4])
    if palette:
        morceaux.append(f"palette {palette}")
    return ". ".join(part for part in morceaux if part).strip()


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
