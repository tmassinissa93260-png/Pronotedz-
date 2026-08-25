# ADR-0008 — Une capacité se mesure, une dépense s'autorise

**Statut** : accepté — phase 11
**Date** : 2026-08-23

## Contexte

Le §14 pose une distinction qui a l'air d'un détail de vocabulaire :

```
ANNOUNCED ≠ MEASURED ≠ UNKNOWN
```

Elle ne l'est pas. Un routeur qui traite une capacité annoncée comme une
capacité réelle fait des choix sur du vide : il envoie un plan de douze
secondes à un moteur qui en accepte cinq, il chiffre un budget avec un tarif
de brochure, il compte sur une résolution que personne n'a jamais obtenue.
L'erreur ne se voit pas au moment de la décision — elle se voit à la
facturation, ou à l'échec.

Le même piège existe côté coût. Un compteur qui additionne les dépenses
passées ne gouverne rien : quand il annonce le dépassement, l'argent est
parti.

## Décision

### 1. La provenance est portée par le contrat, pas par le moteur

`CapacityValue` refuse trois formes de malhonnêteté, à la construction :

| écrit | refusé parce que |
| --- | --- |
| `MEASURED` sans `measured_at` | une capacité non datée est `UNKNOWN` |
| `MEASURED` sans `method` | une mesure se rejoue ou n'existe pas |
| `UNKNOWN` avec une `value` | on ne chiffre pas ce qu'on ne sait pas |

Le troisième est le plus utile : il rend structurellement impossible le
« chiffre approximatif en attendant », qui est la manière habituelle dont une
estimation devient une vérité.

### 2. Une mesure vieillit

`is_stale()` rend vrai au-delà de trente jours. Les fournisseurs changent
leurs modèles sans prévenir ; une capacité vérifiée il y a deux mois est une
capacité inconnue qui s'ignore. `trustworthy()` exige donc **mesurée et
récente**, et c'est cette méthode-là que le gouverneur consulte.

### 3. Le gouverneur autorise avant, il ne constate pas après

`CostGovernor.may_spend()` est appelé **avant** d'engager. Il rend trois refus
distincts, parce qu'ils appellent trois réactions différentes :

* `BUDGET_EXHAUSTED` — il ne reste rien : arrêter.
* `WOULD_EXCEED` — cette dépense-ci passerait au-dessus : la réduire.
* `UNMEASURED_COST` — on ignore ce que ça coûte : mesurer d'abord.

Le troisième se déclenche **même quand le budget est intact**. C'est le point
de cette ADR : engager une dépense dont on ne connaît pas le montant, c'est
perdre le contrôle du budget d'un seul coup, pas progressivement.

`estimate()` suit la même règle et rend `None` plutôt qu'un chiffre annoncé.

### 4. Une seule comptabilité

`pdz2 costs` ne tient pas de livre à part : il relit les transitions de la
machine à états qui portent un coût. C'est la transposition, au budget, de la
règle « une seule timeline audio » de la phase 2 — deux comptabilités qui
divergent valent moins qu'une seule qui tient.

`CostLedger` refuse par ailleurs un registre dont le total dépasse son
plafond : un tel objet ne devrait pas pouvoir exister, puisque la dépense
aurait dû être refusée avant d'avoir lieu.

## Conséquences

* La sonde ne crée **aucune entrée** pour un fournisseur absent. Aujourd'hui,
  `NO_VIDEO_PROVIDERS` étant vide, la matrice ne contient que `ffmpeg` et
  `espeak-ng` — les deux outils réellement présents.
* Les capacités des outils locaux sont mesurées en les faisant travailler :
  60 images encodées et relues par `ffprobe`, une phrase synthétisée et sa
  durée lue sur les trames. `--measure` est explicite parce que faire tourner
  les outils coûte du temps ; sans lui, les valeurs restent `UNKNOWN`, sans
  chiffre.
* `cost_per_second_usd = 0` pour un binaire local est enregistré `MEASURED`, et
  la méthode dit pourquoi : aucun compte, aucun jeton, aucune facturation. Le
  coût **machine**, lui, est ailleurs — c'est `encode_fps`.

## Ce que cette décision coûte

Un moteur qui voudrait tenter une génération vidéo « pour voir » sera refusé
tant que son coût n'aura pas été relevé une première fois. C'est voulu : la
première facture est une mesure, et elle doit être faite exprès, pas subie.
