# Phase 1 — ce qui est réellement implémenté et vérifié

**Périmètre du cahier des charges** : Research + Fact Graph + DirectorState.

## Chaîne réellement exécutable aujourd'hui

```
pdz2 research       --episode ep/ --topic "Comment fonctionne une voiture électrique ?" \
                    --corpus corpus/ --duration 45
pdz2 brief-template --episode ep/ --out brief.json      # gabarit à remplir
pdz2 direct         --episode ep/ --brief brief.json
```

Produit, dans le dossier d'épisode :

```
ep/
├── topic_request.json
├── research.json         ResearchState : sources, preuves, affirmations, Fact Graph
├── director_brief.json   la décision conceptuelle, telle qu'elle a été prise
├── director_state.json   DirectorState complet, compilé
└── state.json            machine à états : research=done, direction=done, journal complet
```

## Ce que ça donne sur un corpus réel

Trois documents sourcés (documentation, article, encyclopédie), dont deux se
contredisent volontairement sur le rendement :

```
3 documents retenus
12 phrases candidates, regroupées en 10 affirmations
1/10 affirmations corroborées par au moins deux sources
couverture du sujet : 0.6667

[corroborated 0.65] Le moteur électrique convertit l'énergie électrique de la batterie…
[disputed     0.16] Le rendement d'une chaîne de traction électrique atteint 90 %…
[unverified   0.46] Le stator, parcouru par un courant alternatif, génère un champ…

4 arêtes : stator --causes--> rotor ; rendement --quantifies--> conversion ;
           définition --enables--> conversion, rendement
```

La contradiction entre deux sources est **trouvée**, pas moyennée. La
corroboration exige deux sources **indépendantes**.

## Décisions structurantes

| Règle | Où elle est tenue |
| --- | --- |
| Une affirmation est **citée**, jamais réécrite | test comparant chaque `Claim.text` au corpus |
| Deux citations d'une même source ne corroborent pas | `ConfidenceModel`, clé de source |
| MESURER (`demonstrability`) ≠ DÉCIDER (`visually_demonstrable`) | recherche vs Director Core |
| Le graphe reste acyclique par construction | `build_edges` refuse toute arête bouclante |
| Une arête entre documents distincts exige plus | `cross_document_overlap` |
| Une affirmation disputée ne passe pas par inadvertance | `acknowledged_dispute` obligatoire |
| Une affirmation réfutée ne passe jamais | `BriefRejected` |
| Un seul appel conceptuel, tout le reste compilé | `DirectorBrief` → `DirectorCompiler` |
| Rien ne disparaît en silence | `DirectionOutcome.dropped` |
| Sans fournisseur joignable, on refuse | `NoUsableProvider`, jamais un état vide |

## Défauts trouvés et corrigés pendant la phase

Ces quatre-là ont été trouvés en exécutant le moteur sur du texte réel, pas en
relisant le code :

1. **`" ne "` matchait dans « chaî*ne de* »** — une phrase affirmative passait
   pour niée, et la contradiction sur le rendement était comptée comme une
   corroboration. La détection est désormais lexicale, sur mots entiers.
2. **Les élisions cassaient la similarité** — « n'atteint » et « atteint »
   étaient deux mots différents, donc une phrase niée ne rejoignait jamais le
   groupe qu'elle contredit.
3. **L'ordre causal se calculait sur le graphe entier** — une affirmation
   retenue se retrouvait reléguée à cause d'un lien vers une affirmation
   écartée. Il porte maintenant sur le sous-graphe induit.
4. **Jaccard était la mauvaise mesure pour les arêtes** — une grandeur courte
   ne peut structurellement pas ressembler au mécanisme long qu'elle chiffre.
   Le coefficient de recouvrement sépare les liens réels (≥ 0,11) des paires
   sans rapport (0,00) sans aucun faux positif sur le corpus de test.

Une cinquième correction vient d'un test : la branche d'exclusion du
compilateur était **du code mort**, le contrat garantissant déjà la
disjonction. Elle a été retirée, et `excluded_claim_ids` a reçu la sémantique
qu'elle mérite — une trace éditoriale, vérifiée et journalisée.

## Contrats

* `claim` **1.0.0 → 1.1.0** : ajout de `demonstrability`. Compatible en
  lecture — un document 1.0.0 se relit sans migration, et un test le vérifie.
  Première évolution réelle du versionnage.
* `director_brief` **1.0.0** : nouveau contrat, dans `pdz2/contracts/` et non
  dans le moteur — un contrat déclaré hors du paquet échapperait au registre
  et aux schémas. Un test d'architecture interdit désormais ce cas.

## Limites déclarées, pas contournées

* **Aucune recherche web.** La politique réseau de cet environnement refuse
  les hôtes de recherche (403 au CONNECT, vérifié). Le seul fournisseur est le
  corpus local — réellement implémenté, sondé avant usage.
* **Aucun raisonneur.** Le port `Reasoner` est défini ; aucun adaptateur ne
  l'implémente. Le brief est rédigé à la main, appuyé par un gabarit qui
  classe et rappelle mais n'écrit rien. Un test échoue le jour où un
  adaptateur apparaîtra sans mise à jour de `pdz2 phases`.
* **L'extraction est lexicale.** Elle repère des affirmations, elle ne les
  comprend pas. Documenté comme tel dans le module.

## Résultat d'exécution

```
$ pytest pdz2/tests -q
403 passed
$ ruff check pdz2/
All checks passed!
```

Dont, pour la seule phase 1 : 29 tests de texte, 51 de recherche, 34 de
réalisation, 12 de ligne de commande.

## Prochaine étape

Phase 2 — Script + TTS réel + timing, sous la règle VOICE FIRST déjà inscrite
dans le graphe d'étapes (`TIMELINE` dépend de `VOICE`).
