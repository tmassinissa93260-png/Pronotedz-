"""Les mémoires du compilateur.

Quatre mémoires, volontairement séparées — les mélanger produirait un
« contexte » fourre-tout qu'on finirait par envoyer en entier à chaque appel,
exactement ce que l'architecture interdit :

  · **sémantique**  — ce que raconte la vidéo (`DirectorState`, script)
  · **monde**       — l'état des entités (`WorldState`)
  · **visuelle**    — frames, références, ancres (table `artefacts`)
  · **expérience**  — ce qu'une fabrication a coûté, produit et raté

Seule la quatrième est implémentée ici : les trois premières existent déjà,
dispersées mais réelles (`etapes`, `artefacts`, `univers/*.yaml`). Les
rassembler prématurément déplacerait du code sans rien débloquer, alors que
l'expérience, elle, n'est collectée NULLE PART.
"""

from pdz.memory.experience import (
    ExperienceMemory,
    performance_par_modele,
    performance_par_strategie,
)

__all__ = ["ExperienceMemory", "performance_par_strategie", "performance_par_modele"]
