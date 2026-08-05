# Point de situation — 1 page

## ✅ Ce qui marche déjà

| | Détail |
|---|---|
| **Ton workflow n8n** | idée → recherche → script → images → vidéo. Il tourne. |
| **Le rendu vidéo** | C'est la partie la plus dure techniquement. Elle est réglée. |
| **La validation humaine** | Tu valides déjà le script avant la vidéo. |
| **Mesurer une vidéo** | Durée des plans, nombre de coupes, débit de parole, rythme : **fiable à 90–96 %**, et **gratuit** (pas d'IA, juste des outils de calcul). |

**Tu es plus avancé que la plupart des gens qui démarrent ce genre de projet.**

---

## 🔴 Ce qui bloque vraiment (1 seul point)

### Ton gabarit a 4 cases. Il en faut 18.

```
Ton système aujourd'hui  :  4 images  →  4 plans  →  ~27 secondes
Une vraie vidéo TikTok   : 18 plans   →  2,5 s chacun  →  90 secondes
```

Tu peux **analyser** une vidéo. Tu ne peux pas **appliquer** ce que tu as trouvé.
C'est comme lire une recette de cuisine avec une casserole trop petite.

**C'est le seul blocage sérieux du projet.** Tout le reste est du réglage.

---

## 💡 La solution

Ton outil de rendu a sûrement **deux façons de fonctionner** :

| Mode | Ce que ça donne |
|---|---|
| **Fichier CSV** *(ce que tu fais)* | nombre de plans **figé** par le gabarit |
| **Envoi direct (API)** | tu décides du nombre de plans, **autant que tu veux** |

Passer de l'un à l'autre, **ce n'est pas tout refaire**. C'est changer la dernière étape
du workflow. Tes prompts restent bons à 80 %.

**→ La chose à vérifier cette semaine** : ouvre n8n, regarde le nœud juste après celui
qui fabrique le `.csv`, et note le nom ou l'adresse. Ça donne la réponse.

---

## 🟠 Deux limites à connaître (pas des bugs, des faits)

**1. On ne saura jamais *pourquoi* une vidéo a marché.**
Tu n'analyses que des vidéos qui ont réussi. Sans exemples d'échecs, impossible de dire
si « 18 plans de 2,5 s » est la *cause* du succès, ou juste la norme du format.

→ **Ce que tu vends** : « reproduis la forme des vidéos qui marchent ».
→ **Ce que tu ne peux pas promettre** : « on sait pourquoi elles marchent ».

**2. L'« arc émotionnel » n'est pas fiable** (50–65 %).
Deux IA différentes donnent deux réponses différentes sur la même vidéo.

→ **Solution** : le déduire de courbes **mesurées** (énergie du son, densité de coupes,
variations de débit) au lieu de le demander à l'IA. L'IA commente ce qui est mesuré,
elle n'invente pas.

---

## 🟡 Trois petits trucs à corriger (rapide)

| Problème | Pourquoi ça compte | Solution |
|---|---|---|
| `data[6]` / `data[5]` | Si quelqu'un déplace une ligne de config, tous tes prompts reçoivent les mauvaises valeurs **sans erreur**. Et il y a déjà une incohérence entre deux prompts. | Appeler par nom, pas par numéro |
| Le CSV fabriqué par l'IA | Tes textes contiennent des virgules et apostrophes. Un jour l'IA fera une erreur de format et le rendu cassera sans message clair. | Un nœud « Code » — gratuit, jamais faux |
| Aucun suivi de coût | Tu découvriras le prix d'une vidéo sur ton relevé bancaire | Une petite table qui enregistre chaque appel |

---

## En résumé

> **Un seul vrai blocage : le gabarit à 4 cases.**
> **Il a une solution, et elle ne demande pas de tout refaire.**
>
> Le reste, ce sont deux limites à assumer dans ton discours commercial,
> et trois corrections d'une heure.

**La prochaine action** : trouver le nom de ton outil de rendu dans n8n.
