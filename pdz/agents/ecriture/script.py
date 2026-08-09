"""L'agent qui écrit le dialogue de l'épisode.

Il reçoit un univers et une situation, il rend un script plan par plan avec
les répliques, les actions et les émotions.

Toute la logique tient en 25 lignes : le reste (cache, réessais, coût, reprise)
est fourni par le moteur.
"""

from __future__ import annotations

import copy
from typing import Any

from pdz.agents.base import Agent, mots_par_replique, nb_plans_pour, nb_repliques_pour
from pdz.analyse.adn import Adn
from pdz.moteur.erreurs import ErreurValidation
from pdz.moteur.pipeline import Contexte
from pdz.univers import Univers


class ScriptWriter(Agent):
    nom = "script"
    version = "1.1.0"
    prompt_ref = "ecriture/script"

    def variables(self, entrees: dict[str, Any], ctx: Contexte) -> dict[str, Any]:
        univers: Univers = entrees["univers"]
        duree = entrees.get("duree_s") or univers.duree_cible_s

        # Avec un ADN mesuré sur une vidéo de référence, le format vient des
        # mesures. Sans lui, des repères génériques. Les deux chemins donnent
        # les mêmes clés au prompt — il n'a pas à savoir d'où elles viennent.
        adn: Adn | None = entrees.get("adn")
        if adn is not None:
            forme = adn.contraintes(duree)
            variables = {
                "duree_s": forme["duree_s"],
                "nb_repliques": forme["nb_repliques"],
                "mots_par_replique": forme["mots_par_replique"],
                "nb_plans_vises": forme["nb_plans_vises"],
                "forme_mesuree": adn.bloc_pour_prompt(),
                "repliques_de_relance": forme["repliques_de_relance"],
                "duree_hook_s": forme["duree_hook_s"],
            }
        else:
            repliques = nb_repliques_pour(duree)
            variables = {
                "duree_s": duree,
                "nb_repliques": repliques,
                "mots_par_replique": mots_par_replique(duree, repliques),
                # Indicatif : le Storyboard fera le découpage réel.
                "nb_plans_vises": nb_plans_pour(duree),
                "forme_mesuree": "",
                "repliques_de_relance": [],
                "duree_hook_s": 0,
            }

        return {
            **variables,
            "contexte_univers": univers.contexte_script(),
            "situation": entrees["situation"],
            "resume_precedent": entrees.get("resume_precedent", ""),
            "beats": entrees.get("beats") or [],
        }

    def schema(self, base: dict, entrees: dict[str, Any], ctx: Contexte) -> dict:
        """Ferme les identifiants de personnage/décor à ceux de l'univers.

        Une description en texte libre (« identifiant du personnage qui
        parle ») laisse un modèle moins strict — Llama via le profil gratuit,
        mesuré en conditions réelles — répondre avec le nom affiché, une
        casse différente, ou rien du tout. Un `enum` dans le schéma élimine
        le problème à la source plutôt que de compter sur la relecture.
        """
        univers: Univers = entrees["univers"]
        ids_personnages = sorted(p.id for p in univers.personnages)
        ids_decors = sorted(d.id for d in univers.decors)

        schema = copy.deepcopy(base)
        proprietes = schema["properties"]["repliques"]["items"]["properties"]
        proprietes["personnage"]["enum"] = ids_personnages
        proprietes["reaction_de"]["enum"] = [*ids_personnages, ""]
        if ids_decors:
            proprietes["decor"]["enum"] = [*ids_decors, ""]
        return schema

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
        # Le modèle échoue parfois à respecter la casse de l'identifiant même
        # quand elle lui est montrée explicitement (mesuré avec Llama/Groq,
        # qui renvoie « Strawberina » au lieu de « strawberina ») : on
        # rapproche par casse plutôt que de faire échouer tout l'épisode.
        connus_ci = {id_.lower(): id_ for id_ in connus}
        decors_ci = {d.id.lower(): d.id for d in univers.decors}
        for r in repliques:
            cle = r["personnage"].strip().lower()
            if cle not in connus_ci:
                raise ErreurValidation(
                    f"Réplique {r['numero']} : personnage « {r['personnage']} » "
                    f"inconnu de l'univers. Attendus : {', '.join(sorted(connus))}."
                )
            r["personnage"] = connus_ci[cle]
            if r.get("reaction_de"):
                cle_r = r["reaction_de"].strip().lower()
                if cle_r in connus_ci:
                    r["reaction_de"] = connus_ci[cle_r]
            if r.get("decor"):
                cle_d = r["decor"].strip().lower()
                if cle_d in decors_ci:
                    r["decor"] = decors_ci[cle_d]

        if not any(r.get("relance") for r in repliques[1:]):
            raise ErreurValidation(
                "Aucune relance narrative. Il en faut une toutes les 15 à 20 s, "
                "sinon la vidéo s'affaisse au milieu."
            )

        duree = entrees.get("duree_s") or univers.duree_cible_s
        mots = sum(len(r["replique"].split()) for r in repliques)
        adn: Adn | None = entrees.get("adn")
        # Le débit mesuré sur la référence s'il existe, sinon 160 mots/minute.
        debit = adn.debit_wpm if adn is not None else 160

        sortie["duree_cible_s"] = duree
        sortie["nb_repliques"] = len(repliques)
        sortie["mots_total"] = mots
        sortie["duree_parlee_estimee_s"] = round(mots / debit * 60, 1)
        return sortie
