# Phase 14 — Reprise après interruption

## LE CAS QUE LA MACHINE NE SAVAIT PAS DÉFAIRE

Un processus tué **pendant** une étape — Ctrl-C, mémoire épuisée, conteneur
repris, ce qui est le mode de vie normal de cet environnement — laisse cette
étape `RUNNING` sur le disque.

```
$ pdz2 script --episode ep/     # tué au milieu
$ pdz2 script --episode ep/
étape refusée : script tourne déjà
```

Et il n'y avait rien à faire. L'épisode restait bloqué pour toujours : aucune
méthode de la machine à états ne savait défaire cet état.

## POURQUOI PAS `rewind()`

Mécaniquement, il aurait marché. Mais c'est l'outil du Repair Compiler :

* il **consomme un cycle** du budget de réparation, plafonné — quelques
  plantages auraient épuisé la marge dont un vrai échec a besoin ;
* il remet aussi **tout l'aval** en attente, alors que l'aval n'a jamais
  démarré.

Une interruption n'est pas une réparation. Confondre les deux ferait payer un
plantage machine sur le budget prévu pour les échecs de rendu.

## TROIS VERBES, TROIS SITUATIONS

```
recover()   une interruption   → l'étape redevient démarrable, gratuitement
rewind()    une réparation     → l'étape et son aval, un cycle consommé
abandon()   un renoncement     → l'épisode est clos
```

Les tests fixent la frontière, notamment `recover()` appelé trois fois de
suite sur un épisode à deux cycles maximum : `repair_cycles` reste à zéro.

## CE QUE LA REPRISE OUBLIE VOLONTAIREMENT

Les artefacts déjà écrits par l'étape interrompue sont effacés de son état :
on ne sait pas s'ils sont complets. L'étape repart de zéro.

La transition, elle, **reste au journal** :

```
research   running → pending   « conteneur repris »
```

Une reprise silencieuse effacerait la trace de ce qui s'est passé. Le journal
de production la reprendra, et six mois plus tard on saura que cet épisode a
été interrompu.

## COMMANDE

```
$ pdz2 state recover ep/
  script : en cours → en attente

1 étape(s) redémarrable(s). Les artefacts qu'elles avaient commencés sont
oubliés : on ne sait pas s'ils sont complets.
```

Sur un épisode sain, elle ne touche à rien et le dit.

## TESTS — 12

Le blocage d'origine (3), la reprise (6), l'aller-retour complet par le disque
comme le ferait un nouveau processus qui ne connaît que le dossier (2), et le
refus d'une reprise sans motif (1).
