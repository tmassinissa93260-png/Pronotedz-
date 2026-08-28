# Prototype — vidéo éducative semi-automatique

Tu donnes un sujet, une durée, un nombre de plans. Le système écrit le script,
la visual bible, les plans, les prompts image **et** animation. **Tu produis
les images et les animations** avec l'outil de ton choix. Tu renvoies les
vidéos. Il analyse, cale la timeline, écrit les sous-titres et monte le MP4.

**Il ne génère jamais d'image ni de vidéo.** Pas d'automatisation navigateur,
pas de plateforme web, pas de base de données.

```
prototype/
  app/
    main.py             orchestration, logs
    openai_client.py    le cerveau + la boucle de correction
    prompts.py          la grammaire visuelle pédagogique
    models.py           le contrat JSON
    validator.py        les vérifications
    analyzer.py         image réelle → animation · vidéos rendues → analyse
    montage.py          timeline, sous-titres, MP4
    config.py           les 3 valeurs d'entrée
    requirements.txt
    output/             project.json, elements.md, videos/, timeline.json, final.mp4
  .env                  ta clé (jamais commitée)
  tests/
```

---

## Le pipeline

```
SUBJECT · DURATION · SHOT_COUNT
        ↓
   OpenAI  →  script · storyboard · visual bible · prompts image · prompts animation
        ↓
   TOI     →  tu génères les images
        ↓
   TOI     →  tu génères les animations à partir de tes images
        ↓
   TOI     →  tu déposes les vidéos dans output/videos/
        ↓
   OpenAI  →  analyse des vidéos rendues
        ↓
             timeline · sous-titres · montage · MP4 final
```

## Installer

```bash
cd prototype
python3 -m venv .venv && source .venv/bin/activate
pip install -r app/requirements.txt
```

`ffmpeg` est nécessaire pour l'analyse vidéo et le montage — pas pour le
storyboard.

```bash
brew install ffmpeg        # macOS
sudo apt install ffmpeg    # Linux
```

## Configurer

```bash
cp .env.example .env
```

Puis **une** de ces lignes :

```
OPENAI_API_KEY=sk-...      # OpenAI
GROQ_API_KEY=gsk_...       # Groq — API compatible, gratuite
```

La clé n'est jamais dans le code : un test le vérifie.

## Lancer

```bash
cd app && python main.py                            # script + storyboard + prompts
```

ou depuis `prototype/` :

```bash
python -m app.main                                  # idem
python -m app.main elements                         # tout réexporter
python -m app.main affiner --shot 1 --image X       # image réelle → animation ajustée
python -m app.main analyser-videos                  # tes vidéos → ce qu'elles montrent
python -m app.main timeline                         # timeline + sous-titres
python -m app.main montage                          # MP4 final
python -m app.main selfcheck                        # état de la configuration
```

Tout ce qu'il te faut pour produire est rassemblé dans **`output/elements.md`** :
script, visual bible, et pour chaque plan la voix, la fonction, l'élément
pédagogique, le prompt image et le prompt animation.

---

## La règle centrale : la grammaire visuelle pédagogique

Un prompt qui se contente de montrer un objet est refusé. Quand la voix nomme
quelque chose d'invisible — électricité, courant, champ, énergie, signal — le
système doit en **créer une représentation visible**.

> « Le moteur reçoit l'électricité » → montrer un moteur ne suffit pas.
> Il faut des flux lumineux **jaunes** entrant dans les bobinages.

Cet élément jaune n'est pas une décoration : **il porte une information**.

### Code couleur — une couleur, un sens, stable

| | |
|---|---|
| **jaune** | électricité, courant, énergie électrique |
| **bleu** | batterie, système électrique, technologie |
| **vert** | efficacité, énergie récupérée, recharge |
| **orange** | chaleur, puissance, phénomène à distinguer |
| **gris** | mécanique, structure, composants |

### Correspondance image → animation

Ce que l'image introduit, l'animation doit le faire bouger.

| L'image montre | L'animation doit |
|---|---|
| un flux d'énergie jaune | le faire circuler |
| un rotor | le faire tourner |
| des cellules de batterie | les faire s'illuminer, ou montrer l'énergie circuler |

**Interdit** : image « batterie + flux électrique » / animation « zoom caméra ».
La caméra peut bouger, mais jamais comme mouvement principal.

### Vocabulaire de mouvement — fermé

`energy_flow` · `energy_storage` · `energy_transfer` · `mechanical_rotation` ·
`electromagnetic_rotation` · `cause_effect` · `reveal` · `tracking` ·
`macro_travel` · `acceleration` · `deceleration` · `regenerative_braking` ·
`energy_return`

`zoom` n'y figure pas, volontairement. Un `motion_intent` hors liste est rejeté
par le code, pas seulement déconseillé.

---

## Les vérifications

Chaque règle est **écrite dans le prompt** *et* **vérifiée après coup**. Une
règle seulement demandée n'est pas une règle.

| Code | Rejette |
| --- | --- |
| `PLANS` · `DUREE` · `IDS` | mauvais compte, somme des durées fausse, numérotation trouée |
| `DEBIT` | hors de 1,8–4,0 mots/seconde : plan vide, ou impossible à dire |
| `FONCTION` | une fonction pédagogique vague ou dupliquée |
| `STYLE` | la direction artistique absente d'un prompt |
| `PRECISION` | un prompt muet sur cadrage, caméra, position, lumière ou matériaux |
| `CONTINUITE` | un prompt qui ne reprend rien de la visual bible |
| `ALIGNEMENT` | un composant nommé par la voix, absent du prompt image |
| `PROGRESSION` | deux plans qui disent la même chose |
| **`GRAMMAIRE`** | **un phénomène invisible sans représentation colorée** |
| **`CORRESPONDANCE`** | **un élément pédagogique que l'animation ne fait pas bouger, ou une animation réduite à un mouvement de caméra** |
| `QUALITE` | un des sept axes sous 0,8 |

Quand le validateur refuse, la liste exacte repart chez OpenAI, plan par plan.
`MAX_REPAIR_ATTEMPTS` (défaut 2) borne les allers-retours ; ce qui reste est
affiché en `[ATTENTION]`, jamais masqué.

## Montage

La **voix off est la référence temporelle**. Chaque plan occupe la durée prévue
par sa narration : une vidéo trop longue est coupée, une trop courte est
signalée. Les sous-titres sont calés sur cette même timeline, deux lignes au
plus.

Dépose si tu veux `output/voix.mp3` et `output/musique.mp3` : la musique est
mixée à 15 % sous la voix.

## Sur GitHub Actions

`Actions` → **Prototype — vidéo éducative** → `Run workflow`.

| Étape | |
| --- | --- |
| `storyboard` | script, bible, prompts — c'est tout |
| `analyser-videos` | tes vidéos déposées dans `app/output/videos/` |
| `montage` | timeline, sous-titres, MP4 |

Secret : `OPENAI_API_KEY` ou `GROQ_API_KEY`.

## Tests

```bash
python -m unittest discover -s tests
```

62 tests, aucun appel réseau : contrat JSON, code couleur, les vérifications
une par une — dont la grammaire visuelle et la correspondance image → animation
—, conditions présentes dans le prompt, timeline, sous-titres, CLI.

## Limites assumées

- L'analyse vidéo échantillonne quelques images du fichier : un modèle de
  vision lit des images, pas un flux. Elle juge ce qui change entre le début et
  la fin, pas chaque frame.
- `ALIGNEMENT` et `GRAMMAIRE` rapprochent des mots français de leurs
  équivalents anglais attendus : une heuristique, pas une compréhension. Elles
  attrapent les oublis francs, pas les subtils.
- 4 plans. Ne pas monter à 20 avant que les 4 tiennent.
