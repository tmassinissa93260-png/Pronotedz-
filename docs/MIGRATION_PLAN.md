# Plan de migration

> De l'architecture décrite dans [CURRENT_ARCHITECTURE.md](./CURRENT_ARCHITECTURE.md)
> vers [TARGET_ARCHITECTURE.md](./TARGET_ARCHITECTURE.md), en mesurant
> l'écart de [GAP_ANALYSIS.md](./GAP_ANALYSIS.md).

---

## Règles de la migration

1. **La chaîne actuelle ne cesse jamais de fonctionner.** À la fin de chaque
   phase, `pdz episode fruit-island "…"` produit un `.mp4`. Une phase qui casse
   ça est une phase à annuler.
2. **Jamais un déplacement de fichiers et un changement de comportement dans le
   même commit.** Un renommage se relit ; un renommage mêlé à une refonte ne se
   relit pas.
3. **Toute la suite passe à chaque phase.** C'est la condition de passage, pas
   un objectif.
4. **Une phase = un lot livrable**, mesurable par un critère écrit à l'avance.
5. **Aucune couche n'est construite « pour plus tard ».** Une interface sans
   implémentation est autorisée ; une implémentation sans usage ne l'est pas.
6. **Ce qui est inconnu reste `UNKNOWN`.** Aucune phase n'a le droit de
   transformer une incertitude en valeur par défaut.

---

## Phase 0 — Architecture *(documents seuls)* ✅ **FAIT**

Ce document, plus les trois autres. Rien d'autre n'a été modifié dans le dépôt.

**À produire ensuite, avant la Phase 1** :
- `docs/ADR/` — une décision par fichier, format court (contexte / décision /
  conséquences). Premières ADR à écrire :
  - `ADR-001` — pourquoi `pdz/` en sous-paquets plutôt qu'un monorepo
    `apps/ + packages/`
  - `ADR-002` — pourquoi SQLite plutôt que PostgreSQL, et à quelle condition
    précise il faudra en changer
  - `ADR-003` — pourquoi un ordonnanceur de DAG maison plutôt que Temporal /
    Prefect / Airflow
  - `ADR-004` — pourquoi la voix est la chronologie officielle *(décision déjà
    prise et appliquée, jamais écrite)*
  - `ADR-005` — le profil de production `fiction` vs `explicatif`
    *(**bloquée** par la décision §1 de GAP_ANALYSIS)*
- `docs/CONTRACTS.md` — le catalogue des contrats et leur enveloppe.

**Critère** : les quatre documents sont relus et validés. ✅

---

## Phase 1 — Filet de sécurité ✅ **FAIT**

*La seule phase qui ne construit rien.* Rien de ce qui suit n'aurait de valeur
si une régression pouvait passer inaperçue.

### Livré

| Fichier | Rôle |
|---|---|
| `.github/workflows/tester.yml` | ruff + pytest + couverture, sur push et PR. Installe ffmpeg — 110 tests en dépendent réellement. Aucune clé d'API, aucun coût. |
| `tests/test_architecture.py` | les frontières d'import, vérifiées mécaniquement |
| `tests/test_documentation.py` | aucun lien relatif mort dans la doc vivante |
| `pyproject.toml` | `pytest-cov`, section `[tool.pytest.ini_options]`, couverture sans seuil imposé |

### Ce que la phase a trouvé

**Cinq tests étaient rouges sur `main`**, laissés par le commit qui a basculé
l'écriture de `claude-sonnet-5` vers `openai/gpt-oss-120b` (retrait de
`llama-3.3-70b-versatile` par Groq). Personne ne pouvait le savoir : rien ne
les lançait. Ils affirmaient tous l'identité du modèle par défaut du moment.
Réparés en testant le **mécanisme** plutôt que l'identité — le dépôt a déjà
vécu deux retraits de modèle en 2026, ces tests ne rouilleront plus au
troisième.

**Quatre modules du domaine importent un fournisseur en direct**, et non un
seul comme l'audit manuel l'avait conclu :

| Module | Fournisseur | Réparé en |
|---|---|---|
| `production/animation.py` | `ia.fal` | PHASE 6 — `VideoBackend` |
| `production/voix.py` | `ia.elevenlabs` | PHASE 6 — `TTSBackend` |
| `production/appariement_voix.py` | `ia.elevenlabs` | PHASE 6 — `TTSBackend` |
| `analyse/musique.py` | `ia.audd` | PHASE 6 — `AudioBackend` |

**`pdz/analyse/references.py` lit `os.environ` directement** — alors que
`config.py` promet en toutes lettres être le seul à le faire. La variable
`PDZ_DOSSIER_REFERENCES` n'existe dans aucun champ de `Config`, donc ni
`pdz cles`, ni `.env.exemple` ne la connaissent.

Ces cinq écarts sont **déclarés, datés et verrouillés à double sens** dans
`test_architecture.py` : le test échoue si un sixième apparaît, **et** il
échoue si l'un est réparé sans que sa dérogation soit retirée. Une dette
déclarée ne peut donc ni grossir, ni survivre en silence à sa réparation.

**Six liens morts** dans `docs/`, corrigés : renumérotations
(`06-plan.md` → `10-plan.md`, `07-volume.md` → `08-volume.md`), document
archivé (`03-n8n.md` → `archive/saas-v2/`), et deux cibles qui n'ont jamais
existé — remplacées par la réponse réelle, pas par un autre lien.

### Ce que la phase n'a PAS fait

Aucune logique métier. Les quatre violations de fournisseur et le lecteur
d'environnement sont **déclarés, pas réparés** : les corriger appartient aux
phases 2 et 6. Une phase de filet qui se met à changer le comportement n'est
plus un filet.

### Résultat

```
ruff check .   →  All checks passed!
pytest --cov   →  841 passed, 1 skipped   (0 échec)
couverture     →  80 % sur pdz/
```

Le test ignoré est `test_les_contrats_ne_dependent_de_rien` : il s'active tout
seul le jour où `pdz/contracts/` existera — c'est-à-dire en PHASE 2.

**Critère atteint** : un push qui casse un test est désormais rouge sur GitHub.
**Risque** : nul. **Effort** : faible.

---

## Phase 2 — `contracts/` ✅ **FAIT**

Le paquet dont tout le reste dépend.

### Livré — 21 contrats, 0 dépendance

`pdz/contracts/` n'importe **rien** d'autre de `pdz` : vérifié par
`tests/test_architecture.py`, qui n'est plus ignoré.

| Fichier | Contrats |
|---|---|
| `base.py` | `Contrat`, `Provenance`, migrations, empreinte |
| `communs.py` | `Certitude`, `StatutCapacite`, `Verdict`, `Severite`, `Profil` |
| `topic.py` | `TopicRequest` |
| `research.py` · `narrative.py` | `ResearchState`/`Claim`/`Source` · `NarrativeState` |
| `director.py` | `DirectorState` + 6 sous-états |
| `world.py` · `causality.py` | `WorldState`/`Entite`/`Etat` · `CausalState` |
| `audio.py` | `AudioTimeline`/`Replique`/`Mot` |
| `shot.py` · `perception.py` | `ShotGraph`/`ShotSpec` · `PerceptualContract` |
| `motion.py` · `camera.py` | `MotionProgram` · `CameraProgram` |
| `render.py` · `capabilities.py` | `RenderSpec…`/`Strategie` · `CapabilityGraph` |
| `execution.py` | `ExecutionPlan` + ordonnancement en vagues |
| `observation.py` · `diagnosis.py` · `repair.py` | la boucle de retour |
| `experience.py` | `ExperienceRecord` |

### Les règles rendues exécutables

Ce que le dépôt appliquait par culture devient vérifiable :

| Règle | Où | Test |
|---|---|---|
| Un `FAIT` sans source n'est pas affirmable | `Claim.utilisable_comme_fait` | ✅ |
| Une confiance de 0,99 ne promeut pas un heuristique | idem | ✅ |
| Un axe non mesuré vaut `INCERTAIN`, jamais `REUSSI` | `ObservationReport.verdict_axe` | ✅ |
| Une capacité `ANNONCE` n'engage pas | `Capacite.utilisable` | ✅ |
| `valeur=None` ≠ `valeur=False` | `Capacite` | ✅ |
| Une entité non observée n'est pas « conforme » | `Entite.ecart_connu` | ✅ |
| Un diagnostic peu sûr n'est pas actionnable | `FailureDiagnosis.actionnable` | ✅ |
| Une expérience sans conclusion n'est pas exploitable | `ExperienceRecord.exploitable` | ✅ |

`ObservationReport` sait aussi dire ses propres angles morts
(`axes_non_mesures`) — la carte de ce que le système ne sait pas encore
regarder, utile telle quelle.

### Le cache : opt-in, volontairement

`versions(*contrats)` produit le dictionnaire à ajouter à `Agent.signature()`.
Une étape qui manipule un contrat voit son cache s'invalider quand ce schéma
change — exactement le mécanisme des versions de prompt.

**Rien n'a été branché sur les étapes existantes.** Aucun producteur ne
consomme encore de contrat : ajouter leurs versions à l'empreinte aujourd'hui
invaliderait tout le cache du dépôt et ferait repayer des vidéos déjà
produites, sans rien garantir de plus. Le branchement se fait phase par
phase, avec le producteur qui l'utilise.

### Les adaptateurs — `pdz/adaptateurs.py`

Règle 39 appliquée : `ANCIEN → ADAPTATEUR → NOUVEAU`. Rien n'a été supprimé.

`PlanScript → ShotSpec` · `PlanScript[] → ShotGraph` ·
`MotionProgram(legacy) → MotionProgram + CameraProgram` ·
`ContratVisuel → PerceptualContract` · `BandeVoix → AudioTimeline`

**Ce module est fait pour mourir** : chaque fonction existe parce qu'un
producteur écrit encore l'ancienne forme. C'est l'endroit où lire ce qu'il
reste à migrer.

Un adaptateur n'invente **jamais**. `ShotSpec.but` reste vide sur toute la
production existante — parce qu'aucun `PlanScript` ne l'a jamais déclaré, et
que le remplir ferait répondre `est_specifie == True` partout, rendant la
mesure inutile le jour de son introduction. C'est testé explicitement.

### La séparation caméra / mouvement

`motion_program()` et `camera_program()` produisent deux contrats depuis un
seul objet legacy. C'est la fonctionnalité, pas un rangement : tant que les
deux vivent dans le même champ, aucun diagnostic ne peut dire « ça bouge,
mais c'est la caméra ». `ControleCamera.TEXTE_SEULEMENT` est conservé — et
`est_garantie` répond `False`, ce qui est la vérité sur fal.ai.

### Résultat

```
ruff check .   →  All checks passed!
contrats       →  122 tests
adaptateurs    →   32 tests
golden         →    9 tests
```

**Critère atteint** : la compilation d'un épisode est inchangée — le golden
test le prouve, et échoue bien quand on la modifie (vérifié en simulant une
régression sur `PART_REACTION`).

---

## Phase 2b — Golden tests ✅ **FAIT** *(avancée)*

Prévue en PHASE 18, avancée ici : les phases 5 à 9 vont réécrire la chaîne
qui produit ces structures. Sans référence gelée, un changement de
comportement passerait pour un changement voulu.

`tests/test_golden.py` + `tests/golden/fiction_trahison.json`, régénérable
par `python -m tests.golden_regenerer` — un script séparé, jamais une option
`--update` : une mise à jour de référence doit être un geste délibéré.

**Ce qui est gelé** : combien de plans, quelles durées, quel ordre, quelles
arêtes, quelles sondes. **Ce qui ne l'est jamais** : une sortie générative.
Pas de pixels, pas de prompt figé — les figer produirait un test qui échoue
sans régression, le plus sûr moyen de faire ignorer une suite.

Deux niveaux distincts, et le second est le plus précieux :
- la **référence** dit « c'était comme ça » ;
- les **invariants** disent « ça doit être comme ça » — la durée des plans
  couvre exactement la parole, aucun trou de numérotation, chaque plan dure
  assez pour être vu. Ils survivent à une régénération volontaire.

Le cas explicatif viendra avec la PHASE 3 : écrire aujourd'hui une référence
pour une chaîne qui n'existe pas ne testerait que la référence elle-même.

---

## Phase 3 — Director *(bloquée par la décision §1 de GAP_ANALYSIS)*

> ⚠️ **Ne commence pas avant l'arbitrage `fiction` / `explicatif`.**

Sous l'option A recommandée :

- `pdz/director/` : contrat `DirectorState` (`thesis, claims, causal_chain,
  viewer_knowledge_state, emotional_curve, visual_language, visual_evidence,
  shot_intentions, continuity_anchors`), produit par les agents existants
  (`BriefWriter`, `ScriptWriter`) enrichis.
- `pdz/research/` : `ResearchBackend` (Protocol) + `MockResearchAdapter` +
  `PerplexityResearchAdapter` ; `FactGraph`, `Claim`, `Source`, statuts
  `FACT/HEURISTIC/UNKNOWN/HUMAN_VERIFIED`, détection de conflits et
  d'obsolescence.
- `pdz/evidence/` : `CLAIM → EVIDENCE → VISUAL → SHOT`. `fidelite_visuelle.py`
  y devient le vérificateur du dernier maillon.
- Le profil `fiction` fournit un `NarrativeState` issu de l'`Univers` — les deux
  profils convergent sur le **même** `DirectorState`.

**Critère** : `pdz creer --sujet "Comment fonctionne un moteur électrique ?"`
produit un `factgraph.json` où chaque claim porte au moins une source, ou le
statut `UNKNOWN` — et **aucun claim inventé ne porte le statut `FACT`**.
**Risque** : élevé (couche neuve, format neuf). **Effort** : élevé.

---

## Phase 4 — Timeline *(consolidation)*

La phase la plus courte : la chaîne `SCRIPT → TTS → VoiceTimeline` est déjà
juste. Il s'agit de la **nommer**.

- `pdz/audio/` : `BandeVoix` → contrat `VoiceTimeline`.
- Un `AudioPlan` (pistes voix / musique / ambiance / SFX) — pour l'instant avec
  la seule piste voix remplie. L'interface existe, l'implémentation suit.

**Critère** : le contrat `VoiceTimeline` porte les timings mot à mot, et
`storyboard.decouper()` ne lit plus que lui.
**Risque** : faible. **Effort** : faible.

---

## Phase 5 — Shot Compiler

- `PlanScript` → contrat `ShotSpec` avec les champs manquants : `purpose`,
  `state_before`, `event`, `state_after`, `success_criteria`.
- `ShotGraph` : une **structure**, pas une liste — les continuités entre plans
  deviennent des arêtes.
- `pdz/perception/` : `PerceptualContract` extrait de `ContratVisuel` +
  `MotionProgram.cible_perceptuelle`, complété par `attention` ordonnée et
  `ne_doit_pas_etre_confondu_avec`.

**Critère** : chaque plan répond aux questions 1 et 2 des cinq.
**Risque** : moyen. **Effort** : moyen.

---

## Phase 6 — World / Causality

- `pdz/world/` : `Entity, State, Relation, Position, Geometry, Identity,
  Material, Constraints`, avec `expected_state` / `observed_state` /
  `confidence`. `continuite.py` et `geometrie.py` y sont absorbés.
- `pdz/causality/` : chaîne causale, et la décision « quelles conséquences
  montrer ».

**Critère** : après chaque plan validé, le `WorldState` est mis à jour et le
`STATE DELTA` est journalisé — même si, à ce stade, rien ne le consomme encore.
**Risque** : moyen. **Effort** : moyen.

---

## Phase 7 — Motion & Camera

- `pdz/motion/` : le Motion DSL s'étend — `static_regions`, trajectoires,
  `temporal_curve`, rigide / non-rigide, `motion_priority`.
- `pdz/camera/` : `CameraProgram` **séparé**, avec repère spatial partagé.
  `montage.Mouvement` (Ken Burns) devient une compilation possible du
  `CameraProgram`, et non plus une seconde notion de caméra sans rapport.
- `ControleCamera` s'étend : `TEXTE_SEULEMENT` reste la valeur honnête pour
  fal.ai, et une valeur `PARAMETRIQUE` apparaîtra le jour où un backend
  l'accepte **et qu'on l'a mesuré**.

**Critère** : un même `CameraProgram` compile vers un texte pour un backend i2v
**et** vers un filtre FFmpeg pour la stratégie procédurale.
**Risque** : moyen. **Effort** : moyen.

---

## Phase 8 — Rendering

C'est la phase qui corrige la violation d'architecture repérée en Phase 1.

- `pdz/backends/` : interfaces `ImageBackend / VideoBackend / TTSBackend /
  DepthBackend / SegmentationBackend / AudioBackend / EditBackend`
  (`capabilities / validate / estimate / execute`), plus un `Mock*` pour
  chacune. Les 6 adaptateurs existants sont enveloppés, pas réécrits.
- **`production/animation.py` cesse d'appeler `ia/fal.py` en direct.** Le test
  d'architecture de la Phase 1 passe au vert.
- `pdz/capabilities/` : `modeles.yaml` gagne le statut par capacité —
  `ANNONCE / MESURE / INCONNU`, avec la date de mesure. Les mesures qui vivent
  aujourd'hui en commentaires (« ltx-video rend ~4,84 s ») deviennent des
  données.
- `pdz/renderability/` : score `HIGH/MEDIUM/LOW` + validation statique
  (`risque_prompt.py` y est absorbé) + **décomposition automatique** d'un plan
  `LOW`.
- `pdz/strategies/` : `RenderStrategyGraph`. La cascade en dur devient un choix
  arbitré. `vie.py` est nommé `2.5D`, `montage.Mouvement` est nommé
  `PROCEDURAL`, l'appel Kling est `DIRECT_I2V`. `animation.noter()` +
  `combien_animer()` deviennent le Compute Governor.

**Critère** : ajouter un septième fournisseur ne touche que `backends/` et
`modeles.yaml`. Zéro ligne dans `production/`.
**Risque** : élevé (c'est le chemin qui dépense l'argent). **Effort** : élevé.

---

## Phase 9 — Execution

- `pdz/execution/` : `ExecutionPlan` en DAG, nœuds portant `input, output,
  dependencies, estimated_cost, estimated_duration, retry_policy, cache_key`.
- Ordonnanceur `asyncio` maison (~200 lignes), avec la table `etapes` comme
  journal de reprise — elle joue déjà ce rôle.
- **Un seul orchestrateur** : `episode.py` devient `orchestration/`, qui
  assemble un DAG et le confie au kernel. La reprise dupliquée (`_fait()` /
  `_noter()`) disparaît, mais sa **revérification des fichiers cités** monte
  dans le kernel — c'est un acquis né d'un échec réel, il ne se perd pas.

**Critère** : les images d'un plan et sa carte de profondeur se calculent en
parallèle ; un `Ctrl-C` au milieu, puis `pdz reprendre`, ne repaie rien.
**Risque** : élevé. **Effort** : élevé.

---

## Phase 10 — Observation

- `pdz/observation/` : `ObservationReport` unifié sur les six axes. Les cinq
  vérificateurs existants deviennent des **sondes** de ce rapport ; leurs seuils
  calibrés sur données réelles sont conservés tels quels.
- Axes à compléter : temporel (gels, scintillement, coupes inattendues),
  sémantique (identité, événement accompli), continuité (couleur, géométrie),
  audio (loudness, crêtes).
- **`UNKNOWN` partout où la sonde n'existe pas.** Aucun axe ne reçoit une valeur
  par défaut qui ressemblerait à une mesure.

**Critère** : chaque plan rendu produit un `ObservationReport`, et un axe non
mesuré s'affiche `UNKNOWN` — jamais `OK`.
**Risque** : faible. **Effort** : moyen.

---

## Phase 11 — Diagnostics & Repair

- `pdz/diagnostics/` : `expected vs observed` généralisé, taxonomie des 18 modes
  d'échec, chaque diagnostic portant `severite / confiance / preuve /
  candidats_reparation`.
- `pdz/repair/` : arbre `PROMPT_FIX · MOTION_FIX · CAMERA_FIX · ANCHOR_FIX ·
  STRATEGY_FIX · MODEL_FIX · DECOMPOSITION · LOCAL_REPAIR`, chaque branche
  évaluée `succès_attendu / coût / latence / risque`.
- Réparation locale par masque, plutôt que régénération du plan entier.
- **Chaque tentative est enregistrée** — c'est aussi l'alimentation de la
  Phase 13.

**Critère** : un `CAMERA_DOMINANT` et un `STATIC_RENDER` ne reçoivent plus le
même traitement, et le journal dit pourquoi cette branche a été choisie.
**Risque** : moyen. **Effort** : élevé.

---

## Phase 12 — Editor

- `Montage` → contrat `EditTimeline` (pistes vidéo / voix / musique / SFX /
  sous-titres / graphiques / overlays / transitions).
- `FFmpegCompiler` devient un `EditBackend` formel.

**Critère** : aucune commande FFmpeg n'est construite hors de
`backends/ffmpeg.py`.
**Risque** : faible. **Effort** : faible.

---

## Phase 13 — Memory

- `pdz/memory/` : les quatre mémoires séparées + `MemoryPack` (ne jamais envoyer
  tout l'historique).
- **`ExperienceMemory`** : table `experiences` — `modele, strategie, prompt,
  cout, latence, echec, diagnostic, reparation, resultat`. C'est ce qui rend le
  routage empirique possible **un jour** ; sans collecte, jamais.
- Provenance complète sur chaque artefact : `final.mp4 → shot_03 →
  RenderSpec@1.2 → strategy=2.5D → depth_backend=vX → compiler_version=0.8.0`.

**Critère** : `pdz production <job>` répond « pourquoi cette vidéo est comme
ça » pour n'importe quel plan.
**Risque** : faible. **Effort** : moyen.

> **Note d'ordonnancement.** La collecte d'expérience est le composant dont le
> coût de retard est le plus élevé (GAP §4). Si une seule chose peut être
> avancée hors de son ordre, c'est l'**écriture** dans `experiences` — dès la
> Phase 8, même si `memory/` n'existe pas encore. Une table qui se remplit tôt
> vaut mieux qu'un paquet bien rangé qui se remplit tard.

---

## Phase 14 — Evaluation

- `tests/golden/` : corpus de productions de référence — `electric_motor`,
  `airplane_takeoff`, `smartphone_mechanism`, `electric_car`,
  `industrial_machine`, plus **un cas fiction** issu des univers existants.
- Pour chacun : script attendu, shot graph attendu, états attendus, mouvement
  attendu, timeline attendue, comportement QA attendu.
- Backends mock partout : le corpus tourne en CI, gratuitement et de façon
  déterministe.

**Critère** : un changement de code se juge contre le corpus, pas contre une
impression.
**Risque** : faible. **Effort** : moyen.

---

## Ordonnancement et dépendances

```
Phase 0 (fait)
   ↓
Phase 1  filet de sécurité ─────────────────┐  (aucune dépendance)
   ↓                                        │
Phase 2  contracts ─────────────────────────┤  (bloque tout le reste)
   ↓                                        │
   ├─ Phase 3  director/research  ⚠ bloquée par la décision §1
   ├─ Phase 4  timeline ──→ Phase 5  shot ──→ Phase 6  world/causality
   │                             ↓
   │                        Phase 7  motion/camera
   │                             ↓
   └────────────────────→   Phase 8  rendering ──→ Phase 9  execution
                                 ↓                      ↓
                            Phase 10 observation        │
                                 ↓                      │
                            Phase 11 diagnostics/repair │
                                 ↓                      │
                            Phase 12 editor ←───────────┘
                                 ↓
                            Phase 13 memory
                                 ↓
                            Phase 14 evaluation
```

Les phases 3 et 4→7 sont **indépendantes** l'une de l'autre : si la décision §1
tarde, la branche 4→7 avance sans elle.

---

## Ce qui pourrait mal tourner

| Risque | Probabilité | Parade |
|---|---|---|
| La Phase 2 casse le cache et fait repayer des productions | moyenne | la version de contrat entre dans l'empreinte **dès le premier commit** ; un test compare le coût d'une reprise avant/après |
| La Phase 8 change les vidéos produites sans qu'on le voie | élevée | la Phase 14 devrait précéder la 8. **Recommandation : avancer un golden test minimal (1 cas fiction, backends mock) juste après la Phase 2** |
| Le grand renommage noie une régression | élevée | règle 2 : jamais renommage et comportement dans le même commit |
| La décision §1 ne vient pas | — | la branche 4→7 n'en dépend pas ; seule la Phase 3 attend |
| Un fournisseur retire un modèle en cours de migration | **avérée deux fois en 2026** | la Phase 8 (`capabilities/` avec statut mesuré et daté) est précisément la parade ; d'ici là, `pdz cles` reste le filet |
| L'architecture grossit plus vite que l'usage | moyenne | règle 5 : une interface sans implémentation est permise, une implémentation sans usage ne l'est pas |

---

## Ce qui reste hors périmètre

Interfaces préparées, **non implémentées** : vidéo conditionnée par trajectoire,
génération native de caméra, modèles first/last frame, modèles à image de
référence, édition par masque, simulation physique, world models, mémoire
géométrique, reconstruction 3D, représentations 4D, mémoire multimodale longue.

Elles ne sont pas construites. Elles sont seulement **rendues possibles** par la
séparation `strategies/` ↔ `backends/` ↔ `capabilities/`.
