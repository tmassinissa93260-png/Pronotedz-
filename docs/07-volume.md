# 07 — Tenir le rythme : 120 vidéos par mois

## Le vrai problème n'est pas l'argent

À 120 vidéos/mois, le budget tient sans difficulté (38 € de marge en config équilibrée).
Le calcul tient. La machine tient.

**Ce qui ne tient pas, c'est toi.**

```
120 vidéos × 3 validations = 360 décisions par mois
                           = 12 décisions par jour
                           = ~25 min/jour à valider
                           = 12 h/mois passées à cliquer
```

Et ce sont des vidéos de 90 secondes : rien que **regarder** les 120 vidéos finies,
c'est 3 heures. Plus lire 120 scripts. Plus vérifier 1 440 images.

C'est ça, la vraie contrainte. Tout le reste est un détail.

---

## Ce que ça change dans l'outil

### 1. Validation par lot, pas une par une

Une page où je vois **10 scripts d'un coup**, et je traite tout en un passage :

```
┌─ 10 scripts en attente ──────────────────────── tout valider ─┐
│                                                                │
│  ☑  Muscu · 3 erreurs de débutant          92s  ~0,15 €   ▸   │
│  ☑  Cuisine · pourquoi tes pâtes collent   87s  ~0,14 €   ▸   │
│  ☐  Finance · l'erreur du livret A         95s  ~0,15 €   ▸   │  ← à revoir
│  ☑  Muscu · le mythe des abdos             78s  ~0,13 €   ▸   │
│  ✗  Voyage · trop générique                        rejeté     │
│  ...                                                           │
│                                                                │
│  [ ▸ ] déplie le script complet et permet de le corriger      │
└────────────────────────────────────────────────────────────────┘
```

Passer de « 1 écran par vidéo » à « 1 écran pour 10 » divise le temps par 3 ou 4.
C'est la fonctionnalité la plus rentable de tout le projet.

### 2. Les validations passent de 3 à 2 (voire 1)

À ce rythme, valider le découpage image par image n'a plus de sens.

| Validation | À 30 vidéos/mois | À 120 vidéos/mois |
|---|---|---|
| **Script** | oui | **oui, par lot de 10** — c'est là que tout se joue |
| **Découpage / images** | oui | **auto**, sauf si le contrôle qualité râle |
| **Vidéo finale** | oui | **oui, par lot** — lecture rapide, 4 vidéos par écran |

Le script reste la validation clé : corriger un script coûte 0 €, corriger une vidéo
montée coûte une régénération complète.

### 3. Le mode lot devient la façon normale de travailler

```bash
# Je donne mes 10 idées de la semaine, il prépare tous les scripts
pdz batch scripts idees-semaine.txt

# Je valide les 10 scripts en un passage (~8 min)
# → localhost:7777

# Il fabrique tout pendant la nuit
pdz batch build --nuit

# Le matin, je regarde et je valide
pdz batch review
```

Trois moments dans la semaine au lieu de 120 interruptions.

### 4. Une file d'attente, pas 120 lancements

L'outil garde une file. Je remplis quand j'ai des idées, il consomme à son rythme.
Si je valide 30 scripts le dimanche, il en monte 4 par nuit pendant une semaine —
sans saturer ma machine ni mon budget journalier.

---

## Ce que ça change dans les vidéos elles-mêmes

Une vidéo de 90 s n'est pas une vidéo de 30 s en plus long. La difficulté est différente.

| | 30 s | 90 s |
|---|---|---|
| Le problème | accrocher | **garder** |
| Structure | accroche → point → chute | accroche → **3 à 4 chapitres** → chute |
| Ce qui fait décrocher | l'accroche est ratée | ça traîne au milieu |
| Technique clé | le hook | **les relances** toutes les 15-20 s |

**Conséquence sur la recette virale** : pour les vidéos longues, elle doit capturer
les **relances** — les moments où la vidéo repart (nouvelle question, retournement,
changement de rythme, promesse d'une révélation à venir). Sans ça, la structure
générée s'affaisse au milieu.

C'est déjà dans le schéma de la recette (`structure.beats`, `open_loops`), mais ça
devient le champ le plus important au lieu d'un détail. L'agent Script devra être
explicitement contraint : « place une relance toutes les 18 secondes ».

---

## Le contrôle qualité automatique devient obligatoire

À 4 vidéos par jour, je ne peux plus tout vérifier à l'œil. L'agent 12 doit bloquer
tout seul ce qui est manifestement raté :

| Vérification | Seuil de rejet automatique |
|---|---|
| Durée | hors de la fourchette 60-120 s |
| Son | silence > 2 s, volume hors norme |
| Images | image noire, image dupliquée à l'identique |
| Sous-titres | décalage > 300 ms avec la voix |
| Lisibilité | texte hors zone de sécurité TikTok |
| Rythme | un plan qui dure > 8 s (ça traîne) |
| Cohérence | une scène sans image associée |

Une vidéo qui échoue **ne m'est jamais présentée** : elle est relancée automatiquement,
ou mise de côté avec la raison. Ça m'évite de perdre du temps sur des ratés évidents.

---

## Le planning réaliste d'une semaine

| Quand | Quoi | Temps |
|---|---|---|
| **Dimanche soir** | Je note 30 idées, ou je choisis 30 recettes à appliquer | 30 min |
| **Lundi matin** | Je valide 30 scripts par lots de 10 | 25 min |
| **Chaque nuit** | La machine monte 4 à 5 vidéos | 0 min (je dors) |
| **Mardi → samedi** | Je regarde et valide les vidéos de la veille, par lot | 10 min/jour |
| **Total** | **30 vidéos/semaine ≈ 120/mois** | **~2 h/semaine** |

2 heures par semaine pour 30 vidéos publiables. C'est ça, l'objectif réel du projet.
Si l'outil demande plus de 2 h/semaine, il a raté sa cible — même s'il marche techniquement.

---

## Ce que j'ajoute au plan à cause du volume

Ces éléments passent de « plus tard » à **v1** :

| Fonction | Pourquoi c'est devenu indispensable |
|---|---|
| **Validation par lot** | sinon 12 h/mois de clics |
| **Mode nuit** (`--nuit`) | sinon ma machine est bloquée en journée |
| **File d'attente** | sinon je dois lancer 120 fois une commande |
| **Contrôle qualité bloquant** | sinon je regarde des vidéos ratées |
| **Réutilisation d'images + b-roll** | sinon le budget images explose |
| **Relances dans le script** | sinon les vidéos longues s'affaissent au milieu |

En échange, ceux-ci passent en « plus tard » :

| Reporté | Pourquoi |
|---|---|
| Validation du découpage image par image | trop lent à ce rythme |
| Édition fine des sous-titres dans l'interface | le contrôle auto suffit dans 95 % des cas |
| Choix manuel de la musique | tirage automatique selon l'émotion de la recette |

Le plan ([06](./06-plan.md)) est mis à jour en conséquence : le mode lot arrive dès
l'étape 4, et l'étape 2 (qualité vidéo) intègre la réutilisation d'images.
