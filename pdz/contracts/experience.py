"""Ce qu'une exécution a réellement coûté, produit, et raté.

**Le contrat dont le retard coûte le plus cher.** Tant que ces lignes ne sont
pas écrites, aucun routage empirique n'est possible — pas parce que
l'algorithme manque, mais parce que la DONNÉE n'existe pas. Chaque production
faite sans enregistrer son expérience est une observation perdue pour
toujours.

D'où l'ordre imposé, et qu'il ne faut pas inverser :

    collecter → stocker → requêter → analyser → (un jour) router

Construire un routeur avant d'avoir les données produirait un modèle entraîné
sur rien, avec l'assurance d'un modèle entraîné sur beaucoup.
"""

from __future__ import annotations

from pydantic import Field

from pdz.contracts.base import Contrat
from pdz.contracts.communs import Certitude
from pdz.contracts.diagnosis import ModeEchec
from pdz.contracts.render import Strategie
from pdz.contracts.repair import TypeReparation


class ExperienceRecord(Contrat):
    """Une tentative de fabrication d'un plan, du début à sa conclusion.

    Une LIGNE PAR TENTATIVE, pas par plan : un plan réparé trois fois produit
    trois enregistrements. C'est précisément ce qui permettra de mesurer si
    une réparation marche — agréger par plan effacerait l'information.
    """

    VERSION = "1.0.0"

    # ── Quoi ─────────────────────────────────────────────────────────────
    job_id: str = ""
    shot_id: str = ""
    tentative: int = 1

    # ── Comment ──────────────────────────────────────────────────────────
    strategie: Strategie | None = None
    backend: str = ""
    modele: str = ""
    fournisseur: str = ""
    # Les capacités effectivement exigées par ce rendu — c'est ce qui
    # permettra de dire « cette capacité annoncée n'a jamais tenu ».
    capacites_requises: tuple[str, ...] = ()
    # L'empreinte des entrées : deux tentatives de même signature et de
    # résultats différents révèlent un fournisseur non déterministe, ce
    # qu'aucune moyenne ne montrerait.
    signature_entrees: str = ""
    prompt_ref: str = ""

    # ── Combien ──────────────────────────────────────────────────────────
    cout_estime_eur: float = 0.0
    cout_reel_eur: float = 0.0
    latence_ms: int = 0
    duree_demandee_s: float = 0.0
    duree_livree_s: float = 0.0

    # ── Ce qui était attendu, ce qui a été observé ──────────────────────
    attendu: dict[str, str] = Field(default_factory=dict)
    observe: dict[str, str] = Field(default_factory=dict)

    # ── Conclusion ───────────────────────────────────────────────────────
    diagnostic: ModeEchec | None = None
    reparation: TypeReparation | None = None
    # `REUSSI` | `ECHOUE` | `INCERTAIN` — repris de `Verdict` par sa valeur
    # pour que la table reste lisible sans importer le contrat.
    resultat: str = ""
    # 0..1 quand une sonde sait la produire. À lire AVEC `certitude` : une
    # qualité de 0,9 issue d'un heuristique reste un heuristique.
    qualite: float = 0.0
    certitude: Certitude = Certitude.INCONNU
    verifie_humain: bool = False

    @property
    def exploitable(self) -> bool:
        """Cette ligne peut-elle servir à décider quelque chose ?

        Exige de savoir CE QU'ON A FAIT (stratégie, modèle) et CE QUE ÇA A
        DONNÉ. Une ligne sans conclusion est du bruit, et l'agréger avec les
        autres ferait baisser ou monter des moyennes sans rien signifier.
        """
        return bool(self.strategie and self.modele and self.resultat)

    @property
    def ecart_de_cout(self) -> float:
        """Réel moins estimé. Un écart systématique invalide l'arbitrage
        coût/valeur bien avant qu'il n'invalide le budget."""
        return self.cout_reel_eur - self.cout_estime_eur
