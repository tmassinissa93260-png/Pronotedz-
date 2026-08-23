# Phase 9 — Diagnostic et compilateur de réparation

## LE DIAGNOSTIC NE RE-MESURE RIEN

Il lit le rapport d'observation et traduit des contrôles en échec en causes
nommées. Chaque constat **cite les mesures** qui l'étayent — le contrat
`FailureFinding` refuse un constat sans preuve, `FailureDiagnosis` refuse une
cause racine absente des constats.

`CHECK_TO_FAILURE` est une table, pas une cascade de conditions : elle se lit,
elle se complète, et un contrôle sans traduction se voit immédiatement. Un
test vérifie que **tout contrôle émis par l'observateur y figure**.

**La cause racine est la plus en amont, pas la plus visible.** Une image noire
explique l'absence de mouvement ; l'inverse est faux. `_ROOT_PRIORITY` fixe
cet ordre.

## LA RÉPARATION EST BORNÉE ET GARANTIE

`RESPONSES` associe une réponse à chaque cause : quoi faire, et **à quelle
étape rembobiner**. Une cause sans réponse lève une erreur — compléter la
table plutôt qu'improviser.

Trois garanties, tenues par les contrats autant que par le code :

* **bornée** — au dernier cycle, la dernière action doit être un repli
  garanti, et `RepairPlan` le refuse sinon ;
* **gratuite en dernier recours** — un repli local ne peut pas être chiffré,
  et le contrat le refuse ;
* **traçable** — la stratégie mise en échec est enregistrée et le routeur ne
  la reproposera pas.

Le repli se fait plus sobre à mesure que les cycles s'épuisent :

```
cycle 1 → FALLBACK_2_5D
cycle 2 → FALLBACK_KEN_BURNS
cycle 3 → FALLBACK_STILL
```

Un test fait tourner la boucle sur trois cycles et vérifie qu'elle **converge**
sur une image fixe, puis qu'un quatrième cycle est refusé.

## SAUTER EST UNE DÉCISION, PAS UN OUBLI

Quand tous les plans sont conformes, `pdz2 diagnose` **saute explicitement**
les étapes `diagnosis` et `repair`, avec un motif écrit au journal. Sur
l'épisode de référence : *« 6 plans conformes, rien à diagnostiquer »*.

## TEST RESULTS

```
$ pytest pdz2/tests -q   →  694 passed
```

20 tests pour la phase 9.

## NEXT STEP

Phase 10 — montage, mastering audio, sous-titres, QA finale, livraison.
