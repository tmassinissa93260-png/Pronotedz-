# 04 — Ce qui rend l'outil solide

Cinq mécanismes. Ce sont les seuls morceaux « sérieux » que j'ai gardés de la version
SaaS, parce qu'ils servent autant à une personne qu'à mille.

---

## 1. Reprise après plantage

**Le problème** : une vidéo prend 5 minutes et ~0,40 €. Si ça plante à l'étape 9 sur 12,
je ne veux pas tout recommencer ni repayer.

**La solution** : chaque étape terminée est enregistrée dans SQLite avec son résultat.

```
job_42 · étapes
─────────────────────────────────────────────
 1  angle              ✅ terminé   0,004 €
 2  script             ✅ terminé   0,031 €
 3  validation script  ✅ validé
 4  découpage          ✅ terminé   0,007 €
 5  images             ✅ terminé   0,184 €
 6  voix               ✅ terminé   0,090 €
 7  sous-titres        ✅ terminé   0,000 €
 8  montage            ❌ PLANTÉ    (ffmpeg : plus d'espace disque)
 9  contrôle           ⏸ en attente
```

`pdz resume 42` → il refait le parcours, saute les 7 étapes déjà faites,
et **repart à l'étape 8**. Coût de la reprise : 0 €.

Ça marche même si j'ai éteint l'ordinateur, mis à jour le programme, ou attendu 3 jours.
Le moteur ne « se souvient » pas de où il en était : il **relit** ce qui est fait et
en déduit ce qui reste.

---

## 2. Ne jamais payer deux fois

Chaque étape a une empreinte calculée à partir de :

```
empreinte = ce_qui_entre + version_du_prompt + modèle_utilisé
```

Si l'empreinte existe déjà → on ressort le résultat sauvegardé, **sans appeler l'IA**.

**Ce que ça change dans la vraie vie :**

| Situation | Sans cache | Avec cache |
|---|---|---|
| Je corrige une faute dans les sous-titres | 0,40 € | **0,00 €** (seul le montage est refait) |
| Je change la musique | 0,40 € | **0,00 €** |
| Je refais une seule image sur 8 | 0,40 € | **0,023 €** |
| Je réécris le script (le reste suit) | 0,40 € | 0,31 € |
| J'analyse deux fois la même vidéo | 0,12 € | **0,06 €** |

Et si je change le prompt du script, l'empreinte change toute seule → le cache se
renouvelle sans que j'aie rien à purger. C'est automatique.

**Bonus** : Claude sait mettre en cache les longs bouts de prompt qui ne changent pas
(mes règles, mon ton, la recette utilisée). Environ **−40 % sur le coût d'écriture**
quand je génère plusieurs vidéos d'affilée.

---

## 3. Quand ça plante

Chaque erreur tombe dans une catégorie, et la catégorie décide de la réaction :

| Type d'erreur | Exemple | Réaction |
|---|---|---|
| **Réseau** | timeout, coupure | on réessaie 3× (2 s, 4 s, 8 s) |
| **Trop de requêtes** | l'API dit « ralentis » | on attend le délai indiqué, puis on bascule sur le modèle de repli |
| **Fournisseur en panne** | fal.ai ne répond plus | bascule immédiate sur le repli |
| **Réponse mal formée** | l'IA rend un JSON cassé | on relance en lui montrant son erreur (marche 8 fois sur 10) |
| **Refus du modèle** | contenu bloqué | on s'arrête et on me prévient — inutile d'insister |
| **Plus de budget** | plafond atteint | on s'arrête proprement |
| **Bug dans mon code** | erreur Python | on s'arrête, trace complète dans le log |

**Plafond global** : maximum 3 essais par étape **et** un plafond total par vidéo.
Sans ce deuxième plafond, une boucle infinie peut vider un mois de budget en une nuit.
C'est le scénario le plus probable de perte d'argent sur ce projet.

**Dégradation plutôt qu'échec** — dans l'ordre :
1. Modèle moins cher (Sonnet → Haiku)
2. Images moins belles (FLUX dev → schnell)
3. Voix gratuite au lieu d'ElevenLabs
4. Moins de scènes, plans plus longs
5. Livraison sans musique ni transitions

À chaque fois, c'est **marqué visiblement** sur la vidéo dans `pdz list`.
Une dégradation silencieuse, c'est un bug : je dois savoir que ce n'est pas la qualité max.

---

## 4. Les prompts sont versionnés

Un prompt = un fichier, avec un numéro de version :

```yaml
# pdz/prompts/catalogue/creation/script@3.0.0.yaml
id: creation/script
version: 3.0.0
modele_conseille: qualite
temperature: 0.8

entrees:
  angle:    { requis: oui }
  recette:  { requis: non }

messages:
  - role: system
    contenu: |
      Tu écris des scripts de vidéos courtes.
      RÈGLES :
      1. Chaque scène tient en une phrase dite à voix haute.
      2. Respecte exactement le nombre de mots par scène imposé.
      3. Pas de superlatif creux, pas de « dans cette vidéo je vais vous montrer ».
  - role: user
    contenu: |
      ANGLE : {{ angle }}
      {% if recette %}CONTRAINTES : {{ recette }}{% endif %}

historique: |
  3.0.0 — scènes plus courtes, accroches nettement meilleures
  2.1.0 — ajout des contraintes de recette
```

**Pourquoi c'est utile même seul :**

- Je modifie un prompt, les vidéos deviennent moins bonnes → je remets la version d'avant. **Une commande, 10 secondes.**
- Je retrouve une vidéo réussie d'il y a 2 mois → la base me dit exactement quel prompt et quel modèle l'ont produite. Je peux le refaire.
- Je compare deux formulations sur les mêmes idées, avec les coûts en face.

C'est la différence entre bricoler et progresser : sans versionnement, au bout de
50 modifications, on ne sait plus ce qui marchait.

---

## 5. Savoir où part l'argent

Chaque appel à une IA écrit une ligne dans SQLite : quelle étape, quel modèle,
combien de jetons, combien ça a coûté, combien de temps.

```
$ pdz cost --mois

  Août 2026                         31,42 €  /  80,00 €   [████░░░░░░] 39 %

  Par usage
    Images (FLUX dev)               14,72 €   47 %  ← le plus gros poste
    Voix (ElevenLabs)                8,10 €   26 %
    Écriture (Sonnet)                6,20 €   20 %
    Analyse vidéo (Haiku)            2,40 €    7 %

  74 vidéos · 0,42 € en moyenne
  Économisé par le cache : 11,80 €   ← 27 % de dépense évitée

  💡 Passer en FLUX schnell : −0,16 €/vidéo (−38 %)
```

Sans ça, je découvre le problème sur mon relevé bancaire. Avec ça, je le vois le jour même.

**Un garde-fou automatique** : à 95 % du budget mensuel, il refuse de lancer une nouvelle
vidéo et me le dit clairement. Je peux forcer avec `--force` si j'assume.
