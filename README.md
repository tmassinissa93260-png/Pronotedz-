# Pronotedz

**Mon agent IA perso qui fabrique des vidéos courtes (TikTok / Reels / Shorts).**

Ce n'est pas une application pour des clients. C'est un outil, pour moi, qui tourne
sur ma machine.

> **État : la chaîne complète tourne.** Projet Python autonome — pas de n8n,
> pas d'outil de rendu payant. Tout est fait sur mesure.
>
> 👉 **[Comment l'installer sur ta machine](./INSTALLER.md)**
> 📱 **[Pas d'ordinateur ? Le faire tourner depuis ton téléphone](./TELEPHONE.md)**

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

**Il sait aussi partir d'une vidéo que j'aime** : mesurer son style, en tirer des
personnages jouables et retrouver des voix qui ressemblent aux siennes — sans en
recopier ni le sujet ni les personnages. Voir
[14 — Reproduire un style](./docs/14-reproduire-un-style.md).

## Comment je m'en sers

```bash
pdz cles                                   # tout est branché ?
pdz univers                                # mes mondes

# Partir d'une vidéo de référence
pdz analyser ma-reference.mp4              # mesures + ADN — 0 €
pdz charte ma-reference.mp4 --id mon-monde # style + personnages → univers/
pdz voix apparier mon-monde --source ma-reference.mp4

# Produire
pdz episode fruit-island "Strawberina trahit Bananito"
pdz episode mon-monde "une dispute" --forme str_a1b2c3d4

# Reconnaître la musique d'une vidéo
pdz musique ma-video.mp4

# Suivre
pdz jobs · pdz reprendre <job> · pdz cout · pdz web

# Savoir ce qui marche, sur MON catalogue
pdz resultats publie <job> --url ...
pdz resultats importer export-tiktok.csv
pdz resultats bilan
```

`pdz reprendre` finit une production interrompue **sans repayer** ce qui est déjà
fait. Plus une petite page web locale pour valider les scripts et revoir les vidéos.

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
| ⭐⭐ [14 — Reproduire un style](./docs/14-reproduire-un-style.md) | **Mesurer le visuel, les personnages et les voix d'une vidéo pour en refaire du même genre** |
| ⭐ [15 — Musique et résultats](./docs/15-musique-et-resultats.md) | **Reconnaître la musique de fond ; et pourquoi les outils qui « expliquent » une vidéo virale n'en expliquent aucune** |

### Architecture

| Doc | Contenu |
|---|---|
| 👉 [MIGRATION_PLAN](./docs/MIGRATION_PLAN.md) | **Ce qui a été construit, phase par phase, et pourquoi** |
| [SOURCE_OF_TRUTH](./docs/SOURCE_OF_TRUTH.md) | Qui fait autorité sur quoi — avant et après |
| [TARGET_ARCHITECTURE](./docs/TARGET_ARCHITECTURE.md) | Le compilateur audiovisuel — la cible |
| [CURRENT_ARCHITECTURE](./docs/CURRENT_ARCHITECTURE.md) | La photographie de départ *(document d'époque)* |
| [GAP_ANALYSIS](./docs/GAP_ANALYSIS.md) | L'écart mesuré, et son solde *(document d'époque)* |

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
