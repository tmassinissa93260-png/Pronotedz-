"""generate_storyboard() : le cerveau, avec sa boucle de correction.

Quand le validateur refuse, on ne rend pas la main : la liste exacte des
manquements repart chez OpenAI, plan par plan.
"""

from __future__ import annotations

import json
import time

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


def chat_json(model: str, messages: list[dict], max_tokens: int | None = None) -> dict:
    """Un appel JSON, avec le budget de sortie qu'il lui faut et pas plus.

    `max_tokens` est compte par le service dans la CADENCE : reserver 16 000
    jetons pour un appel qui en rendra 800 mange le quota de la minute pour
    rien. Le run 43 est mort la-dessus — 29 531 jetons demandes pour une
    limite de 30 000, dont 16 000 reserves d'avance.
    """
    if not model:
        raise OpenAIError(
            "aucun modele nomme pour cet appel.\n"
            "  Renseigne OPENAI_MODEL, ou OPENAI_VISION_MODEL pour l'analyse d'image.")
    budget = max_tokens or config.MAX_OUTPUT_TOKENS

    reponse = None
    for tentative in range(1, config.MAX_RATE_RETRIES + 2):
        try:
            reponse = client().chat.completions.create(
                model=model, messages=messages,
                response_format={"type": "json_object"}, max_tokens=budget)
            break
        except openai.AuthenticationError as exc:
            raise OpenAIError(f"cle refusee : {exc}") from exc
        except openai.NotFoundError as exc:
            raise OpenAIError(f"modele '{model}' indisponible : {exc}\n"
                              "  Choisis-en un autre via OPENAI_MODEL dans .env") from exc
        except openai.APIConnectionError as exc:
            raise OpenAIError(f"service injoignable : {exc}") from exc
        except openai.RateLimitError as exc:
            # La cadence se compte par minute : elle se libere toute seule.
            if tentative > config.MAX_RATE_RETRIES:
                raise OpenAIError(
                    f"cadence depassee apres {config.MAX_RATE_RETRIES} reprises : {exc}\n"
                    "  Baisse MAX_OUTPUT_TOKENS, ou demande moins de plans.") from exc
            attente = config.RATE_RETRY_SECONDS * tentative
            print(f"[CADENCE] limite atteinte, reprise dans {attente}s "
                  f"({tentative}/{config.MAX_RATE_RETRIES})", flush=True)
            time.sleep(attente)
        except openai.APIStatusError as exc:
            raise OpenAIError(f"le service a repondu {exc.status_code} : {exc}") from exc

    choix = reponse.choices[0]
    if choix.finish_reason == "length":
        raise OpenAIError(
            f"reponse coupee a {budget} jetons.\n"
            "  Augmente MAX_OUTPUT_TOKENS, ou demande moins de plans.")
    contenu = (choix.message.content or "").strip()
    if not contenu:
        raise OpenAIError("reponse vide")
    try:
        return json.loads(contenu)
    except json.JSONDecodeError as exc:
        raise OpenAIError(f"reponse non JSON : {exc}\n---\n{contenu[:500]}") from exc


def generate_storyboard(subject: str, duration: float, shot_count: int,
                        on_attempt=None, script: str = "") -> tuple[Storyboard, list]:
    """Genere puis fait corriger jusqu'a ce que le validateur accepte.

    `script` est la narration deja ecrite et verifiee par le redacteur : le
    storyboard la decoupe au lieu de l'ecrire en meme temps que tout le reste.
    """
    base = [
        {"role": "system", "content": prompts.STORYBOARD_SYSTEM},
        {"role": "user", "content": prompts.storyboard_user(subject, duration,
                                                            shot_count, script)},
    ]
    messages = list(base)
    budget = config.budget_storyboard(shot_count)
    storyboard, problems = None, []

    for tentative in range(1, config.MAX_REPAIR_ATTEMPTS + 2):
        brut = chat_json(config.OPENAI_MODEL, messages, budget)
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
            messages = base + [
                {"role": "assistant", "content": json.dumps(brut, ensure_ascii=False)},
                {"role": "user", "content": validator.correction_request(problems)}]
            continue

        for s in candidat.shots:
            s.image_prompt = prompts.enforce_style(s.image_prompt)

        storyboard = candidat
        problems = validator.validate(candidat, duration, shot_count)
        if on_attempt:
            on_attempt(tentative, problems)
        if not problems or tentative > config.MAX_REPAIR_ATTEMPTS:
            break

        # La liste repart de la consigne : au run 20 chaque tour empilait un
        # storyboard entier, et le troisieme depassait la cadence a lui seul.
        messages = base + [
            {"role": "assistant", "content": json.dumps(brut, ensure_ascii=False)},
            {"role": "user", "content": validator.correction_request(problems)}]

    if storyboard is None:
        raise OpenAIError("aucun storyboard exploitable")
    return storyboard, problems
