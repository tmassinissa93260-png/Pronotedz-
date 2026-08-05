# ADR-004 — Moteur de rendu : FFmpeg + libass

**Statut** : Proposé · **Date** : 2026-08-05

## Contexte

Il faut assembler images, voix, musique et sous-titres karaoké en un MP4 9:16, avec
mouvement, transitions et burn-in du texte.

## Options

**A. Remotion** (composition vidéo en React)
✅ De loin la meilleure expérience de développement : animations, itération visuelle,
sous-titres animés triviaux.
❌ **Licence** : gratuit pour les individus et les entreprises de ≤ 3 personnes en usage
interne ; un SaaS commercial requiert une Company License payante — incompatible avec
80 €/mois. Et le rendu passe par Chromium headless : ~3× plus de RAM et de CPU que ffmpeg.

**B. Creatomate / Shotstack** (API de rendu)
✅ Zéro infrastructure. ❌ 40–100 €/mois, soit 50 à 125 % du budget total.

**C. MoviePy**
✅ Python, simple. ❌ Lent, mono-thread, mal maintenu, gourmand en mémoire sur les
compositions longues.

**D. FFmpeg + libass, piloté depuis Python** ✅

## Décision

Option D pour la v1, **derrière une interface `RenderEngine`** qui permet de brancher
Remotion en v2 sans toucher au pipeline.

Techniques employées :
- Ken Burns via `zoompan` (le mouvement est ce qui distingue une vidéo d'un diaporama).
- Sous-titres karaoké mot à mot en ASS (`\k` tags) — libass les rend nativement.
- Transitions via `xfade`.
- `loudnorm` pour normaliser à −14 LUFS.
- Coupes alignées sur le beat à partir des données de l'`AudioAgent`.
- Rendu segmenté et mis en cache : re-render de sous-titres sans réencoder la vidéo.

## Conséquences

**Positif** — 0 € de licence, empreinte mémoire faible (~500 Mo/rendu contre ~1,5 Go pour
Chromium), rapide (~45 s pour 30 s de vidéo sur 4 vCPU dédiés), déterministe et testable
par comparaison de frames.

**Négatif** — les `filter_complex` deviennent illisibles au-delà d'une certaine complexité ;
un builder Python typé est indispensable, pas optionnel. Les animations restent moins
riches que ce que permet Remotion.

**Seuil de bascule** — passer à Remotion quand les revenus dépassent ~2 k€/mois ET que
les animations deviennent un facteur de différenciation produit.
