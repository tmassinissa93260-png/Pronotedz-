"""Le registre de modèles : résout un alias en modèle concret, calcule le coût.

Les agents demandent une capacité (« qualite », « images »), jamais un
fournisseur. C'est ce qui permet de changer de modèle en éditant `modeles.yaml`,
sans toucher au code.

Voir docs/09-les-fichiers.md § « Le fichier modeles.yaml ».
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from pdz.config import RACINE, config
from pdz.moteur.erreurs import ErreurConfig

log = logging.getLogger(__name__)


class Prix(BaseModel):
    entree_par_million: float = 0.0
    sortie_par_million: float = 0.0
    par_image: float = 0.0
    par_seconde: float = 0.0
    par_1000_caracteres: float = 0.0
    par_heure_audio: float = 0.0


class Cache(BaseModel):
    lecture: float = 0.10     # part du prix d'entrée pour un jeton relu du cache
    ecriture: float = 1.25    # surcoût pour écrire dans le cache


class Modele(BaseModel):
    id: str
    fournisseur: str
    fait: list[str] = Field(default_factory=list)
    contexte: int = 0
    prix: Prix = Field(default_factory=Prix)
    cache: Cache = Field(default_factory=Cache)
    sorties_structurees: bool = False
    options: list[str] = Field(default_factory=list)

    def cout_texte(self, entree: int, sortie: int,
                   cache_lu: int = 0, cache_ecrit: int = 0) -> float:
        """Coût réel d'un appel, cache compris.

        Les jetons relus du cache sont facturés ~10 % : sur une série, où le
        contexte d'univers est identique d'un épisode à l'autre, ça fait la
        différence entre un projet viable et une facture qui dérape.
        """
        p = self.prix
        neufs = max(0, entree - cache_lu - cache_ecrit)
        return (
            neufs * p.entree_par_million / 1_000_000
            + cache_lu * p.entree_par_million * self.cache.lecture / 1_000_000
            + cache_ecrit * p.entree_par_million * self.cache.ecriture / 1_000_000
            + sortie * p.sortie_par_million / 1_000_000
        )

    def cout_unites(self, nombre: float, unite: str) -> float:
        table = {
            "image": self.prix.par_image,
            "seconde": self.prix.par_seconde,
            "caractere": self.prix.par_1000_caracteres / 1000,
            "heure_audio": self.prix.par_heure_audio,
        }
        if unite not in table:
            raise ErreurConfig(f"Unité de facturation inconnue : {unite}")
        return nombre * table[unite]


class Resolution(BaseModel):
    """Ce que le registre renvoie : le modèle à utiliser, et pourquoi."""

    modele: Modele
    alias: str
    temperature: float | None = None
    replis: list[str] = Field(default_factory=list)
    raison: str = "alias par défaut"


class Registre:
    def __init__(self, donnees: dict[str, Any]):
        self._brut = donnees
        self.modeles: dict[str, Modele] = {
            m["id"]: Modele.model_validate(m) for m in donnees.get("modeles", [])
        }
        self.alias: dict[str, dict] = donnees.get("alias", {})
        self.profils: dict[str, dict] = donnees.get("profils", {})
        self.regles: list[dict] = donnees.get("regles", [])

    # ── Résolution ────────────────────────────────────────────────────────

    def resoudre(self, alias: str, *, profil: str = "equilibre",
                 budget_restant_pct: float = 100.0,
                 repli_si_cle_absente: bool = False) -> Resolution:
        """alias → modèle concret, en tenant compte du profil et du budget.

        Ordre de priorité, du plus fort au plus faible :
          1. les règles de budget (elles peuvent tout écraser)
          2. le profil actif
          3. l'alias par défaut

        `repli_si_cle_absente` ajoute une dernière étape : si la clé du
        fournisseur retenu n'est pas renseignée, prendre un modèle de même
        capacité chez un fournisseur utilisable. C'est ce qui évite qu'un
        `--profil equilibre` s'arrête net sur « clé Anthropic manquante »
        alors qu'une clé Groq parfaitement fonctionnelle est configurée.
        Réservé aux chemins d'exécution : la résolution reste pure quand on
        interroge le registre pour savoir ce qu'un profil *désigne*.
        """
        entree = self.alias.get(alias)
        if entree is None:
            raise ErreurConfig(
                f"Alias inconnu : « {alias} ». "
                f"Connus : {', '.join(sorted(self.alias))}"
            )

        id_modele = entree["principal"]
        raison = "alias par défaut"

        if (surcharge := self.profils.get(profil, {}).get(alias)):
            id_modele, raison = surcharge, f"profil « {profil} »"

        for regle in self.regles:
            if self._regle_active(regle.get("si", {}), budget_restant_pct):
                alors = regle.get("alors", {})
                if alors.get("stop"):
                    raise ErreurConfig(
                        f"Budget épuisé ({budget_restant_pct:.0f} % restant) : "
                        "production interrompue par sécurité."
                    )
                if alias in alors:
                    id_modele = alors[alias]
                    raison = f"budget bas ({budget_restant_pct:.0f} % restant)"
                break

        modele = self.modeles.get(id_modele)
        if modele is None:
            raise ErreurConfig(f"Modèle « {id_modele} » absent de modeles.yaml")

        if repli_si_cle_absente and not self.cle_disponible(modele.fournisseur):
            if (equivalent := self._equivalent_disponible(modele)) is not None:
                log.warning(
                    "Clé %s absente : %s remplacé par %s (%s). Renseigne %s "
                    "pour retrouver la qualité prévue par le profil « %s ».",
                    modele.fournisseur, modele.id, equivalent.id,
                    equivalent.fournisseur,
                    self._nom_cle(modele.fournisseur), profil,
                )
                raison = (f"clé {modele.fournisseur} absente, repli sur "
                          f"{equivalent.fournisseur}")
                modele = equivalent

        replis = [entree["repli"]] if "repli" in entree else []
        return Resolution(
            modele=modele, alias=alias, replis=replis,
            temperature=entree.get("temperature"), raison=raison,
        )

    def option_profil(self, profil: str, cle: str, defaut: Any = None) -> Any:
        """Lit un réglage non-modèle du profil : `animer`, `plans_animes_max`…"""
        return self.profils.get(profil, {}).get(cle, defaut)

    def _regle_active(self, condition: dict, budget_pct: float) -> bool:
        seuil = condition.get("budget_restant_pourcent")
        if seuil is None:
            return False
        texte = str(seuil).strip()
        if texte.startswith("<"):
            return budget_pct < float(texte[1:])
        if texte.startswith(">"):
            return budget_pct > float(texte[1:])
        return budget_pct == float(texte)

    def _nom_cle(self, fournisseur: str) -> str:
        """« ANTHROPIC_API_KEY » — le nom de variable à renseigner."""
        infos = self._brut.get("fournisseurs", {}).get(fournisseur) or {}
        return infos.get("cle", "").upper()

    def cle_disponible(self, fournisseur: str) -> bool:
        """Dit si ce fournisseur est utilisable, sans lever d'exception.

        Un fournisseur déclaré sans champ `cle` (Pollinations) n'en demande
        aucune : il est toujours disponible.
        """
        infos = self._brut.get("fournisseurs", {}).get(fournisseur)
        if infos is None:
            return False
        if "cle" not in infos:
            return True
        return bool(getattr(config(), infos["cle"], ""))

    def _equivalent_disponible(self, modele: Modele) -> Modele | None:
        """Un modèle de même capacité chez un fournisseur utilisable.

        L'égalité de capacité passe par `fait` : c'est le seul vocabulaire
        commun aux modèles, et il empêche par construction de proposer une
        voix là où il faut une image. Le premier trouvé gagne, donc l'ordre
        de `modeles.yaml` fait office de préférence.
        """
        for candidat in self.modeles.values():
            if candidat.id == modele.id:
                continue
            if not set(candidat.fait) & set(modele.fait):
                continue
            if self.cle_disponible(candidat.fournisseur):
                return candidat
        return None

    def cle_fournisseur(self, fournisseur: str) -> str:
        infos = self._brut.get("fournisseurs", {}).get(fournisseur)
        if infos is None:
            raise ErreurConfig(f"Fournisseur inconnu : {fournisseur}")
        valeur = getattr(config(), infos["cle"], "")
        if not valeur:
            raise ErreurConfig(
                f"Clé d'API manquante pour {fournisseur}. "
                f"Renseigne {infos['cle'].upper()} dans le fichier .env "
                "(copie .env.exemple si tu ne l'as pas encore fait)."
            )
        return valeur

    def base_url(self, fournisseur: str) -> str:
        return self._brut["fournisseurs"][fournisseur]["base_url"]


@lru_cache(maxsize=1)
def registre(chemin: Path | None = None) -> Registre:
    fichier = chemin or RACINE / "modeles.yaml"
    if not fichier.exists():
        raise ErreurConfig(f"modeles.yaml introuvable : {fichier}")
    return Registre(yaml.safe_load(fichier.read_text(encoding="utf-8")))
