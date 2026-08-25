# Phase 8 — Observateur déterministe

## CURRENT STATE

`pdz2 observe` mesure les rendus réels. Sur l'épisode de référence : 6 plans
observés, 6 conformes, huit mesures chacune avec sa méthode.

## CE QU'IL MESURE

| Mesure | Méthode |
| --- | --- |
| `duration_s`, `frame_count`, `fps` | ffprobe sur le fichier |
| `motion_first_to_last` | différence absolue moyenne première image ↔ dernière |
| `motion_mean_abs_diff` | différence moyenne entre images consécutives |
| `black_frame_ratio` | part d'images de luminance < 0,02 |
| `frozen_frame_ratio` | part de transitions **strictement** identiques |
| `sharpness` | variance du laplacien, moyennée sur huit images |
| `palette_distance` | distance RGB au plus proche voisin de la palette |

Huit contrôles en découlent, chacun avec observé, attendu, tolérance et
gravité. Le verdict découle mécaniquement des contrôles — le contrat
`ObservationReport` le revérifie.

## LE DÉFAUT QUI COMPTE

**Une différence image à image ne voit pas un mouvement lent.** Les quatre
premiers rendus, dont on avait vérifié visuellement la poussée, étaient
déclarés *figés* : le seuil aurait condamné chaque plan légitimement lent, et
la réparation se serait acharnée sur des rendus corrects.

Mesuré :

```
                        image-à-image   première→dernière
poussée lente 4,5 s        0,000091           0,005267
parallaxe 4,3 s            0,000570           0,019822
plan volontairement figé   0,000000           0,000002
```

Le déplacement de bout en bout est 20 à 60 fois plus grand. C'est **lui** la
mesure du « ce plan a-t-il bougé ». La différence image à image reste, mais
pour ce qu'elle sait faire : détecter un gel réel.

`frozen_frame_ratio` a suivi le même sort : il comptait les transitions sous
0,001, ce qui vaut 100 % sur un travelling lent. Il compte désormais les
images **strictement** identiques — 0,000 à 0,023 sur des rendus corrects,
0,970 sur un plan bloqué.

Contre-épreuve exécutée : un plan rendu volontairement fixe alors que son
`MotionProgram` demandait du mouvement échoue bien sur `motion_present` et
`not_frozen`.

## CE QU'IL NE PRÉTEND PAS MESURER

La beauté, la reconnaissance d'un objet, la fidélité au sujet. Ces jugements
demandent un modèle ; sans lui, prétendre les rendre serait une mesure
inventée. Ils reviennent à la revue humaine. Un test vérifie que le module le
dit.

## TEST RESULTS

```
$ pytest pdz2/tests -q   →  675 passed
```

16 tests pour la phase 8, dont trois contre-épreuves sur de vrais fichiers :
plan figé, durée fausse, rendu noir.

## NEXT STEP

Phase 9 — diagnostic et compilateur de réparation.
