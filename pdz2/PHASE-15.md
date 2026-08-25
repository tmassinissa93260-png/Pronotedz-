# Phases 15 à 19 — fermeture des contrats sans consommateur

Ces phases ne viennent pas du cahier des charges. Elles viennent d'un audit
qui posait une seule question à chaque contrat : **qui te relit ?**

## LE MOTIF

Trois contrats étaient produits, validés, persistés — et relus par personne.

| contrat | ce qui le remplaçait |
| --- | --- |
| `RepairPlan` | `repairs/forbidden_strategies.json`, un dict libre |
| `ExecutionPlan` | une politique de reprise codée en dur dans l'aiguilleur |
| `ShotSpec.text_overlay` | rien : aucun pixel n'en portait la trace |
| `ShotSpec.audio_events` | rien : aucune piste n'en portait la trace |

Un contrat qu'on n'a pas le droit de relire n'est pas une frontière, c'est une
trace.

## LE DÉFAUT QUE L'AUDIT A DÉTERRÉ

En cherchant pourquoi aucune incrustation n'apparaissait, j'ai lu le script à
la main : **six répliques identiques sur huit.** Le mécanisme causal du plan
de preuve devient la réplique du plan ; six preuves partageaient le même
mécanisme.

L'épisode partait au rendu, coûtait neuf plans, sortait un MP4 aux contrôles
techniques verts. Rien ne le disait. Le refus est maintenant posé au premier
endroit qui voit le brief, avant toute dépense — et il a fait tomber 22 tests
d'un coup, ce qui mesure l'ampleur du problème.

## CE QUI EST FERMÉ

**Incrustations** — `ShotSpec.text_overlay` traverse désormais
`RenderSpecRequested` (1.1.0), l'écho de divergence, `RenderSpecExecutable`
(1.1.0), le module de graphics, et ressort en `overlay_rendered` mesuré sur
les pixels. Sur l'épisode de référence : incrustation « 90 % » demandée, écart
mesuré 0,0398 pour un seuil de 0,01.

**Conception sonore** — `ShotSpec.audio_events` aboutit à un `AudioDesign` :
chaque repère est placé sur la timeline de l'épisode, une bibliothèque est
interrogée, et l'absence de source est **déclarée**. Aucun son n'est
synthétisé : un bruit fabriqué à la volée serait un son, pas une conception
sonore.

**Durée** — `DurationPolicy` sépare la durée commandée, la durée calibrée
(mesure d'une synthèse réelle), la tolérance et la décision. Le seul levier
est le débit de parole, borné à une bande mesurée.

## CE QUI RESTE INDISPONIBLE, ET POURQUOI

| élément | état | raison |
| --- | --- | --- |
| sujet généré (I2V) | INDISPONIBLE | aucun fournisseur joignable |
| sources sonores | INDISPONIBLE | ni catalogue, ni réseau, ni licence |
| raisonneur | INDISPONIBLE | aucun identifiant |

Dans les trois cas l'architecture est écrite, le port existe, la capacité se
déclare `UNAVAILABLE`, et la chaîne livre sans eux.
