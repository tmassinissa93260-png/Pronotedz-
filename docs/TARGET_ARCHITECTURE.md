# Architecture cible — le compilateur audiovisuel

> Ce document décrit **où l'on va**. L'état actuel est dans
> [CURRENT_ARCHITECTURE.md](./CURRENT_ARCHITECTURE.md), l'écart dans
> [GAP_ANALYSIS.md](./GAP_ANALYSIS.md), le chemin dans
> [MIGRATION_PLAN.md](./MIGRATION_PLAN.md).

---

## 0. Le principe

Le produit n'est pas un générateur de vidéos. C'est un **compilateur** :
il traduit une intention humaine en artefact vidéo, à travers une suite de
représentations intermédiaires typées, versionnées et vérifiables.

Un modèle vidéo, un modèle image, FFmpeg, un moteur 2.5D : ce sont des
**backends**. Le compilateur est le produit.

**Le prompt n'est jamais la source de vérité.** Un prompt est une *projection
temporaire* d'un contrat structuré. Si une information n'existe que dans un
prompt, elle n'existe pas.

---

## 1. La chaîne de compilation

```
USER IDEA
  ↓ TopicIR
RESEARCH → FactGraph
  ↓
DIRECTOR CORE → WorldState / CausalState / EvidenceState
  ↓
SCRIPT COMPILER → ScriptState
  ↓ TTS
VoiceTimeline                       ← LA CHRONOLOGIE OFFICIELLE
  ↓
SHOT GRAPH → SceneState → PerceptualContract
  ↓
MOTION PROGRAM + CAMERA PROGRAM
  ↓
RenderSpecRequested
  ↓ analyse de faisabilité
RENDERABILITY → (décomposition si nécessaire)
  ↓ validation statique
CAPABILITY RESOLUTION → RENDER STRATEGY GRAPH
  ↓
ExecutionPlan (DAG)
  ↓ backends
RenderArtifact
  ↓
OBSERVATION → ObservationReport
  ↓
EXPECTED vs OBSERVED → FailureDiagnosis
  ↓
REPAIR COMPILER → RepairPlan → (boucle)
  ↓
ValidatedShot → mise à jour WorldState/Memory → plan suivant
  ↓
EditTimeline → AudioMaster → Subtitles → FinalQA
  ↓
MASTER VIDEO + ExperienceMemory
```

Aucune couche ne disparaît. Certaines sont, au départ, des implémentations
minimales — mais elles existent comme **frontière typée**.

---

## 2. Structure du dépôt — décision assumée

> **Le monorepo `apps/ + packages/` en 25 paquets n'est pas retenu.**

Raisons, tirées de l'audit :

1. Un seul utilisateur, un seul processus, un seul déploiement. 25 paquets
   installables imposeraient 25 `pyproject.toml`, une résolution de versions
   croisées et un outil de build de monorepo — pour zéro frontière de
   déploiement réelle. C'est la règle « chaque dépendance doit avoir une
   justification », appliquée à l'outillage.
2. Le dépôt a déjà **807 tests qui importent `pdz.*`**. Un déplacement massif
   de fichiers réécrirait ces 807 tests dans le même commit que le changement
   d'architecture — exactement la situation où une régression devient
   invisible.
3. La séparation qui compte n'est pas physique, elle est **directionnelle** :
   qui a le droit d'importer qui. Elle se tient par une règle testée, pas par
   des dossiers.

**Ce qui est retenu** : les mêmes 29 responsabilités, en sous-paquets de `pdz/`,
avec les frontières d'import vérifiées par un test.

```
pdz/
├── kernel/          (ex-moteur/) job, étape, artefact, événement, provenance,
│                    cache, idempotence, coût, annulation, DAG
├── contracts/       ★ NOUVEAU — tous les contrats versionnés
├── research/        ★ NOUVEAU — FactGraph, sources, confiance
├── director/        thesis, claims, courbe émotionnelle, état du spectateur
├── world/           ★ NOUVEAU — entités, états, relations, expected/observed
├── causality/       ★ NOUVEAU — chaînes causales
├── evidence/        ★ NOUVEAU — claim → preuve → représentation → plan
├── script/          (ex-agents/ecriture/) compilateur de script
├── audio/           (ex-production/voix.py) TTS, VoiceTimeline, plan sonore
├── shot/            (ex-production/storyboard.py) ShotGraph, décomposition
├── perception/      ★ NOUVEAU — PerceptualContract (extrait de contrat_visuel)
├── motion/          (ex-production/motion_program.py) Motion DSL
├── camera/          ★ NOUVEAU — CameraProgram, séparé du mouvement d'objet
├── renderability/   ★ NOUVEAU — score de faisabilité, décomposition
├── capabilities/    (ex-ia/registre.py) annoncé / mesuré / inconnu
├── strategies/      ★ NOUVEAU — RenderStrategyGraph
├── execution/       ★ NOUVEAU — ExecutionPlan (DAG), ordonnanceur, cache
├── backends/        (ex-ia/) adaptateurs derrière une interface commune
├── observation/     (ex-production/verification_*, qa_*) ObservationReport
├── diagnostics/     ★ NOUVEAU — taxonomie d'échec, expected vs observed
├── repair/          ★ NOUVEAU — compilateur de réparation, arbre de recherche
├── editor/          (ex-video/) EditTimeline → FFmpegCompiler
├── memory/          ★ NOUVEAU — sémantique / monde / visuelle / expérience
├── evaluation/      ★ NOUVEAU — golden tests, benchmarks, régression
├── orchestration/   (ex-production/episode.py) assemble, ne décide rien
├── api/             (ex-web.py)
└── cli.py
```

`pdz/analyse/` (mesure locale de vidéos de référence, zéro IA) reste tel quel :
c'est un outil d'entrée amont, pas une couche du compilateur.

### La règle d'import, testée

```
contracts   ← n'importe RIEN de pdz (sauf kernel/types)
kernel      ← contracts
director/world/causality/evidence/script/shot/motion/camera/perception
            ← contracts, kernel        (JAMAIS backends)
renderability/capabilities/strategies
            ← contracts, kernel, capabilities
execution   ← contracts, kernel, strategies, backends
backends    ← contracts, capabilities  (JAMAIS director, JAMAIS shot)
observation/diagnostics/repair
            ← contracts, kernel        (backends autorisé pour l'observation IA)
orchestration ← tout
```

> **Le Director ne doit jamais connaître le nom d'un fournisseur.** Cette règle
> est aujourd'hui respectée par les agents et **violée par
> `production/animation.py`**, qui appelle `ia/fal.py` en direct. Un test
> d'architecture la rendra impossible à violer de nouveau.

---

## 3. Les contrats

Tout contrat hérite d'une enveloppe commune :

```python
class Contrat(BaseModel):
    schema_version: str          # "1.2.0" — semver
    id: str                      # "shot_03", "job_x/shot_03/render_spec"
    cree_le: float
    maj_le: float
    producteur: str              # "ShotPromptWriter@1.4.0"
    provenance: Provenance       # d'où vient chaque décision
    dependances: tuple[str, ...] # ids des contrats en entrée
    payload: ...                 # le contenu typé, propre à chaque contrat
```

**Contrats de la chaîne** : `TopicIR` · `ResearchState` · `FactGraph` ·
`DirectorState` · `WorldState` · `CausalState` · `EvidenceState` ·
`ScriptState` · `VoiceTimeline` · `ShotGraph` · `ShotSpec` ·
`PerceptualContract` · `MotionProgram` · `CameraProgram` · `AudioPlan` ·
`RenderSpec` · `ExecutionPlan` · `ObservationReport` · `FailureDiagnosis` ·
`RepairPlan` · `EditTimeline` · `MemoryState`.

**Règles** :
- versionnement semver, avec migration explicite `1.0 → 1.1` ;
- une version majeure ne casse jamais silencieusement une production en cache :
  un contrat illisible lève, il ne se dégrade pas en `dict` partiel ;
- sérialisation JSON stable (clés triées) — c'est ce qui rend l'empreinte de
  cache reproductible ;
- **la version de contrat entre dans la clé de cache**, comme la version de
  prompt aujourd'hui.

Le catalogue de prompts versionnés du dépôt (`prompts/catalogue/<id>@<semver>`)
est le modèle éprouvé à répliquer.

---

## 4. Les couches, une par une

### 4.1 Kernel
Identité de projet, jobs, transactions, événements, versionnement, artefacts,
provenance, dépendances, états, réessais, **idempotence**, journaux, coûts,
erreurs, annulation, délais.

Un job interrompu reprend sans repayer les plans validés. **Acquis** — à
généraliser à un ordonnanceur de DAG.

### 4.2 Topic IR
```yaml
topic: "Comment fonctionne un moteur électrique ?"
langue: fr
audience: general_public
duree_cible_s: 45
plateformes: [tiktok, shorts]
famille_de_style: cinematic_educational
```
Le sujet ne part **jamais** directement dans un prompt vidéo.

### 4.3 Research Engine → FactGraph
Indépendant du LLM (adaptateurs : Perplexity, recherche ouverte, mock).
```
Claim
 ├── sources[]
 ├── evidence[]
 ├── confiance          0..1
 ├── statut_temporel    actuel | daté | obsolète
 ├── conflits[]
 └── visualisabilite    peut-on le MONTRER ?
```
Statuts : `FACT` · `HEURISTIC` · `UNKNOWN` · `HUMAN_VERIFIED`.
**Une information incertaine ne devient jamais un fait certain.** Le moteur
doit savoir détecter sources contradictoires, information périmée, preuve
manquante, confiance faible.

`ChampInterprete(valeur, confiance)` de `univers/modele.py` porte déjà cette
discipline : c'est la brique à généraliser.

### 4.4 Director Core
Produit — jamais des prompts visuels : `thesis`, `claims`, `causal_chain`,
`viewer_knowledge_state`, `emotional_curve`, `visual_language`,
`visual_evidence`, `shot_intentions`, `continuity_anchors`.

Il sait ce que le spectateur est **censé comprendre** à chaque instant :
`T0 ignorance → T1 question → T2 première explication → T3 mécanisme →
T4 compréhension causale → T5 payoff`.

### 4.5 World State
Léger, pas un simulateur 4D. `Entity`, `State`, `Relation`, `Position`,
`Orientation`, `Geometry`, `Identity`, `Material`, `Constraints` — et surtout
`expected_state` / `observed_state` / `confidence`.

```
EXPECTED WORLD → RENDER → OBSERVED WORLD → STATE DELTA
```

### 4.6 Causal Model
`pedal_pressed → control_signal → motor_torque → wheel_rotation →
vehicle_acceleration`. Le système décide **quelles conséquences méritent
d'être montrées**.

### 4.7 Evidence Model
`CLAIM → EVIDENCE → VISUAL REPRESENTATION → SHOT`. Chaque claim important est
relié à une preuve visuelle nommée.

### 4.8 Script Compiler
`line_id, text, claim, purpose, emotion, speaker, estimated_duration`, puis TTS,
puis **alignement mot à mot**, puis `VoiceTimeline` — et seulement ensuite les
durées de plans.

**Aucune durée de plan n'est figée avant les timings réels du TTS.** ✅ Acquis.

### 4.9 Shot Graph
Un plan est un nœud : `shot_id, purpose, claim, evidence, duration,
state_before, event, state_after, subject, secondary_entities, composition,
perception, camera, motion, audio, continuity, success_criteria`.

Jamais `prompt = "cinematic airplane taking off"`.

### 4.10 Shot Decomposition Optimizer
Quand le score de faisabilité est trop bas, **un plan complexe devient
plusieurs plans exécutables** — automatiquement, avant toute dépense.

### 4.11 Perceptual Contract
```yaml
objectif_principal: acceleration
attention: [aircraft, runway_motion, engine_light]
doit_percevoir: [acceleration, takeoff]
ne_doit_pas_etre_confondu_avec: [camera_only_motion, static_aircraft]
```
C'est ce contrat que la QA utilise — pas un score esthétique.

### 4.12 Motion DSL
`static_regions`, `rigid_motion`, `non_rigid_motion`, `subject_trajectory`,
`camera_trajectory`, `environment_motion`, `temporal_curve`, `invariants`,
`motion_priority`. Indépendant du fournisseur, compilé ensuite vers 2D / 3D /
chemin de caméra / contrôles spécifiques / 2.5D / procédural.

### 4.13 Camera Program
**Programme séparé** : `position, orientation, lens, FOV, dolly, truck, pan,
tilt, orbit, tracking, zoom, depth, speed, acceleration`.
Mouvement d'objet et mouvement de caméra sont distincts — mais partagent le
même repère spatial.

### 4.14 Renderability Analyzer
Avant toute dépense : complexité caméra, complexité de mouvement, nombre
d'entités, rigide / non-rigide, contraintes d'identité, profondeur, durée,
contrôles requis, support fournisseur → `HIGH | MEDIUM | LOW`.
C'est un score de **faisabilité technique**, jamais de qualité esthétique.
`LOW` déclenche décomposition, changement de stratégie, simplification ou
rendu hybride.

### 4.15 Visual Bible & Anchors
`Univers` joue déjà le rôle de Visual Bible. À ajouter : `AnchorSpec`
(`appearance, geometry, material, color, scale, state, references,
preservation_rules`), utilisable par la génération d'image, la vidéo, le
montage, la QA, la continuité et la réparation.

### 4.16 Memory Pack et les quatre mémoires
**Jamais tout l'historique à chaque plan.** Un `MemoryPack` ne contient que :
entités actives, frames pertinentes, état du monde courant et précédent, chaîne
causale en cours, continuités non résolues, anchors visuels, événements audio
importants.

Quatre mémoires séparées : **sémantique** (ce que raconte la vidéo), **monde**
(état des entités), **visuelle** (frames, références), **expérience** (modèle,
stratégie, prompt, coût, latence, échec, diagnostic, réparation, résultat).
`Geometric Memory` est prévue comme abstraction, hors MVP.

### 4.17 RenderSpec et validation statique
`RenderSpecRequested` (ce que le Director veut) → compilé en
`RenderSpecExecutable` (ce qu'un backend peut recevoir). **Jamais une intention
LLM envoyée directement à un fournisseur.**

Bloqué **avant** génération : caméra non supportée, durée invalide, anchor
manquant, asset manquant, mouvements en conflit, référence manquante,
transition non supportée, budget dépassé, incompatibilité fournisseur.

### 4.18 Capability Graph
```yaml
modele: exemple-video
capacites:
  text_to_video:   {valeur: true,  statut: ANNONCE}
  image_to_video:  {valeur: true,  statut: MESURE, le: 2026-08-13}
  camera_control:  {statut: INCONNU}
  masks:           {valeur: false, statut: MESURE}
```
**`ANNONCE` ≠ `MESURE` ≠ `INCONNU`.** Une capacité annoncée n'est jamais
traitée comme mesurée. Une capacité inconnue reste inconnue — et l'adaptateur
est construit pour qu'on puisse l'ajouter plus tard.

### 4.19 Render Strategy Graph
Pas un `ModelRouter`. Un graphe de stratégies :
`DIRECT_I2V · REFERENCE_I2V · START_END_FRAME · CONTROLLED_VIDEO · V2V_EDIT ·
MASKED_EDIT · 2.5D · 3D · PROCEDURAL · HYBRID`.

Le système choisit **stratégie + backend + paramètres**, pas un modèle.
`vie.py` (parallaxe locale) et `montage.Mouvement` (Ken Burns) sont déjà,
respectivement, `2.5D` et `PROCEDURAL` — non nommés.

### 4.20 Provider Adapters
```python
class VideoBackend(Protocol):
    def capabilities(self) -> CapabilitySet: ...
    def validate(self, spec: RenderSpec) -> ValidationResult: ...
    def estimate(self, spec: RenderSpec) -> CostEstimate: ...
    async def execute(self, spec: RenderSpec) -> RenderArtifact: ...
```
Même principe pour `ImageBackend`, `DepthBackend`, `SegmentationBackend`,
`TTSBackend`, `AudioBackend`, `EditBackend`, `3DBackend`, `ProceduralBackend`,
`ResearchBackend`. Chacun a une implémentation `Mock*` — c'est ce qui rend les
tests d'intégration gratuits et déterministes.

### 4.21 Execution Plan = DAG
```
BASE IMAGE
 ├── DEPTH ──→ 2.5D CAMERA
 ├── SUBJECT MASK ──→ VIDEO GENERATION
 ├── GRAPHICS
 └── ATMOSPHERE
                ↓
           COMPOSITING
```
Chaque nœud : `input, output, dependencies, estimated_cost, estimated_duration,
retry_policy, cache_key`.

### 4.22 Observer
Après chaque rendu, un `ObservationReport` sur six axes :
**technique** (durée, fps, résolution, codec, intégrité) ·
**temporel** (coupes, gels, scintillement, cohérence) ·
**mouvement** (caméra, sujet, environnement, amplitude, rigide/non-rigide) ·
**sémantique** (présence, identité, événement accompli, preuve visuelle) ·
**continuité** (couleur, géométrie, état, position, identité) ·
**audio** (synchronisation, alignement voix, SFX, loudness, crêtes).

### 4.23 Expected vs Observed → Diagnostic
```
DELTA = OBSERVED - EXPECTED
```
Taxonomie : `STATIC_RENDER · WEAK_MOTION · EXCESSIVE_MOTION · CAMERA_DOMINANT ·
SUBJECT_MOTION_MISSING · PRIMARY_EVENT_MISSING · RIGID_BODY_DEFORMATION ·
NON_RIGID_FAILURE · IDENTITY_DRIFT · GEOMETRY_DRIFT · COLOR_DRIFT · FLICKER ·
UNEXPECTED_CUT · DURATION_FAILURE · AUDIO_DESYNC · SUBTITLE_DESYNC ·
CONTINUITY_FAILURE · UNKNOWN`.

Chaque diagnostic porte `severite`, `confiance`, `preuve`,
`candidats_reparation`.

### 4.24 Repair Compiler
Jamais `retry 1 / retry 2 / retry 3`. Un arbre :
`PROMPT_FIX · MOTION_FIX · CAMERA_FIX · ANCHOR_FIX · STRATEGY_FIX ·
MODEL_FIX · DECOMPOSITION · LOCAL_REPAIR`, chaque branche évaluée par
`succès_attendu / coût / latence / risque`.

**Réparation locale** : `VIDEO → RÉGION FAUTIVE → MASQUE → RÉPARATION →
CONTEXTE TEMPOREL → COMPOSITE`. On ne régénère jamais un plan entier quand une
réparation locale est techniquement possible.

### 4.25 Compute Governor
```
              valeur_narrative
maximiser  ──────────────────────
             coût_total_attendu
```
Un plan narrativement critique reçoit un backend premium ; un plan secondaire
prend du procédural, du 2.5D ou une image bon marché.
`animation.noter()` + `combien_animer()` en sont déjà la première version.

### 4.26 Audio Engine & Subtitles
Timeline structurée : `VOICE · MUSIC · AMBIENCE · SFX · EVENTS`. Les SFX sont
liés au **graphe causal** et au **Motion Program**, pas seulement à une
description textuelle. Sous-titres : TTS → phonèmes → mots horodatés →
timeline → karaoké, en **données structurées**. ✅ Largement acquis.

### 4.27 Edit Timeline
`EditTimeline` (pistes vidéo, voix, musique, SFX, sous-titres, graphiques,
overlays, transitions) → `FFmpegCompiler`. **FFmpeg est un backend**, jamais
une commande construite à la volée par le métier.

### 4.28 Final QA
`TECHNICAL · TEMPORAL · VISUAL · MOTION · SEMANTIC · CONTINUITY · AUDIO ·
SUBTITLE · NARRATIVE`. **Jamais de score forcé** quand le système ne sait pas
mesurer : `UNKNOWN` plutôt qu'une fausse certitude.

### 4.29 Mémoire, provenance, observabilité
Après chaque plan validé : `ValidatedShot → WorldState → VisualMemory →
SemanticMemory → ExperienceMemory`.

Chaque artefact sait : qui l'a créé, quel modèle, quelle projection de prompt,
quel `RenderSpec`, quelle stratégie, quelles sources, quelle version de
compilateur, combien il a coûté.

```
final.mp4 → shot_03 → RenderSpec@1.2 → strategy=2.5D
          → depth_backend=vX → image_backend=vY → compiler_version=0.8.0
```

Tableau de bord minimal : coût total, durée totale, plans réussis, plans
échoués, taux de réparation, nombre moyen de relances, taux d'échec par
fournisseur, métriques de qualité.

### 4.30 Human review
Le système doit savoir dire `UNKNOWN` et demander un avis quand : le claim est
ambigu, le diagnostic incertain, deux réparations équivalentes, la continuité
subjective, ou le plan narrativement critique et techniquement douteux.
**Ce n'est pas un échec d'architecture, c'est un mécanisme de sécurité.** ✅ Acquis.

---

## 5. Routage empirique — dans cet ordre, pas l'inverse

1. routage **par règles** (aujourd'hui) ;
2. **collecte** correcte des résultats dans `ExperienceMemory` ;
3. quand la donnée existe : performance par stratégie, par fournisseur, coût,
   probabilité d'échec → routeur empirique.

**Aucun modèle de ML de routage avant d'avoir les données.** La priorité est
donc la *collecte*, pas le routeur.

---

## 6. Stack

**Conservée** (justifiée par l'audit, aucune raison d'en changer) :
Python 3.11+ · Pydantic v2 · Typer · httpx · PyYAML · Jinja2 · FastAPI ·
numpy · Pillow · FFmpeg · SQLite · Docker · GitHub Actions · pytest · ruff.

**Ajouts justifiés, un par un** :

| Ajout | Pourquoi | Quand |
|---|---|---|
| `pydantic` pour **tous** les contrats | déjà là ; sert de système de types + validation + JSON Schema + doc | Phase 2 |
| ordonnanceur de DAG **maison** (~200 l., `asyncio`) | 20 à 40 nœuds par job, sur une machine, avec `etapes` comme journal de reprise déjà en place. Temporal/Prefect/Airflow apporteraient un serveur, une base et un modèle de déploiement pour un gain nul ici | Phase 9 |
| `pytest-cov` | mesurer, pas deviner | Phase 1 |

**Non retenus, et pourquoi** : PostgreSQL (mono-utilisateur, mono-processus —
SQLite en WAL suffit et se sauvegarde par copie de fichier ; à reconsidérer le
jour où plusieurs workers écrivent en concurrence) · S3 (le stockage local +
artefacts adressés par sha256 remplit le rôle ; l'interface `Artefact` permet
de basculer plus tard) · Redis (aucune file inter-processus) · TypeScript
(aucun front à écrire ; `pdz web` est une page locale) · Temporal / Prefect /
Airflow (voir ci-dessus) · un framework d'agents (voir §7).

---

## 7. Ce que l'architecture n'est pas

Interdictions, reprises de la mission et **déjà respectées** par le dépôt :

- ✗ toute la logique dans un agent LLM — 14 des 19 modules de `production/`
  n'appellent aucun modèle ;
- ✗ n8n — le dépôt l'a explicitement écarté (`docs/archive/plan-n8n-obsolete.md`) ;
- ✗ fournisseur en dur — résolution par alias ;
- ✗ prompt sans contrat — à finir de tenir (c'est le sens de `contracts/`) ;
- ✗ un modèle vidéo pour chaque plan — `animation.noter()` choisit ;
- ✗ régénérer tout le plan à chaque erreur — à construire (`repair/`) ;
- ✗ un score esthétique unique — `qa_image` rend PASS/FAIL/UNCERTAIN ;
- ✗ croire une capacité annoncée — à formaliser (`capabilities/`) ;
- ✗ stocker seulement du texte — artefacts adressés par contenu ;
- ✗ envoyer tout l'historique à chaque appel — à formaliser (`MemoryPack`) ;
- ✗ entraîner un routeur ML sans données — la donnée n'est même pas collectée ;
- ✗ un simulateur physique universel pour le MVP.

**Et surtout** : les agents ne sont pas l'architecture. L'architecture, ce sont
des contrats, des machines à états, des compilateurs, des graphes, des
validateurs, des workers, des backends et des observateurs. Un agent est
appelé quand le problème est réellement sémantique — planification narrative,
interprétation d'un claim, planification de la preuve visuelle, alternatives
créatives, aide au diagnostic. Jamais pour un calcul de durée, une arithmétique
de timeline, une validation de schéma, un calcul de coût, une vérification de
capacité, un hachage, une résolution de dépendances, un ordonnancement de DAG
ou une validation de fichier.

---

## 8. Critère de réussite

```bash
pdz creer --sujet "Comment fonctionne un moteur électrique ?" \
          --duree 45 --langue fr
```

produit :

```
projet/
├── recherche/     factgraph.json, sources.json
├── script/        script.json, director.json
├── voix/          voix.mp3, timeline.json
├── plans/         shot_graph.json, shot_*.json
├── rendus/        shot_*.mp4 + render_spec_*.json
├── observations/  observation_*.json
├── reparations/   diagnostic_*.json, repair_*.json
├── timeline/      edit_timeline.json
├── final/         final.mp4, production.json, cout.json, qa.json
└── memoire/       experience.json, world.json
```

Et pour **chaque plan**, le système sait répondre à cinq questions :

| # | Question | Contrat qui répond |
|---|---|---|
| 1 | Pourquoi ce plan existe-t-il ? | `ShotSpec.purpose` + `claim` |
| 2 | Que doit-il montrer ? | `PerceptualContract` |
| 3 | Comment doit-il évoluer ? | `SceneState` + `event` + `MotionProgram` |
| 4 | Comment le fabrique-t-on ? | `RenderStrategyGraph` → `ExecutionPlan` |
| 5 | Comment sait-on qu'il a réussi ? | `expected` vs `observed` |

**Un plan qui ne peut pas répondre aux cinq n'est pas suffisamment spécifié.**
