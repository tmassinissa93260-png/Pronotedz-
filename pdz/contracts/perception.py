"""Ce que le spectateur doit PERCEVOIR — le contrat que la QA vérifie.

Le dépôt en possède déjà les deux moitiés, séparées : `ContratVisuel`
répond aux « 8 questions » (qui, quoi, où, dans quel registre) et
`MotionProgram.cible_perceptuelle` porte une vraie cible
(`viewer_must_perceive_subject_motion`), déjà recoupée en aval par la
vérification de mouvement.

Ce qui manquait, et qui est ici : l'ORDRE d'attention, et les confusions à
éviter. Sans elles, « le plan montre-t-il l'accélération ? » n'a pas de
réponse vérifiable — un travelling avant sur un avion immobile satisfait
« quelque chose bouge » tout en ratant complètement l'intention.
"""

from __future__ import annotations

from pydantic import ConfigDict

from pdz.contracts.base import Contrat


class PerceptualContract(Contrat):
    VERSION = "1.0.0"

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    shot_id: str = ""
    # LA chose que ce plan existe pour faire percevoir. Une seule — un plan
    # avec deux objectifs principaux n'en a aucun.
    objectif_principal: str = ""
    # Dans l'ordre : ce que l'œil doit trouver en premier, puis ensuite.
    # L'ordre EST l'information ; un ensemble non ordonné ne dirait rien.
    attention: tuple[str, ...] = ()
    doit_percevoir: tuple[str, ...] = ()
    # Les lectures ERRONÉES que le plan risque de produire. C'est ce qui
    # transforme un diagnostic vague (« mouvement faible ») en diagnostic
    # actionnable (`CAMERA_DOMINANT` : ça bouge, mais c'est la caméra).
    ne_doit_pas_etre_confondu_avec: tuple[str, ...] = ()

    @property
    def est_verifiable(self) -> bool:
        """Un contrat perceptuel sans `doit_percevoir` ne peut rien réfuter.

        Il serait satisfait par n'importe quelle image — donc inutile comme
        contrat. Mieux vaut le savoir avant de dépenser un rendu.
        """
        return bool(self.objectif_principal and self.doit_percevoir)
