# Architecture actuelle — audit du dépôt

> État au 19/08/2026, commit `a5e6319`, branche `claude/audiovisual-compiler-design-my7lva`.
> Ce document **décrit ce qui existe**, sans jugement et sans projection.
> La comparaison avec la cible est dans [GAP_ANALYSIS.md](./GAP_ANALYSIS.md).

---

## A. Carte du dépôt

```
Pronotedz-/
├── pdz/                      le paquet Python — tout le système
│   ├── cli.py                921 l. — 20 commandes Typer
│   ├── config.py             le SEUL lecteur d'environnement du projet
│   ├── db.py                 SQLite, 7 tables, sans ORM
│   ├── cles.py               vérification des clés d'API
│   ├── web.py                page locale de validation humaine (FastAPI)
│   ├── moteur/               noyau : pipeline, cache, reprise, erreurs
│   ├── contracts/            ✗ n'existe pas
│   ├── agents/               6 agents LLM (écriture ×4, analyse ×2)
│   ├── prompts/              catalogue de prompts VERSIONNÉS (36 fichiers)
│   ├── ia/                   adaptateurs fournisseurs + registre de modèles
│   ├── production/           19 modules — le cœur de la chaîne
│   ├── analyse/              12 modules — mesure locale, zéro IA
│   ├── video/                montage FFmpeg, sous-titres, parallaxe locale
│   └── univers/              le modèle « monde réutilisable » (Pydantic)
├── univers/                  4 mondes livrés en YAML
├── tests/                    41 fichiers, 739 tests
├── tools/                    7 scripts de démonstration
├── scripts/                  garde-fou anti-fuite de vidéos privées
├── docs/                     15 documents + archive/
├── modeles.yaml              LE fichier d'arbitrage qualité/coût
├── .github/workflows/        produire.yml · verifier-videos.yml
└── Dockerfile · docker-compose.yml · pyproject.toml
```

**Volume** : ~25 600 lignes Python, dont ~11 000 de tests. Aucun n8n, aucun
outil de rendu tiers. Python 3.11+, `pdz` en point d'entrée console.

---

## B. Architecture existante

Le système est **déjà un compilateur**, pas un workflow de prompts — mais un
compilateur à **deux orchestrateurs concurrents**, ce qui est le fait le plus
important de cet audit.

### B.1 — Les deux orchestrateurs

**`pdz/moteur/pipeline.py` (413 l.) — le moteur générique.**
`Pipeline(nom, etapes)` où chaque `Etape(cle, agent, depend_de, validation,
optionnelle)`. `Moteur.executer(job_id, pipeline)` :

- ne mémorise jamais sa position — il **relit** `etapes` en base et déduit ce
  qui reste (reprise = même opération qu'un premier lancement) ;
- calcule une `empreinte()` = `sha256(entrées normalisées + signature agent)`
  et sert le cache avant tout appel payant ;
- arrête net sur budget épuisé, échec non optionnel, ou validation humaine ;
- relance selon la politique portée par l'erreur, avec **deux compteurs
  séparés** (transitoire vs contenu) et réinjection du motif d'échec au modèle.

**`pdz/production/episode.py` (666 l.) — la chaîne réellement utilisée.**
Sept étapes câblées à la main (`brief → script → voix → découpage → prompts →
réalisme → images → animation → sous-titres → montage`), avec sa **propre**
mécanique de reprise (`_fait()`, `_noter()`) qui écrit dans la même table
`etapes` mais **sans passer par `Moteur`** — donc sans son cache par empreinte,
sans `Etape.depend_de`, sans le mécanisme de validation.

`_fait()` ajoute une chose que `Moteur` n'a pas : la **revérification des
fichiers cités**. Une étape marquée terminée dont le `.mp4` a disparu est
refaite. C'est un vrai acquis, né d'un échec réel.

> **Conséquence** : `Etape.depend_de` est déclaré mais jamais exploité comme
> graphe — `Moteur` itère linéairement sur `pipeline.etapes`. Il n'y a pas
> d'ordonnanceur de DAG dans le dépôt.

### B.2 — L'ordre des étapes, et pourquoi il est juste

`episode.py` documente et applique la règle qui est le cœur de tout
compilateur audiovisuel sérieux :

```
script → TTS → timings RÉELS mot à mot → découpage en plans → images
```

**La voix passe avant les images.** La durée d'un plan vient de la parole
réellement prononcée (`pdz/production/voix.py` recale les timings ElevenLabs
sur la piste complète), jamais d'une estimation. `storyboard.point_de_coupe()`
place la coupe parlant/réaction sur une **vraie pause mesurée** quand elle est
retrouvable dans les timings.

C'est exactement la contrainte « LA VOIX DEVIENT LA CHRONOLOGIE OFFICIELLE ».
Elle est déjà tenue.

### B.3 — Séparation intention / texte envoyé au modèle

`pdz/production/motion_program.py` (258 l.) porte un `MotionProgram` gelé :
`action, camera, environnement, intensite, cible_perceptuelle,
doit_preserver, peut_changer, interdit, registre`. Compilé ensuite en prompt
par `compiler_prompt()`.

Deux détails montrent la maturité du code :

- `ControleCamera.TEXTE_SEULEMENT` **dit explicitement** que l'adaptateur
  fal.ai n'envoie aucun paramètre de caméra : « caméra verrouillée » est une
  intention, pas une garantie technique. C'est la règle de non-hallucination
  technique, déjà appliquée dans le code.
- `cible_perceptuelle` (`viewer_must_perceive_subject_motion`…) est déjà une
  **cible perceptuelle** au sens du contrat perceptuel, et elle est
  effectivement recoupée en aval par la vérification de mouvement.

### B.4 — Résolution de capacité

`pdz/ia/registre.py` + `modeles.yaml` : les agents demandent un **alias**
(`qualite`, `images`, `animation`, `vision`), jamais un fournisseur.
`Registre.resoudre()` arbitre dans cet ordre : règles de budget > profil >
alias par défaut, avec **substitution de capacité** (un appel qui envoie des
images demande `vision` ; si le modèle du profil ne sait pas le faire, on
prend celui qui sait plutôt que d'aller échouer chez le fournisseur).

`Modele` porte : `fait: [...]`, `contexte`, `prix`, `cache`,
`sorties_structurees`, `options`, `durees_s` (les paliers de durée que le
endpoint livre **réellement**) et `duree_facturable()`.

### B.5 — Prompts versionnés

`pdz/prompts/catalogue/{analyse,ecriture}/<id>@<semver>.yaml` — 36 fichiers,
jusqu'à `plans@1.14.0`. La version utilisée entre dans la signature de l'agent,
donc dans l'empreinte de cache : changer un prompt invalide le cache tout seul.
`appels_ia.prompt_ref` garde la trace par appel.

**C'est le modèle à répliquer pour les contrats de données** : il fonctionne,
il est testé, et il résout déjà versionnement + provenance + invalidation.

---

## C. Modules existants

### `moteur/` — noyau
| Module | Rôle |
|---|---|
| `pipeline.py` | `Moteur`, `Pipeline`, `Etape`, `Contexte`, `empreinte()`, cache, reprise, validation |
| `erreurs.py` | 8 classes d'erreur, chacune portant sa `Politique(reessayer, tentatives_max, facturee, repli_modele, bruyante)` |

`ErreurReseau · ErreurQuota · ErreurFournisseur · ErreurValidation ·
ErreurRefus · ErreurBudget · ErreurConfig`. Une `ErreurConfig` a
`repli_modele=False` — un identifiant de modèle périmé arrête la production
au lieu d'être masqué par un repli.

### `production/` — le cœur (19 modules)
| Module | Rôle | IA ? |
|---|---|---|
| `episode.py` | la chaîne complète, la reprise fichier | orchestration |
| `voix.py` | bande voix + timings mot à mot recalés | ElevenLabs |
| `storyboard.py` | répliques → plans, durées, point de coupe | ✗ |
| `images.py` | images par plan, stabilité des personnages | fal/Pollinations |
| `animation.py` | **quels** plans animer, puis les animer | fal (Kling) |
| `motion_program.py` | intention temporelle typée d'un plan | ✗ |
| `contrat_visuel.py` | le plan en 8 questions, forme typée | ✗ |
| `decision_visuelle.py` | recoupe le contrat visuel avec lui-même | ✗ |
| `geometrie.py` | position qualitative des objets | ✗ |
| `cadrage.py` | vocabulaire fixe de cadrage + variété | ✗ |
| `continuite.py` | porte le décor d'une réplique à l'autre | ✗ |
| `risque_prompt.py` | filtre déterministe : ce prompt mérite-t-il une passe réalisme | ✗ |
| `fidelite_visuelle.py` | le prompt nomme-t-il ce que la réplique nomme | ✗ |
| `coherence_duree.py` | la vidéo dure-t-elle aussi longtemps que la voix | ✗ |
| `verification_mouvement.py` | ce clip bouge-t-il vraiment | ✗ |
| `qa_video_finale.py` | combien de plans bougent dans le master monté | ✗ |
| `qa_images.py` | quelles images méritent une vérification visuelle | déclenche |
| `appariement_voix.py` | retrouver la voix la plus proche d'une référence | ✗ |

**14 modules sur 19 ne coûtent rien.** La politique de décision
(« déterministe → pas de LLM ») est déjà appliquée sérieusement.

### `analyse/` — mesure locale, 12 modules, **zéro appel IA**
`sonde` (métadonnées) · `coupes` (détection avec calibrage automatique du
seuil) · `son` (énergie, silences, tempo, débit) · `visuel` (style chiffré) ·
`voix` (hauteur, timbre, débit) · `musique` (mesure + identification AudD) ·
`adn` (mesures → contraintes de production) · `retention` · `diversite` ·
`references` · `rapport` · `rapport_transfert`.

### `video/`
`montage.py` (`Montage`, `Plan`, `Mouvement` → FFmpeg) · `soustitres.py`
(karaoké ASS mot à mot) · `vie.py` (travelling en perspective, particules,
scintillement — **une parallaxe locale gratuite**, sans modèle vidéo).

### `univers/modele.py` (358 l., Pydantic)
`Univers` = `Personnage[]`, `Decor[]`, `Style`, règles. `EmpreinteCreative`
avec `ChampInterprete(valeur, confiance)` — **la confiance est déjà un champ
de premier ordre**, et `texte_empreinte()` filtre les `unknown` et les
confiances < 0,2 plutôt que de les faire passer pour des faits.

---

## D. Agents existants (6)

| Agent | Fichier | Ce qu'il décide |
|---|---|---|
| `BriefWriter` | `agents/ecriture/brief.py` | stratégie créative + squelette de beats |
| `ScriptWriter` | `agents/ecriture/script.py` | dialogue, action minimale, émotions, relances |
| `ShotPromptWriter` | `agents/ecriture/plans.py` | prompt d'image par plan + `mouvement_*`, `geometrie`, `relations`, `risques_predits`, `registre_visuel` |
| `RealismWriter` | `agents/ecriture/realisme.py` | réécrit ce qu'un modèle d'image ne sait pas rendre |
| `CharteVisuelle` | `agents/analyse/charte.py` | vidéo de référence → univers jouable |
| `AdnTransfert` | `agents/analyse/adn.py` | forme mesurée → situation à jouer |
| `QaImage` | `agents/analyse/qa_image.py` | PASS / FAIL / **UNCERTAIN**, jamais un score |

`agents/base.py` : un agent = `nom`, `prompt_ref`, `variables()`. Le reste
(cache, réessais, coût, reprise, budget) vient du moteur. `schema()` permet de
resserrer le schéma de sortie en `enum` à l'exécution — utilisé pour forcer les
identifiants d'univers valides.

Les agents **n'appellent jamais un fournisseur par son nom**. Ils passent par
`pdz.ia.texte.appeler(alias=…)`.

---

## E. Schémas et contrats existants

**Typés et validés (Pydantic)** : `Config`, `Univers`, `Personnage`, `Decor`,
`Style`, `EmpreinteCreative`, `ChampInterprete`, `Modele`, `Prix`, `Cache`,
`Resolution`.

**Typés sans validation (dataclasses nues)** : `PlanScript`, `MotionProgram`,
`ContratVisuel`, `Candidature`, `PlanAnime`, `VerdictMouvement`, `Montage`,
`Plan`, `Etape`, `Contexte`, `Resultat`, `Episode`, `BandeVoix`, `Mot`.

**Non typés (dicts JSON qui traversent le système)** : les sorties d'agents,
les entrées d'étapes, le contenu de `etapes.resultat`, `jobs.entree`,
`structures.mesures`.

**Aucun de ces objets ne porte** : `schema_version`, `id`, `created_at`,
`producer`, `provenance`, `dependencies`. Il n'y a **pas de paquet
`contracts/`**, pas de migration de schéma, pas de test de compatibilité
ascendante. Le seul versionnement réel du dépôt est celui des **prompts**
(et `structures.schema_version`, à `'1.0'`, jamais incrémenté).

### Le schéma SQLite (7 tables)
`jobs` · `etapes` (UNIQUE(job_id, cle) — le socle de la reprise) ·
`validations` · `structures` · `appels_ia` (chaque appel payant) ·
`artefacts` (adressés par sha256, dédupliqués) · `cache` (empreinte → valeur,
TTL 7 j, `cout_evite`).

---

## F. Tests existants

**739 tests, 41 fichiers, ~11 000 lignes.** Couverture par module réelle et
sérieuse : `test_production_images_voix.py` (1 416 l.), `test_shot_prompts.py`
(788 l.), `test_ia_et_prompts.py` (721 l.), `test_chaine_complete.py` (431 l.).

Ce qui existe : tests unitaires, tests de chaîne complète, tests de
non-régression sur des incidents datés (run #66, run #70, run #74), tests de
gating (`test_qa_images_gating.py`, `test_realisme_gating.py`).

**Ce qui manque** :
- ⚠️ **aucun workflow CI ne lance les tests.** `produire.yml` produit des
  vidéos, `verifier-videos.yml` cherche des fuites de vidéos privées. `pytest`
  et `ruff` sont déclarés dans `[dev]` et n'apparaissent dans aucun workflow ;
- pas de corpus de golden tests (productions de référence versionnées) ;
- pas de tests de contrat / compatibilité de schéma (il n'y a pas de contrats) ;
- pas de tests d'adaptateur fournisseur contre une interface commune (il n'y a
  pas d'interface commune).

---

## G. Fournisseurs existants

| Adaptateur | Fournisseur | Sert à |
|---|---|---|
| `ia/claude.py` | Anthropic | texte, vision, sortie structurée forcée, cache de prompt |
| `ia/groq.py` | Groq | texte gratuit (`openai/gpt-oss-120b`), vision gratuite (`qwen/qwen3.6-27b`) |
| `ia/fal.py` | fal.ai | images FLUX (synchrone) **et** animation Kling (file d'attente) |
| `ia/pollinations.py` | Pollinations | images gratuites, sans clé — **ne prend pas d'image de référence** |
| `ia/elevenlabs.py` | ElevenLabs | voix + alignement caractère par caractère |
| `ia/audd.py` | AudD | identification musicale |
| `ia/texte.py` | — | point d'entrée unique texte, dispatch par fournisseur résolu |
| `ia/images.py` | — | point d'entrée unique image, même principe |

**Il n'existe aucune interface formelle** (`Protocol`/ABC) du type
`capabilities() / validate() / estimate() / execute()`. Le dispatch se fait par
un `if fournisseur == …` dans `texte.py` et `images.py`. L'animation, elle, est
appelée **directement** depuis `production/animation.py` vers `ia/fal.py` — sans
même passer par un point d'entrée unique.

`modeles.yaml` déclare `a_verifier: true` sur SkyReels et documente en
commentaire des capacités **mesurées** (« ltx-video rend ~4,84 s qu'on lui
demande 5 ou 10 »). Mais la structure de données ne distingue nulle part
**annoncé / mesuré / inconnu** : tout ce qui est écrit dans `fait:` a le même
statut.

---

## H. Workflows existants

- **`produire.yml`** — `workflow_dispatch` avec 10 actions (`episode`,
  `reprendre`, `analyser`, `musique`, `charte`, `voix`, `resultats`,
  `references`, `avant-apres`, `cles`). Restaure le cache et la base, installe
  ffmpeg, exécute, republie la vidéo en lien direct et en artefact ZIP, affiche
  le coût. **C'est la version « sans ordinateur » du produit**, documentée dans
  `TELEPHONE.md` (18 ko).
- **`verifier-videos.yml`** — bloque la présence de vidéos privées suivies par
  git. Doublé d'un `.githooks/pre-commit` optionnel.
- **Aucun workflow de test, de lint, ou de build.**

---

## I. Dette technique identifiée

| # | Dette | Impact |
|---|---|---|
| 1 | **Deux orchestrateurs.** `episode.py` réimplémente reprise et journalisation sans `Moteur`, donc sans cache par empreinte ni validation humaine. | Le chemin de production principal **ne bénéficie pas** du cache du moteur. Deux mécanismes de reprise à maintenir, qui divergeront. |
| 2 | **Pas de paquet `contracts/`.** Les objets pivots sont des dataclasses nues sans version ni provenance ; entre les étapes, ce sont des `dict` JSON. | Une évolution de champ casse silencieusement les jobs en cache. Le code contient déjà des rustines explicites (« compatibilité avec les jobs en cache d'avant `plans@1.13.0` »). |
| 3 | **`Etape.depend_de` déclaré, jamais ordonnancé.** `Moteur` itère linéairement. | Aucune parallélisation. Un plan = une suite d'appels séquentiels alors que image/profondeur/masque sont indépendants. |
| 4 | **Pas d'interface fournisseur.** Dispatch par `if`, animation en accès direct à `ia/fal.py`. | Ajouter un backend vidéo touche `animation.py`, pas seulement `ia/`. Le Director connaît indirectement fal. |
| 5 | **Capacités non qualifiées.** `fait:` mélange annoncé et mesuré ; les mesures vivent en commentaires. | Le code ne peut pas raisonner sur « je ne sais pas ». Les retraits de modèles Groq (17/06 et 13/08/2026) ont été détectés **en production**, pas en amont. |
| 6 | **Pas de stratégie de rendu, une cascade en dur.** `animation.animer()` : modèle → `vie` → `camera`, en if/else. | Impossible d'arbitrer coût/risque/latence, ni d'ajouter `START_END_FRAME` ou `MASKED_EDIT` sans toucher le cœur. |
| 7 | **Réparation = relance.** Après échec de mouvement, on retombe sur `vie`. Aucun diagnostic ne pilote une réparation ciblée. | Un `CAMERA_DOMINANT` et un `STATIC_RENDER` reçoivent le même traitement. |
| 8 | **Aucune mémoire d'expérience.** `PlanAnime.diagnostic` existe mais n'est pas persisté comme série exploitable stratégie → résultat. | Impossible de passer un jour d'un routage par règles à un routage empirique : la donnée n'est pas collectée. |
| 9 | **Les tests ne tournent pas en CI.** 739 tests, aucun workflow. | La seule barrière de régression dépend d'un lancement manuel local. |
| 10 | **Provenance partielle.** `appels_ia` connaît modèle et prompt ; `artefacts` connaît le sha256. Rien ne relie un `.mp4` à sa stratégie, sa version de compilateur, son `RenderSpec`. | On ne peut pas répondre « pourquoi cette vidéo est comme ça ». |
| 11 | **Aucune couche recherche.** `perplexity_api_key` est déclarée dans `config.py` et **lue nulle part**. Ni claim, ni source, ni preuve, ni confiance sur le contenu factuel. | Le format « expliquer un mécanisme » n'a aucun socle de véracité. |
| 12 | Doc obsolète : le `README.md` renvoie à `docs/03-le-template-n8n.md` et `docs/07-budget.md`, **absents** du dépôt (`03` n'existe qu'en archive). | Petite, mais visible dès la première lecture. |

---

## Ce qui est déjà juste, et qu'il ne faut pas casser

1. **La voix comme chronologie officielle** — timings réels mot à mot, coupes
   sur pauses mesurées.
2. **Zéro IA là où le déterminisme suffit** — 14 modules `production/` sur 19.
3. **Les prompts versionnés**, avec invalidation automatique du cache.
4. **La résolution par alias** avec substitution de capacité.
5. **La reprise sans repayer**, doublée de la revérification des fichiers.
6. **L'honnêteté technique** — `ControleCamera.TEXTE_SEULEMENT`, `UNCERTAIN`
   dans `qa_image`, `ChampInterprete.confiance`, `a_verifier: true`. Le code
   refuse déjà de faire passer une intention pour une garantie.
7. **L'observation mesurée** — seuil de mouvement calibré sur des données
   réelles (`SEUIL_MOUVEMENT = 1.0`, entre 0,509 mesuré statique et 1,723
   mesuré en mouvement), pas choisi à vue.
8. **La validation humaine** — table `validations` + `pdz web`, et le moteur
   s'arrête vraiment.
9. **Le gouverneur de calcul en germe** — `animation.noter()` +
   `combien_animer()` : on n'anime pas tout, on anime ce qui compte, sous
   budget.
