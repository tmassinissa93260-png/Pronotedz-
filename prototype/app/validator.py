"""Les verifications imposees avant de rendre un storyboard.

Chaque probleme porte sa consigne de correction, adressee a OpenAI : le
validateur ne dit pas seulement non, il dit quoi refaire.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import (
    COLOR_NOTION,
    EXPLICATION_FIELDS,
    MAX_COLOR_NOTIONS,
    MIN_COLOR_NOTIONS,
    QUALITY_AXES,
    Storyboard,
)
from .prompts import STYLE_FINGERPRINT, STYLE_PAR_DEFAUT

#: Le spectateur tranche vers 3,1 s sur un fil vertical, et la moitie de ceux
#: qui partent sont partis avant. Le plan d'ouverture ne peut pas s'etaler.
DUREE_MAX_CROCHET = 3.0

MIN_WORDS_PER_SECOND = 1.8
MAX_WORDS_PER_SECOND = 4.0
MIN_QUALITY = 0.8
MIN_IMAGE_PROMPT_CHARS = 260
MIN_ANIMATION_PROMPT_CHARS = 120
DURATION_TOLERANCE_S = 0.5

# CONDITION : le prompt photo doit dire ou est quoi, comment c'est cadre,
# sous quelle lumiere, en quels materiaux.
SPECIFICITY_FAMILIES = {
    "cadrage": ("shot", "framing", "close-up", "closeup", "wide", "medium", "macro", "view"),
    "camera": ("camera", "angle", "lens", "perspective", "eye level", "low angle", "high angle"),
    "position": ("left", "right", "centre", "center", "beneath", "under", "above", "behind",
                 "front", "rear", "between", "along", "inside", "mounted", "positioned",
                 "toward", "towards", "into", "around"),
    "lumiere": ("light", "lighting", "lit", "illuminat", "volumetric", "backlight", "rim"),
    "materiaux": ("material", "metal", "aluminium", "aluminum", "copper", "composite",
                  "matte", "paint", "plastic", "steel", "glass", "rubber"),
}

# Mots qui signalent un phenomene invisible rendu visible.
PHENOMENE = ("energy", "current", "electric", "flow", "stream", "pulse", "particle",
             "field", "charge", "power", "signal", "heat")

# Une couleur qui qualifie l'ECLAIRAGE ou le decor est de la direction
# artistique, pas une notion pedagogique : « cinematic blue lighting » est
# impose par le style de reference, et personne ne peut le faire bouger.
AMBIANCE = ("lighting", "light on", "light from", "backlight", "rim light",
            "key light", "ambient", "haze", "backdrop", "environment", "studio",
            "atmosphere", "tone", "cast", "background", "wash")

# Verbes de mouvement qui font vraiment bouger la chose.
MOUVEMENT = ("flow", "travel", "move", "pulse", "circulat", "rotat", "spin", "turn",
             "illuminat", "light up", "glow", "advance", "progress", "accelerat",
             "reverse", "enter", "exit", "rise", "propagat", "sweep")

# MULTI-MOTION : les familles de mouvement physique. Une animation qui n'en
# porte qu'une seule ne donne au generateur qu'une chose a faire bouger, et
# il comble le temps avec la camera — c'est ce qu'on a vu sur les plans 1 et 2.
FAMILLES_MOUVEMENT = {
    "flux": ("flow", "travel", "stream", "propagat", "sweep", "circulat", "surge"),
    "rotation": ("rotat", "spin", "turn", "revolv"),
    "illumination": ("illuminat", "light up", "lights up", "lighting up", "glow",
                     "brighten", "pulse", "pulsing", "pulses"),
    "translation": ("advance", "moves forward", "moving forward", "roll", "drive",
                    "accelerat", "decelerat", "slows", "propel", "moving the",
                    "moves the", "pushes", "pushing"),
    "inversion": ("reverse", "reversing", "reverses", "returns", "back into"),
    "transfert": ("enter", "enters", "entering", "exit", "reach", "reaches",
                  "reaching", "arriv", "leaving", "leaves"),
}
MIN_FAMILLES_MOUVEMENT = 2

# Une chaine mecanique — le rotor tourne, la transmission tourne, les roues
# tournent — est bien PLUSIEURS mouvements coordonnes, meme si les trois
# appartiennent a la meme famille. On compte donc aussi ce qui bouge.
COMPOSANTS_MOBILES = ("rotor", "stator", "gear", "transmission", "drivetrain",
                      "axle", "wheel", "tyre", "tire", "hub", "cell", "pack",
                      "cable", "busbar", "motor", "battery", "disc", "caliper",
                      "car", "vehicle", "chassis", "piston", "crankshaft")
MIN_COMPOSANTS_MOBILES = 2

# Une piece n'est pas « en mouvement » parce qu'un flux part d'elle, passe par
# elle ou va vers elle : « travels along the cables from the battery toward the
# motor » ne fait bouger que le flux. Ces prepositions marquent l'origine, le
# trajet ou la destination — pas l'acteur du mouvement.
ROLE_PASSIF = ("from", "along", "through", "via", "out of", "between", "across",
               "toward", "towards", "into", "back to", "onto", "up to", "down to")

# Les mouvements doivent etre lies, pas juxtaposes : le prompt doit dire le
# lien a voix haute.
LIAISON = ("as ", "then", "which", "causing", "so that", "in turn", "powered by",
           "driven by", "while", "making", "makes", "until", "and then", "once ",
           "sets off", "setting off", "propel", "driving", "sending", "pushing",
           "resulting", "moving the", "so the", "before")

# Un flux doit aller QUELQUE PART : sans direction lisible, le spectateur ne
# peut pas savoir dans quel sens l'energie circule.
DIRECTION = ("toward", "towards", "into", "out of", "from", "back to", "along",
             "through", "up to", "down to", "reverses", "reversing", "outward",
             "inward", "forward", "returns", "leaving", "entering")

# PROGRESSION DANS LE TEMPS : sans elle le generateur rend un instant fige qui
# derive, pas une scene qui evolue. C'est ce que reclament tous les guides
# image-to-video, et c'est ce qui manquait a nos prompts.
PROGRESSION = ("gradual", "progressiv", "slowly", "steadily", "building",
               "builds", "increasingly", "accelerat", "decelerat", "begins to",
               "starts to", "continuously", "over the course", "one after",
               "finally", "until", "little by little")

# Un dernier plan qui RESUME n'a plus rien a animer. Trois sujets de suite ont
# fini sur un plan de synthese, et c'etait a chaque fois le plan le plus faible.
RESUME = ("résum", "resum", "synthès", "synthes", "récapitul", "recapitul",
          "bilan", "vue d'ensemble", "summar", "overview", "recap", "wrap up",
          "to conclude", "conclusion")

# ---------------------------------------------------------------------------
# LE TEXTE
#
# Le validateur avait dix-huit controles sur l'image et presque aucun sur la
# narration : le debit, et deux phrases identiques. Le run 41 est passe sans
# un manquement avec « L'electricite commence par la capture de l'energie
# mecanique » en ouverture, et une phrase fausse au milieu.
# ---------------------------------------------------------------------------

# Une premiere phrase qui pourrait ouvrir n'importe quelle video sur
# n'importe quel sujet n'ouvre rien du tout.
OUVERTURE_PLATE = (
    "est un ", "est une ", "sont des ", "désigne", "s'appelle", "se définit",
    "commence par", "il existe", "on utilise", "on appelle", "nous allons",
    "on va voir", "dans cette vidéo", "essentiel", "essentielle", "important",
    "dans notre vie", "au quotidien", "de nos jours", "aujourd'hui,",
    "depuis toujours", "partout autour", "joue un rôle",
)

# Le passif efface celui qui agit. « les aubes sont poussées par la vapeur »
# raconte la meme chose que « la vapeur pousse les aubes », en cachant la
# vapeur — or c'est elle qu'il faut voir a l'image.
AUXILIAIRE = re.compile(
    r"\b(?:est|sont|était|étaient|a été|ont été|sera|seront)\s+"
    r"([a-zà-ÿ]+)(?:\s+([a-zà-ÿ]+))?")

# Un participe passe francais : au moins quatre lettres, et une terminaison
# qui n'appartient qu'a lui.
PARTICIPE = re.compile(r"^[a-zà-ÿ]{4,}(?:ée|ées|és|é|ies|ie|ues|ue|us|ises|ise|"
                       r"ites|ite|is|it)$")

# Ces mots-la se glissent entre l'auxiliaire et le participe — et « ensuite »
# se termine comme un participe sans en etre un.
ADVERBES = frozenset((
    "ensuite", "alors", "puis", "également", "aussi", "enfin", "ainsi", "donc",
    "souvent", "toujours", "déjà", "encore", "parfois", "désormais",
    "maintenant", "directement", "immédiatement", "progressivement",
    "généralement", "naturellement", "simplement", "rapidement", "lentement",
    "très", "plus", "bien", "trop", "peu", "assez", "tout", "tous",
))


def est_passive(phrase: str) -> bool:
    """« est transportée » oui ; « est ensuite transportée » aussi ;
    « est essentielle », « est très rapide » et « est un moteur » non."""
    for premier, second in AUXILIAIRE.findall(phrase.lower()):
        if premier not in ADVERBES and PARTICIPE.match(premier):
            return True
        if premier in ADVERBES and second and PARTICIPE.match(second):
            return True
    return False

# Une phrase qui commence par « cette energie », « ce processus » ou « elle »
# ne nomme personne : elle renvoie a la precedente. Enchainer trois de ces
# phrases, c'est expliquer sans jamais montrer qui agit — et l'image, elle, a
# besoin d'un acteur physique a filmer.
ANAPHORE = re.compile(
    r"^(?:enfin,?\s+|puis,?\s+|ensuite,?\s+|alors,?\s+|ainsi,?\s+)?"
    r"(?:(?:ce|cet|cette|ces)\s+(?:énergie|processus|système|mécanisme|"
    r"phénomène|principe|dispositif|élément|ensemble|opération|transformation)"
    r"|cela|ceci|ça|celui-ci|celle-ci|il|elle|ils|elles)\b")

# Des mots qui promettent sans montrer. Un seul passe ; deux, c'est un style.
VAGUE = ("notamment", "principalement", "généralement", "différentes formes",
         "diverses", "plusieurs types", "certains types", "permet de",
         "permettent de", "essentiel", "quotidien", "moderne", "efficacement",
         "de manière", "il est possible", "on peut dire")

# Mouvements de camera : ils ne comptent pas comme mouvement pedagogique.
CAMERA = ("camera", "zoom", "dolly", "pan", "tilt", "orbit", "push in", "pull out",
          "tracking shot")

# Composant nomme -> mouvement attendu si l'image le met en avant.
COMPOSANT_MOUVEMENT = {
    "rotor": ("rotat", "spin", "turn"),
    "stator": ("rotat", "spin", "turn", "stationary", "fixed", "still"),
    "crankshaft": ("rotat", "spin", "turn"),
    "piston": ("move", "travel", "stroke", "down", "up"),
    "gear": ("rotat", "mesh", "turn"),
    "transmission": ("rotat", "turn", "transmit", "carr"),
    "wheel": ("rotat", "spin", "turn"),
    "cell": ("illuminat", "light", "glow", "charge", "flow"),
}

# REGLE « L'IMAGE EST LE PREMIER PLAN DE L'ANIMATION » : si l'animation fait
# bouger un de ces objets, l'image doit deja le montrer. On raisonne par
# famille : un prompt qui cadre le stator et le rotor montre bien le moteur.
FAMILLES = (
    ("battery", "cell", "pack", "module"),
    ("motor", "engine", "rotor", "stator", "winding"),
    ("cable", "wiring", "busbar", "harness"),
    ("wheel", "tyre", "tire", "hub"),
    ("gear", "transmission", "drivetrain", "axle"),
    ("brake", "caliper", "disc"),
    ("inverter", "controller"),
    ("piston", "crankshaft", "cylinder"),
)

# « vers la batterie » ne met pas la batterie dans le cadre. Un objet nomme
# seulement comme destination d'un flux n'est jamais montre : c'est le defaut
# constate en production sur le plan du freinage regeneratif.
DESTINATION = ("toward", "towards", "into", "back to", "up to", "down to", "onto",
               "reaches", "reaching", "arrives at", "heading to", "returns to",
               "travels to", "flowing to", "back into")
FENETRE_DESTINATION = 30

# L'ENERGIE NE TOURNE PAS EN ROND. En fonctionnement normal la chaine est a
# sens unique — batterie, onduleur, moteur, transmission, roues — et le
# freinage regeneratif la remonte. Une boucle est scientifiquement fausse, et
# elle efface la direction que le spectateur doit lire.
BOUCLE = ("cyclical", "cyclically", "in a loop", "a loop", "continuous loop",
          "closed loop", "energy cycle", "cycle of energy", "loops back", "endless")

# L'energie n'est ni de la fumee ni des paillettes.
DECORATIF = ("smoke", "sparkle", "glitter", "lens flare", "floating particle",
             "randomly", "magical", "fairy")

# La voiture est sombre, presque noire, et elle ne change pas de plan en plan.
VEHICULE_NOMS = ("car", "sedan", "vehicle", "bodywork", "body", "chassis", "paint")
TEINTE_CLAIRE = ("white", "silver", "ivory", "pearl", "beige", "cream", "light grey",
                 "light gray")

# Mots trop generiques pour ancrer quoi que ce soit dans le prompt photo.
GENERIQUES = {"the", "a", "an", "and", "or", "with", "its", "that", "this", "which",
              "of", "in", "on", "to", "from", "for", "by", "at", "into", "through",
              "along", "as", "is", "are", "it", "their", "these", "those", "other",
              "each", "one", "main", "primary", "visible", "clearly", "element",
              "elements", "object", "objects", "component", "components", "part",
              "parts", "view", "shot", "image", "animation", "system",
              "whole", "entire", "full", "complete", "overall", "general"}

# Le vehicule entier n'est pas un objet precis : un plan qui n'a rien de plus
# precis a montrer que « la voiture » ne montre aucune information.
VEHICULE = {"car", "vehicle", "automobile", "ev"}

# Les champs qui NOMMENT peuvent etre courts ; ceux qui DECRIVENT ne peuvent pas.
LONGUEUR_MINIMALE = {
    "physical_element": 8,
    "secondary_elements": 8,
}
LONGUEUR_PAR_DEFAUT = 15

# CONDITION : ce qui est dit doit etre montre.
SEMANTIQUE = {
    "batterie": ("battery", "cell", "pack", "module"),
    "cellule": ("cell",),
    "moteur": ("motor", "engine", "rotor", "stator", "winding"),
    "rotor": ("rotor",),
    "stator": ("stator",),
    "roue": ("wheel", "tyre", "tire", "hub"),
    "câble": ("cable", "wiring", "busbar", "harness"),
    "cable": ("cable", "wiring", "busbar", "harness"),
    "onduleur": ("inverter", "power electronics"),
    "électronique": ("electronic", "inverter", "controller", "module"),
    "electronique": ("electronic", "inverter", "controller", "module"),
    "accélérateur": ("pedal", "accelerator", "throttle"),
    "accelerateur": ("pedal", "accelerator", "throttle"),
    "pédale": ("pedal",),
    "pedale": ("pedal",),
    "transmission": ("transmission", "gear", "drivetrain", "axle"),
    "engrenage": ("gear",),
    "piston": ("piston",),
    "vilebrequin": ("crankshaft",),
    "freinage": ("brake", "regenerat"),
}


@dataclass
class Problem:
    code: str
    where: str
    message: str
    fix: str

    def __str__(self) -> str:
        return f"[{self.code}] {self.where} : {self.message}"


def validate(sb: Storyboard, duration: float, shot_count: int) -> list[Problem]:
    problems: list[Problem] = []
    problems += _plans(sb, shot_count)
    problems += _duree(sb, duration)
    problems += _debit(sb)
    problems += _rythme(sb)
    problems += _fonction(sb)
    problems += _style(sb)
    problems += _precision(sb)
    problems += _continuite(sb)
    problems += _alignement(sb)
    problems += _progression(sb)
    problems += _grammaire_visuelle(sb)
    problems += _correspondance(sb)
    problems += _explication(sb)
    problems += _ancrage(sb)
    problems += _dynamique(sb)
    problems += _physique(sb)
    problems += _texte(sb)
    problems += _temporel(sb)
    problems += _dernier_plan(sb)
    problems += _code_couleur(sb)
    problems += _qualite(sb)
    return problems


# --- nombre de plans, duree, debit ------------------------------------------


def _plans(sb: Storyboard, attendu: int) -> list[Problem]:
    if len(sb.shots) == attendu:
        return []
    return [Problem("PLANS", "storyboard", f"{len(sb.shots)} plan(s) au lieu de {attendu}",
                    f"Return exactly {attendu} shots, ids 1 to {attendu}.")]


def _duree(sb: Storyboard, attendue: float) -> list[Problem]:
    out = []
    if abs(sb.total_duration - attendue) > DURATION_TOLERANCE_S:
        out.append(Problem("DUREE", "storyboard",
                           f"somme des plans = {sb.total_duration}s au lieu de {attendue}s",
                           f"The durations must sum to exactly {attendue}."))
    for s in sb.shots:
        if s.duration_seconds <= 0:
            out.append(Problem("DUREE", s.slug, f"duree invalide : {s.duration_seconds}",
                               f"Shot {s.id} needs a positive duration_seconds."))
    return out


def _rythme(sb: Storyboard) -> list[Problem]:
    """Le premier plan est la decision, et les durees doivent decider.

    Sur un fil vertical le spectateur tranche vers trois secondes, et la
    moitie de ceux qui partent sont partis avant. Un premier plan de quatre
    secondes couvre donc toute la fenetre de decision avec une seule image.

    Le banc dit que ces deux controles s'allument sur les vingt-quatre
    plateaux passes : les durees y sont rigoureusement identiques partout.
    Ce n'est pas un defaut qu'on decouvre, c'est une exigence qu'on ajoute,
    et on sait ce qu'elle coute.
    """
    out = []
    if len(sb.shots) < 2:
        return out

    premier = sb.shots[0]
    if premier.duration_seconds > DUREE_MAX_CROCHET:
        out.append(Problem("RYTHME", premier.slug,
                           f"le plan d'ouverture dure {premier.duration_seconds:g}s, "
                           f"la decision se prend vers {DUREE_MAX_CROCHET:g}s",
                           f"Shot 1 is the decision, not a shot: bring it to "
                           f"{DUREE_MAX_CROCHET:g} seconds or less, and give the seconds "
                           f"you free to a shot that has a cause and its effect to show. "
                           f"Half the viewers who leave are gone before three seconds."))

    durees = {s.duration_seconds for s in sb.shots}
    if len(durees) == 1:
        out.append(Problem("RYTHME", "storyboard",
                           f"les {len(sb.shots)} plans durent tous "
                           f"{sb.shots[0].duration_seconds:g}s",
                           "Identical durations everywhere mean no link was judged more "
                           "worth the time than another. A shot that shows one thing "
                           "takes less time than a shot that shows a cause producing an "
                           "effect. Decide, and let the durations say it."))
    return out


def _debit(sb: Storyboard) -> list[Problem]:
    out = []
    for s in sb.shots:
        taux = s.words_per_second
        cible = int(s.duration_seconds * 2.7)
        if taux < MIN_WORDS_PER_SECOND:
            out.append(Problem("DEBIT", s.slug,
                               f"{s.word_count} mots pour {s.duration_seconds}s "
                               f"({taux:.1f} mot/s) : le plan serait vide",
                               f"Shot {s.id}: write about {cible} words, not {s.word_count}. "
                               f"Say more about the causal link, do not pad."))
        elif taux > MAX_WORDS_PER_SECOND:
            out.append(Problem("DEBIT", s.slug,
                               f"{s.word_count} mots pour {s.duration_seconds}s "
                               f"({taux:.1f} mot/s) : impossible a prononcer",
                               f"Shot {s.id}: shorten the narration to about {cible} words."))
    return out


def _fonction(sb: Storyboard) -> list[Problem]:
    out = []
    ids = [s.id for s in sb.shots]
    if ids != list(range(1, len(sb.shots) + 1)):
        out.append(Problem("IDS", "storyboard", f"ids non contigus : {ids}",
                           f"Number the shots 1 to {len(sb.shots)} in order."))
    for s in sb.shots:
        if len(s.educational_function) < 20:
            out.append(Problem("FONCTION", s.slug,
                               "educational_function trop vague pour justifier le plan",
                               f"Shot {s.id}: state in one full sentence what the viewer "
                               f"understands after this shot that no other shot provides."))
    return out


def _style(sb: Storyboard) -> list[Problem]:
    return [Problem("STYLE", s.slug, "direction artistique absente du prompt photo",
                    f"Shot {s.id}: end image_prompt with the mandatory art direction "
                    f"sentence, copied verbatim.")
            for s in sb.shots if STYLE_FINGERPRINT.lower() not in s.image_prompt.lower()]


# --- precision et continuite ------------------------------------------------


def own_part(image_prompt: str) -> str:
    """Le prompt photo prive de la direction artistique commune.

    On COUPE a la signature : la supprimer d'abord rendrait la coupe
    introuvable et laisserait la fin de la phrase de style passer pour du
    contenu propre au plan.
    """
    debut = image_prompt.lower().find(STYLE_FINGERPRINT.lower())
    return image_prompt if debut < 0 else image_prompt[:debut]


def familles_absentes(image_prompt: str) -> list[str]:
    """Ce dont le prompt photo ne dit rien : cadrage, camera, position...

    L'agent d'alignement s'en sert aussi : en reecrivant un prompt autour de
    l'action choisie, il ne doit pas laisser tomber ce que le storyboard
    exigeait deja.
    """
    bas = own_part(image_prompt).lower()
    return [nom for nom, mots in SPECIFICITY_FAMILIES.items()
            if not any(m in bas for m in mots)]


def _precision(sb: Storyboard) -> list[Problem]:
    out = []
    for s in sb.shots:
        propre = own_part(s.image_prompt)
        if len(propre.strip()) < MIN_IMAGE_PROMPT_CHARS:
            out.append(Problem("PRECISION", s.slug,
                               f"prompt photo trop general ({len(propre.strip())} caracteres "
                               f"hors direction artistique)",
                               f"Shot {s.id}: state the subject, the phenomenon shown, the "
                               f"pedagogical elements and their colour, where each sits, the "
                               f"framing, the camera angle, the depth, the lighting, the "
                               f"materials, what to preserve and what is forbidden."))
        absentes = familles_absentes(s.image_prompt)
        if absentes:
            out.append(Problem("PRECISION", s.slug,
                               f"le prompt photo ne dit rien sur : {', '.join(absentes)}",
                               f"Shot {s.id}: the image_prompt must explicitly state "
                               f"{', '.join(absentes)}."))
        if len(s.animation_prompt.strip()) < MIN_ANIMATION_PROMPT_CHARS:
            out.append(Problem("PRECISION", s.slug,
                               f"prompt d'animation trop court "
                               f"({len(s.animation_prompt.strip())} caracteres)",
                               f"Shot {s.id}: say which element moves, in which direction, at "
                               f"what speed, what stays still, and what must not deform."))
    return out


def _continuite(sb: Storyboard) -> list[Problem]:
    ancres = _ancres(sb)
    if not ancres:
        return []
    return [Problem("CONTINUITE", s.slug,
                    "le prompt photo ne reprend rien de la visual_bible",
                    f"Shot {s.id}: restate the subject, the environment and the materials "
                    f"fixed by visual_bible, so every shot shows the same object.")
            for s in sb.shots if not any(a in own_part(s.image_prompt).lower() for a in ancres)]


def _ancres(sb: Storyboard) -> list[str]:
    source = " ".join([sb.visual_bible.vehicle, sb.visual_bible.main_subject,
                       sb.visual_bible.environment]).lower()
    candidats = ("white", "silver", "black", "sedan", "hatchback", "compact", "suv", "coupe",
                 "studio", "dark", "grey", "gray", "blue", "navy", "concrete")
    return [c for c in candidats if c in source]


def _alignement(sb: Storyboard) -> list[Problem]:
    out = []
    for s in sb.shots:
        # own_part et pas le prompt entier : la direction artistique contient
        # « 3D engineering visualization », dont le « engine » suffisait a faire
        # croire qu'un moteur etait montre.
        manquants = _non_montres(s.voice, own_part(s.image_prompt))
        if manquants:
            out.append(Problem("ALIGNEMENT", s.slug,
                               f"la voix parle de {', '.join(manquants)} — "
                               f"invisible dans le prompt photo",
                               f"Shot {s.id}: the voice mentions {', '.join(manquants)}, so the "
                               f"image_prompt must show it clearly and name it."))
    return out


def _non_montres(voix: str, image: str) -> list[str]:
    """Les composants nommes par la voix et absents du prompt photo.

    Recherche sur les mots entiers : « engine » ne doit pas etre trouve dans
    « engineering », ni « cell » dans « excellent ».
    """
    v, i = voix.lower(), image.lower()
    return [fr for fr, en in SEMANTIQUE.items()
            if fr in v and not any(mot_present(a, i) for a in en)]


def _forme(mot: str) -> str:
    """Le motif d'un mot entier, ses flexions courantes comprises.

    Le run 18 a montre le defaut inverse du precedent : « braking » ne
    matchait pas « brake », et le validateur reclamait un frein que le prompt
    photo nommait deux fois. On accepte donc le gerondif et le participe, en
    retirant le e muet — brake -> brak(e|es|ing|ed) — sans pour autant
    rouvrir la porte a « engine » dans « engineering », qui ne fait partie
    d'aucune de ces flexions.
    """
    # Le pluriel anglais en -ies : au run 41 le prompt photo nommait six fois
    # « red batteries » et le validateur reclamait une batterie absente.
    if mot.endswith("y") and len(mot) > 2 and mot[-2] not in "aeiou":
        return rf"\b{re.escape(mot[:-1])}(y|ies|ying|ied)\b"
    radical = mot[:-1] if mot.endswith("e") else mot
    return rf"\b{re.escape(radical)}(e?s|es|ing|ed|e)?\b"


def mot_present(mot: str, texte: str) -> bool:
    """Mot entier, flexions tolerees. « engine » ne matche pas
    « engineering », mais « winding » matche « windings » et « brake »
    matche « braking »."""
    return re.search(_forme(mot), texte) is not None


def _progression(sb: Storyboard) -> list[Problem]:
    out = []
    vues: dict[str, int] = {}
    for s in sb.shots:
        cle = _normalise(s.voice)
        if cle in vues:
            out.append(Problem("PROGRESSION", s.slug,
                               f"narration identique au plan {vues[cle]}",
                               f"Shot {s.id}: advance the causal chain instead of repeating "
                               f"what shot {vues[cle]} already said."))
        vues[cle] = s.id
    fonctions = [_normalise(s.educational_function) for s in sb.shots]
    if len(set(fonctions)) < len(fonctions):
        out.append(Problem("PROGRESSION", "storyboard",
                           "deux plans revendiquent la meme fonction pedagogique",
                           "Give each shot a distinct educational_function: one link of the "
                           "causal chain each, in order."))
    return out


def _normalise(texte: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", texte.lower()).strip()


# --- LA REGLE CENTRALE : grammaire visuelle et correspondance ---------------


def notions_pedagogiques(texte: str, table: dict[str, str] | None = None) -> set[str]:
    """Les NOTIONS du code couleur portees par le texte.

    On raisonne en notions et pas en teintes : l'energie electrique est
    jaune/orange, donc un flux annonce en jaune dans l'image et repris en
    orange dans l'animation reste le meme flux.

    « yellow energy streams » compte ; « yellow paint » ne compte pas : la
    couleur doit etre attachee a un phenomene, pas a un objet.
    """
    bas = texte.lower()
    trouvees = set()
    for couleur, notion in (table or COLOR_NOTION).items():
        if notion in trouvees:
            continue
        # Mot entier : « credible » contient « red », et le code couleur d'un
        # autre sujet peut nommer n'importe quelle teinte.
        for m in re.finditer(rf"\b{re.escape(couleur)}\b", bas):
            apres = bas[m.end():m.end() + 40]
            premier_ambiance = min((apres.find(a) for a in AMBIANCE
                                    if a in apres), default=-1)
            premier_phenomene = min((apres.find(p) for p in PHENOMENE
                                     if p in apres), default=-1)
            # « blue lighting » est la direction artistique, pas une notion.
            if premier_ambiance >= 0 and (premier_phenomene < 0
                                          or premier_ambiance < premier_phenomene):
                continue
            fenetre = bas[max(0, m.start() - 60):m.end() + 90]
            if any(p in fenetre for p in PHENOMENE):
                trouvees.add(notion)
                break
    return trouvees


def _mouvement_non_camera(texte: str) -> bool:
    """Vrai s'il reste un mouvement une fois les phrases de camera retirees."""
    phrases = re.split(r"[.;]", texte.lower())
    utiles = [p for p in phrases if not any(c in p for c in CAMERA)]
    return any(v in " ".join(utiles) for v in MOUVEMENT)


def _grammaire_visuelle(sb: Storyboard) -> list[Problem]:
    """Un phenomene invisible nomme par la voix doit etre rendu visible."""
    out = []
    table = sb.notion_par_couleur()
    for s in sb.shots:
        parle_invisible = any(mot in s.voice.lower() for mot in
                              ("énergie", "energie", "électricité", "electricite", "courant",
                               "champ", "signal", "puissance", "chaleur", "récupér", "recuper"))
        if parle_invisible and not notions_pedagogiques(s.image_prompt, table):
            out.append(Problem("GRAMMAIRE", s.slug,
                               "la voix nomme un phenomene invisible, "
                               "aucune representation coloree dans le prompt photo",
                               f"Shot {s.id}: the narration names something the eye cannot see. "
                               f"Create a visible representation of it and name its colour "
                               f"from the colour code — for example controlled yellow luminous "
                               f"streams for electrical energy."))
    return out


def _correspondance(sb: Storyboard) -> list[Problem]:
    """Ce que l'image introduit, l'animation doit le faire bouger."""
    out = []
    table = sb.notion_par_couleur()
    mobiles_du_sujet = set(sb.notions_mobiles())
    for s in sb.shots:
        image, anim = own_part(s.image_prompt), s.animation_prompt
        bas_anim = anim.lower()

        notions_image = notions_pedagogiques(image, table)
        mobiles = notions_image & mobiles_du_sujet
        perdues = mobiles - notions_pedagogiques(anim, table)
        if perdues:
            out.append(Problem("CORRESPONDANCE", s.slug,
                               f"l'image introduit une representation « {', '.join(sorted(perdues))} », "
                               f"l'animation ne la fait pas bouger",
                               f"Shot {s.id}: the image carries a {'/'.join(sorted(perdues))} "
                               f"representation of an invisible phenomenon. The animation must "
                               f"make that same element travel, pulse or circulate — not just "
                               f"move the camera."))

        # LE FLUX N'EST JAMAIS STATIQUE : il doit aller quelque part.
        if (notions_image & mobiles_du_sujet) and not any(d in bas_anim for d in DIRECTION):
            out.append(Problem("FLUX", s.slug,
                               "le phenomene mobile n'a pas de direction lisible "
                               "dans l'animation",
                               f"Shot {s.id}: the flow must never be static. State where it "
                               f"comes from and where it goes — from which component toward "
                               f"which other one — so the viewer reads the direction of the "
                               f"transfer."))

        if not _mouvement_non_camera(anim):
            out.append(Problem("CORRESPONDANCE", s.slug,
                               "l'animation ne contient qu'un mouvement de camera",
                               f"Shot {s.id}: a camera move alone is rejected. Name the element "
                               f"that moves and how, and keep the camera secondary."))

        concept = s.visual_concept.lower()
        for composant, verbes in COMPOSANT_MOUVEMENT.items():
            if composant in concept and composant in image.lower():
                if composant not in bas_anim or not any(v in bas_anim for v in verbes):
                    out.append(Problem("CORRESPONDANCE", s.slug,
                                       f"l'image met en avant « {composant} », "
                                       f"l'animation ne le fait pas bouger",
                                       f"Shot {s.id}: the animation must name the {composant} "
                                       f"and describe its motion "
                                       f"({', '.join(verbes)})."))
    return out


def _explication(sb: Storyboard) -> list[Problem]:
    """Le raisonnement en sept temps qui precede le prompt."""
    out = []
    for s in sb.shots:
        courts = [f for f in EXPLICATION_FIELDS
                  if len(s.visual_explanation.get(f, "").strip())
                  < LONGUEUR_MINIMALE.get(f, LONGUEUR_PAR_DEFAUT)]
        if courts:
            out.append(Problem("EXPLICATION", s.slug,
                               f"visual_explanation trop vague : {', '.join(courts)}",
                               f"Shot {s.id}: answer the seven questions before writing any "
                               f"prompt — which information must be understood, which single "
                               f"object shows it, which secondary objects make it readable, "
                               f"which visible phenomenon represents it, which movement "
                               f"animates it, which camera lets it be seen, which framing that "
                               f"movement requires."))
            continue

        mouvement = s.visual_explanation["animation_movement"].lower()
        if not any(v in mouvement for v in MOUVEMENT):
            out.append(Problem("EXPLICATION", s.slug,
                               "animation_movement ne decrit aucun mouvement reel",
                               f"Shot {s.id}: animation_movement must name a real motion — a "
                               f"flow travelling, a part rotating, a light spreading — not a "
                               f"mood or a camera position."))
    return out


def _mots_ancrables(texte: str, generiques: set[str]) -> list[list[str]]:
    """Les mots du texte qui peuvent servir d'ancre, avec leurs equivalents.

    Le raisonnement peut nommer « le moteur » quand le prompt photo, lui, est
    en anglais : SEMANTIQUE porte deja cette correspondance, on la reutilise
    plutot que d'exiger que les deux textes soient dans la meme langue.
    """
    mots = re.findall(r"[^\W\d_]+", texte.lower(), re.UNICODE)
    ancres = []
    for mot in mots:
        racine = mot[:-1] if mot.endswith("s") and not mot.endswith("ss") else mot
        if len(racine) <= 2 or racine in GENERIQUES or racine in generiques:
            continue
        ancres.append([racine, *SEMANTIQUE.get(racine, ())])
    return ancres


def _dans_le_cadre(mot: str, texte: str) -> bool:
    """Vrai si le mot est nomme autrement que comme destination d'un flux."""
    bas = texte.lower()
    for m in re.finditer(_forme(mot), bas):
        avant = bas[max(0, m.start() - FENETRE_DESTINATION):m.start()]
        if not any(d in avant for d in DESTINATION):
            return True
    return False


def _ancrage(sb: Storyboard) -> list[Problem]:
    """L'image est le premier plan de l'animation, pas une illustration.

    Deux sens a verifier, et c'est le second qui attrape le defaut vu en
    production : une animation qui ramene l'energie « vers la batterie »
    alors que la batterie n'a jamais ete dans le cadre.
    """
    out = []
    for s in sb.shots:
        image = own_part(s.image_prompt)
        anim = s.animation_prompt

        # 1. L'objet principal du raisonnement doit etre dans l'image.
        principal = s.visual_explanation.get("physical_element", "")
        ancres = _mots_ancrables(principal, VEHICULE)
        if not ancres:
            out.append(Problem("ANCRAGE", s.slug,
                               f"physical_element ne nomme aucun objet precis : "
                               f"« {principal.strip()} »",
                               f"Shot {s.id}: name ONE precise physical object — the battery "
                               f"pack, the high-voltage cable, the stator windings. The whole "
                               f"vehicle is not an object: a shot with nothing more precise to "
                               f"show carries no information."))
        elif not any(mot_present(m, image) for groupe in ancres for m in groupe):
            out.append(Problem("ANCRAGE", s.slug,
                               f"l'objet principal « {principal.strip()} » "
                               f"n'est pas dans le prompt photo",
                               f"Shot {s.id}: the image prompt must show {principal.strip()} "
                               f"explicitly. The image is the first frame of the animation, so "
                               f"it carries every element the animation needs."))

        # 2. Ce que l'animation fait bouger doit deja etre DANS LE CADRE.
        for famille in FAMILLES:
            nommes = [o for o in famille if mot_present(o, anim)]
            if not nommes or any(_dans_le_cadre(o, image) for o in famille):
                continue
            objet = nommes[0]
            if any(mot_present(o, image) for o in famille):
                out.append(Problem("ANCRAGE", s.slug,
                                   f"« {objet} » n'est nomme que comme destination "
                                   f"dans le prompt photo : il n'est jamais dans le cadre",
                                   f"Shot {s.id}: the image prompt only mentions the {objet} "
                                   f"as somewhere the flow goes. Put the {objet} itself in "
                                   f"frame, clearly visible, so the viewer sees where the "
                                   f"energy arrives — otherwise the flow simply leaves the "
                                   f"picture and the shot explains nothing."))
            else:
                out.append(Problem("ANCRAGE", s.slug,
                                   f"l'animation fait bouger « {objet} », "
                                   f"absent du prompt photo",
                                   f"Shot {s.id}: never introduce an important object only in "
                                   f"the animation. Either put the {objet} in the image "
                                   f"prompt, in frame and clearly visible, or stop naming it "
                                   f"in the animation."))
    return out


def _hors_camera(texte: str) -> str:
    """Le texte prive de ses phrases de camera."""
    phrases = re.split(r"[.;]", texte.lower())
    return " ".join(p for p in phrases if not any(c in p for c in CAMERA))


def _acteur(mot: str, proposition: str) -> bool:
    """Vrai si la piece bouge elle-meme, plutot que de subir un flux."""
    for m in re.finditer(_forme(mot), proposition):
        if not any(r in proposition[max(0, m.start() - 20):m.start()]
                   for r in ROLE_PASSIF):
            return True
    return False


def _composants_en_mouvement(monde: str) -> list[str]:
    """Les pieces qui bougent vraiment, dans une proposition qui porte un mouvement."""
    bouge = set()
    for proposition in re.split(r"[,:;.]", monde):
        if not any(v in proposition for verbes in FAMILLES_MOUVEMENT.values()
                   for v in verbes):
            continue
        bouge.update(c for c in COMPOSANTS_MOBILES if _acteur(c, proposition))
    return sorted(bouge)


def _dynamique(sb: Storyboard) -> list[Problem]:
    """Le zoom n'est jamais le mouvement principal, et un mouvement seul suffit rarement.

    Un plan qui ne donne qu'UNE chose a faire bouger laisse le generateur
    combler le reste du temps avec la camera. C'est exactement ce qui est
    arrive aux plans 1 et 2 du run 14 : le prompt ne disait pas « zoom », mais
    il ne proposait qu'un seul mouvement, et la video rendue est un travelling.

    « Plusieurs mouvements » se compte de deux facons, et l'une suffit : des
    familles differentes — un flux ET une rotation —, ou des pieces
    differentes qui bougent — le rotor PUIS la transmission PUIS les roues.
    Le run 17 a prouve qu'il fallait les deux : une chaine mecanique de trois
    rotations est le meilleur plan du lot, et ne compte qu'une famille.
    """
    out = []
    for s in sb.shots:
        monde = _hors_camera(s.animation_prompt)

        familles = sorted(f for f, verbes in FAMILLES_MOUVEMENT.items()
                          if any(v in monde for v in verbes))
        composants = _composants_en_mouvement(monde)
        if (len(familles) < MIN_FAMILLES_MOUVEMENT
                and len(composants) < MIN_COMPOSANTS_MOBILES):
            porte = (f"qu'un seul mouvement ({familles[0]})" if familles
                     else "aucun mouvement")
            out.append(Problem("DYNAMIQUE", s.slug,
                               f"l'animation ne porte {porte} : "
                               f"le generateur comblera le reste avec la camera",
                               f"Shot {s.id}: one movement is not enough. Answer WHAT IS "
                               f"MOVING IN THE WORLD, not how the camera moves: combine at "
                               f"least two coordinated physical movements — the flow "
                               f"travelling AND what it makes happen when it arrives, the "
                               f"rotor turning AND the wheels it drives. Never add movement "
                               f"just to look spectacular: each one must explain something."))
            continue

        if not any(mot in monde for mot in LIAISON):
            out.append(Problem("DYNAMIQUE", s.slug,
                               f"les mouvements ({', '.join(familles)}) sont juxtaposes, "
                               f"leur lien n'est pas dit",
                               f"Shot {s.id}: the movements must be synchronised and causally "
                               f"related, and the prompt must say the link out loud — 'as the "
                               f"energy reaches the windings, the rotor begins to turn', "
                               f"'driven by that rotation, the wheels turn'."))
    return out


def _physique(sb: Storyboard) -> list[Problem]:
    """Ce qui est montre doit rester vrai, et l'energie rester de l'energie."""
    out = []
    for s in sb.shots:
        image, anim = own_part(s.image_prompt), s.animation_prompt
        for ou, texte in (("le prompt photo", image), ("l'animation", anim)):
            bas = texte.lower()

            boucles = [b for b in BOUCLE if b in bas]
            if boucles:
                out.append(Problem("PHYSIQUE", s.slug,
                                   f"{ou} fait tourner l'energie en rond "
                                   f"(« {boucles[0]} »)",
                                   f"Shot {s.id}: energy does not run in a loop. In normal "
                                   f"operation it goes one way — battery, inverter, motor, "
                                   f"transmission, wheels — and regenerative braking runs it "
                                   f"back the other way. State ONE clear direction for "
                                   f"this shot, and follow it from where the phenomenon "
                                   f"starts to where it arrives."))

            decoratifs = [d for d in DECORATIF if d in bas]
            if decoratifs:
                out.append(Problem("PHYSIQUE", s.slug,
                                   f"{ou} traite l'energie en decor "
                                   f"(« {decoratifs[0]} »)",
                                   f"Shot {s.id}: the energy representation must never look "
                                   f"like smoke, sparkles or decorative particles, and must "
                                   f"never float randomly. It follows real electrical "
                                   f"pathways, enters and leaves components according to the "
                                   f"explanation, and always communicates direction."))

        if STYLE_PAR_DEFAUT:
            claires = [t for t in TEINTE_CLAIRE
                       for m in re.finditer(re.escape(t), image.lower())
                       if any(n in image.lower()[m.end():m.end() + 30]
                              for n in VEHICULE_NOMS)]
            if claires:
                out.append(Problem("VEHICULE", s.slug,
                                   f"la carrosserie est claire (« {claires[0]} ») "
                                   f"alors que la voiture de reference est sombre",
                                   f"Shot {s.id}: the vehicle is the same modern dark, "
                                   f"near-black electric sedan in every shot — same geometry, "
                                   f"proportions, wheels, glass, materials. Never redesign, "
                                   f"replace or recolour it between shots."))
    return out


def phrases(texte: str) -> list[str]:
    """Le script, phrase par phrase."""
    return [p.strip() for p in re.split(r"(?<=[.!?])\s+", texte.strip()) if p.strip()]


def _texte(sb: Storyboard) -> list[Problem]:
    """La narration : l'ouverture, la voix active, et les mots qui ne montrent rien."""
    out = []
    toutes = phrases(sb.script)
    if not toutes:
        return out

    premiere = toutes[0].lower()
    plates = [m for m in OUVERTURE_PLATE if m in premiere]
    if plates:
        out.append(Problem("CROCHET", "script",
                           f"l'ouverture est une generalite (« {plates[0].strip()} »)",
                           "The first sentence could open any video on any subject. "
                           "Replace it: name a number that surprises, point at something "
                           "the viewer has seen a hundred times without understanding it, "
                           "or say out loud the thing that seems impossible. Never a "
                           "definition, never 'X est essentiel', never 'X commence par'."))

    passives = [p for p in toutes if est_passive(p)]
    if len(passives) > len(toutes) / 2:
        out.append(Problem("PASSIF", "script",
                           f"{len(passives)} phrases sur {len(toutes)} au passif",
                           "The narration hides who acts. Rewrite in the active voice: "
                           "'la vapeur pousse les aubes', never 'les aubes sont poussées "
                           "par la vapeur'. The thing that acts is the thing the image "
                           "must show."))

    sans_acteur = [p for p in toutes if ANAPHORE.match(p.lower())]
    if len(sans_acteur) >= 2:
        out.append(Problem("ACTEUR", "script",
                           f"{len(sans_acteur)} phrases ne nomment personne "
                           f"(« {sans_acteur[0][:40]}… »)",
                           "These sentences point back at the previous one instead of "
                           "naming who acts. Every sentence needs a physical actor doing "
                           "something — the steam, a blade, a magnet, a wire — because "
                           "that actor is what the image has to show. 'Cette énergie est "
                           "transférée' shows nothing; 'la vapeur pousse les aubes' does."))

    bas = sb.script.lower()
    flous = [m for m in VAGUE if m in bas]
    if len(flous) >= 2:
        out.append(Problem("VAGUE", "script",
                           f"mots qui promettent sans montrer : {', '.join(flous[:4])}",
                           f"Remove {', '.join(flous[:4])}. Each sentence must carry one "
                           f"concrete fact with a physical actor doing something — steam, "
                           f"a blade, a magnet, a wire. 'permet de produire' is 'produit'."))
    return out


def _temporel(sb: Storyboard) -> list[Problem]:
    """L'animation doit dire comment le mouvement progresse dans le temps."""
    out = []
    for s in sb.shots:
        if not any(mot in s.animation_prompt.lower() for mot in PROGRESSION):
            out.append(Problem("TEMPS", s.slug,
                               "l'animation ne dit pas comment le mouvement progresse "
                               "dans le temps",
                               f"Shot {s.id}: say how the movement progresses over the "
                               f"shot — where it starts, how it builds, where it arrives. "
                               f"Use explicit temporal wording: 'gradually', 'steadily', "
                               f"'begins to', 'building in intensity', 'until'. Without it "
                               f"the generator returns a frozen instant that drifts."))
    return out


def _dernier_plan(sb: Storyboard) -> list[Problem]:
    """Le dernier plan porte le resultat physique, il ne resume pas."""
    if not sb.shots:
        return []
    dernier = sb.shots[-1]
    texte = f"{dernier.educational_function} {dernier.visual_concept}".lower()
    mots = [m for m in RESUME if m in texte]
    if not mots:
        return []
    return [Problem("FINAL", dernier.slug,
                    f"le dernier plan est un plan de synthese (« {mots[0]} »)",
                    f"Shot {dernier.id} is the last one: it must NOT summarise. Give it "
                    f"the physical RESULT of everything explained before, happening on "
                    f"screen — the thing the whole video was building towards, finally "
                    f"moving. A recap shot has nothing left to animate.")]


def _code_couleur(sb: Storyboard) -> list[Problem]:
    """Le code couleur doit etre celui du SUJET, pas celui de la voiture."""
    consigne = ("Return a \"color_code\" array beside the visual bible: between "
                f"{MIN_COLOR_NOTIONS} and {MAX_COLOR_NOTIONS} entries, each with "
                "\"notion\" (what it means IN YOUR subject), \"color\", \"meaning\" "
                "and \"moving\" (true only when the notion is an invisible phenomenon "
                "that travels). At least one notion must be moving.")

    if not sb.color_code:
        return [Problem("COULEUR", "storyboard", "aucun code couleur propre au sujet",
                        consigne)]

    out = []
    if not MIN_COLOR_NOTIONS <= len(sb.color_code) <= MAX_COLOR_NOTIONS:
        out.append(Problem("COULEUR", "storyboard",
                           f"{len(sb.color_code)} notion(s) de couleur",
                           consigne))
    if not sb.notions_mobiles():
        out.append(Problem("COULEUR", "storyboard",
                           "aucune notion ne represente un phenomene qui se deplace",
                           "At least one colour notion must have \"moving\": true — the "
                           "invisible phenomenon the narration explains and the animation "
                           "makes travel. A pure identity colour never moves."))

    # Seules les notions MOBILES sont verifiees a l'usage : une couleur
    # d'identite est fixee par la visual bible, elle n'a pas a etre nommee
    # comme phenomene dans chaque prompt. Chercher sa teinte au hasard du
    # texte ferait matcher le « blue » de la direction artistique.
    table = sb.notion_par_couleur()
    jamais = [e.notion for e in sb.color_code if e.moving
              and not any(e.notion in notions_pedagogiques(own_part(s.image_prompt), table)
                          for s in sb.shots)]
    # Le code couleur est une convention VISUELLE : la voix ne la dit pas.
    # Au run 34 le script annoncait « ce signal infrarouge rouge », ce qui
    # revient a lire la legende a voix haute.
    for shot in sb.shots:
        dites = sorted({c for e in sb.color_code for c in e.couleurs
                        if re.search(rf"\b{re.escape(c)}s?\b", shot.voice.lower())})
        if dites:
            out.append(Problem("COULEUR", shot.slug,
                               f"la voix nomme la couleur du code (« {dites[0]} »)",
                               f"Shot {shot.id}: the colour code is a visual convention, "
                               f"for the eye only. Remove the colour from the French "
                               f"narration — the voice says what happens, the image says "
                               f"in which colour."))

    if jamais:
        out.append(Problem("COULEUR", "storyboard",
                           f"phenomene(s) declare(s) et jamais montre(s) : "
                           f"{', '.join(jamais)}",
                           f"The colour code declares {', '.join(jamais)} as a moving "
                           f"phenomenon, but no image prompt ever makes it visible. Either "
                           f"show it, with its colour, in at least one shot, or remove it "
                           f"from color_code."))
    return out


def _qualite(sb: Storyboard) -> list[Problem]:
    out = []
    for axe in QUALITY_AXES:
        note = sb.quality_check.get(axe)
        if note is None:
            continue
        if not 0.0 <= note <= 1.0:
            out.append(Problem("QUALITE", "storyboard", f"{axe} hors bornes : {note}",
                               f"quality_check.{axe} must be between 0 and 1."))
        elif note < MIN_QUALITY:
            out.append(Problem("QUALITE", "storyboard",
                               f"{axe} = {note} < {MIN_QUALITY}",
                               f"Rework the storyboard until {axe} honestly reaches "
                               f"{MIN_QUALITY}, then re-score."))
    return out


# ---------------------------------------------------------------------------
# CONTROLE DE CE QUI A ETE REELLEMENT PRODUIT
#
# Jusqu'ici rien ne mesurait le resultat : les videos etaient analysees, et
# l'analyse restait sur le disque. Ces controles-la comparent ce que la video
# MONTRE a ce que le plan DEMANDAIT, et disent quels plans sont a refaire.
#
# Leur « fix » s'adresse a l'utilisateur, pas a OpenAI : il est en francais.
# ---------------------------------------------------------------------------

VIDEO_TOLERANCE_S = 1.0

# « None observed », « no defects » : le modele remplit la liste meme quand il
# n'a rien a signaler. Ce ne sont pas des defauts.
NON_DEFAUTS = ("none", "no defect", "no visible", "nothing", "aucun", "n/a", "rien")
MOTS_VIDES = ("the", "and", "with", "that", "from", "into", "toward", "towards",
              "along", "through", "this", "their", "its", "for", "onto", "over",
              "under", "between", "which", "what", "when", "then", "than",
              "each", "every", "some", "very", "more", "most", "being")


def mots_du_concept(concept: str) -> list[str]:
    """Les mots qui portent vraiment l'element pedagogique."""
    return [m for m in re.findall(r"[a-z]+", concept.lower())
            if len(m) > 3 and m not in MOTS_VIDES]


def controler_videos(sb: Storyboard, analyses: dict) -> list[Problem]:
    """Ce que la video montre vraiment, compare a ce que le plan demandait."""
    out: list[Problem] = []
    for s in sb.shots:
        analyse = analyses.get(s.id)
        if analyse is None:
            out.append(Problem("VIDEO", s.slug, "aucune analyse",
                               "Dépose la vidéo de ce plan, puis relance "
                               "`analyser-videos`."))
            continue

        if not analyse.matches_plan:
            out.append(Problem("VIDEO", s.slug,
                               "la vidéo ne fait pas ce que le plan demandait",
                               f"À refaire. Ce qui a été constaté : "
                               f"{analyse.voice_match}"))

        vu = " ".join([analyse.content, analyse.movement,
                       " ".join(analyse.pedagogical_elements)]).lower()
        attendus = mots_du_concept(s.visual_concept)
        absents = [m for m in attendus if not mot_present(m, vu)]
        if attendus and len(absents) > len(attendus) / 2:
            out.append(Problem("ELEMENT", s.slug,
                               f"l'élément pédagogique n'est pas lisible à l'écran "
                               f"({', '.join(absents[:4])})",
                               f"À refaire : ce plan doit montrer « {s.visual_concept} ». "
                               f"La vidéo montre : {analyse.content}"))

        if not _mouvement_non_camera(analyse.movement):
            out.append(Problem("MOUVEMENT", s.slug,
                               "rien ne bouge dans le monde, seule la caméra",
                               f"À refaire : le prompt d'animation demandait un mouvement "
                               f"physique. Ce qui bouge réellement : {analyse.movement}"))

        ecart = abs(analyse.measured_duration - s.duration_seconds)
        if analyse.measured_duration and ecart > VIDEO_TOLERANCE_S:
            out.append(Problem("DUREE", s.slug,
                               f"{analyse.measured_duration:g}s au lieu de "
                               f"{s.duration_seconds:g}s",
                               "Le montage recadrera, mais un écart d'une seconde se voit. "
                               "Régénère la vidéo à la bonne durée si tu peux."))

        for defaut in analyse.defects:
            if defaut.strip().lower().startswith(NON_DEFAUTS):
                continue
            out.append(Problem("DEFAUT", s.slug, defaut,
                               "Relance la génération de ce plan : ce défaut se verra "
                               "au montage."))
    return out


def a_refaire(problems: list[Problem]) -> list[str]:
    """Les plans dont au moins un controle est bloquant."""
    bloquants = ("VIDEO", "ELEMENT", "MOUVEMENT")
    return sorted({p.where for p in problems if p.code in bloquants})


# ---------------------------------------------------------------------------


def correction_request(problems: list[Problem]) -> str:
    lignes = [
        "Your previous JSON was rejected by an automatic validator.",
        "Fix every point below and return the SAME JSON shape, corrected.",
        "Do not explain, do not apologise, return only the JSON.",
        "",
    ]
    lignes += [f"- {p.where}: {p.fix}" for p in problems]
    return "\n".join(lignes)
