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

from difflib import SequenceMatcher

from . import config, prompts, validator
from .openai_client import OpenAIError, chat_json

#: Trois ouvertures, pour qu'il y ait un choix a faire.
MIN_OUVERTURES = 3
#: Une phrase par plan, exactement. Au run 44 le redacteur en a rendu douze
#: pour treize plans, et le storyboard a bouche le trou en inventant « Votre
#: experience musicale sans fil est subtile et fascinante » — un plan de
#: synthese, celui que la regle du dernier plan refuse. La tolerance d'une
#: phrase servait a etre gentil ; elle laissait passer un plan vide.
ECART_PHRASES = 0
#: En deca, ce n'est pas une chaine physique, c'est une affirmation.
MIN_MAILLONS = 3

#: Au-dela, « la raison » n'est qu'une paraphrase de la phrase verifiee.
PARAPHRASE = 0.7

#: Le plan d'ouverture tient en trois secondes ; la phrase qu'il porte doit
#: donc se dire en trois secondes. Au run 46 le redacteur a ecrit seize mots
#: — 5,3 mots par seconde, impossible a prononcer — parce qu'il ecrivait sans
#: savoir que l'ouverture serait courte.
MOTS_MAX_OUVERTURE = int(validator.DUREE_MAX_CROCHET * prompts.WORDS_PER_SECOND)

# Un maillon qui REMONTE le courant. Au run 45 la chaine partait du
# haut-parleur, remontait jusqu'au telephone en quatre maillons, puis
# repartait en avant : le spectateur suit une explication qui fait demi-tour.
SENS_INVERSE = ("provient", "proviennent", "provenir", "vient de", "viennent de",
                "reçoit", "reçoivent", "est issu", "sont issus", "résulte",
                "résultent", "est produit par", "sont produits par",
                "est généré par", "sont générés par", "est causé par",
                "en provenance de", "grâce à")

# Un maillon qui ne fait RIEN. « Les ecouteurs contiennent des haut-parleurs »
# decrit un objet, il n'enchaine rien sur rien.
SANS_ACTION = ("contient", "contiennent", "est composé", "sont composés",
               "possède", "possèdent", "comporte", "comportent",
               "est constitué", "sont constitués", "est équipé", "sont équipés",
               "dispose de", "disposent de", "se compose")

CHAMPS_OUVERTURE = ("sentence", "why_it_holds")
CHAMPS_OBJECTION = ("sentence", "checks_out", "objection", "fix")


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
        brut = chat_json(config.OPENAI_MODEL, messages, config.JETONS_TEXTE)
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


def relire(brut: object, duration: float, sentences: int) -> tuple[dict, list[str]]:
    """Un texte venu d'ailleurs, controle comme s'il sortait de la boucle.

    Le mode manuel colle la reponse de ChatGPT ici : elle passe par la meme
    mise en forme et les memes controles, hors ligne, sans un centime.
    """
    texte = _normaliser(brut)
    return texte, _problemes(texte, duration, sentences)


def consigne(problemes: list[str]) -> str:
    """La consigne de correction, telle que la boucle la renvoie."""
    return _correction(problemes)


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

    brutes = brut.get("objections") if isinstance(brut.get("objections"), list) else []
    objections = _objets(brut.get("objections"), CHAMPS_OBJECTION, "objection")

    # `_objets` ne garde que les champs texte : le numero de maillon se lit
    # sur l'entree d'origine.
    for i, (entree, brute) in enumerate(zip(objections, brutes, strict=True)):
        try:
            maillon = int(brute["link"])
        except (KeyError, TypeError, ValueError):
            raise OpenAIError(f"texte : objection #{i + 1}, 'link' absent ou "
                              f"non numerique") from None
        if not 1 <= maillon <= len(chaine):
            raise OpenAIError(f"texte : objection #{i + 1}, le maillon {maillon} "
                              f"n'existe pas (la chaine en a {len(chaine)})")
        entree["link"] = maillon

    return {
        "chain": chaine,
        "openings": ouvertures,
        "chosen_opening": str(brut["chosen_opening"]).strip(),
        "why_chosen": str(brut["why_chosen"]).strip(),
        "script": " ".join(str(brut["script"]).split()),
        "objections": objections,
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
        out.append(f"the script has {len(dites)} sentences, {sentences} were asked "
                   f"for — exactly one per shot. Not one more, not one fewer: a "
                   f"missing sentence forces the storyboard to invent a hollow shot "
                   f"to fill the count, and an extra one is a shot nobody will see.")

    mots = len([m for m in script.split() if m.strip()])
    attendus = int(duration * prompts.WORDS_PER_SECOND)
    if not attendus * 0.7 <= mots <= attendus * 1.3:
        out.append(f"the script runs to {mots} words for {duration} seconds; aim for "
                   f"about {attendus}, spoken at a natural pace.")

    if dites and len(dites[0].split()) > MOTS_MAX_OUVERTURE:
        out.append(f"the opening sentence runs to {len(dites[0].split())} words. It is "
                   f"spoken in under three seconds — the viewer decides to stay by then "
                   f"— so it holds {MOTS_MAX_OUVERTURE} words at most. Cut it down "
                   f"without losing what makes someone stay.")

    if texte["chosen_opening"] not in script:
        out.append("the script does not start with the opening you chose. The chosen "
                   "opening must be its first sentence, word for word.")

    # Le run 42 a repondu « aucune » six fois sur six. On n'exige pas qu'il
    # trouve un defaut — on lui interdit de se taire : il doit dire sur quoi
    # chaque phrase repose, et cette raison ne peut pas etre la phrase.
    paraphrases = [o["sentence"] for o in texte["objections"]
                   if SequenceMatcher(None, o["sentence"].lower(),
                                      o["checks_out"].lower()).ratio() > PARAPHRASE]
    if paraphrases:
        out.append(f"for {len(paraphrases)} sentence(s), 'checks_out' repeats the "
                   f"sentence instead of giving the reason it holds — starting with "
                   f"« {paraphrases[0]} ». Name the link of the chain it states and "
                   f"the physics that makes it true.")

    # Run 44 : sept maillons pour douze phrases. « Ce signal traverse l'air
    # jusqu'au recepteur » puis « ils captent alors le signal recu » — deux
    # phrases pour un seul evenement. Deux phrases sur le meme maillon disent
    # la meme chose deux fois, et le spectateur le sent.
    maillons = [o["link"] for o in texte["objections"]]
    doubles = sorted({m for m in maillons if maillons.count(m) > 1})
    if doubles:
        redites = [o["sentence"] for o in texte["objections"] if o["link"] in doubles]
        out.append(f"{len(redites)} sentences state links already stated — "
                   f"link(s) {', '.join(str(m) for m in doubles)}, starting with "
                   f"« {redites[0]} ». One sentence, one link, never the same link "
                   f"twice: say it once and move to the next link of the chain.")

    remontees = [m for m in texte["chain"]
                 if any(mot in m.lower() for mot in SENS_INVERSE)]
    if remontees:
        out.append(f"{len(remontees)} link(s) of the chain run BACKWARDS — starting "
                   f"with « {remontees[0]} ». A chain goes one way: each link says "
                   f"what a thing DOES to produce the next state. Write "
                   f"« l'émetteur envoie les données aux écouteurs », never "
                   f"« les données proviennent de l'émetteur ».")

    inertes = [m for m in texte["chain"]
               if any(mot in m.lower() for mot in SANS_ACTION)]
    if inertes:
        out.append(f"{len(inertes)} link(s) state what something CONTAINS instead of "
                   f"what it does — starting with « {inertes[0]} ». Composition is not "
                   f"a link: nothing happens, and nothing follows from it. Every link "
                   f"is an action that produces the next one.")

    if len(texte["chain"]) < sentences:
        out.append(f"the chain holds {len(texte['chain'])} links for {sentences} "
                   f"sentences. Each sentence states one link, so the chain needs at "
                   f"least {sentences} real, distinct links — or the subject does not "
                   f"carry {sentences} shots.")

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
