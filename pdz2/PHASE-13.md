# Phase 13 — Couche d'exécution : stratégie, fournisseur, renderer

## LE TROU QUE L'AUDIT A OUVERT

Le cahier des charges pose une chaîne précise :

```
RenderSpecExecutable → ExecutionPlan → Strategy → Renderer / Provider → RenderArtifact
```

Trois maillons manquaient, et ils se tenaient.

**Le port `VideoProvider` n'était appelé par personne.** `pdz2 render`
invoquait `DeterministicRenderer` en dur. Un plan routé vers une stratégie
générative aurait été refusé à l'exécution. Le chemin I2V était du code mort,
et la chaîne était un enrobage autour d'un unique exécutant.

**Le routeur ne pouvait structurellement jamais choisir une stratégie
générative.** `_by_energy` ne rendait que des barreaux locaux, `_best` ne
parcourait que l'échelle locale : les stratégies IA ajoutées à `available`
n'étaient jamais consultées. `preferred_strategy` n'était pas lu non plus.

**`provider` et `model` valaient `None` sur tout exécutable**, sans exception.
La règle « le fournisseur décide avec quel moteur » n'avait aucun chemin de
données.

## L'ÉCHELLE ENTIÈRE

```
STILL → KEN_BURNS → PARALLAX_2_5D → PROCEDURAL │ HYBRID → CONTROLLED_I2V → DIRECT_I2V
        ← s'exécute sans personne →            │      ← demande un fournisseur →
```

`HYBRID` était déclaré dans l'enum et géré nulle part. Il se place au-dessus du
procédural et en dessous de l'I2V : sa base est générée, donc il demande un
fournisseur, mais il en demande moins qu'un plan entièrement généré.

Sans fournisseur joignable, les trois derniers barreaux n'entrent jamais dans
les stratégies mobilisables et l'échelle se réduit exactement à ce qu'elle
était : le comportement d'avant est préservé, il n'est plus le seul possible.

## LE SEUIL, MESURÉ AVANT D'ÊTRE FIXÉ

Premier essai : 0.85. Injouable — l'énergie relevée sur l'épisode de référence
(8 plans, rythme mesuré) va de 0,30 à 0,70, plafonnée par `MECHANISM`.

```
plafond par fonction            MECHANISM   0.70
rythme mesuré (documentaire)    +0.00       → 0.70   jamais génératif
rythme soutenu                  +0.10       → 0.80   génératif
rythme rapide                   +0.20       → 0.90   génératif
mécanisme répété, mesuré        +0.15       → 0.85   génératif
```

Recalé à **0,80**. Une narration posée ne paie donc jamais de modèle, ce qui
est le comportement voulu ; un épisode au rythme rapide en emmène deux plans
sur quatre chez un fournisseur. C'est le même défaut que le seuil de
lisibilité de la phase 3, trouvé de la même façon : en mesurant d'abord.

## L'AIGUILLEUR NE CHOISIT PAS LA STRATÉGIE

Elle est déjà décidée, déclarée et validée en amont. Il choisit **l'exécutant**.

Ce qu'il garantit :

* un plan génératif part chez un fournisseur qui déclare savoir le faire ;
* un plan local part chez le renderer déterministe, sans fournisseur ;
* un fournisseur qui échoue ne provoque **aucune reprise à l'aveugle** : une
  tentative, la panne nommée, l'écart déclaré, et le plan redescend l'échelle
  jusqu'à ce qui s'exécute réellement ici ;
* la livraison reste possible sans le moindre fournisseur.

Le repli redescend d'un barreau plutôt que de sauter à l'image fixe : un plan
génératif perdu vaut mieux en procédural, et l'écart déclaré dit de combien on
est descendu.

## LES LIMITES MESURÉES ÉCARTENT, LES LIMITES INCONNUES NON

Une capacité qui ne tient pas la durée ou le cadre du plan est écartée, et
l'écart est déclaré. Une limite `None` n'est pas « pas de limite » : c'est une
limite inconnue. Elle n'écarte pas le fournisseur, mais elle ne le retient pas
non plus — UNKNOWN ne devient jamais SUPPORTED sans preuve.

## CE QUE LE DOUBLE PROUVE, ET CE QU'IL NE PROUVE PAS

Le chemin fournisseur est exercé par un double **local et réel**, qui encode
vraiment par ffmpeg. Il vit dans `pdz2/tests/`, jamais dans `providers/`.
`NO_VIDEO_PROVIDERS` reste vide et `pdz2 capabilities` continue de dire
qu'aucun fournisseur vidéo n'est joignable.

Il ne prouve donc **pas** que PDZ 2 sait générer de la vidéo par IA — il ne le
sait pas, aucun service de génération n'est joignable dans cet environnement.
Il prouve que la couche qui appellera un adaptateur, mesurera son résultat et
déclarera ses échecs est écrite et vérifiée, et qu'un adaptateur pourra
se brancher sans toucher au CLI.

## TESTS — 14

Le port (2), le routage vers l'IA (4), l'exécution mélangée fournisseur/local
(5), le repli (3). Dont les deux qui comptent le plus : un fournisseur en
panne ne perd aucun plan et déclare son écart ; sans le moindre fournisseur,
chaque plan sort quand même.
