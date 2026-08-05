# Pronotedz — Architecture (v0.1, à valider)

> **Statut : PROPOSITION — aucune ligne de code applicatif n'est écrite tant que ce document n'est pas validé.**

SaaS de génération automatique de vidéos courtes (TikTok / Reels / Shorts) avec
extraction et transfert d'**ADN viral**, validation humaine et publication multi-réseaux.

## Contrainte structurante

**Budget abonnements : 80 €/mois.** Cette contrainte n'est pas un détail : elle
élimine Vercel Pro, n8n Cloud, Temporal Cloud, Creatomate, la licence entreprise
Remotion et les plans managés Supabase/Sentry. Toute l'architecture ci-dessous est
conçue pour tenir dans 80 €/mois **en auto-hébergé sur Hetzner**, tout en gardant
des interfaces qui permettent de basculer vers du managé sans réécriture.
Voir [`10-budget.md`](./10-budget.md).

## Table des matières

| # | Document | Contenu |
|---|---|---|
| 00 | [Vision & principes](./00-vision-principes.md) | Objectifs, principes directeurs, non-objectifs |
| 01 | [Architecture globale](./01-architecture-globale.md) | Vue C4, couches, frontières, flux |
| 02 | [Structure du projet](./02-structure-projet.md) | Arborescence monorepo commentée |
| 03 | [Agents spécialisés](./03-agents.md) | 18 agents, contrat commun, ADN viral |
| 04 | [Workflows n8n](./04-workflows-n8n.md) | 17 workflows indépendants + règle de frontière |
| 05 | [Données & mémoire](./05-donnees-memoire.md) | Schéma PostgreSQL, 5 types de mémoire, pgvector |
| 06 | [Prompts & modèles IA](./06-prompts-modeles.md) | Registry de prompts versionnés, model registry |
| 07 | [Fiabilité](./07-fiabilite.md) | Erreurs, retry, reprise automatique, checkpoints |
| 08 | [Cache](./08-cache.md) | 5 niveaux de cache, adressage par contenu |
| 09 | [Observabilité](./09-observabilite.md) | Logs, traces, métriques, coûts |
| 10 | [Budget](./10-budget.md) | Ventilation 80 €/mois + coût unitaire par vidéo |
| 11 | [APIs & dépendances](./11-apis-dependances.md) | Fournisseurs externes, librairies, versions |
| 12 | [Risques](./12-risques.md) | Registre de risques avec mitigations |
| 13 | [Améliorations & évolutions](./13-evolutions.md) | Dette assumée, roadmap v1 → v4 |
| — | [ADR](./adr/) | Décisions d'architecture tracées |

## Résumé exécutif en 10 lignes

1. **Monorepo** : `apps/` (web, api, worker, renderer) + `libs/` Python partagées + `orchestration/n8n`.
2. **Frontend** Next.js 15, **backend** FastAPI, **workers** ARQ/Redis, **render** FFmpeg+libass.
3. **PostgreSQL 16 + pgvector** = source de vérité unique. Redis = file + cache. Cloudflare R2 = artefacts.
4. **n8n orchestre, n8n ne stocke jamais l'état.** Tout état vit en base ; chaque nœud est idempotent.
5. **18 agents** derrière un contrat unique (`AgentSpec`), sans dépendance directe à un fournisseur.
6. **Model Registry déclaratif** : ajouter un modèle IA = ajouter 15 lignes de YAML, zéro code.
7. **Prompt Registry versionné** (semver + hash + éval de non-régression) découplé du code.
8. **Reprise automatique** par checkpoints par étape + artefacts adressés par contenu : un re-run ne repaye jamais deux fois.
9. **Validation humaine** modélisée comme des *gates* first-class, avec expiration et politique de repli.
10. **Coût unitaire cible : 0,05 à 0,30 € par vidéo de 30 s** — vérifié en [10-budget.md](./10-budget.md).

## Ce que j'ai changé par rapport à la demande initiale

Trois écarts assumés, argumentés dans les documents concernés :

- **n8n n'est pas le moteur d'orchestration principal** ([04](./04-workflows-n8n.md), [ADR-002](./adr/002-orchestration.md)).
  À l'échelle « milliers d'utilisateurs », n8n devient le goulot d'étranglement et
  rend le test automatisé quasi impossible. n8n reste — mais sur son terrain fort :
  intégrations, workflows métier à itération rapide, ops. Le moteur durable est côté backend.
- **Pas de Remotion en v1** ([ADR-004](./adr/004-moteur-rendu.md)) : la licence entreprise
  est incompatible avec 80 €/mois. FFmpeg + libass derrière une interface `RenderEngine`.
- **L'ingestion TikTok est le risque n°1 du projet**, pas une tâche technique
  ([12-risques.md](./12-risques.md#r1)). Elle conditionne la faisabilité légale de la feature 2/3/4.

## Prochaine étape

Valider ou amender ce document. Les points qui demandent **explicitement une décision**
sont listés dans [`DECISIONS-A-PRENDRE.md`](./DECISIONS-A-PRENDRE.md).
