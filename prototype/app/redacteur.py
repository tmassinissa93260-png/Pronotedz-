"""Le texte, ecrit seul et verifie avant qu'un seul plan n'existe.

Le script etait un champ parmi dix-huit dans l'appel du storyboard : le modele
ecrivait la narration en meme temps que la visual bible, les six plans et les
douze prompts. La narration prenait ce qui restait de son attention, et ca se
lisait — « L'electricite commence par la capture de l'energie mecanique »,
puis, deux phrases plus loin, « la rotation de la turbine genere un champ
magnetique », qui est faux.

C'est la meme lecon que pour les images : ce qui partage l'attention perd.
Le texte est donc ecrit AVANT, seul, en quatre temps — la vraie chaine
physique, trois ouvertures, le script, puis l'objection d'un ingenieur
hostile — et la machine verifie ce qu'elle peut verifier avant de le laisser
passer au storyboard.
"""

from __future__ import annotations

from . import config, prompts, validator
from .openai_client import OpenAIError, chat_json

#: Trois ouvertures, pour qu'il y ait un choix a faire.
MIN_OUVERTURES = 3
#: Une phrase par plan, a une pres : le decoupage doit rester possible.
ECART_PHRASES = 1
#: En deca, ce n'est pas une chaine physique, c'est une affirmation.
MIN_MAILLONS = 3

CHAMPS_OUVERTURE = ("sentence", "why_it_holds")
CHAMPS_OBJECTION = ("sentence", "objection", "fix")


def ecrire(subject: str, duration: float, sentences: int,
           on_attempt=None) -> tuple[dict, list[str]]:
    """Le script et son dossier, ou le meilleur essai avec ce qui cloche."""
    base = [
        {"role": "system", "content": prompts.SCRIPT_SYSTEM},
        {"role": "user", "content": prompts.script_user(subject, duration, sentences)},
    ]

    meilleur, restants = None, ["aucune reponse exploitable"]
    for tentative in range(1, config.MAX_TEXT_ATTEMPTS + 1):
        messages = list(base)
        if meilleur is not None:
            messages.append({"role": "user", "content": _correction(restants)})
        brut = chat_json(config.OPENAI_MODEL, messages)
        try:
            texte = _normaliser(brut)
        except OpenAIError:
            if tentative == config.MAX_TEXT_ATTEMPTS:
                raise
            meilleur, restants = meilleur or {}, ["the JSON did not have the shape asked for"]
            continue

        problemes = _problemes(texte, duration, sentences)
        if on_attempt:
            on_attempt(tentative, problemes)
        if not problemes:
            return texte, []
        if meilleur is None or len(problemes) < len(restants):
            meilleur, restants = texte, problemes

    return meilleur, restants


# ---------------------------------------------------------------------------


def _normaliser(brut: object) -> dict:
    if not isinstance(brut, dict):
        raise OpenAIError("texte : la reponse doit etre un objet JSON")

    for champ in ("script", "chosen_opening", "why_chosen"):
        if not str(brut.get(champ) or "").strip():
            raise OpenAIError(f"texte : '{champ}' vide")

    chaine = [str(m).strip() for m in (brut.get("chain") or []) if str(m).strip()]
    if len(chaine) < MIN_MAILLONS:
        raise OpenAIError(f"texte : la chaine physique tient en {len(chaine)} maillon(s), "
                          f"il en faut au moins {MIN_MAILLONS}")

    ouvertures = _objets(brut.get("openings"), CHAMPS_OUVERTURE, "opening")
    if len(ouvertures) < MIN_OUVERTURES:
        raise OpenAIError(f"texte : il faut {MIN_OUVERTURES} ouvertures, "
                          f"une seule idee n'est pas un choix")

    return {
        "chain": chaine,
        "openings": ouvertures,
        "chosen_opening": str(brut["chosen_opening"]).strip(),
        "why_chosen": str(brut["why_chosen"]).strip(),
        "script": " ".join(str(brut["script"]).split()),
        "objections": _objets(brut.get("objections"), CHAMPS_OBJECTION, "objection"),
    }


def _objets(brut: object, champs: tuple[str, ...], label: str) -> list[dict]:
    if not isinstance(brut, list):
        raise OpenAIError(f"texte : '{label}s' manquant ou invalide")
    propres = []
    for i, entree in enumerate(brut):
        if not isinstance(entree, dict):
            raise OpenAIError(f"texte : {label} #{i + 1} invalide")
        vides = [c for c in champs if not str(entree.get(c) or "").strip()]
        if vides:
            raise OpenAIError(f"texte : {label} #{i + 1}, "
                              f"champ(s) vide(s) : {', '.join(vides)}")
        propres.append({c: str(entree[c]).strip() for c in champs})
    return propres


def _problemes(texte: dict, duration: float, sentences: int) -> list[str]:
    """Ce que la machine sait verifier d'un texte : sa forme, pas sa verite.

    La verite, elle, est le travail de l'etape 4 du prompt — l'objection de
    l'ingenieur hostile — et celui de l'humain qui lit le dossier.
    """
    out = []
    script = texte["script"]
    dites = validator.phrases(script)

    if abs(len(dites) - sentences) > ECART_PHRASES:
        out.append(f"the script has {len(dites)} sentences, {sentences} were asked for "
                   f"— one per shot, so the cut into shots stays possible.")

    mots = len([m for m in script.split() if m.strip()])
    attendus = int(duration * prompts.WORDS_PER_SECOND)
    if not attendus * 0.7 <= mots <= attendus * 1.3:
        out.append(f"the script runs to {mots} words for {duration} seconds; aim for "
                   f"about {attendus}, spoken at a natural pace.")

    if texte["chosen_opening"] not in script:
        out.append("the script does not start with the opening you chose. The chosen "
                   "opening must be its first sentence, word for word.")

    if len(texte["objections"]) < len(dites):
        out.append(f"you examined {len(texte['objections'])} sentences out of "
                   f"{len(dites)}. Re-read EVERY sentence as a hostile engineer, and "
                   f"say 'aucune' where there is nothing to object to.")

    # Les memes controles que sur le storyboard : le texte n'a pas a etre
    # juge deux fois selon deux regles.
    out += [p.fix for p in validator._texte(_plateau(script))]
    return out


class _plateau:
    """Le minimum que `_texte` regarde : un objet qui porte un script."""

    def __init__(self, script: str):
        self.script = script


def _correction(problemes: list[str]) -> str:
    lignes = ["Your previous JSON was rejected by an automatic check.",
              "Fix every point below and return the SAME JSON shape, corrected.",
              "Do not explain, do not apologise, return only the JSON.",
              ""]
    lignes += [f"- {p}" for p in problemes]
    return "\n".join(lignes)
