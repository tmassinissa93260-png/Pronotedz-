"""Le vocabulaire partagé par tous les contrats.

Ces énumérations ne décrivent pas des données, elles décrivent **ce qu'on
sait** des données. Elles sont ici, et pas dans chaque contrat, parce qu'un
système qui distingue « mesuré » de « annoncé » à trois endroits différents
finit par les confondre au quatrième.

Le dépôt appliquait déjà cette discipline de façon dispersée :
`ChampInterprete(valeur, confiance)` dans `univers/modele.py`, `UNCERTAIN`
dans l'agent `qa_image`, `a_verifier: true` dans `modeles.yaml`,
`ControleCamera.TEXTE_SEULEMENT` dans `motion_program.py`. Ce module en fait
une règle unique plutôt qu'une culture.
"""

from __future__ import annotations

from enum import Enum


class Certitude(str, Enum):
    """Ce que vaut une information, jamais l'information elle-même.

    L'interdit central, qui vaut pour tout le système : **une valeur ne
    remonte jamais d'un cran toute seule.** Un `HEURISTIQUE` ne devient pas
    un `FAIT` parce qu'un modèle l'a répété avec assurance, et un `INCONNU`
    ne devient jamais `FAUX` — ne pas savoir n'est pas savoir que non.
    """

    FAIT = "FACT"                     # sourcé, vérifiable, non contredit
    HEURISTIQUE = "HEURISTIC"         # plausible, non vérifié
    INCONNU = "UNKNOWN"               # on ne sait pas, et on le dit
    VERIFIE_HUMAIN = "HUMAN_VERIFIED" # un humain a tranché

    @property
    def est_fiable(self) -> bool:
        return self in (Certitude.FAIT, Certitude.VERIFIE_HUMAIN)


class StatutCapacite(str, Enum):
    """D'où vient ce qu'on croit savoir d'un fournisseur.

    `ANNONCE` est ce que dit sa documentation. `MESURE` est ce qu'on a
    constaté soi-même, sur une vraie requête, à une vraie date.

    **Les deux ne sont jamais interchangeables.** Une documentation n'est
    pas une mesure : le dépôt a déjà connu deux modèles retirés en 2026
    (`llama-3.3-70b-versatile`, `llama-4-maverick`) dont les capacités
    annoncées étaient parfaitement exactes jusqu'au jour où le modèle a
    cessé de répondre.
    """

    ANNONCE = "ANNOUNCED"
    MESURE = "MEASURED"
    INCONNU = "UNKNOWN"

    @property
    def est_garanti(self) -> bool:
        """Seule une mesure engage. Une annonce est une intention du
        fournisseur, pas une propriété du système."""
        return self is StatutCapacite.MESURE


class Verdict(str, Enum):
    """Le résultat d'une vérification — trois valeurs, jamais deux.

    `INCERTAIN` n'est pas un échec de la QA : c'est son honnêteté. Une sonde
    qui n'a pas pu conclure doit le dire, sinon le système apprend à traiter
    « pas mesuré » comme « bon », ce qui est exactement l'erreur qui laisse
    passer un clip statique à la bonne durée.
    """

    REUSSI = "PASS"
    ECHOUE = "FAIL"
    INCERTAIN = "UNCERTAIN"

    @property
    def bloque(self) -> bool:
        """Seul un échec avéré bloque. Un incertain remonte à l'humain."""
        return self is Verdict.ECHOUE


class Severite(str, Enum):
    """À quel point un diagnostic doit interrompre la production."""

    CRITIQUE = "critical"   # le plan ne montre pas ce pour quoi il existe
    MAJEURE = "major"       # visible du spectateur, réparable
    MINEURE = "minor"       # écart mesurable, sans conséquence perçue
    INFO = "info"           # constat, aucune action attendue


class Profil(str, Enum):
    """Les deux familles de production, décidées dans docs/GAP_ANALYSIS.md § 1.

    Elles divergent **avant** le compilateur et convergent sur le même
    `DirectorState` : un `Claim` sourcé n'a aucun sens pour « Strawberina
    trahit Bananito », et un `Personnage` n'en a aucun pour « comment
    fonctionne un moteur électrique ». Forcer l'un dans le moule de l'autre
    produirait une abstraction vide sur la moitié des productions.
    """

    EXPLICATIF = "explanatory"
    FICTION = "fictional"
