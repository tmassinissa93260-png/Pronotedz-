"""Pourquoi un rendu a raté — l'écart entre ce qui était attendu et ce qui est.

Un diagnostic n'est pas un échec constaté : c'est une HYPOTHÈSE de cause,
avec sa confiance et ses preuves. La distinction est ce qui sépare une
réparation ciblée d'une relance à l'aveugle : « ça ne bouge pas assez » ne dit
pas quoi changer, `CAMERA_DOMINANT` si.

Le dépôt en possède déjà l'embryon : `PlanAnime.diagnostic` distingue
`mouvement_confirme`, `rejete_duree`, `rejete_mouvement`, `timeout`,
`erreur_appel`, `hors_portee`, `non_elu`. C'est la même idée, étendue aux
modes d'échec visuels que rien ne nommait.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict

from pdz.contracts.base import Contrat
from pdz.contracts.communs import Severite


class ModeEchec(str, Enum):
    """La taxonomie. `INCONNU` en fait partie, et ce n'est pas un aveu :
    un échec qu'on ne sait pas nommer doit se compter comme tel, sinon il
    se range dans la catégorie voisine et fausse toutes les statistiques."""

    # ── Mouvement ────────────────────────────────────────────────────────
    RENDU_STATIQUE = "STATIC_RENDER"
    MOUVEMENT_FAIBLE = "WEAK_MOTION"
    MOUVEMENT_EXCESSIF = "EXCESSIVE_MOTION"
    CAMERA_DOMINANTE = "CAMERA_DOMINANT"
    MOUVEMENT_SUJET_ABSENT = "SUBJECT_MOTION_MISSING"
    EVENEMENT_PRINCIPAL_ABSENT = "PRIMARY_EVENT_MISSING"
    # ── Géométrie et identité ────────────────────────────────────────────
    DEFORMATION_CORPS_RIGIDE = "RIGID_BODY_DEFORMATION"
    ECHEC_NON_RIGIDE = "NON_RIGID_FAILURE"
    DERIVE_IDENTITE = "IDENTITY_DRIFT"
    DERIVE_GEOMETRIE = "GEOMETRY_DRIFT"
    DERIVE_COULEUR = "COLOR_DRIFT"
    # ── Temporel ─────────────────────────────────────────────────────────
    SCINTILLEMENT = "FLICKER"
    COUPE_INATTENDUE = "UNEXPECTED_CUT"
    DUREE_INCORRECTE = "DURATION_FAILURE"
    # ── Audio ────────────────────────────────────────────────────────────
    DESYNC_AUDIO = "AUDIO_DESYNC"
    DESYNC_SOUSTITRES = "SUBTITLE_DESYNC"
    # ── Chaîne ───────────────────────────────────────────────────────────
    RUPTURE_CONTINUITE = "CONTINUITY_FAILURE"
    CAPACITE_ABSENTE = "CAPABILITY_FAILURE"
    INCONNU = "UNKNOWN"


class Ecart(BaseModel):
    """Attendu vs observé, sur une dimension précise. La preuve du diagnostic."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dimension: str              # « mouvement_sujet », « identite »…
    attendu: str = ""
    observe: str = ""


class FailureDiagnosis(Contrat):
    """Une hypothèse de cause, ses preuves, et ce qu'on pourrait tenter."""

    VERSION = "1.0.0"

    shot_id: str = ""
    mode: ModeEchec = ModeEchec.INCONNU
    severite: Severite = Severite.INFO
    # 0..1 — à quel point on croit à CETTE cause. Un diagnostic peu confiant
    # reste utile : il oriente une réparation prudente au lieu d'en imposer
    # une coûteuse. Le taire reviendrait à traiter une hypothèse comme un fait.
    confiance: float = 0.0
    ecarts: tuple[Ecart, ...] = ()
    # Les noms des mesures qui l'appuient — le lien vers l'ObservationReport.
    preuves: tuple[str, ...] = ()
    # Les réparations envisageables, par ordre de préférence. Le diagnostic
    # PROPOSE ; c'est le compilateur de réparation qui arbitre coût et risque.
    reparations_possibles: tuple[str, ...] = ()
    explication: str = ""

    @property
    def actionnable(self) -> bool:
        """Assez sûr et assez grave pour justifier de dépenser à nouveau.

        Le seuil de 0,5 est un choix explicite, pas une mesure : en dessous,
        l'hypothèse est plus proche du pile ou face que du diagnostic, et
        réparer sur cette base coûterait plus que d'accepter le plan.
        """
        return (self.confiance >= 0.5
                and self.severite in (Severite.CRITIQUE, Severite.MAJEURE)
                and bool(self.reparations_possibles))
