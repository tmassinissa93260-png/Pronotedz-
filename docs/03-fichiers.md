# 03 — Les fichiers du projet

Un seul projet Python. Pas de monorepo, pas de frontend séparé, pas de microservices.

```
pronotedz/
│
├── pdz/                          # Tout le code
│   │
│   ├── cli.py                    # Les commandes : pdz new, pdz analyze...
│   ├── web.py                    # La petite page locale de validation (FastAPI)
│   ├── config.py                 # Réglages + clés d'API (lues dans .env)
│   │
│   ├── moteur/
│   │   ├── pipeline.py           # Enchaîne les étapes, sauvegarde après chacune
│   │   ├── reprise.py            # Repart où ça s'est arrêté
│   │   ├── validation.py         # Les 3 pauses où il me demande mon avis
│   │   └── erreurs.py            # Quoi faire quand ça plante
│   │
│   ├── agents/
│   │   ├── base.py               # Le socle commun à tous les agents
│   │   ├── analyse/              # 1-ingest · 2-transcription · 3-decoupage
│   │   │                         # 4-vision · 5-son
│   │   ├── recette/              # 6-recette · 7-nettoyage
│   │   ├── creation/             # 8-angle · 9-script · 10-decoupage-visuel
│   │   └── production/           # 11-assets · 12-montage
│   │
│   ├── ia/                       # ⚠️ LE SEUL ENDROIT qui connaît les fournisseurs
│   │   ├── registre.py           # Lit modeles.yaml et choisit le bon modèle
│   │   ├── claude.py
│   │   ├── openai_compat.py      # Marche pour Groq, OpenRouter, Ollama, DeepSeek...
│   │   ├── fal.py                # Images
│   │   └── elevenlabs.py         # Voix
│   │
│   ├── prompts/
│   │   ├── registre.py           # Charge le bon prompt, la bonne version
│   │   └── catalogue/            # ← LES PROMPTS, un fichier chacun
│   │       ├── recette/extraire@2.1.0.yaml
│   │       ├── creation/script@3.0.0.yaml
│   │       └── ...
│   │
│   ├── memoire/
│   │   ├── recettes.py           # Ma bibliothèque de recettes + recherche
│   │   ├── historique.py         # Ce qui a déjà été fait (anti-répétition)
│   │   └── ma_marque.py          # Mon ton, mes sujets, ce que je ne veux jamais
│   │
│   ├── video/
│   │   ├── montage.py            # Construction de la commande FFmpeg
│   │   ├── soustitres.py         # Sous-titres karaoké (format .ass)
│   │   ├── mouvement.py          # Zoom lent sur les images
│   │   └── controle.py           # Vérifs auto : durée, son, images noires
│   │
│   ├── cache.py                  # Ne jamais repayer deux fois la même chose
│   └── db.py                     # SQLite
│
├── donnees/                      # ⚠️ Ne pas mettre sur GitHub (.gitignore)
│   ├── pronotedz.db              # LA base — 1 seul fichier, à sauvegarder
│   ├── sources/                  # Les vidéos que je donne à analyser
│   ├── travail/                  # Images, voix, fichiers temporaires
│   ├── sorties/                  # 📹 Mes vidéos finies
│   └── musique/                  # Ma banque de musiques libres de droits
│
├── modeles.yaml                  # Quel modèle IA pour quoi ← à éditer souvent
├── .env                          # Mes clés d'API (JAMAIS sur GitHub)
├── .env.exemple                  # Le modèle à copier
├── docker-compose.yml            # Pour lancer d'un coup
├── pyproject.toml                # Les dépendances Python
└── docs/                         # Cette documentation
```

## Trois règles qui comptent

### 1. `pdz/ia/` est la seule porte vers l'extérieur
Si je cherche le mot « anthropic » ou « elevenlabs » ailleurs dans le code, je ne dois
rien trouver. C'est ce qui me permet de changer de fournisseur en modifiant une ligne
de `modeles.yaml`, sans toucher au reste.

### 2. Les prompts sont des fichiers, pas du code
Un prompt dans `catalogue/`, avec un numéro de version. Je peux le modifier, comparer
les versions, revenir en arrière — sans rien casser dans le programme.

### 3. `donnees/` n'est jamais versionné
C'est le seul dossier à sauvegarder régulièrement. Le reste se retrouve sur GitHub.

## Le fichier `modeles.yaml` — celui que je toucherai le plus

C'est ici que je pilote la qualité et le coût. Un exemple :

```yaml
fournisseurs:
  anthropic:  { cle: ANTHROPIC_API_KEY }
  groq:       { cle: GROQ_API_KEY, compatible_openai: oui }
  fal:        { cle: FAL_KEY }
  elevenlabs: { cle: ELEVENLABS_API_KEY }

modeles:
  - id: claude-sonnet-4-5
    fournisseur: anthropic
    fait: [ecriture, analyse, vision]
    prix: { entree_par_million: 2.8, sortie_par_million: 14.0 }

  - id: claude-haiku-4-5
    fournisseur: anthropic
    fait: [ecriture_rapide, vision]
    prix: { entree_par_million: 0.9, sortie_par_million: 4.6 }

  - id: flux-dev
    fournisseur: fal
    fait: [images]
    prix: { par_image: 0.023 }

  - id: flux-schnell
    fournisseur: fal
    fait: [images]
    prix: { par_image: 0.0028 }      # 8× moins cher, un peu moins beau

# ── C'est ICI que je pilote tout ──
choix:
  qualite:  { principal: claude-sonnet-4-5, repli: claude-haiku-4-5 }
  rapide:   { principal: claude-haiku-4-5 }
  images:   { principal: flux-dev,          repli: flux-schnell }
  voix:     { principal: eleven-turbo-v2-5, repli: kokoro-local }

regles:
  - si: { budget_restant_pourcent: "<20" }
    alors: { qualite: claude-haiku-4-5, images: flux-schnell }
```

**Ce que ça me permet, concrètement :**

| Je veux... | Ce que je change |
|---|---|
| Essayer un nouveau modèle | +8 lignes de YAML |
| Changer de fournisseur de voix | 1 ligne |
| Passer en mode économique ce mois-ci | 2 lignes dans `choix` |
| Ajouter un fournisseur (DeepSeek, Mistral, Cerebras...) | +4 lignes — l'adaptateur `openai_compat` marche déjà pour eux |
| Utiliser un modèle sur ma machine (Ollama) | +4 lignes |

Zéro ligne de code Python à modifier dans tous ces cas.
