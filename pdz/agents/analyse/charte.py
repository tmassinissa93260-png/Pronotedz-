"""L'agent qui regarde une vidéo et en rend un **univers produisible**.

C'est le chaînon qui manquait entre « j'ai analysé une vidéo » et « je peux
en faire une autre du même genre ». Avant, l'analyse produisait des chiffres
que personne ne relisait. Maintenant elle produit un fichier `univers/*.yaml`
directement utilisable par la commande `pdz episode`.

Le partage du travail, qui est tout l'intérêt du module :

  · **mesuré** (pdz.analyse.visuel) — palette, contraste, netteté, grain,
    cadrage, rythme. Fiable, gratuit, reproductible.
  · **interprété** (cet agent) — qui sont les personnages, à quoi ils
    ressemblent, quelles règles régissent ce monde. Utile mais faillible.

Les deux ne sont jamais mélangés : la palette de l'univers produit vient des
mesures, pas de ce que le modèle croit avoir vu. Quand le modèle contredit une
mesure, la mesure gagne — c'est écrit dans le prompt, et re-vérifié ici.

⚠️ Sur les personnages : ce module sait décrire un personnage assez précisément
pour le refabriquer. Utilisé sur une œuvre protégée, ça produirait une copie —
d'où le mode `transposer`, actif par défaut, qui garde l'archétype et le style
mais change ce qui identifie le personnage. Voir docs/13-les-formats.md § B.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from pdz.agents.base import Agent
from pdz.analyse.adn import Adn
from pdz.analyse.visuel import AnalyseVisuelle
from pdz.moteur.erreurs import ErreurValidation
from pdz.moteur.pipeline import Contexte
from pdz.univers import (
    ChampInterprete,
    Decor,
    EmpreinteCreative,
    EmpreinteHook,
    EmpreinteNarrative,
    EmpreinteVisuelle,
    Format,
    Personnage,
    Style,
    Univers,
    Voix,
)


class CharteVisuelle(Agent):
    """Images-clés + mesures → style, personnages, décors, règles du monde,
    et empreinte créative (le mécanisme d'attention, pas le contenu)."""

    nom = "charte"
    version = "1.1.0"
    prompt_ref = "analyse/charte"

    def variables(self, entrees: dict[str, Any], ctx: Contexte) -> dict[str, Any]:
        visuel: AnalyseVisuelle = entrees["visuel"]
        return {
            "mesures_visuelles": visuel.bloc_pour_prompt(),
            "mesures_rythme": entrees.get("mesures_rythme", "non mesuré"),
            "transposer": bool(entrees.get("transposer", True)),
            "langue": entrees.get("langue", "français"),
        }

    def images(self, entrees: dict[str, Any], ctx: Contexte) -> list[Path]:
        visuel: AnalyseVisuelle = entrees["visuel"]
        return list(visuel.images_cles)

    def apres(self, sortie: dict, entrees: dict, ctx: Contexte) -> dict:
        """Ce que le schéma JSON ne peut pas vérifier tout seul."""
        personnages = sortie.get("personnages") or []
        if not personnages:
            raise ErreurValidation(
                "Aucun personnage identifié. Sur une vidéo à personnages c'est "
                "une erreur ; sur une vidéo sans personnage, utilise plutôt "
                "le format « narration »."
            )

        vus: set[str] = set()
        for p in personnages:
            # Un identifiant en double casserait silencieusement l'univers :
            # deux personnages différents partageraient voix et fiche image.
            if p["id"] in vus:
                raise ErreurValidation(
                    f"Identifiant « {p['id'] } » utilisé deux fois. "
                    "Chaque personnage doit avoir le sien."
                )
            vus.add(p["id"])

            if len(p["apparence"].split()) < 15:
                raise ErreurValidation(
                    f"L'apparence de {p['nom']} tient en {len(p['apparence'].split())} "
                    "mots : trop vague pour redessiner le personnage. Il en faut "
                    "25 à 45, avec matière, couleur, forme et vêtement."
                )

        if entrees.get("transposer", True) and not sortie.get("transposition"):
            raise ErreurValidation(
                "Mode transposition demandé mais `transposition` est vide : "
                "dis pour chaque personnage ce qui a été gardé et ce qui a changé."
            )

        if not sortie.get("creative_fingerprint"):
            raise ErreurValidation(
                "`creative_fingerprint` est vide : explique le mécanisme "
                "d'attention de la vidéo (hook, structure, rétention), pas "
                "seulement son style visuel."
            )

        sortie["nb_personnages"] = len(personnages)
        return sortie


# ── De la charte à un univers utilisable ─────────────────────────────────

def vers_univers(charte: dict, visuel: AnalyseVisuelle, *,
                 identifiant: str, nom: str,
                 format: Format = Format.SERIE_ANIMEE,
                 duree_cible_s: int = 45,
                 langue: str = "fr",
                 adn: Adn | None = None) -> Univers:
    """Assemble la charte et les mesures en un `Univers` prêt à produire.

    Règle de partage, appliquée ici littéralement :
      · la **palette** vient des mesures — le modèle nomme mal les couleurs,
        l'histogramme non ;
      · le **rendu** et l'**éclairage** viennent du modèle — aucune mesure ne
        sait dire « contours noirs épais, aplats sans dégradé » ;
      · le **pacing** de l'empreinte créative vient de `adn`, jamais de
        `charte["creative_fingerprint"]` — même principe, un plan dure ce
        qu'il dure indépendamment de ce qu'un modèle en perçoit ;
      · la **graine** est dérivée de l'identifiant, donc stable : deux images
        générées à six mois d'écart gardent la même patte.
    """
    style = Style(
        rendu=_nettoyer_rendu(charte["rendu"]),
        palette=visuel.palette_hex[:5],
        eclairage=charte.get("eclairage", ""),
        ambiance=charte.get("ambiance", ""),
        ratio="9:16",
        seed=_graine(identifiant),
    )

    personnages = [
        Personnage(
            id=_identifiant(p["id"]),
            nom=p["nom"],
            espece=p["espece"],
            apparence=p["apparence"],
            caractere=p.get("caractere", ""),
            # voice_id vide : c'est `pdz voix apparier` qui le remplira, en
            # mesurant les voix disponibles plutôt qu'en en choisissant une
            # au hasard. Les réglages perçus servent de point de départ.
            voix=Voix(**_reglages_depuis_percu(p.get("voix_percue") or {})),
        )
        for p in charte["personnages"]
    ]

    decors = [
        Decor(id=_identifiant(d["id"]), nom=d["nom"], description=d["description"])
        for d in charte.get("decors", [])
    ]

    return Univers(
        id=identifiant,
        nom=nom,
        format=format,
        langue=langue,
        style=style,
        regles_du_monde=list(charte.get("regles_du_monde", [])),
        personnages=personnages,
        decors=decors,
        interdits=["marques réelles", "noms d'œuvres existantes"],
        duree_cible_s=duree_cible_s,
        empreinte_creative=_vers_empreinte(charte.get("creative_fingerprint"), adn),
    )


def _champ(brut: dict | None) -> ChampInterprete:
    """Un `{valeur, confiance, justification}` du modèle → `ChampInterprete`.

    Défensif plutôt que strict : un champ manquant ou mal formé retombe sur
    `unknown` plutôt que de faire échouer tout l'univers pour une charte par
    ailleurs exploitable.
    """
    brut = brut or {}
    return ChampInterprete(
        valeur=str(brut.get("valeur") or "unknown"),
        confiance=max(0.0, min(1.0, float(brut.get("confiance") or 0.0))),
        justification=str(brut.get("justification") or ""),
    )


def _vers_empreinte(brut: dict | None, adn: Adn | None) -> EmpreinteCreative | None:
    """Assemble l'empreinte créative. `None` si `charte` n'en a pas rendu —
    par exemple un ancien appel resté sur le prompt 1.0.0."""
    if not brut:
        return None

    hook = brut.get("hook") or {}
    narrative = brut.get("narrative") or {}
    visuel = brut.get("visuel") or {}

    return EmpreinteCreative(
        # Mesuré, jamais interprété — voir la docstring de la fonction.
        pacing=adn.contraintes() if adn is not None else {},
        hook=EmpreinteHook(
            type=_champ(hook.get("type")),
            mecanisme=_champ(hook.get("mecanisme")),
            promesse=_champ(hook.get("promesse")),
        ),
        narrative=EmpreinteNarrative(
            structure=_champ(narrative.get("structure")),
            escalade=_champ(narrative.get("escalade")),
            fin=_champ(narrative.get("fin")),
        ),
        curiosite=_champ(brut.get("curiosite")),
        arc_emotionnel=_champ(brut.get("arc_emotionnel")),
        retention=_champ(brut.get("retention")),
        visuel=EmpreinteVisuelle(
            style=_champ(visuel.get("style")),
            cadrage=_champ(visuel.get("cadrage")),
            son=_champ(visuel.get("son")),
        ),
        principes_reutilisables=list(brut.get("principes_reutilisables") or []),
        fonctions_plans=list(brut.get("fonctions_plans") or []),
    )


def _reglages_depuis_percu(percu: dict) -> dict:
    """Traduit « posé et las » ou « haut perché et pressé » en réglages.

    Le registre est conservé tel quel dans l'univers : c'est lui qui permettra
    de choisir une voix le jour où on n'a pas d'audio de référence à mesurer.
    """
    ton = (percu.get("ton") or "").lower()
    registre = percu.get("registre") or ""
    stabilite, style = 0.5, 0.45

    if any(m in ton for m in ("posé", "pose", "calme", "las", "monocorde", "grave")):
        stabilite, style = 0.75, 0.25
    if any(m in ton for m in ("pressé", "presse", "excité", "excite", "haut perché",
                              "haut perche", "nerveux", "théâtral", "theatral")):
        stabilite, style = 0.3, 0.75

    return {"stabilite": stabilite, "style": style,
            "registre_percu": registre if registre != "inconnu" else ""}


def _nettoyer_rendu(rendu: str) -> str:
    """Dernier filet avant le validateur de `Style`.

    Le prompt interdit déjà les noms d'œuvres ; ce nettoyage attrape les cas
    où le modèle glisse « in the style of X » malgré la consigne. Mieux vaut
    couper la formule que faire échouer toute l'analyse à la validation.
    """
    coupe = re.sub(r"\b(in the style of|inspired by|à la manière de)\b.*?(,|$)",
                   "", rendu, flags=re.IGNORECASE).strip()
    return re.sub(r"\s*,\s*,", ",", coupe).strip(" ,")


def _identifiant(brut: str) -> str:
    """Un id de fichier : minuscules, sans accent, sans espace."""
    import unicodedata

    sans_accent = "".join(
        c for c in unicodedata.normalize("NFD", brut)
        if unicodedata.category(c) != "Mn"
    )
    propre = re.sub(r"[^a-z0-9]+", "_", sans_accent.lower()).strip("_")
    return propre or "sans_nom"


def _graine(identifiant: str) -> int:
    """Graine stable dérivée du nom : reproductible d'une machine à l'autre.

    `hash()` de Python ne conviendrait pas — il est salé différemment à chaque
    lancement, et deux exécutions donneraient deux styles d'images.
    """
    return int(hashlib.sha256(identifiant.encode()).hexdigest()[:8], 16) % 1_000_000
