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
| VOICE FIRST | `VoiceTimeline` refuse un timing estimé ; `TIMELINE` dépend de `VOICE` ; `pdz2/audio/` ne peut pas lire `estimated_duration_s` |
| La durée officielle sort d'un fichier | `MeasuredLine` n'a pas de champ de durée, seulement une mesure de trames |
| Un audio muet n'a pas de durée officielle | plancher d'énergie : `AudioSilent` refuse un WAV lisible et vide |
| Les plans pavent exactement l'audio mesuré | `TemporalPlan` refuse tout trou ou chevauchement au-delà de 2 ms |
| Un plan démontre une affirmation écrite | `ShotSpec.visual_subject` recopie la preuve rédigée ; sinon refus |
| Aucune décision narrative dans le découpage | six tests : tout sujet, toute preuve, toute fonction vient de l'amont |
| La bible ignore les fournisseurs | test d'architecture sur la bible compilée et sur les préréglages |
| Continuité représentée dans les données | `AnchorSpec` exige au moins un attribut d'identité `fixed` |
| Pas de dégradation silencieuse | `RenderSpecExecutable` refuse tout écart avec l'écho de la demande qui n'est pas déclaré en `Degradation` |
| Caméra verrouillée ≠ caméra qui bouge | `CameraProgram` refuse `locked=true` avec un mouvement, une vitesse ou une trajectoire |
| Pas de dépense avant validation | `ASSETS` et `RENDER` sont barrées tant que `STATIC_VALIDATION` n'est pas `DONE` |
| Mouvement représenté mathématiquement | `Trajectory` exige points de contrôle, amplitude, axe ou fréquence selon la primitive |
| Les replis garantissent la livraison | `RepairPlan.guaranteed_fallback` n'accepte que des actions sans fournisseur |
| Pas de dictionnaire arbitraire | Test d'architecture : aucun contrat n'expose de champ `dict[...]` |
| Provider-agnostic | Test d'architecture : aucune marque de fournisseur dans `contracts/`, `state/`, `storage/`, `schemas/` |
| Une capacité annoncée n'est pas une capacité | `CapacityValue` refuse `MEASURED` sans date ni méthode, et `UNKNOWN` avec une valeur |
| Une mesure vieillit | `is_stale()` à trente jours ; `trustworthy()` exige mesurée **et** récente |
| Pas de dépense au coût inconnu | `CostGovernor` refuse `UNMEASURED_COST` même budget intact ; `estimate()` rend `None` plutôt qu'un chiffre annoncé |
| Une dépense se refuse avant, pas après | `CostLedger` refuse un registre dont le total dépasse son plafond |
| Un épisode s'explique après coup | `ProductionJournal` est **reconstruit** depuis les contrats du disque ; retirer un contrat retire ses entrées |

## Carte du paquet

```
pdz2/
├── architecture/   décisions et frontières (ce dossier)
├── contracts/      contrats Pydantic versionnés — le seul langage commun
├── schemas/        schémas JSON générés et versionnés dans le dépôt
├── state/          graphe d'étapes et machine à états reprenable
├── storage/        dossier d'épisode : écriture atomique, relecture typée
├── cli/            inspection des contrats, des schémas et d'un épisode
├── engines/        research, direction, script, temporal, visual, shots,
│                   motion, imagery, renderspec, validation, routing,
│                   governance, journal
├── audio/          synthèse réelle, mesure du WAV, VoiceTimeline, mastering
├── providers/      **ports** de fournisseurs — aucun adaptateur implémenté
├── renderers/      stratégies déterministes locales, ffmpeg
├── qa/             observation déterministe et QA finale
├── repair/         diagnostic adossé aux mesures, réparation bornée
├── editing/        montage, sous-titres, assemblage
└── tests/          tests de contrat, d'état et d'architecture
```

`providers/` ne contient **que des ports**, sans adaptateur : le cahier des
charges interdit les faux adaptateurs et les capacités simulées, et aucun
service de génération vidéo n'est joignable ici. Un test le verrouille
(`TestPhaseHonesty::test_no_adapter_pretends_to_exist`), et il échouera le jour
où un adaptateur réel arrivera — c'est le signal qu'il faudra retirer les
mentions « aucun adaptateur vidéo implémenté » de `pdz2 phases`.

## Rapport avec l'ancien PDZ

L'ancien système vit toujours dans `pdz/` et n'est **ni migré, ni réparé, ni
importé**. PDZ 2 est un paquet indépendant : aucun module de `pdz2/` n'importe
quoi que ce soit de `pdz/`. Le jour où l'ancien système sera retiré, `pdz2`
pourra prendre le nom `pdz` — c'est un renommage de paquet, pas une fusion.

## État réel du chantier

Voir `pdz2 phases`. **Les douze phases sont implémentées.** La chaîne produit
un MP4 réel, mesuré, à partir d'un corpus local et d'un brief humain.

| phase | contenu | détail |
| --- | --- | --- |
| 0 | contrats, versionnage, machine à états, persistance, schémas | [`PHASE-0.md`](../PHASE-0.md) |
| 1 | recherche factuelle, Fact Graph, Director Core | [`PHASE-1.md`](../PHASE-1.md) |
| 2 | script compilé, synthèse vocale réelle, timeline mesurée | [`PHASE-2.md`](../PHASE-2.md) |
| 3 | Temporal Director, Shot Graph, Visual Bible | [`PHASE-3.md`](../PHASE-3.md) |
| 4 | RenderSpec et validateur statique (douze règles) | [`PHASE-4.md`](../PHASE-4.md) |
| 5 | moteur d'images schématiques déterministe | [`PHASE-5.md`](../PHASE-5.md) |
| 6 | MotionProgram, port vidéo, routeur de stratégie | [`PHASE-6.md`](../PHASE-6.md) |
| 7 | 2.5D et procédural : vraies vidéos H.264 | [`PHASE-7.md`](../PHASE-7.md) |
| 8 | observateur déterministe sur les pixels réels | [`PHASE-8.md`](../PHASE-8.md) |
| 9 | diagnostic et repair compiler borné | [`PHASE-9.md`](../PHASE-9.md) |
| 10 | montage, mastering, sous-titres, QA finale | [`PHASE-10.md`](../PHASE-10.md) |
| 11 | matrice de capacités et gouverneur de coût | [`PHASE-11.md`](../PHASE-11.md) |
| 12 | journal de production reconstruit | [`PHASE-12.md`](../PHASE-12.md) |

### Ce qui manque, et qui est déclaré plutôt que simulé

* **Aucun raisonneur (LLM) n'est branché.** Le port existe ; aucun identifiant
  n'est disponible ici. Le brief de réalisation est donc rédigé par un humain,
  et `pdz2 create` s'arrête devant lui plutôt que d'inventer une thèse.
* **Aucun adaptateur de génération vidéo n'est joignable.** Le routeur
  enregistre une `Degradation` nommée pour chaque plan qui bascule sur une
  stratégie déterministe locale.
* **Aucune recherche en ligne.** La politique réseau de cet environnement
  refuse les hôtes de recherche ; le corpus est local et sourcé.

`pdz2 capabilities` dit à tout moment ce qui est réellement joignable, mesuré
et daté.

### Dépendances système

| binaire | rôle | absent ? |
| --- | --- | --- |
| `espeak-ng` | synthèse vocale (phase 2) | l'adaptateur se déclare `UNAVAILABLE` avec la raison, les tests concernés sont ignorés |
| `ffmpeg` / `ffprobe` | encodage, mesure, mastering (phases 7 à 10) | idem |

Rien ne fait semblant de fonctionner : une dépendance absente est déclarée,
jamais contournée par une simulation.
