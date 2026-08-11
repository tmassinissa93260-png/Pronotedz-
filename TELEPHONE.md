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
navigateur de ton téléphone.

### Le raccourci

Colle cette adresse dans ton navigateur — elle t'amène pile sur la bonne
page, sans avoir à chercher dans les menus :

```
github.com/tmassinissa93260-png/Pronotedz-/settings/secrets/actions
```

Puis bouton vert **New repository secret**, et tu ajoutes une clé par une :

| Name | Secret |
|---|---|
| `ANTHROPIC_API_KEY` | ta clé Anthropic |
| `FAL_KEY` | ta clé fal.ai |
| `ELEVENLABS_API_KEY` | ta clé ElevenLabs |
| `AUDD_API_KEY` | ta clé AudD (facultatif) |
| `GROQ_API_KEY` | ta clé Groq (facultatif — voir encadré ci-dessous) |

Ces clés sont chiffrées par GitHub. Elles n'apparaissent jamais dans le code,
jamais dans les journaux, et personne d'autre que toi ne peut les relire —
même toi, tu ne peux que les remplacer.

> **Pas envie de payer pour Anthropic tout de suite ?**
> Contrairement à l'appli où tu me parles, la Console Anthropic
> (`console.anthropic.com`) n'a pas d'offre gratuite — il faut au moins
> quelques euros de crédit (Billing) pour que `ANTHROPIC_API_KEY` fonctionne.
>
> Si tu veux produire des épisodes **sans rien payer et sans carte
> bancaire**, crée une clé sur `console.groq.com` (gratuite, aucune carte
> demandée), ajoute-la comme `GROQ_API_KEY`, et lance tes épisodes avec
> **`--profil gratuit`** (étape 4). Ce profil écrit avec Llama à la place de
> Claude, et illustre avec Pollinations (aucune clé, aucune inscription) à
> la place de fal.ai — tu n'as alors ni `ANTHROPIC_API_KEY` ni `FAL_KEY` à
> renseigner du tout.
>
> Deux limites à connaître : l'écriture est probablement un peu moins fine,
> et les personnages sont moins constants d'un plan à l'autre qu'avec fal.ai
> (Pollinations ne prend pas d'image de référence). Tout le reste — écrire,
> dire, illustrer, monter, **et analyser une vidéo de référence** — marche
> normalement : la vision passe par un second modèle Groq, choisi
> automatiquement (voir l'étape 5).
>
> Déjà de la carte sur fal.ai mais pas encore sur Anthropic ? Le profil
> **`hybride`** écrit gratuitement avec Groq et illustre avec fal.ai — de
> meilleures images et des personnages plus constants que `gratuit`, sans
> attendre d'avoir du crédit Claude.

### Si la page est trop serrée : le mode ordinateur

Sur un écran de téléphone, le menu de gauche de GitHub se replie et devient
difficile à trouver. Le mode ordinateur remet la mise en page complète :

| Navigateur | Où c'est |
|---|---|
| **Chrome sur Android** | les **⋮** en haut à droite → descendre → cocher **« Site pour ordinateur »** |
| **Safari sur iPhone** | le **ᴀA** à gauche de la barre d'adresse (en bas) → **« Afficher la version pour ordinateur »** |
| **Chrome sur iPhone** | les **⋯** en bas à droite → **« Demander la version pour ordinateur »** |

La page se recharge, le texte devient plus petit, et tu retrouves l'affichage
d'un ordinateur. Le même réglage sert plus loin pour déposer une vidéo ou un
export CSV dans le dépôt.

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
- *Qualité* : `economique` pour un premier essai — ou **`gratuit`** si tu n'as
  pas mis de crédit sur Anthropic (voir l'encadré de l'étape 1)

Compte 5 à 15 minutes. Quand la coche verte apparaît, ouvre le lancement :

- le **résumé** te montre le script écrit, ce que ça a coûté, et — sous
  **📹 Ta vidéo** — un **lien direct vers le .mp4**. Tu le touches, il se lit.
  C'est le chemin le plus court sur un téléphone ;
- tout en bas, **Artifacts** garde une copie en ZIP pendant 30 jours. Le lien
  direct, lui, reste dans l'onglet **Releases** du dépôt et ne disparaît pas.

## Étape 5 — Partir d'une vidéo que tu aimes

Le téléphone ne peut pas envoyer un fichier directement au workflow : il faut
un **lien direct**. Mets la vidéo sur Google Drive ou Dropbox, récupère un
lien de **téléchargement direct** (Dropbox : remplace `?dl=0` par `?dl=1`), et
colle-le dans *Vidéo de référence*.

> ⚠️ **Ne dépose jamais une vidéo de référence dans le dépôt** (dossier
> `donnees/sources` via « Add file → Upload files »). `donnees/` est ignoré
> par git en local, mais l'upload web de GitHub ne regarde pas
> `.gitignore` : le fichier serait commis pour de bon, publiquement, dans
> l'historique du dépôt. Une vidéo de référence n'est presque jamais la
> tienne — le lien direct est la seule façon de la donner au workflow sans
> la publier. (Ce garde-fou ne concerne pas le CSV d'analytics de l'étape
> « Savoir ce qui marche » plus bas : c'est ton propre export, pas le
> contenu d'un tiers.)

Ensuite tu peux lancer `analyser` (mesurer sa forme), `musique` (reconnaître
la musique) ou `charte` (en faire un univers avec ses personnages).

### Copier le **rythme** d'une vidéo — gratuit

`analyser` ne fait aucun appel à une IA : c'est de la mesure de signal.
**Aucune clé, aucun crédit, 0 €.** Il relève la durée de l'accroche, la
cadence de coupe, le débit de parole et les remontées d'énergie.

1. **Produire** → `analyser`, avec ta vidéo dans *Vidéo de référence*
2. Le résumé finit par `✓ Forme enregistrée : str_a1b2c3…` — **note cet
   identifiant**, il reste valable pour tous tes prochains épisodes
3. **Produire** → `episode`, et colle-le dans *Épouser la forme d'une vidéo
   déjà analysée*

L'épisode épouse alors le rythme de la référence, sans rien reprendre de son
contenu.

### Copier le **style visuel** — gratuit aussi

`charte` doit *regarder* les images pour décrire le style et les
personnages. Avec `GROQ_API_KEY`, le programme prend tout seul un modèle
Groq capable de vision : **aucun crédit Anthropic nécessaire**.

1. **Produire** → `charte`, ta vidéo dans *Vidéo de référence*
2. Dans *Univers*, mets l'identifiant du **nouvel** univers à créer
   (ex. `mon-univers`) — surtout pas `fruit-island`, tu l'écraserais
3. Puis `voix` sur ce nouvel univers, et enfin `episode`

Les personnages sont **transposés** : on garde l'archétype et la patte
graphique, on change ce qui identifie. Recopier un personnage protégé n'est
pas une option du programme.

> Deux limites à connaître : Groq n'accepte que 5 images par requête là où
> l'analyse en extrait 6 (la dernière est écartée, l'analyse porte donc sur
> un échantillon un peu plus étroit), et si tu as du crédit Anthropic, c'est
> Claude qui garde la main — il lit les détails de costume que le modèle
> gratuit manque.

## Étape 6 — Comparer plusieurs vidéos, et vérifier le transfert

Deux commandes de plus dans **Produire**, pour aller plus loin que « ça
marche » : vérifier que le système capture vraiment des mécaniques
différentes d'une vidéo à l'autre, et qu'un script généré sur un sujet neuf
transfère cette mécanique sans recopier le contenu de la référence.

Aucune vidéo de référence n'est jamais commise à ce dépôt — même principe
qu'à l'étape 5 (**toujours un lien direct**, jamais un upload dans
`donnees/`), mais pour plusieurs vidéos à la fois, gardées le temps de les
comparer (voir plus bas).

### Ajouter des vidéos au dossier de comparaison

1. **Produire** → `references`, ta vidéo dans *Vidéo de référence* — un
   lien direct, comme à l'étape 5
2. Dans *Univers*, donne un identifiant à CETTE vidéo (ex. `hologramme-1`)
3. Répète avec deux ou trois autres vidéos, chacune avec son propre
   identifiant

Chaque lancement charte la vidéo et la range dans `donnees/references` —
gardé par le cache d'un lancement à l'autre, jamais publié sur le dépôt. À
partir de 3 vidéos, le résumé signale les empreintes qui se ressemblent
trop (`POTENTIAL_ANALYSIS_COLLAPSE`).

> Le cache n'est pas permanent : GitHub l'évince après 7 jours d'inactivité,
> ou au-delà de 10 Go pour tout le dépôt. Une vidéo « perdue » se réajoute
> simplement en relançant `references` avec le même identifiant.

**Optionnel :** pour noter à la main, avant analyse, de quoi parlait
vraiment la vidéo — utile pour le rapport avant/après plus bas — ajoute un
fichier `donnees/references/<identifiant>.yaml` dans le dépôt (navigateur
en mode ordinateur, voir l'étape 1 : dossier `donnees/references` →
**Add file** → **Upload files**). Rien à cacher ici : ce fichier ne contient
que tes propres notes, jamais la vidéo elle-même, donc aucun souci à le
publier. Exemple de contenu :

```yaml
sujet_original: une IA qui explique la physique quantique avec un hologramme
mecanique_attendue: pose une question dans les 2 premières secondes, jamais résolue
```

Sans lui, tout marche pareil — seule la vérification de chevauchement
lexical du rapport avant/après est sautée.

### Le rapport avant/après

Une fois une référence chartée (étape précédente), donne-lui une idée
totalement neuve :

1. **Produire** → `avant-apres`
2. *Univers* : l'identifiant de la référence (ex. `hologramme-1`)
3. *Sujet* : une idée SANS RAPPORT avec la vidéo d'origine

Le résumé du lancement affiche directement le rapport : l'empreinte reçue
par le scénariste, le script généré réplique par réplique, et deux
vérifications automatiques (est-ce que chaque plan a une fonction
différente, et le script partage-t-il des mots avec le sujet original de
la référence). Le reste — est-ce que ça *marche* vraiment, mécanique
transférée sans le contenu — reste à juger toi-même : c'est écrit noir sur
blanc dans le rapport, ce n'est pas quelque chose qu'un algorithme peut
trancher à ta place.

## Si ça s'arrête en cours de route

Quota atteint, coupure, dépassement du temps imparti : **rien n'est perdu et
rien ne sera repayé**.

Le résumé du lancement raté contient une ligne du genre
`job job_a1b2c3d4e5f6`. Relance **Produire** avec :

- *Ce que je veux faire* : `reprendre`
- *Identifiant de l'épisode* : `job_a1b2c3d4e5f6`

Le script, la voix et les images déjà produits sont relus depuis la base ; la
production repart exactement là où elle s'était arrêtée.

## Savoir ce qui marche, une fois publié

1. TikTok Studio → Analytiques → exporter en CSV
2. Dépose le CSV dans le dépôt (navigateur en mode ordinateur, voir l'étape 1 :
   dossier `donnees/sources` → **Add file** → **Upload files**)
3. **Produire** → `resultats`, et dans *Vidéo de référence, ou export CSV* :
   `donnees/sources/export.csv`

Le résumé te dit alors quels réglages vont avec tes meilleurs résultats — et
il refuse de conclure quoi que ce soit sous 10 épisodes publiés.

## Ce qu'il faut savoir

- **Le temps de calcul est gratuit** si ton dépôt est public, et limité à
  2 000 minutes par mois s'il est privé. Un épisode prend 5 à 15 minutes :
  largement de quoi tenir tes 30 épisodes mensuels.
- **Les clés d'API, elles, restent à ta charge** — sauf avec `--profil
  gratuit` (Groq + Pollinations), qui n'a besoin d'aucun crédit ni carte
  bancaire pour écrire et illustrer. Seule la voix (ElevenLabs) reste à
  brancher, et sa formule gratuite (sans carte non plus) couvre largement
  quelques épisodes par mois.
- **Le cache est conservé d'un lancement à l'autre** : une image ou une voix
  déjà payée n'est jamais refacturée.
- **Une seule production à la fois.** Si tu relances pendant qu'un épisode se
  fabrique, le second attend son tour.
- **Le lien direct de la vidéo ne périme pas** (onglet *Releases*). Seule la
  copie ZIP disparaît au bout de 30 jours.
- **Un lancement raté se reprend**, il ne se recommence pas : voir plus haut.

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
