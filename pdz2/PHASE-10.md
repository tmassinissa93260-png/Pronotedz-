# Phase 10 — Montage, mastering, sous-titres, QA finale, livraison

## LE MP4 EXISTE

```
$ pdz2 deliver --episode ep/
6 plans concaténés sans ré-encodage vidéo
25.308s, 1080×1920, 30.00 i/s, 2028 Kio

  [ok  blocking] final_duration    observé 25.308  attendu 25.308
  [ok  blocking] final_format      observé 0.5625  attendu 0.5625
  [ok  blocking] final_has_audio   observé 1.0     attendu 1.0
  [ok  blocking] final_not_black   observé 0.0     attendu 0.0
  [ok  minor   ] final_loudness    observé -16.14  attendu -14.0
  [ok  major   ] final_true_peak   observé -1.46   attendu -1.5
  [ok  major   ] final_not_frozen  observé 0.004   attendu 0.001

LIVRÉ : ep/final.mp4   25.31s  1080×1920  30 i/s  2028 Kio
```

Vérifié par `ffprobe` : H.264 1080×1920 à 30 i/s, AAC 48 kHz mono, 25,308 s.

## LE MONTAGE N'INVENTE RIEN

Il pose les plans rendus aux instants du découpage, qui dérive lui-même de la
voix mesurée. Il **refuse dès que deux durées divergent** : un rendu qui ne
fait pas la longueur de son créneau, une voix qui ne fait pas la longueur du
découpage. Un montage bâti sur deux vérités temporelles produit un décalage
qu'on ne rattrape plus.

Les plans sont concaténés **sans ré-encodage** quand aucun filtre n'est
demandé — la qualité du rendu arrive intacte au master.

## LE MASTERING MESURE AVANT ET APRÈS

EBU R128 en deux passes : la première mesure, la seconde corrige avec les
valeurs mesurées. Une passe unique corrige à l'aveugle et manque la cible de
plusieurs LU. La mesure finale est **refaite sur le fichier écrit** — on ne
fait pas confiance à ce que le filtre annonce.

Sur l'épisode de référence, la cible de −14 LUFS n'est **pas** atteinte
(−16,14). Le masterer dit pourquoi :

> atteindre −14 LUFS demanderait +8,6 dB, ce qui porterait la crête à
> +5,8 dBTP contre un plafond de −1,5 dBTP. Le plafond de crête est la
> contrainte, pas la normalisation. Réduire l'écart exigerait une compression
> qui change la dynamique — c'est une décision de mixage, pas une correction
> mécanique.

Mesuré : les modes `linear=true` et `linear=false` donnent le même résultat,
et un compresseur en amont ne gagne que 0,5 LU. La contrainte est physique.

## LES SOUS-TITRES SE CALENT SUR LA VOIX MESURÉE

Un carton par portion de segment de `VoiceTimeline`. Les répliques trop
longues sont découpées au **temps proportionnel au nombre de caractères** :
c'est une approximation, et elle est dite. Le calage à la syllabe exigerait
des timings de mots, qui ne sont pas mesurés — un aligneur approximatif
produirait des sous-titres faux avec l'air d'être justes.

## LA QA FINALE DIT CE QU'ELLE NE JUGE PAS

Sept contrôles sur le fichier qui partira. Et, dans chaque rapport :

> Ce rapport ne dit pas si la vidéo est bonne. Il dit qu'elle est
> techniquement livrable. La pertinence de la démonstration, la justesse du
> ton et la qualité des images relèvent d'une revue humaine.

Une loudness hors plage est **mineure**, pas bloquante : la plateforme
corrigera. Une vidéo muette, noire, de mauvais format ou de mauvaise durée est
bloquante.

## TEST RESULTS

```
$ pytest pdz2/tests -q   →  720 passed
```

26 tests pour la phase 10, dont des contre-épreuves sur de vrais fichiers :
master muet, mauvais format, rendu de longueur fausse.

## NEXT STEP

Phase 11 — matrice de capacités et gouverneur de coût.
