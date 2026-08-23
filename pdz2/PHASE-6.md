# Phase 6 — Port fournisseur vidéo + routeur de stratégie

## CURRENT STATE

`pdz2 route` choisit une stratégie par plan et **enregistre chaque écart**.
Sur l'épisode de référence : `parallax_2_5d×4`, `procedural×2`, 6 dégradations
consignées, 13 étapes d'exécution.

## LE PORT, ET RIEN QUE LE PORT

`pdz2/providers/video.py` définit `VideoProvider`, `VideoCapability`,
`VideoJob`, `VideoResult`. **Aucun adaptateur ne l'implémente**, et
`NO_VIDEO_PROVIDERS` le dit explicitement plutôt que de laisser une liste vide
anonyme.

La politique réseau de cet environnement refuse les hôtes de génération vidéo
et aucun identifiant n'est disponible. Un client qu'on ne peut ni joindre ni
vérifier serait une capacité fictive. Deux tests d'architecture verrouillent
la déclaration : le dossier `providers/` ne contient que des ports, et
`pdz2 phases` doit continuer à dire « aucun adaptateur vidéo implémenté ».

## LE ROUTEUR

Les critères du §18, dans l'ordre où ils s'appliquent :

```
interdiction de la vidéo IA → écarte les stratégies génératives
capacité mesurée            → écarte ce qu'aucun exécutant ne sait faire
échecs antérieurs           → écarte ce qui a déjà raté sur ce plan
risque d'identité           → note ce qu'aucun moteur ne garantit
complexité de mouvement     → still < ken burns < 2.5D < procédural
exigence caméra             → vérifie que le mouvement est tenable
durée et coût               → écarte ce qui dépasse plafond ou budget
```

Le dernier recours est toujours `STILL` : une image fixe se rend sans
personne, ce qui rend la livraison garantie.

`_CAMERA_BY_STRATEGY` liste les mouvements que chaque stratégie **sait
réellement tenir** — c'est ce que les renderers de la phase 7 implémentent,
pas une annonce.

## AUCUNE DÉGRADATION SILENCIEUSE

Le contrat `RenderSpecExecutable` refuse tout écart non déclaré. Trois champs
ont été ajoutés au vocabulaire libre parce qu'ils ne sont **pas** des écarts
de stratégie :

* `provider_availability` — la vidéo IA était autorisée, aucun fournisseur
  n'est joignable ;
* `retry_strategy` — toutes les stratégies ont déjà échoué sur ce plan ;
* `motion` — l'énergie visée n'est pas atteinte.

Quand la réalisation n'a exprimé **aucune** préférence de stratégie, en choisir
une n'est pas une dégradation. Constater qu'un fournisseur autorisé est
injoignable en est une, et elle mérite son propre nom.

## DÉFAUT TROUVÉ

**Le parallaxe retombait en Ken Burns en silence** quand l'image n'avait qu'un
calque séparable. La contrainte était absorbée dans le choix d'énergie au lieu
d'être déclarée. Elle est maintenant une `Degradation` nommée : *« un seul
calque séparable : le parallaxe n'a aucune profondeur à décaler »*.

## TEST RESULTS

```
$ pytest pdz2/tests -q   →  638 passed
```

19 tests pour la seule phase 6.

## NEXT STEP

Phase 7 — 2.5D et procédural : exécuter réellement ces stratégies.
