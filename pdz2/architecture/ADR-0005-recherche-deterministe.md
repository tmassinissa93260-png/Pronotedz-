# ADR-0005 — Une recherche déterministe, et un raisonneur qu'on n'invente pas

**Statut** : accepté — phase 1
**Date** : 2026-08-22

## Contexte

Le §4 demande un moteur qui cherche, identifie des affirmations, les rattache
à des sources, calcule une confiance, construit un Fact Graph et repère ce qui
est démontrable visuellement. Le §6 demande un Director Core qui produit une
décision conceptuelle, ensuite compilée de façon déterministe.

Deux contraintes réelles de cet environnement :

* la politique réseau refuse les hôtes de recherche web (403 au CONNECT sur
  `fr.wikipedia.org`, vérifié) ;
* aucun identifiant de modèle de langue n'est disponible.

Le cahier des charges tranche ce cas : « Si une dépendance externe n'est pas
disponible, l'architecture doit l'indiquer explicitement et utiliser uniquement
un fallback réellement implémenté. »

## Décision

### La recherche est déterministe et fonctionne sans réseau

`LocalCorpusProvider` lit un dossier de documents sourcés — en-tête obligatoire
avec titre, type et autorité. Un document sans en-tête est **refusé** : une
affirmation sans source déclarée n'a rien à faire dans un Fact Graph.

L'extraction est **lexicale, pas générative**. Une phrase devient candidate
selon des signaux comptables : termes du sujet, indices causaux, grandeur
chiffrée, longueur exploitable. Chaque affirmation sort **citée mot pour mot**,
jamais reformulée — un test le vérifie contre le corpus.

Ce n'est pas un modèle de langue et cela ne prétend pas l'être. Un extracteur
lexical ne sait pas reformuler ; il sait citer. Une citation exacte adossée à
sa source est exactement ce dont le Fact Graph a besoin.

### La confiance est une fonction écrite

```
base          = max sur les preuves favorables de (autorité × force)
corroboration = bonus décroissant par source indépendante supplémentaire
contradiction = pénalité proportionnelle à la meilleure preuve contraire
```

Deux citations d'une même source ne corroborent pas. Une source contraire de
poids comparable rend l'affirmation *disputée*. Sans preuve favorable face à
une preuve contraire, elle est *réfutée* et sa confiance tombe à zéro.

Chaque résultat porte son arithmétique en clair. La formule est contestable —
c'est le but.

### Les seuils sont mesurés, pas devinés

Les seuils de regroupement et d'arêtes ont été **mesurés sur de la prose
technique réelle**, pas choisis à vue :

| Décision | Séparation observée | Seuil retenu |
| --- | --- | --- |
| Deux phrases disent la même chose | reformulations 0,60–0,75 ; distinctes < 0,25 | 0,50 (Jaccard) |
| Une grandeur chiffre un mécanisme | liens réels ≥ 0,28 ; sans rapport 0,00 | 0,25 (recouvrement) |
| Une définition éclaire un énoncé | liens réels ≥ 0,11 ; sans rapport 0,00 | 0,10 (recouvrement) |

Deux mesures distinctes, parce que les questions sont distinctes : Jaccard
répond à « ces deux phrases sont-elles la même ? », le recouvrement à « cette
phrase courte parle-t-elle du sujet de cette phrase longue ? ». Une grandeur
en huit mots ne peut structurellement pas *ressembler* au mécanisme en trente
mots qu'elle chiffre.

Le graphe est délibérément conservateur : entre deux documents distincts, le
seuil monte. Une arête manquante se rattrape ; une fausse chaîne causale se
retrouve dans la vidéo et se raconte au spectateur.

### MESURER n'est pas DÉCIDER

Le moteur calcule une `demonstrability` — à quel point une affirmation est
*montrable*. Il ne coche jamais `visually_demonstrable`, et n'écrit jamais de
`visual_proof`. Décider *ce que le spectateur doit voir* est une décision
conceptuelle : elle appartient au Director Core, adossée à une preuve rédigée.
Le contrat `Claim` refuse de toute façon l'un sans l'autre.

### Le brief est la seule décision, le reste est compilé

`DirectorBrief` porte ce qu'aucun calcul ne produit : thèse, ton, rythme,
registre visuel, chute, ancres, et une preuve visuelle par affirmation. Le
`DirectorCompiler` en déduit tout le reste sans un seul appel supplémentaire :
chaîne causale (ordre topologique du **sous-graphe retenu**), fonction
narrative de chaque plan, durées réparties sous les bornes de rythme, courbe
émotionnelle, densité d'information.

Le compilateur refuse plutôt que d'arranger : une affirmation réfutée, une
affirmation disputée sans `acknowledged_dispute`, une preuve portant sur une
affirmation absente de la recherche, un brief rédigé sur un autre état de
recherche, un budget temporel intenable.

### Le raisonneur : un port, pas un faux adaptateur

Le port `Reasoner` est défini. **Aucun adaptateur ne l'implémente**, et c'est
écrit partout — dans le module, dans `pdz2 phases`, et dans un test qui
échouera le jour où un adaptateur apparaîtra sans que la mention soit retirée.

Le chemin disponible aujourd'hui est le brief rédigé à la main, appuyé par
`pdz2 brief-template` : un gabarit qui classe les affirmations par
démontrabilité mesurée, rappelle leur texte, et **laisse vides** les champs
que seul un auteur peut écrire. Un gabarit non rempli est refusé par le
contrat. C'est le comportement voulu : « HUMANS JUDGE WHAT MACHINES CANNOT
MEASURE ».

## Alternatives écartées

* **Un adaptateur HTTP de recherche web écrit à l'aveugle.** Rejeté : ni
  joignable ni vérifiable depuis cet environnement, donc une capacité fictive.
* **Un extracteur qui reformule.** Rejeté : sans modèle, une reformulation
  déterministe est une paraphrase mécanique qu'aucune source ne dit.
* **Un `visual_proof` produit par gabarit.** Rejeté : ce serait exactement
  « illustrer une phrase abstraite », ce que le §5 interdit.

## Conséquences

* La qualité factuelle d'un épisode dépend du corpus fourni. C'est assumé :
  un corpus tenu à la main est souvent une meilleure base qu'une recherche
  web, et il est reproductible.
* Brancher un raisonneur ne changera rien en aval : il produira un
  `DirectorBrief`, exactement comme un humain, et passera par les mêmes refus.
