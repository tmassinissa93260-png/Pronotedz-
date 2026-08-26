# Phase 22 — ce que le run #8 a mis à nu

Le run #8 est le premier à avoir tourné avec les huit correctifs de la PR #10.
Il a réussi : 50,08 s, 1501 images, huit plans, `delivered`, 0,0000 USD, treize
points non résolus déclarés. Le mouvement, absent du run #7, était mesurable.

Verdict de son auteur, en trois mots : **« Y a rien qui va. »**

Il avait raison, et le rapport de conformité le disait déjà à sa manière :

> Ce rapport ne dit pas si la vidéo est bonne. Il dit qu'elle est
> techniquement livrable.

Ce document consigne les cinq défauts trouvés en mesurant le fichier livré et
en relisant les traces du run, et ce que chacun a coûté à l'écran.

## Ce qui a été mesuré sur le fichier livré

1501 images extraites, différence absolue moyenne entre images consécutives,
part de pixels quasi noirs (< 0,04), découpe des plans sur les ruptures.

| plan | durée | différence image à image | pixels quasi noirs (moy. / max) |
|------|-------|--------------------------|----------------------------------|
| S00  | 7,3 s | 0,0049                   | 0,8 % / 1,1 %                    |
| S01  | 7,3 s | 0,0057                   | 4,1 % / 4,4 %                    |
| S02  | 6,0 s | 0,0185                   | 4,6 % / 17,9 %                   |
| S03  | 5,0 s | 0,0261                   | **33,1 % / 39,6 %**              |
| S04  | 6,2 s | 0,0064                   | **15,6 % / 17,7 %**              |
| S05  | 4,3 s | 0,0052                   | **11,1 % / 11,4 %**              |
| S06  | 7,0 s | 0,0064                   | 1,8 % / 4,9 %                    |
| S07  | 6,9 s | 0,0075                   | 2,5 % / 4,3 %                    |

Le mouvement est réel — le run #7 plafonnait à 0,0027 — et aucune image n'est
gelée ni noire. Les correctifs de mouvement de la PR #10 tiennent. Le reste ne
tient pas.

## 1. Le sujet de l'épisode n'atteignait pas le fournisseur

`pdz2 prompts` recompile la commande envoyée à fal. Voici celle du calque le
plus lointain de S00, en entier :

> Ouverture dans le registre décidé : technical Cadrage : wide, angle low,
> sujet center. Style : technical — clean high-tech. Lumière : lumière froide,
> néons bleus. Optique : plans rapprochés et macro. Profondeur : profondeur
> moyenne, sujet détaché sans isolement. Matières : aluminium, verre. Texture :
> lisse métallique. **Décor : atelier de fabrication et laboratoire.**
> Graphisme : infographies animées ; motifs récurrents : flux lumineux, lignes
> de champ. Palette : #1A73E8, #FFFFFF, #000000.. Plan sky : fond lointain de
> la scène : Ouverture dans le registre décidé : technical, sans le sujet
> lui-même

L'épisode s'intitule « Comment fonctionne une voiture électrique ? ». Ni
voiture, ni moteur, ni batterie, ni roue. Le seul substantif concret de la
phrase est le décor décidé par la bible visuelle — et le fournisseur l'a rendu
fidèlement : un entrepôt de cartons, un garage vide, un couloir de centre
commercial, un homme de dos dans une embrasure de porte. Quatre plans sur huit.

Ce n'est pas un mauvais fournisseur. C'est une commande qui ne demandait rien.

Deux trous distincts :

* **`ImageSpec` ne portait pas le sujet de l'épisode.** `subject` porte le
  sujet du *plan*, `evidence_required` ce qu'il doit prouver ; aucun champ ne
  portait le domaine. Un plan peut demander « le rotor tourne dans le stator »
  sans que rien ne dise qu'il s'agit d'une voiture. → `image_spec@1.2.0`,
  champ `subject_matter`, posé en tête du prompt.
* **Les plans d'encadrement commandaient une étiquette de style.**
  `_framing_shot_subject` rendait `f"Ouverture dans le registre décidé :
  {register}"` — le *nom* du registre. Cette phrase partait telle quelle,
  recopiée dans les quatre calques. → l'ouverture prend la thèse, la chute
  prend la chute ; les deux sont déjà décidées par le raisonneur et parlent du
  sujet.

## 2. Le procédural s'appliquait aux huit plans

Le journal du run est sans ambiguïté : `routing S00 … S07`, huit fois
« stratégie *procedural* ». La cause est dans `subject_motion_for` : elle rend
`LINEAR` — « déplacement du sujet dans le cadre » — pour tout plan dont
l'énergie dépasse le seuil de verrouillage et qui ne porte pas d'affirmation de
mécanisme. C'est-à-dire presque tous. `_aim_for_subject` voyait une primitive
que `renderers.mechanism` sait dessiner, et relevait.

Une dérive du sujet dans le cadre n'est pas un mécanisme : il n'y a rien à en
dessiner qui soit vrai. → `_MECHANICAL` restreint le relèvement à
`ROTATE, ORBIT, FLOW, OSCILLATE, SPIRAL, ARC`. Un plan en `LINEAR` garde sa
stratégie de caméra et le routeur inscrit la dégradation — elle est réelle.

**Distinction à tenir** : `ANIMATED_PRIMITIVES` déclare ce que le renderer
*sait* dessiner ; `_MECHANICAL` décide *quand c'est justifié*. Un renderer
déclare une capacité, un routeur juge de son emploi. Les confondre est ce qui a
mis des pointes de flux sur un entrepôt de cartons.

## 3. Les indicateurs étaient peints en noir opaque

`_teintes` prenait `palette[2]` pour l'accent et `palette[3]` pour le rappel,
en supposant une palette ordonnée dominante d'abord, accent ensuite. Rien ne
garantit cet ordre. La bible du run #8 rendait `#1A73E8, #FFFFFF, #000000` :
`palette[2]` valait `#000000`, `palette[min(3, 2)]` aussi. **Les deux teintes
étaient du noir**, peintes sur des photographies sombres.

À l'écran, vingt-et-une pointes noires en grille sur le plan large — de la
poussière sur l'objectif — et sept traits noirs sur le rotor — des rayures.

→ La palette est classée par écart de luminance avec le fond **mesuré** sur
l'image (réduction 32×32, coefficients Rec. 709). Un plancher de lisibilité
écarte les couleurs qui ne se détachent pas ; si aucune ne convient, l'annotation
sort de la palette plutôt que de disparaître. Les deux teintes se prennent du
même côté du fond, pour qu'un liseré unique puisse les cerner toutes deux.

Le liseré est tracé en deux passes sur le même calque — l'épaisse d'abord,
puis les teintes par-dessus. `ImageDraw` écrit sans fondre, donc la seconde
passe recouvre le cœur et ne laisse du liseré que la frange. Dilater le canal
alpha aurait donné le même résultat pour 147 ms par image, mesurées, soit 220 s
de plus par épisode.

Le faisceau de flux passe de trois voies écartées de 0,14 sur une portée de
1,8 à deux voies de 0,075 sur 1,25 : un faisceau qui traverse le sujet, plus
une grille sur tout le cadre.

## 4. La rotation du calque ouvrait des coins vides

`_spin` appliquait `Image.rotate` au calque du sujet, d'un angle allant jusqu'à
`120° × énergie` au fil du plan. Deux torts :

1. Ce n'est pas le mécanisme qui tourne, c'est la photographie — la fausse
   animation que `renderers.mechanism` a été écrit pour remplacer, et que son
   propre en-tête nommait déjà comme un défaut pendant qu'elle tournait encore.
2. `rotate` sans `expand` laisse les angles transparents. Sur un cadrage plat,
   `layers_for` ne rend qu'un calque : il n'y a rien dessous, et le vide est le
   noir de la toile. C'est la colonne de droite du tableau — S03, S04, S05 sont
   exactement les trois plans à cadrage plat.

→ Retiré. Le mouvement n'est pas perdu : `draw_mechanism` dessine la rotation
comme un mécanisme, sans toucher aux pixels de l'image ni à ses bords.

## 5. « Électricité qui bouge » n'avait aucun chemin

Le manque était nommé mot pour mot par l'auteur du run : « moteur qui tourne,
électricité qui bouge ». Le moteur avait sa rotation ; le courant n'avait rien,
parce que `subject_motion_for` ne connaissait que deux cas — mécanisme, ou
défaut.

→ Une affirmation de **conséquence** décrit quelque chose qui passe d'un point
à un autre. Elle rend désormais `FLOW`, que `renderers.mechanism` sait déjà
dessiner. `LINEAR` reste le cas par défaut, et reste indessinable.

## Et un défaut de l'outil de diagnostic lui-même

`pdz2 prompts --animation` levait une `AttributeError` au premier plan :
`RenderSpecExecutable.requested` est un `RequestedEcho`, qui ne porte pas
`motion_program_id`. Les programmes de mouvement sont maintenant indexés par
plan.

Plus grave, la commande reconstruisait la phrase du calque à la main au lieu
d'appeler `image_prompt(spec, bible, calque)` — et l'ordre obtenu différait du
réel : le calque arrivait après la palette au lieu de la précéder. Une commande
dont la raison d'être est d'être exacte par construction ne peut pas se
permettre de recompiler autrement que l'adaptateur.

## Ce qui n'est pas corrigé, et se voit toujours

* Les plans d'encadrement ne portent pas d'exigence de preuve, par
  construction : ils ne démontrent rien. Leur sujet est désormais la thèse,
  ce qui est mieux qu'une étiquette, mais reste une phrase abstraite à
  illustrer.
* `renderers.mechanism` dessine des **indicateurs de mouvement**, pas des
  schémas. Il ne sait pas ce qu'est un stator, une bobine, un arbre. Pour un
  vrai schéma anatomique il faudrait un moteur qui comprenne la structure de
  ce qui est démontré ; aucun n'est branché.
* `final_not_black` compte des images entières, pas des régions. Il a déclaré
  0,0 sur un épisode dont un plan avait un tiers du cadre noir. Un contrôle qui
  ne mesure pas ce qu'on croit qu'il mesure est pire qu'une absence de
  contrôle.
* La recherche lit un corpus local : le sujet demandé doit y correspondre.

---

# Deuxième passe — pourquoi il n'y avait toujours pas de voiture

Verdict de l'auteur du run #8, après la première passe de correctifs :
« L'animation elle ne marche pas. Et y a pas de voiture ni rien. »

Les correctifs de la première passe n'avaient pas encore tourné. Mais en les
relisant, un défaut plus grave est apparu, et il ne se serait pas corrigé tout
seul.

## Empiler des images opaques n'est pas composer

`flux`, chez fal, est un moteur texte-vers-image : il rend un PNG **opaque**,
alpha = 255 sur la totalité des pixels. `_composer` empile les calques avec
`paste(image, (0, 0), image)` — le masque étant l'alpha de l'image elle-même.
Avec un alpha plein, **chaque calque remplace intégralement le précédent**. Le
composite est exactement le dernier peint.

Mesuré :

```
sky          alpha min=255
background   alpha min=255
subject      alpha min=255
foreground   alpha min=255
composite final : (190, 20, 30)      ← la couleur du seul foreground
```

Le même défaut a donc frappé deux fois, par ses deux bouts :

| run | tri | dernier peint | ce qu'on voyait |
|-----|-----|---------------|-----------------|
| #7  | descendant | le plus **lointain** | « fond lointain de la scène » |
| #8  | croissant (corrigé) | le plus **proche** | « éléments de premier plan, cadre partiel » |

Corriger le tri était juste et insuffisant. Sur un plan large à quatre
calques, trois images générées sont payées puis jetées, et celle qui survit
est celle dont la commande dit explicitement « **sujet exclu** » ou « cadre
partiel » — précisément la moins susceptible de montrer une voiture.

C'est exactement ce que montre le run #8 : des cartons au premier plan d'un
entrepôt, un anneau de néon dans un couloir de centre commercial, un homme de
dos dans une embrasure de porte. Des avant-plans sans leur scène.

## La correction n'est pas un troisième tri

`LayerSpec.must_be_separable` est une exigence du contrat. Un moteur qui rend
des images opaques ne peut pas la satisfaire — il faut donc qu'il le **dise**,
et que le compilateur en tienne compte, au lieu de lui commander quatre fois
ce qu'il ne sait pas faire.

* `ImageProvider` déclare `supports_alpha_layers`, sans valeur par défaut :
  un adaptateur muet sur la question refait le défaut.
* `FalImageProvider` : `False`, mesuré sur les fichiers du run #8.
  `ProceduralImageRenderer` : `True` — il dessine sur fond transparent, et
  c'est ce qui a caché le défaut pendant tout le développement.
* `layers_for(..., separable=False)` rend **un** calque, décrit comme
  « scène entière, sujet compris — ⟨le sujet⟩ ». Ni « sujet exclu », ni
  « cadre partiel ».
* `ImageSpecCompiler` reçoit la capacité, et la phase 4 l'interroge auprès du
  fournisseur d'images prioritaire.
* `_composer` ne s'appelle plus que sur un moteur qui déclare la transparence.

Effet secondaire : quatre appels d'image par plan large deviennent un. Le
parallaxe 2.5D n'a plus de profondeur à décaler sur ces images, et
`_respect_layers` le constate et le déclare — ce qui est la vérité, et non une
perte.

## Ce qui, honnêtement, n'animera toujours pas

Aucune stratégie locale n'anime le contenu d'une photographie :

| stratégie | ce qu'elle fait | un moteur y tourne-t-il ? |
|-----------|-----------------|---------------------------|
| `still` | rien | non |
| `ken_burns` | recadre une image fixe | non |
| `parallax_2_5d` | fait glisser des calques | non |
| `procedural` | dessine des repères **sur** une image fixe | non |

Seul l'image-vers-vidéo anime réellement ce qui est dans le cadre.
`FalVideoProvider` est écrit, complet, et appelle vraiment
`kling-video/v2.1/standard/image-to-video`. Deux verrous le retiennent :

1. `_GENERATIVE_ABOVE = 0.80` — jamais franchi ; l'énergie observée plafonne à
   0,70.
2. `cost_per_second_usd = None` → le gouverneur refuse pour `UNMEASURED_COST`.
   Et il refuse aussi un tarif seulement `ANNOUNCED` : « une brochure n'est pas
   une mesure ».

Le second n'est pas contournable par du code, et ne doit pas l'être : c'est la
règle « ne jamais dépenser avant validation », posée au cahier des charges.
Pour mesurer un coût il faut l'engager une fois. C'est une décision qui engage
de l'argent, donc elle appartient à celui qui paie, pas au compilateur.
