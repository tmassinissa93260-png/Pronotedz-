"""L'agent qui écrit le dialogue de l'épisode.

Il reçoit un univers et une situation, il rend un script plan par plan avec
les répliques, les actions et les émotions.

Toute la logique tient en 25 lignes : le reste (cache, réessais, coût, reprise)
est fourni par le moteur.
"""

from __future__ import annotations

from typing import Any

from pdz.agents.base import Agent, mots_par_replique, nb_plans_pour, nb_repliques_pour
from pdz.moteur.erreurs import ErreurValidation
from pdz.moteur.pipeline import Contexte
from pdz.univers import Univers


class ScriptWriter(Agent):
    nom = "script"
    version = "1.0.0"
    prompt_ref = "ecriture/script"

    def variables(self, entrees: dict[str, Any], ctx: Contexte) -> dict[str, Any]:
        univers: Univers = entrees["univers"]
        duree = entrees.get("duree_s") or univers.duree_cible_s
        repliques = nb_repliques_pour(duree)

        return {
            "contexte_univers": univers.contexte_script(),
            "situation": entrees["situation"],
            "duree_s": duree,
            "nb_repliques": repliques,
            "mots_par_replique": mots_par_replique(duree, repliques),
            # Indicatif pour le scénariste : le Storyboard fera le découpage réel.
            "nb_plans_vises": nb_plans_pour(duree),
            "resume_precedent": entrees.get("resume_precedent", ""),
        }

    def apres(self, sortie: dict, entrees: dict, ctx: Contexte) -> dict:
        """Vérifications que le schéma JSON ne peut pas faire.

        Une erreur levée ici est de catégorie « validation » : le moteur relance
        automatiquement en montrant l'erreur au modèle, ce qui passe environ
        8 fois sur 10 au deuxième essai.
        """
        univers: Univers = entrees["univers"]
        repliques = sortie.get("repliques", [])
        if not repliques:
            raise ErreurValidation("Script vide : aucune réplique produite.")

        connus = {p.id for p in univers.personnages}
        for r in repliques:
            if r["personnage"] not in connus:
                raise ErreurValidation(
                    f"Réplique {r['numero']} : personnage « {r['personnage']} » "
                    f"inconnu de l'univers. Attendus : {', '.join(sorted(connus))}."
                )

        if not any(r.get("relance") for r in repliques[1:]):
            raise ErreurValidation(
                "Aucune relance narrative. Il en faut une toutes les 15 à 20 s, "
                "sinon la vidéo s'affaisse au milieu."
            )

        duree = entrees.get("duree_s") or univers.duree_cible_s
        mots = sum(len(r["replique"].split()) for r in repliques)
        sortie["duree_cible_s"] = duree
        sortie["nb_repliques"] = len(repliques)
        sortie["mots_total"] = mots
        # 160 mots/minute : la durée réellement parlée, à comparer à la cible.
        sortie["duree_parlee_estimee_s"] = round(mots / 160 * 60, 1)
        return sortie
