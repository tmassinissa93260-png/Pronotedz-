# Analyse d'écart — de l'existant vers le compilateur

> Lecture : [CURRENT_ARCHITECTURE.md](./CURRENT_ARCHITECTURE.md) décrit
> l'existant, [TARGET_ARCHITECTURE.md](./TARGET_ARCHITECTURE.md) la cible.
> Ce document mesure la distance entre les deux, et rien d'autre.

> ## ⚠️ Document d'ÉPOQUE — conservé tel quel
>
> **Cet écart a été comblé.** Les tableaux ci-dessous décrivent le dépôt
> *avant* la migration, et ils sont laissés intacts : effacer la mesure de
> départ rendrait impossible de juger ce qui a été fait.
>
> Où en est le dépôt aujourd'hui : voir
> [MIGRATION_PLAN.md](./MIGRATION_PLAN.md) — **18 phases sur 19 faites**, la
> dernière verrouillée par la donnée et non par le code.
>
> | Compte | Avant | Après |
> |---|---|---|
> | ✅ acquis | 6 | **28** |
> | 🟨 partiel | 14 | 1 *(routage empirique)* |
> | ⛔ absent | 9 | 0 |
> | Tests | 807 *(dont 5 rouges)* | **1230, 0 échec** |
> | CI | aucune | ruff + pytest + couverture |
>
> Deux constats de ce document se sont révélés **faux à la mesure**, et le
> test d'architecture les a corrigés dès la PHASE 1 : la violation
> métier→fournisseur était **quadruple**, pas unique ; et un module lisait
> `os.environ` hors de `config.py`, ce que la docstring de ce dernier
> promettait impossible.

Légende : ✅ acquis · 🟨 partiel · ⛔ absent

---

## 1. La contradiction à trancher avant de coder

> ⚠️ **STOP — décision requise.** Elle change la Phase 3, et rien d'autre.

**Problème.** La chaîne cible est écrite pour un compilateur **explicatif** :
`FactGraph`, `claims`, `evidence`, `causal_chain`, et un exemple qui est
« Comment fonctionne un moteur électrique ? ». Le système existant est bâti pour
de la **fiction sérielle** : `Univers`, `Personnage`, `Decor`, dialogue,
émotions, relances, constance des personnages d'un épisode à l'autre. Les 807
tests, les 4 univers livrés et l'intégralité de `production/` reposent sur ce
second modèle.

**Impact.** `Claim`, `Evidence` et `FactGraph` n'ont **aucun sens** pour
« Strawberina trahit Bananito » : il n'y a pas de source à citer, pas de
confiance à mesurer, pas de fait à ne pas inventer — c'est de la fiction
assumée. Poser le FactGraph en passage obligé de toute production casserait le
format qui marche aujourd'hui, pour un format qui n'existe pas encore.
Symétriquement, sans FactGraph, le format explicatif n'a aucun socle de
véracité, et le système inventera des mécanismes physiques avec l'aplomb d'un
modèle de langage.

**Options.**

| | Option | Conséquence |
|---|---|---|
| A | **Deux profils de production** — `fiction` (Univers/Personnages, chemin actuel) et `explicatif` (FactGraph/Evidence, chemin neuf), partageant tout à partir du Script Compiler | Le chemin qui marche continue de marcher. Le Director Core devient une interface à deux implémentations. Coût : une abstraction de plus au bon endroit. |
| B | **Tout passer par le FactGraph**, la fiction produisant des claims de statut `FICTION` non sourcés | Une seule chaîne, mais un `FactGraph` vide de sens sur 100 % des productions actuelles, et 807 tests à réécrire pour une valeur nulle. |
| C | **Abandonner la fiction**, ne garder que l'explicatif | Jette 4 univers, `images.py` (stabilité des personnages), `appariement_voix.py`, `charte.py` — le travail le plus dur du dépôt. |

**Recommandation : A.** `FactGraph` et `EvidenceState` deviennent des contrats
**du profil explicatif**, produits par `research/` et consommés par
`director/`, et le profil `fiction` fournit à leur place un `NarrativeState`
issu de l'`Univers`. Les deux convergent sur le **même** `DirectorState` et le
même `ShotGraph` — c'est-à-dire que la divergence s'arrête avant le compilateur
proprement dit.

**Décision prise : option A** (PHASE 3, commit `6bcded7`).

`ResearchState` (explicatif) et `NarrativeState` (fiction) convergent sur le
même `DirectorState@1.0.0`. Le routage se fait sur le **type** de la source,
jamais sur un drapeau : un `ResearchState` ne peut pas être compilé en
fiction, et laisser un booléen décider ouvrirait cette possibilité pour rien.

Les paliers de compréhension **diffèrent** entre profils, et c'est le point :
on ne « comprend » pas une trahison. En fiction, l'acquisition n'est pas un
savoir mais une tension — les six paliers explicatifs y seraient un
contresens.

---

## 2. Écart couche par couche

| # | Couche cible | État | Ce qui existe déjà | Ce qui manque |
|---|---|---|---|---|
| 01 | **Kernel** | 🟨 | `moteur/pipeline.py` : jobs, étapes, reprise, cache par empreinte, budget, réessais à deux compteurs, validation humaine. `db.py` : 7 tables, artefacts par sha256 | ordonnanceur de DAG (`depend_de` inutilisé), événements, annulation, délais, provenance complète, **un seul** orchestrateur |
| 02 | **Contracts** | ⛔ | prompts versionnés `<id>@<semver>` — le modèle à répliquer. Pydantic sur `Univers`/`Modele` | paquet `contracts/`, enveloppe commune, migration, JSON Schema, tests de compatibilité ascendante. Les objets pivots sont des dataclasses nues, et voyagent en `dict` |
| 03 | **Research** | ⛔ | `perplexity_api_key` déclarée dans `config.py` — **lue nulle part** | tout : `ResearchBackend`, `FactGraph`, `Claim`, sources, `FACT/HEURISTIC/UNKNOWN/HUMAN_VERIFIED`, détection de conflits et d'obsolescence |
| 04 | **Director Core** | 🟨 | `BriefWriter` (beats, structure, escalade), `ScriptWriter`, `EmpreinteCreative` (arc émotionnel, rétention, hook) | `thesis`, `claims`, `viewer_knowledge_state` (T0→T5), `visual_evidence`, `shot_intentions`, `continuity_anchors` comme contrat |
| 05 | **World State** | ⛔ | `continuite.porter_le_decor()` (décor porté de réplique en réplique), `geometrie.py` (position qualitative), `Univers`/`Personnage` (statique) | `Entity/State/Relation/Position/Geometry/Identity/Material/Constraints`, et surtout `expected_state` / `observed_state` / `confidence` |
| 06 | **Causality** | ⛔ | — | tout : chaîne causale, décision « quelles conséquences montrer » |
| 07 | **Evidence** | 🟨 | `fidelite_visuelle.py` : le prompt d'image nomme-t-il ce que la réplique nomme (`elements_obligatoires`) — un proto-lien preuve↔plan, déjà vérifié | `CLAIM → EVIDENCE → VISUAL → SHOT` comme chaîne typée |
| 08 | **Script Compiler** | ✅ | `BriefWriter` → `ScriptWriter` → répliques (`texte, emotion, personnage, relance, decor`) | `claim` et `purpose` par ligne (dépend de §1) |
| 09 | **Audio / VoiceTimeline** | ✅ | `voix.py` : bande unique, bonne voix par personnage, **timings mot à mot recalés sur la piste complète**. `elevenlabs.py` : alignement caractère par caractère | pistes musique / ambiance / SFX ; SFX liés au graphe causal et au Motion Program |
| 10 | **Shot Graph** | 🟨 | `storyboard.decouper()` : répliques + durées **réelles** → plans ; `point_de_coupe()` sur pause mesurée ; `PlanScript` riche (cadrage, émotion, mouvement, géométrie, registre) | c'est une **liste**, pas un graphe : ni `state_before`/`event`/`state_after`, ni `claim`, ni `evidence`, ni `success_criteria` explicites |
| 11 | **Perception** | 🟨 | `MotionProgram.cible_perceptuelle` (`viewer_must_perceive_*`) — une vraie cible perceptuelle, déjà recoupée en aval. `ContratVisuel` (le plan en 8 questions). `decision_visuelle.verifier()` recoupe le contrat avec lui-même | `attention` ordonnée, `ne_doit_pas_etre_confondu_avec`, et l'extraction en contrat de premier ordre |
| 12 | **Motion DSL** | 🟨 | `MotionProgram` gelé : `action, camera, environnement, intensite, doit_preserver, peut_changer, interdit, registre` + `compiler_prompt()`. **Zéro appel IA** | trajectoires, `static_regions`, `temporal_curve`, rigide / non-rigide, `motion_priority`, et une compilation vers autre chose que du texte |
| 13 | **Camera** | ⛔ | la caméra est **un champ du MotionProgram** : 5 valeurs de vocabulaire (`push_in_lent`, `pull_back_lent`, `pan_lent`, `leger_tremblement`, `fixe`). `montage.Mouvement` est une seconde notion de caméra, déconnectée | `CameraProgram` séparé, avec un repère spatial partagé avec le mouvement d'objet |
| 14 | **Renderability** | ⛔ | `risque_prompt.py` : filtre déterministe avant génération (texte, logo, visage interdit) — un proto-validateur statique | score `HIGH/MEDIUM/LOW`, et surtout la **décomposition automatique** d'un plan trop complexe |
| 15 | **Capabilities** | 🟨 | `modeles.yaml` + `registre.resoudre()` : capacités (`fait:`), prix, `durees_s` réellement livrés, substitution de capacité, `a_verifier: true` | la distinction **ANNONCÉ / MESURÉ / INCONNU** en données. Aujourd'hui les mesures vivent en commentaires, et `fait:` mélange les deux statuts |
| 16 | **Strategies** | ⛔ | `animation.animer()` : modèle i2v → `vie` (parallaxe) → `camera` (Ken Burns), en **if/else** ; `PlanAnime.methode` nomme les trois | `RenderStrategyGraph` : 10 stratégies, choix `stratégie + backend + paramètres` arbitré sur coût / risque / latence |
| 17 | **Execution** | ⛔ | `Etape.depend_de` déclaré ; `etapes` sert de journal de reprise ; cache par empreinte dans `Moteur` | `ExecutionPlan` en DAG, ordonnanceur, exécution parallèle, `cache_key` et `retry_policy` **par nœud** |
| 18 | **Backends** | 🟨 | 6 adaptateurs ; `ia/texte.py` et `ia/images.py` dispatchent par fournisseur **résolu** ; les agents ignorent les fournisseurs | interface `capabilities/validate/estimate/execute` ; backends mock ; ⚠️ **quatre** modules du domaine appellent un fournisseur **en direct** (`animation.py`→fal, `voix.py` et `appariement_voix.py`→elevenlabs, `musique.py`→audd) — mesuré par `tests/test_architecture.py`, là où la lecture manuelle n'en avait vu qu'un |
| 19 | **Observation** | 🟨 | **le point fort du dépôt.** `verification_mouvement.verifier()` (diff inter-frames, seuil calibré sur données réelles : 0,509 statique vs 1,723 en mouvement → seuil 1,0) · `qa_video_finale.verifier()` (mouvement par plan sur le master **monté**) · `coherence_duree` (vidéo vs voix) · `cadrage` (variété) · `qa_image` (PASS/FAIL/**UNCERTAIN**) | `ObservationReport` unifié ; axes temporel (gels, scintillement, coupes inattendues), sémantique (identité, événement accompli), continuité (couleur, géométrie), audio (loudness, crêtes) |
| 20 | **Diagnostics** | 🟨 | `PlanAnime.diagnostic` : `mouvement_confirme, rejete_duree, rejete_mouvement, timeout, erreur_appel, hors_portee, non_elu`. `erreurs.py` : 8 catégories avec politique | la taxonomie des 18 modes d'échec, `expected vs observed` généralisé, `severite/confiance/preuve/candidats_reparation` |
| 21 | **Repair** | ⛔ | relance N fois (avec réinjection du motif au modèle sur `ErreurValidation` — bon), puis repli `vie`/`camera` | compilateur de réparation, arbre de recherche coût/risque, **réparation locale par masque**, historisation des tentatives |
| 22 | **Editor** | 🟨 | `montage.Montage` (objet structuré `Plan[]` + pistes) → FFmpeg ; `soustitres.py` (karaoké ASS mot à mot) ; `vie.py` (parallaxe locale gratuite) | `EditTimeline` comme contrat versionné, avec pistes graphiques / overlays / transitions ; FFmpeg formellement backend |
| 23 | **Memory** | 🟨 | `structures` (formes mesurées) · `univers/*.yaml` (Visual Bible) · `appels_ia` (coût) · `cache` · `artefacts` · `pdz resultats` (stats TikTok) | les **4 mémoires** séparées, `MemoryPack` (ne jamais tout envoyer), et surtout **`ExperienceMemory`** : `PlanAnime.diagnostic` existe mais n'est **pas persisté** comme série stratégie → résultat |
| 24 | **Evaluation** | ⛔ | 841 tests, dont des non-régressions sur incidents datés | corpus de golden tests (`electric_motor`, `airplane_takeoff`…), benchmarks, ⚠️ **et un CI qui lance les tests** |
| 25 | **Orchestration** | 🟨 | `episode.py` (666 l.) enchaîne, journalise et reprend | ne doit plus **décider** : la décision descend dans les couches, l'orchestration assemble |
| 26 | **API** | ✅ | `web.py` : validation humaine locale (FastAPI) | — |
| 27 | **CLI** | ✅ | 20 commandes Typer, `pdz reprendre` sans repayer | `pdz creer --sujet` (profil explicatif) |
| 28 | **Tests** | 🟨 | 841 tests, ~11 000 lignes, fixtures réelles | tests de contrat, tests d'adaptateur, tests de DAG, tests de réparation, golden tests, **CI** |
| 29 | **Infra** | ✅ | Dockerfile, compose, `produire.yml` (production depuis un téléphone), garde-fou anti-fuite | workflow de tests + lint |

**Compte** : ✅ 6 · 🟨 14 · ⛔ 9.

---

## 3. Composants réutilisables

Ce qui est repris **tel quel ou presque**, et qui représente l'essentiel de la
valeur déjà construite :

| Composant | Devient | Modification |
|---|---|---|
| `moteur/pipeline.py` — cache par empreinte, reprise, budget, réessais | `kernel/` | ajouter l'ordonnancement de DAG ; `empreinte()` est déjà la bonne fonction de `cache_key` |
| `moteur/erreurs.py` — 8 erreurs à politique | `kernel/erreurs.py` | inchangé |
| `db.py` — 7 tables, artefacts par sha256 | `kernel/db.py` | + `experiences`, `observations`, `diagnostics` |
| `prompts/` — catalogue `<id>@<semver>` | inchangé | le **patron** du versionnement de contrats |
| `ia/registre.py` + `modeles.yaml` | `capabilities/` | + statut ANNONCÉ/MESURÉ/INCONNU |
| `ia/{claude,groq,fal,pollinations,elevenlabs,audd}.py` | `backends/` | envelopper dans l'interface commune |
| `production/voix.py` + `ia/elevenlabs.py` | `audio/` | inchangé — c'est déjà la VoiceTimeline |
| `production/storyboard.py` | `shot/` | `PlanScript` → contrat `ShotSpec` |
| `production/motion_program.py` | `motion/` | extraire la caméra vers `camera/` |
| `production/contrat_visuel.py` + `decision_visuelle.py` | `perception/` | + attention ordonnée, + confusions interdites |
| `production/verification_mouvement.py` + `qa_video_finale.py` + `coherence_duree.py` + `cadrage.py` + `qa_images.py` | `observation/` | agréger en `ObservationReport` |
| `production/risque_prompt.py` + `fidelite_visuelle.py` | validation statique de `renderability/` | inchangé |
| `production/animation.py` — `noter()`, `combien_animer()` | Compute Governor de `strategies/` | séparer la **notation** (garder) de la **cascade en dur** (remplacer) |
| `video/vie.py` | backend `2.5D` de `strategies/` | nommer la stratégie |
| `video/montage.py` + `soustitres.py` | `editor/` | `Montage` → contrat `EditTimeline` |
| `univers/modele.py` — `ChampInterprete(valeur, confiance)` | `research/` et `world/` | le patron de la confiance comme champ de premier ordre |
| `analyse/*` — 12 modules, zéro IA | inchangé | outil amont, hors chaîne de compilation |
| `production/continuite.py`, `geometrie.py` | `world/` | germe du WorldState |

**Rien d'important n'est jeté.** Le travail consiste à *nommer*, *typer* et
*séparer* ce qui existe — pas à le réécrire.

---

## 4. Composants entièrement à construire

Par ordre de valeur décroissante, valeur = « ce que ça débloque » :

1. **`contracts/`** — sans lui, aucune autre couche ne peut être versionnée ni
   testée en compatibilité. Bloque tout le reste.
2. **`observation/` unifié + `diagnostics/`** — l'observation existe mais ses
   verdicts ne pilotent rien. `expected vs observed` généralisé est ce qui rend
   la réparation possible.
3. **`ExperienceMemory`** — la donnée n'est pas collectée aujourd'hui, donc le
   routage empirique est hors d'atteinte **pour toujours** tant qu'on ne
   commence pas. C'est le composant dont le coût de retard est le plus élevé.
4. **`strategies/` + interface backend** — débloque tout ajout de fournisseur
   ou de stratégie sans toucher au métier.
5. **`repair/`** — transforme un échec en information exploitable au lieu d'un
   repli silencieux.
6. **`execution/` (DAG)** — parallélisation et granularité de reprise.
7. **`camera/`** — séparation caméra / objet.
8. **`renderability/` + décomposition** — évite de dépenser sur un plan
   infaisable.
9. **`world/` + `causality/`** — nécessaires au format explicatif, utiles à la
   continuité du format fiction.
10. **`research/` + `evidence/`** — **dépend de la décision §1**.
11. **`evaluation/` (golden tests)** — nécessaire dès que les phases 4+
    commencent à changer des sorties.

---

## 5. Les cinq questions, aujourd'hui

Pour un plan produit par la chaîne actuelle :

| # | Question | Réponse aujourd'hui |
|---|---|---|
| 1 | Pourquoi ce plan existe-t-il ? | 🟨 `PlanScript` porte la réplique et l'émotion, jamais un `purpose` explicite ni un claim |
| 2 | Que doit-il montrer ? | 🟨 `ContratVisuel` (8 questions) + `elements_obligatoires` — sans attention ordonnée ni confusions interdites |
| 3 | Comment doit-il évoluer ? | ✅ `MotionProgram` (`doit_preserver` / `peut_changer` / `interdit` / `cible_perceptuelle`) |
| 4 | Comment le fabrique-t-on ? | 🟨 une cascade en dur, pas une stratégie choisie |
| 5 | Comment sait-on qu'il a réussi ? | 🟨 le **mouvement** est vraiment vérifié (avant et après montage) ; l'identité, la continuité, l'événement, l'audio ne le sont pas |

**Trois questions sur cinq sont partiellement répondues, une l'est pleinement,
aucune ne l'est nulle part.** Le système est bien plus proche de la cible que
son README ne le laisse penser — il lui manque surtout le **typage** et la
**boucle de retour** qui relie l'observation à la décision suivante.

---

## 6. Risques de l'écart, non de la migration

| Risque | Pourquoi il existe déjà | Conséquence si on ne fait rien |
|---|---|---|
| Rupture silencieuse de cache | les objets pivots n'ont pas de version ; le code contient déjà des rustines « compatibilité avec les jobs en cache d'avant `plans@1.13.0` » | un job repris produit un mélange de deux générations de décisions, sans erreur |
| Retrait de modèle chez un fournisseur | arrivé **deux fois** en 2026 (Groq, 17/06 et 13/08), détecté **en production** | une production échoue en 2 s, ou pire, part sur un repli non voulu |
| Échec non diagnostiqué | un clip peut être valide, de la bonne durée, et statique (run #66) | on paie un modèle vidéo pour un résultat que le repli gratuit aurait égalé |
| Aucune régression détectée | 807 tests, aucun CI — ✅ comblé en PHASE 1 | la seule barrière dépend d'un lancement manuel |
| Impossible d'améliorer le routage | l'expérience n'est pas persistée | on choisit les modèles à l'intuition, indéfiniment |
