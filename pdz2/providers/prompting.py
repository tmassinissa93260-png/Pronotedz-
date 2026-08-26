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

    En tête vient le **sujet de la séquence**. Il n'y était pas, et le run #8
    montre ce que ça donne : sur un épisode consacré à la voiture électrique,
    le prompt complet d'un plan large disait « Ouverture dans le registre
    décidé : technical. Cadrage : wide […] Décor : atelier de fabrication et
    laboratoire. Palette : #1A73E8, #FFFFFF, #000000. » Pas un mot du sujet.
    Le seul substantif concret étant le décor, le fournisseur a rendu des
    ateliers — un entrepôt de cartons, un garage vide, un couloir de centre
    commercial. Ce n'était pas un mauvais fournisseur : c'était une commande
    qui ne demandait rien.

    Cette fonction récitait la bible une seconde fois — registre, lumière,
    matières, graphisme — alors que `spec.intent` la porte déjà en entier.
    Mesuré sur un plan réel : le registre visuel apparaissait quatre fois
    dans un prompt de 1 187 caractères, la lumière et les matières deux fois
    chacune. Une consigne répétée n'est pas une consigne appuyée : c'est une
    consigne diluée.
    """
    quoi: list[str] = []
    if spec.subject_matter:
        # Le domaine, avant tout le reste. Sans lui la phrase ne nomme rien
        # que le fournisseur puisse reconnaître : il complète avec le décor.
        quoi.append(f"Sujet de la séquence : {spec.subject_matter}")
    if spec.evidence_required:
        # La raison d'être de l'image, dite comme telle.
        quoi.append(f"L'image doit rendre visible : {spec.evidence_required}")
    quoi.append(f"Au centre de l'image : {spec.subject}")
    if layer is not None:
        quoi.append(f"Plan {layer.role.value} : {layer.description}")

    comment = [_style(spec, bible)]

    quoi = [part.strip().rstrip(".") for part in quoi if part and part.strip()]
    comment = [part.strip().rstrip(".") for part in comment if part and part.strip()]
    return ". ".join([*quoi, *_tenir_le_budget(quoi, comment)]) + "."


def _style(spec: ImageSpec, bible: VisualBible) -> str:
    """La partie esthétique, en un seul morceau, ordonnée par ce qui pèse.

    `spec.intent` récitait la bible entière — neuf champs, dont l'optique et
    la profondeur de champ, qui se lisent bien pour un humain et n'apprennent
    presque rien à un moteur de diffusion. Le cadrage et le style d'abord, le
    décor en dernier : c'est lui qui a produit les entrepôts du run #8, il
    n'entre plus qu'après tout le reste.
    """
    morceaux = [
        f"Cadrage : {spec.composition.framing.value}, angle "
        f"{spec.composition.angle.value}, sujet "
        f"{spec.composition.subject_position.value}",
        f"Style : {bible.style}",
        f"Lumière : {bible.lighting}",
        f"Matières : {', '.join(bible.materials)}" if bible.materials else "",
        f"Texture : {bible.texture}" if bible.texture else "",
        f"Graphisme : {bible.graphics}" if bible.graphics else "",
        f"Palette : {', '.join(bible.color.palette[:4])}"
        if bible.color.palette
        else "",
        f"Décor : {bible.environment}" if bible.environment else "",
    ]
    return ". ".join(part.rstrip(".") for part in morceaux if part)


def _tenir_le_budget(quoi: list[str], comment: list[str]) -> list[str]:
    """Le sujet doit peser au moins autant que l'esthétique.

    Ce n'est pas une préférence de rédaction, c'est ce que le run #8 a coûté.
    Mesuré sur la commande réellement envoyée : **7,3 % de ses 904 caractères
    nommaient le sujet, 54 % décrivaient le style**. Le seul substantif concret
    qui pesait était le décor de la bible — « atelier de fabrication et
    laboratoire » — et le fournisseur a rendu des ateliers.

    La règle : ce qui doit être visible reçoit au moins la moitié de la
    commande. Si la bible déborde, c'est l'esthétique qui est coupée, jamais le
    sujet — et la coupe se voit, puisqu'elle se termine par un signe.

    INFÉRENCE D'INGÉNIERIE. La moitié n'est pas un seuil calibré : c'est le
    partage le plus simple qui renverse un rapport de sept contre un. Un rendu
    mesuré peut le contredire ; le rapport qu'il remplace, lui, n'avait aucune
    justification.
    """
    budget = sum(len(part) for part in quoi)
    tenus: list[str] = []
    reste = budget
    for part in comment:
        if len(part) <= reste:
            tenus.append(part)
            reste -= len(part)
        elif reste > 40:
            # Le signe de coupe tient DANS le budget : sinon l'invariant se
            # trouve enfreint de deux caractères, et un invariant qui tolère un
            # dépassement n'en est pas un.
            tronque = part[: reste - 2].rsplit(" ", 1)[0]
            tenus.append(f"{tronque} …")
            reste = 0
    return tenus


_ARTEFACTS = (
    "texte",
    "lettres",
    "chiffres",
    "légende",
    "filigrane",
    "logo",
    "signature",
)
"""Artefacts de génération, refusés quel que soit le sujet.

INFÉRENCE D'INGÉNIERIE, et fondée sur ce que le run #8 a mis à l'écran. Le
prompt négatif y était **vide** — ni la bible ni la spécification ne
remplissaient `forbidden` — et deux plans sur huit portent du faux texte
inventé par le moteur : « MITSUBAMOX 197 » sur le flanc d'un moteur, et
« 66 kWh / 360am / BP-001 » sur l'afficheur d'un boîtier.

Un texte inventé sur une image pédagogique est pire qu'un ornement : il se
lit comme une donnée, et il est faux. Ces termes ne décrivent aucun sujet, ils
écartent un mode de défaillance du générateur — ils ne prennent donc la place
d'aucune décision de la bible.
"""


def negative_prompt(spec: ImageSpec, bible: VisualBible) -> str:
    """Ce que l'image ne doit pas contenir.

    Les interdits décidés viennent en premier — ils appartiennent à la bible
    et à la spécification. Le plancher d'artefacts vient après : il ne décide
    rien, il refuse ce qu'aucun contrat ne demanderait jamais.
    """
    interdits = [*spec.forbidden, *bible.forbidden, *_ARTEFACTS]
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
