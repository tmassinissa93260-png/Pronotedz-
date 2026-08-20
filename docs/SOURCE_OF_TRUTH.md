# Matrice des sources de vérité

> Demandée en § 4 du prompt de migration. Pour chaque domaine : **qui fait
> autorité**, avant et après.
>
> La colonne qui compte est « source de vérité ». Un domaine qui en a deux
> n'en a aucune — c'était le cas de la reprise, et c'est ce qui rendait le
> dépôt imprévisible sur son chemin le plus important.

Légende : ✅ comblé · 🟨 partiel · 🔒 verrouillé par la donnée

---

## Les domaines

| Domaine | Implémentation | Source de vérité **avant** | Source de vérité **après** | Cible | Écart |
|---|---|---|---|---|---|
| **Chronologie audio** | `production/voix.py` · `ia/elevenlabs.py` | timings ElevenLabs mot à mot, recalés sur la piste | *inchangée* — c'était déjà juste | `AudioTimeline` | ✅ contrat ajouté, mécanisme intact |
| **Reprise** | `moteur/journal.py` | **DEUX** : `moteur/pipeline.py` **et** `production/episode.py` | `moteur/journal.py`, seul | état du compilateur | ✅ verrouillé par test |
| **Cache** | `moteur/journal.py` | `Moteur` seul — le chemin de production n'y accédait pas | `moteur/journal.py`, partagé | cache d'artefacts | ✅ + revérification des fichiers |
| **Découpage** | `production/storyboard.py` | durées de voix **mesurées** | *inchangée* | `ShotGraph` | ✅ contrat + arêtes |
| **Prompts** | `prompts/catalogue/<id>@<semver>` | fichiers YAML versionnés | *inchangée* | idem | ✅ patron réutilisé pour les contrats |
| **Mouvement** | `production/motion_program.py` | champs `mouvement_*` de `ShotPromptWriter` | *inchangée* | `MotionProgram` | ✅ caméra extraite |
| **Caméra** | `contracts/camera.py` | **un champ** du `MotionProgram` | `CameraProgram`, séparé | `CameraProgram` | ✅ + `est_garantie` |
| **Perception** | `production/contrat_visuel.py` | les « 8 questions », sans ordre d'attention | + `PerceptualContract` | idem | ✅ attention ordonnée, confusions |
| **Capacités** | `modeles.yaml` · `capabilities/` | `fait: [...]`, sans statut ; mesures **en commentaires** | `capacites:` avec `ANNONCE`/`MESURE`/`INCONNU` | `CapabilityGraph` | ✅ 25/32 déclarées non mesurées |
| **Fournisseurs** | `backends/` | 4 modules métier importaient fal/elevenlabs/audd | `backends/`, registre public | interfaces backend | ✅ vérifié par AST |
| **Stratégie de rendu** | `strategies/` | cascade `if/else` dans `animation.py`, sans nom | `RenderStrategyGraph` | idem | 🟨 le repli passe par elle, pas la décision de dépenser |
| **Observation** | `observation/` | 5 sondes séparées, verdicts journalisés puis oubliés | `ObservationReport` unifié | idem | ✅ + axes non mesurés |
| **Diagnostic** | `diagnostics/` | étiquettes (`rejete_mouvement`) — un symptôme | `FailureDiagnosis` — une **cause** | taxonomie 18 modes | ✅ branché sur l'animation |
| **Réparation** | `repair/` | relance, puis repli local | `RepairPlan`, arbitré par cause | arbre de réparation | 🟨 seul `STRATEGY_FIX` est exécutable |
| **État du monde** | `world/` | décor porté par `continuite.py`, rien d'autre | `WorldState` + attendu/observé | idem | ✅ delta mesurable |
| **Expérience** | `memory/` | **aucune** — rien n'était collecté | table `experiences`, une ligne/tentative | `ExperienceMemory` | ✅ alimentée en production |
| **Exécution** | `execution/` | séquence linéaire dans `episode.py` | `ExecutionPlan` (DAG) + ordonnanceur | DAG | 🟨 écrit et testé, pas appelé par `episode.py` |
| **Recherche** | `research/` | **aucune** — `perplexity_api_key` lue nulle part | `RechercheBackend` + `SansRecherche` | `FactGraph` | 🟨 adaptateur réseau non écrit |
| **Mise en scène** | `director/` | `BriefWriter` + `ScriptWriter`, sans état commun | `DirectorState`, deux profils convergents | idem | ✅ |
| **Montage** | `video/montage.py` | objet `Montage` → FFmpeg | *inchangée* | `EditTimeline` | 🟨 contrat défini, `Montage` pas encore migré |
| **Routage empirique** | — | — | — | routeur empirique | 🔒 attend que `experiences` se remplisse |

---

## Ce que la matrice rend visible

**Un domaine avait deux sources de vérité : la reprise.** `moteur/pipeline.py`
et `production/episode.py` écrivaient tous deux dans `etapes`, sans se
connaître. C'était le défaut structurel principal du dépôt — et le plus
dangereux, parce que le chemin qui produit réellement les vidéos était le
second, celui qui n'avait pas accès au cache.

**Un domaine n'en avait aucune : l'expérience.** Rien n'était collecté, donc
aucun routage empirique n'était possible — pas faute d'algorithme, faute de
donnée.

**Cinq domaines gardent leur source de vérité inchangée**, et c'est
délibéré : la chronologie audio, le découpage, les prompts versionnés, le
mouvement et le montage étaient déjà justes. Les contrats les *nomment* sans
les remplacer.

## Les quatre écarts qui restent

| Écart | Pourquoi il tient encore |
|---|---|
| Stratégie : la décision de dépenser | change ce que `pdz episode` fabrique |
| Réparation exécutée | demande une boucle de régénération dans `animation.py` |
| DAG en production | `episode.py` reste linéaire |
| Recherche réseau | l'adaptateur n'existe pas ; `SansRecherche` dit honnêtement qu'il ne cherche rien |

Les trois premiers modifient le chemin qui dépense de l'argent. La règle § 39
(`ANCIEN → ADAPTATEUR → NOUVEAU`, jamais un déplacement et un changement de
comportement dans le même commit) les a volontairement laissés en dehors de
la migration : les franchir est une décision de produit, pas de technique.
