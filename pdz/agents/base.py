"""Le socle commun à tous les agents.

Un agent ne s'occupe QUE de sa logique propre. Le moteur lui fournit
gratuitement : le cache, les réessais, le suivi du coût, le point de reprise
et le garde-fou de budget.

Écrire un agent = ~30 lignes. Voir docs/05-les-agents.md.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from pdz.ia import texte
from pdz.moteur.pipeline import Contexte
from pdz.prompts import registre as prompts


class Agent:
    """Classe de base. Un agent qui appelle Claude n'a qu'à définir
    `nom`, `prompt_ref`, et la méthode `variables()`."""

    nom: str = "agent"
    version: str = "1.0.0"
    prompt_ref: str = ""          # « ecriture/script » ou « ecriture/script@1.0.0 »

    def signature(self) -> dict[str, str]:
        """Ce qui identifie l'agent dans l'empreinte de cache.

        Changer de version d'agent, de prompt ou de modèle invalide
        automatiquement le cache — sans purge manuelle.
        """
        sig = {"agent": self.nom, "version": self.version}
        if self.prompt_ref:
            p = prompts.charger(self.prompt_ref)
            sig["prompt"] = p.ref
            sig["alias"] = p.alias_modele
        return sig

    # ── À implémenter par chaque agent ───────────────────────────────────

    def variables(self, entrees: dict[str, Any], ctx: Contexte) -> dict[str, Any]:
        """Les variables à injecter dans le prompt."""
        raise NotImplementedError

    def images(self, entrees: dict[str, Any], ctx: Contexte) -> list[Path] | None:
        """Les images à faire regarder au modèle. Par défaut, aucune.

        Utilisé par les agents de vision (analyse d'un style visuel, contrôle
        qualité d'une image produite). Elles entrent dans l'empreinte de cache
        par leur contenu, pas par leur chemin — voir `signature_images()`.
        """
        return None

    def apres(self, sortie: dict, entrees: dict, ctx: Contexte) -> dict:
        """Retouche ou vérification de la sortie. Par défaut, rien."""
        return sortie

    def schema(self, base: dict, entrees: dict[str, Any], ctx: Contexte) -> dict:
        """Le schéma de sortie, éventuellement resserré pour cette exécution.

        Par défaut, celui du prompt tel quel. Un agent qui connaît, au moment
        de l'appel, l'ensemble exact des valeurs valides pour un champ (les
        identifiants d'un univers, par exemple) peut le transformer en `enum`
        ici — ça guide le modèle bien mieux qu'une description en texte
        libre, surtout un modèle moins strict sur les instructions."""
        return base

    # ── Exécution ────────────────────────────────────────────────────────

    async def executer(self, entrees: dict[str, Any], ctx: Contexte) -> dict:
        prompt = prompts.charger(self.prompt_ref)
        stable, variable, message = prompt.rendre(**self.variables(entrees, ctx))
        images = self.images(entrees, ctx)

        budget_pct = 100.0
        if ctx.budget_restant > 0:
            budget_pct = min(100.0, ctx.budget_restant * 100.0)

        reponse = await texte.appeler(
            alias=prompt.alias_modele,
            systeme_stable=stable,
            systeme_variable=variable,
            message=message,
            schema_sortie=self.schema(prompt.schema_sortie, entrees, ctx),
            images=images,
            nom_outil=self.nom,
            max_tokens=prompt.max_tokens,
            temperature=prompt.temperature,
            profil=ctx.profil,
            budget_restant_pct=budget_pct,
            job_id=ctx.job_id,
            etape=ctx.etape_cle,
            agent=self.nom,
            prompt_ref=prompt.ref,
        )
        ctx.facturer(reponse.cout)
        return self.apres(reponse.donnees, entrees, ctx)


def signature_images(chemins: list[Path] | None) -> str:
    """Empreinte du **contenu** d'une liste d'images.

    Les chemins ne conviennent pas : deux jobs extraient les mêmes images-clés
    d'une même vidéo dans deux dossiers de travail différents. Par le contenu,
    la seconde analyse est gratuite ; par le chemin, elle serait repayée.
    """
    if not chemins:
        return ""
    h = hashlib.sha256()
    for chemin in chemins:
        h.update(hashlib.sha256(Path(chemin).read_bytes()).digest())
    return h.hexdigest()[:24]


# ── Réplique ≠ plan : deux choses différentes, souvent confondues ────────
#
#   RÉPLIQUE : une prise de parole. ~3,5 s, ~9 mots. C'est du DIALOGUE.
#   PLAN     : un changement visuel. ~1,75 s. C'est du MONTAGE.
#
# Une réplique occupe 2 plans en moyenne : celui qui parle, puis la réaction
# de l'autre. C'est le b-a-ba du montage dialogué, et c'est ce qui permet de
# tenir le rythme visuel de 2026 sans écrire des répliques de 5 mots.
#
# Le Script Writer produit des répliques. Le Storyboard les découpe en plans.


def nb_repliques_pour(duree_s: float, secondes_par_replique: float = 3.5) -> int:
    """Combien de prises de parole tiennent dans la durée visée."""
    return max(3, round(duree_s / secondes_par_replique))


def mots_par_replique(duree_s: float, nb_repliques: int,
                      debit_wpm: int = 160) -> list[int]:
    """Combien de mots par réplique pour tenir sa durée.

    Remplace la règle arbitraire « 18 mots par partie » : le nombre de mots
    découle de la durée et du débit de parole mesurés, pas d'une convention.
    """
    if nb_repliques <= 0:
        return []
    duree = duree_s / nb_repliques
    return [max(4, round(duree * debit_wpm / 60)) for _ in range(nb_repliques)]


def nb_plans_pour(duree_s: float, secondes_par_plan: float = 1.75) -> int:
    """Combien de changements visuels — repère 2026 : un toutes les 1,5 à 2 s.

    En dessous de 1,2 s, le cerveau traite le montage comme du bruit.
    Voir docs/11-etat-de-lart.md.
    """
    return max(4, round(duree_s / secondes_par_plan))
