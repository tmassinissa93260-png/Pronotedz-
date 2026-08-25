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
| raisonneur | `anthropic`, `groq` | aucun — le brief se rédige à la main |
| sons | aucun | aucun : les repères restent **non résolus**, et le disent |

Le repli local n'est jamais retiré d'une famille. Ce n'est pas un plan B
facultatif, c'est la garantie de livraison — et un test d'architecture le
vérifie pour chaque combinaison de clés.

## DEUX RAISONNEURS, UNE SEULE SURFACE DE DÉCISION

Anthropic et Groq : deux services, deux formes d'API, deux factures — dont
une nulle, Groq servant sur son palier gratuit. Ce qu'on leur demande est
strictement identique, et `providers/reasoning.py` le tient : surface de
décision, consigne, scellement, boucle de reprise. Un adaptateur ne fournit
qu'une chose, `demander(échanges) -> dict`.

Sans cette séparation, la surface de décision existerait en deux exemplaires
qui divergeraient au premier changement de contrat — le motif exact que ce
dépôt traque.

Quand les deux clés sont là, l'ordre tranche, mais un ordre n'est pas une
décision : `PDZ2_REASONER` nomme celui qu'on veut. Et si le raisonneur nommé
n'a pas sa clé, **aucun autre ne prend sa place** : le brief serait signé
d'un nom qu'on n'a pas demandé, et personne ne s'en apercevrait avant de
relire le contrat.

### Ce que Groq impose, et qu'on a appris ailleurs

Trois choses ne sont pas devinées — elles viennent de mesures faites en
production par l'ancien système, que cet adaptateur consigne :

* **La contrainte de forme passe par un appel d'outil forcé**, pas par
  `response_format` : `tools` + `tool_choice`, à la façon OpenAI.
* **Groq rend parfois `"true"` en chaîne** là où le schéma attend un
  booléen — et `VisualProofDraft.acknowledged_dispute` en est un. Le schéma
  envoyé accepte les deux types, la réponse est durcie au retour. On accepte
  un dialecte à la porte, pas dans la maison : le contrat reste strict.
* **`llama-3.3-70b-versatile` est mort** — coupé le 17/06/2026, constaté en
  production le 18/08/2026 par un 404 avant le premier appel. Un identifiant
  périmé n'est rattrapable par aucun repli. La sonde vérifie donc que le
  modèle est encore au catalogue, et le dit s'il n'y est plus.

### Ce que le premier appel réel a appris

Le 25/08/2026, la première requête vraiment partie s'est fait refuser :

    413 — Request too large … tokens per minute (TPM):
    Limit 8000, Requested 18813

Le texte envoyé ne pesait que 2 800 jetons. Les 16 000 autres étaient la
**sortie réservée** : Groq la compte dans son plafond avant qu'un seul mot ne
soit écrit. Réserver largement « au cas où » brûlait donc deux fois le budget
pour rien.

Trois corrections, dont deux profitent aussi à l'autre raisonneur :

* **Le gabarit recopié dans la demande a disparu** (−1 050 jetons). Il redisait
  ce que le schéma décrit déjà, plus strictement, et les affirmations qu'il
  rappelait sont dans le relevé de recherche.
* **Les `title` fabriqués par pydantic ne sont plus envoyés** (−265 jetons) :
  le modèle lit déjà le nom du champ juste à côté.
* **La sortie n'est plus réservée en aveugle.** Elle est calculée : ce que le
  plafond laisse une fois la question payée, avec 8 % de réserve pour absorber
  l'écart d'estimation. En dessous de 1 500 jetons pour écrire, l'adaptateur
  refuse en le disant plutôt que de rendre une décision tronquée.

Et la reprise du contrat, qui renvoie une seconde requête quelques secondes
après la première, **attend le tour de la fenêtre** au lieu de se cogner à un
plafond qu'on savait atteindre. La requête réelle est passée de 18 813 jetons
demandés à 7 360, pour 8 000 permis.

### Ce que le deuxième appel réel a appris

La requête est passée, le modèle a décidé — et le service a refusé sa sortie
contre le schéma :

    /visual_proofs/0 : missing properties: 'acknowledged_dispute',
      'anchor_names', 'causal_mechanism', 'evidence_required', 'visual_proof'
    /visual_proofs/0 : additionalProperties 'description' not allowed

Une preuve visuelle réduite à un `claim_id` et un champ `description` inventé :
la signature d'un **renvoi vers `$defs` que le modèle n'a pas suivi**. Il ne
voyait, à l'endroit où il écrivait, qu'un pointeur.

Le schéma envoyé ne contient donc plus aucun `$ref` : chaque définition est
mise en place. Le coût est nul — chacune n'était citée qu'une fois, donc on
les déplace au lieu de les copier ; le schéma a même perdu 68 jetons avec
l'enveloppe `$defs`. Un test refuse désormais qu'un `$ref` revienne, et un
autre surveille que l'inlining ne se mette pas à dupliquer si un contrat futur
citait deux fois la même définition.

S'y ajoute un filet : **un refus de forme par le service est retenté une
fois**. Il vient du modèle, pas de la requête — la même demande peut mieux
tomber. À ne pas confondre avec la reprise du contrat, qui explique au modèle
ce qu'on lui reproche ; ici il n'a rien produit d'exploitable à commenter. Une
clé refusée ou un plafond dépassé, eux, ne sont jamais retentés : les rejouer
ne les rendrait pas valides.

## UNE SONDE VERTE N'EST PAS UNE GARANTIE

Le repli local n'était pas tenu là où il sert. Le CLI choisissait le moteur de
voix sur sa **sonde**, puis s'y accrochait :

    moteur elevenlabs : retenu — 21 voix disponibles
    calibration impossible : 402 — Free users cannot use library
      voices via the API.
    PRODUCTION INTERROMPUE à l'étape « voice ».

Sonde verte, production morte. Le registre promettait que le moteur local
n'est jamais retiré d'une famille ; la promesse ne valait rien tant qu'elle
n'était pas tenue **au moment où elle sert**, c'est-à-dire quand le distant
lâche en cours de route.

Le repli se déclenche désormais sur la synthèse, pas seulement sur la sonde,
et chaque écart est inscrit au journal comme dégradation — un repli silencieux
donnerait un épisode correct et un journal faux. Si aucun moteur ne parle,
c'est un refus : jamais un épisode muet.

Une seconde supposition tombe avec celle-là. L'adaptateur portait un
identifiant de voix **en dur**, pris dans le catalogue public. Une voix de
bibliothèque n'appartient pas au compte, et le palier gratuit la refuse. On
lit maintenant le catalogue du compte, en préférant ce qui est à lui — voix
clonée ou générée — avant les voix communes ; et à défaut on déclare
l'indisponibilité au lieu d'inventer un identifiant.

## CE QU'UN CONTRAT N'EXIGE PAS, UN MODÈLE L'IGNORE

La palette de la bible visuelle devait être hexadécimale. La règle vivait dans
deux docstrings et un validateur de fin de chaîne — donc nulle part où elle
comptait. Le raisonneur a rendu :

    palette : ['bleu électrique', 'gris acier', 'blanc pur']

Le brief a été **accepté**, enregistré, et la compilation visuelle est tombée
trois étapes plus tard sur une trace d'exécution.

Deux endroits l'ignoraient, et c'est le même oubli vu de deux côtés :

* le **schéma envoyé au modèle** n'annonçait qu'une liste de chaînes ;
* le **contrat du brief** ne vérifiait rien, laissant le refus à un
  consommateur lointain.

`HexColour` est maintenant un type annoté, défini une fois dans
`contracts/common.py` et employé par le brief comme par la bible. En type, la
contrainte est vérifiée **à la porte** et publiée **dans le schéma JSON** : le
raisonneur la lit avant d'écrire, et s'il se trompe quand même, la boucle de
reprise lui rend l'erreur exacte au lieu de laisser passer.

La leçon générale, elle, dépasse les couleurs : une règle qu'un commentaire
est seul à porter n'est pas une règle. Elle ne devient contraignante qu'en
atteignant le type — le seul endroit que lisent à la fois le validateur et le
modèle.

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
`ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `GROQ_MODEL`, `PDZ2_REASONER`. Aucune n'a
de valeur par défaut, et aucune valeur n'est jamais écrite dans un contrat, un
journal ou une sortie de commande.
