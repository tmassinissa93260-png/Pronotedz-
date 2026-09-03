"""Le mode manuel : les mêmes prompts, collés à la main dans ChatGPT.

L'API se paie au jeton, et un compte vide arrête tout. L'interface web de
ChatGPT, elle, ne coûte rien de plus que l'abonnement — et les trois étapes
qui écrivent (le texte, le storyboard, l'alignement) ne sont rien d'autre
qu'un prompt qui part et un JSON qui revient. Rien n'oblige ce JSON à passer
par l'API.

Ce module ne fait donc que deux choses :

  · `prompt_*` rend le prompt EXACT que l'API aurait envoyé — pas une version
    simplifiée, pas un résumé : le même texte, à coller tel quel.
  · `relire_*` reprend la réponse collée en retour et lui applique LES MÊMES
    contrôles que la boucle automatique, hors ligne et sans un centime. Ce
    qui cloche revient sous la forme d'une consigne à recoller dans la même
    conversation, exactement comme la boucle le faisait.

Ce qu'on perd en manuel : les tours de correction ne s'enchaînent plus tout
seuls, c'est l'humain qui fait l'aller-retour. Ce qu'on ne perd pas : les
contrôles, qui sont locaux, et qui sont le vrai travail.
"""

from __future__ import annotations

import json

from . import aligner, prompts, redacteur, validator
from .models import Shot, Storyboard
from .openai_client import OpenAIError

#: Les étapes qui n'ont besoin que de texte — donc faisables à la main.
ETAPES = ("texte", "storyboard", "aligner")

#: Ce que ChatGPT ne devine pas et que l'API imposait : le format de sortie.
FORMAT = (
    "Answer with the JSON object only. No prose before it, no prose after it, "
    "no explanation, no markdown heading. A single JSON object."
)


def prompt_texte(subject: str, duration: float, sentences: int) -> str:
    """L'étape 1 : la narration seule."""
    return _coller(prompts.SCRIPT_SYSTEM,
                   prompts.script_user(subject, duration, sentences))


def prompt_storyboard(subject: str, duration: float, shots: int,
                      script: str = "") -> str:
    """L'étape 2 : le découpage, la visual bible et les deux prompts par plan."""
    return _coller(prompts.STORYBOARD_SYSTEM,
                   prompts.storyboard_user(subject, duration, shots, script))


def prompt_alignement(sb: Storyboard, shot: Shot) -> str:
    """L'étape 3, un plan à la fois : l'image doit EXPLIQUER la phrase."""
    return _coller(prompts.ALIGNMENT_SYSTEM, aligner.demande(sb, shot))


# ---------------------------------------------------------------------------
# La réponse revient — et elle est contrôlée exactement comme celle de l'API
# ---------------------------------------------------------------------------


def relire_texte(brut: object, duration: float, sentences: int) -> tuple[dict, list[str]]:
    return redacteur.relire(brut, duration, sentences)


def relire_storyboard(brut: object, duration: float,
                      shots: int) -> tuple[Storyboard, list]:
    """Le storyboard collé, mis en forme et validé — le validateur complet."""
    sb = Storyboard.from_dict(brut)
    sb.style_directive = prompts.STYLE_DIRECTIVE
    for s in sb.shots:
        s.image_prompt = prompts.enforce_style(s.image_prompt)
    return sb, validator.validate(sb, duration, shots)


def relire_alignement(sb: Storyboard, shot: Shot,
                      brut: object) -> tuple[dict, list[str]]:
    return aligner.relire(sb, shot, brut)


def consigne(etape: str, problemes: list) -> str:
    """La consigne de correction à recoller dans la MÊME conversation."""
    if etape == "storyboard":
        return validator.correction_request(problemes)
    if etape == "texte":
        return redacteur.consigne(problemes)
    return aligner.consigne(problemes)


# ---------------------------------------------------------------------------


def json_colle(texte: str) -> object:
    """Le JSON d'une réponse copiée à la main, clôtures markdown comprises.

    On ne demande pas à quelqu'un qui copie sur un téléphone de nettoyer la
    réponse : ChatGPT entoure souvent le JSON de ```json … ```, et parfois
    d'une phrase de politesse. On prend le premier objet et on ignore le
    reste.
    """
    brut = (texte or "").strip()
    if not brut:
        raise OpenAIError("réponse vide : colle le JSON rendu par ChatGPT.")

    debut, fin = brut.find("{"), brut.rfind("}")
    if debut == -1 or fin <= debut:
        raise OpenAIError("aucun objet JSON dans ce qui a été collé.\n"
                          "  Recopie la réponse depuis la première accolade { "
                          "jusqu'à la dernière }.")
    try:
        return json.loads(brut[debut:fin + 1])
    except json.JSONDecodeError as exc:
        raise OpenAIError(f"le JSON collé est incomplet ou abîmé : {exc}\n"
                          "  C'est presque toujours une copie coupée : ChatGPT a "
                          "peut-être arrêté la réponse en route.\n"
                          "  Redemande-lui « continue » et recolle la réponse "
                          "entière.") from exc


def fiche(titre: str, prompt: str, quoi_faire: str) -> str:
    """Le prompt, prêt à copier depuis un téléphone.

    GitHub pose un bouton « copier » sur les blocs de code : c'est la seule
    façon de sortir mille lignes d'un prompt d'un écran de téléphone sans le
    sélectionner à la main.
    """
    return "\n".join([f"# {titre}", "", quoi_faire, "", _bloc(prompt), ""])


def _bloc(texte: str) -> str:
    """Un bloc de code dont la clôture est plus longue que ce qu'il contient."""
    plus_long = max((len(m) for m in _accents_graves(texte)), default=0)
    cloture = "`" * max(3, plus_long + 1)
    return f"{cloture}\n{texte}\n{cloture}"


def _accents_graves(texte: str) -> list[str]:
    suites, courante = [], ""
    for c in texte + " ":
        if c == "`":
            courante += c
            continue
        if courante:
            suites.append(courante)
            courante = ""
    return suites


def _coller(systeme: str, demande: str) -> str:
    """Système et demande réunis : l'interface web n'a pas de rôle système."""
    return "\n".join([systeme.strip(), "", demande.strip(), "", FORMAT])
