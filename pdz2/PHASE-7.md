# Phase 7 — 2.5D et procédural

## CURRENT STATE

`pdz2 render` produit de **vraies vidéos H.264**. Sur un épisode de test :
4 plans, 523 images composées, 17,4 s de vidéo en 1080×1920, sans le moindre
fournisseur.

## LES QUATRE STRATÉGIES

| Stratégie | Ce qu'elle fait |
| --- | --- |
| `STILL` | une image, répétée. Rien ne bouge, et c'est assumé. |
| `KEN_BURNS` | recadrage progressif sur l'image composite. |
| `PARALLAX_2_5D` | chaque calque se décale selon sa profondeur. |
| `PROCEDURAL` | parallaxe, plus rotation ou orbite du sujet. |

Toutes suivent la même mécanique : lire les calques de la phase 5,
échantillonner le `MotionProgram` image par image, composer, encoder. **Le
mouvement vient du `MotionProgram`, jamais d'une phrase** — il n'y a personne
à qui parler.

## LA GRAMMAIRE DE MOUVEMENT DEVIENT DES PIXELS

`renderers/motion_paths.py` évalue les dix primitives du contrat : `STATIC`,
`LINEAR`, `ARC`, `ORBIT`, `OSCILLATE`, `SPIRAL`, `ROTATE`, `SCALE`, `FLOW`,
`JITTER`, avec cinq courbes d'accélération. Un test vérifie que **toute
primitive du contrat est évaluable** : une primitive déclarée sans calcul
derrière serait une promesse vide.

## PERFORMANCE — DEUX CORRECTIONS MESURÉES

1. **Redimensionner le calque entier à chaque image** coûtait ~30 s par plan.
   `Image.resize(box=…)` recadre et redimensionne en une passe, à la taille de
   sortie directement.
2. **Écrire un PNG par image puis le relire** coûtait plus que l'encodage
   lui-même. Les images brutes RGB passent maintenant dans l'entrée standard
   de ffmpeg — plus de compression intermédiaire, plus d'allers-retours
   disque.

Un défaut de câblage a été trouvé au passage : `communicate()` tentait de
vider une entrée déjà fermée. On attend et on lit la sortie d'erreur à la main.

## TESTS

22 tests, dont : le fichier contient réellement ce qui a été demandé (codec,
dimensions, cadence, durée, absence de piste audio) ; l'empreinte enregistrée
correspond au fichier ; **une stratégie animée change réellement l'image**
entre la première et la dernière frame (mesuré par différence de pixels) ; une
stratégie fixe ne bouge pas ; toute primitive du contrat est évaluable.

```
$ pytest pdz2/tests -q   →  660 passed
```

## LIMITATIONS

* **Le rendu est lent** : ~10 s par seconde de vidéo en 1080×1920 pour le
  parallaxe à quatre calques. Acceptable pour un format court, à revoir si la
  durée cible augmente.
* Le parallaxe est un décalage de calques plats, pas une reprojection 3D. Un
  décalage trop fort révèle la platitude ; `MAX_PARALLAX_SHIFT` le borne.
* **Dépendance système `ffmpeg`.** Absent, les renderers se déclarent
  injoignables avec la raison et l'étape échoue avec un motif.

## NEXT STEP

Phase 8 — observateur déterministe : mesurer ce qui est réellement sorti.
