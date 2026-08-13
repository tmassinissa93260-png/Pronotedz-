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
# produire un.
MOTIFS_VISAGE = [
    r"\bvisage (net|d[ée]taill[ée]|reconnaissable)\b",
    r"\bface (close-?up|detailed)\b", r"\bfacial features\b", r"\bportrait\b",
    r"\bman\b", r"\bwoman\b", r"\bperson\b", r"\bhuman figure\b",
    r"\bhis face\b", r"\bher face\b", r"\bhomme\b", r"\bfemme\b",
    r"\bfigure humaine\b", r"\bpersonnage humain\b",
]


def raisons_de_correction(prompt: str, *, visage_interdit: bool) -> list[str]:
    """Les raisons pour lesquelles ce prompt mérite RealismWriter — liste
    vide si rien ne le justifie (cas le plus fréquent, et le moins cher).

    `visage_interdit` vient de l'univers (voir `visage_est_interdit`) : un
    univers qui autorise les visages ne doit jamais déclencher cette
    correction pour ça — la contrainte n'existe pas.
    """
    p = prompt.lower()
    raisons: list[str] = []
    if any(re.search(m, p) for m in MOTIFS_TEXTE_LISIBLE):
        raisons.append("texte lisible")
    if any(re.search(m, p) for m in MOTIFS_LOGO):
        raisons.append("logo")
    if visage_interdit and any(re.search(m, p) for m in MOTIFS_VISAGE):
        raisons.append("visage")
    return raisons


def visage_est_interdit(consignes_image: list[str]) -> bool:
    """Devine, depuis les consignes de l'univers, si les visages nets sont
    proscrits — pour ne pas signaler un « risque visage » là où il n'y en a
    pas."""
    return any(
        "face" in c.lower() or "visage" in c.lower() or "portrait" in c.lower()
        for c in consignes_image
    )
