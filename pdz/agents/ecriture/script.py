"""L'agent qui écrit le dialogue de l'épisode.

Il reçoit un univers et une situation, il rend un script plan par plan avec
les répliques, les actions et les émotions.

Toute la logique tient en 25 lignes : le reste (cache, réessais, coût, reprise)
est fourni par le moteur.
"""

from __future__ import annotations

import copy
from typing import Any

from pdz.agents.base import (
    Agent,
    mots_par_replique,
    nb_plans_pour,
    nb_repliques_pour,
    positions_relance_par_defaut,
)
from pdz.analyse.adn import Adn
from pdz.moteur.erreurs import ErreurValidation
from pdz.moteur.pipeline import Contexte
from pdz.univers import Univers


def _texte_empreinte(e) -> str:
    """Rend l'empreinte créative en texte pour le prompt — direction
    créative, jamais une contrainte chiffrée.

    Seuls les champs interprétés avec une confiance non négligeable sont
    rendus : un « unknown » n'a rien à apporter au scénariste, et l'inclure
    donnerait l'illusion d'une information là où il n'y en a pas. Le pacing
    n'apparaît jamais ici — il part par une autre voie (`forme_mesuree`),
    mesurée sur le signal, pas interprétée par le modèle de vision.
    """
    lignes: list[str] = []

    def ajouter(label: str, champ) -> None:
        if champ.valeur and champ.valeur != "unknown" and champ.confiance >= 0.2:
            lignes.append(f"- {label} (confiance {champ.confiance:.0%}) : {champ.valeur}")

    ajouter("Type d'accroche", e.hook.type)
    ajouter("Mécanisme de l'accroche", e.hook.mecanisme)
    ajouter("Promesse posée", e.hook.promesse)
    ajouter("Structure narrative", e.narrative.structure)
    ajouter("Escalade", e.narrative.escalade)
    ajouter("Type de fin", e.narrative.fin)
    ajouter("Mécanisme de curiosité", e.psychologie.curiosite)
    ajouter("Arc émotionnel", e.psychologie.arc_emotionnel)
    ajouter("Mécanisme de rétention", e.psychologie.retention)
    ajouter("Stratégie de cadrage", e.visuel.cadrage)
    ajouter("Rôle de la voix", e.audio.voix)
    ajouter("Rôle de la musique", e.audio.musique)
    ajouter("Rôle du silence", e.audio.silence)

    if e.principes_reutilisables:
        lignes.append("Principes réutilisables :")
        lignes += [f"  · {p}" for p in e.principes_reutilisables]

    return "\n".join(lignes)


class ScriptWriter(Agent):
    nom = "script"
    version = "1.3.0"
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
                "repliques_de_relance": positions_relance_par_defaut(duree, repliques),
                "duree_hook_s": 0,
            }

        empreinte_texte = ""
        if univers.empreinte_creative is not None:
            empreinte_texte = _texte_empreinte(univers.empreinte_creative)

        return {
            **variables,
            "contexte_univers": univers.contexte_script(),
            "situation": entrees["situation"],
            "resume_precedent": entrees.get("resume_precedent", ""),
            "beats": entrees.get("beats") or [],
            "empreinte_texte": empreinte_texte,
        }

    def schema(self, base: dict, entrees: dict[str, Any], ctx: Contexte) -> dict:
        """Adapte le schéma à l'univers de cet épisode.

        Un `enum` vaut mieux qu'une description en texte libre là où la
        valeur compte vraiment : un modèle moins strict répondrait sinon
        avec le nom affiché ou une casse différente. Mais il coûte cher au
        mauvais endroit — Groq valide le schéma côté serveur et **rejette
        toute la réponse** sur une seule valeur hors liste. On ne contraint
        donc que ce qui ne se rattrape pas après coup :

        · `personnage` décide qui parle et quelle voix sort : contraint.
          Et quand l'univers n'a qu'un locuteur — une narration en voix off
          — on ne le demande plus du tout, il n'y a rien à choisir.
        · `decor` et `reaction_de` sont indicatifs : une valeur inconnue
          retombe sur le premier décor sans conséquence. Décrits, pas
          contraints.
        """
        univers: Univers = entrees["univers"]
        ids_personnages = sorted(p.id for p in univers.personnages)
        ids_decors = sorted(d.id for d in univers.decors)

        schema = copy.deepcopy(base)
        items = schema["properties"]["repliques"]["items"]
        proprietes = items["properties"]

        if len(ids_personnages) <= 1:
            proprietes.pop("personnage", None)
            items["required"] = [c for c in items["required"]
                                 if c != "personnage"]
        else:
            proprietes["personnage"]["enum"] = ids_personnages

        proprietes["reaction_de"]["description"] = (
            "identifiant du personnage dont on veut voir la réaction, parmi "
            f"{', '.join(ids_personnages)} — ou chaîne vide"
        )
        if ids_decors:
            proprietes["decor"]["description"] = (
                f"identifiant du décor, parmi {', '.join(ids_decors)} "
                "— ou chaîne vide"
            )
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
        # Un seul locuteur : le champ n'est même pas demandé au modèle (voir
        # `schema`). On le remplit ici, ce qui vaut aussi correction si une
        # version antérieure du schéma l'avait laissé passer de travers.
        if len(connus) == 1:
            seul = next(iter(connus))
            for r in repliques:
                r["personnage"] = seul

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

        estimee = round(mots / debit * 60, 1)

        # La durée était calculée et rangée sans jamais être vérifiée : un
        # script deux fois trop court passait. Mesuré à l'écran — 24 s
        # rendues pour 45 s demandées. La borne est large à dessein : on
        # rejette ce qui se voit, pas ce qui approche. Une erreur de
        # validation relance le modèle en lui montrant son écart.
        if estimee < duree * 0.7:
            manquants = max(1, round((duree * 0.85 - estimee) * debit / 60))
            raise ErreurValidation(
                f"Script trop court : {mots} mots donnent environ {estimee} s "
                f"à voix haute, pour {duree} s demandées. Ajoute environ "
                f"{manquants} mots — en allongeant les répliques existantes "
                "ou en en ajoutant, sans changer l'histoire."
            )
        if estimee > duree * 1.4:
            raise ErreurValidation(
                f"Script trop long : {mots} mots donnent environ {estimee} s "
                f"à voix haute, pour {duree} s demandées. Resserre les "
                "répliques : la vidéo serait coupée avant la fin."
            )

        sortie["duree_cible_s"] = duree
        sortie["nb_repliques"] = len(repliques)
        sortie["mots_total"] = mots
        sortie["duree_parlee_estimee_s"] = estimee
        return sortie
