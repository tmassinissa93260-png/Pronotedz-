"""Le filtre déterministe qui décide si un prompt d'image mérite RealismWriter.

RealismWriter (voir `pdz/agents/ecriture/realisme.py`) corrige ce qu'un
modèle d'image rate systématiquement — texte lisible, logo, visage interdit.
Mais l'appeler sur CHAQUE plan, à chaque fois, coûte un appel Groq par plan,
même quand rien dans le prompt ne l'exige. Recherche (2026, guides de
prompt-engineering négatif) : le risque de texte/logo illisible vient
presque toujours d'une description qui IMPLIQUE ce détail (« conversation
visible », « logo affiché »), pas d'un mot isolé anodin — c'est exactement
ce que ce filtre repère, en Python, sans aucun coût.

Détecter ces motifs ne remplace pas RealismWriter : un modèle de langage
comprend des formulations que ce filtre ne connaît pas encore. Mais filtrer
d'abord les plans qui n'en ont manifestement pas besoin réduit le nombre
d'appels réels — mesuré comme le facteur direct de l'épuisement de quota
Groq de cette nuit (4 appels IA par épisode rien que pour l'écriture).
"""

from __future__ import annotations

import re

# Chaque motif capte une FAÇON de décrire une scène qui implique un détail
# qu'un modèle d'image ne sait pas bien rendre — jamais un mot isolé qui
# pourrait apparaître dans un tout autre contexte (« texte » seul, par
# exemple, est trop générique et donnerait des faux positifs constants).
MOTIFS_TEXTE_LISIBLE = [
    r"\breadable text\b", r"\bmessage(s)? affich", r"\btexte lisible\b",
    r"\bconversation (visible|affich[ée]e)\b", r"\b[ée]cran (montrant|affichant)\b",
    r"\bscreen (showing|displaying)\b", r"\bwritten text\b", r"\btext on screen\b",
    r"\bvisible text\b", r"\bnotification (affich[ée]e|visible)\b",
    r"\btexte (pr[ée]cis|exact) à l'écran\b",
    # Élargi (mesuré à l'écran, techno-holo) : ces formulations INDIRECTES
    # produisent le même faux texte/chiffres illisibles qu'un écran
    # affichant un message, sans jamais dire « texte » ou « écran affichant »
    # explicitement — une carte avec sa légende, une interface système, un
    # « digital readout ». Volontairement PAS de motif sur « data stream »
    # seul : trop générique dans cet univers (un flux lumineux abstrait n'a
    # rien d'un risque de texte), ça ferait déclencher presque tous les plans.
    r"\bdigital readout\b", r"\bscrolling code\b", r"\bsystem interface\b",
    r"\bdisplayed information\b", r"\btechnical labels?\b", r"\bmap legend\b",
    r"\blegend\b", r"\bdatabase interface\b", r"\b(visible|displayed) numbers\b",
    r"\bl[ée]gende( (cartographique|de carte))?\b", r"\binterface syst[èe]me\b",
    r"\blecture num[ée]rique\b", r"\bcode d[ée]filant\b",
    r"\binformations? affich[ée]es?\b", r"\b[ée]tiquettes? techniques?\b",
]
MOTIFS_LOGO = [
    r"\blogo\b", r"\bmarque déposée\b", r"\bbrand(ing)?\b", r"\bwordmark\b",
]
# Mesuré à l'écran sur techno-holo : un prompt qui décrit « a determined
# man » sans jamais dire « visage » ni « face » produit quand même un
# visage humain complet, détaillé, photoréaliste — la consigne générale de
# l'univers (« no human faces ») ne suffit pas à l'arrêter. Se limiter aux
# formulations qui nomment explicitement un visage détaillé manquait donc
# la vraie source du risque : toute présence humaine décrite suffit à en
# produire un — pas seulement un visage. Mesuré une deuxième fois : « a
# finger touches an icon » a produit une main photoréaliste à peau colorée,
# sur fond chaud — ni « man », ni « woman », ni « face » n'y figuraient.
# HUMAN_PRESENCE_RISK, pas seulement un risque de visage.
MOTIFS_VISAGE = [
    r"\bvisage (net|d[ée]taill[ée]|reconnaissable)\b",
    r"\bface (close-?up|detailed)\b", r"\bfacial features\b", r"\bportrait\b",
    r"\bman\b", r"\bwoman\b", r"\bperson\b", r"\bhuman\b", r"\bhuman figure\b",
    r"\bhis face\b", r"\bher face\b", r"\bhomme\b", r"\bfemme\b",
    r"\bfigure humaine\b", r"\bpersonnage humain\b",
    r"\bhand\b", r"\bhands\b", r"\bfinger\b", r"\bfingers\b",
    r"\barm\b", r"\barms\b", r"\bpalm\b", r"\bwrist\b", r"\bskin\b",
    r"\bhead\b", r"\bbody\b", r"\bsilhouette\b",
    r"\bmain\b", r"\bmains\b", r"\bdoigt\b", r"\bdoigts\b",
    r"\bbras\b", r"\bpaume\b", r"\bpoignet\b", r"\bpeau\b",
    # Élargi une seconde fois (mesuré à l'écran, ep56 plan 5 puis ep60 plan
    # 0 — ce dernier après le premier élargissement) : ces VERBES impliquent
    # une main/un doigt jamais nommé — « an icon lights up as it is
    # pressed » produit une main pleine, photoréaliste, sur un wireframe UI
    # par ailleurs correct, sans qu'aucun des mots ci-dessus n'apparaisse.
    r"\btouches?\b", r"\btouching\b", r"\btouched\b",
    r"\bpress(es|ing|ed)?\b", r"\btaps?\b", r"\btapped\b",
    r"\breach(es|ing)? (for|toward|out)\b", r"\bpoints? at\b",
    r"\btouche(nt)?\b", r"\bappuie(nt)?\b", r"\btapote(nt)?\b",
]


def raisons_de_correction(prompt: str, *, visage_interdit: bool,
                          marque_interdite: bool = False,
                          elements_obligatoires: list[str] | None = None,
                          vocabulaire_connu: frozenset[str] | None = None,
                          ) -> list[str]:
    """Les raisons pour lesquelles ce prompt mérite RealismWriter — liste
    vide si rien ne le justifie (cas le plus fréquent, et le moins cher).

    `visage_interdit` vient de l'univers (voir `visage_est_interdit`) : un
    univers qui autorise les visages ne doit jamais déclencher cette
    correction pour ça — la contrainte n'existe pas. Même principe pour
    `marque_interdite` (voir `marque_est_interdite`) et `vocabulaire_connu`
    (voir `vocabulaire_connu()`) : sans eux, aucun risque de marque n'est
    évalué — défauts inertes, rétrocompatibles avec les appels existants.
    """
    p = prompt.lower()
    raisons: list[str] = []
    if any(re.search(m, p) for m in MOTIFS_TEXTE_LISIBLE):
        raisons.append("texte lisible")
    if any(re.search(m, p) for m in MOTIFS_LOGO):
        raisons.append("logo")
    if visage_interdit and any(re.search(m, p) for m in MOTIFS_VISAGE):
        raisons.append("visage")
    if (marque_interdite and vocabulaire_connu is not None
            and mots_hors_vocabulaire(prompt, elements_obligatoires or [], vocabulaire_connu)):
        raisons.append("marque")
    return raisons


def visage_est_interdit(consignes_image: list[str]) -> bool:
    """Devine, depuis les consignes de l'univers, si les visages nets sont
    proscrits — pour ne pas signaler un « risque visage » là où il n'y en a
    pas."""
    return any(
        "face" in c.lower() or "visage" in c.lower() or "portrait" in c.lower()
        for c in consignes_image
    )


def marque_est_interdite(interdits: list[str]) -> bool:
    """Devine, depuis les interdits de l'univers, si les marques réelles
    sont proscrites — même lecture sémantique que `visage_est_interdit`,
    sur le champ `interdits` plutôt que `consignes_image`."""
    return any(
        "marque" in i.lower() or "brand" in i.lower() or "trademark" in i.lower()
        for i in interdits
    )


# Mots grammaticaux capitalisés en début de proposition ou dans une formule
# figée — jamais des noms propres, donc jamais un signal de marque à eux
# seuls. Volontairement PAS une liste de marques : voir mots_hors_vocabulaire().
_EXCEPTIONS_CAPITALISATION = {
    "a", "an", "the", "in", "on", "with", "as", "at", "his", "her", "its",
    "their", "he", "she", "it", "they", "i",
}
_MOTIF_CAPITALE = re.compile(r"\b[A-Z][a-z]+\b")  # exclut les ACRONYMES par construction


def vocabulaire_connu(noms_connus: list[str]) -> frozenset[str]:
    """Aplatit une liste de textes (id/nom/espèce des personnages, id/nom
    des décors...) en un ensemble de mots en minuscules, pour distinguer un
    nom propre LÉGITIME de l'univers d'un nom hors vocabulaire — voir
    `mots_hors_vocabulaire()`. Reste texte-vers-texte, comme le reste de ce
    module : jamais un import de `Univers` ici, c'est à l'appelant
    d'aplatir une fois par épisode, pas par plan."""
    mots: set[str] = set()
    for texte in noms_connus:
        mots.update(m.lower() for m in re.findall(r"[A-Za-zÀ-ÿ]+", texte))
    return frozenset(mots)


def mots_hors_vocabulaire(action: str, elements_obligatoires: list[str],
                          vocabulaire: frozenset[str]) -> list[str]:
    """Les mots capitalisés de `action`/`elements_obligatoires` qui ne sont
    ni un mot grammatical figé, ni un mot du vocabulaire propre de
    l'univers (personnages, décors) — un signal déterministe de nom de
    marque potentiel, sans jamais maintenir une liste de marques.

    Limite assumée : n'attrape qu'un nom de marque écrit explicitement dans
    le texte. Un logo que le générateur d'image invente à partir d'une
    description neutre (« a sleek electric sedan », sans jamais dire le
    nom de la marque) reste hors de portée d'un filtre sur le TEXTE du
    prompt — voir la dimension `conformite_univers` de `analyse/qa_image`,
    qui vérifie l'IMAGE, pas le texte, pour ce cas résiduel.
    """
    trouves: list[str] = []
    for m in _MOTIF_CAPITALE.finditer(action):
        if m.start() == 0:
            continue  # premier mot de la phrase — capitalisation structurelle, pas un signal
        mot = m.group(0)
        if mot.lower() not in _EXCEPTIONS_CAPITALISATION and mot.lower() not in vocabulaire:
            trouves.append(mot)
    for item in elements_obligatoires:
        for m in _MOTIF_CAPITALE.finditer(item):
            mot = m.group(0)
            if mot.lower() not in _EXCEPTIONS_CAPITALISATION and mot.lower() not in vocabulaire:
                trouves.append(mot)
    return trouves
