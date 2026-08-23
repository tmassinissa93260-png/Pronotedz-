# Phase 4 — RenderSpec + StaticValidator

## CURRENT STATE

```
… → shots → motion → specs → validate
```

Sur l'épisode de référence : 6 programmes de mouvement, 6 spécifications
d'image en 1080×1920, 14 calques, 6 demandes de rendu à 30 i/s — **acceptées**
par le validateur, avec six constats mineurs qui disent la vérité sur cet
environnement.

## ARCHITECTURE

```
ShotGraph + TemporalPlan + CameraProgram → MotionCompiler    → MotionProgram
ShotGraph + VisualBible + AnchorSpec     → ImageSpecCompiler → ImageSpec
tout ce qui précède                      → RenderSpecCompiler → RenderSpecRequested
                                         → StaticValidator   → ValidationReport
```

`MOTION` a été **tirée en avant depuis la phase 6** : le graphe d'étapes la
place avant `RENDER_SPEC`, et `RenderSpecRequested.motion_program_id` est
obligatoire. Sans elle, aucune demande de rendu ne peut exister. La phase 6
gardera le port fournisseur et le routeur de stratégie.

## NEW CONTRACTS

| Contrat | Version | Rôle |
| --- | --- | --- |
| `validation_report` | 1.0.0 | verdict du validateur, constat par constat |
| `ValidationIssue` (élément) | — | règle, gravité, sujet, détail, remède |
| `ValidationRule` (énuméré) | — | les douze règles du §13 |

`STATIC_VALIDATION` produit désormais `validation_report` et **rien d'autre** ;
`ROUTING` produira `render_spec_executable` et `execution_plan`. Le validateur
refuse, le routeur choisit — deux étapes, deux responsabilités.

## LE VALIDATEUR

Douze règles nommées, chacune testée :

| Règle | Ce qu'elle refuse |
| --- | --- |
| `schema`, `contract_version` | un contrat illisible par le lecteur courant |
| `required_field` | un plan sans demande, une demande orpheline, un plan sans image |
| `logical_contradiction` | deux demandes pour un plan, une durée qui ne colle pas au plan, un plan immobile d'intensité non nulle |
| `camera_constraint` | **caméra verrouillée + mouvement demandé** (l'exemple du §13), et tout écart entre la demande et le programme caméra |
| `duration_feasibility` | au-delà de 30 s d'un tenant, en deçà de 0,4 s |
| `resolution_format` | dimensions impaires, cadence sous 12 i/s |
| `provider_capability` | une stratégie demandée qu'aucun exécutant ne propose |
| `fallback_availability` | l'absence de tout repli déterministe |
| `budget` | une somme de plafonds au-dessus du budget d'épisode |
| `continuity` | une ancre exigée absente des images, un verrou d'identité perdu |
| `evidence_link` | un plan qui démontre sans dire ce qu'il faut voir |

**Tout blocage doit dire comment le lever** — le contrat `ValidationIssue` le
refuse sinon. Un rejet sans remède est un caprice ; un rejet nommé se corrige.

## TEST RESULTS

```
$ pytest pdz2/tests -q   →  606 passed
$ ruff check pdz2/       →  All checks passed!
```

35 tests pour la seule phase 4.

## LIMITATIONS

* **Aucun fournisseur vidéo n'est joignable ici.** Le validateur le dit en
  clair, plan par plan, en `MINOR` : le rendu passera par une stratégie
  déterministe et la dégradation sera enregistrée. Ce n'est pas un échec,
  c'est la garantie du §46 — le système fonctionne sans génération vidéo IA.
* Le champ `intent` d'une `ImageSpec` est un assemblage de chaînes déjà
  décidées. Sa traduction en prompt appartient à l'adaptateur, pas au cœur.
* `MAX_SHOT_DURATION_S = 30` est une borne d'ingénierie, pas une capacité
  mesurée. La matrice de capacités (phase 11) la remplacera par du mesuré.

## NEXT STEP

Phase 5 — Image Engine : exécuter réellement les `ImageSpec`.
