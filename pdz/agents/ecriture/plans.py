"""L'agent qui transforme le storyboard déjà découpé en prompts d'image riches.

ScriptWriter écrit le dialogue et une action minimale par réplique — de quoi
savoir ce qui se passe, pas de quoi cadrer une image. Le découpage
(`pdz.production.storyboard`) transforme ensuite ces répliques en PLANS : une
réplique avec réaction en donne deux (celui qui parle, puis celui qui
écoute), et ce second plan n'a jamais reçu qu'une action générique codée en
dur (« reacting to what X just said »).

Cet agent prend le relais UNE FOIS le découpage fait, pas avant : à partir de
ce qui se dit et de la fonction de chaque plan (SHOT_FUNCTION), il écrit un
vrai prompt de cinéaste — cadrage, ce qui est net, ce qui reste dans l'ombre
— un par PLAN, réaction comprise. C'est ce prompt qui remplace `action` avant
la génération d'image.

Le séparer de l'écriture du dialogue n'est pas cosmétique : un modèle qui
répartit son attention entre « qu'est-ce qu'on dit » et « comment on le
filme » en même temps écrit les deux moins bien qu'un modèle qui ne
s'occupe QUE du cadrage, une fois le texte ET le montage déjà là.
"""

from __future__ import annotations

import copy
import logging
import re
from dataclasses import replace
from typing import Any

from pdz.agents.base import Agent
from pdz.moteur.erreurs import ErreurValidation
from pdz.moteur.pipeline import Contexte
from pdz.production import cadrage, fidelite_visuelle
from pdz.production import geometrie as geometrie_mod
from pdz.production.continuite import indices_de_scene
from pdz.production.storyboard import PlanScript
from pdz.univers import Univers

log = logging.getLogger(__name__)

# Les champs que ce contrat sait perdre — tout ce qui ENRICHIT le prompt sans
# être nécessaire pour fabriquer une image. Les six champs requis
# (`prompt_image`, `cadrage`, `registre_visuel`, `elements_obligatoires`,
# `elements_a_exclure`, `numero`) suffisent à produire un épisode ; ceux-ci
# le rendent meilleur.
#
# Ils sont retirés du schéma dès qu'une tentative a échoué, parce qu'ils
# pèsent 75 % du schéma (3193 caractères sur 4262) ET la majeure partie de
# la sortie. Mesuré sur le palier gratuit Groq : la requête complète demande
# 7677 jetons pour une limite de 8000 par minute, dont 2200 réservés à la
# sortie. Il n'y a donc de marge NULLE PART — `max_tokens` ne peut pas
# monter sans dépasser la limite, ni descendre sans couper la réponse.
# Le run #76 est mort là-dessus : trois tentatives, trois « Failed to parse
# tool call arguments as JSON », épisode perdu alors que le script était
# écrit.
#
# Même philosophie que partout ailleurs ici : un plan qui rate son animation
# retombe sur la parallaxe, une voix indisponible retombe sur le muet — un
# contrat visuel trop lourd retombe sur sa version essentielle. Une vidéo
# moins riche vaut mieux que pas de vidéo.
_ENRICHISSEMENTS = (
    "geometrie", "abstractions", "relations", "risques_predits",
    "disposition", "elements_secondaires", "mouvement_sujet",
    "mouvement_camera", "mouvement_environnement", "intensite_mouvement",
)


class ShotPromptWriter(Agent):
    nom = "shot_prompts"
    version = "2.7.0"
    prompt_ref = "ecriture/plans"

    def variables(self, entrees: dict[str, Any], ctx: Contexte) -> dict[str, Any]:
        univers: Univers = entrees["univers"]
        plans: list[PlanScript] = entrees["plans"]
        repliques_par_numero = {r["numero"]: r for r in entrees["repliques"]}
        # Un changement de décor EST un changement de scène (voir
        # pdz/production/continuite.py) : le premier plan d'une scène doit
        # établir le lieu, les suivants peuvent le supposer déjà connu.
        scenes = indices_de_scene([p.decor for p in plans])
        return {
            "contexte_univers": univers.contexte_script(),
            # En narration, personne n'est jamais montré à l'écran (voix off
            # sur des images de ce dont elle parle) — voir la consigne dans
            # plans@1.6.0.yaml. `univers.anime` distingue ce cas des séries à
            # personnages, où un humain visible est au contraire attendu.
            "anime": univers.anime,
            # ScriptWriter décrit déjà, à chaque script (CONTRAINTE ABSOLUE
            # #7), comment le dernier plan doit boucler avec le premier —
            # jamais lu par aucun agent en aval jusqu'ici (voir l'audit
            # data-flow). Vide sur un job repris d'avant ce champ.
            "derniere_image": entrees.get("derniere_image", ""),
            "plans": [
                {
                    "numero": p.numero,
                    "personnage": p.personnage,
                    "replique": repliques_par_numero.get(p.replique_numero, {}).get("replique", ""),
                    "reaction": p.reaction,
                    "action": p.action,
                    "fonction_plan": p.fonction,
                    "nouvelle_scene": i == 0 or scenes[i] != scenes[i - 1],
                    "dernier": i == len(plans) - 1,
                }
                for i, p in enumerate(plans)
            ],
        }

    def schema(self, base: dict, entrees: dict[str, Any], ctx: Contexte) -> dict:
        """Impose au moins un prompt par plan — y compris les plans de
        réaction, qui n'existent qu'après le découpage et n'ont sinon
        jamais reçu de prompt écrit pour eux.

        Et, sur une SECONDE tentative, allège le contrat : voir
        `_ENRICHISSEMENTS`.
        """
        schema = copy.deepcopy(base)
        schema["properties"]["plans"]["minItems"] = len(entrees["plans"])

        if entrees.get("_erreur_precedente"):
            proprietes = schema["properties"]["plans"]["items"]["properties"]
            retires = [c for c in _ENRICHISSEMENTS if proprietes.pop(c, None)]
            if retires:
                log.warning(
                    "Contrat visuel allégé pour la relance : %d champ(s) "
                    "d'enrichissement retirés (%s). Les images resteront "
                    "correctes ; l'animation retombera sur son vocabulaire "
                    "par émotion.", len(retires), ", ".join(retires),
                )
        return schema

    def apres(self, sortie: dict, entrees: dict, ctx: Contexte) -> dict:
        plans_ecrits = sortie.get("plans", [])
        attendus = {p.numero for p in entrees["plans"]}
        obtenus = {p.get("numero") for p in plans_ecrits}
        manquants = attendus - obtenus
        if manquants:
            raise ErreurValidation(
                f"Prompts d'image manquants pour les plans "
                f"{sorted(manquants)} — il en faut un par plan, "
                f"{len(attendus)} au total."
            )

        # Diagnostic seulement, jamais une relance (voir cadrage.py) : un
        # appel Groq de plus pour ça annulerait justement ce qu'on cherche à
        # réduire cette nuit.
        par_numero = sorted(plans_ecrits, key=lambda p: p["numero"])
        avertissements = cadrage.verifier_diversite(
            [p.get("cadrage", "") for p in par_numero]
        )
        for a in avertissements:
            log.info("Cadrage : %s", a)

        return sortie

    def fusionner(self, plans: list[PlanScript], sortie: dict) -> list[PlanScript]:
        """Remplace `action` et `cadrage` par ceux écrits ici, plan par plan.

        Sépare exprès de `apres()` : `apres()` valide ce que le modèle a
        renvoyé, `fusionner()` l'applique au storyboard. Un plan dont le
        numéro n'a pas de prompt correspondant — ne devrait plus arriver
        après `apres()`, mais un appelant qui saute la validation ne doit
        pas planter pour autant — garde son action d'origine plutôt que de
        perdre toute description.
        """
        par_numero = {p["numero"]: p for p in sortie.get("plans", [])}
        fusionnes = []
        renforces = 0
        for p in plans:
            ecrit = par_numero.get(p.numero)
            if ecrit is None:
                fusionnes.append(p)
                continue
            prompt, manquants = fidelite_visuelle.renforcer(
                ecrit["prompt_image"], ecrit.get("elements_obligatoires", [])
            )
            if manquants:
                renforces += 1
                log.info("Plan %d : élément(s) manquant(s) rajouté(s) — %s",
                         p.numero, ", ".join(manquants))
            prompt = fidelite_visuelle.exclure(
                prompt, ecrit.get("elements_a_exclure", [])
            )

            # abstractions : un concept risqué (marque, présence interdite…)
            # remplacé par son substitut visuel s'il apparaît tel quel dans
            # le prompt, sinon le substitut est simplement ajouté — défense
            # en profondeur, au cas où le concept viendrait d'une reprise
            # antérieure du texte plutôt que du prompt écrit ici.
            abstractions = ecrit.get("abstractions", [])
            for a in abstractions:
                concept, representation = a.get("concept", ""), a.get("representation", "")
                if not concept or not representation:
                    continue
                motif = re.compile(re.escape(concept), re.IGNORECASE)
                if motif.search(prompt):
                    prompt = motif.sub(representation, prompt)
                else:
                    prompt, _ = fidelite_visuelle.renforcer(prompt, [representation])

            # risques_predits : le modèle anticipe lui-même un défaut connu
            # du générateur ET sa formulation d'évitement, dans le même
            # souffle qui écrit le prompt — jamais d'attendre qu'un mot
            # interdit apparaisse d'abord (voir risque_prompt.py).
            risques_predits = ecrit.get("risques_predits", [])
            mitigations = [r["mitigation"] for r in risques_predits if r.get("mitigation")]
            prompt, _ = fidelite_visuelle.renforcer_libre(prompt, mitigations)

            # relations : qui fait quoi avec quoi, déjà formulé par le
            # modèle qui vient d'écrire la phrase — jamais reconstruit par
            # position côté Python (mécanisme superseded, voir plan).
            relations = ecrit.get("relations", [])
            etats = [
                f"{r['cible']} {r['etat']}" for r in relations
                if r.get("cible") and r.get("etat")
            ]
            prompt, _ = fidelite_visuelle.renforcer_libre(prompt, etats)

            # geometrie : où se place chaque objet nommé l'un par rapport à
            # l'autre — jamais une coordonnée, jamais confondu avec la
            # priorité perceptuelle (élements_obligatoires/secondaires,
            # juste en dessous). Même filet conditionnel que les autres
            # champs : une position déjà couverte par la prose n'est pas
            # rajoutée en double.
            geo = ecrit.get("geometrie", [])
            phrases_geo = [
                p2 for g in geo
                if (p2 := geometrie_mod.phrase(
                    g.get("entite", ""), g.get("zone", ""), g.get("profondeur", ""),
                ))
            ]
            prompt, _ = fidelite_visuelle.renforcer_libre(prompt, phrases_geo)

            elements_obligatoires = ecrit.get("elements_obligatoires", [])
            elements_secondaires = ecrit.get("elements_secondaires", [])
            if elements_secondaires and elements_obligatoires:
                # Priorité perceptuelle, jamais une position physique —
                # « visual focus »/« secondary in the frame », jamais
                # « foreground »/« background » (interdit par le plan).
                primaires = ", ".join(elements_obligatoires)
                secondaires = ", ".join(elements_secondaires)
                prompt = f"{prompt}, {primaires} as the visual focus, {secondaires} secondary in the frame"

            # disposition : vocabulaire qualitatif fixe, replié dans
            # registre_visuel — jamais un nouveau paramètre sur
            # prompt_plan(), qui reste intouché.
            disposition = ecrit.get("disposition", "")
            registre_visuel = ecrit.get("registre_visuel", p.registre_visuel)
            phrase_disposition = cadrage.phrase_disposition(disposition)
            if phrase_disposition and phrase_disposition.lower() not in registre_visuel.lower():
                registre_visuel = (
                    f"{registre_visuel}, {phrase_disposition}" if registre_visuel
                    else phrase_disposition
                )

            # mouvement_* : décisions pour un clip ANIMÉ, jamais consommées
            # ici — `action`/`prompt` restent le prompt d'IMAGE, intouché
            # par ces champs. Simple passthrough, lu directement par
            # `pdz.production.animation._prompt_mouvement()` plus tard dans
            # le pipeline (voir plans@1.13.0).
            fusionnes.append(replace(
                p, action=prompt, cadrage=ecrit.get("cadrage", p.cadrage),
                registre_visuel=registre_visuel,
                elements_obligatoires=elements_obligatoires,
                elements_a_exclure=ecrit.get("elements_a_exclure", []),
                elements_secondaires=elements_secondaires,
                relations=relations,
                abstractions=abstractions,
                risques_predits=risques_predits,
                disposition=disposition,
                geometrie=geo,
                mouvement_sujet=ecrit.get("mouvement_sujet", ""),
                mouvement_camera=ecrit.get("mouvement_camera", ""),
                mouvement_environnement=ecrit.get("mouvement_environnement", ""),
                intensite_mouvement=ecrit.get("intensite_mouvement", ""),
                corrections_fidelite=manquants,
            ))
        if renforces:
            log.info("Fidélité visuelle : %d/%d plan(s) complété(s) après coup",
                     renforces, len(fusionnes))
        return fusionnes
