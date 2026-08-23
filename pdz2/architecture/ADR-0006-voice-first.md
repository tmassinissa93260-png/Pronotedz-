# ADR-0006 — La durée officielle sort d'un fichier, pas d'un texte

**Statut** : accepté — phase 2
**Date** : 2026-08-23

## Contexte

Le §7 pose la règle qui commande toute la suite du compilateur :

```
TTS réel → audio réel → durée réelle → découpage temporel
```

`estimated_duration_s` existe au contrat, désigné comme estimation. Le risque
n'est pas qu'on décide un jour de s'en servir comme autorité : c'est qu'on le
fasse **par accident**, un après-midi, parce que la valeur était à portée de
main et que le TTS n'avait pas encore tourné. Une fois ce glissement fait, il
est invisible : les durées ont l'air justes, et la vidéo tombe à côté.

## Décision

### Une frontière que le code ne peut pas franchir

`pdz2/audio/` ne connaît pas `estimated_duration_s`. Ce n'est pas une
convention : `VoiceTimelineBuilder.build()` prend une liste de `MeasuredLine`,
et `MeasuredLine` **n'a pas de champ de durée** — seulement une
`AudioMeasurement` issue de `measure_wav`, c'est-à-dire du décompte des trames
d'un fichier. Il n'existe aucune signature par laquelle une estimation entre.

Deux tests d'architecture ferment la porte restante :

* aucun module de `pdz2/audio/` ne lit `estimated_duration_s` — vérifié sur
  l'arbre syntaxique, pas sur le texte : la prose a le droit de nommer le
  champ pour expliquer qu'elle l'ignore, le code n'a pas le droit d'y toucher,
  ni par attribut ni par `getattr` ;
* aucun module de `pdz2/audio/` n'importe `pdz2.engines.script`.

### Un fichier par réplique

Chaque réplique est synthétisée dans son propre WAV, puis mesurée. Les bornes
de segment sont donc des **sommes de durées mesurées**, jamais la répartition
au prorata d'un total. Les silences inter-répliques sont *écrits*, donc exacts
au nombre d'échantillons près.

L'assemblage final est ensuite **re-mesuré** et confronté à la somme attendue.
Un écart au-delà de deux millisecondes est une `DurationInconsistent` — pas un
arrondi qu'on absorbe.

### Le port ne rend jamais une durée

`SpeechSynthesiser.synthesise()` rend un **chemin**. La durée est lue ensuite,
sur le fichier, par un module qui ne sait pas quel texte l'a produit. Un
moteur ne peut donc pas « annoncer » une durée qui deviendrait officielle.

### eSpeak NG, et pourquoi

eSpeak NG n'est pas une voix de production, et cela s'entend. Il est là pour
quatre propriétés qui comptent davantage à ce stade : **réel**, **hors-ligne**,
**reproductible au bit près**, **débit réglable**. Cette dernière est ce qui
permet de vérifier la règle pour de bon plutôt que d'en parler :

| script | réglage moteur | durée estimée | durée officielle |
| --- | --- | --- | --- |
| identique | 165 mots/min | 19,44 s | **25,31 s** |
| identique | 110 mots/min | 19,44 s | **37,86 s** |

Un moteur de meilleure qualité s'ajoutera derrière le même port sans qu'une
ligne bouge en aval : la durée continuera de sortir de la mesure du fichier.

### Ce qui est refusé, et journalisé

| Situation | Exception | Conséquence |
| --- | --- | --- |
| moteur absent | `SynthesiserUnavailable` | étape `voice` en `failed`, motif écrit |
| moteur en erreur ou en dépassement | `SynthesisFailed` | idem |
| WAV illisible, tronqué, sans trame | `AudioCorrupt` | idem |
| WAV lisible mais muet | `AudioSilent` | idem |
| format changé en cours de script | `AudioFormatMismatch` | étape `timeline` en `failed` |
| assemblage qui ne retombe pas juste | `DurationInconsistent` | idem |
| fichier modifié depuis la synthèse | `DurationInconsistent` | idem |

Un WAV muet est le cas qui compte le plus : un moteur qui échoue à mi-parcours
rend souvent un fichier parfaitement lisible et parfaitement vide. Sans le
plancher d'énergie, sa durée deviendrait officielle et personne ne le saurait
avant le montage.

### Le script est une compilation, pas une décision

`ScriptState` sort de `DirectorState` sans un appel de modèle. Chaque mot
prononcé remonte à quelque chose que la réalisation a déjà tranché : la thèse
pour l'ouverture, le mécanisme causal rédigé pour un plan démonstratif, la
chute pour la fin. Un test vérifie que **tout** texte de réplique appartient à
cet ensemble — rien n'apparaît au moment de la compilation.

Le compilateur refuse plutôt que de combler : un plan démonstratif dont
l'affirmation n'a pas de mécanisme rédigé ne produit pas de réplique. Réciter
la citation brute d'une source n'est pas une narration.

## Alternatives écartées

* **Un seul WAV segmenté par détection d'énergie.** Rejeté : un aligneur se
  trompe, et ses erreurs se propagent dans toutes les durées officielles. Un
  fichier par réplique donne des bornes exactes par construction.
* **Faire confiance à la durée enregistrée à la synthèse.** Rejeté : `timeline`
  re-mesure les fichiers. Si l'un a bougé, la timeline suit le fichier, pas le
  souvenir qu'on en avait.
* **Une deuxième timeline audio.** Rejeté : `VoiceTimeline` existe depuis la
  phase 0 et suffit. Rien n'a été ajouté à côté.

## Conséquences

* **Dépendance système** : le binaire `espeak-ng`. Absent, l'adaptateur se
  déclare `UNAVAILABLE` avec la raison, l'étape échoue avec un motif, et les
  tests qui en dépendent se déclarent ignorés plutôt que de faire semblant.
* Les timings de **mots** ne sont pas mesurés : `VoiceSegment.words` reste
  vide. eSpeak NG ne rend pas de marques de mot exploitables, et un aligneur
  approximatif produirait des sous-titres faux avec l'air d'être justes. À
  traiter en phase 10, avec un moteur qui les fournit ou un aligneur mesuré.
