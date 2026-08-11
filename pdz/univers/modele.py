"""Un Univers = un monde réutilisable : ses personnages, son style, ses règles.

C'est la pièce centrale du système. On le définit **une fois**, on produit des
dizaines d'épisodes avec.

Le point important : le modèle ne sait rien des fruits, des voitures ou des animes.
Un personnage a une `espece` qui est une chaîne libre — « fraise », « vieille Renault 4L
rouillée », « apprenti ninja ». Le système ne code aucune niche en dur, jamais.

Voir docs/12-videos-a-personnages.md et docs/13-les-formats.md.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator


class Format(str, Enum):
    """D'où viennent les images. C'est la seule chose qui change vraiment
    entre les formats — le reste de la chaîne est commun."""

    SERIE_ANIMEE = "serie_animee"            # fiches → images → animation
    NARRATION_GENEREE = "narration_generee"  # images générées, pas d'animation
    NARRATION_METRAGE = "narration_metrage"  # métrage fourni par moi


class Voix(BaseModel):
    """La voix d'un personnage. Fixe pour toujours : c'est ce qui fait
    qu'on le reconnaît d'un épisode à l'autre."""

    fournisseur: str = "elevenlabs"
    voice_id: str = ""
    stabilite: float = Field(0.5, ge=0, le=1)
    style: float = Field(0.5, ge=0, le=1)
    vitesse: float = Field(1.0, ge=0.5, le=2.0)

    # Le registre attendu — « grave », « aigu »… Renseigné par l'analyse d'une
    # vidéo de référence, ou à la main. Sert à choisir la voix quand on n'a
    # aucun audio à mesurer : c'est une intention, pas une mesure.
    registre_percu: str = ""


class Personnage(BaseModel):
    id: str
    nom: str

    # Chaîne libre : « fraise », « Renault 4L rouillée », « apprenti ninja »…
    espece: str

    # Description visuelle détaillée. C'est elle qui part dans chaque prompt
    # d'image — d'où la constance d'un plan à l'autre.
    apparence: str

    # La planche de référence, générée une fois puis réutilisée à l'infini.
    fiche_image: Path | None = None

    caractere: str = ""
    tics_de_langage: list[str] = Field(default_factory=list)
    voix: Voix = Field(default_factory=Voix)

    # Relations : {"bananito": "l'a trahi à l'épisode 3"}
    relations: dict[str, str] = Field(default_factory=dict)

    def prompt_image(self, situation: str, style: Style) -> str:
        """Construit le prompt d'un plan. L'apparence passe TOUJOURS en entier :
        c'est le prix de la constance."""
        morceaux = [
            self.apparence.strip(),
            situation.strip(),
            style.rendu.strip(),
        ]
        if style.eclairage:
            morceaux.append(style.eclairage.strip())
        return ", ".join(m for m in morceaux if m)


class Style(BaseModel):
    """L'identité visuelle. Un « style anime 90s » et un « rendu 3D Pixar »
    sont deux valeurs de ce même objet — rien d'autre ne change."""

    rendu: str                       # « 3D render, Pixar-like » / « 90s cel-shaded anime »
    palette: list[str] = Field(default_factory=list)
    eclairage: str = ""
    ambiance: str = ""
    ratio: str = "9:16"

    # Contraintes envoyées à CHAQUE prompt d'image, en anglais comme le reste
    # du prompt. `regles_du_monde` et `interdits` ne conviennent pas pour ça :
    # ils sont rédigés en français, pour l'agent d'écriture, et un prompt
    # mélangeant deux langues rend moins bien. Mesuré à l'écran : un univers
    # qui interdit les visages en a vu apparaître un, faute de le dire au
    # générateur d'images.
    consignes_image: list[str] = Field(default_factory=list)

    # Graine fixe : deux images de la même série gardent la même patte.
    seed: int | None = None

    @field_validator("rendu")
    @classmethod
    def _pas_de_reference_protegee(cls, v: str) -> str:
        """Bloque les mentions d'œuvres protégées dans les prompts d'images.

        Un style graphique ne se protège pas, un personnage si. Décrire le style
        par ses caractéristiques est à la fois plus sûr et plus efficace : les
        modèles rendent mieux une description précise qu'une référence.
        Voir docs/13-les-formats.md § B.
        """
        interdits = (
            "naruto", "dragon ball", "goku", "one piece", "luffy", "pokemon",
            "pikachu", "disney", "pixar movie", "studio ghibli", "totoro",
            "mickey", "marvel", "star wars", "sailor moon", "demon slayer",
        )
        bas = v.lower()
        for mot in interdits:
            if mot in bas:
                raise ValueError(
                    f"« {mot} » est une œuvre ou un personnage protégé. "
                    "Décris le style par ses caractéristiques visuelles "
                    "(cel-shading, palette, cadrage, éclairage) plutôt que par "
                    "une référence — c'est plus sûr et ça rend mieux."
                )
        return v


class Decor(BaseModel):
    id: str
    nom: str
    description: str


class Univers(BaseModel):
    """Un monde complet. Une niche = un univers."""

    id: str
    nom: str
    format: Format = Format.SERIE_ANIMEE
    langue: str = "fr"

    style: Style
    regles_du_monde: list[str] = Field(default_factory=list)
    personnages: list[Personnage] = Field(default_factory=list)
    decors: list[Decor] = Field(default_factory=list)

    # Sujets, mots ou situations à ne jamais produire dans cet univers.
    interdits: list[str] = Field(default_factory=list)

    duree_cible_s: int = 45
    episodes_produits: int = 0

    # ── Accès ────────────────────────────────────────────────────────────

    def personnage(self, id_: str) -> Personnage | None:
        return next((p for p in self.personnages if p.id == id_), None)

    def decor(self, id_: str) -> Decor | None:
        return next((d for d in self.decors if d.id == id_), None)

    @property
    def anime(self) -> bool:
        return self.format is Format.SERIE_ANIMEE

    def contexte_script(self) -> str:
        """Le bloc injecté dans le prompt d'écriture.

        Il est stable d'un épisode à l'autre → il est mis en cache côté Claude,
        ce qui réduit fortement le coût d'entrée sur une série.
        """
        lignes = [f"UNIVERS : {self.nom}", f"AMBIANCE : {self.style.ambiance}", ""]

        if self.regles_du_monde:
            lignes.append("RÈGLES DU MONDE :")
            lignes += [f"- {r}" for r in self.regles_du_monde]
            lignes.append("")

        lignes.append("PERSONNAGES (utilise l'identifiant entre crochets dans le champ "
                      "« personnage » de chaque réplique, jamais le nom affiché) :")
        for p in self.personnages:
            bout = f"- [{p.id}] {p.nom} ({p.espece}) : {p.caractere}"
            if p.tics_de_langage:
                bout += f" — dit souvent : {', '.join(p.tics_de_langage)}"
            lignes.append(bout)
            for autre, rel in p.relations.items():
                lignes.append(f"    · avec {autre} : {rel}")

        if self.decors:
            lignes += ["", "DÉCORS (même règle, utilise l'identifiant entre crochets) :"] + [
                f"- [{d.id}] {d.nom} : {d.description}" for d in self.decors
            ]

        if self.interdits:
            lignes += ["", "INTERDITS :"] + [f"- {i}" for i in self.interdits]

        return "\n".join(lignes)

    # ── Chargement / sauvegarde ──────────────────────────────────────────

    @classmethod
    def charger(cls, chemin: Path) -> Univers:
        donnees = yaml.safe_load(Path(chemin).read_text(encoding="utf-8"))
        return cls.model_validate(donnees)

    def sauver(self, chemin: Path) -> None:
        Path(chemin).write_text(
            yaml.safe_dump(
                self.model_dump(mode="json", exclude_none=True),
                allow_unicode=True, sort_keys=False,
            ),
            encoding="utf-8",
        )
