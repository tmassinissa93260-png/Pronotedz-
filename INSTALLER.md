# Installer sur ta machine

> Sur ta machine, **rien n'est bloqué**. Tes clés fonctionnent, l'outil appelle
> Claude, fal.ai et ElevenLabs directement, et tout tourne tout seul.

Compte **20 minutes** la première fois.

---

## 1. Installer Docker

Docker embarque Python, ffmpeg et les polices : tu n'as rien d'autre à installer.

| | |
|---|---|
| **Mac** | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop) → télécharge, ouvre, glisse dans Applications |
| **Windows** | même lien → installe, redémarre |
| **Linux** | `curl -fsSL https://get.docker.com \| sh` |

**Lance Docker Desktop** et laisse-le ouvert. Tu dois voir la baleine 🐳 dans la barre du haut.

---

## 2. Récupérer le projet

Ouvre le **Terminal** (Mac : `Cmd + Espace` puis « Terminal ») et colle :

```bash
git clone https://github.com/tmassinissa93260-png/Pronotedz-.git
cd Pronotedz-
```

---

## 3. Mettre tes clés

```bash
cp .env.exemple .env
open .env          # Mac    (Windows : notepad .env)
```

Colle chaque clé **après le signe `=`**, sans rien d'autre :

```
ANTHROPIC_API_KEY=sk-ant-api03-abc123...
FAL_KEY=abc123...
ELEVENLABS_API_KEY=sk_abc123...
```

### ⚠️ Les trois erreurs qui font tout planter

```
❌  ANTHROPIC_API_KEY = sk-ant-abc      ← espaces autour du =
❌  ANTHROPIC_API_KEY="sk-ant-abc"      ← guillemets
❌  ANTHROPIC_API_KEY=sk-ant-abc  # ma clé   ← commentaire sur la même ligne

✅  ANTHROPIC_API_KEY=sk-ant-abc
```

Le commentaire sur la même ligne est le plus vicieux : il est lu **comme faisant
partie de la clé**, et le message d'erreur ne le dit pas. Les commentaires vont
toujours sur leur propre ligne.

**Enregistre et ferme le fichier.**

---

## 4. Vérifier que les clés marchent

```bash
docker compose run --rm pdz pdz cles
```

La première fois, Docker télécharge et construit — compte 3 à 5 minutes. Ensuite c'est instantané.

Tu dois voir :

```
  Vérification des clés — aucun coût, aucune génération

  Anthropic    les scripts                    ✓ fonctionne
  fal.ai       les images et l'animation      ✓ fonctionne
  ElevenLabs   la voix                        ✓ fonctionne  formule free · 9 500 caractères restants

  Tout est prêt.
```

Ce test **ne coûte rien** : il lit les quotas, il ne génère rien.

### Si une clé échoue

| Message | Ce qu'il faut faire |
|---|---|
| `non renseignée` | Tu ne l'as pas collée, ou tu as laissé le texte d'exemple |
| `clé refusée` | Mauvaise clé, ou espace/guillemet resté au copier-coller |
| `AUCUN CRÉDIT` | La clé est bonne, mais le compte est vide → onglet **Billing** |
| `caractère accentué dans la clé` | Tu as collé un commentaire avec la clé (voir étape 3) |

---

## 5. Fabriquer une vidéo

D'abord un test **sans aucune IA ni dépense**, pour vérifier que ffmpeg marche :

```bash
docker compose run --rm pdz python tools/demo_montage.py
# ta vidéo apparaît dans  donnees/sorties/
```

Ensuite, chaque personnage a besoin d'une voix. Une seule fois par univers :

```bash
docker compose run --rm pdz pdz voix apparier fruit-island
```

Puis un vrai épisode :

```bash
docker compose run --rm pdz pdz episode fruit-island "Strawberina trahit Bananito"
```

Tes fichiers sortent dans le dossier **`donnees/sorties/`** de ton ordinateur.

### Si ça s'arrête en cours de route

Coupure de réseau, quota atteint, ordinateur éteint : rien n'est perdu.

```bash
docker compose run --rm pdz pdz jobs          # retrouve l'identifiant
docker compose run --rm pdz pdz reprendre job_a1b2c3
```

La reprise **ne repaie pas** ce qui est déjà fait : le script, la voix et les
images déjà produites sont relus depuis la base.

---

## 6. Partir d'une vidéo que tu aimes

```bash
# Mesurer sa forme — quelques secondes, 0 €
docker compose run --rm pdz pdz analyser donnees/sources/ma-reference.mp4

# En tirer un univers jouable : style, personnages, décors
docker compose run --rm pdz pdz charte donnees/sources/ma-reference.mp4 --id mon-monde

# Des voix qui ressemblent à celles de la référence
docker compose run --rm pdz pdz voix apparier mon-monde --source donnees/sources/ma-reference.mp4

# Produire sur TON sujet, avec SA forme
docker compose run --rm pdz pdz episode mon-monde "ton sujet" --forme str_a1b2c3
```

Les personnages sont **transposés**, pas recopiés : le système garde l'archétype
et le style graphique, et change ce qui identifie. Voir
[docs/14](./docs/14-reproduire-un-style.md).

---

## 7. Reconnaître la musique d'une vidéo

```bash
docker compose run --rm pdz pdz musique donnees/sources/ma-video.mp4
```

Le tempo, la tonalité et les passages sans parole sortent toujours, sans
aucune clé. Pour avoir le **titre** du morceau en plus, crée une clé gratuite
sur [audd.io](https://audd.io) (300 identifications offertes) et colle-la
dans `.env` sous `AUDD_API_KEY`.

---

## 8. Savoir ce qui marche vraiment

Une fois tes épisodes publiés, c'est ton propre compte qui détient la vérité —
personne d'autre n'a accès à ta courbe de rétention.

```bash
# après avoir publié
docker compose run --rm pdz pdz resultats publie job_a1b2c3 --url https://...

# TikTok Studio → Analytiques → exporter en CSV, puis
docker compose run --rm pdz pdz resultats importer donnees/export.csv
docker compose run --rm pdz pdz resultats bilan
```

Sous 10 épisodes publiés, le programme refuse de conclure quoi que ce soit :
en dessous, l'écart entre deux groupes est du hasard.

---

## Suivre la dépense

```bash
docker compose run --rm pdz pdz cout          # par modèle, par agent
docker compose run --rm pdz pdz web           # puis http://127.0.0.1:7777
```

---

## Ce qui reste chez toi

| Dossier | Contenu |
|---|---|
| `donnees/sorties/` | 📹 tes vidéos finies |
| `donnees/pronotedz.db` | la base — **le seul fichier à sauvegarder** |
| `.env` | tes clés — **jamais sur GitHub** |
| `univers/` | tes personnages et tes styles |
| `modeles.yaml` | quel modèle IA pour quoi |

---

## Sans Docker

Si tu préfères, il faut Python 3.11+ et ffmpeg installés :

```bash
brew install python ffmpeg      # Mac
pip install -e .
pdz cles
```

---

## Deux règles de sécurité

1. **Mets un plafond de dépense** sur chaque compte (onglet *Billing* ou *Limits*).
   Même en cas de bug, tu ne peux pas perdre plus que ce plafond.
2. **Ne colle jamais tes clés dans une conversation.** Elles vivent dans `.env`,
   sur ta machine, et nulle part ailleurs.
