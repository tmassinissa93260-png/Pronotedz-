# Phase 5 — Image Engine

## CURRENT STATE

`pdz2 assets` produit de **vraies images** : 6 composites 1080×1920 et 14
calques PNG pour l'épisode de référence, écrits sur le disque, déterministes
au bit près.

## CE QUE C'EST, ET CE QUE CE N'EST PAS

`ProceduralImageRenderer` est un **moteur schématique**. Il compose des
aplats, des dégradés, une forme-sujet et des repères, à partir de la palette,
du cadrage et de la densité décidés dans la `VisualBible`. Il ne dessine pas
un moteur électrique ; il dessine *où* le sujet se trouve, *quelle place* il
occupe, *comment* il est éclairé.

Pourquoi lui plutôt qu'un adaptateur de fournisseur : aucun service d'image
n'est joignable depuis cet environnement, et écrire un client qu'on ne peut
pas exécuter reviendrait à livrer une capacité fictive. Celui-ci tourne, et
produit des fichiers mesurables dont le 2.5D, l'observation et le montage ont
besoin pour fonctionner pour de bon.

Trois propriétés qui comptent plus que le réalisme à ce stade :

* **déterministe** — même `ImageSpec`, mêmes octets ; graine dérivée du plan ;
* **calqué** — un fichier RGBA par calque, ce que le parallaxe exige ;
* **conforme à la bible** — palette, cadrage, densité, position du sujet.

## TESTS

13 tests, dont : le composite s'ouvre à la résolution demandée ; un fichier
par calque déclaré ; les calques portent un canal alpha ; l'empreinte
enregistrée correspond au fichier ; deux rendus donnent les mêmes octets ; une
graine différente donne une image différente ; **la palette de la bible se
retrouve dans les pixels** ; un gros plan occupe plus de cadre qu'un plan
large ; déplacer le sujet déplace son barycentre.

```
$ pytest pdz2/tests -q   →  619 passed
$ ruff check pdz2/       →  All checks passed!
```

## LIMITATIONS

* Le rendu est schématique, pas photoréaliste. C'est dit dans le module, dans
  le nom de la classe, et ici.
* Aucun adaptateur de fournisseur d'image n'existe : le réseau les rend
  injoignables et un client invérifiable serait une capacité fictive.

## NEXT STEP

Phase 6 — MotionProgram (fait en phase 4) + port fournisseur vidéo et routeur
de stratégie de rendu.
