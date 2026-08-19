"""L'enveloppe commune à tous les contrats — la source de vérité du système.

Un contrat n'est pas un `dict` avec des noms de clés convenus : c'est une
structure typée, versionnée, qui sait d'où elle vient et de quoi elle dépend.
La différence se voit le jour où un champ change de sens — un `dict` continue
de se relire sans bruit et produit une vidéo faite de deux générations de
décisions mélangées ; un contrat versionné, lui, refuse ou migre.

Ce que le dépôt faisait déjà, et qu'on généralise ici : les prompts sont des
fichiers `<id>@<semver>.yaml`, leur version entre dans la signature de
l'agent, donc dans l'empreinte de cache. Changer un prompt invalide son cache
tout seul, sans purge manuelle. C'est exactement le mécanisme que ce module
étend aux ÉTATS, et pas seulement aux instructions.

── Ce module n'importe rien d'autre de `pdz` ─────────────────────────────

C'est vérifié par `tests/test_architecture.py`. Un contrat qui dépendrait
d'un module de production ne serait plus une source de vérité, seulement une
vue sur du code — et le sens de la dépendance s'inverserait.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from typing import Any, ClassVar, TypeVar

from pydantic import BaseModel, ConfigDict, Field

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")

T = TypeVar("T", bound="Contrat")


class ErreurContrat(Exception):
    """Un contrat ne peut pas être relu, ou l'être sans perdre son sens.

    Volontairement une exception à part, et non une `ErreurValidation` du
    moteur : celle-ci se relance en montrant l'erreur au modèle, ce qui n'a
    aucun sens ici. Un contrat illisible est un problème de code ou de
    migration, jamais quelque chose qu'un modèle peut corriger.
    """


class Provenance(BaseModel):
    """D'où vient ce contrat — la réponse à « pourquoi cette vidéo est ainsi ».

    Aucun champ n'est obligatoire : une provenance partielle vaut mieux
    qu'une provenance inventée. Ce qui est inconnu reste vide, jamais
    rempli d'une valeur plausible.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    producteur: str = ""            # « ShotPromptWriter@1.4.0 », « storyboard.decouper »
    modele: str = ""                # l'identifiant RÉSOLU, pas l'alias
    fournisseur: str = ""
    prompt_ref: str = ""            # « ecriture/plans@1.14.0 »
    strategie: str = ""             # « 2.5D », « DIRECT_I2V »…
    version_compilateur: str = ""
    cout_eur: float = 0.0
    duree_ms: int = 0
    # Les contrats qui ont servi d'entrée, par leur id. C'est ce qui permet
    # de remonter une vidéo jusqu'à la phrase qui l'a demandée.
    entrees: tuple[str, ...] = ()


class Contrat(BaseModel):
    """La classe mère. Tout contrat du système en hérite.

    `VERSION` est déclarée par la sous-classe et n'est PAS un champ : deux
    instances d'un même contrat partagent forcément leur version de schéma,
    la stocker par instance inviterait à les faire diverger. Elle est
    recopiée dans `schema_version` à la sérialisation, où elle sert à
    décider comment relire.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    VERSION: ClassVar[str] = "1.0.0"
    # Nom stable du contrat dans les journaux et le cache. Par défaut le nom
    # de la classe ; une sous-classe renommée doit garder l'ancien nom ici
    # plutôt que de casser la relecture de tout l'historique.
    NOM: ClassVar[str] = ""

    id: str = ""
    cree_le: float = 0.0
    maj_le: float = 0.0
    provenance: Provenance = Field(default_factory=Provenance)
    dependances: tuple[str, ...] = ()

    # ── Identité ─────────────────────────────────────────────────────────

    @classmethod
    def nom(cls) -> str:
        return cls.NOM or cls.__name__

    @classmethod
    def reference(cls) -> str:
        """« ShotSpec@1.0.0 » — la même forme que les références de prompt,
        volontairement : c'est déjà la convention du dépôt, et une seule
        forme de référence vaut mieux que deux."""
        return f"{cls.nom()}@{cls.VERSION}"

    # ── Sérialisation ────────────────────────────────────────────────────

    def en_dict(self) -> dict[str, Any]:
        """La forme sérialisable, avec sa version.

        `schema_version` est ajoutée ici et non portée en champ : elle
        décrit le contenant, pas le contenu, et un champ modifiable
        laisserait écrire un contrat qui ment sur sa propre version.
        """
        brut = self.model_dump(mode="json")
        return {"schema_version": self.VERSION, "contrat": self.nom(), **brut}

    def en_json(self) -> str:
        """JSON déterministe : clés triées, pas d'échappement Unicode.

        Le déterminisme n'est pas cosmétique — c'est ce qui rend
        `empreinte()` reproductible d'une exécution à l'autre. Un dump non
        trié produirait deux empreintes pour un même contenu, et le taux de
        réutilisation du cache tomberait à zéro sans que rien ne le signale.
        """
        return json.dumps(self.en_dict(), ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), default=str)

    def empreinte(self) -> str:
        """sha256 du contrat, version comprise.

        Deux contrats identiques au champ près mais de versions différentes
        ont deux empreintes différentes : c'est précisément la propriété qui
        empêche un artefact produit sous l'ancien sens d'être réutilisé sous
        le nouveau.
        """
        return hashlib.sha256(self.en_json().encode("utf-8")).hexdigest()

    # ── Relecture ────────────────────────────────────────────────────────

    @classmethod
    def depuis_dict(cls: type[T], donnees: dict[str, Any]) -> T:
        """Relit un contrat, en le migrant si sa version est antérieure.

        Trois refus explicites, parce que chacun cache un bug différent :
          · version absente → la donnée ne vient pas d'un contrat ;
          · version FUTURE → le fichier a été écrit par un code plus récent,
            le relire au format actuel perdrait silencieusement des champs ;
          · aucun chemin de migration → mieux vaut une erreur nette qu'un
            contrat à moitié compris.
        """
        if not isinstance(donnees, dict):
            raise ErreurContrat(f"{cls.nom()} : attendu un dict, reçu {type(donnees).__name__}")

        donnees = dict(donnees)
        version = donnees.pop("schema_version", None)
        donnees.pop("contrat", None)

        if version is None:
            raise ErreurContrat(
                f"{cls.nom()} : aucune `schema_version`. Cette donnée n'a pas "
                f"été écrite par un contrat — la relire comme tel supposerait "
                f"que ses champs ont le sens qu'on leur prête aujourd'hui."
            )
        if not SEMVER.match(str(version)):
            raise ErreurContrat(f"{cls.nom()} : version « {version} » n'est pas du semver.")

        if version != cls.VERSION:
            if _plus_recent(str(version), cls.VERSION):
                raise ErreurContrat(
                    f"{cls.nom()}@{version} a été écrit par une version PLUS "
                    f"RÉCENTE que celle de ce code ({cls.VERSION}). Relire en "
                    f"arrière perdrait ce que cette version savait en plus. "
                    f"Mets le code à jour plutôt que la donnée."
                )
            donnees = migrer(cls, str(version), donnees)

        try:
            return cls.model_validate(donnees)
        except Exception as e:  # noqa: BLE001 — retypée, jamais avalée
            raise ErreurContrat(f"{cls.nom()}@{cls.VERSION} illisible : {e}") from e

    @classmethod
    def depuis_json(cls: type[T], brut: str) -> T:
        try:
            donnees = json.loads(brut)
        except json.JSONDecodeError as e:
            raise ErreurContrat(f"{cls.nom()} : JSON invalide — {e}") from e
        return cls.depuis_dict(donnees)


# ── Migrations ───────────────────────────────────────────────────────────
#
# Une migration transforme le DICT d'une version vers la suivante, avant
# validation. Volontairement sur le dict et non sur l'objet : à ce stade
# l'objet ne peut pas encore exister, c'est tout l'intérêt.
#
# Le registre est vide au départ, et c'est normal — tous les contrats
# naissent en 1.0.0. Il existe dès maintenant pour que la PREMIÈRE évolution
# de schéma ait un endroit évident où aller, plutôt que d'être bricolée à
# l'endroit où elle fait mal.

Migration = Callable[[dict[str, Any]], dict[str, Any]]

_MIGRATIONS: dict[tuple[str, str, str], Migration] = {}


def enregistrer_migration(contrat: str, de: str, vers: str) -> Callable[[Migration], Migration]:
    """Déclare comment passer un contrat d'une version à la suivante.

        @enregistrer_migration("ShotSpec", "1.0.0", "1.1.0")
        def _ajoute_le_but(d):
            d["but"] = ""      # champ neuf : valeur neutre, jamais devinée
            return d
    """
    def decorer(fn: Migration) -> Migration:
        cle = (contrat, de, vers)
        if cle in _MIGRATIONS:
            raise ErreurContrat(f"Migration déjà déclarée : {contrat} {de} → {vers}")
        _MIGRATIONS[cle] = fn
        return fn
    return decorer


def migrer(contrat: type[Contrat], depuis: str, donnees: dict[str, Any]) -> dict[str, Any]:
    """Enchaîne les migrations de `depuis` jusqu'à la version du code.

    Suit les sauts déclarés un par un plutôt que de tenter un chemin
    direct : chaque migration reste ainsi lisible seule, et une chaîne
    interrompue se voit tout de suite au lieu de produire un contrat
    partiellement converti.
    """
    nom, courante = contrat.nom(), depuis
    vu: set[str] = set()

    while courante != contrat.VERSION:
        if courante in vu:
            raise ErreurContrat(f"{nom} : boucle de migration sur {courante}")
        vu.add(courante)

        suite = [(d, v) for (c, d, v) in _MIGRATIONS if c == nom and d == courante]
        if not suite:
            raise ErreurContrat(
                f"{nom}@{courante} ne sait pas devenir {contrat.VERSION} : "
                f"aucune migration déclarée depuis {courante}. Écris-la avec "
                f"`@enregistrer_migration(\"{nom}\", \"{courante}\", …)` — un "
                f"contrat qu'on relit sans migration est un contrat dont on a "
                f"oublié ce qu'il voulait dire."
            )
        if len(suite) > 1:
            raise ErreurContrat(
                f"{nom}@{courante} a {len(suite)} migrations sortantes : "
                f"le chemin est ambigu, il ne doit y en avoir qu'un."
            )

        _, vers = suite[0]
        donnees = _MIGRATIONS[(nom, courante, vers)](dict(donnees))
        courante = vers

    return donnees


def _plus_recent(a: str, b: str) -> bool:
    return tuple(int(x) for x in a.split(".")) > tuple(int(x) for x in b.split("."))


def versions(*contrats: type[Contrat]) -> dict[str, str]:
    """Les versions d'un jeu de contrats, prêtes à entrer dans une signature.

    C'est le pont avec le cache existant : une étape qui produit ou consomme
    des contrats ajoute le résultat de cet appel à `Agent.signature()`, et
    son cache s'invalide tout seul quand un de ces schémas change — le même
    mécanisme, mot pour mot, que celui des versions de prompt.

    **Opt-in, volontairement.** Une étape qui ne manipule aucun contrat n'a
    rien à déclarer et son cache reste valide : invalider aujourd'hui les
    productions de tout le dépôt pour des contrats que rien ne consomme
    encore ferait repayer des vidéos déjà faites, sans rien garantir de plus.
    """
    return {c.nom(): c.VERSION for c in sorted(contrats, key=lambda c: c.nom())}
