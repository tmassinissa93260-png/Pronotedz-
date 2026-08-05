# Pronotedz

**Mon agent IA perso qui fabrique des vidéos courtes (TikTok / Reels / Shorts).**

Ce n'est pas une application pour des clients. C'est un outil, pour moi, qui tourne
sur ma machine.

> État : conception validée à 80 %. Pas encore de code.

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

Et une petite page web sur `localhost:7777` pour valider les scripts et regarder
les vidéos — parce que valider un script dans un terminal, c'est pénible.

## Documentation

| Doc | Contenu |
|---|---|
| [01 — Comment ça marche](./docs/01-comment-ca-marche.md) | Le schéma global, les 3 parcours |
| [02 — Les agents](./docs/02-agents.md) | Les 18 agents et ce que fait chacun |
| [03 — Les fichiers](./docs/03-fichiers.md) | L'arborescence du projet |
| [04 — Ce qui rend ça solide](./docs/04-solidite.md) | Reprise, cache, erreurs, prompts, modèles |
| [05 — Budget](./docs/05-budget.md) | Où passent les 80 €/mois |
| [06 — Plan](./docs/06-plan.md) | Par quoi on commence |
| [07 — Tenir le rythme](./docs/07-volume.md) | Produire 120 vidéos/mois sans y passer ses journées |

📦 [`docs/saas-plus-tard/`](./docs/saas-plus-tard/) — l'architecture SaaS complète
(multi-clients, facturation, montée en charge). Gardée au cas où tu voudrais en faire
un produit un jour. **À ignorer pour l'instant.**

## En bref

| | |
|---|---|
| **Tourne sur** | Ma machine, avec Docker. (Ou un petit serveur à 5 €/mois si je veux qu'il bosse la nuit.) |
| **Langage** | Python |
| **Base de données** | SQLite — un seul fichier |
| **Montage vidéo** | FFmpeg |
| **Interface** | Ligne de commande + une page web locale |
| **Cerveau** | Claude (Sonnet + Haiku) |
| **Images** | FLUX via fal.ai |
| **Voix** | ElevenLabs |
| **Objectif** | **120 vidéos/mois, 1 à 2 min** |
| **Agents** | 18 spécialistes, dont Script Critic, Hook Optimizer et Psychology |
| **Coût** | ~0,20 € par vidéo · **49 €/mois** sur les 80 € |
