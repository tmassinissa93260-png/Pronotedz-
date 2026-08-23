# Phase 3 — Shot Graph + Visual Bible

## CURRENT STATE

```
pdz2 research → brief-template → direct → script → voice → timeline → bible → shots
```

Huit commandes, de la question au découpage. Les phases 0 à 3 sont
implémentées ; rien de la phase 4 n'a été commencé.

Sur l'épisode de référence (« Comment fonctionne une voiture électrique ? »,
audio réel eSpeak NG de 25,308 s) :

```
6 créneaux pavant 25.308s d'audio mesuré
6 plans pavant 25.308s — 4 démontrent une affirmation, 2 encadrent
6/6 caméras en mouvement

  S00   0.00→ 5.19s [hook       ] wide             push_in   mv 0.65 nv 0.30 at 0.86 in 0.76
  S01   5.19→ 8.83s [mechanism  ] cutaway_diagram  pan       mv 0.70 nv 0.10 at 0.94 in 0.80
  S02   8.83→12.53s [consequence] medium           pull_out  mv 0.50 nv 0.25 at 0.96 in 0.76
  S03  12.53→16.42s [mechanism  ] cutaway_diagram  tilt      mv 0.70 nv 0.25 at 0.94 in 0.78
  S04  16.42→20.22s [consequence] medium           push_in   mv 0.50 nv 0.25 at 0.91 in 0.77
  S05  20.22→25.31s [payoff     ] wide             pan       mv 0.60 nv 0.30 at 0.83 in 0.76
```

## ARCHITECTURE

```
DirectorState ─┐
               ├→ TemporalDirector → TemporalPlan ─┐
VoiceTimeline ─┘   (créneaux + 5 courbes)          ├→ ShotGraphCompiler → ShotGraph
                                                   │                    + CameraProgram[]
DirectorBrief ─→ VisualBibleCompiler → VisualBible ┘
```

| Paquet | Rôle |
| --- | --- |
| `engines/temporal/slots.py` | pavage du temps mesuré, découpe, constats |
| `engines/temporal/curves.py` | les cinq courbes, une formule écrite chacune |
| `engines/temporal/director.py` | assemblage, lignée, constats de rythme |
| `engines/visual/presets.py` | tables de style déclarées par ton |
| `engines/visual/bible.py` | décidé vs dérivé, sans fournisseur |
| `engines/shots/grammar.py` | cadrage, caméra, mouvement, raccord, son, incrustation |
| `engines/shots/compiler.py` | assemblage, lignée, lien affirmation → plan |

## CHANGES

* `SHOT_GRAPH` produit désormais `camera_program` : un plan ne peut pas
  exister sans caméra, et `ShotSpec.camera_program_id` est obligatoire.
  `MOTION` reste la source de vérité du mouvement (phase 6). C'était une
  incohérence de la phase 0, révélée par la phase 3.
* `syllable_count` déplacé vers les outils de texte partagés : le Temporal
  Director n'a pas à dépendre du module d'estimation de la phase 2.
* `ShotGraph.shots_for_claim()` et `demonstrated_claim_ids()` : le lien
  affirmation → plan se lit dans les données.
* `TemporalPlan.position_of()` et l'échantillonnage des courbes passent par la
  même fonction, `sample_position`.

## NEW CONTRACTS

| Contrat | Version | Rôle |
| --- | --- | --- |
| `temporal_plan` | 1.0.0 | créneaux pavant l'audio + cinq courbes + constats |
| `ShotSlot` (élément) | — | fenêtre d'un plan, avec ses bornes de parole |
| `RhythmFinding` (élément) | — | constat de rythme, mesuré et seuillé |
| `VisualStyleDecision` (élément) | — | parti pris esthétique, décidé une fois |
| `director_brief` | 1.0.0 → **1.1.0** | `visual_style` facultatif ; 1.0.0 relu sans migration |

## SHOT GRAPH

**Durées.** Un créneau par réplique, du début de sa parole au début de la
suivante ; le dernier va à la dernière trame. Les créneaux pavent exactement
l'audio — pas de trou, pas de chevauchement, et le contrat le revérifie à 2 ms
près. Aucune durée théorique n'entre : la seule source est `VoiceTimeline`.

**Recouvrements et marges.** Un fondu se déclare *à l'intérieur* de la durée
d'un plan et ne déborde jamais sur son voisin ; sa durée est plafonnée au
quart du plus court des deux plans qu'il relie. La somme des plans reste donc
égale à la durée de l'audio.

**Découpe et fusion.** Une réplique trop longue est découpée en parts égales —
opération purement temporelle, rien de narratif ne change. Une réplique trop
courte est **constatée, jamais fusionnée** : fusionner supprimerait un temps
visuel décidé par la réalisation, ce qui serait une décision narrative prise
en silence par le compilateur.

**Chaque plan est complet.** Les seize champs exigés sont renseignés, et
chacun vient d'une règle nommée dans `grammar.py` : cadrage par fonction
narrative, caméra par cible de mouvement (verrouillée sous 0,30, alternée
sinon), rotation du sujet pour un mécanisme, raccord par continuité
d'affirmation et d'ancres, ponctuation sonore par fonction, incrustation
uniquement pour une grandeur chiffrée.

**Le lien avec l'affirmation est structurel.**

```
Claim.id → VisualEvidencePlan.claim_id → ShotSpec.claim_id
                                      → ShotSpec.evidence_required
                                      → ShotSpec.visual_subject
```

Un plan démonstratif sans preuve visuelle rédigée est refusé ; une affirmation
de la chaîne causale sans aucun plan l'est aussi.

## VISUAL BIBLE

Quatorze champs, aucun fournisseur. Deux natures que le compilateur ne
mélange pas :

* **décidé** — style, lumière, palette, optique, matières, texture, décor,
  graphisme, venant de `DirectorBrief.visual_style` ;
* **dérivé** — densité visuelle depuis la densité d'information, interdits
  depuis l'imagerie proscrite, langage caméra et profondeur de champ depuis le
  rythme, longueur de ligne depuis la densité.

Sans décision, un **préréglage déclaré** est appliqué selon le ton, et le
compilateur l'écrit : *« style NON décidé : préréglage déclaré pour le ton
documentary »*. Un préréglage est une table publiée — deux appels rendent le
même objet, rien n'est fabriqué à l'exécution.

## TESTS

| Fichier | Ce qu'il prouve |
| --- | --- |
| `test_temporal_director.py` | pavage exact, découpe, constat de créneau court, précision d'échantillonnage, propriétés des cinq courbes, refus de lignée |
| `test_shot_graph.py` | seize champs remplis, lien affirmation → plan, **cinq propagations**, absence de décision narrative nouvelle, grammaire, contraintes de rendu |
| `test_visual_bible.py` | zéro fournisseur, décidé vs préréglé, champs dérivés, refus de lignée |
| `test_cli_phase3.py` | `bible` et `shots` de bout en bout, échecs journalisés |

Les propagations demandées, vérifiées chiffres en main :

```
1. DirectorState modifié  → sujets visuels des plans modifiés
2. VoiceTimeline modifiée → audio 9,450s → 29,450s
                            graphe 9,450s → 29,450s
                            départs [0, 2.45, 4.75, 7.10] → [0, 7.45, 14.75, 22.10]
                            script rigoureusement identique
3. Claim modifié          → S01 mouvement du sujet rotate → linear
                            plans non concernés modifiés : aucun
4. VisualBible modifiée   → espace négatif 0.339 → 0.15 sur tous les plans
5. Rythme modifié         → cibles de mouvement [0.65, 0.40, 0.20, 0.60]
                                              → [0.85, 0.60, 0.40, 0.80]
```

**Aucune décision narrative nouvelle** — six tests distincts : tout sujet
visuel appartient à l'ensemble décidé par la réalisation ; toute exigence de
preuve vient du plan de preuve ; toute fonction narrative et toute affirmation
viennent d'une intention de plan ; toute ancre vient du `DirectorState` ; la
seule règle d'incrustation recopie un chiffre déjà présent dans la réplique ;
`grammar.py` ne mentionne ni thèse, ni chute, ni audience ; et le paquet
n'importe ni réseau ni sous-processus.

## TEST RESULTS

```
$ pytest pdz2/tests -q
571 passed
$ ruff check pdz2/
All checks passed!
```

Dont, pour la seule phase 3 : 28 tests de Temporal Director, 38 de Shot Graph,
15 de Visual Bible, 10 de ligne de commande.

## DEFECTS FOUND

1. **Une cible de 0,30 se lisait 0,2999998.** Les courbes étaient
   échantillonnées au milieu du créneau, mais relues à une position recalculée
   sans le même arrondi. L'interpolation qui en résultait faisait passer la
   cible sous le seuil de verrouillage, et **la caméra se figeait en silence**.
   Une seule fonction, `sample_position`, sert maintenant aux deux.

2. **Le seuil de lisibilité frappait la narration normale.** Posé à 0,65, il
   valait 4,9 syllabes/seconde ; une narration documentaire courante en fait
   5,8 (mesuré). La pénalité s'appliquait donc à *tous* les plans et rabotait
   tous les mouvements de caméra. Recalé à 0,85 (6,4 syll/s) sur des débits
   réellement mesurés. C'est le cas d'école de la pseudo-métrique : un seuil
   qui frappe le cas courant ne mesure plus rien.

3. **Une incrustation pouvait durer 0,34 s** — illisible. Aucune durée
   minimale de lecture n'était déclarée. `MIN_OVERLAY_SECONDS = 0.8` : mieux
   vaut aucune incrustation qu'une incrustation que personne ne peut lire, et
   qui laisserait croire que l'information a été donnée.

4. **`ShotSpec.camera_program_id` était obligatoire alors que le graphe
   d'étapes attribuait `camera_program` à `MOTION`**, en aval. Incohérence de
   la phase 0, corrigée : le découpage produit les caméras.

5. **Ma fabrique de test donnait la même preuve visuelle à toutes les
   affirmations**, ce qui rendait la propagation invisible — un test de
   propagation qui ne peut rien voir bouger ne prouve rien.

## LIMITATIONS

* **Le modèle d'attention est un modèle.** Personne ici ne regarde le
  spectateur. Ses constantes sont déclarées et ses propriétés testées, mais il
  prédit ; il ne mesure pas. L'observateur déterministe (phase 8) dira ce qui
  a réellement été obtenu.
* **`information_curve` mesure un débit de parole**, pas une charge cognitive.
  Le numérateur est un comptage de syllabes du texte, le dénominateur une
  durée mesurée. C'est réel, c'est étroit, et c'est dit.
* **Aucun mot n'est calé.** Les timings de mots restent non mesurés depuis la
  phase 2 : les incrustations se posent sur le plan, pas sur la syllabe.
* **Le style est un préréglage tant qu'il n'est pas décidé.** Six tables, une
  par ton. C'est un défaut déclaré, pas un parti pris propre à l'épisode.
* **Les fixtures de test à 4 s par réplique sont sur-denses** (jusqu'à 0,97) :
  le système le constate correctement, mais ce n'est pas représentatif d'une
  narration réelle, qui tourne à 0,77.

## REMAINING GAPS

* `RenderSpec`, `StaticValidator`, adaptateurs image et vidéo, exécution du
  mouvement, 2.5D, procédural, observateur, diagnostic, réparation, montage —
  phases 4 et suivantes, rien n'a été commencé.
* `MotionProgram` (source de vérité du mouvement) n'existe qu'au contrat.
  `ShotSpec` porte des `MotionDescriptor`, pas un programme complet.
* Les constats de rythme sont produits mais aucun mécanisme ne les traite :
  le Repair Compiler (phase 9) sera leur destinataire.

## NEXT STEP

Phase 4 — RenderSpec + StaticValidator. **Non commencée**, comme demandé.
