# Pronotedz

**Mon agent IA perso qui fabrique des vidéos courtes (TikTok / Reels / Shorts).**

Ce n'est pas une application pour des clients. C'est un outil, pour moi, qui tourne
sur ma machine.

> **État : construction en cours.** Projet Python autonome — pas de n8n,
> pas d'outil de rendu payant. Tout est fait sur mesure.

## Ce qu'il sait faire

**Des séries animées à personnages récurrents.** Des fruits qui jouent une histoire,
des légumes au bureau, des animaux de la ferme — un univers par niche.

1. Je définis un **univers** une fois : les personnages, leurs voix, leur caractère, le décor.
2. Je demande un épisode → il écrit les dialogues, me les fait valider.
3. Il fabrique les plans en gardant **mes personnages identiques** d'un plan à l'autre.
4. Il anime ce qui doit bouger, laisse fixe ce qui peut l'être — c'est ce qui tient le budget.
5. Il monte, ajoute les voix, les bruitages et les sous-titres.
6. L'épisode suivant **se souvient** du précédent.

## Comment je m'en sers

```bash
pdz univers creer "Fruit Island"        # les personnages, une fois
pdz episode "Strawberina trahit Bananito"
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
| ⭐⭐ [12 — Vidéos à personnages](./docs/12-videos-a-personnages.md) | **LE vrai projet : séries animées. Remplace la direction des docs 01/05/07/08** |

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
| **Objectif** | **~1 épisode par jour, 30 à 45 s** |
| **Coût** | ~1,00 à 1,56 € par épisode · **~80 €/mois** |
