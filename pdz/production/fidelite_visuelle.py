"""Garantit que le prompt d'image montre ce que la réplique nomme vraiment.

Laissé libre, un modèle qui écrit un prompt d'image a tendance à illustrer
« l'esprit » d'une réplique plutôt que les objets concrets qu'elle nomme :
la voix dit « le signal plonge dans le câble sous-marin », l'image montre un
hologramme générique sans câble ni océan. `ShotPromptWriter` désigne donc
ces objets explicitement dans `elements_obligatoires` ; ce module vérifie
après coup qu'ils sont bien dans le prompt final, et les rajoute sinon —
jamais un appel Groq de plus, une simple concaténation de texte.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

# Le filet qui protège `corriger_prompt()` : Groq ne valide JAMAIS
# `maxLength` ni la langue côté serveur (voir pdz/ia/groq.py), seulement le
# `type` JSON — un simple ajustement du schéma du prompt (qa_image@1.2.0)
# est donc une aide au modèle, pas une garantie. Mesuré en production
# (audit 2, ep56/ep62) : `manquants`/`incorrects`/`en_trop` reviennent
# parfois comme des phrases françaises complètes, injectées telles quelles
# par `exclure()` dans un prompt Flux anglais. `assainir()` est le vrai
# rempart : tout ce qui ne ressemble pas à un court token anglais est
# rejeté avant d'atteindre le prompt, jamais levé en erreur — un élément
# douteux doit juste disparaître de la correction, pas la faire planter.
_LIMITE_MOTS = 4
_LIMITE_CARACTERES = 40
_CARACTERES_ACCENTUES = "éèêëàâäîïôöùûüçÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ"
_MOTS_VIDES_FR = {
    "le", "la", "les", "un", "une", "des", "dans", "sur", "qui", "que", "où",
    "avec", "pour", "est", "sont", "alors", "parce", "ne", "pas",
}


def assainir(elements: list[str]) -> list[str]:
    """Ne garde que les éléments qui ressemblent à un court token anglais.

    Même contrat que `elements_obligatoires`/`elements_a_exclure` (voir
    ecriture/plans@1.9.0.yaml : « 1 à 4 mots, en anglais ») — mais appliqué
    ici en Python, pas seulement demandé dans un schéma, parce que rien côté
    Groq ne garantit qu'il soit respecté.
    """
    retenus = []
    for brut in elements:
        e = brut.strip()
        if not e:
            continue
        if len(e) > _LIMITE_CARACTERES:
            log.warning("Élément QA rejeté (%d caractères, > %d) : %r",
                       len(e), _LIMITE_CARACTERES, brut)
            continue
        mots = e.split()
        if len(mots) > _LIMITE_MOTS:
            log.warning("Élément QA rejeté (%d mots, > %d) : %r",
                       len(mots), _LIMITE_MOTS, brut)
            continue
        if any(c in _CARACTERES_ACCENTUES for c in e):
            log.warning("Élément QA rejeté (caractère accentué français) : %r", brut)
            continue
        if {m.lower() for m in mots} & _MOTS_VIDES_FR:
            log.warning("Élément QA rejeté (mot vide français) : %r", brut)
            continue
        retenus.append(e)
    return retenus


def renforcer(prompt: str, elements: list[str]) -> tuple[str, list[str]]:
    """Ajoute au prompt les éléments obligatoires qui n'y sont pas déjà.

    Comparaison insensible à la casse sur une sous-chaîne simple : pas besoin
    de plus, `elements_obligatoires` est écrit par le même modèle et dans le
    même appel que `prompt_image`, donc dans un vocabulaire déjà cohérent.
    """
    bas = prompt.lower()
    manquants = [e for e in elements if e.strip() and e.strip().lower() not in bas]
    if not manquants:
        return prompt, []
    return f"{prompt}, featuring {', '.join(manquants)}", manquants


def renforcer_registre(prompt: str, registre: str) -> str:
    """Réaffirme le registre visuel après un `registre_correspond=False`.

    Volontairement plus insistant que le simple ajout passif que
    `prompt_plan()` fait déjà par défaut (voir `images.py`) — celui-là a
    déjà tourné une première fois et a échoué : le répéter à l'identique
    n'apporterait aucun signal de plus. `", rendering strictly in this
    style"` force explicitement le RENDU, pas seulement la présence d'un
    mot-clé de style dans le prompt.
    """
    registre = registre.strip()
    if not registre:
        return prompt
    return f"{prompt}, rendering strictly in this style: {registre}"


def exclure(prompt: str, elements: list[str]) -> str:
    """Ajoute au prompt les éléments à exclure de CE plan précis.

    Les modèles Flux (fal.ai) n'ont pas de canal de negative prompt séparé :
    la seule façon d'exclure un élément est de l'écrire en toutes lettres
    dans le prompt — même convention que `univers.style.consignes_image`
    (« no human faces, no facial features »), en plan-spécifique cette fois.
    Utile pour empêcher qu'un objet d'un autre moment du récit s'invite ici
    (le téléphone une fois que la donnée l'a quitté, le câble sous-marin
    avant que le signal y arrive).
    """
    propres = [e.strip() for e in elements if e.strip()]
    if not propres:
        return prompt
    return f"{prompt}, no {', no '.join(propres)}"
