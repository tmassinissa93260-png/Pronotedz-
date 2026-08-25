# ADR-0009 — Le journal se relit, il ne s'écrit pas

**Statut** : accepté — phase 12
**Date** : 2026-08-23

## Contexte

Le §45 demande qu'un épisode puisse être expliqué après coup : pourquoi cette
vidéo est-elle comme ça ? Quelles décisions, quelles dégradations, quels
constats non corrigés ?

La façon évidente de répondre est d'écrire un journal au fil de la production :
chaque moteur ajoute sa ligne quand il finit. C'est ce que fait presque tout le
monde, et c'est ce qu'on ne fera pas ici.

## Décision

Le `ProductionJournal` est **reconstruit** à la demande depuis le dossier
d'épisode. Il ne contient aucune information qui ne soit déjà dans un contrat
sur le disque.

| entrée | source |
| --- | --- |
| `DEGRADATION` | `render_spec_executable.degradations` |
| `FINDING` | `observation_report.checks` en échec, `temporal_plan.findings` |
| `REFUSAL` | `validation_report.issues` bloquantes, transitions `failed` |
| `DECISION` | `director_brief`, stratégie de chaque exécutable, étapes sautées |
| `SPEND` | transitions portant un coût |
| `CAPABILITY` | sonde de la phase 11, datée |
| `LIMITATION` | ce que la chaîne sait ne pas savoir faire |

## Justification

Un journal tenu au fil de l'eau **diverge** de la production dès la première
reprise. Une étape rejouée, un contrat remplacé par un descendant, un
processus interrompu puis relancé : le récit ne correspond plus aux fichiers.
Il faut alors choisir à qui faire confiance — et un journal auquel on ne fait
pas confiance ne sert à rien. Pire : il sert à se tromper avec assurance.

Un journal reconstruit ne peut pas mentir. S'il dit qu'une dégradation a eu
lieu, c'est qu'elle est déclarée dans un contrat. Deux tests verrouillent la
propriété dans les deux sens : toute dégradation déclarée apparaît au journal,
et supprimer les contrats la fait disparaître du journal.

C'est le même raisonnement que la phase 2 sur la durée : la vérité vit dans
l'artefact, et tout le reste en est une **vue**.

## Conséquences

* Le journal n'a aucun coût pendant la production : rien à écrire, rien à
  synchroniser, aucun risque d'incohérence sur interruption.
* Il est rejouable : le même dossier donne le même journal.
* Il peut être enrichi après coup sans rejouer la production — brancher une
  nouvelle source d'entrées, c'est ajouter une lecture.
* En contrepartie, un événement qui n'atterrit dans **aucun** contrat est
  invisible au journal. C'est une contrainte utile : elle pousse à représenter
  les faits dans les contrats plutôt que dans des messages de log.

## Ce que le journal met sous les yeux

`unresolved` réunit constats, dégradations et limites — tout ce que personne
n'a corrigé. Sur l'épisode de référence : 15 points, dont trois limites
structurelles déclarées (style visuel non décidé, aucun timing de mot mesuré,
sous-titres calés au caractère).

C'est le seul endroit du système où un humain reçoit en un bloc ce que les
machines ont dû accepter.

    HUMANS JUDGE WHAT MACHINES CANNOT MEASURE
