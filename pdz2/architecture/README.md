# PDZ 2 — architecture

PDZ 2 n'est pas un agent qui fabrique des vidéos. C'est **un compilateur
audiovisuel** : une idée entre, un MP4 sort, et chaque étape intermédiaire
est un artefact typé, versionné, relisible et rejouable.

```
LLMs DECIDE.            Les modèles produisent des décisions, une seule fois.
CONTRACTS CONSTRAIN.    Les décisions atterrissent dans des contrats typés.
VALIDATORS REJECT.      Ce qui est contradictoire est refusé avant de coûter.
ROUTERS CHOOSE.         La stratégie de rendu est choisie, pas subie.
RENDERERS EXECUTE.      L'exécution ne connaît pas la raison narrative.
OBSERVERS MEASURE.      Ce qui sort est mesuré, pas jugé à l'œil.
DIAGNOSTICS EXPLAIN.    Un échec cite les mesures qui le prouvent.
REPAIR COMPILERS ADAPT. La réparation est bornée et déterministe.
FALLBACKS GUARANTEE.    Un repli local garantit toujours la livraison.
HUMANS JUDGE.           Ce qu'aucune mesure ne tranche revient à l'humain.
```

## La règle absolue : trois couches, jamais mélangées

```
        NARRATIVE INTENT                RENDER SPECIFICATION            EXECUTION
        ────────────────                ────────────────────            ─────────
        TopicRequest                                                    RenderArtifact
        ResearchState                   RenderSpecRequested              ObservationReport
        Claim / Evidence      ────►     ImageSpec              ────►     MasterArtifact
        FactGraph                       MotionProgram
        DirectorState                   CameraProgram                   ▲
        AnchorSpec                      ShotSpec                        │
        ShotIntent                      VisualBible                     │
        ScriptState                            │                        │
                                               ▼                        │
                                       StaticValidator                  │
                                               │                        │
                                               ▼                        │
                                       RenderSpecExecutable ────────────┘
                                       ExecutionPlan
```

* Le **Director Core** ne sait pas quel fournisseur vidéo existe. Aucun champ
  `provider`, `model`, `fps`, `strategy` ou `cost` n'entre dans un contrat de
  la couche narrative — un test d'architecture le vérifie
  (`pdz2/tests/test_layering.py::TestLayerPurity`).
* Le **renderer** ne sait pas *pourquoi* un plan existe. `RenderSpecExecutable`
  ne porte ni thèse, ni fonction narrative, ni identifiant d'affirmation.
* La frontière entre les deux est l'**ABI de rendu** :
  `RenderSpecRequested` (ce qui est demandé) → `StaticValidator` →
  `RenderSpecExecutable` (ce qui sera vraiment fait, avec ses dégradations).

## Invariants tenus par la structure, pas par la discipline

| Règle du cahier des charges | Où elle est rendue impossible à violer |
| --- | --- |
| Jamais un fait certain sans preuve | `Claim` : sans `evidence_ids`, la confiance est forcée à 0 et le statut reste `unverified` |
| Une affirmation porteuse a une preuve visuelle | `Claim.load_bearing` exige `causal_mechanism`, `evidence_required`, `visual_proof` |
| Ne pas illustrer une phrase abstraite | `VisualEvidencePlan` refuse un `visual_proof` de moins de quatre mots |
| VOICE FIRST | `VoiceTimeline` refuse une source de timing estimée ; `TIMELINE` dépend de `VOICE` dans le graphe d'étapes |
| Continuité représentée dans les données | `AnchorSpec` exige au moins un attribut d'identité `fixed` |
| Pas de dégradation silencieuse | `RenderSpecExecutable` refuse tout écart avec l'écho de la demande qui n'est pas déclaré en `Degradation` |
| Caméra verrouillée ≠ caméra qui bouge | `CameraProgram` refuse `locked=true` avec un mouvement, une vitesse ou une trajectoire |
| Pas de dépense avant validation | `ASSETS` et `RENDER` sont barrées tant que `STATIC_VALIDATION` n'est pas `DONE` |
| Mouvement représenté mathématiquement | `Trajectory` exige points de contrôle, amplitude, axe ou fréquence selon la primitive |
| Les replis garantissent la livraison | `RepairPlan.guaranteed_fallback` n'accepte que des actions sans fournisseur |
| Pas de dictionnaire arbitraire | Test d'architecture : aucun contrat n'expose de champ `dict[...]` |
| Provider-agnostic | Test d'architecture : aucune marque de fournisseur dans `contracts/`, `state/`, `storage/`, `schemas/` |

## Carte du paquet

```
pdz2/
├── architecture/   décisions et frontières (ce dossier)
├── contracts/      contrats Pydantic versionnés — le seul langage commun
├── schemas/        schémas JSON générés et versionnés dans le dépôt
├── state/          graphe d'étapes et machine à états reprenable
├── storage/        dossier d'épisode : écriture atomique, relecture typée
├── cli/            inspection des contrats, des schémas et d'un épisode
├── engines/        research + direction (phase 1) ; image, 2.5D à venir
├── providers/      adaptateurs de fournisseurs        — non implémenté
├── renderers/      exécution des stratégies de rendu   — non implémenté
├── qa/             observation déterministe            — non implémenté
├── repair/         diagnostic et réparation            — non implémenté
├── audio/          voix, sound design, mastering       — non implémenté
├── editing/        montage                             — non implémenté
└── tests/          tests de contrat, d'état et d'architecture
```

Les paquets marqués « non implémenté » sont vides *par décision*. Le cahier des
charges interdit les faux adaptateurs et les capacités simulées : tant que le
code réel n'existe pas, rien ne doit laisser croire le contraire. Un test le
vérifie (`TestPhaseHonesty`).

## Rapport avec l'ancien PDZ

L'ancien système vit toujours dans `pdz/` et n'est **ni migré, ni réparé, ni
importé**. PDZ 2 est un paquet indépendant : aucun module de `pdz2/` n'importe
quoi que ce soit de `pdz/`. Le jour où l'ancien système sera retiré, `pdz2`
pourra prendre le nom `pdz` — c'est un renommage de paquet, pas une fusion.

## État réel du chantier

Voir `pdz2 phases`. Aujourd'hui : **phases 0 et 1**.

* Phase 0 — contrats, versionnage, machine à états, persistance, schémas.
  Détail : [`PHASE-0.md`](../PHASE-0.md).
* Phase 1 — recherche factuelle, Fact Graph, Director Core. Corpus local
  seulement (le réseau de recherche est bloqué ici), brief rédigé à la main
  (aucun raisonneur branché). Détail : [`PHASE-1.md`](../PHASE-1.md).
