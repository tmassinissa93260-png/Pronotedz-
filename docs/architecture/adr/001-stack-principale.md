# ADR-001 — Stack principale : Python/FastAPI + Next.js

**Statut** : Proposé · **Date** : 2026-08-05

## Contexte

Le système fait beaucoup de traitement média (ffmpeg, whisper, librosa, détection de
scènes), beaucoup d'appels à des modèles IA, et expose une UI temps réel.

## Options

**A. Tout TypeScript** (Next.js + NestJS + BullMQ)
Un seul langage, types partagés, écosystème n8n homogène.
Mais : l'écosystème média/IA Python (faster-whisper, librosa, PySceneDetect, pgvector,
scikit) n'a pas d'équivalent sérieux en JS. On finirait par appeler des binaires Python
depuis Node — le pire des deux mondes.

**B. Tout Python** (FastAPI + HTMX/Reflex)
Cohérent côté traitement, mais l'UI temps réel demandée (timeline live, gates d'édition,
visualisation d'ADN) serait nettement plus laborieuse à construire.

**C. Hybride : Python côté backend/agents, TypeScript côté frontend** ✅

## Décision

Option C. Python 3.12 pour `api`, `worker`, `renderer` et toutes les `libs`.
TypeScript pour `web` et `packages`.

La frontière est nette et unique : l'OpenAPI de FastAPI, depuis lequel le SDK TypeScript
est **généré**. Aucun DTO n'est écrit deux fois, donc aucune dérive de types possible.

## Conséquences

**Positif** — accès direct à l'écosystème média/IA Python ; Pydantic v2 donne une
validation stricte alignée avec les sorties structurées de LLM ; le typage bout-en-bout
est préservé via la génération de SDK.

**Négatif** — deux toolchains (`uv` + `pnpm`), deux CI, deux cultures de test ; un
développeur unique doit être à l'aise dans les deux.

**Mitigation** — un `justfile` unifie les commandes (`just dev`, `just test`, `just lint`)
pour que la double toolchain reste invisible au quotidien.
