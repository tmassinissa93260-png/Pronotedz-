# Prototype — sujet → OpenAI → storyboard validé → images → animations

Petit programme local. Un sujet, une durée, un nombre de plans. OpenAI écrit,
un validateur vérifie, et fait corriger OpenAI tant que ce n'est pas bon.

Prototype **4 plans**. Indépendant : rien de `pdz`/`pdz2`, pas de plateforme
web, pas de framework, pas de base de données.

```
prototype/
  app/
    main.py             orchestration, logs, reprise
    openai_client.py    generate_storyboard() + boucle de correction
    prompts.py          les 10 conditions, la direction artistique
    models.py           le contrat JSON
    validator.py        les 10 vérifications
    image_analyzer.py   analyze_image() puis generate_animation_prompt()
    config.py           les 3 valeurs d'entrée, modèles, chemins
    fal_client.py       point d'intégration images/vidéos
    requirements.txt
    output/             project.json, status.json, shots/
  .env                  ta clé (jamais commité)
  tests/
```

---

## 1. Installer

```bash
cd prototype
python3 -m venv .venv && source .venv/bin/activate    # Windows : .venv\Scripts\activate
pip install -r app/requirements.txt
```

## 2. Configurer la clé

```bash
cp .env.example .env
```

Puis **une** de ces lignes dans `.env` :

```
OPENAI_API_KEY=sk-...      # OpenAI
GROQ_API_KEY=gsk_...       # Groq — API compatible OpenAI, gratuite
```

La clé n'est jamais dans le code (un test le vérifie). Sans clé, le programme
affiche `OPENAI_API_KEY manquante dans .env` et sort proprement.

Le modèle se change dans `.env` : `OPENAI_MODEL`, `OPENAI_VISION_MODEL`.

## 3. Lancer

```bash
cd app && python main.py           # le cerveau seul, TEST_MODE
```

ou, depuis `prototype/` :

```bash
python -m app.main                              # idem
python -m app.main valider                      # rejouer les 10 vérifications
python -m app.main analyser --shot 1 --image X  # image → analyse → animation
python -m app.main produire --sans-video        # images via fal.ai
python -m app.main comparer --shot 1            # le même prompt sur N modèles
python -m app.main selfcheck                    # état de la config
```

Sortie de `python main.py` :

```
[INPUT]
  Fonctionnement d'une voiture électrique
  16 secondes
  4 plans

[OPENAI] Génération du script...
[OPENAI] Génération du storyboard...
[VALIDATION] Vérification... (tentative 1)
[CORRECTION] 3 point(s) à corriger, renvoi à OpenAI
  ! [DEBIT] shot_01 : 2 mots pour 4.0s (0.5 mot/s) : phrase trop courte
[VALIDATION] Vérification... (tentative 2)
[OK] 4 plans validés
[OUTPUT] .../output/project.json
```

Puis les 4 plans, avec leur voix, leur fonction et leur prompt photo.

---

## Les 10 conditions, et comment elles sont tenues

Chacune est **écrite dans le prompt** (`prompts.py`) *et* **vérifiée après coup**
(`validator.py`). Une condition seulement demandée n'est pas une condition.

| Condition | Dans le prompt | Vérifiée par |
| --- | --- | --- |
| 1 · chaîne causale | exemple de chaîne, interdiction de lister | `PROGRESSION` : deux plans ne peuvent dire la même chose |
| 2 · durée | somme exacte, ~2,7 mots/seconde | `DUREE` + `DEBIT` : mots/seconde hors de [1.8, 4.0] rejeté |
| 3 · fonction du plan | `educational_function` justifiée | `FONCTION` : trop vague, ou dupliquée |
| 4 · visual bible | remplie avant les prompts, réinjectée partout | `CONTINUITE` : la bible doit se retrouver dans chaque prompt |
| 5 · prompt spécifique | 11 points exigés | `PRECISION` : longueur + cadrage, caméra, position, lumière, matériaux |
| 6 · dit = montré | score honnête, seuil 0,8 | `ALIGNEMENT` : composant nommé dans la voix cherché dans le prompt photo |
| 7 · animation qui explique | facettes obligatoires, vocabulaire contrôlé | `AnimationPlan` : `motion_intent` hors liste rejeté |
| 8 · animation après l'image | `analyze_image()` avant `generate_animation_prompt()` | l'ordre est imposé par le code |
| 9 · physique plausible | stator fixe, pas de déformation, flux orienté | dans le prompt système |
| 10 · pas de texte | direction artistique, `no text no labels` | `STYLE` : direction artistique absente = rejet |

### La boucle de correction

Quand le validateur refuse, on ne rend pas la main : la liste exacte des
manquements repart chez OpenAI, plan par plan.

```
Your previous JSON was rejected by an automatic validator.
- shot_01: write about 10 words of narration, not 2. Say more about the causal link, do not pad.
- shot_02: the image_prompt must explicitly state cadrage, camera, position, lumiere, materiaux.
- shot_03: rework it until what the voice says is unmistakably the thing shown.
```

`MAX_REPAIR_ATTEMPTS` (défaut 2) borne le nombre d'allers-retours. Ce qui reste
non corrigé est affiché en `[ATTENTION]`, jamais masqué.

### Vocabulaire d'animation

`motion_intent` doit valoir exactement une de ces valeurs :

`reveal` · `orbit` · `macro_travel` · `interaction` · `tracking` ·
`energy_follow` · `mechanical_rotation` · `electromagnetic_rotation` ·
`gear_rotation` · `drivetrain_follow` · `causal_traversal` · `acceleration` ·
`deceleration` · `reverse_energy` · `energy_generation` · `energy_return`

`zoom_in` n'y est pas, volontairement.

---

## Ce que produit le programme

```
app/output/
  project.json          storyboard validé, rejouable
  status.json           {"shot_01": "completed", ...}
  shots/shot_01/
    voice.txt
    image_prompt.txt
    image.png             si fal.ai a tourné
    image_analysis.json   ce qui est réellement visible
    animation.json        prompt, intention, caméra, mécanique, énergie, préserver, interdit
    animation_prompt.txt
    video.mp4             si fal.ai a animé
```

## TEST_MODE

`TEST_MODE = True` dans `app/config.py` : OpenAI, validation, `project.json`,
affichage — **aucune image, aucune vidéo**. C'est le mode par défaut.

## Sur GitHub Actions

`Actions` → **Prototype — produire une vidéo** → `Run workflow`.

| Étape | Ce qu'elle fait |
| --- | --- |
| `storyboard` | le cerveau seul, gratuit hors OpenAI |
| `produire` | + images et vidéos via fal.ai (**payant**) |
| `analyser` | une image → analyse → prompt d'animation |
| `comparer` | le même prompt photo sur plusieurs modèles, pour choisir sur pièces |

### Choisir le générateur d'images

Le premier essai s'est fait avec `fal-ai/flux/schnell` en 1080×1920. Résultat :
du texte halluciné malgré `no text`, une tige métallique sortant d'une roue, un
rectangle gris sur une calandre. Deux causes — le modèle le plus faible de la
famille, et une résolution au double du domaine d'entraînement de FLUX.

Les mêmes prompts, collés dans Meta AI, ont rendu des images justes : voir
`exemples/meta-ai/`. **Le cerveau n'était pas en cause, le générateur l'était.**

Défaut actuel : `fal-ai/flux-pro/v1.1` en 768×1344 (1,03 Mpx). Mais plutôt que
de me croire :

```bash
python -m app.main comparer --shot 1
```

envoie le même prompt à `flux-pro/v1.1`, `flux/dev` et `flux/schnell`, et dépose
les images côte à côte. Tu regardes, tu choisis, tu fixes `FAL_IMAGE_MODEL`.

Chaque famille a ses champs propres — `ultra` raisonne en rapport d'image, les
`pro` ne prennent pas de nombre de pas, `schnell` ignore la guidance. La charge
utile s'adapte au modèle : envoyer un champ inconnu fait rejeter l'appel.

Secrets : `OPENAI_API_KEY` ou `GROQ_API_KEY`, et `FAL_KEY` pour `produire`.
Le champ `animations` vaut **0 par défaut** : aucune dépense vidéo.

## Tests

```bash
python -m unittest discover -s tests
```

77 tests, aucun appel réseau : contrat JSON, les 10 vérifications une par une,
conditions présentes dans le prompt, résolution du cerveau, reprise, CLI, et
le client fal contre un service simulé.

## Limites assumées

- Le point d'intégration images/vidéos est `fal_client.py`. Le premier vrai
  appel se fait sur ta machine ou en CI, pas ici.
- `ALIGNEMENT` compare des mots français de la voix à leurs équivalents
  anglais attendus dans le prompt photo : c'est une heuristique, pas une
  compréhension. Elle attrape les oublis francs, pas les subtils.
- 4 plans. Ne pas monter à 20 avant que les 4 tiennent.
