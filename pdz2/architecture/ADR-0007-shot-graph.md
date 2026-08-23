# ADR-0007 — Le découpage est une conséquence, pas une décision

**Statut** : accepté — phase 3
**Date** : 2026-08-23

## Contexte

Entre `DirectorState + VoiceTimeline` et `ShotGraph`, il y a une place idéale
pour une deuxième couche de décisions narratives : « le modèle relit le sujet
et propose un découpage ». C'est exactement ce qu'il ne faut pas faire. Le
sujet, la thèse, la chute et ce qui est démontré ont déjà été tranchés une
fois. Le découpage les *organise*.

## Décision

### Le pavage est arithmétique

Un créneau par réplique, du début de sa parole au début de la parole suivante ;
le dernier va jusqu'à la dernière trame. Les créneaux **pavent exactement**
l'audio mesuré — leur somme *est* sa durée, par construction et non par
ajustement. Le contrat `TemporalPlan` le revérifie et refuse tout trou ou
chevauchement au-delà de 2 ms.

Règle de recouvrement, explicite : un fondu se déclare *à l'intérieur* de la
durée d'un plan, il ne déborde jamais sur le créneau voisin. Sinon la somme
des plans cesserait d'égaler la durée de l'audio, et le montage n'aurait plus
de vérité à laquelle se tenir.

Deux écarts, tous deux nommés :

* **Découper** une réplique trop longue est *temporel* : même réplique, même
  affirmation, plusieurs images. Rien de narratif ne change, et c'est fait.
* **Fusionner** deux répliques courtes serait *narratif* : cela supprimerait
  un temps visuel que la réalisation a décidé. Ce n'est donc pas fait. Le
  créneau court est constaté, et la réalisation tranche.

### Cinq courbes, cinq formules écrites

| Courbe | Nature | Règle |
| --- | --- | --- |
| `emotional` | **transportée** | décision du Director, relue à la position mesurée |
| `information` | **mesurée** | syllabes(texte) / durée de parole mesurée / 7,5 |
| `attention` | **modèle déclaré** | décroissance en demi-vie + regain à chaque coupe |
| `motion` | **cible** | fonction narrative + biais de rythme + répétition − lisibilité |
| `visual_novelty` | **demande** | base + même affirmation + mêmes ancres + usure − affirmation neuve |

Trois natures distinctes, jamais confondues. L'`attention` est une hypothèse
chiffrée, pas une mesure — personne ici ne regarde le spectateur. Elle est
nommée comme telle, ses constantes sont déclarées, et elle sera remplaçable le
jour où des données d'audience existeront.

Les seuils sont posés sur du **débit réellement mesuré**, pas choisis à vue :

```
narration documentaire courante     5,7 – 6,0 syll/s   → 0,76 – 0,80
seuil de pénalité de lisibilité     6,4 syll/s         → 0,85
seuil de saturation constatée       7,0 syll/s         → 0,93
```

Le seuil de lisibilité valait d'abord 0,65 — soit 4,9 syll/s. Il se déclenchait
donc sur une narration parfaitement normale et rabotait *tous* les mouvements
de caméra sans que rien ne le signale. Un seuil qui frappe le cas courant ne
mesure plus rien : il déguise une constante en règle.

### Le lien avec l'affirmation est dans les données

```
Claim.id → VisualEvidencePlan.claim_id → ShotSpec.claim_id
                                      → ShotSpec.evidence_required
                                      → ShotSpec.visual_subject
```

`ShotGraph.shots_for_claim()` remonte le lien. Un plan démonstratif dont
l'affirmation n'a pas de preuve visuelle rédigée est **refusé** ; une
affirmation de la chaîne causale sans aucun plan l'est aussi. Le compilateur
recopie la preuve rédigée mot pour mot : un test le vérifie sur chaque plan.

### La bible sépare le décidé du dérivé

* **Décidé** — style, lumière, palette, optique, matières, texture, décor,
  graphisme. Aucun calcul ne les produit. Ils viennent de
  `DirectorBrief.visual_style`, ou d'un **préréglage déclaré** choisi sur le
  ton — et le compilateur écrit alors noir sur blanc que le style a été
  *défaut*, pas *décidé*.
* **Dérivé** — densité visuelle depuis la densité d'information, interdits
  depuis l'imagerie proscrite, langage caméra et profondeur de champ depuis le
  rythme, longueur de ligne depuis la densité.

Un préréglage est une table publiée, pas une génération : deux appels rendent
le même objet. Rien n'est fabriqué à l'exécution.

### L'échantillonnage et la lecture doivent tomber au même endroit

Les courbes sont échantillonnées au milieu de chaque créneau. Relire une
courbe à cette position doit rendre **exactement** la valeur stockée. Sans
cette égalité, à 10⁻⁷ près une cible de mouvement de 0,30 se lit 0,2999998, et
la caméra se verrouille en silence. Une seule fonction,
`temporal.sample_position`, sert aux deux — c'est ce qui garantit qu'elles
coïncident.

## Alternatives écartées

* **Un modèle qui propose le découpage.** Rejeté : ce serait une seconde
  couche de décisions narratives, exactement ce que la phase interdit.
* **Fusionner les répliques trop courtes.** Rejeté : décision narrative prise
  en silence par un compilateur.
* **Faire déborder les fondus sur les plans voisins.** Rejeté : la somme des
  plans doit rester égale à la durée de l'audio mesuré.
* **Un `MotionProgram` complet dès cette phase.** Rejeté : `ShotSpec` a besoin
  d'un cadrage et d'une caméra, pas de la source de vérité du mouvement, qui
  relève de la phase 6.

## Conséquences

* `SHOT_GRAPH` produit désormais les programmes caméra : un plan ne peut pas
  exister sans caméra, et `ShotSpec.camera_program_id` est obligatoire. La
  phase 6 reprendra ces programmes et en fera la source de vérité du mouvement.
* `DirectorBrief` passe en 1.1.0 avec un `visual_style` facultatif. Les briefs
  1.0.0 restent lisibles et retombent sur le préréglage.
* Les timings de mots restant non mesurés (phase 2), aucun événement visuel
  n'est calé sur un mot précis. Les incrustations se posent sur le plan, pas
  sur la syllabe.
