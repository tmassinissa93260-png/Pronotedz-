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

## Phase 3 — Deux profils, une convergence ✅ **FAIT**

> La décision de docs/GAP_ANALYSIS.md § 1 est prise : **option A**.

### Livré

| Paquet | Rôle | IA ? |
|---|---|---|
| `pdz/narrative/` | `Univers` + script → `NarrativeState` | ✗ |
| `pdz/research/` | `RechercheBackend` (Protocol) → `ResearchState` | ✗ |
| `pdz/director/` | l'un OU l'autre → **`DirectorState`** | ✗ |

**Aucun appel IA dans les trois.** Tout vient de matière déjà écrite :
l'univers (YAML versionné), le brief et le script (`BriefWriter`,
`ScriptWriter`), le graphe de connaissance. Redemander à un modèle ce que
deux structures portent déjà serait payer pour dégrader une information
qu'on avait exacte.

### La convergence

`compiler(topic, source)` route sur le **type** de la source, jamais sur un
drapeau : un `ResearchState` ne peut pas être compilé en fiction, et laisser
un booléen décider ouvrirait cette possibilité pour rien.

Les deux profils produisent le même `DirectorState@1.0.0`. Tout ce qui suit —
plans, perception, mouvement, rendu, observation, réparation — s'écrit **une
seule fois**.

### Ce qui reste propre à chacun

|  | FICTION | EXPLICATIF |
|---|---|---|
| matière | personnages, conflit, événements, règles du monde | claims, sources, confiance, conflits |
| thèse | la promesse du script | le claim le plus solide |
| points portés | les événements | **seulement les claims sourcés** |
| paliers | découvre → enjeu → parti pris → tension → retournement → conséquence | ignore → question → explication → mécanisme → causalité → payoff |

Les paliers diffèrent parce qu'**on ne « comprend » pas une trahison** : en
fiction, l'acquisition n'est pas un savoir mais une tension. Les six paliers
explicatifs y seraient un contresens.

### L'honnêteté, appliquée

`qualifier()` centralise la règle en un seul endroit testable :

- aucune source → `HEURISTIQUE` (un énoncé non sourcé peut être vrai ; il
  n'est pas *vérifié*) ;
- une contradiction → `HEURISTIQUE`, quoi qu'il arrive par ailleurs — le
  système ne tranche pas un désaccord tout seul ;
- information périmée → `HEURISTIQUE` ;
- la confiance **plafonne sous 1,0** : aucune recherche automatique ne mérite
  la certitude absolue, et laisser le nombre atteindre 1 inviterait à
  confondre confiance et statut.

**Seuls les claims affirmables entrent dans `points_a_porter`.** Un
heuristique peut apparaître dans la vidéo, nuancé — il ne fait pas partie de
ce qu'elle *promet*. Les lacunes de recherche remontent en continuité non
résolue : une lacune énoncée est utilisable, une lacune silencieuse produit
une vidéo assurée sur du vide.

`SansRecherche` est le backend par défaut. Ce n'est pas un mode dégradé :
c'est la réponse honnête quand rien n'est configuré. Il produit un état vide
dont la lacune est nommée — infiniment préférable à un graphe de claims
inventés par un modèle à qui l'on aurait demandé « ce que tu sais ».

> **Backend réel** : non fourni ici. `RechercheBackend` est un `Protocol`, et
> l'adaptateur réseau appartient à la PHASE 6 avec les autres backends.
> L'écrire maintenant dupliquerait ce travail.

### Corpus golden étendu

`explicatif_moteur.json` gèle la compilation explicative, avec un énoncé
volontairement non sourcé : la référence **prouve** qu'il est exclu des
promesses et remonté en lacune.

### Résultat

```
profils   →  30 tests · golden → 12 tests
pytest    →  1039 passed, 0 échec
```

---

## Phase 4 — `ExperienceMemory` ✅ **FAIT**

**Le composant dont le retard coûte le plus cher.** Sans ces lignes, aucun
routage empirique n'est possible — pas faute d'algorithme, faute de *donnée*.
Chaque production faite sans enregistrer son expérience est une observation
perdue pour toujours.

### Livré

Table `experiences` **dans la base existante** — jamais une seconde base,
jamais un second cache. `pdz/memory/experience.py` fait quatre choses :
collecter, stocker, requêter, analyser. **Il ne route rien.**

### Une ligne par TENTATIVE

Pas par plan. Un plan réparé trois fois produit trois enregistrements —
c'est précisément ce qui permettra de mesurer si une réparation marche.
Agréger par plan effacerait l'information cherchée.

L'unicité porte sur `(job, plan, tentative)` : reprendre un job ne duplique
pas ses expériences, ce qui gonflerait les échantillons — et la confiance
accordée aux chiffres — sans qu'aucune tentative de plus n'ait eu lieu.

### `None` n'est pas `0.0`

`taux_de_reussite` rend `None` quand rien n'a été observé. « On n'a jamais
essayé » et « ça échoue toujours » sont deux informations opposées : les
confondre éliminerait pour toujours une stratégie jamais tentée.

`echantillon` accompagne chaque statistique : une réussite sur une tentative
et quarante sur quarante donnent le même taux, et l'une ne vaut rien.
`significative` le dit sans rien bloquer.

Stratégie et modèle sont agrégés **séparément** — `2.5D` peut être rendu par
plusieurs moteurs, un modèle peut servir plusieurs stratégies ; les mélanger
masquerait lequel est en cause.

### Pas encore de routeur

L'ordre imposé, à ne pas inverser :
`collecter → stocker → requêter → analyser → (un jour) router`.

Construire un routeur avant d'avoir les données produirait un modèle entraîné
sur rien, avec l'assurance d'un modèle entraîné sur beaucoup. **La PHASE 19
n'a pas le droit de commencer avant que cette table soit remplie par de
vraies productions.**

### Résultat

```
mémoire   →  17 tests
```

---

## Phase 5 — Un seul orchestrateur ✅ **FAIT**

**Le GAP structurel principal du dépôt.**

`moteur/pipeline.py` et `production/episode.py` écrivaient chacun dans la
table `etapes` sans se connaître — `episode.py` neuf fois, via ses propres
`_fait()`/`_noter()`. Deux mécanismes de reprise devant rester d'accord pour
toujours, ce qui n'arrive jamais. Et le chemin réel de production, le second,
n'avait **aucun accès au cache du moteur**.

### `pdz/moteur/journal.py` — la seule autorité

Lecture, écriture, cache : un seul module, appelé par les deux. Ce
qu'`episode.py` savait faire de mieux — **revérifier que les fichiers cités
existent encore** — monte au noyau et devient la règle commune, y compris
pour le cache : une entrée dont le `.mp4` a disparu est rejetée *et purgée*,
au lieu de faire échouer le montage trente secondes plus tard sur une erreur
méconnaissable.

Reprise et cache restent **distincts**, et c'est essentiel : la reprise est
par *job*, le cache par *empreinte*. Les confondre ferait resservir à un job
les fichiers d'un autre.

### Verrouillé

`test_seul_le_journal_ecrit_les_points_de_reprise` interdit tout `INSERT INTO
etapes` / `INSERT INTO cache` hors du journal. Un troisième mécanisme ne peut
plus naître en silence.

**Résultat** : 16 tests de journal, 0 changement de comportement.

---

## Phase 6 — Interfaces backend ✅ **FAIT**

Les **quatre** dépendances métier → fournisseur déclarées en PHASE 1 ont
disparu. `ECARTS_CONNUS` est vide, et le test à double sens a *forcé* le
retrait des dérogations.

### `pdz/backends/` enveloppe, ne réécrit pas

```
métier  →  backends  →  pdz/ia/<fournisseur>  →  HTTP
```

`pdz/ia/*` est inchangé : ce sont les clients HTTP, écrits et éprouvés.

| Interface | Méthodes | Réel | Mock |
|---|---|---|---|
| `VideoBackend` | `capabilities` · `valider` · `estimer` · `executer` | fal | ✅ |
| `TTSBackend` | `capabilities` · `voix_disponibles` · `synthetiser` | elevenlabs | ✅ |
| `ReconnaissanceAudioBackend` | `capabilities` · `identifier` | audd | ✅ |

Séparer `valider`/`estimer` d'`executer` est ce qui permet de **refuser un
plan infaisable sans payer pour l'apprendre**. `executer()` revalide toujours :
un appelant qui oublie ne doit pas pouvoir engager un euro.

### `VoixDisponible` remonte dans l'interface

`elevenlabs.Voix` en hérite. Le métier annote ses variables sans importer un
fournisseur pour un nom de type.

### Le registre est public

`BACKENDS` est un point d'extension, pas un détail privé. Les tests
substituent un fournisseur par `monkeypatch.setitem` — **si un test devait
forcer une porte privée, ce serait le signe que l'architecture ne tient pas
sa promesse.**

Onze faux `animer_image` déjà écrits ont été *enveloppés*, pas réécrits :
chacun reproduit un mode d'échec précis, et ce qu'ils vérifient est inchangé.

**Résultat** : 28 tests de backend, 0 écart d'architecture.

---

## Phase 7 — `ANNONCE` / `MESURE` / `INCONNU` ✅ **FAIT**

Le dépôt savait ces choses — **en commentaires** :

> « MESURÉ (runs #57, #65, #66) : ce endpoint rend ~4,84 s qu'on lui demande
> 5 ou 10 » · « ANNONCÉES par fal, pas encore mesurées ici »

Un commentaire ne se requête pas, ne s'agrège pas, et ne peut pas empêcher
une décision. `modeles.yaml` porte désormais un bloc `capacites:`.

### La règle de conversion

- `fait:` → **ANNONCE**. C'est une déclaration de configuration : elle sert à
  *router*, jamais à garantir. Choisir n'est pas promettre.
- `capacites:` → le statut écrit. Seul endroit où `MESURE` peut apparaître.

**Conséquence assumée : 25 capacités sur 32 sont non mesurées.** Ce n'est pas
un défaut du module, c'est l'état réel de la connaissance du dépôt.
`mesures_manquantes()` en fait la liste de travail.

### `MESURÉ-FAUX` ≠ `INCONNU`

`duree_10s` sur ltx-video : `statut: MESURE, valeur: false` — « on a vérifié
que non ». Sur Kling : `statut: ANNONCE, valeur: true` — « fal le dit ».
Même capacité, deux statuts. C'est précisément ce que l'ancienne structure ne
savait pas exprimer.

**Résultat** : 15 tests de capacités.

---

## Phase 8 — Stratégies ✅ **FAIT**

`vie.py` **était** du 2.5D, le Ken Burns **était** du procédural, l'appel
Kling **était** du `DIRECT_I2V`. Aucun des trois n'était nommé, et la
sélection était un `if/else` : modèle payant → `vie` → `camera`.

### Ce que le nommage a révélé

**Deux stratégies garantissent le mouvement, une l'espère.** Le run #66 a
mesuré un clip payé, valide, de la bonne durée et parfaitement statique. La
parallaxe locale, elle, est du calcul.

Et l'inverse est vrai aussi : **la parallaxe ne sait pas inventer un
mouvement de sujet.** Un personnage qui tourne la tête demande des pixels
absents de l'image de départ. Chaque stratégie déclare donc ce qu'elle sait
rendre (`sujet` / `ambiance` / `camera`), et sa confiance en dépend.

### L'erreur de conception, corrigée et gardée en test

La première version classait sur « confiance par euro ». Mathématiquement
cohérent, et **faux** : diviser par un coût quasi nul rend toute stratégie
gratuite mille fois meilleure que n'importe quelle payante — le modèle
génératif n'aurait *jamais* été choisi, y compris sur un plan qu'il est seul
à savoir rendre.

Remplacé par une **utilité espérée** :

```
utilité = confiance × valeur_du_plan − coût
```

`test_un_ratio_confiance_par_euro_ferait_toujours_gagner_le_gratuit` garde
le défaut comme test de non-régression.

### Le comportement obtenu

| mouvement attendu | plan critique | plan secondaire |
|---|---|---|
| **sujet** | `DIRECT_I2V` — seul à savoir le rendre | `2.5D` — n'en vaut pas le prix |
| **ambiance** | `2.5D` — gratuit **et** garanti | `2.5D` |
| **caméra** | `2.5D` | `2.5D` |
| budget épuisé | `2.5D`, avec la raison écrite | idem |

C'est **meilleur** que la cascade en dur, qui tentait toujours le payant
d'abord — y compris pour une ambiance que la parallaxe rendait gratuitement
et à coup sûr.

`VALEUR_PLAN_MAXIMALE_EUR = 1,00 €` est calibré sur ce que le dépôt **paie
déjà** (1,56 €/épisode animé, 0,23 € le clip de 5 s), pas sur une intuition.
C'est le paramètre le plus discutable du module, et c'est voulu qu'il soit
le plus visible.

### Branché

`animation._repli()` exécute désormais `TWO_POINT_FIVE_D` et `PROCEDURAL`
nommément. Comportement identique — vérifié par les 91 tests d'animation
existants. Une implémentation sans usage n'aurait pas été acceptable.

**Résultat** : 21 tests de stratégie.

---

## Phase 9 — `CameraProgram` branché

Le contrat existe (PHASE 2), l'adaptateur aussi. Reste à le faire produire
par la chaîne au lieu d'un champ de `MotionProgram`, et à faire de
`montage.Mouvement` une **compilation** du `CameraProgram` plutôt qu'une
seconde notion de caméra sans rapport.

`ControleCamera.PARAMETRIQUE` n'apparaîtra que le jour où un backend
l'accepte **et** qu'on l'a mesuré.

**Critère** : un même `CameraProgram` compile vers un texte pour un backend
i2v **et** vers un filtre FFmpeg pour la stratégie procédurale.
**Risque** : moyen. **Effort** : moyen.

---

## Phase 10 — `SceneState` + événements + transitions

`WorldState` et `CausalState` existent (PHASE 2). Reste à les **produire et
mettre à jour** : `continuite.py` et `geometrie.py` y sont absorbés, et
chaque plan validé écrit son delta.

Le mouvement devient exprimable comme `ÉTAT A → ÉVÉNEMENT → ÉTAT B` — la
base sur laquelle le Motion Program s'appuiera vraiment.

**Critère** : après chaque plan validé, le delta d'état est journalisé.
**Risque** : moyen. **Effort** : moyen.

---

## Phase 11 — `PerceptualContract` branché

Contrat et adaptateur faits (PHASE 2). Reste à le faire produire par la
chaîne, et surtout à ce que **la QA le lise** — c'est lui qui transforme
« mouvement faible » en `CAMERA_DOMINANT`.

**Critère** : chaque plan répond aux questions 1 et 2 des cinq.
**Risque** : faible. **Effort** : moyen.

---

## Phases 12 à 14 — Faisabilité, décomposition, exécution ✅ **FAIT**

### 12 — `pdz/renderability/` : ne pas payer pour apprendre qu'un plan est infabricable

`HIGH` / `MEDIUM` / `LOW` est une estimation de **faisabilité technique**.
Ce n'est pas une note esthétique : « difficile à fabriquer » et « sera moche »
sont deux jugements sans rapport, et aucun champ de `Complexite` ne parle de
qualité — c'est testé.

Le score **part de 1,0 et retire** : un plan sans contrainte vaut 1, ce qui
est le cas de la majorité des plans du dépôt. Les difficultés se **cumulent**
(produit, pas moyenne) — six entités *et* une identité à tenir *et* un
mouvement de sujet est bien plus dur que chacun séparément, ce qu'une moyenne
lisserait.

Les poids sont assumés et en table lisible, tirés de ce que le dépôt a déjà
mesuré ou documenté : au-delà de trois éléments un modèle d'image en oublie
(`fidelite_visuelle.py` existe pour ça), l'identité est « le problème n°1 des
séries générées » (`images.py`), un mouvement de sujet est plus dur qu'une
ambiance (même limite que côté stratégies).

`facteur_dominant` dit **quoi simplifier** : « ce plan est LOW » ne sert à
rien, « LOW à cause de sept éléments » si.

La validation statique **réutilise `risque_prompt.py` tel quel** — filtre
déterministe, zéro appel IA, qui sait déjà repérer texte lisible, logos et
visages interdits. `visage_interdit` est *passé*, pas déduit : la contrainte
vient de l'univers, et ce module ne connaît pas l'univers.

### 13 — `pdz/renderability/decomposition.py` : découper plutôt qu'échouer

**Jamais sans conserver la fonction narrative.** Chaque plan issu d'un
découpage hérite du `but`, du `porte`, de la `fonction`, des ancres et de
l'émotion. Une décomposition qui perd le pourquoi produit trois plans
corrects qui ne racontent plus rien — et ça ne se voit qu'au montage.

Le découpage attaque le **facteur dominant** : trop d'entités → *établir*
puis *révéler* ; mouvement trop chargé → *poser* puis *jouer* ; durée hors
capacité → deux moitiés. Simplifier ce qui n'était pas le problème ne rendrait
le plan ni plus faisable, ni plus lisible.

Deux garde-fous : la somme des durées est conservée (la voix reste la
chronologie officielle), et un plan sous ~2,4 s n'est **jamais** découpé —
sous 1,2 s une coupe n'est plus lue comme un changement, on fabriquerait du
clignotement.

`decomposer()` rend **toujours au moins un plan** : un appelant ne doit
jamais avoir à distinguer « décomposé » de « pas décomposé ».

### 14 — `pdz/execution/` : le DAG, exécuté

`ExecutionPlan.ordonnancer()` existait depuis la PHASE 2. L'ordonnanceur
`asyncio` l'exécute, vague par vague.

L'ordre des vérifications avant chaque nœud :

```
1. déjà fait dans CE job ?   → reprise, gratuite
2. déjà calculé AILLEURS ?   → cache par empreinte, gratuit
3. sinon                     → exécution, payante
```

Les inverser ferait préférer le résultat d'un autre job à celui de celui-ci :
la reprise est plus *spécifique* que le cache. Les deux viennent du journal —
**aucun troisième mécanisme**, c'est ce que la PHASE 5 a supprimé.

Ce que l'ordonnanceur garantit :

- **profondeur et masque partent ensemble** — les exécuter en série
  doublerait l'attente pour rien ;
- **la reprise est par NŒUD** — un composite raté ne refait pas la carte de
  profondeur, et ne la repaie pas ;
- **un échec n'arrête pas le DAG** — les branches indépendantes continuent ;
  seules celles qui en dépendent sont ignorées. Tout arrêter perdrait le
  travail déjà payé de la même vague ;
- **la politique de relance vit sur le nœud** — une carte de profondeur
  locale et un appel vidéo en file d'attente n'appellent pas la même ;
- **le parallélisme est plafonné** — dix appels simultanés chez le même
  fournisseur se font limiter, et dix ffmpeg d'un coup ne vont pas plus vite.

> **Pourquoi maison plutôt que Temporal / Prefect / Airflow** : 20 à 40 nœuds
> par job, sur une machine, avec `etapes` comme journal déjà en place. Ces
> outils apporteraient un serveur, une base et un modèle de déploiement pour
> un gain nul. Voir docs/TARGET_ARCHITECTURE.md § 6.

**Résultat** : 24 tests de faisabilité, 16 tests de DAG.

---

## Phases 15 à 17 — La boucle de retour ✅ **FAIT**

Observation → diagnostic → réparation. C'est ce qui transforme un échec en
information exploitable, au lieu d'un repli silencieux.

### 15 — `pdz/observation/` : les sondes parlent une langue commune

Les cinq sondes du dépôt sont **traduites, pas réécrites**. Leurs seuils
calibrés sur données réelles sont conservés tels quels — les rejouer
autrement reviendrait à jeter le travail de mesure qui les a produits. Le
seuil est reporté dans chaque `Mesure` : sans lui, un ancien rapport devient
ininterprétable après un recalibrage.

**Un axe non mesuré vaut `INCERTAIN`, jamais `REUSSI`.** Un rapport ne
portant qu'une mesure de mouvement est globalement `INCERTAIN`, et
`axes_non_mesures` dit lesquels manquent — la carte des angles morts, utile
telle quelle.

Deux distinctions que le module refuse de gommer :
- un **fichier illisible** rend le mouvement `INCERTAIN`, pas `ECHOUE` :
  accuser le modèle d'un problème de fichier ferait chercher au mauvais
  endroit ;
- une **répétition de cadrage** reste `INCERTAIN` — le module d'origine
  refuse explicitement d'en faire une faute, et ce n'est pas à la traduction
  de durcir ce choix.

### 16-17 — `pdz/diagnostics/` : l'écart, pas le verdict

Un diagnostic est une **hypothèse de cause**, avec sa confiance. `None` est
un résultat (« l'observation ne contredit pas l'intention »), distinct
d'`INCONNU` (« on n'a pas pu savoir »).

L'`Attendu` est passé explicitement, réduit à ce qui est **vérifiable** —
trois questions, pas trente. Le diagnostic ne relit pas le `MotionProgram` :
il vivrait alors dans la couche de décision.

| observation | attendu | diagnostic |
|---|---|---|
| aucun mouvement | le sujet devait agir | `STATIC_RENDER` (0,9) |
| aucun mouvement | + confusion caméra déclarée | `CAMERA_DOMINANT` (**0,6**) |
| aucun mouvement | rien ne devait bouger | *aucun* |
| mouvement non mesurable | le sujet devait agir | `UNKNOWN` (0,3) → humain |
| fichier illisible | — | diagnostiqué **avant** le mouvement |

`CAMERA_DOMINANT` porte volontairement une confiance plus basse : sans sonde
qui *sépare* le mouvement de caméra de celui du sujet, c'est une hypothèse
fondée sur l'intention. Le dire est plus utile que d'affirmer.

### 16 — `pdz/repair/` : changer la cause, pas relancer

Le catalogue est indexé **par cause**, et l'escalade va du ciblé au lourd :

| cause | réparation | puis |
|---|---|---|
| `CAMERA_DOMINANT` | `CAMERA_FIX` | `MOTION_FIX` → `STRATEGY_FIX` |
| `STATIC_RENDER` | `MOTION_FIX` | `STRATEGY_FIX` → `PROMPT_FIX` |
| `IDENTITY_DRIFT` | `LOCAL_REPAIR` | jamais tout refaire si le masque suffit |
| `UNKNOWN` | `ASK_HUMAN` | — |

Une branche déjà tentée n'est **pas** reproposée : sans cette règle, l'arbre
choisirait éternellement la même — c'est-à-dire exactement
`retry 1 / retry 2 / retry 3`.

### L'erreur commise deux fois, corrigée à la racine

Le choix de stratégie **et** le choix de réparation ont d'abord classé leurs
options sur « confiance par euro ». Conséquences observées :

- le modèle génératif n'était **jamais** retenu, y compris sur un plan qu'il
  est seul à savoir rendre ;
- `ACCEPTER` gagnait contre **toutes** les réparations, y compris gratuites —
  le défaut n'était jamais corrigé, et le journal affichait pourtant
  « réparation choisie : accepter ».

`utilite_esperee()` vit désormais dans le vocabulaire commun :

```
utilité = confiance × (1 − risque) × valeur_du_plan − coût
```

Un seul endroit à relire, un seul à remplacer quand `ExperienceMemory` aura
de quoi le contredire. Deux corrections de fond en ont découlé :
`ACCEPTER.succes_attendu = 0` (accepter ne *répare* rien, elle *termine*), et
`CHANGER_STRATEGIE` ramené de 0,85 à 0,60 — retomber sur la parallaxe
garantit *un* mouvement, pas *celui qui était demandé*, exactement la limite
déjà énoncée côté stratégies.

**Résultat** : 32 tests de boucle, et le défaut du ratio gardé comme test de
non-régression.

---

## Phase 18 — Golden tests ✅ **FAIT** *(avancée en PHASE 2b)*

Avancée parce que les phases 5 à 14 réécrivent la chaîne qui produit ces
structures. Le corpus s'étoffe à chaque phase qui ajoute un producteur.

---

## Phase 19 — Routage empirique — **verrouillée**

Ne commence **que** lorsque `experiences` contient de vraies productions en
quantité suffisante (`ECHANTILLON_MINIMAL` par stratégie, au minimum).

Avant cela, il n'y a rien à apprendre, et un routeur entraîné sur rien aurait
l'assurance d'un routeur entraîné sur beaucoup.

---

## Ordonnancement et dépendances

```
0 architecture ✅ → 1 filet ✅ → 2 contracts ✅ → 2b golden ✅
                                      │
        ┌─────────────────────────────┼──────────────────────────┐
        ↓                             ↓                          ↓
  3 profils ✅              4 ExperienceMemory ✅      5 orchestrateur unique ✅
                                      │                          ↓
                                      │                 6 backends ✅ → 7 capacités ✅
                                      │                          ↓
                                      │                   8 stratégies ✅
                                      │                          │
                                      │      ┌───────────────────┼────────────────┐
                                      │      ↓                   ↓                ↓
                                      │  9 caméra        10 scene state    12 renderability
                                      │      │                   │                │
                                      │      └──→ 11 perception ←─┤                ↓
                                      │                          │        13 décomposition
                                      │                          ↓                │
                                      │                 14 execution DAG ←─────────┘
                                      │                          ↓
                                      │                   15 diagnostics
                                      │                          ↓
                                      │                     16 repair
                                      │                          ↓
                                      └────────────→ 17 expected vs observed
                                                                 ↓
                                                     19 routage empirique 🔒
```

**Neuf phases sur dix-neuf sont faites** (0, 1, 2, 2b, 3, 4, 5, 6, 7, 8 —
plus la 18 avancée). La 19 est verrouillée par la donnée, pas par le code :
elle attend que `experiences` se remplisse de vraies productions.

Les phases 9 à 13 sont largement **indépendantes entre elles** — leurs
contrats existent depuis la PHASE 2, il ne reste qu'à les brancher. Elles
peuvent avancer dans n'importe quel ordre selon ce qui bloque le plus.

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
