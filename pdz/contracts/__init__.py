"""Les contrats : la source de vérité du compilateur.

Un contrat est un état typé, versionné, sérialisable et INDÉPENDANT de tout
fournisseur. Les prompts en sont des projections temporaires ; si une
information n'existe que dans un prompt, elle n'existe pas.

── Deux règles, vérifiées par `tests/test_architecture.py` ──────────────

1. **Ce paquet n'importe rien d'autre de `pdz`.** Un contrat qui dépendrait
   d'un module de production ne serait plus une source de vérité, seulement
   une vue sur du code.
2. **Un `Contrat` est ce qui a une vie et une version propres.** Tout ce qui
   ne vit qu'imbriqué dans un autre est un `BaseModel` — `Mot`, `Claim`,
   `Mesure`, `Branche`, `NoeudExecution`…

── La chaîne ────────────────────────────────────────────────────────────

    TopicRequest
      ├── ResearchState   (profil explicatif)
      └── NarrativeState  (profil fiction)
              ↓
        DirectorState              ← les deux profils convergent ICI
              ↓
    WorldState · CausalState
              ↓
        AudioTimeline              ← la chronologie officielle
              ↓
        ShotGraph → ShotSpec
              ↓
    PerceptualContract · MotionProgram · CameraProgram
              ↓
    RenderSpecRequested → RenderSpecExecutable
              ↓
        ExecutionPlan
              ↓
      ObservationReport
              ↓
      FailureDiagnosis → RepairPlan
              ↓
       ExperienceRecord
"""

from pdz.contracts.audio import AudioTimeline, EvenementAudio, Mot, Replique
from pdz.contracts.base import (
    Contrat,
    ErreurContrat,
    Provenance,
    enregistrer_migration,
    versions,
)
from pdz.contracts.camera import CameraProgram, ControleCamera, MouvementCamera
from pdz.contracts.capabilities import CapabilityGraph, Capacite, ModeleCapacites
from pdz.contracts.causality import CausalState, Maillon
from pdz.contracts.communs import Certitude, Profil, Severite, StatutCapacite, Verdict
from pdz.contracts.diagnosis import Ecart, FailureDiagnosis, ModeEchec
from pdz.contracts.director import (
    Continuite,
    ContraintesProduction,
    DirectorState,
    EtatEmotionnel,
    EtatSpectateur,
    LangageVisuel,
    NarrativeIntention,
)
from pdz.contracts.execution import ExecutionPlan, NoeudExecution, StatutNoeud
from pdz.contracts.experience import ExperienceRecord
from pdz.contracts.motion import MotionProgram, NatureMouvement, Trajectoire
from pdz.contracts.narrative import Evenement, NarrativeState
from pdz.contracts.narrative import Personnage as PersonnageNarratif
from pdz.contracts.observation import Axe, Mesure, ObservationReport
from pdz.contracts.perception import PerceptualContract
from pdz.contracts.render import (
    ExigenceCapacite,
    Faisabilite,
    RenderSpecExecutable,
    RenderSpecRequested,
    Strategie,
)
from pdz.contracts.repair import Branche, RepairPlan, TypeReparation
from pdz.contracts.research import Claim, ResearchState, Source
from pdz.contracts.shot import Critere, ShotGraph, ShotSpec
from pdz.contracts.topic import TopicRequest
from pdz.contracts.world import Entite, Etat, Position, Relation, WorldState

__all__ = [
    # socle
    "Contrat", "ErreurContrat", "Provenance", "enregistrer_migration", "versions",
    # vocabulaire
    "Certitude", "StatutCapacite", "Verdict", "Severite", "Profil",
    # intention et savoir
    "TopicRequest", "ResearchState", "Claim", "Source",
    "NarrativeState", "PersonnageNarratif", "Evenement",
    # mise en scène
    "DirectorState", "NarrativeIntention", "EtatSpectateur", "EtatEmotionnel",
    "LangageVisuel", "Continuite", "ContraintesProduction",
    # monde
    "WorldState", "Entite", "Etat", "Position", "Relation",
    "CausalState", "Maillon",
    # temps
    "AudioTimeline", "Replique", "Mot", "EvenementAudio",
    # plans
    "ShotGraph", "ShotSpec", "Critere", "PerceptualContract",
    "MotionProgram", "Trajectoire", "NatureMouvement",
    "CameraProgram", "MouvementCamera", "ControleCamera",
    # fabrication
    "RenderSpecRequested", "RenderSpecExecutable", "Strategie", "Faisabilite",
    "ExigenceCapacite",
    "CapabilityGraph", "ModeleCapacites", "Capacite",
    "ExecutionPlan", "NoeudExecution", "StatutNoeud",
    # retour
    "ObservationReport", "Mesure", "Axe",
    "FailureDiagnosis", "ModeEchec", "Ecart",
    "RepairPlan", "Branche", "TypeReparation",
    "ExperienceRecord",
]
