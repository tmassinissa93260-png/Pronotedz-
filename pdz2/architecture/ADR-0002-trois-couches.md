# ADR-0002 — Trois couches, et l'ABI qui les sépare

**Statut** : accepté — phase 0
**Date** : 2026-08-22

## Contexte

L'échec classique d'un système de production vidéo est le mélange de trois
choses : *pourquoi* un plan existe, *ce qu'on demande* au rendu, et *ce que
l'infrastructure sait faire*. Quand elles se mélangent, un changement de
fournisseur devient une réécriture, et une dégradation devient invisible.

## Décision

Trois couches, un seul langage commun (les contrats).

1. **NARRATIVE INTENT** — `TopicRequest`, `ResearchState`, `Claim`, `FactGraph`,
   `DirectorState`, `AnchorSpec`, `ShotIntent`, `ScriptState`. Aucune notion de
   fournisseur, de modèle, de résolution, de fps, de coût ou de stratégie.
2. **RENDER SPECIFICATION** — `ShotSpec`, `VisualBible`, `ImageSpec`,
   `MotionProgram`, `CameraProgram`, `RenderSpecRequested`. Ce qui est demandé,
   en termes physiques et mesurables, toujours sans nommer de fournisseur.
3. **EXECUTION** — `RenderSpecExecutable`, `ExecutionPlan`, `RenderArtifact`,
   `ObservationReport`. Ce qui sera et ce qui a été réellement fait.

La frontière 2 → 3 est l'**ABI de rendu** :

```
RenderSpecRequested ──► StaticValidator ──► RenderSpecExecutable ──► ExecutionPlan ──► Renderer
```

`RenderSpecExecutable` embarque un **écho** de la demande (`RequestedEcho`) :
caméra, durée, résolution, fps, stratégie préférée. Le contrat compare l'écho à
ce qui sera exécuté, et **refuse tout écart non déclaré** en `Degradation`. Une
dégradation porte quatre choses : le champ, le demandé, l'exécuté, et la raison
— *pourquoi l'infrastructure ne peut pas*.

## Alternatives écartées

* **Un seul objet « plan » traversant tout le système.** Rejeté : c'est
  exactement ce qui rend un changement de fournisseur impossible.
* **Dégradation implicite dans le routeur.** Rejeté : une dégradation qui
  n'apparaît pas dans un contrat n'apparaît nulle part.

## Vérification

`pdz2/tests/test_layering.py` échoue si un champ d'exécution entre dans un
contrat narratif, si un champ narratif entre dans `RenderSpecExecutable`, ou si
une marque de fournisseur apparaît dans le cœur.
