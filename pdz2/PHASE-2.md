# Phase 2 — ce qui est réellement implémenté et vérifié

**Périmètre du cahier des charges** : Script + TTS réel + timing.

```
DirectorState → ScriptState → TTS réel → VoiceTimeline → durées mesurées
```

## Critère de réussite

> SI LE TTS CHANGE → LA VOICETIMELINE CHANGE → LES DURÉES OFFICIELLES CHANGENT.

Vérifié de bout en bout, sur le même épisode, en ne changeant que le réglage
du moteur :

| script | réglage moteur | durée **estimée** | durée **officielle** |
| --- | --- | --- | --- |
| identique | 165 mots/min | 19,44 s | **25,31 s** |
| identique | 110 mots/min | 19,44 s | **37,86 s** |

Le script — donc l'estimation — est rigoureusement le même. Seule la durée
officielle bouge, parce qu'elle est lue sur les trames du fichier audio.

## Chaîne réellement exécutable

```
pdz2 script    --episode ep/                 DIRECTION → SCRIPT
pdz2 voice     --episode ep/ --rate 165      SCRIPT    → VOICE
pdz2 timeline  --episode ep/                 VOICE     → TIMELINE
```

Trois commandes pour trois étapes, et ce découpage n'est pas cosmétique : on
ne peut pas obtenir une timeline sans que de l'audio existe sur le disque. La
règle VOICE FIRST devient une impossibilité pratique — le graphe d'étapes
refuse `timeline` tant que `voice` n'a pas abouti, avant même que le code
applicatif soit atteint.

Produit dans le dossier d'épisode :

```
ep/
├── script.json                  ScriptState : répliques, fonction, émotion, énergie
├── audio/lines/line-NNN.wav     un fichier par réplique — la mesure porte sur eux
├── renders/render_artifact-*.json  un artefact par réplique : sha256, durée mesurée
├── voice.wav                    assemblage, re-mesuré et vérifié
└── voice_timeline.json          VoiceTimeline : la source temporelle officielle
```

## Les dix règles, et où elles sont tenues

| Règle | Tenue par |
| --- | --- |
| 1. DirectorState reste la source conceptuelle | le compilateur ne lit rien d'autre |
| 2. ScriptState est une compilation | test : tout texte de réplique appartient à `{thèse, mécanismes rédigés, chute}` |
| 3. `estimated_duration` reste une estimation | nommée telle au contrat, dans le module, dans les journaux |
| 4. La durée officielle vient du TTS mesuré | `measure_wav` compte des trames ; le texte n'entre pas dans le calcul |
| 5. `VoiceTimeline` fait autorité | `timing_source` refusé s'il n'est pas mesuré |
| 6. Aucun ShotGraph avant le TTS | `SHOT_GRAPH` dépend de `TIMELINE` dans le graphe ; rien n'a été construit |
| 7. Pas de seconde timeline audio | `VoiceTimeline` de la phase 0, réutilisée telle quelle |
| 8. Aucun appel LLM ajouté | test : la chaîne script n'importe ni réseau ni sous-processus |
| 9. Contrats typés, sans dictionnaires | `VoiceSpec`, `MeasuredLine`, `RenderArtifact` — aucun `dict` de paramètres |
| 10. Échecs refusés et journalisés | sept exceptions nommées, chacune écrite dans l'étape en `failed` |

## La garde qui compte

L'estimation ne peut pas devenir l'autorité **par accident** :

* `VoiceTimelineBuilder.build()` prend des `MeasuredLine`, et `MeasuredLine`
  **n'a pas de champ de durée** — seulement une mesure issue d'un fichier. Il
  n'existe aucune signature par laquelle une estimation entre.
* Un test parcourt l'arbre syntaxique de `pdz2/audio/` et échoue si un module
  lit `estimated_duration_s`, par attribut ou par nom. La prose a le droit de
  nommer le champ pour dire qu'elle l'ignore ; le code, non.
* Un second test interdit à `pdz2/audio/` d'importer `pdz2.engines.script`.
* Le port de synthèse rend un **chemin**, jamais une durée : un moteur ne peut
  pas annoncer un chiffre qui deviendrait officiel.

## Ce qui est refusé, et journalisé

| Situation | Exception | Étape marquée |
| --- | --- | --- |
| binaire de synthèse absent | `SynthesiserUnavailable` | `voice` → `failed` |
| moteur en erreur ou dépassement de délai | `SynthesisFailed` | `voice` → `failed` |
| WAV illisible, tronqué, sans trame | `AudioCorrupt` | `voice` / `timeline` → `failed` |
| WAV lisible mais **muet** | `AudioSilent` | `voice` → `failed` |
| format audio changé en cours de script | `AudioFormatMismatch` | `timeline` → `failed` |
| assemblage qui ne retombe pas juste (> 2 ms) | `DurationInconsistent` | `timeline` → `failed` |
| fichier modifié depuis la synthèse | `DurationInconsistent` | `timeline` → `failed` |
| répliques manquantes, en trop, ou d'un autre script | `DurationInconsistent` | `timeline` → `failed` |

Le cas du **WAV muet** est celui qui compte le plus : un moteur qui échoue à
mi-parcours rend souvent un fichier parfaitement lisible et parfaitement vide.
Sans le plancher d'énergie, sa durée deviendrait officielle sans que personne
le sache avant le montage.

## Défauts trouvés pendant la phase

1. **Le plan de chute portait la thèse** — défaut de la phase 1, invisible
   jusqu'à ce que le script compilé fasse dire deux fois la même phrase au
   spectateur. Corrigé à la source, dans le compilateur de réalisation.
2. **`--voices` et `=fr` passés en deux arguments** — le filtre de langue était
   ignoré et le binaire listait les 131 voix.
3. **`latency_s` calculé n'importe comment** dans la commande `voice` (un
   `and` résiduel qui rendait toujours 0). La vraie latence de synthèse est
   maintenant portée par `MeasuredLine`.
4. **La garde anti-estimation attrapait sa propre documentation** — elle
   scannait le texte des fichiers. Elle porte désormais sur l'arbre
   syntaxique : plus précise, et plus stricte là où ça compte.
5. Un test attendait un message applicatif là où **le graphe d'étapes refuse
   plus tôt**. L'attente était plus faible que la réalité : le test dit
   maintenant la garantie structurelle.

## Contrats

* `render_artifact` **1.0.0 → 1.1.0** : ajout de `source_contract_id`, le
  contrat dont l'artefact est le rendu — ici une réplique de script.
  Rétrocompatible, vérifié par test sur une charge utile 1.0.0.
* `ProviderCapability` et `CapabilityState` déplacés de
  `engines/research/ports.py` vers `contracts/capability.py` : sans ce
  déplacement, la chaîne audio aurait dû importer le moteur de recherche pour
  savoir dire « injoignable ».
* Aucune seconde timeline. `VoiceTimeline`, `VoiceSegment`, `TimingSource`
  datent de la phase 0 et sont utilisés tels quels.

## Limites déclarées, pas contournées

* **Dépendance système `espeak-ng`.** Installée ici par `apt-get install
  espeak-ng`. Absente, l'adaptateur se déclare `UNAVAILABLE` avec la raison,
  et les tests qui en dépendent se déclarent **ignorés** plutôt que de faire
  semblant de passer.
* **eSpeak NG n'est pas une voix de production.** C'est un synthétiseur à
  formants, et cela s'entend. Il est là parce qu'il est réel, hors-ligne,
  reproductible au bit près et à débit réglable — les quatre propriétés qui
  permettent de *prouver* la règle. Un meilleur moteur se branchera derrière
  le même port sans qu'une ligne bouge en aval.
* **Les timings de mots ne sont pas mesurés.** `VoiceSegment.words` reste
  vide. eSpeak NG ne rend pas de marques de mot exploitables, et un aligneur
  approximatif produirait des sous-titres faux avec l'air d'être justes. À
  traiter en phase 10.
* **Le script observé est trop court pour sa cible** (25,3 s mesurées contre
  45 s visées). Ce n'est pas un défaut du compilateur : c'est ce que dit le
  brief, et le système le signale — avant la synthèse par l'estimation, après
  par la mesure. Rapprocher les deux relève de la réalisation, pas du
  compilateur.

## Résultat d'exécution

```
$ pytest pdz2/tests -q
480 passed
$ ruff check pdz2/
All checks passed!
```

Dont, pour la seule phase 2 : 20 tests de mesure audio, 24 sur la règle VOICE
FIRST, 18 sur le compilateur de script, 14 sur la ligne de commande.

## Prochaine étape

Phase 3 — Shot Graph + Visual Bible, construits sur `voice_timeline.json` et
sur rien d'autre. Aucune durée théorique n'entrera dans le découpage.
