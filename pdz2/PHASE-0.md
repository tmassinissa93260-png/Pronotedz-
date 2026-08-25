# Phase 0 — ce qui est réellement implémenté et vérifié

**Périmètre du cahier des charges** : contrats + versionnage + machine à états.
Rien d'autre n'a été implémenté, et rien n'a été simulé.

## Livré

### Contrats (`pdz2/contracts/`)

**30 contrats** enregistrés, incluant les 21 du minimum exigé :

`topic_request` · `research_state` · `claim` · `evidence` · `source_reference` ·
`fact_graph` · `director_state` · `anchor_spec` · `shot_intent` · `script_state` ·
`script_line` · `voice_timeline` · `visual_bible` · `image_spec` ·
`camera_program` · `motion_program` · `shot_spec` · `shot_graph` ·
`render_spec_requested` · `render_spec_executable` · `execution_plan` ·
`render_artifact` · `observation_report` · `failure_diagnosis` · `repair_plan` ·
`edit_timeline` · `subtitle_track` · `master_artifact` · `state_transition` ·
`episode_snapshot`

Chacun porte `id`, `version`, `created_at`, `parent_id`, `status` — vérifié par
test sur l'ensemble du registre. Aucun contrat n'expose de champ `dict[...]` :
les objets imbriqués sont des `Element` typés.

### Versionnage (`pdz2/contracts/versioning.py`)

SemVer, registre unique, règle de lecture (même majeure, mineure ≤ courante),
migrations enregistrées et chaînées. Une version illisible sans migration est
**refusée**, pas devinée. Identifiants déterministes sous `deterministic_ids(seed)`.

### Machine à états (`pdz2/state/`)

DAG de 21 étapes, statuts `pending/running/done/failed/skipped`, journal complet
des transitions, rembobinage transitif pour la boucle de réparation, plafonds de
cycles et de budget, sérialisation et reprise.

### Persistance (`pdz2/storage/`) et schémas (`pdz2/schemas/`)

Dossier d'épisode conforme au §46, écriture atomique, relecture typée par le
registre. 30 schémas JSON générés et versionnés dans le dépôt, avec un test qui
échoue s'ils divergent du code.

### CLI (`pdz2/cli/`)

`pdz2 contracts list|schema` · `pdz2 schemas export|check` ·
`pdz2 state graph|show` · `pdz2 phases`. `pdz2 create` **refuse** de produire.

## Invariants vérifiés par test

| Invariant | Test |
| --- | --- |
| Jamais un fait certain sans preuve | `test_research_contracts.py::TestClaimNeverBecomesCertain` |
| Preuve visuelle concrète, pas d'illustration abstraite | `TestVisualEvidence`, `TestVisualEvidencePlan` |
| Fact Graph acyclique et refermé sur lui-même | `TestFactGraph`, `TestResearchState` |
| Identité d'ancre épinglée dans les données | `TestAnchorSpec` |
| VOICE FIRST | `test_script_contracts.py::TestVoiceFirst`, `test_state_machine.py::test_voice_first_is_structural` |
| Caméra verrouillée ≠ caméra qui bouge | `TestCameraContradictions` |
| Mouvement paramétré mathématiquement | `TestMotionGrammar` |
| Aucune dégradation silencieuse | `test_render_abi.py::TestNoSilentDegradation` |
| Cœur provider-agnostic | `test_layering.py::test_no_provider_brand_in_the_core` |
| Trois couches non mélangées | `test_layering.py::TestLayerPurity` |
| Pas de dépense avant validation | `test_state_machine.py::TestCostGate` |
| Boucle de réparation bornée | `TestRepairLoop` |
| Livraison garantie par un repli local | `TestRepairPlan` |
| Reprise sans rejouer ce qui est fait | `TestResume` |
| Pas de faux moteur dans les phases à venir | `TestPhaseHonesty` |

## Résultat d'exécution

```
$ pytest pdz2/tests -q
270 passed
$ ruff check pdz2/
All checks passed!
```

## Non implémenté — et pas simulé

`providers/` `renderers/` `engines/` `qa/` `repair/` `audio/` `editing/` sont
vides, avec une notice explicite. Aucun faux adaptateur, aucune capacité
annoncée sans mesure, aucun test en trompe-l'œil. Ces paquets se remplissent
aux phases 1 à 12.

## Prochaine étape

Phase 1 — Research + Fact Graph + DirectorState, avec des sources réelles.
