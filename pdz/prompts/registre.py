"""Les prompts sont des fichiers versionnés, pas du code.

Un prompt a un `id`, une `version` semver et un historique. On peut le modifier,
comparer deux versions, revenir en arrière — sans toucher au programme.

La version utilisée est enregistrée avec chaque étape : quand une vidéo est
réussie, on sait exactement quel prompt l'a produite. Et quand elle est ratée,
on sait quoi corriger.

Voir docs/06-solidite.md § « Les prompts sont versionnés ».
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml
from jinja2 import BaseLoader, Environment, StrictUndefined
from pydantic import BaseModel, Field

from pdz.moteur.erreurs import ErreurConfig, ErreurValidation

CATALOGUE = Path(__file__).parent / "catalogue"

# `ecriture/script@1.2.0.yaml`
MOTIF = re.compile(r"^(?P<id>.+)@(?P<version>\d+\.\d+\.\d+)$")

_jinja = Environment(
    loader=BaseLoader(),
    undefined=StrictUndefined,   # une variable oubliée échoue tout de suite
    trim_blocks=True,
    lstrip_blocks=True,
    autoescape=False,
)


class Prompt(BaseModel):
    id: str
    version: str
    statut: str = "stable"           # brouillon | canari | stable | deprecie
    alias_modele: str = "qualite"
    temperature: float | None = None
    max_tokens: int = 4000

    # Le bloc mis en cache côté Claude : tout ce qui ne change pas d'un
    # épisode à l'autre. C'est lui qui fait baisser le coût sur une série.
    systeme_stable: str = ""
    systeme_variable: str = ""
    message: str

    entrees: dict[str, dict] = Field(default_factory=dict)
    schema_sortie: dict = Field(default_factory=dict)
    historique: str = ""

    @property
    def ref(self) -> str:
        return f"{self.id}@{self.version}"

    def rendre(self, **variables) -> tuple[str, str, str]:
        """Renvoie (systeme_stable, systeme_variable, message) prêts à l'envoi."""
        manquantes = [
            nom for nom, spec in self.entrees.items()
            if spec.get("requis", True) and nom not in variables
        ]
        if manquantes:
            raise ErreurValidation(
                f"{self.ref} : variables manquantes → {', '.join(manquantes)}"
            )
        try:
            return (
                _jinja.from_string(self.systeme_stable).render(**variables),
                _jinja.from_string(self.systeme_variable).render(**variables),
                _jinja.from_string(self.message).render(**variables),
            )
        except Exception as e:
            raise ErreurValidation(f"{self.ref} : rendu impossible — {e}") from e


@lru_cache(maxsize=64)
def charger(reference: str) -> Prompt:
    """`ecriture/script` → dernière version stable.
    `ecriture/script@1.0.0` → cette version exactement.
    """
    if (m := MOTIF.match(reference)):
        chemin = CATALOGUE / f"{m['id']}@{m['version']}.yaml"
        if not chemin.exists():
            raise ErreurConfig(f"Prompt introuvable : {reference}")
        return _lire(chemin)

    candidats = sorted(
        CATALOGUE.glob(f"{reference}@*.yaml"),
        key=lambda p: _cle_version(p.stem.split("@")[1]),
        reverse=True,
    )
    if not candidats:
        raise ErreurConfig(
            f"Aucun prompt « {reference} » dans {CATALOGUE}. "
            f"Disponibles : {', '.join(sorted(p.stem for p in CATALOGUE.rglob('*.yaml')))}"
        )
    for chemin in candidats:
        prompt = _lire(chemin)
        if prompt.statut == "stable":
            return prompt
    return _lire(candidats[0])


def versions(id_prompt: str) -> list[str]:
    return sorted(
        (p.stem.split("@")[1] for p in CATALOGUE.glob(f"{id_prompt}@*.yaml")),
        key=_cle_version, reverse=True,
    )


def _lire(chemin: Path) -> Prompt:
    return Prompt.model_validate(yaml.safe_load(chemin.read_text(encoding="utf-8")))


def _cle_version(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))
