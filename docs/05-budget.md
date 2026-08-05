# 05 — Budget : 80 €/mois pour 120 vidéos de 1 à 2 min

> Les prix des IA bougent tous les 2-3 mois. Ce sont des ordres de grandeur à revérifier
> au moment de payer. Ce qui compte, c'est la **structure** du budget et les leviers.

**Objectif** : 120 vidéos/mois, durée 60 à 120 s. Hypothèse de calcul : **90 s en moyenne**.

---

## 1. Ce qui change quand on passe de 30 s à 90 s

| | 30 s | 90 s | Facteur |
|---|---|---|---|
| Nombre de plans | 8 | ~18 | ×2,25 |
| Texte lu (à 160 mots/min) | ~530 caractères | ~1 600 caractères | ×3 |
| Longueur du script généré | courte | longue | ×2,5 en jetons |
| Temps de montage | ~45 s | ~3 min | ×4 |

**Le piège** : croire qu'il faut 18 images différentes pour 18 plans. C'est faux, et
c'est ce qui ferait exploser le budget. Voir le point 3.

---

## 2. Les 3 scénarios possibles

Coût **par vidéo de 90 s** :

| Poste | 🟢 Économique | 🔵 Équilibré *(recommandé)* | 🟣 Premium |
|---|---|---|---|
| Angle + légende (Haiku) | 0,006 € | 0,006 € | 0,006 € |
| Script long (Sonnet) | 0,045 € | 0,045 € | 0,045 € |
| **Script Critic + réécriture** (Sonnet) | 0,030 € | 0,030 € | 0,030 € |
| **Hook Optimizer** (Sonnet) | 0,011 € | 0,011 € | 0,011 € |
| Storyboard 18 plans (Haiku) | 0,010 € | 0,010 € | 0,010 € |
| **Image Director** (Haiku) | 0,008 € | 0,008 € | 0,008 € |
| **Voice Director** (Haiku) | 0,002 € | 0,002 € | 0,002 € |
| Quality Control (Haiku vision) | 0,009 € | 0,009 € | 0,009 € |
| **Images** | 12 × FLUX schnell<br/>**0,034 €** | 2 dev + 10 schnell<br/>**0,074 €** | 12 × FLUX dev<br/>**0,276 €** |
| Voix | Kokoro local<br/>0,000 € | ElevenLabs<br/>*(dans l'abo)* | ElevenLabs<br/>*(dans l'abo)* |
| Musique · sous-titres · montage | 0,000 € | 0,000 € | 0,000 € |
| **Total par vidéo** | **0,155 €** | **0,195 €** | **0,397 €** |

### Budget mensuel complet

| | 🟢 Économique | 🔵 Équilibré | 🟣 Premium |
|---|---|---|---|
| 120 vidéos × coût unitaire | 18,60 € | 23,40 € | 47,64 € |
| 20 analyses de vidéos virales | 1,62 € | 1,62 € | 1,62 € |
| Trend Hunter (4×/mois) | 0,40 € | 0,40 € | 0,40 € |
| Abonnement ElevenLabs Creator | — | 22,00 € | 22,00 € |
| Sauvegarde | 2,00 € | 2,00 € | 2,00 € |
| **Total** | **22,62 €** | **49,42 €** | **73,66 €** |
| **Marge sur 80 €** | 57 € | **31 €** | **6 €** ❌ |

### Ma recommandation : 🔵 Équilibré

**Le premium ne passe plus.** Avec les 6 agents ajoutés (Critic, Hook Optimizer,
Psychology, Image Director, Voice Director, QC indépendant), il ne reste que 6 € de
marge — et à 120 vidéos/mois, un taux de reprise de 30 % (réaliste) ajoute ~14 €.
Le premium déborderait à ~88 €.

L'équilibré laisse **31 € de marge**, ce qui absorbe largement les reprises.
Après un mois de mesures réelles avec `pdz cost`, tu sauras exactement combien tu peux
remonter en qualité. C'est le bon ordre.

> **L'arbitrage à retenir** : mieux vaut un **bon script** en images correctes qu'un
> script moyen en images sublimes. Les 6,50 €/mois d'agents créatifs supplémentaires
> valent bien plus que le passage de FLUX schnell à FLUX dev.

---

## 3. Le vrai levier : 12 images, pas 18

**Sur une vidéo premium, plus de la moitié du coût, ce sont les images.** C'est donc là qu'il faut réfléchir.

Pour 18 plans, on ne génère que **12 images**. Les 6 plans manquants viennent de :

| Technique | Comment |
|---|---|
| **Recadrage** | Une même image, zoomée sur deux zones différentes = 2 plans distincts à l'écran |
| **Zoom avant puis arrière** | La même image en début et en fin de vidéo, avec un mouvement inversé |
| **B-roll gratuit** | Pexels / Pixabay : vidéos de stock libres de droits, 0 € |
| **Plans de texte** | Une carte de texte animée sur fond uni — souvent plus fort qu'une image IA |

Et ce n'est pas qu'une économie : **c'est meilleur visuellement.** 18 images IA toutes
différentes sur 90 secondes, ça part dans tous les sens. 12 images cohérentes avec du
mouvement et du b-roll, ça tient ensemble. Les vidéos qui marchent réutilisent leurs plans.

**Économie : 0,14 €/vidéo = 16,60 €/mois**, pour un meilleur rendu.

---

## 4. Attention au quota de voix ElevenLabs ⚠️

C'est le seul vrai piège du plan à 120 vidéos.

```
120 vidéos × 1 600 caractères = 192 000 caractères/mois
Plan Creator (22 €)           = 100 000 caractères/mois
                                ─────────────────────────
                                Il manque 92 000 caractères
```

Le plan Creator ne couvre qu'**environ 62 vidéos sur 120**. Le plan supérieur
(500 k caractères) coûte ~99 €/mois — hors budget.

**Trois solutions :**

| Solution | Comment | Coût |
|---|---|---|
| **Mixte** *(recommandé)* | ElevenLabs sur les 60 vidéos les plus importantes, Kokoro local sur les autres. Un réglage par vidéo : `pdz new "..." --voix=premium` | 22 € |
| **Modèle Flash** | ElevenLabs Flash v2.5 consomme moins de crédits par caractère sur les plans payants — à vérifier au moment de souscrire, ça pourrait suffire | 22 € |
| **Tout en local** | Kokoro pour les 120. Voix correcte, un peu robotique | **0 €** |

Le mode mixte est déjà prévu dans l'architecture : c'est une ligne dans `modeles.yaml`.

---

## 5. Le temps de montage (ce n'est plus négligeable)

| | 30 s | 90 s |
|---|---|---|
| Montage FFmpeg | ~45 s | **~3 min** |
| Pour 120 vidéos | 1,5 h | **6 h de calcul/mois** |

6 heures par mois, ce n'est pas un problème — **sauf si tu les subis en pleine journée.**
120 vidéos, c'est 4 par jour ; si tu les lances d'un coup le lundi, ton ordinateur est
bloqué 3 heures.

**Solution** : `pdz batch --nuit`. Les scripts sont validés dans la journée, le montage
tourne la nuit, les vidéos sont prêtes au réveil. C'est prévu dans le plan.

*(Le zoom lent sur les images — l'effet qui transforme un diaporama en vidéo — est
l'opération la plus lourde de FFmpeg. C'est elle qui explique les 3 minutes.)*

---

## 6. Les garde-fous (à câbler avant le premier appel payant)

1. **Plafond par vidéo** : 0,60 € en équilibré. Au-delà → dégradation puis arrêt.
2. **Plafond mensuel** : à 95 % des 80 €, refus de démarrer. `--force` pour passer outre.
3. **`max_tokens` toujours écrit en dur.** Sur des scripts longs, c'est encore plus
   important qu'avant : une réponse qui part en boucle coûte cher.
4. **Alerte à 3× le coût moyen** sur une vidéo → il y a un problème, on s'arrête.

---

## 7. Ce que je surveille le premier mois

| À mesurer | Attendu | Si c'est dépassé |
|---|---|---|
| Coût réel par vidéo | 0,195 € | vérifier le nombre d'images réellement générées |
| Taux de reprise (vidéos refaites) | < 30 % | **c'est un problème de prompt, pas de budget** |
| Caractères de voix consommés | 1 600/vidéo | scripts trop bavards → raccourcir |
| Temps de montage | 3 min | baisser la qualité d'encodage |

Le taux de reprise est le chiffre le plus important. À 120 vidéos/mois, chaque point
de reprise en trop coûte de l'argent **et** du temps de validation — et le temps sera
ta vraie limite, pas l'argent. Voir [07 — Tenir le rythme](./07-volume.md).
