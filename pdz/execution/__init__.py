"""Exécuter un DAG de nœuds — en parallèle quand c'est possible.

`ExecutionPlan.ordonnancer()` (PHASE 2) sait déjà répartir les nœuds en
vagues parallélisables. Ce paquet les exécute.

── Ce qu'un DAG apporte, et ce qu'il ne doit PAS coûter ─────────────────

Un plan en 2.5D a besoin d'une image, puis d'une carte de profondeur, puis
d'un rendu de caméra. Ces dépendances existent qu'on les écrive ou non ; les
écrire permet de paralléliser (profondeur et masque partent ensemble), de
reprendre nœud par nœud, et de mettre chacun en cache séparément.

**Un plan simple reste un seul nœud.** Forcer tous les plans à ressembler à
un graphe complexe n'apporterait rien, et le code le dit plutôt que de le
sous-entendre.

── Une seule autorité pour le cache et la reprise ───────────────────────

L'ordonnanceur n'invente ni cache ni journal : il appelle
`pdz/moteur/journal.py`, comme le moteur et la production. Un troisième
mécanisme de reprise serait précisément ce que la PHASE 5 a supprimé.
"""

from pdz.execution.ordonnanceur import Ordonnanceur, ResultatExecution, executer

__all__ = ["Ordonnanceur", "ResultatExecution", "executer"]
