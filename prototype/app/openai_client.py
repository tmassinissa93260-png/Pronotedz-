"""generate_storyboard() : le cerveau, avec sa boucle de correction.

Quand le validateur refuse, on ne rend pas la main : la liste exacte des
manquements repart chez OpenAI, plan par plan.
"""

from __future__ import annotations

import json
import re

import openai

from . import config, prompts, validator
from .models import Storyboard, StoryboardError


class OpenAIError(RuntimeError):
    """Echec d'un appel OpenAI, avec un message lisible."""


def client() -> openai.OpenAI:
    if not config.OPENAI_API_KEY:
        raise OpenAIError(
            "OPENAI_API_KEY manquante dans .env\n"
            f"  Cree {config.ROOT_DIR / '.env'} a partir de .env.example :\n"
            "      OPENAI_API_KEY=sk-...\n"
            "  Une cle GROQ_API_KEY est acceptee a la place (API compatible).\n"
            "  La cle ne doit jamais etre ecrite dans le code."
        )
    kwargs = {"api_key": config.OPENAI_API_KEY, "timeout": config.OPENAI_TIMEOUT}
    if config.OPENAI_BASE_URL:
        kwargs["base_url"] = config.OPENAI_BASE_URL
    return openai.OpenAI(**kwargs)


def chat_json(model: str, messages: list[dict]) -> dict:
    if not model:
        raise OpenAIError(
            "aucun modele nomme pour cet appel.\n"
            "  Renseigne OPENAI_MODEL, ou OPENAI_VISION_MODEL pour l'analyse d'image.")
    try:
        reponse = client().chat.completions.create(
            model=model, messages=messages, response_format={"type": "json_object"})
    except openai.AuthenticationError as exc:
        raise OpenAIError(f"cle refusee : {exc}") from exc
    except openai.NotFoundError as exc:
        raise OpenAIError(f"modele '{model}' indisponible : {exc}\n"
                          "  Choisis-en un autre via OPENAI_MODEL dans .env") from exc
    except openai.APIConnectionError as exc:
        raise OpenAIError(f"service injoignable : {exc}") from exc
    except openai.RateLimitError as exc:
        raise OpenAIError(f"quota ou cadence depasse : {exc}") from exc
    except openai.APIStatusError as exc:
        raise OpenAIError(f"le service a repondu {exc.status_code} : {exc}") from exc

    contenu = (reponse.choices[0].message.content or "").strip()
    if not contenu:
        raise OpenAIError("reponse vide")
    try:
        return json.loads(contenu)
    except json.JSONDecodeError as exc:
        raise OpenAIError(f"reponse non JSON : {exc}\n---\n{contenu[:500]}") from exc


def _plans_vises(problems: list) -> set[int]:
    """Les plans nommes par les manquements, s'ils le sont tous."""
    vises = set()
    for p in problems:
        m = re.fullmatch(r"shot_(\d+)", p.where)
        if not m:
            return set()          # un manquement global : on corrige l'ensemble
        vises.add(int(m.group(1)))
    return vises


def _fusionner(brut: dict, corriges: object) -> dict:
    """Remet les plans corriges a leur place, sans toucher au reste."""
    if not isinstance(corriges, dict):
        return brut
    liste = corriges.get("shots")
    if not isinstance(liste, list):
        return brut
    par_id = {s.get("id"): s for s in liste if isinstance(s, dict)}
    fusion = dict(brut)
    fusion["shots"] = [par_id.get(s.get("id"), s) for s in brut.get("shots", [])]
    return fusion


def _demande_de_correction(brut: dict, problems: list) -> tuple[list, bool]:
    """Le message de correction, et s'il ne porte que sur quelques plans."""
    vises = _plans_vises(problems)
    partielle = bool(vises) and len(vises) < len(brut.get("shots", []))
    charge = ({"shots": [s for s in brut.get("shots", []) if s.get("id") in vises]}
              if partielle else brut)
    consignes = "\n".join(f"- {p.where}: {p.fix}" for p in problems)
    return ([{"role": "system", "content": prompts.STORYBOARD_SYSTEM},
             {"role": "user", "content": prompts.correction_user(charge, consignes,
                                                                 partielle)}],
            partielle)


def generate_storyboard(subject: str, duration: float, shot_count: int,
                        on_attempt=None) -> tuple[Storyboard, list]:
    """Genere puis fait corriger jusqu'a ce que le validateur accepte.

    Chaque tour de correction repart d'un message neuf : empiler la
    conversation renvoyait une copie entiere du storyboard a chaque fois, et
    a vingt plans le troisieme tour depassait la limite de jetons par minute.
    """
    messages = [
        {"role": "system", "content": prompts.STORYBOARD_SYSTEM},
        {"role": "user", "content": prompts.storyboard_user(subject, duration, shot_count)},
    ]
    storyboard, problems = None, []
    precedent: dict | None = None
    partielle = False

    for tentative in range(1, config.MAX_REPAIR_ATTEMPTS + 2):
        reponse = chat_json(config.OPENAI_MODEL, messages)
        brut = _fusionner(precedent, reponse) if partielle and precedent else reponse

        try:
            candidat = Storyboard.from_dict(brut)
        except StoryboardError as exc:
            problems = [validator.Problem("FORME", "storyboard", str(exc),
                                          f"The JSON was rejected: {exc}. Return the exact "
                                          f"shape asked for.")]
            if on_attempt:
                on_attempt(tentative, problems)
            if tentative > config.MAX_REPAIR_ATTEMPTS:
                raise OpenAIError(f"storyboard invalide apres correction : {exc}") from exc
            # Une reponse hors contrat ne peut pas servir de base : on repart
            # du dernier storyboard valide, ou du prompt complet s'il n'y en a
            # aucun.
            if precedent is None:
                partielle = False
                continue
            messages, partielle = _demande_de_correction(precedent, problems)
            continue

        for s in candidat.shots:
            s.image_prompt = prompts.enforce_style(s.image_prompt)
        brut["shots"] = [dict(b, image_prompt=s.image_prompt)
                         for b, s in zip(brut["shots"], candidat.shots, strict=False)]

        storyboard, precedent = candidat, brut
        problems = validator.validate(candidat, duration, shot_count)
        if on_attempt:
            on_attempt(tentative, problems)
        if not problems or tentative > config.MAX_REPAIR_ATTEMPTS:
            break

        messages, partielle = _demande_de_correction(brut, problems)

    if storyboard is None:
        raise OpenAIError("aucun storyboard exploitable")
    return storyboard, problems
