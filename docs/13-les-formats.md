# 13 — Les formats : ce que l'outil doit savoir produire

Tu as décrit plusieurs choses très différentes. Elles n'ont ni le même coût, ni la même
difficulté, ni le même risque. Ce document les sépare proprement.

**La bonne nouvelle** : elles partagent 80 % du système. Le moteur, les validations, le
montage, les sous-titres, le suivi de coût ne changent pas. Ce qui change, c'est
**d'où viennent les images**.

---

## Vue d'ensemble

| Format | Exemple | Coût/vidéo | Difficulté | Juridique |
|---|---|---|---|---|
| **A · Série animée** | Fruits qui se trahissent | ~1,56 € | 🔴 élevée | ✅ clean |
| **B · Style anime, histoire à toi** | « ambiance shonen des années 90 » | ~1,56 € | 🔴 élevée | ✅ clean *(si personnages originaux)* |
| **C · Narration sur images générées** | Une histoire racontée, visuels créés | **~0,25 €** | 🟢 faible | ✅ clean |
| **D · Narration sur extrait de film** | Voix IA qui raconte par-dessus un film | ~0,15 € | 🟢 faible | ⚠️ **problème** |

> **Le format C est le moins cher, le plus simple, et sans aucun risque.**
> C'est celui par lequel il faut commencer — et probablement ton format de volume.

---

## A · Série animée à personnages

Déjà traité en détail dans [12 — Vidéos à personnages](./12-videos-a-personnages.md).
Univers → personnages → épisodes, avec fiches de personnages réutilisées.

**~30 à 55 épisodes/mois** dans les 80 €.

---

## B · Le style d'un anime, mais ton histoire

C'est ce que tu décris : *« je prends un animé de notre enfance et je le fais jouer une
scène, genre cette tête-là mais ma propre histoire »*.

### La distinction qui change tout

| | Statut |
|---|---|
| **Reprendre le STYLE** — cel-shading, palette, cadrages, ambiance shonen 90s | ✅ **Un style graphique ne se protège pas.** Tu as le droit |
| **Reprendre les PERSONNAGES** — Naruto, Goku, Luffy nommés et reconnaissables | ❌ Protégés. Les ayants droit japonais (Toei, Shueisha) sont très actifs |

Ce que tu décris — *« ma propre histoire »* — tombe du bon côté, à condition que les
personnages soient **les tiens**, dans ce style-là. C'est exactement ce que font les
créateurs qui durent dans ce genre.

### Et techniquement, ça ne demande rien de nouveau

Un « style anime 90s » est **juste un autre Univers** :

```
UNIVERS « Shonen 90s »
├── Style visuel   cel-shading, grain de pellicule, palette désaturée,
│                  contre-jours, cases dynamiques, lignes de vitesse
├── Personnages    LES TIENS — fiches de personnages, comme pour les fruits
├── Décors         village, forêt, arène
└── Règles         pouvoirs, hiérarchie, enjeux
```

**Zéro modification de l'architecture.** C'est une définition d'univers de plus.

> Point de vigilance concret : le prompt d'images ne doit **jamais** contenir le nom
> d'une œuvre ou d'un personnage protégé (« in the style of Naruto »). Il décrit le
> style par ses caractéristiques visuelles. C'est plus sûr **et** ça donne de meilleurs
> résultats — les modèles rendent mieux une description précise qu'une référence.
> Une vérification automatique bloquera ces mentions.

---

## C · Narration sur images générées ⭐

*« Une voix IA qui raconte une histoire »*, avec des visuels créés pour l'occasion.

C'est le genre « histoire racontée » / « récit » — massif sur TikTok et YouTube.

### Pourquoi c'est le meilleur point de départ

| | |
|---|---|
| **Coût** | ~0,25 € — **6 fois moins cher** qu'un épisode animé |
| **Difficulté** | Aucun problème de constance de personnage : les plans peuvent varier |
| **Vitesse** | Pas d'animation à générer → ~1 min au lieu de 5 |
| **Juridique** | Tout est créé par toi. Zéro risque |
| **Volume** | **~230 vidéos/mois** dans les 80 € |

### Le détail du coût (45 s)

| Poste | Coût |
|---|---|
| Script narratif (Claude Sonnet) | 0,045 € |
| Critique + accroche | 0,041 € |
| 12 images (FLUX schnell + 2 dev) | 0,074 € |
| Voix ElevenLabs | *dans l'abonnement* |
| Musique, bruitages, sous-titres, montage | 0,000 € |
| Contrôle qualité | 0,009 € |
| **TOTAL** | **≈ 0,17 €** |

### 💡 Le bon mélange budgétaire

```
30 épisodes animés (format A ou B)  ×  1,56 €  =  47 €
80 vidéos narrées (format C)        ×  0,17 €  =  14 €
ElevenLabs                                      =  22 €
                                                  ─────
                                                   83 €
```

**Tu tiens les deux formats en parallèle.** Les séries animées créent l'attachement,
les vidéos narrées font le volume et alimentent l'algorithme entre deux épisodes.

---

## D · Narration par-dessus un extrait de film ⚠️

*« Je prends un extrait d'un film et je mets une voix IA qui raconte l'histoire. »*

Techniquement c'est **le format le plus simple de tous** : pas d'images à générer, juste
découper, ajouter une voix et des sous-titres. ~0,15 €, et deux minutes de calcul.

Juridiquement, c'est le seul des quatre qui pose un vrai problème, et je préfère te le
dire clairement plutôt que de te laisser le découvrir après 50 vidéos.

### Ce qui se passe concrètement

| | |
|---|---|
| **YouTube** | Content ID détecte le métrage automatiquement. Selon l'ayant droit : monétisation redirigée vers lui, blocage dans certains pays, ou retrait. Trois strikes = chaîne supprimée |
| **TikTok / Instagram** | Détection également, retraits fréquents sur les gros studios |
| **Le « fair use »** | Existe aux États-Unis pour la critique et le commentaire, mais c'est une **défense en justice**, pas une autorisation préalable. Et il n'a pas d'équivalent direct en droit français |

Beaucoup de chaînes de « résumé de film » tournent quand même. Certaines vivent des
années, d'autres disparaissent du jour au lendemain. **C'est un pari, pas une base.**

### Les versions propres du même format

Elles produisent le même type de vidéo, sans le risque :

| Option | Détail |
|---|---|
| **🥇 Recréer les plans en images générées** | Tu racontes la même histoire, mais les visuels sont créés. **C'est le format C.** Aucun risque, et ça devient ton style à toi plutôt qu'un montage d'images empruntées |
| **Films du domaine public** | Catalogue énorme et libre : *Nosferatu*, *Metropolis*, *La Nuit des morts-vivants*, les premiers Hitchcock, le cinéma muet… Utilisables sans autorisation |
| **Banques sous licence** | Pexels, Pixabay, Archive.org — gratuit et explicitement autorisé |
| **Ton propre métrage** | Ce que tu filmes t'appartient |

### Ce que je construis

Un mode **« narration sur métrage fourni »** — tu donnes une vidéo, l'outil ajoute
narration, sous-titres et montage. Il est légitime et nécessaire pour le domaine public,
les banques libres et tes propres images.

Ce que je ne construis pas : de la détection de contenu protégé à contourner, du
recadrage ou de la modification de vitesse destinés à échapper à Content ID. Ce n'est
pas une posture morale, c'est que ça ne marche pas durablement et que ça finit par
coûter la chaîne.

**L'outil te dira ce que tu lui donnes ; ce que tu lui donnes, c'est ton choix.**

---

## Ce que ça change dans l'architecture

Bonne nouvelle : **presque rien.** Il suffit de généraliser d'un cran.

```
FORMAT  ─── d'où viennent les images ?
  ├── serie_animee        → fiches de personnages → images → animation
  ├── narration_generee   → images générées, pas d'animation      ⭐ le moins cher
  └── narration_metrage   → tu fournis la vidéo

UNIVERS ─── style, personnages, décors, règles, voix
  ├── « Fruit Island »
  ├── « Shonen 90s »
  ├── « Légumes au bureau »
  └── … autant que tu veux

Le reste est commun : script → critique → accroche → validation →
                      voix → sous-titres → montage → contrôle qualité
```

| Élément | Impact |
|---|---|
| Le moteur, la reprise, le cache, le budget | ✅ aucun changement |
| Script, Critic, Hook, Voice, montage, sous-titres, QC | ✅ communs aux 4 formats |
| Agent **Animateur** | actif uniquement en format A et B |
| Agent **Continuité** | actif uniquement pour les séries |
| Nouveau : **Importateur de métrage** | découpe et normalise une vidéo fournie |
| Nouveau : **Contrôle de style** | bloque les noms d'œuvres et personnages protégés dans les prompts d'images |

---

## Ma recommandation sur l'ordre

| Ordre | Format | Pourquoi |
|---|---|---|
| **1er** | **C — narration sur images générées** | Le plus simple, le moins cher, zéro risque. Il valide toute la chaîne (script → voix → sous-titres → montage) avant d'ajouter la difficulté de l'animation |
| **2e** | **A/B — séries animées** | On ajoute les fiches de personnages et l'animation par-dessus une chaîne qui marche déjà |
| **3e** | **D — métrage fourni** | Simple techniquement, mais à réserver au domaine public et aux banques libres |

> Construire le format C d'abord n'est pas un compromis : c'est ce qui te permet
> d'avoir des vidéos publiables **la première semaine**, pendant que l'animation se met
> en place.
