"""L'agent d'alignement : l'image doit EXPLIQUER la phrase, pas l'illustrer.

Un plan par appel, et une seule question : SANS LE SON, le spectateur
comprend-il ce que la voix dit ? L'agent propose trois actions possibles,
garde celle qui se lit le plus vite, se note lui-meme, puis reecrit les deux
prompts autour de cette action.

Ce que la machine verifie ensuite, elle : que l'action choisie est vraiment
dans le prompt photo, que la note est honnete, que l'animation progresse dans
le temps. Ce qui echoue repart chez OpenAI, comme partout ailleurs ici.
"""

from __future__ import annotations

from . import config, prompts, validator
from .models import Shot, Storyboard
from .openai_client import OpenAIError, chat_json

#: En dessous, le plan ne se comprend pas sans le son.
MIN_MUTE_TEST = 0.75
#: Trois pistes, pas une : une seule idee n'est pas un choix.
MIN_CANDIDATS = 3
#: La moitie des mots de l'action doit se retrouver dans le prompt photo.
PART_ACTION_EXIGEE = 0.5

CHAMPS_CANDIDAT = ("action", "explains", "misses")


def aligner_plan(sb: Storyboard, shot: Shot,
                 on_attempt=None) -> tuple[dict, list[str]]:
    """Rend le plan realigne, et ce qui n'a pas pu etre corrige."""
    base = [
        {"role": "system", "content": prompts.ALIGNMENT_SYSTEM},
        {"role": "user", "content": prompts.alignment_user(
            shot.voice, shot.educational_function, shot.visual_concept,
            sb.visual_bible.as_block(), _code_couleur(sb),
            shot.image_prompt, shot.animation_prompt)},
    ]

    meilleur, restants = None, ["aucune reponse exploitable"]
    for tentative in range(1, config.MAX_ALIGN_ATTEMPTS + 1):
        messages = list(base)
        if meilleur is not None:
            messages.append({"role": "user", "content": _correction(restants)})
        brut = chat_json(config.OPENAI_MODEL, messages)
        try:
            plan = _normaliser(brut)
        except OpenAIError as exc:
            if tentative == config.MAX_ALIGN_ATTEMPTS:
                raise
            meilleur, restants = meilleur or {}, [str(exc)]
            continue

        problemes = _verifier(plan)
        if on_attempt:
            on_attempt(tentative, problemes)
        if not problemes:
            return plan, []
        if meilleur is None or len(problemes) < len(restants):
            meilleur, restants = plan, problemes

    return meilleur, restants


# ---------------------------------------------------------------------------


def _code_couleur(sb: Storyboard) -> str:
    return "\n".join(f"  {e.color:14} = {e.notion} — {e.meaning}"
                     + ("  (se deplace)" if e.moving else "")
                     for e in sb.code_couleur())


def _normaliser(brut: object) -> dict:
    """La forme du contrat, ou une erreur lisible."""
    if not isinstance(brut, dict):
        raise OpenAIError("alignement : la reponse doit etre un objet JSON")

    for champ in ("understanding", "chosen", "why_chosen",
                  "image_prompt", "animation_prompt"):
        if not str(brut.get(champ) or "").strip():
            raise OpenAIError(f"alignement : '{champ}' vide")

    candidats = brut.get("candidates")
    if not isinstance(candidats, list) or len(candidats) < MIN_CANDIDATS:
        raise OpenAIError(f"alignement : il faut {MIN_CANDIDATS} pistes, "
                          f"une seule idee n'est pas un choix")
    propres = []
    for i, c in enumerate(candidats):
        if not isinstance(c, dict):
            raise OpenAIError(f"alignement : piste #{i + 1} invalide")
        vides = [f for f in CHAMPS_CANDIDAT if not str(c.get(f) or "").strip()]
        if vides:
            raise OpenAIError(f"alignement : piste #{i + 1}, "
                              f"champ(s) vide(s) : {', '.join(vides)}")
        propres.append({f: str(c[f]).strip() for f in CHAMPS_CANDIDAT})

    try:
        note = float(brut.get("mute_test"))
    except (TypeError, ValueError):
        raise OpenAIError("alignement : 'mute_test' absent ou non numerique") from None
    if not 0.0 <= note <= 1.0:
        raise OpenAIError(f"alignement : 'mute_test' hors bornes ({note})")

    return {
        "understanding": str(brut["understanding"]).strip(),
        "candidates": propres,
        "chosen": str(brut["chosen"]).strip(),
        "why_chosen": str(brut["why_chosen"]).strip(),
        "mute_test": note,
        "image_prompt": prompts.enforce_style(str(brut["image_prompt"]).strip()),
        "animation_prompt": str(brut["animation_prompt"]).strip(),
    }


def _verifier(plan: dict) -> list[str]:
    """Ce que la machine peut controler, elle le controle."""
    out = []
    image = validator.own_part(plan["image_prompt"])
    anim = plan["animation_prompt"]

    if plan["mute_test"] < MIN_MUTE_TEST:
        out.append(f"the mute test scores {plan['mute_test']} — below "
                   f"{MIN_MUTE_TEST}. Go back to step 3 and choose an action a "
                   f"viewer reads faster with the sound off.")

    if len(image) < validator.MIN_IMAGE_PROMPT_CHARS:
        out.append(f"the image prompt is too short ({len(image)} characters "
                   f"before the art direction). Say where each element sits, "
                   f"the framing, the camera, the light, the materials.")

    if len(anim) < validator.MIN_ANIMATION_PROMPT_CHARS:
        out.append(f"the animation prompt is too short ({len(anim)} characters).")

    mots = validator.mots_du_concept(plan["chosen"])
    presents = [m for m in mots if validator.mot_present(m, image.lower())]
    if mots and len(presents) < len(mots) * PART_ACTION_EXIGEE:
        absents = [m for m in mots if m not in presents]
        out.append(f"the image prompt does not show the action you chose: "
                   f"{', '.join(absents[:5])} appear nowhere in it. The chosen "
                   f"action must BE the picture, not a note beside it.")

    if not any(m in anim.lower() for m in validator.PROGRESSION):
        out.append("the animation prompt does not say how the movement "
                   "progresses in time — where it starts, how it builds, where "
                   "it arrives. Use 'gradually', 'begins to', 'building', "
                   "'until'.")
    return out


def _correction(problemes: list[str]) -> str:
    lignes = ["Your previous JSON was rejected by an automatic check.",
              "Fix every point below and return the SAME JSON shape, corrected.",
              "Do not explain, do not apologise, return only the JSON.",
              ""]
    lignes += [f"- {p}" for p in problemes]
    return "\n".join(lignes)
