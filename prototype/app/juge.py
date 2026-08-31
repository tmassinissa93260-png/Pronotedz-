"""Le juge aveugle : quelqu'un qui n'a pas ecrit le plan, et qui n'entend rien.

Tout le reste du systeme se note lui-meme. L'agent d'alignement s'etait donne
0.85 au run 37 en degradant le plan — une note qu'on s'attribue ne vaut rien.

Ici, deux appels separes, et c'est la separation qui fait tout :

  1. REGARDER — le modele recoit les images de la video et RIEN d'autre. Ni la
     voix, ni le sujet, ni ce qu'il fallait comprendre. Il dit ce qu'il voit,
     ce qui change, et ce qu'il en comprend.
  2. COMPARER — un second appel, lui, connait l'intention, et dit si les deux
     se rejoignent.

Le premier ne peut donc pas repeter l'intention : il ne l'a jamais lue.
"""

from __future__ import annotations

from pathlib import Path

from . import analyzer, config, prompts
from .models import Shot
from .openai_client import OpenAIError, chat_json

#: En dessous, le plan ne se comprend pas sans le son.
COMPRIS = 0.7
#: En dessous, le plan est a refaire, pas a retoucher.
PERDU = 0.4

CHAMPS_VU = ("what_i_see", "what_happens", "what_i_understand")


def regarder(video: Path, into: Path) -> dict:
    """Ce qu'on comprend de la video quand on ne sait rien d'elle."""
    images = analyzer.sample_frames(video, into / "frames")
    contenu: list[dict] = [{"type": "text", "text": prompts.BLIND_USER}]
    contenu += [{"type": "image_url",
                 "image_url": {"url": analyzer.image_payload(i)}} for i in images]

    brut = chat_json(config.OPENAI_VISION_MODEL, [
        {"role": "system", "content": prompts.BLIND_SYSTEM},
        {"role": "user", "content": contenu},
    ])
    if not isinstance(brut, dict):
        raise OpenAIError("regard aveugle : la reponse doit etre un objet JSON")
    vides = [c for c in CHAMPS_VU if not str(brut.get(c) or "").strip()]
    if vides:
        raise OpenAIError(f"regard aveugle : champ(s) vide(s) : {', '.join(vides)}")
    return {
        **{c: str(brut[c]).strip() for c in CHAMPS_VU},
        "confidence": _note(brut.get("confidence"), "confidence"),
        "unclear": _liste(brut.get("unclear")),
    }


def comparer(shot: Shot, intention: str, vu: dict) -> dict:
    """L'intention et ce qui a ete compris se rejoignent-ils ?"""
    rapport = "\n".join(f"{c}: {vu[c]}" for c in CHAMPS_VU)
    brut = chat_json(config.OPENAI_MODEL, [
        {"role": "system", "content": prompts.VERDICT_SYSTEM},
        {"role": "user", "content": prompts.verdict_user(intention, shot.voice, rapport)},
    ])
    if not isinstance(brut, dict):
        raise OpenAIError("verdict : la reponse doit etre un objet JSON")
    for champ in ("verdict", "fix"):
        if not str(brut.get(champ) or "").strip():
            raise OpenAIError(f"verdict : '{champ}' vide")
    return {
        "understood": _note(brut.get("understood"), "understood"),
        "verdict": str(brut["verdict"]).strip(),
        "missing": _liste(brut.get("missing")),
        "fix": str(brut["fix"]).strip(),
    }


def juger(shot: Shot, video: Path, intention: str, into: Path) -> dict:
    """Le jugement complet d'un plan : ce qui a ete vu, puis le verdict."""
    vu = regarder(video, into)
    verdict = comparer(shot, intention, vu)
    return {"shot_id": shot.id, "intention": intention, "vu": vu, **verdict,
            "etat": etat(verdict["understood"])}


def etat(note: float) -> str:
    if note >= COMPRIS:
        return "compris"
    return "à refaire" if note < PERDU else "à retoucher"


def intention_du_plan(shot: Shot, alignement: dict | None) -> str:
    """Ce que le plan devait faire comprendre.

    L'agent d'alignement l'ecrit noir sur blanc ; sans lui, la fonction
    pedagogique du storyboard fait l'affaire.
    """
    if alignement and str(alignement.get("understanding") or "").strip():
        return str(alignement["understanding"]).strip()
    return shot.educational_function


# ---------------------------------------------------------------------------


def _note(valeur: object, label: str) -> float:
    try:
        note = float(valeur)
    except (TypeError, ValueError):
        raise OpenAIError(f"'{label}' absent ou non numerique") from None
    if not 0.0 <= note <= 1.0:
        raise OpenAIError(f"'{label}' hors bornes ({note})")
    return note


def _liste(valeur: object) -> list[str]:
    if isinstance(valeur, str):
        valeur = [valeur]
    if not isinstance(valeur, list):
        return []
    return [str(v).strip() for v in valeur if str(v).strip()]
