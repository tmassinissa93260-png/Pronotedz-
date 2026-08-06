# Pronotedz

**Mon agent IA perso qui fabrique des vidéos courtes (TikTok / Reels / Shorts).**

Ce n'est pas une application pour des clients. C'est un outil, pour moi, qui tourne
sur ma machine.

> **État : construction en cours.** Projet Python autonome — pas de n8n,
> pas d'outil de rendu payant. Tout est fait sur mesure.

## Ce qu'il sait faire

1. Je lui donne une idée → il me sort une vidéo montée, avec voix et sous-titres.
2. Je lui donne une vidéo TikTok qui marche → il analyse pourquoi elle marche.
3. Il en extrait la « recette » (le rythme, la structure, le ton, les coupes).
4. Il applique cette recette à **mon** sujet, complètement différent.
5. Il me demande mon avis aux moments clés — je valide ou je corrige.
6. Il me prépare le texte et les hashtags à coller pour publier.

## Comment je m'en sers

```bash
pdz new "3 erreurs que font tous les débutants en muscu"
pdz analyze ~/Downloads/video-virale.mp4
pdz remix <recette> "les erreurs en cuisine"
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
| **Objectif** | **120 vidéos/mois, 1 à 2 min, pour moi** |
| **Coût** | ~0,20 € par vidéo · **~43 €/mois tout compris** |
