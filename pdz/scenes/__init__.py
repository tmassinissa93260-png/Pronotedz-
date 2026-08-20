"""Un plan, compilé en tous ses contrats — en un seul appel.

Les contrats et leurs adaptateurs existent depuis la PHASE 2 ; ce paquet est
ce qui les **branche**. Sans lui, chaque appelant devrait savoir dans quel
ordre appeler cinq fonctions et lesquelles dépendent des autres — c'est-à-dire
reconstruire ce compilateur à chaque fois, un peu différemment.

    PlanScript + Univers
            ↓
    ShotSpec · PerceptualContract · MotionProgram · CameraProgram · WorldState

**Zéro appel IA.** Tout vient de décisions déjà prises : `ShotPromptWriter`
a écrit les champs `mouvement_*`, `geometrie`, `elements_*` dans le seul
appel de l'épisode ; l'univers porte le style et les interdits. Redemander à
un modèle ce que ces structures portent déjà serait payer pour dégrader une
information qu'on avait exacte.
"""

from pdz.scenes.compilation import PlanCompile, compiler_plan, compiler_plans

__all__ = ["PlanCompile", "compiler_plan", "compiler_plans"]
