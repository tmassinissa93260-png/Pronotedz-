# Faire tourner Pronotedz sans ordinateur

> Ton PC ne marche pas. Voilà les quatre solutions, de la plus simple à la
> plus lourde. **La première ne demande rien d'autre que ton téléphone.**

| | Ce qu'il faut | Coût | Ça vaut quoi |
|---|---|---|---|
| **1. GitHub Actions** | rien, juste ton téléphone | 0 € | ⭐ à faire en premier |
| **2. Termux (Android)** | un téléphone Android | 0 € | vraiment local, un peu technique |
| **3. Un petit serveur** | une carte bancaire | ~5 €/mois | le mieux si tu produis tous les jours |
| **4. iPhone tout seul** | — | — | ❌ impossible, voir plus bas |

---

# 1. GitHub Actions — la solution à essayer d'abord

GitHub prête des ordinateurs pour faire tourner du code. Le programme est
déjà chez eux : il suffit de leur demander de le lancer. **Tout se fait depuis
ton téléphone**, et la vidéo t'attend à la fin.

## Étape 1 — Mettre tes clés en lieu sûr (une seule fois)

⚠️ **L'app GitHub ne permet pas d'ajouter des clés.** Il faut passer par le
navigateur de ton téléphone, en mode ordinateur.

1. Ouvre **Chrome** (ou Safari) sur ton téléphone
2. Va sur `github.com/tmassinissa93260-png/Pronotedz-`
3. Menu ⋮ → coche **« Site pour ordinateur »** (Safari : « aA » → « Version
   pour ordinateur »)
4. **Settings** → à gauche **Secrets and variables** → **Actions**
5. Bouton **New repository secret**, et tu ajoutes une par une :

| Name | Secret |
|---|---|
| `ANTHROPIC_API_KEY` | ta clé Anthropic |
| `FAL_KEY` | ta clé fal.ai |
| `ELEVENLABS_API_KEY` | ta clé ElevenLabs |
| `AUDD_API_KEY` | ta clé AudD (facultatif) |

Ces clés sont chiffrées par GitHub. Elles n'apparaissent jamais dans le code,
jamais dans les journaux, et personne d'autre que toi ne peut les relire —
même toi, tu ne peux que les remplacer.

## Étape 2 — Vérifier que tout est branché

1. Onglet **Actions** (dans l'app GitHub ou dans le navigateur)
2. À gauche, **Produire** → bouton **Run workflow**
3. Dans *Ce que je veux faire*, choisis **`cles`**
4. **Run workflow**

Attends une minute, ouvre le lancement : le résumé te dit, service par
service, ce qui fonctionne. **Ce test ne coûte rien.**

## Étape 3 — Donner une voix à tes personnages (une fois par univers)

Même chemin, mais choisis **`voix`** et laisse `fruit-island` dans *Univers*.

Le programme essaie les voix de ton compte ElevenLabs, mesure chacune, et
garde la plus adaptée à chaque personnage. **Le résultat est enregistré dans
le dépôt automatiquement** — tu n'as rien à recopier.

## Étape 4 — Faire un épisode

**Actions** → **Produire** → **Run workflow** :

- *Ce que je veux faire* : `episode`
- *Univers* : `fruit-island`
- *Ce qui se passe* : `Strawberina découvre que Bananito a triché`
- *Durée* : `45`
- *Qualité* : `economique` pour un premier essai

Compte 5 à 15 minutes. Quand la coche verte apparaît, ouvre le lancement :

- le **résumé** te montre le script écrit et ce que ça a coûté ;
- tout en bas, **Artifacts** → **video-3** → la vidéo se télécharge sur ton
  téléphone.

## Étape 5 — Partir d'une vidéo que tu aimes

Le téléphone ne peut pas envoyer un fichier directement au workflow. Deux
moyens de lui donner ta vidéo :

**A. Un lien direct.** Mets la vidéo sur Google Drive ou Dropbox, récupère un
lien de **téléchargement direct** (Dropbox : remplace `?dl=0` par `?dl=1`), et
colle-le dans *Vidéo de référence*.

**B. La déposer dans le dépôt.** Depuis le navigateur en mode ordinateur :
dossier `donnees/sources` → **Add file** → **Upload files**. Puis écris
`donnees/sources/ma-video.mp4` dans *Vidéo de référence*.

Ensuite tu peux lancer `analyser` (mesurer sa forme), `musique` (reconnaître
la musique) ou `charte` (en faire un univers avec ses personnages).

## Ce qu'il faut savoir

- **Le temps de calcul est gratuit** si ton dépôt est public, et limité à
  2 000 minutes par mois s'il est privé. Un épisode prend 5 à 15 minutes :
  largement de quoi tenir tes 30 épisodes mensuels.
- **Les clés d'API, elles, sont payantes comme d'habitude.** GitHub prête la
  machine, pas les crédits Claude ou fal.ai.
- **Le cache est conservé d'un lancement à l'autre** : une image ou une voix
  déjà payée n'est jamais refacturée.
- **Une seule production à la fois.** Si tu relances pendant qu'un épisode se
  fabrique, le second attend son tour.
- Les vidéos restent téléchargeables **30 jours**. Passé ce délai, il faut
  relancer — ou mieux, les enregistrer sur ton téléphone au fur et à mesure.

---

# 2. Termux — le programme vraiment sur ton téléphone Android

Ça marche pour de bon : Python, ffmpeg et le montage tournent sur le
téléphone. Compte 20 minutes d'installation.

⚠️ **Installe Termux depuis [F-Droid](https://f-droid.org/packages/com.termux/),
pas depuis le Play Store** — la version du Play Store n'est plus mise à jour
et ne peut plus rien installer.

```bash
pkg update && pkg upgrade -y
pkg install -y python ffmpeg git libjpeg-turbo
pip install --upgrade pip
```

```bash
git clone https://github.com/tmassinissa93260-png/Pronotedz-.git
cd Pronotedz-
pip install -e .
```

Si `numpy` ou `Pillow` refusent de s'installer :

```bash
pkg install -y python-numpy python-pillow
pip install -e . --no-deps
pip install typer rich httpx pydantic pydantic-settings PyYAML jinja2 jsonschema
```

Tes clés :

```bash
cp .env.exemple .env
nano .env        # colle chaque clé après le =, puis Ctrl+O, Entrée, Ctrl+X
pdz cles
```

Et pour produire :

```bash
pdz voix apparier fruit-island
pdz episode fruit-island "Strawberina découvre la triche"
```

Les vidéos sortent dans `donnees/sorties/`. Pour les voir dans ta galerie :

```bash
termux-setup-storage       # accepte la demande
cp donnees/sorties/*.mp4 ~/storage/movies/
```

**Ce qui va coincer :** le rendu d'un épisode de 45 secondes prend 1 à 3
minutes sur un téléphone récent, bien plus sur un vieux. Le téléphone chauffe.
Et si Android tue Termux pendant le rendu, relance avec
`pdz reprendre <job>` — rien n'est perdu ni repayé.

---

# 3. Un petit serveur — si tu produis tous les jours

Environ 5 €/mois chez Hetzner, Scaleway ou OVH. Le projet a déjà tout ce
qu'il faut (`Dockerfile`, `docker-compose.yml`) :

```bash
git clone https://github.com/tmassinissa93260-png/Pronotedz-.git
cd Pronotedz- && cp .env.exemple .env && nano .env
docker compose run --rm pdz pdz cles
docker compose run --rm pdz pdz episode fruit-island "mon sujet"
```

Tu le pilotes depuis ton téléphone avec une app SSH (**Termius** ou
**JuiceSSH** sur Android, **Termius** sur iPhone).

C'est la solution la plus confortable sur la durée, mais c'est la seule qui
demande une carte bancaire et un peu d'administration.

---

# 4. iPhone seul — non, et voici pourquoi

Ce n'est pas de la mauvaise volonté : iOS interdit à une application de
lancer d'autres programmes. Or Pronotedz appelle **ffmpeg** en permanence —
pour les mesures, la voix, le montage. Des applications comme *a-Shell*
embarquent bien Python et ffmpeg, mais elles ne peuvent pas les faire
communiquer comme le programme en a besoin.

**Sur iPhone, prends la solution 1.** Elle marche parfaitement depuis Safari
et l'app GitHub, et tu récupères la vidéo dans tes fichiers.

---

# Récapitulatif

| Tu as… | Fais… |
|---|---|
| n'importe quel téléphone | **solution 1 — GitHub Actions** |
| un Android et l'envie de bidouiller | solution 2 — Termux |
| besoin d'en faire tous les jours | solution 3 — un petit serveur |
| un iPhone | solution 1, la 2 est impossible |

Et quoi qu'il arrive : **ne colle jamais tes clés dans une conversation ni
dans un fichier du dépôt.** Elles vivent dans les Secrets GitHub ou dans
`.env` sur ta machine, nulle part ailleurs.
