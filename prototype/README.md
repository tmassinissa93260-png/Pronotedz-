# Prototype — SUJET → OpenAI → prompts → navigateur → Meta AI

Petit programme local. Un sujet, une durée, un nombre de plans. OpenAI prépare
le contenu, ton navigateur fait les copier-coller dans Meta AI.

Prototype **4 plans**. Indépendant : rien à voir avec `pdz`/`pdz2`, pas de
plateforme web, pas de framework.

```
prototype/
  app/
    main.py            orchestration + logs + reprise
    config.py          les 3 valeurs d'entrée, l'URL Meta AI, les chemins
    models.py          structure du storyboard + validation de la réponse OpenAI
    prompts.py         direction artistique et prompts envoyés à OpenAI
    openai_client.py   storyboard (texte) et prompt d'animation (vision)
    browser.py         Chromium visible, profil persistant, pauses, captures
    meta_ai.py         recherche du composer, collage, envoi, récupération
    requirements.txt
    output/            project.json, status.json, shots/, screenshots/
  browser_profile/     session Meta conservée entre deux lancements
  tests/
```

---

## 1. Comment installer

```bash
cd prototype
python3 -m venv .venv && source .venv/bin/activate      # Windows : .venv\Scripts\activate
pip install -r app/requirements.txt
python -m playwright install chromium
```

## 2. Comment configurer OPENAI_API_KEY

```bash
cp .env.example .env
```

Puis dans `.env` :

```
OPENAI_API_KEY=sk-...
```

Ni espace, ni guillemets, pas de commentaire sur la même ligne. `.env` est dans
`.gitignore` — la clé n'est **jamais** écrite dans le code.

Vérifie :

```bash
python -m app.main selfcheck
```

Ça contrôle la config, la présence de la clé et le démarrage de Chromium. Aucun
appel réseau, aucun navigateur visible.

## 3. Comment lancer

```bash
# OpenAI seul, sans jamais ouvrir le navigateur — pour vérifier le JSON d'abord
python -m app.main storyboard

# la boucle : navigateur visible + Meta AI
python -m app.main run

# où on en est
python -m app.main status
```

Autres options utiles :

| Commande | Effet |
| --- | --- |
| `run --regenerate` | ignorer `project.json` et redemander le storyboard |
| `run --force` | refaire un plan déjà marqué terminé |
| `storyboard --subject "..." --duration 20 --shots 5` | override ponctuel |

## 4. Ce que tu dois faire manuellement lors du premier test

`TEST_MODE = True` : le programme s'arrête volontairement après le **SHOT 01**.

```bash
python -m app.main run
```

Déroulé :

1. OpenAI génère le storyboard → `app/output/project.json` **(automatique)**
2. Chromium s'ouvre, **visible**, sur l'URL Meta AI fixe **(automatique)**
3. **À toi** : si Meta demande une connexion, le programme affiche
   `Connexion Meta requise. Connecte-toi manuellement dans le navigateur puis appuie sur Entrée.`
   Tu te connectes **toi-même** dans la fenêtre, puis tu appuies sur Entrée.
   Le programme ne te demande jamais ton mot de passe ni ton code 2FA, et
   ne les stocke nulle part.
4. Le prompt photo du SHOT 01 est collé et envoyé **(automatique)**
5. **À toi** : vérifier à l'écran que le prompt est bien dans la zone de saisie
   et bien parti. Puis Entrée pour fermer.

Grâce au profil persistant `browser_profile/`, la connexion de l'étape 3 n'est
normalement à refaire qu'une fois.

Si un élément de l'interface est introuvable, le programme **ne plante pas en
silence** : message explicite, capture d'écran + HTML dans
`app/output/screenshots/`, pause, et tu reprends à la main.

## 5. Comment passer de TEST_MODE=true à false

Dans `app/config.py` :

```python
TEST_MODE = False
```

Ou sans toucher au fichier :

```bash
python -m app.main run --no-test-mode
```

Les 4 plans s'enchaînent alors : photo → analyse OpenAI → prompt d'animation →
animation, plan après plan.

---

## Ce que produit le programme

```
app/output/
  project.json          le storyboard complet, rejouable
  status.json           {"shot_01": "completed", "shot_02": "pending", ...}
  shots/
    shot_01/
      image_prompt.txt      prompt photo (aussi collable à la main)
      voice.txt             narration du plan
      image.png             si la récupération auto a marché
      animation_prompt.txt  prompt d'animation généré à partir de l'image réelle
      video.mp4             si la récupération auto a marché
    shot_02/ shot_03/ shot_04/
  screenshots/          captures de debug en cas de souci
```

### Reprise

`status.json` est écrit après chaque plan. Si le programme s'arrête après le
SHOT 02, relancer `run` reprend au SHOT 03 — le storyboard est relu depuis
`project.json`, pas redemandé à OpenAI. Une image déjà présente dans un dossier
de plan est réutilisée telle quelle.

### Direction artistique

`prompts.py` impose la phrase de style à OpenAI **et** la revérifie après coup :
si un `image_prompt` ne la contient pas, `enforce_style()` l'ajoute. La
continuité (même voiture blanche, même studio, mêmes matériaux, même lumière)
est demandée explicitement et rappelée dans `visual_continuity`.

### Prompt d'animation

Il n'est **pas** écrit à l'aveugle : OpenAI reçoit l'image réellement générée
et la narration du plan, puis doit dire ce qui bouge, comment, ce qui reste
immobile, le mouvement de caméra, et interdire toute déformation. Le prompt
système refuse explicitement un simple « zoom in », et le client rejette une
réponse trop courte pour être pédagogique.

## Sécurité

- Aucun contournement de CAPTCHA, d'authentification ou de protection.
- Le programme ne saisit jamais d'identifiant, de mot de passe ni de code.
- `.env`, `browser_profile/` et `app/output/` sont hors de Git.
- Le profil de navigateur ne contient que ce que Chromium y écrit quand **tu**
  te connectes à la main.

## Tests

```bash
python -m unittest discover -s tests          # hors ligne : parsing, style, reprise, CLI
python -m unittest tests.test_browser_paste   # vrai Chromium, fausse page de chat locale
```

## Limites connues de ce prototype

- **Les sélecteurs Meta AI ne sont pas vérifiés contre le vrai site.** Meta AI
  demande un compte et une session ; ils sont écrits en cascade (rôle
  `textbox`, puis placeholder, puis `contenteditable`, puis `textarea`) avec
  capture d'écran et reprise manuelle en cas d'échec. C'est le point à valider
  en premier sur ta machine.
- La récupération automatique de l'image et de la vidéo est **best-effort** :
  si l'interface ne l'expose pas, le programme te demande d'enregistrer le
  fichier à la main plutôt que de bloquer.
- Détection de fin de génération par comptage de `<img>` / `<video>` : simple,
  suffisant pour un prototype, pas infaillible.
- 4 plans. Ne pas monter à 20 avant que la boucle 4 plans tourne.
