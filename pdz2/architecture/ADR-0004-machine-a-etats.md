# ADR-0004 — Machine à états : dépendances, barrière de coût, boucle bornée

**Statut** : accepté — phase 0
**Date** : 2026-08-22

## Contexte

Une production doit être *reprenable* (une interruption ne doit pas coûter deux
fois), *observable* (on doit savoir pourquoi elle est là où elle est) et
*bornée* (une boucle de réparation ne doit pas tourner à l'infini ni vider un
budget).

## Décision

### Un graphe, pas une file

Les 21 étapes forment un DAG (`pdz2/state/stages.py`). Une étape démarre quand
toutes ses dépendances sont `DONE` ou `SKIPPED`. Le graphe encode des règles :

* `TIMELINE` dépend de `VOICE` : la timeline officielle ne peut pas exister
  avant l'audio réel. La règle VOICE FIRST devient une impossibilité, pas une
  consigne.
* `EDIT` dépend de `DIAGNOSIS` et `REPAIR` (toutes deux sautables avec motif) :
  on ne monte jamais sans avoir explicitement statué sur l'observation. Sauter
  le diagnostic est une décision écrite au journal, pas un oubli.

### Une barrière de coût

`ASSETS` et `RENDER` sont marquées `gated_by_validation`. Elles refusent de
démarrer tant que `STATIC_VALIDATION` n'est pas `DONE`, et le refus le dit
avant même de parler des dépendances. Aucun appel coûteux avant validation.

Le plafond budgétaire est vérifié deux fois : au démarrage d'une étape payante
(budget déjà épuisé) et à la déclaration d'un coût (le franchirait). Une étape
déclarée sans coût qui rapporte une dépense est refusée.

### Une boucle bornée

`rewind(stage)` remet une étape **et tout son aval transitif** en attente, en
effaçant leurs artefacts. C'est le mécanisme du Repair Compiler : réparer le
rendu invalide l'observation, le diagnostic et le montage qui en dérivaient.
Chaque rembobinage consomme un cycle de réparation ; le plafond atteint, la
machine refuse et renvoie vers le repli garanti.

### Un état sérialisable

Tout tient dans `EpisodeSnapshot` : statut de chaque étape, tentatives,
artefacts, dépense, cycles, et le **journal complet des transitions**
(`StateTransition` : étape, avant, après, horodatage, motif, acteur, coût).
`EpisodeStateMachine.resume(snapshot)` repart de là, sur une copie — la reprise
ne modifie pas l'objet d'origine.

## Alternatives écartées

* **Un état par étape en cours (`RESEARCHING`, `RESEARCHED`, …).** Rejeté :
  42 états pour dire ce que `(étape, statut)` dit en deux dimensions.
* **Un statut d'étape mutable sans journal.** Rejeté : sans journal, une
  production n'est pas explicable après coup.
