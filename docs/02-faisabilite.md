# 1. Faisabilité d'abord

> Section 1 du brief SaaS. Verrou technique du projet : si cette section ne tient pas,
> aucune décision d'architecture n'a d'importance.

## 1.1 La réponse courte

**L'extraction d'« ADN viral » est fiable pour la *forme*, pas pour la *cause*.**

On sait mesurer très précisément **comment une vidéo est construite**. On ne sait pas
extraire **pourquoi elle a marché** — et c'est une limite de nature, pas de maturité
technologique. Elle ne sera pas levée par un meilleur modèle l'an prochain.

Ça ne tue pas le produit. Ça change ce qu'il peut promettre, et donc son positionnement
marketing, son argumentaire de vente et son exposition juridique. Le reste du document
part de là.

## 1.2 Les trois niveaux de fiabilité

Tout ce que le brief liste ne se vaut pas. Trois catégories, à ne jamais mélanger dans
le produit ni dans l'UI.

```
NIVEAU 1 — MESURÉ            traitement du signal, déterministe, reproductible
                             même entrée → même sortie, toujours
                             coût ≈ 0 €

NIVEAU 2 — INFÉRÉ            jugement d'un LLM/VLM sur des preuves structurées
                             reproductible à prompt+modèle+température figés
                             mais ce sont des étiquettes, pas des mesures

NIVEAU 3 — NON EXTRACTIBLE   n'est pas dans le fichier vidéo
                             toute valeur produite ici est une invention
```

---

## 1.3 Niveau 1 — Ce qui est objectivement mesurable

Aucun LLM. Traitement du signal classique. C'est la fondation crédible du produit.

| Métrique | Méthode | Fiabilité | Coût | Là où ça casse |
|---|---|---|---|---|
| **Durée / résolution / fps / ratio** | ffprobe | 100 % | 0 € | — |
| **Frontières de plans (coupes)** | PySceneDetect *content-aware* + seuil adaptatif | **90–96 %** | 0 € | speed ramps, whip pans, flashs, fondus progressifs |
| **Densité de coupes** (coupes/min) | dérivé du précédent | hérite de l'erreur | 0 € | — |
| **Durée des plans** (moyenne, médiane, p10/p90, distribution) | dérivé | hérite de l'erreur | 0 € | — |
| **Courbe d'énergie audio** (RMS par fenêtre) | librosa / ffmpeg | 99 % | 0 € | — |
| **Loudness intégrée (LUFS)** | ffmpeg `loudnorm` | 99 % | 0 € | — |
| **Silences / pauses** | détection de seuil sur RMS | 95 % | 0 € | musique de fond continue |
| **BPM / grille de beats** | librosa beat tracking | **75–90 %** | 0 € | musique sans percussion, voix seule, tempo variable |
| **Alignement coupes/beats** | corrélation croisée coupes × beats | dérivé | 0 € | — |
| **Débit narratif (mots/min)** | timestamps mot de Whisper | **95 %+** | ~0,001 € | forte musique, accents marqués |
| **Distribution des pauses de narration** | timestamps mot | 95 % | inclus | — |
| **Ratio voix / musique** | séparation de sources (Demucs) ou VAD | 85–95 % | 0 € (CPU) | Demucs coûte du CPU |
| **Palette de couleurs par plan** | k-means sur keyframes | 100 % | 0 € | — |
| **Intensité de mouvement** | flux optique / différence de frames | 95 % | 0 € | — |
| **Présence et taille de visage** | détection de visages | ~90 % | 0 € | visages partiels, filtres |
| **Texte à l'écran** | OCR par keyframe (PaddleOCR) | **65–85 %** | 0 € | police stylisée, texte animé, fond chargé |

**Ce que ça donne concrètement** : durée des plans, densité de coupes, courbe audio,
débit narratif, structure rythmique, alignement musical, palette. C'est-à-dire **tout
le squelette technique du montage** — la partie du brief la plus solide.

**Point clé pour le coût** : ces 16 métriques ne coûtent **rien** en API. Beaucoup de
projets concurrents envoient tout à un LLM multimodal. C'est 100× plus cher, plus lent,
et **moins précis** — un modèle qui « estime » un BPM est objectivement moins bon que
`librosa`. C'est un avantage de coût structurel qu'il faut tenir.

### Le format qui casse tout : le carrousel photo

Sur TikTok, une part significative du contenu performant n'est **pas** de la vidéo :
ce sont des diaporamas photo (« photo mode »). Aucune coupe à détecter, pas d'audio
narratif, souvent juste un son tendance. **La moitié du niveau 1 ne s'applique pas.**

À traiter dès le départ : détecter le format en entrée et router vers un pipeline
d'analyse distinct — ou refuser explicitement avec un message clair. Un produit qui
renvoie une analyse vide sur un carrousel perd l'utilisateur au premier essai.

---

## 1.4 Niveau 2 — Ce qui s'infère avec une confiance moyenne

Ici on demande à un modèle de **classer** et **interpréter** des preuves du niveau 1.
C'est utile et vendable, mais ce sont des étiquettes de modèle, pas des faits.

| Élément | Méthode | Confiance réaliste | Remarque |
|---|---|---|---|
| **Type de hook** (question / négation / chiffre / POV / choc) | LLM sur les 3 premières secondes (transcript + 3 keyframes + OCR) | **75–85 %** | taxonomie fermée = bien plus stable que du texte libre |
| **Découpage en actes** | LLM sur transcript + timings | 70–80 % | dépend beaucoup du format |
| **Type et position du CTA** | LLM sur la fin du transcript + OCR | 80–90 % | assez explicite en général |
| **Boucles ouvertes / relances** | LLM sur transcript horodaté | 60–75 % | subjectif mais le plus utile sur 60 s+ |
| **Niche / sujet / archétype** | LLM | 85–90 % | facile |
| **Ton de narration** | LLM sur transcript + prosodie | 65–80 % | |
| **Arc émotionnel** | LLM/VLM | **50–65 %** ⚠️ | **le plus faible de tout le produit** |
| **Style de sur-titrage** | VLM sur keyframes | 70–85 % | |

### L'arc émotionnel mérite un avertissement séparé

Le brief le demande explicitement. Il faut être clair : ce qu'on obtient, c'est
**l'impression d'un modèle de langage sur l'émotion supposée d'un spectateur imaginaire**.
Ce n'est ni mesuré, ni validé, ni reproductible d'un modèle à l'autre.

Deux modèles différents produisent régulièrement des courbes d'émotion divergentes sur
la même vidéo. C'est un test à faire en semaine 1 : passer 20 vidéos dans deux modèles
et mesurer l'accord. **Si l'accord inter-modèles est sous 60 %, la métrique ne doit pas
être affichée comme un fait dans l'UI.**

Ce qui est réellement exploitable et proche de l'émotion, mais **mesuré** :
la courbe d'énergie audio, la courbe de densité de coupes, les variations de débit,
les ruptures de rythme. Ces quatre courbes captent une grande partie de ce que
l'utilisateur appelle « l'arc émotionnel », et elles sont du niveau 1.

**Recommandation** : construire l'arc émotionnel comme une **lecture interprétée de
courbes mesurées**, pas comme une sortie LLM libre. Le LLM nomme et commente ce que
les courbes montrent ; il ne les invente pas.

### Rendre le niveau 2 acceptable — 3 mécanismes

1. **Taxonomies fermées.** Un hook est classé parmi 8 types définis, jamais décrit en
   texte libre. La sortie devient comparable, cachable, évaluable.
2. **Confiance par section, exposée dans l'UI.** Le rythme est à 0,95, l'émotion à 0,60.
   L'utilisateur doit voir la différence, et le générateur doit pondérer les contraintes
   par leur confiance. Sans ça, on transfère du bruit avec la même autorité que du signal.
3. **Jeu de test étiqueté à la main.** 50 vidéos annotées par toi = la seule façon de
   savoir si les 75–85 % annoncés ci-dessus sont vrais **sur ton corpus**. Ces chiffres
   sont des estimations d'ingénierie, pas des mesures sur tes données.

---

## 1.5 Niveau 3 — Ce qui n'est pas extractible

À refuser de promettre, quelle que soit la pression commerciale.

| Ce qu'on aimerait | Pourquoi c'est impossible |
|---|---|
| **La courbe de rétention** | Elle n'est pas dans le fichier. Elle vit dans TikTok Analytics, côté créateur. À ne jamais confondre avec l'« arc émotionnel » — beaucoup de gens les confondent |
| **Pourquoi la vidéo a percé** | Déterminé majoritairement par des facteurs hors vidéo : audience existante du compte, heure de publication, son tendance, lot de test de l'algorithme, section commentaires, hasard |
| **Un score de viralité prédictif** | Nécessiterait un corpus de vidéos ayant échoué, avec leurs métriques. Personne ne publie ses échecs |
| **Le taux d'engagement attendu** | Idem |
| **Ce qui a fonctionné vs ce qui est du bruit** | Voir le biais de survivance ci-dessous |

### Le biais de survivance — la vraie limite du concept

C'est le point que la plupart des produits de ce type esquivent.

On n'analyse **que des vidéos qui ont marché**. Il n'y a pas de groupe témoin. Donc
quand le système observe « 18 plans de 2,5 s, hook par négation, CTA à 92 % », il est
**incapable de distinguer** :

- ce qui a causé la performance,
- de ce qui est simplement la norme du format dans cette niche — présent à l'identique
  dans les milliers de vidéos comparables qui ont fait 400 vues.

Sans exemples négatifs, **l'ADN viral est une description, pas une explication.**

Trois conséquences directes :

1. **Marketing** : « reproduis la structure des vidéos qui marchent » est vrai.
   « on sait pourquoi elles marchent » est faux et attaquable.
2. **Produit** : la valeur réelle n'est pas la prédiction, c'est la **contrainte créative
   structurée et répétable** — appliquer une forme éprouvée à un sujet nouveau, vite et
   de façon cohérente. C'est un vrai besoin, et c'est ce qui se vend.
3. **Roadmap** : le seul chemin vers une causalité réelle est de **collecter les
   performances réelles des vidéos générées par tes utilisateurs**. À 50 utilisateurs
   × 20 vidéos, ça fait 1 000 points de données avec succès **et** échecs, sur des
   structures connues. C'est le seul actif défendable à 18 mois, et il se construit
   dès le jour 1 ou jamais.

---

## 1.6 Ce qui rend le concept réellement plus fiable

Trois leviers qui ne coûtent presque rien et changent la qualité du produit.

**a) Analyser N vidéos, pas une.**
Une vidéo = du bruit. Dix vidéos performantes du même créateur ou de la même niche =
un signal. Ce qui se répète dans 8 cas sur 10 est une caractéristique du format ; ce qui
n'apparaît qu'une fois est une coïncidence.
→ C'est aussi une **fonctionnalité vendable** (« analyse un compte entier ») et un
argument de montée en gamme tarifaire.

**b) Séparer strictement la forme du fond.**
Ce qui entre dans la bibliothèque réutilisable est un squelette abstrait — durées,
courbes, types, ratios — jamais une phrase, un nom ou un visuel du créateur analysé.
C'est une nécessité technique (la transférabilité) **et** la principale protection
juridique du produit.

**c) Ancrer le niveau 2 sur le niveau 1.**
Le LLM ne doit jamais produire un chiffre qu'un outil sait mesurer. Il reçoit les
mesures et il les interprète. Règle dans le prompt et assertion en test :
toute valeur numérique de la sortie doit être traçable à une mesure d'entrée.

---

## 1.7 Verdict de faisabilité

| Brique du brief | Verdict | Confiance |
|---|---|---|
| Hook (détection + typage) | ✅ faisable | 75–85 % |
| Rythme / durée de scène / découpage | ✅ **très fiable** | 90–96 % |
| Débit narratif | ✅ **très fiable** | 95 % |
| CTA (type + position) | ✅ faisable | 80–90 % |
| Arc émotionnel | ⚠️ **à recadrer** — dériver de courbes mesurées | 50–65 % en LLM pur |
| Transfert de structure vers un autre sujet | ✅ faisable — c'est le cœur de valeur | — |
| Prédiction de viralité | ❌ **hors de portée** | — |

**Conclusion.** Le produit est faisable. Sa valeur réelle est de transformer une vidéo
admirée en **cahier des charges de production réutilisable**, puis de l'exécuter
automatiquement — pas de prédire un succès.

C'est moins vendeur sur une landing page. C'est infiniment plus défendable devant un
utilisateur qui compare 10 analyses, devant un concurrent, et devant un avocat.

---

## 1.8 Le test à faire avant d'écrire l'architecture

**Trois jours, aucun code applicatif, aucun abonnement.**

1. Prendre **20 vidéos TikTok** de ta niche cible (formats variés, dont 2 carrousels photo).
2. Faire tourner à la main : `ffprobe`, PySceneDetect, Whisper, librosa. Tout est gratuit et local.
3. Annoter à la main le type de hook, les actes et le CTA sur ces 20 vidéos.
4. Passer les mêmes vidéos dans **deux modèles différents** pour le niveau 2 et mesurer l'accord.
5. Vérifier trois chiffres :

| Mesure | Seuil d'acceptation |
|---|---|
| Détection de coupes vs comptage manuel | **> 90 %** |
| Accord LLM vs ton annotation sur le type de hook | **> 75 %** |
| Accord entre les deux modèles sur l'arc émotionnel | **> 60 %**, sinon on ne l'affiche pas comme un fait |

Si les deux premiers seuils tombent, le produit ne repose sur rien et il faut le savoir
maintenant. S'ils passent, tout le reste de l'architecture est de l'ingénierie ordinaire.

**Ce test conditionne tout ce qui suit.** Je ne recommande d'engager ni le budget de
200 €/mois ni six semaines de développement avant d'avoir ces trois chiffres.
