# Pronotedz

**Mon agent IA perso qui fabrique des vidéos courtes (TikTok / Reels / Shorts).**

Ce n'est pas une application pour des clients. C'est un outil, pour moi, qui tourne
sur ma machine.

> **État : construction en cours.** Projet Python autonome — pas de n8n,
> pas d'outil de rendu payant. Tout est fait sur mesure.

## Ce qu'il sait faire

**Plusieurs formats, un seul système.** Un univers par niche, autant que je veux.

| Format | Exemple | Coût |
|---|---|---|
| ⭐ **Narration + images générées** | une histoire racontée en voix off | **0,17 €** |
| **Série animée** | des fruits qui se trahissent | 1,56 € |
| **Style anime, mon histoire** | ambiance shonen 90s, mes personnages | 1,56 € |
| **Narration sur métrage** | domaine public, banques libres, mes images | 0,15 € |

Dans tous les cas : il écrit, **me fait valider**, fabrique les images, la voix, les
sous-titres, monte, et vérifie. Les séries gardent leurs personnages identiques d'un
épisode à l'autre.

## Comment je m'en sers

```bash
pdz univers creer "Fruit Island"              # les personnages, une fois
pdz episode "Strawberina trahit Bananito"     # série animée
pdz raconter "l'histoire du type qui a vendu Bitcoin en 2011"
pdz list
```

Plus une petite page web locale pour valider les scripts et regarder les vidéos.

## Documentation

| Doc | Contenu |
|---|---|
| 👉 [10 — Plan](./docs/10-plan.md) | **Par quoi on commence. À lire en premier.** |
| [01 — Ce que ça fait](./docs/01-comment-ca-marche.md) | Les 3 parcours du produit |
| [02 — Faisabilité](./docs/02-faisabilite.md) | Ce qui est mesurable, ce qui ne l'est pas |
| [03 — Le template n8n](./docs/03-le-template-n8n.md) | Ce qu'on en garde, l'erreur à ne pas répéter |
| [05 — Les agents](./docs/05-les-agents.md) | Les 18 spécialistes IA |
| [06 — Solidité](./docs/06-solidite.md) | Reprise après plantage, cache, erreurs, prompts |
| [07 — Budget](./docs/07-budget.md) | Le coût par vidéo et par mois |
| [08 — Tenir le rythme](./docs/08-volume.md) | 120 vidéos/mois sans y passer ses journées |
| [09 — Les fichiers](./docs/09-les-fichiers.md) | L'arborescence du projet |
| ⭐ [11 — État de l'art](./docs/11-etat-de-lart.md) | Ce que font les autres, les chiffres 2026 |
| ⭐⭐ [12 — Vidéos à personnages](./docs/12-videos-a-personnages.md) | Séries animées : univers, personnages, constance |
| ⭐⭐ [13 — Les formats](./docs/13-les-formats.md) | **Les 4 formats, leur coût, leur risque. Par quoi commencer** |

📦 [`docs/archive/`](./docs/archive/) — versions écartées (SaaS multi-clients, SaaS
Lovable/Supabase, outil Python en ligne de commande). **À ignorer.**

## En bref

| | |
|---|---|
| **Tourne sur** | Ma machine, avec Docker |
| **Langage** | Python — **pas de n8n** |
| **Base de données** | SQLite — un seul fichier |
| **Montage vidéo** | FFmpeg — **autant de plans que je veux, 0 €** |
| **Cerveau** | Claude (Sonnet + Haiku) |
| **Images** | FLUX via fal.ai |
| **Voix** | ElevenLabs |
| **Animation** | Kling 3.0 / Veo 3.1 en image-to-video |
| **Objectif** | 30 épisodes animés **+** 80 vidéos narrées par mois |
| **Coût** | 0,17 € à 1,56 € selon le format · **~83 €/mois** |
