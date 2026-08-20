"""ATTENDU vs OBSERVÉ — l'écart, et ce qu'il permet de conclure.

Un diagnostic n'est pas un échec constaté : c'est une **hypothèse de cause**,
avec sa confiance et ses preuves. La distinction sépare une réparation ciblée
d'une relance à l'aveugle — « ça ne bouge pas assez » ne dit pas quoi
changer, `CAMERA_DOMINANT` si.

    MotionProgram + CameraProgram + PerceptualContract   ← ce qui était voulu
                        ↓
                ObservationReport                        ← ce qui est
                        ↓
                    DELTA
                        ↓
                FailureDiagnosis                         ← pourquoi

Le dépôt en avait l'embryon : `PlanAnime.diagnostic` distingue déjà
`mouvement_confirme`, `rejete_duree`, `rejete_mouvement`, `timeout`,
`erreur_appel`, `hors_portee`, `non_elu`. C'est la même idée, étendue aux
modes d'échec visuels que rien ne nommait.
"""

from pdz.diagnostics.ecarts import Attendu, diagnostiquer, ecarts

__all__ = ["Attendu", "diagnostiquer", "ecarts"]
