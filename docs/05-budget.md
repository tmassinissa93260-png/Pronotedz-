# 05 — Budget : 80 €/mois

> Les prix des IA bougent tous les 2-3 mois. Ce sont des ordres de grandeur à revérifier
> au moment de payer. Ce qui compte ici, c'est la **structure** du budget.

## La bonne nouvelle

Pour une seule personne, **80 €/mois c'est confortable**. Dans la version SaaS, presque
tout le budget partait dans les serveurs. Ici, il n'y a pas de serveur : tout tourne sur
ma machine. Donc **presque tout le budget part dans les IA** — c'est-à-dire dans la qualité.

Concrètement : je peux me payer la **configuration premium** partout.

## Où passent les 80 €

| Poste | Détail | €/mois |
|---|---|---|
| **Serveur** | aucun — ça tourne sur ma machine | **0,00** |
| **Base de données** | SQLite, un fichier | **0,00** |
| **Stockage** | mon disque dur | **0,00** |
| **ElevenLabs Creator** | belle voix, 100 000 caractères/mois ≈ 160 vidéos | 22,00 |
| **Sauvegarde cloud** | Backblaze B2 ou un disque externe | 2,00 |
| **Sous-total fixe** | | **24,00** |
| **Crédits IA à l'usage** | Claude + FLUX + Whisper | **56,00** |
| **TOTAL** | | **80,00** |

*(Si un jour je veux qu'il tourne la nuit sans laisser mon ordi allumé : +5 €/mois pour
un petit serveur Hetzner CX22. À prendre sur les crédits IA.)*

## Combien coûte une vidéo

### Configuration premium — 30 secondes, 8 scènes

| Étape | Avec quoi | Coût |
|---|---|---|
| Angle | Claude Haiku | 0,003 € |
| Script + accroches | Claude Sonnet | 0,026 € |
| Découpage visuel | Claude Haiku | 0,007 € |
| **8 images** | **FLUX dev** | **0,184 €** ← le plus gros poste |
| **Voix** | **ElevenLabs Turbo** | **0,090 €** |
| Musique | ma banque locale | 0,000 € |
| Sous-titres | libass | 0,000 € |
| Montage | FFmpeg sur ma machine | 0,000 € |
| Contrôle qualité | Claude Haiku vision | 0,006 € |
| Légende + hashtags | Claude Haiku | 0,003 € |
| **TOTAL** | | **≈ 0,42 €** |

### Configuration économique — si je veux tenir plus longtemps

FLUX schnell au lieu de dev, voix Kokoro locale, Haiku partout : **≈ 0,07 €**.
Six fois moins cher. La différence se voit surtout sur les images et la voix.

### Analyser une vidéo TikTok

| Étape | Coût |
|---|---|
| Transcription (Groq Whisper) | 0,001 € |
| Découpage + son (outils gratuits) | 0,000 € |
| Vision, 12 images clés (Haiku) | 0,018 € |
| Extraction de la recette (Sonnet) | 0,031 € |
| Nettoyage (Haiku) | 0,009 € |
| **TOTAL** | **≈ 0,06 €** |

Une recette est **réutilisable à l'infini** : je la paie une fois, je m'en sers 50 fois.

## Ce que je peux faire chaque mois

Avec 56 € de crédits :

| Ce que je fais | Nombre par mois |
|---|---|
| Tout en premium | **~133 vidéos** |
| Moitié premium, moitié éco | ~230 vidéos |
| Tout en économique | ~800 vidéos |
| Analyses de vidéos virales | ~930 |

**En pratique** : si je publie 1 vidéo par jour, ça fait 30 vidéos/mois → environ **13 €**.
Il me reste 43 € de marge pour rater des essais, refaire des vidéos, tester des prompts.

C'est très large. Le budget n'est pas la contrainte ici.

## Les 3 garde-fous (à câbler avant le premier appel payant)

1. **Plafond par vidéo** — 0,60 €. Au-delà, l'agent dégrade la qualité puis s'arrête.
2. **Plafond mensuel** — à 95 % des 80 €, il refuse de démarrer. `--force` pour passer outre.
3. **`max_tokens` toujours écrit en dur** sur chaque appel.
   Un `max_tokens` oublié est le bug le plus cher qui existe avec une API d'IA :
   une réponse qui part en boucle peut coûter plusieurs euros en une fois.

## Ce que je surveille le premier mois

- **Le coût réel par vidéo** contre les 0,42 € estimés ici. Un facteur 2 est plausible
  (essais ratés, régénérations). À vérifier dès la première semaine avec `pdz cost`.
- **Le nombre de régénérations par vidéo.** Si je refais 3 fois chaque vidéo,
  le coût réel est ×3 — et ça veut dire que les prompts sont à revoir, pas le budget.

## Si je veux dépenser moins

| Changement | Économie | Ce que je perds |
|---|---|---|
| Voix Kokoro locale au lieu d'ElevenLabs | **−22 €/mois fixes** −0,09 €/vidéo | voix correcte mais moins naturelle |
| FLUX schnell au lieu de dev | −0,16 €/vidéo (−38 %) | images un peu moins fines |
| Haiku au lieu de Sonnet pour le script | −0,02 €/vidéo | scripts nettement moins bons — **à ne pas faire** |

Le meilleur rapport qualité/prix : **garder Sonnet pour le script** (c'est ce qui fait
la vidéo) et économiser sur les images si besoin.
