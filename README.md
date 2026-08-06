# Pronotedz

**Mon agent IA perso qui fabrique des vidéos courtes (TikTok / Reels / Shorts).**

Ce n'est pas une application pour des clients. C'est un outil, pour moi, qui tourne
sur ma machine.

> État : le système de base tourne déjà sur n8n. Reste 3 briques à ajouter.

## Ce qu'il sait faire

1. Je lui donne une idée → il me sort une vidéo montée, avec voix et sous-titres.
2. Je lui donne une vidéo TikTok qui marche → il analyse pourquoi elle marche.
3. Il en extrait la « recette » (le rythme, la structure, le ton, les coupes).
4. Il applique cette recette à **mon** sujet, complètement différent.
5. Il me demande mon avis aux moments clés — je valide ou je corrige.
6. Il me prépare le texte et les hashtags à coller pour publier.

## Où j'en suis

**Ce qui marche déjà** : mon workflow n8n complet — idée → recherche → script →
descriptions d'images → vidéo montée. Avec validation du script.

**Ce qui bloque** : mon gabarit de rendu a 4 emplacements fixes. Une vraie vidéo
TikTok en demande 18. Je peux analyser une structure, je ne peux pas l'appliquer.

**La suite** : trois briques à ajouter, ~2 semaines.
→ [04 — Ce qu'il faut changer](./docs/04-ce-quil-faut-changer.md)

## Documentation

| Doc | Contenu |
|---|---|
| 👉 [04 — Ce qu'il faut changer](./docs/04-ce-quil-faut-changer.md) | **Le plan concret sur mon n8n. À lire en premier.** |
| [01 — Ce que ça fait](./docs/01-comment-ca-marche.md) | Les 3 parcours du produit |
| [02 — Faisabilité](./docs/02-faisabilite.md) | Ce qui est mesurable, ce qui ne l'est pas |
| [03 — Mon système actuel](./docs/03-mon-systeme-actuel.md) | Analyse de mon workflow n8n : acquis, blocage, corrections |
| [05 — Les agents](./docs/05-les-agents.md) | Les spécialistes IA et ce que fait chacun |
| [06 — Solidité](./docs/06-solidite.md) | Reprise après plantage, cache, erreurs, prompts |
| [07 — Budget](./docs/07-budget.md) | Le coût par vidéo et par mois |
| [08 — Tenir le rythme](./docs/08-volume.md) | 120 vidéos/mois sans y passer ses journées |

📦 [`docs/archive/`](./docs/archive/) — versions écartées (SaaS multi-clients, SaaS
Lovable/Supabase, outil Python en ligne de commande). **À ignorer.**

## En bref

| | |
|---|---|
| **Automatisation** | n8n *(déjà en place)* |
| **Cerveau** | Claude — Sonnet + Haiku |
| **Montage vidéo** | Mon outil de rendu actuel, en mode API |
| **Mesure des vidéos** | Un petit service Python (~150 lignes) sur Modal |
| **Cerveau** | Claude (Sonnet + Haiku) |
| **Images** | FLUX via fal.ai |
| **Voix** | ElevenLabs |
| **Objectif** | **120 vidéos/mois, 1 à 2 min, pour moi** |
| **Coût** | ~0,20 € par vidéo · **~68 €/mois** hors outil de rendu |
