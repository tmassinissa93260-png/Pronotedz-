# 06 — Par quoi on commence

## L'ordre compte

Le piège classique : passer 2 mois à construire un beau système, et découvrir à la fin
que les vidéos produites sont inregardables. On fait l'inverse.

---

## Étape 0 — Avant le code (2 à 3 jours) ⚠️ la plus importante

**Fabriquer 5 vidéos à la main, de 90 secondes.** Avec FFmpeg, des images générées à la main sur fal.ai,
une voix ElevenLabs, des sous-titres faits à la main.

Pourquoi c'est indispensable :
- Je vais découvrir en 3 jours ce qui fait qu'une vidéo « marche » ou pas.
- Ces 5 vidéos deviennent la référence : l'agent devra faire aussi bien.
- Je vais trouver 20 détails que je n'aurais jamais anticipés en théorie
  (la taille des sous-titres, la vitesse du zoom, où couper, la longueur des phrases).
- Si les vidéos faites à la main ne sont pas bonnes, **automatiser ne les rendra pas
  meilleures** — et il vaut mieux le savoir maintenant qu'après 2 mois de code.

Sortie de cette étape : 5 MP4 de 90 s + une note « voilà ce qui fait la différence ».

> ⚠️ **Fais-les en 90 secondes, pas en 30.** La difficulté d'une vidéo longue n'est pas
> d'accrocher, c'est de **garder** l'attention au milieu. Si tu ne testes ça qu'à la fin,
> tu vas construire un outil qui fait de bonnes vidéos de 30 s et de mauvaises de 90 s.

**À faire en parallèle** : ouvrir les comptes et récupérer les clés d'API
(Anthropic, fal.ai, Groq, ElevenLabs).

---

## Étape 1 — Le squelette qui marche (1 semaine)

**Objectif : une vraie vidéo, de bout en bout, en tapant une commande.**
Moche, mais complète et réelle.

- 6 agents seulement : angle, script, découpage, images, voix, montage.
- Le moteur avec les sauvegardes par étape (**dès le début** — c'est le socle de tout le reste).
- SQLite, cache par empreinte, `modeles.yaml`.
- **1 seule validation** : le script.
- Interface : ligne de commande uniquement.

Pas de recette virale, pas de page web, pas de musique, pas de sous-titres fancy.

✅ **Critère de réussite** : `pdz new "mon idée"` produit un MP4 que je trouve regardable.

---

## Étape 2 — La qualité vidéo (1 semaine)

C'est ici qu'on transforme un diaporama en vidéo.

- Zoom lent sur chaque image.
- **Réutilisation d'images** (1 image → 2 plans) + b-roll gratuit Pexels.
- Sous-titres karaoké mot à mot.
- Musique de fond + volume normalisé.
- Coupes calées sur le rythme.
- Contrôles automatiques : durée, images noires, son manquant.

✅ **Critère de réussite** : je compare avec mes 5 vidéos de l'étape 0.
Si c'est proche, on continue. Sinon, on reste ici — inutile d'aller plus loin.

---

## Étape 3 — La recette virale (1,5 semaine)

La partie qui rend l'outil vraiment intéressant.

- Les 5 agents d'analyse (transcription, découpage, vision, son, ingestion).
- L'agent recette + l'agent nettoyage.
- La bibliothèque de recettes, avec recherche.
- L'application d'une recette à un nouveau sujet.

✅ **Critère de réussite** : j'analyse 5 vidéos qui marchent, je génère 5 vidéos sur mes
sujets avec leurs recettes, et je vois clairement la différence avec une génération
sans recette.

---

## Étape 4 — Le mode volume (1,5 semaine)

- **La validation par lot** — 10 scripts sur un écran. C'est LA fonction qui rend 120 vidéos/mois tenable.
- **Le mode nuit** : `pdz batch build --nuit`, la machine monte pendant que je dors.
- **La file d'attente** : je remplis quand j'ai des idées, il consomme à son rythme.
- Le contrôle qualité bloquant (une vidéo ratée ne m'est jamais montrée).
- `pdz cost`, `pdz list`, `pdz resume`.
- Génération de la légende et des hashtags à coller.

---

## Étape 5 — Le peaufinage (en continu)

- Réglage des prompts en comparant les résultats.
- Optimisation du coût.
- Banque de musiques.
- Et si j'en ai envie : n8n pour publier automatiquement, ou un petit serveur pour que
  ça tourne la nuit.

---

## Résumé

| Étape | Durée | Ce que j'ai à la fin |
|---|---|---|
| 0 · À la main | 3 jours | Je sais ce qui fait une bonne vidéo |
| 1 · Squelette | 1 semaine | Une commande → une vidéo |
| 2 · Qualité | 1 semaine | Une vidéo que j'oserais publier |
| 3 · Recette | 1,5 semaine | Le vrai truc : copier la forme, pas le fond |
| 4 · Volume | 1,5 semaine | **120 vidéos/mois en ~2 h par semaine** |
| **Total** | **~5,5 semaines** | **Mon agent perso** |

Contre 12 semaines pour la version SaaS. **La simplification fait gagner 7 semaines.**

---

## Ce que je te conseille de faire cette semaine

1. **Ouvrir les comptes** : Anthropic, fal.ai, Groq, ElevenLabs. Mettre ~20 € de crédit
   pour commencer, pas plus.
2. **Faire l'étape 0.** Sérieusement. C'est 3 jours qui décident si le projet vaut le coup.
3. Me dire « go » pour l'étape 1.

Je ne commence à coder qu'à ton feu vert.
