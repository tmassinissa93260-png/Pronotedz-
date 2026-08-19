"""Ce qu'on demande, et ce qu'un backend peut réellement recevoir.

Deux contrats, volontairement distincts :

  · `RenderSpecRequested`  — l'intention de mise en scène
  · `RenderSpecExecutable` — ce qui part chez un backend précis

Une intention n'est JAMAIS envoyée directement à un fournisseur. Entre les
deux il y a la résolution de capacité et le choix de stratégie : c'est là que
« caméra verrouillée » devient soit une phrase dans un prompt, soit un
paramètre, soit un mouvement rendu localement — trois choses très
différentes, dont une seule est garantie.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from pdz.contracts.base import Contrat
from pdz.contracts.communs import StatutCapacite


class Strategie(str, Enum):
    """COMMENT fabriquer le plan — jamais AVEC QUEL moteur.

    Une stratégie n'est pas un modèle : `2.5D` peut être rendu par le
    module local `pdz/video/vie.py` comme par un service tiers, et
    `DIRECT_I2V` par n'importe quel fournisseur image→vidéo. Confondre les
    deux est ce qui a produit la cascade en dur de `animation.py`.
    """

    DIRECT_I2V = "DIRECT_I2V"
    REFERENCE_I2V = "REFERENCE_I2V"
    START_END_FRAME = "START_END_FRAME"
    CONTROLLED_VIDEO = "CONTROLLED_VIDEO"
    V2V_EDIT = "V2V_EDIT"
    MASKED_EDIT = "MASKED_EDIT"
    # Parallaxe et travelling en perspective calculés sur la machine. Le
    # dépôt le fait DÉJÀ (`pdz/video/vie.py`) sans jamais l'avoir nommé.
    DEUX_ET_DEMI_D = "TWO_POINT_FIVE_D"
    TROIS_D = "THREE_D"
    # Ken Burns, fondus, incrustations : garanti, gratuit, local.
    PROCEDURAL = "PROCEDURAL"
    HYBRIDE = "HYBRID"
    # Ne rien animer. Une décision légitime, pas un échec — et il faut
    # pouvoir la distinguer d'une animation qui a raté.
    IMAGE_FIXE = "STILL"


class Faisabilite(str, Enum):
    """Estimation TECHNIQUE, jamais esthétique.

    « Ce plan est difficile à fabriquer » et « ce plan sera moche » sont
    deux jugements sans rapport. Les mélanger dans un score unique est
    l'erreur que ce système refuse.
    """

    HAUTE = "HIGH"
    MOYENNE = "MEDIUM"
    BASSE = "LOW"
    INCONNUE = "UNKNOWN"


class ExigenceCapacite(BaseModel):
    """Une capacité dont ce rendu a besoin, et ce qu'on en sait.

    Un `BaseModel` et non un `Contrat` : ce n'est jamais persisté seul, ça
    voyage à l'intérieur d'un `RenderSpec`. La règle du paquet — un
    `Contrat` est ce qui a une vie et une version propres, tout ce qui est
    imbriqué est un `BaseModel`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    nom: str = ""               # « image_to_video », « first_frame »…
    obligatoire: bool = True
    statut: StatutCapacite = StatutCapacite.INCONNU


class RenderSpecRequested(Contrat):
    """L'intention : ce que ce plan doit devenir."""

    VERSION = "1.0.0"

    shot_id: str = ""
    duree_s: float = 0.0
    image_depart: str = ""
    images_reference: tuple[str, ...] = ()
    # Ce que la mise en scène veut, avant tout arbitrage de faisabilité.
    strategie_souhaitee: Strategie | None = None
    exigences: tuple[ExigenceCapacite, ...] = ()
    faisabilite: Faisabilite = Faisabilite.INCONNUE
    # Ce que ce plan pèse dans le récit (0..1). Alimente l'arbitrage
    # coût/valeur — `animation.noter()` en est déjà la première version.
    importance_narrative: float = 0.0


class RenderSpecExecutable(Contrat):
    """Ce qui part réellement chez un backend, une fois tout résolu.

    `backend` et `modele` sont ici, et NULLE PART en amont : c'est le seul
    contrat de la chaîne autorisé à nommer un fournisseur.
    """

    VERSION = "1.0.0"

    shot_id: str = ""
    strategie: Strategie = Strategie.IMAGE_FIXE
    backend: str = ""
    modele: str = ""
    duree_s: float = 0.0
    prompt: str = ""
    image_depart: str = ""
    images_reference: tuple[str, ...] = ()
    parametres: dict[str, str] = Field(default_factory=dict)
    cout_estime_eur: float = 0.0
    # Ce que le contrat perceptuel attend — recopié ici pour que
    # l'observation puisse comparer sans remonter toute la chaîne.
    attendu: dict[str, str] = Field(default_factory=dict)
