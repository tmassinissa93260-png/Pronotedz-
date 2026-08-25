"""Ce qui est réellement branché, ici et maintenant.

Un adaptateur *existe* dans le dépôt ; il n'est *actif* que si son identifiant
est présent dans l'environnement. Ces deux états n'ont rien à voir, et les
confondre est exactement la façon dont un système se met à annoncer des
capacités qu'il n'a pas.

Ce module est la seule autorité sur la question « qui est branché ? ». Il
répond en lisant l'environnement, jamais en devinant, et **sans toucher au
réseau** : savoir si une clé est là est local et instantané ; savoir si le
service répond est une *mesure*, et cette mesure appartient à la matrice de
capacités (`pdz2.engines.governance.matrix`), qui la date et la conserve.

Deux règles tenues ici :

* **Le repli local est toujours dans la liste**, en dernier. Le moteur d'images
  procédural et le moteur de voix local ne dépendent de rien : ils sont la
  garantie de livraison, pas un plan B facultatif.
* **Une famille sans adaptateur reste vide.** Aucune entrée n'est fabriquée
  pour faire nombre — la bibliothèque de sons n'en a aucun, et le dit.

Chaque décision est accompagnée d'une note lisible : `ActiveProviders.notes`
explique pourquoi une famille est dans l'état où elle est, ce qui rend une
dégradation visible dans le journal plutôt que silencieuse.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from pdz2.audio.espeak import EspeakSynthesiser
from pdz2.audio.library import NO_SOUND_LIBRARIES, SoundLibrary
from pdz2.audio.ports import SpeechSynthesiser
from pdz2.engines.direction.ports import Reasoner
from pdz2.engines.imagery.renderer import ProceduralImageRenderer
from pdz2.providers.elevenlabs import ELEVENLABS_KEY_ENV, ElevenLabsSynthesiser
from pdz2.providers.fal import FAL_KEY_ENV, FalImageProvider, FalVideoProvider
from pdz2.providers.groq import GROQ_KEY_ENV, GroqReasoner
from pdz2.providers.image import ImageProvider
from pdz2.providers.reasoner import ANTHROPIC_KEY_ENV, AnthropicReasoner
from pdz2.providers.video import VideoProvider

__all__ = [
    "ActiveProviders",
    "active_providers",
    "CREDENTIAL_ENV",
    "REASONER_CHOICE_ENV",
    "ANTHROPIC_KEY_ENV",
    "ELEVENLABS_KEY_ENV",
    "FAL_KEY_ENV",
    "GROQ_KEY_ENV",
]

CREDENTIAL_ENV = {
    "fal": FAL_KEY_ENV,
    "elevenlabs": ELEVENLABS_KEY_ENV,
    "anthropic": ANTHROPIC_KEY_ENV,
    "groq": GROQ_KEY_ENV,
}
"""Quelle variable d'environnement active quel adaptateur. Rien de secret ici :
seuls les *noms* figurent, jamais les valeurs."""

REASONER_CHOICE_ENV = "PDZ2_REASONER"
"""Nom du raisonneur à employer quand plusieurs clés sont présentes.

Sans lui, l'ordre de `_REASONERS` tranche — un ordre fixe et lisible vaut
mieux qu'un hasard, mais il ne remplace pas une décision. Nommer ici
« groq » ou « anthropic » rend ce choix explicite, et écarte les autres."""

_REASONERS: tuple[tuple[str, str, type], ...] = (
    ("anthropic", ANTHROPIC_KEY_ENV, AnthropicReasoner),
    ("groq", GROQ_KEY_ENV, GroqReasoner),
)
"""Raisonneurs connus, dans l'ordre où ils sont retenus à défaut de choix."""


@dataclass(frozen=True)
class ActiveProviders:
    """L'ensemble des adaptateurs branchés, par famille, dans l'ordre d'essai.

    L'ordre est significatif : le premier est tenté d'abord, le dernier est le
    repli. Une famille peut être vide — c'est un état légitime, pas une panne.
    """

    video: tuple[VideoProvider, ...]
    image: tuple[ImageProvider, ...]
    speech: tuple[SpeechSynthesiser, ...]
    reasoners: tuple[Reasoner, ...]
    sound_libraries: tuple[SoundLibrary, ...]
    notes: tuple[str, ...]

    @property
    def reasoner(self) -> Reasoner | None:
        """Le raisonneur à employer, ou `None` : le brief sera alors écrit à la main."""
        return self.reasoners[0] if self.reasoners else None

    def summary(self) -> str:
        return "\n".join(self.notes)


def _present(env: Mapping[str, str], key: str) -> bool:
    return bool(env.get(key, "").strip())


def _reasoners(env: Mapping[str, str]) -> tuple[tuple[Reasoner, ...], str]:
    """Les raisonneurs branchés, et la phrase qui explique lequel décidera.

    Un choix explicite l'emporte sur l'ordre. S'il désigne un raisonneur dont
    la clé manque, on ne se rabat pas en silence sur un autre : le brief
    serait rédigé par quelqu'un d'autre que celui qu'on a nommé, et personne
    ne le saurait avant de lire la signature du contrat.
    """
    disponibles = [
        (nom, fabrique) for nom, cle, fabrique in _REASONERS if _present(env, cle)
    ]
    manquantes = ", ".join(cle for _, cle, _ in _REASONERS)

    choisi = env.get(REASONER_CHOICE_ENV, "").strip().lower()
    if choisi:
        connus = {nom for nom, _, _ in _REASONERS}
        if choisi not in connus:
            return (), (
                f"raisonneur : {REASONER_CHOICE_ENV}={choisi!r} inconnu "
                f"(attendu : {', '.join(sorted(connus))}) — aucun raisonneur"
            )
        retenu = [(nom, fab) for nom, fab in disponibles if nom == choisi]
        if not retenu:
            cle = next(c for n, c, _ in _REASONERS if n == choisi)
            return (), (
                f"raisonneur : {choisi} demandé par {REASONER_CHOICE_ENV}, mais "
                f"{cle} est absente — aucun repli, le brief est à rédiger à la main"
            )
        return (retenu[0][1](),), f"raisonneur : {choisi} (choisi par {REASONER_CHOICE_ENV})"

    if not disponibles:
        return (), (
            f"raisonneur : aucun ({manquantes} absentes) — brief à rédiger à la main"
        )
    premier = disponibles[0][0]
    if len(disponibles) == 1:
        return (disponibles[0][1](),), f"raisonneur : {premier} (seule clé présente)"
    autres = ", ".join(nom for nom, _ in disponibles[1:])
    return (
        tuple(fabrique() for _, fabrique in disponibles),
        f"raisonneur : {premier} — {autres} aussi branché(s), "
        f"nommer le voulu dans {REASONER_CHOICE_ENV} pour trancher",
    )


def active_providers(env: Mapping[str, str] | None = None) -> ActiveProviders:
    """Assemble les familles d'adaptateurs à partir de l'environnement.

    `env` est injectable pour que les tests décrivent un environnement sans en
    fabriquer un vrai.
    """
    env = os.environ if env is None else env
    notes: list[str] = []

    fal = _present(env, FAL_KEY_ENV)
    video: tuple[VideoProvider, ...] = (FalVideoProvider(),) if fal else ()
    image: tuple[ImageProvider, ...] = (
        (FalImageProvider(), ProceduralImageRenderer())
        if fal
        else (ProceduralImageRenderer(),)
    )
    notes.append(
        f"images : distant + repli procédural ({FAL_KEY_ENV} présente)"
        if fal
        else f"images : moteur procédural local seul ({FAL_KEY_ENV} absente)"
    )
    notes.append(
        f"vidéo : un fournisseur génératif ({FAL_KEY_ENV} présente)"
        if fal
        else f"vidéo : aucun fournisseur génératif ({FAL_KEY_ENV} absente) — "
        "les stratégies déterministes rendront seules"
    )

    voix = _present(env, ELEVENLABS_KEY_ENV)
    speech: tuple[SpeechSynthesiser, ...] = (
        (ElevenLabsSynthesiser(), EspeakSynthesiser())
        if voix
        else (EspeakSynthesiser(),)
    )
    notes.append(
        f"voix : distante + repli local ({ELEVENLABS_KEY_ENV} présente)"
        if voix
        else f"voix : moteur local seul ({ELEVENLABS_KEY_ENV} absente)"
    )

    reasoners, note = _reasoners(env)
    notes.append(note)

    notes.append("sons : aucune bibliothèque implémentée — les repères resteront non résolus")

    return ActiveProviders(
        video=video,
        image=image,
        speech=speech,
        reasoners=reasoners,
        sound_libraries=NO_SOUND_LIBRARIES,
        notes=tuple(notes),
    )
