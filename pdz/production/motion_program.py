"""L'intention temporelle d'un plan, sous forme typée.

Une image fixe dit CE QUI EST PRÉSENT. Une animation doit dire, en plus :
ce qui reste identique, ce qui change, comment ça change, et ce qui est
interdit. Ce module porte cette différence.

Le principe qui gouverne tout le reste : **l'image générée juste avant est
la source de vérité**. Le modèle vidéo n'est pas là pour refabriquer une
scène — il reçoit une image déjà correcte et un programme minimal décrivant
comment elle doit évoluer. C'est pourquoi `doit_preserver` existe, et
pourquoi le prompt compilé ne redécrit jamais la scène.

Zéro appel IA : les décisions de mouvement viennent déjà du seul appel
`ShotPromptWriter` (champs `mouvement_*`, voir plans@1.13.0), et les
invariants se dérivent de l'univers et du plan. Rien n'est inventé ici —
une information absente reste absente.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pdz.univers import Univers


class ControleCamera(str, Enum):
    """Comment la contrainte de caméra peut être imposée au fournisseur.

    Distinction volontairement explicite : l'adaptateur fal.ai n'envoie que
    `{prompt, image_url, duration, aspect_ratio}` — aucun paramètre de
    caméra, de graine, de guidage ni de trajectoire. « Caméra verrouillée »
    est donc une INTENTION exprimée en toutes lettres, pas une garantie
    technique. Le code le dit plutôt que de le laisser croire : un
    diagnostic `CAMERA_DOMINANT` en aval sera un désaccord entre l'intention
    et le résultat, pas un bug de paramétrage.
    """

    TEXTE_SEULEMENT = "text_only"


# Traduction du vocabulaire fixe de `mouvement_camera` (plans@1.13.0). Même
# discipline que `cadrage.PHRASES` : une table, pas de génération.
PHRASES_CAMERA = {
    "push_in_lent": "camera performs a slow forward push-in",
    "pull_back_lent": "camera performs a slow pull-back",
    "pan_lent": "camera pans slowly across the scene",
    "leger_tremblement": "subtle handheld camera vibration",
    "fixe": "camera holds steady",
}

# Repli quand ShotPromptWriter n'a rien décidé de plus précis que l'émotion
# (job en cache d'avant plans@1.13.0, ou plan sans évolution concrète).
# Toujours filtré ensuite par `risque_prompt.purger_mouvement_interdit()`.
VOCABULAIRE_EMOTION = {
    "colere": "the character shouts, shoulders heaving",
    "surprise": "the character recoils sharply, then freezes",
    "peur": "the character shrinks back, trembling slightly",
    "joie": "the character laughs, body bouncing",
    "tristesse": "the character looks down slowly",
    "mepris": "the character slowly turns their head away",
    "gene": "the character shifts weight, eyes darting sideways",
    "calme": "subtle idle motion, slight breathing, eyes blinking",
}

# Ce que l'architecture impose, indépendamment de l'univers : l'image est la
# source de vérité, donc son sujet, sa géométrie et sa composition ne sont
# pas négociables. Ce n'est pas une supposition sur le contenu du plan, mais
# une conséquence directe du mode image→vidéo (voir l'en-tête du module).
PRESERVATION_UNIVERSELLE = ("subject identity", "scene geometry", "composition")
INTERDITS_UNIVERSELS = ("new objects", "scene redesign")

# Ce que le prompt dit DÉJÀ en toutes lettres par ailleurs. Le programme, lui,
# reste complet : c'est la donnée qui servira au diagnostic en aval, et elle ne
# doit pas être amputée pour une raison de rédaction. Seule la COMPILATION
# économise les mots — mesuré : un prompt de mouvement trop long fait
# refabriquer la scène au lieu de l'animer (enquête run #66).
_DEJA_COUVERT_PAR_LIDENTITE = ("subject identity",)

# Amplification textuelle par intensité. `faible` n'ajoute rien : demander
# explicitement « peu de mouvement » à un modèle qui en produit déjà trop
# peu serait contre-productif.
PHRASES_INTENSITE = {
    "fort": "clearly visible, unmistakable motion throughout",
    "modere": "steady, clearly readable motion",
}


@dataclass(frozen=True)
class MotionProgram:
    """L'intention temporelle d'UN plan — jamais sa description visuelle."""

    shot_id: str
    duree_s: float
    action: str
    camera: str
    camera_controle: ControleCamera
    environnement: str
    intensite: str
    cible_perceptuelle: str
    doit_preserver: tuple[str, ...] = ()
    peut_changer: tuple[str, ...] = ()
    interdit: tuple[str, ...] = ()
    # Le registre visuel du plan, réaffirmé seulement s'il n'est pas déjà
    # porté par le reste — un modèle image→vidéo peut dériver de style en
    # cours de clip (mesuré, enquête run #66).
    registre: str = ""

    @property
    def camera_verrouillee(self) -> bool:
        """Vrai quand aucun mouvement de caméra n'est voulu — soit par choix
        explicite (`fixe`), soit par absence de décision. Sert au diagnostic
        en aval : un `CAMERA_DOMINANT` sur un plan verrouillé est un échec,
        sur un plan en `pan_lent` c'est l'inverse."""
        return self.camera in ("", PHRASES_CAMERA["fixe"])


def _invariants(plan: dict, univers: Univers) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """(doit_preserver, peut_changer, interdit) — DÉRIVÉS, jamais inventés.

    Les sources sont, dans l'ordre : le principe image→vidéo (universel),
    puis les consignes et interdits de l'univers, puis ce que le plan a
    réellement décidé. Un plan qui ne dit rien sur son environnement ne
    reçoit aucun invariant d'environnement.
    """
    doit_preserver = list(PRESERVATION_UNIVERSELLE)
    interdit = list(INTERDITS_UNIVERSELS)
    peut_changer: list[str] = []

    # Depuis l'univers — la seule source légitime pour ces contraintes-là.
    # La détection du « visage interdit » n'est PAS refaite ici : c'est
    # `risque_prompt.visage_est_interdit()` qui la porte déjà, et deux
    # détections concurrentes finiraient par diverger.
    from pdz.production import risque_prompt

    if univers.style.rendu.strip():
        doit_preserver.append("visual style")
    if risque_prompt.visage_est_interdit(univers.style.consignes_image):
        interdit.append("facial motion")
    if "wireframe" in " ".join(univers.style.consignes_image).lower():
        doit_preserver.append("wireframe rendering")

    # Depuis le plan — ce que ShotPromptWriter a réellement décidé.
    if (plan.get("mouvement_sujet") or "").strip():
        peut_changer.append("subject motion")
    if (plan.get("mouvement_environnement") or "").strip():
        peut_changer.append("environmental motion")
    if plan.get("geometrie"):
        # Des positions relatives ont été décidées : elles font partie de la
        # composition à tenir, pas de ce qui peut bouger librement.
        doit_preserver.append("relative object placement")
    if (plan.get("mouvement_camera") or "") == "fixe":
        # Seulement sur un CHOIX explicite. Un champ vide veut dire « aucun
        # mouvement de caméra n'apporte rien ici », pas « fige la caméra » :
        # traduire ce vide en consigne d'immobilité revenait à instruire
        # l'immobilité sur la majorité des plans, ce que le correctif du run
        # #66 avait justement retiré.
        interdit.append("camera reframing")

    return tuple(doit_preserver), tuple(peut_changer), tuple(interdit)


def _cible_perceptuelle(action: str, intensite: str, camera: str) -> str:
    """Ce que le spectateur doit RÉELLEMENT percevoir — déterministe.

    Sert à la QA en aval : la question devient « le mouvement attendu est-il
    perceptible ? » plutôt que « les pixels changent-ils ? ».
    """
    # `action` n'est jamais vide ici : `depuis_plan()` garantit au minimum le
    # repli par émotion. Pas de branche « aucun mouvement attendu » tant que
    # rien ne peut la produire — une branche morte finit par mentir.
    if camera and camera != PHRASES_CAMERA["fixe"]:
        return "viewer_must_perceive_camera_movement"
    if intensite == "fort":
        return "viewer_must_perceive_strong_subject_motion"
    return "viewer_must_perceive_subject_motion"


def depuis_plan(plan: dict, univers: Univers) -> MotionProgram:
    """Compile un `PlanScript.en_dict()` en intention temporelle.

    Purement déterministe, aucun appel IA : les décisions viennent déjà des
    champs `mouvement_*` écrits par ShotPromptWriter dans le seul appel de
    l'épisode. Un plan qui n'en porte aucun retombe sur le vocabulaire par
    émotion, comme avant — la compatibilité avec les jobs en cache d'avant
    plans@1.13.0 est le premier contrat de cette fonction.
    """
    action = (plan.get("mouvement_sujet") or "").strip()
    if not action:
        emotion = plan.get("emotion", "calme")
        action = VOCABULAIRE_EMOTION.get(emotion, "subtle idle motion")

    camera = PHRASES_CAMERA.get(plan.get("mouvement_camera") or "", "")
    intensite = plan.get("intensite_mouvement") or ""
    doit_preserver, peut_changer, interdit = _invariants(plan, univers)

    return MotionProgram(
        shot_id=str(plan.get("numero", "")),
        duree_s=float(plan.get("duree_s") or 0),
        action=action,
        camera=camera,
        camera_controle=ControleCamera.TEXTE_SEULEMENT,
        environnement=(plan.get("mouvement_environnement") or "").strip(),
        intensite=intensite,
        cible_perceptuelle=_cible_perceptuelle(action, intensite, camera),
        doit_preserver=doit_preserver,
        peut_changer=peut_changer,
        interdit=interdit,
        registre=(plan.get("registre_visuel") or "").strip(),
    )


def compiler_prompt(programme: MotionProgram, univers: Univers) -> str:
    """Le texte envoyé au modèle vidéo — l'artefact final du programme.

    Blocs conceptuels (action, caméra, environnement, préservation,
    interdits) mais formulation compacte : l'image de départ porte déjà la
    scène, la redécrire fait REFABRIQUER au lieu d'animer. Mesuré : le
    prompt d'IMAGE réinjecté ici portait le texte à 119 mots, 2,6× le seuil
    que ce projet documente.

    Ouvre explicitement sur « animate this still image » — le modèle doit
    savoir qu'il transforme, pas qu'il génère.
    """
    from pdz.production import risque_prompt

    morceaux = ["animate this still image", programme.action]

    if programme.camera:
        morceaux.append(programme.camera)
    if programme.environnement:
        morceaux.append(programme.environnement)
    if phrase := PHRASES_INTENSITE.get(programme.intensite, ""):
        morceaux.append(phrase)

    # « character design stays identical » est conservé tel quel : c'est la
    # formulation déjà éprouvée pour l'identité, et la retirer casserait ce
    # que le prompt garantissait avant ce refactor.
    morceaux.append("character design stays identical")

    # +12 mots environ au pire cas mesuré — assumés, et de nature différente
    # de ce qui avait été retiré : `action` réinjectait 65 mots de DESCRIPTION
    # DE SCÈNE (le modèle refabriquait), là où ces deux blocs sont des
    # CONTRAINTES, c'est-à-dire précisément ce qui empêche la refabrication.
    if preserver := [c for c in programme.doit_preserver
                     if c not in _DEJA_COUVERT_PAR_LIDENTITE]:
        morceaux.append("preserve " + ", ".join(preserver))
    if programme.interdit:
        morceaux.append("no " + ", no ".join(programme.interdit))

    prompt = ", ".join(morceaux)

    if programme.registre and programme.registre.lower() not in prompt.lower():
        prompt = f"{prompt}, maintain style: {programme.registre}"
    if univers.style.ambiance:
        prompt = f"{prompt}, {univers.style.ambiance}"

    return risque_prompt.purger_mouvement_interdit(prompt, univers)
