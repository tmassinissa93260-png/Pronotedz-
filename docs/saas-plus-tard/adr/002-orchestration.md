# ADR-002 — Orchestration : moteur maison + n8n en périphérie

**Statut** : Proposé · **Date** : 2026-08-05
**C'est la décision la plus structurante du projet, et celle qui s'écarte le plus de la demande initiale.**

## Contexte

La demande explicite des « workflows n8n indépendants ». Le système doit tenir des
milliers d'utilisateurs, avec des pipelines de 10–15 étapes, des attentes humaines de
plusieurs heures, du fan-out parallèle, de la reprise fine et un contrôle strict du coût.

## Options

### A — Tout dans n8n
✅ Rapide à démarrer, très visuel, modifiable sans déploiement, écosystème d'intégrations énorme.
❌ Une exécution longue par job en mémoire ; la table `execution_entity` grossit vite ;
la reprise ne connaît pas la notion d'artefact déjà produit (on repaye les étapes) ;
tests automatisés quasi impossibles sur du JSON ; fan-out avec budget/retry par branche
illisible ; pas de contrôle fin des coûts par appel.

### B — Temporal
✅ La référence en exécution durable : reprise, timers, signaux (parfait pour les gates HITL), versionnement des workflows.
❌ Temporal Cloud ~90 €/mois — hors budget. Auto-hébergé : Cassandra/PostgreSQL + 4
services, charge d'exploitation supérieure à tout le reste du système réuni.

### C — Moteur de pipeline maison sur PostgreSQL + ARQ, n8n en périphérie ✅
✅ Contrôle total sur les checkpoints, le budget par étape, le cache par `input_hash`.
Testable comme du code ordinaire. Coût d'infrastructure nul. n8n conservé là où il excelle.
❌ Code à écrire et à maintenir (~400–600 lignes pour le moteur). Pas de garanties formelles d'exécution durable.

## Décision

Option C.

**Frontière** :
- **Backend** : pipelines de génération (fort volume, latence critique, fan-out, budget).
- **n8n** : intégrations tierces, notifications, gates HITL (`Wait` node sur webhook —
  cas d'usage où n8n est objectivement supérieur), crons de maintenance, workflows métier
  à faible volume, prototypage de nouveaux pipelines.

**Règle inviolable** : n8n ne détient aucun état. Chaque nœud actif appelle
`apps/api` en HTTP avec une `Idempotency-Key`. Rejouer un workflow n8n ne duplique rien.

**File** : ARQ (Redis, async, léger) plutôt que Celery — nos étapes sont majoritairement
I/O-bound (attente de réponses de modèles), un worker async à concurrence 50 les absorbe
là où Celery consommerait 50 processus. Les étapes CPU-bound (ffmpeg, whisper) vont sur
une file dédiée à concurrence 2.

## Conséquences

**Positif** — reprise réellement fine (au niveau étape, avec artefacts réutilisés) ;
pipelines testables unitairement ; coût maîtrisé au niveau de l'appel ; n8n reste utile
et le lien avec l'écosystème d'intégrations est préservé.

**Négatif** — le moteur est du code à écrire, tester et maintenir ; la vision d'ensemble
d'un pipeline est répartie entre code et n8n (mitigé par WF-01, qui documente visuellement
le pipeline principal).

**Chemin de sortie** — si les besoins de durabilité deviennent critiques (> 10 types de
pipelines, exigences de garantie d'exécution), le moteur est remplaçable par Temporal :
`libs/core/pipeline/engine.py` est l'unique point de contact, les agents ne changent pas.

## Ce qui invaliderait cette décision

Si, après la phase 1, il apparaît que les pipelines changent plusieurs fois par semaine
pour des raisons métier et que personne ne touche au code Python, alors n8n devrait
reprendre plus de terrain. À réévaluer à la fin de la phase 2.
