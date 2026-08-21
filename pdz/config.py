"""Configuration globale, lue depuis le fichier .env.

Un seul endroit pour les clés d'API, les chemins et les garde-fous de budget.
Rien d'autre dans le projet ne lit os.environ.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

RACINE = Path(__file__).resolve().parent.parent


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Clés d'API ────────────────────────────────────────────────────────
    anthropic_api_key: str = ""
    fal_key: str = ""
    elevenlabs_api_key: str = ""
    groq_api_key: str = ""          # transcription (parcours 2)
    perplexity_api_key: str = ""    # recherche web, optionnel
    skyreels_api_key: str = ""      # animation, alternative à fal.ai
    audd_api_key: str = ""          # reconnaissance musicale (`pdz musique`)

    # ── Chemins ───────────────────────────────────────────────────────────
    donnees: Path = RACINE / "donnees"

    # Les vidéos de référence privées. Lu ici et non dans
    # `pdz/analyse/references.py`, qui appelait `os.environ` en direct : la
    # docstring de ce module promet depuis toujours que rien d'autre ne lit
    # l'environnement, et c'était la dernière exception. Une configuration
    # lue à deux endroits est une configuration dont personne ne sait, de
    # l'extérieur, ce qui la détermine.
    #
    # `validation_alias` garde le nom historique de la variable : la
    # renommer casserait les installations qui l'utilisent, pour le seul
    # bénéfice d'une cohérence de préfixe.
    dossier_references: Path = Field(
        default=Path("donnees/references"),
        validation_alias="PDZ_DOSSIER_REFERENCES",
    )

    @field_validator("dossier_references", mode="before")
    @classmethod
    def _vide_vaut_defaut(cls, v):
        """Une variable vide veut dire « je n'ai rien choisi », pas « la
        racine ».

        `PDZ_DOSSIER_REFERENCES=` dans un `.env` donne la chaîne vide, que
        `Path` transforme en `Path(".")` — le dépôt entier. Quelqu'un qui
        copie `.env.exemple` verrait alors `pdz references` parcourir tout
        le projet au lieu du dossier prévu, sans un mot d'avertissement.
        """
        if v is None or (isinstance(v, str) and not v.strip()):
            return Path("donnees/references")
        return v

    # ── Garde-fous de budget ──────────────────────────────────────────────
    # Voir docs/07-budget.md. Ce sont les seules protections contre une
    # boucle d'appels qui viderait le budget d'un mois en une nuit.
    budget_mensuel_eur: float = 80.0
    budget_max_par_video_eur: float = 0.60
    budget_max_par_analyse_eur: float = 0.25

    # ── Réglages vidéo ────────────────────────────────────────────────────
    duree_cible_s: int = 90
    largeur: int = 1080
    hauteur: int = 1920
    fps: int = 30

    # ── Divers ────────────────────────────────────────────────────────────
    profil: str = "equilibre"       # economique | equilibre | premium
    langue: str = "fr"
    web_port: int = 7777
    log_niveau: str = "INFO"

    # ── Dossiers dérivés ──────────────────────────────────────────────────
    @property
    def base_sqlite(self) -> Path:
        return self.donnees / "pronotedz.db"

    @property
    def dossier_sources(self) -> Path:
        return self.donnees / "sources"

    @property
    def dossier_travail(self) -> Path:
        return self.donnees / "travail"

    @property
    def dossier_sorties(self) -> Path:
        return self.donnees / "sorties"

    @property
    def dossier_musique(self) -> Path:
        return self.donnees / "musique"

    @property
    def dossier_cache(self) -> Path:
        return self.donnees / "cache"

    def preparer_dossiers(self) -> None:
        for d in (
            self.donnees,
            self.dossier_sources,
            self.dossier_travail,
            self.dossier_sorties,
            self.dossier_musique,
            self.dossier_cache,
        ):
            d.mkdir(parents=True, exist_ok=True)

    def cles_manquantes(self, requises: tuple[str, ...]) -> list[str]:
        """Renvoie les clés d'API vides parmi celles demandées.

        Sert à échouer tôt et clairement plutôt qu'au premier appel HTTP.
        """
        return [nom for nom in requises if not getattr(self, nom, "")]


@lru_cache(maxsize=1)
def config() -> Config:
    return Config()
