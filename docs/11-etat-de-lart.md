# 11 — Ce que font les autres, et ce que disent les chiffres

Recherche menée en août 2026 sur les outils existants, les techniques qui marchent
réellement, et les modèles de génération vidéo. Sources en bas de page.

---

## 11.1 La mauvaise nouvelle : le marché est saturé de « slop »

**59 % des vidéos servies à un nouvel utilisateur TikTok sont de l'« AI slop »** —
contre 21 % sur YouTube Shorts. Trois fois plus sur TikTok.

Définition retenue par l'étude : visuels manifestement générés par IA, compilations
de mauvaise qualité, scripts et voix off visiblement automatiques.

**Et TikTok réagit** : les utilisateurs peuvent désormais réduire la part de contenu
généré par IA dans leur fil, via « Manage Topics ». C'est une réponse directe aux
plaintes sur l'invasion de slop.

### Ce que ça veut dire pour nous

Construire « encore un générateur de vidéos faceless » revient à entrer dans une
catégorie **saturée et activement pénalisée**. Il faut le savoir avant de commencer.

**Mais** — et c'est précisément l'intérêt de notre approche — le slop a deux causes :

| Cause du slop | Notre réponse |
|---|---|
| **Structure générique** : toutes les vidéos ont le même squelette plat | On copie la structure d'une vidéo **qui a réellement fonctionné** |
| **Visuels génériques** : images IA sans direction, sans mouvement, sans cohérence | Direction artistique imposée, mouvement systématique, réutilisation cohérente |

Le transfert de structure est **exactement l'antidote** au problème n°1. C'est la
meilleure justification du projet que j'aie trouvée — et elle vient des données,
pas de mon intuition.

---

## 11.2 ⚠️ Correction importante : je me suis trompé sur le rythme

J'ai écrit dans les documents précédents « 18 plans de 2,5 s » pour une vidéo de 90 s.
**C'est trop lent.**

Le repère 2026 pour le court format :

```
Changement visuel toutes les 1,5 à 2 secondes
En dessous de 1,2 s → le cerveau traite ça comme du bruit et décroche
```

Pour 90 secondes, ça fait donc **45 à 60 changements visuels**, pas 18.

### Ce que ça change concrètement

Un « changement visuel » **n'est pas forcément une nouvelle image générée**. C'est :

| Type de changement | Coût |
|---|---|
| Nouvelle image IA | 0,003 à 0,023 € |
| **Recadrage sur la même image** | **0 €** |
| **Zoom qui s'inverse** | **0 €** |
| **Carte de texte animée** | **0 €** |
| **B-roll de stock (Pexels)** | **0 €** |
| Changement de vitesse, flash, secousse | 0 € |

Donc : **~15 images générées pour ~50 changements visuels.** Le budget images ne bouge
presque pas ; c'est le montage qui devient plus dense. FFmpeg encaisse sans problème,
mais le temps de rendu augmente (~4 min au lieu de 3 pour 90 s).

**Tous les chiffres de rythme des documents 01, 05 et 07 sont à corriger.**

---

## 11.3 La métrique qui décide de tout

```
Complétion ≥ 70 %  +  engagement ≥ 15 % dans la première heure
                    ↓
        ≈ 3× plus de portée que la moyenne
```

C'est **le** chiffre à viser. Et il a une conséquence directe sur le produit :

> **La complétion se gagne en faisant plus court, pas en faisant plus long.**

---

## 11.4 ⚠️ Deuxième correction : la durée cible

Tu m'as demandé des vidéos de **1 à 2 minutes**. Les données disent :

> « La majorité du contenu qui performe se situe entre **30 et 60 secondes** »

Et la mécanique est logique : à 70 % de complétion exigés, tenir 100 secondes est
beaucoup plus dur que tenir 45 secondes. Une vidéo de 45 s vue en entier bat une
vidéo de 100 s abandonnée à 50 %.

### Ma recommandation

**Vise 45 à 60 secondes.** C'est le chevauchement entre ta préférence et les données.

Mais **c'est ton appel** : l'outil produira la durée que tu lui demandes, c'est un
paramètre. Je te donne le chiffre, tu décides.

*(Si tu tiens aux 90 s, alors les « relances » toutes les 15-20 s ne sont plus une
option mais une obligation absolue — c'est le seul moyen de tenir la complétion.)*

---

## 11.5 La structure du hook, précisée par les données

Ce que je savais : « les 3 premières secondes comptent ».
Ce que les données ajoutent : **le hook doit être multimodal**, trois choses en même temps.

```
Seconde 0-3   HOOK — les trois simultanément :
              ① rupture visuelle (mouvement, surprise, gros plan)
              ② texte à l'écran orienté bénéfice
              ③ premiers mots parlés avec le mot-clé

Seconde 3-5   PROMESSE — UNE seule. Pas deux, pas trois. Une.

Milieu        CONTENU — zéro remplissage, on passe d'un point de valeur au suivant

Fin           CTA court + dernière image qui boucle visuellement
```

Règles de rédaction confirmées :
- **Présent et verbes actifs.** « Voilà pourquoi tes vidéos ne décollent pas » bat
  « Aujourd'hui nous allons voir quelques raisons pour lesquelles… »
- **Une seule promesse.**
- **Les affirmations tranchées et les manques d'information** surperforment systématiquement.

→ Ça devient la grille du **Script Critic** et du **Hook Optimizer**.

Autre point qui compte : beaucoup de vidéos démarrent **sans le son**. Les sous-titres
et les indices visuels ne sont donc pas un confort, ce sont le canal principal des
premières secondes.

---

## 11.6 Les modèles de génération vidéo — et pourquoi c'est enfin intéressant

| Modèle | Prix indicatif | Note |
|---|---|---|
| **Veo 3.1 Lite** | ~0,03 $/s en 720p · ~0,05 $/s en 1080p | Le moins cher |
| **Veo 3.1 Standard** | ~0,40 à 0,75 $/s | **Seul modèle avec audio natif** + 4K |
| **Kling 3.0** | ~0,07 à 0,11 $/s | Sans audio |
| **Sora 2** | ~0,10 $/s · Pro 0,70 $/s | ⚠️ **API fermée le 24 septembre 2026** — ne rien bâtir dessus |
| **Runway Gen-4.5 · Seedance 2.0** | variable | |

### Le calcul qui compte

```
Vidéo entière en IA générative :
  90 s × 0,05 $/s = 4,50 $   ❌ 22× le budget par vidéo

Seulement les 3 premières secondes :
   3 s × 0,05 $/s = 0,15 $   ✅ tenable
```

### 💡 L'idée qui sort de cette recherche

> **Générer en vraie vidéo IA uniquement le hook — les 3 premières secondes.
> Images fixes animées pour tout le reste.**

Pourquoi c'est le bon arbitrage :
- Les 3 premières secondes décident de tout le reste de la vidéo.
- C'est le seul endroit où 0,15 € de dépense supplémentaire se justifie.
- Un vrai mouvement filmé en ouverture, c'est exactement ce qui distingue une vidéo
  du « slop » à images fixes — au moment précis où le spectateur décide.
- Le surcoût passe le coût par vidéo de ~0,20 € à ~0,35 €. Ça reste dans le budget.

C'est activable par option (`--hook-video`) et par profil : sur les vidéos où tu crois
vraiment, tu paies 0,15 € de plus.

---

## 11.7 Les outils existants

| Outil | Ce qu'il fait | Ce qu'il ne fait pas |
|---|---|---|
| **FlowShorts** | pipeline complet + publication auto TikTok/Shorts/Reels | pas d'analyse de vidéo source |
| **AutoShorts · BigMotion** | idem, publication auto TikTok | idem |
| **StoryShort** | idées → script → médias → publication quotidienne | idem |
| **Overchat** | reel complet depuis une phrase, format « brainrot » | idem |
| **InVideo AI** | 16 M+ d'assets de stock assemblés | idem |
| **OpusClip · Submagic** | découpe de vidéos longues, sous-titres, b-roll | ne crée pas depuis une idée |
| **HeyGen · Synthesia** | avatars parlants réalistes | autre catégorie |

**Le constat** : tous font « idée → vidéo ». **Aucun ne fait « analyse une vidéo qui
a marché → applique sa structure exacte à ton sujet ».**

C'est ton angle, et il est vide. Ce n'est pas un hasard : c'est plus dur à faire, et
ça demande d'accepter qu'on copie une forme sans promettre le résultat.

Ce que je reprends d'eux :
- **La publication automatique** est devenue le standard — à prévoir en v2.
- **Les sous-titres animés façon TikTok** sont un minimum absolu, pas une option.
- **La voix ElevenLabs** est la norme du segment premium.

---

## 11.8 Ce que je change dans le projet

| # | Décision | Raison |
|---|---|---|
| 1 | **Rythme : 1,5–2 s** par changement visuel, pas 2,5 s | repère 2026 mesuré |
| 2 | **~15 images pour ~50 changements** (recadrages, zooms, cartes de texte, b-roll) | tenir le rythme sans exploser le budget |
| 3 | **Durée recommandée 45–60 s** *(paramétrable)* | complétion 70 % = la métrique reine |
| 4 | **Hook multimodal obligatoire** : visuel + texte + voix, ensemble | ce que disent les données |
| 5 | **Option hook en vidéo IA générative** (Veo 3.1 Lite, ~0,15 €) | le seul endroit où ça vaut le coût |
| 6 | **Grille du Script Critic revue** : une seule promesse, présent, verbes actifs, zéro remplissage | idem |
| 7 | **Ne jamais bâtir sur Sora 2** | API fermée le 24/09/2026 |
| 8 | **Dernière image qui boucle** | favorise le replay, donc la complétion |
| 9 | **Sortir du slop est un objectif produit**, pas une fierté d'ingénieur | TikTok filtre désormais l'IA |

---

## Sources

- [Nearly 60% of TikTok videos shown to new users are AI slop, study finds — TNW](https://thenextweb.com/news/tiktok-ai-slop-59-percent-new-users-kapwing-study)
- [The AI slop video trend: how mass-produced AI video is flooding feeds — Kompozy](https://kompozy.io/guides/ai-slop-video-content-trend)
- [TikTok Algorithm 2026: 3 New Rules You Must Follow — Virvid](https://virvid.ai/blog/tiktok-algorithm-2026-explained)
- [Short-Form Video Editing at Scale: Captions, B-Roll, and the 2026 Pacing Model — Aibrify](https://aibrify.com/blog/short-form-video-editing-captions-b-roll-guide)
- [The YouTube Shorts Retention Curve Playbook (2026) — Aibrify](https://aibrify.com/blog/youtube-shorts-retention-curve-playbook)
- [The First 3 Seconds: Hook Structures That Stop Scroll on Shorts — Virvid](https://virvid.ai/blog/first-3-seconds-hook-faceless-shorts-2026)
- [B-Roll & Visual Effects Guide for Short-Form Video (2026 Data) — OpusClip](https://www.opus.pro/research/broll-visual-effects-short-form)
- [YouTube Shorts Length in 2026: How Long to Go Viral — Toptal](https://www.toptal.com/creator/post/youtube-shorts-length)
- [Veo 3.1 vs Kling 3.0 vs Sora 2: AI Video API Pricing 2026 — ModelsLab](https://modelslab.com/blog/api/veo-3-1-vs-kling-3-sora-2-ai-video-api-cost-2026)
- [AI Video Generation Pricing 2026 — FluxNote](https://fluxnote.io/blog/ai-video-generation-pricing-guide-2026)
- [7 Best Faceless Video Generators That Auto-Post (2026) — FlowShorts](https://flowshorts.app/blog/best-faceless-video-generators-auto-post)
- [12 Best Tools to Create Faceless Videos in 2026 — StoryShort](https://storyshort.ai/en/blog/12-best-tools-to-create-faceless-videos)
