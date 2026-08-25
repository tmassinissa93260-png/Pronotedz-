# ADR-0003 — Versionnage des contrats et migrations explicites

**Statut** : accepté — phase 0
**Date** : 2026-08-22

## Contexte

Un épisode est produit en plusieurs heures, parfois repris plusieurs jours plus
tard, avec un code qui a bougé entre-temps. Un système « reprenable » doit
savoir dire *je ne sais pas lire ce document* plutôt que de le lire de travers.

## Décision

* Chaque contrat déclare `CONTRACT_NAME` et `CONTRACT_VERSION` (SemVer) et
  s'enregistre dans un registre unique, via le décorateur `@contract(...)`.
* Chaque instance porte les cinq champs imposés : `id`, `version`,
  `created_at`, `parent_id`, `status`. Ils sont estampillés automatiquement et
  **gelés** après création ; seul `status` reste mutable.
* Règle de lecture : un lecteur en version `R` lit une charge utile `P`
  **si et seulement si** `P.major == R.major` et `P.minor <= R.minor`.
* Tout le reste exige une **migration enregistrée**, appliquée en chaîne
  jusqu'à la version courante. Sans migration : `IncompatibleVersion`. Jamais
  de lecture « au mieux », jamais de champ deviné.
* `parent_id` porte la lignée : `derive()` produit un descendant, le parent est
  marqué `SUPERSEDED`. Une réparation est donc traçable dans les données.
* Les schémas JSON sont **générés et versionnés dans le dépôt**
  (`pdz2/schemas/json/`). Un test échoue si le code et les schémas divergent :
  une modification de contrat se voit en revue.

## Reproductibilité

Les identifiants passent par une fabrique remplaçable. `deterministic_ids(seed)`
rend `new_id()` déterministe : deux exécutions d'un même épisode avec la même
graine produisent les mêmes identifiants. C'est la condition pour comparer deux
productions autrement qu'à l'œil.

## Conséquences

* Ajouter un champ optionnel = bump mineur, les anciens documents restent
  lisibles.
* Renommer ou retirer un champ = bump majeur + migration, sinon le système
  refuse de lire — ce qui est le comportement voulu.
