> ⚠️ **Ce document remplace la direction produit des docs 01, 05, 07 et 08.**
> Le projet ne fabrique plus des vidéos éducatives illustrées, mais des
> **épisodes narratifs joués par des personnages récurrents**.

# 12 — Vidéos à personnages : le vrai projet

## 12.1 Ce que tu veux réellement faire

Pas « une voix off qui explique avec des images derrière ».
**Des personnages qui jouent une histoire.** Des fruits qui se trahissent, se draguent,
s'éliminent. Avec des dialogues, des réactions, du drame.

C'est un métier technique complètement différent, et une **niche documentée qui explose**.

## 12.2 La preuve que ça marche

**@ai.cinema021 — « Fruit Love Island », mars 2026 :**

```
300+ millions de vues · 3,3 millions d'abonnés · en 9 jours
```

Le format : une télé-réalité de rencontres où les candidats sont des fruits.
Strawberina la méchante, Bananito le briseur de cœurs, l'Avocat qui joue les détachés.
Les spectateurs **votent** pour qui reste et qui est éliminé.

### La leçon la plus importante de toute ma recherche

> **« Le contenu en série bat le contenu isolé à tous les coups. Des personnages
> constants donnent au public une raison de suivre, de s'abonner, et de revenir. »**

Ça change la nature du produit :

| Ancien projet | **Nouveau projet** |
|---|---|
| Générer *une vidéo* depuis une idée | **Faire tourner une série avec un casting récurrent** |
| Chaque vidéo repart de zéro | Chaque épisode continue le précédent |
| Volume : 120 vidéos/mois | **Régularité : 1 épisode par jour** |
| Le sujet est roi | **Les personnages sont rois** |

## 12.3 Le concept central : l'Univers

C'est la pièce d'architecture qui rend tout le reste possible — et qui répond
directement à ton « j'ai plein de niches ».

```
UNIVERS « Fruit Island »
├── Personnages
│   ├── Strawberina   fiche visuelle · voix ElevenLabs #1 · caractère : manipulatrice
│   ├── Bananito      fiche visuelle · voix #2 · caractère : charmeur lâche
│   └── Avocado       fiche visuelle · voix #3 · caractère : détaché, sarcastique
├── Décors            la villa, la piscine, la cérémonie d'élimination
├── Règles du monde   les fruits ont des bras, parlent, vivent dans une villa
├── Style visuel      rendu 3D façon Pixar, couleurs saturées, éclairage doux
└── Épisodes          #1, #2, #3… avec continuité

UNIVERS « Légumes au bureau »   ← ta niche n°2
UNIVERS « Animaux de la ferme » ← ta niche n°3
```

**Tu définis un univers une fois. Tu produis 50 épisodes avec.**

C'est ce qui rend la production quotidienne tenable, et c'est aussi ce qui crée
l'attachement du public. Un nouvel univers = une nouvelle niche, sans retoucher
au système.

## 12.4 Le problème technique n°1 : la constance des personnages

Si Strawberina change de tête entre le plan 3 et le plan 7, **tout s'effondre**.
C'est LE point dur du genre.

### La méthode qui fonctionne en 2026

```
1. FICHE DE PERSONNAGE          Une planche : le personnage sous plusieurs angles,
   (une seule fois par perso)   plusieurs expressions, plusieurs poses.
                                → Nano Banana ou Midjourney
                                ↓
2. IMAGE DE DÉPART              Chaque plan part de la fiche comme référence.
   (une par plan)               Même personnage, nouvelle situation.
                                → FLUX avec image de référence
                                ↓
3. ANIMATION                    L'image de départ est mise en mouvement.
   (une par plan)               → Kling 3.0 ou Veo 3.1 en image-to-video
                                ↓
4. VOIX PAR PERSONNAGE          Une voix ElevenLabs fixe par personnage.
                                Strawberina a TOUJOURS la même voix.
```

**Le point clé** : on ne génère jamais un personnage « de zéro ». Chaque image part
de la fiche. C'est ce qui garantit que c'est la même fraise du premier au dernier plan.

Les fiches de personnages sont stockées une fois et réutilisées à l'infini → **coût nul
sur tous les épisodes suivants**.

## 12.5 Ce que ça change dans le budget — la conversation difficile

Il faut être direct : **animer coûte 10 à 20 fois plus cher qu'une image fixe.**

### Le calcul pour un épisode de 45 secondes

| Poste | Détail | Coût |
|---|---|---|
| Script dialogué (Claude Sonnet) | réplique par réplique, par personnage | 0,04 € |
| Critique du script | rythme dramatique, punchlines | 0,03 € |
| Fiches de personnages | **déjà faites, réutilisées** | **0,00 €** |
| Images de départ | 8 plans × FLUX dev | 0,18 € |
| **Animation** | **8 clips × 3,5 s × ~0,05 $/s** | **~1,30 €** ⚠️ |
| Voix multi-personnages | ~700 caractères, ElevenLabs | *dans l'abonnement* |
| Bruitages + musique | banque libre de droits | 0,00 € |
| Montage + sous-titres | FFmpeg | 0,00 € |
| Contrôle qualité | Claude Haiku vision | 0,01 € |
| **TOTAL** | | **≈ 1,56 €** |

### Ce que 80 €/mois permet réellement

```
80 €  −  22 € (ElevenLabs)  =  58 € de production

58 € ÷ 1,56 €  ≈  37 épisodes par mois
```

**Soit environ 1 épisode par jour.** Ce qui est exactement le bon rythme pour une série.

| Format | Épisodes/mois dans 80 € |
|---|---|
| **Tout animé, 45 s** | **~37** |
| Hybride *(voir 12.6)*, 45 s | ~55 |
| Tout animé, 90 s | ~19 |
| Images fixes animées *(l'ancien projet)* | ~350 |

### ⚠️ Il faut renoncer aux 120 vidéos par mois

Avec de vrais personnages animés, **120 vidéos/mois coûteraient ~210 €**.

Mais pour ce genre, ce n'est pas grave — c'est même mieux :

> Fruit Love Island a fait 300 millions de vues avec **une poignée d'épisodes**.
> Dans le narratif, la régularité et l'attachement battent le volume.
> **30 épisodes soignés valent mieux que 120 bâclés.**

## 12.6 Comment étirer le budget sans casser l'illusion

Tous les plans n'ont pas besoin d'être animés. Dans un épisode de 45 s :

| Type de plan | Combien | Coût |
|---|---|---|
| **Plans d'action animés** — le personnage bouge, parle, réagit | 5 à 6 | payant |
| **Plans de réaction** — gros plan sur un visage, léger zoom, image fixe | 3 à 4 | **0 €** |
| **Plans de coupe** — décor, objet, détail, avec mouvement de caméra | 2 à 3 | **0 €** |
| **Cartes de texte** — « ÉPISODE 4 », « 3 HEURES PLUS TARD » | 1 à 2 | **0 €** |

Le montage classique fait exactement ça depuis toujours : on n'anime que ce qui doit
bouger. Un gros plan fixe sur un visage choqué pendant 1,5 s est **plus efficace**
qu'une animation moyenne, et il ne coûte rien.

**Résultat : ~1,00 €/épisode au lieu de 1,56 €, soit ~55 épisodes/mois.**

## 12.7 Ce que ça change dans le système

| Élément | Avant | **Maintenant** |
|---|---|---|
| L'objet central | une vidéo | **un univers + des épisodes** |
| Le script | voix off qui explique | **dialogues entre personnages** |
| La voix | une seule | **une par personnage, fixe** |
| Les images | illustrations du propos | **plans de cinéma, personnages constants** |
| Le mouvement | zoom lent sur image fixe | **animation image-to-video** |
| Le son | musique de fond | **musique + bruitages + réactions** |
| Ce qu'on réutilise | rien | **les fiches de personnages, les décors, les voix** |
| La continuité | aucune | **l'épisode N connaît les épisodes 1 à N-1** |

### Les agents qui changent

| Agent | Ce qui change |
|---|---|
| ✍️ **Script Writer** | écrit des **dialogues** : qui dit quoi, avec quelle intention. Plus de voix off |
| 🧐 **Script Critic** | note le **drame** : enjeu clair ? retournement ? punchline finale ? |
| 🎨 **Image Director** | devient **directeur de casting et de plateau** : quel personnage, quel angle, quelle expression, quel décor — en partant des fiches |
| 🎬 **Nouveau : Animateur** | décide **quels plans méritent d'être animés** et lesquels restent fixes. C'est lui qui tient le budget |
| 🎤 **Voice Director** | attribue la bonne voix au bon personnage, et l'intention de jeu |
| 🔊 **Nouveau : Sound Designer** | bruitages et réactions. Dans ce genre, le son fait 30 % de l'effet |
| 📖 **Nouveau : Continuité** | se souvient de ce qui s'est passé dans les épisodes précédents |

## 12.8 Une mise en garde honnête

**La niche « fruits » a démarré en mars 2026 et a explosé.** Nous sommes en août.
Dans ce genre de tendance, les premiers prennent tout et les suivants ramassent les miettes.

Deux conséquences :

1. **Ne construis pas un outil à fruits.** Construis un outil à **univers**. Les fruits
   sont un univers parmi d'autres. Quand la tendance passe, tu changes d'univers en une
   soirée au lieu de tout refaire. Ton « j'ai plein de niches » est exactement le bon
   réflexe — je le mets au cœur de l'architecture.

2. **Ce qui dure, ce sont les personnages, pas le format.** Un casting auquel les gens
   s'attachent survit à la mode qui l'a fait naître.

## 12.9 Ce que je change dans le plan

| # | Décision |
|---|---|
| 1 | **L'Univers devient l'objet central** du système : personnages, décors, style, règles |
| 2 | **Les fiches de personnages** sont créées une fois et réutilisées — coût nul ensuite |
| 3 | **Chaque plan part d'une image de référence**, jamais d'une génération libre |
| 4 | **Une voix ElevenLabs fixe par personnage** |
| 5 | **Le Script Writer écrit des dialogues**, plus de la voix off |
| 6 | **Nouvel agent Animateur** : décide quoi animer et quoi laisser fixe — c'est le gardien du budget |
| 7 | **Nouvel agent Sound Designer** : bruitages, 30 % de l'effet dans ce genre |
| 8 | **Nouvel agent Continuité** : mémoire des épisodes précédents |
| 9 | **Objectif révisé : ~30 à 55 épisodes/mois**, pas 120 vidéos |
| 10 | **Durée cible 30 à 45 s** — dans le narratif animé, court et dense bat long et mou |
| 11 | **Ne jamais coder « fruits » en dur.** Tout passe par la définition d'univers |

---

## Sources

- [AI Fruit Love Island: How to Make Your Own Viral Fruit Characters — ZenCreator](https://zencreator.pro/ai-university/guides/ai-fruit-love-island-trend)
- [Making AI Fruit Drama Videos in 2026: Complete Practical Tutorial — Medium](https://medium.com/@mrhotfix/making-ai-fruit-drama-videos-in-2026-the-complete-practical-tutorial-tools-workflow-b2e68e60c4b7)
- [How to Keep AI Characters Consistent Across Videos — 2026 Guide, FlyAIgh](https://www.flyaigh.com/blog/guide-character-consistency-2026)
- [Kling AI Pricing 2026: All Plans, Credit Costs, and Honest Trade-offs — MagicHour](https://magichour.ai/blog/kling-ai-pricing)
- [AI Video Generation Pricing 2026 — FluxNote](https://fluxnote.io/blog/ai-video-generation-pricing-guide-2026)
- [AI Filmmaking Cost Breakdown 2026 — MindStudio](https://www.mindstudio.ai/blog/ai-filmmaking-cost-breakdown-2026)
