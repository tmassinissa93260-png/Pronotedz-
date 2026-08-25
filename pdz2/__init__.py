"""PDZ 2 — compilateur audiovisuel.

Reconstruction complète, indépendante de l'ancien système PDZ. Rien n'est
importé de `pdz/` : les deux paquets coexistent sans se connaître.

Règle architecturale absolue (voir `pdz2/architecture/`) :

    NARRATIVE INTENT  ->  RENDER SPECIFICATION  ->  EXECUTION

Ces trois couches ne se mélangent jamais.
"""

__all__ = ["__version__"]

# Version du paquet. Distincte des versions de contrats, qui sont déclarées
# contrat par contrat (voir `pdz2.contracts.versioning`).
__version__ = "0.1.0"
