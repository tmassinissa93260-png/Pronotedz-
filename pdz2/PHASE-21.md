# Phase 21 — les fournisseurs distants, et la ligne qui les tient

Pendant vingt phases, `pdz2/providers/` a porté une phrase en tête :

> **Aucun adaptateur n'est implémenté.**

Elle était vraie, et elle était honnête : les hôtes de génération sont
injoignables depuis l'environnement où ce dépôt a été écrit, et un client
qu'on ne peut ni appeler ni vérifier est une capacité fictive.

Elle était aussi une impasse. Un compilateur audiovisuel qui ne sait produire
que du schématique procédural n'est pas un compilateur audiovisuel diminué :
c'est autre chose.

## LA DISTINCTION QUI REMPLACE LA PHRASE

    un adaptateur EXISTE dans le dépôt ;
    il n'est ACTIF que si son identifiant est présent dans l'environnement.

Ces deux états n'ont rien à voir, et les confondre est exactement la façon
dont un système se met à annoncer des capacités qu'il n'a pas. Le dépôt peut
donc contenir un client distant sans jamais prétendre pouvoir l'appeler.

`pdz2/providers/registry.py` est la seule autorité sur la question. Il lit
l'environnement, **ne touche pas au réseau** — savoir si une clé est là est
local et instantané ; savoir si le service répond est une *mesure*, et cette
mesure appartient à la matrice de capacités, qui la date.

## CE QUI EST BRANCHÉ

| famille | adaptateur distant | repli |
| --- | --- | --- |
| images | `fal-flux`, un appel par calque | `procedural-image`, toujours en fin de liste |
| animation | `fal-kling`, image vers vidéo | stratégies déterministes locales |
| voix | `elevenlabs` | `espeak-ng`, toujours en fin de liste |
| raisonneur | `anthropic` | aucun — le brief se rédige à la main |
| sons | aucun | aucun : les repères restent **non résolus**, et le disent |

Le repli local n'est jamais retiré d'une famille. Ce n'est pas un plan B
facultatif, c'est la garantie de livraison — et un test d'architecture le
vérifie pour chaque combinaison de clés.

## LE RAISONNEUR NE REÇOIT PAS UN FORMULAIRE RECOPIÉ

La surface de décision — ce qu'aucun calcul ne peut produire — est **dérivée
du contrat** `DirectorBrief`, jamais réécrite à côté :

    DirectorBrief.model_json_schema()
      → on garde les champs de _DECIDED_BY_THE_REASONER
      → on retire ce que le modèle n'a pas à choisir : identité du dossier,
        lignée du contrat, signature de son propre travail
      → on impose additionalProperties: false — la règle extra="forbid" des
        contrats, portée jusqu'au modèle

Le jour où le contrat change, le schéma envoyé change avec lui. Un brief
refusé par le contrat est renvoyé une fois au modèle avec l'erreur de
validation exacte ; si la seconde tentative échoue, l'adaptateur lève
`ReasonerUnavailable`. **Il ne complète jamais une décision à la place du
modèle.**

Et la décision reste un **fichier** : `pdz2 brief-draft` l'écrit sur le
disque, signé dans `DirectorBrief.author`, relisible et modifiable. `direct`
ne fait aucune différence entre un brief rédigé par un humain et un brief
rédigé par un raisonneur — le contrat les juge de la même façon.

## LE DÉFAUT QUE CE BRANCHEMENT A DÉTERRÉ

Le négociateur de durée choisit un **débit de parole**, mesure une synthèse
réelle, et en déduit le réglage qui tiendra la commande. Tout cela suppose
que le moteur obéisse au réglage.

eSpeak NG obéit. Un service distant qui n'expose aucune commande de vitesse,
non. Le négociateur aurait annoncé « débit porté de 165 à 190 mots/min »,
inscrit ce chiffre au contrat `DurationPolicy` — et produit un audio
identique. Une décision démentie par le fichier, invisible.

La sonde `_debit_agit()` synthétise une phrase courte à deux vitesses et
compare les durées mesurées. Le verdict est **mesuré, pas supposé** :

    sonde de débit : 3.42s à 120 mots/min contre 2.11s à 200 — écart 38 %,
    le moteur obéit au réglage

Quand le moteur ignore le débit, la décision devient `content_too_long` ou
`content_too_short` — ce qui est la vérité : le seul levier restant est le
texte. La sonde est mise en cache : elle peut coûter un appel facturé.

## CE QUI RESTE OUVERT, ET SE DIT

**Aucun de ces adaptateurs n'a été appelé ici.** `fal.run`,
`api.elevenlabs.io` sont injoignables depuis l'environnement de
développement ; `api.anthropic.com` l'est, donc la sonde du raisonneur dit la
vérité dès le premier appel, mais aucune décision n'y a été obtenue. Chaque
fichier le déclare en tête. La première exécution réelle a lieu dans
`.github/workflows/pdz2.yml`.

**Le coût des images distantes n'est pas relevé.** Le registre de dépenses
inscrit 0 parce que le montant n'a pas été facturé et lu — c'est une lacune
déclarée, pas une gratuité, et la commande l'affiche en clair.

**La recherche ne va pas sur le web.** `pdz2 research` lit un corpus de
documents sourcés. Le sujet passé en paramètre doit donc correspondre au
corpus fourni : c'est la limite réelle du « sujet en paramètre » aujourd'hui,
et aucun adaptateur de recherche distante n'a été écrit pour la masquer.

## LES COMMANDES

    pdz2 providers            qui est actif, et pourquoi — sans réseau
    pdz2 providers --probe    qui répond vraiment — avec réseau
    pdz2 phases               l'état du chantier, adaptateurs compris
    pdz2 brief-draft          faire rédiger le brief par le raisonneur

Les variables lues : `FAL_KEY`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`,
`ANTHROPIC_API_KEY`. Aucune n'a de valeur par défaut, et aucune valeur n'est
jamais écrite dans un contrat, un journal ou une sortie de commande.
