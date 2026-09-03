# Comment on vole une voiture récente sans casser une vitre

74.5 secondes · 20 plans

## Script

Ta voiture peut être volée en trente secondes. Sans casser une vitre, sans toucher à la serrure. Bienvenue dans le monde du hacking automobile. Première technique : l'attaque par relais. Les voleurs ne touchent plus à la serrure. Un complice capte le signal de ta clé à travers ta porte d'entrée. Le complice le retransmet à un second boîtier posé contre ta voiture. La voiture croit que tu es à côté, et se déverrouille. Plus lourd encore : le bus CAN. C'est le réseau interne où tous les composants de ta voiture se parlent. Des pirates arrivent à se brancher sur ce réseau interne. Les pirates injectent leurs propres trames sur ce câble. Le calculateur les lit, croit reconnaître la vraie clé, et ouvre. Même tes pneus sont vulnérables. Des capteurs radio non chiffrés envoient la pression de chaque roue. Un pirate copie leur signal et annonce une crevaison qui n'existe pas. Le tableau de bord alerte, et le conducteur s'arrête sur la bande d'arrêt. Ce même bus CAN sert aussi à reprendre le contrôle. Un boîtier à 900 euros et OpenPilot y branchent une conduite autonome. Abonne-toi pour la partie 2.

## Visual bible

À réutiliser dans **chaque** image. Les couleurs ont un sens fixe.

- **main subject** : a modern dark near-black car on a Parisian street at night, and two featureless white mannequins acting on it
- **characters objects** : mannequin 1 in a fitted dark black polo shirt, mannequin 2 in a heather grey pullover hoodie, both featureless and smooth matte white
- **vehicle** : modern dark near-black car, realistic proportions, unchanged in every shot
- **colors** : blue for the legitimate radio and data frames, red for what the attacker adds, green for the control given back to the driver, grey for the mechanical parts
- **environment** : Parisian street and courtyard at night, wet cobblestone, neon signs, dark car interior
- **materials** : matte white plastic skin, black cotton polo, grey brushed cotton hoodie, matte near-black paint, brushed aluminium, braided grey sheath, tinted glass
- **lighting** : warm street lamps and sodium light, cold neon and LED, deep shadows, high contrast
- **camera** : static views, 35mm lens at f/1.8, shallow depth of field, realistic bokeh
- **style 3d** : photorealistic editorial photography, physically accurate
- **realism** : photorealistic, no stylisation
- **invisible phenomena** : radio and data frames shown as discrete luminous pulses travelling along their real physical path

## Code couleur

Une notion, une couleur, la même du début à la fin.

- **blue** = signal — the legitimate radio and data frames the car's own parts exchange  *(se déplace)*
- **red** = intrusion — everything added from outside the car — the relay link, the injected frames, the second sensor reading  *(se déplace)*
- **green** = controle — the commands the driver puts back on the same bus on purpose  *(se déplace)*
- **grey** = mecanique — the bodywork, the lock, the wheels and the structure

## Contrôle qualité

- narrative quality : 0.92
- visual quality : 0.91
- scientific accuracy : 0.92
- voice visual alignment : 0.94
- visual continuity : 0.93
- pedagogical clarity : 0.92
- animation potential : 0.94

---

## Plan 01 — 3s

**Voix** : Ta voiture peut être volée en trente secondes.

**Fonction** : Montre le résultat avant la cause : la voiture s'ouvre sans personne.

**Élément pédagogique** : red pulses reaching the mirror housing, the repeater lighting and the mirror opening

**Intention de mouvement** : `cause_effect`

### Le raisonnement, avant le prompt

1. **information** : la voiture s'ouvre sans que personne ne la touche
2. **physical element** : the folded wing mirror and its indicator repeater
3. **secondary elements** : la poignée, la carrosserie, la rue mouillée derrière
4. **visual behavior** : des impulsions rouges longent la carrosserie et atteignent le rétroviseur
5. **animation movement** : les impulsions rouges parcourent le flanc jusqu'au rétroviseur, le répétiteur s'allume et le rétroviseur se déplie
6. **camera position** : macro statique à hauteur de rétroviseur, faible profondeur de champ
7. **composition** : le rétroviseur sur la moitié gauche, la poignée en bas à droite

### Prompt image

```
Macro shot of the driver's door mirror and the top of the door handle of a modern dark near-black car parked on a Parisian street at night, nobody within reach of it. Position: the folded wing mirror fills the left half of the frame with its indicator repeater along the lower edge of the housing, the handle running across the lower right, the wet street behind. Red luminous pulses travel along the flank of the car and reach the mirror housing, clearly representing a command arriving from outside. Camera: static macro at mirror height, shallow depth of field so the repeater is sharp and the street falls into bokeh. Lighting: warm street lamp raking along the paint from above left, cold neon rim on the upper edge of the mirror, deep shadow beneath the housing. Materials: matte near-black paint, gloss black mirror cap, chrome handle, tinted glass. Aesthetic photorealistic 9:16 vertical frame with featureless smooth matte white blank mannequins, no facial features — mannequin 1 in a fitted dark black polo shirt, mannequin 2 in a heather grey pullover hoodie with drawstrings; moody dark cinematic night atmosphere with deep shadows, warm ambient light from street lamps, neon signs and subtle glowing tech LEDs, cinematic Parisian street setting with modern cars and dark interiors; shot on a 35mm lens at f/1.8 with shallow depth of field and realistic bokeh, high-end streetwear editorial photography, hyper-detailed fabric texture, realistic plastic skin shading, 8k, no text, no labels, no logos, no watermark.
```

### Prompt animation

```
The red pulses travel steadily along the flank and reach the mirror housing, and as the last of them arrives the indicator repeater lights up once and the folded mirror rotates outward until it stands fully open. The paint, the handle and the street stay perfectly rigid. The camera holds still. Preserve exact geometry, proportions and materials. No deformation, no floating parts.
```

---

## Plan 02 — 3.5s

**Voix** : Sans casser une vitre, sans toucher à la serrure.

**Fonction** : Montre que rien n'est forcé : le signal traverse la carrosserie.

**Élément pédagogique** : blue pulses passing through the intact glass and the untouched barrel answering

**Intention de mouvement** : `energy_flow`

### Le raisonnement, avant le prompt

1. **information** : rien n'est forcé, le signal traverse la carrosserie
2. **physical element** : the driver's window glass and the lock barrel
3. **secondary elements** : le joint de caoutchouc, le reflet de la rue
4. **visual behavior** : des impulsions bleues traversent la vitre sans la déformer
5. **animation movement** : les impulsions bleues parcourent la vitre de droite à gauche et le barillet s'allume à leur passage
6. **camera position** : macro statique à hauteur de vitre, faible profondeur de champ
7. **composition** : le barillet en bas à gauche, la vitre sur les deux tiers droits

### Prompt image

```
Macro shot of the untouched driver's window glass and the lock barrel below it on the same dark near-black car, the metal unmarked, no tool anywhere in frame. Position: the barrel sits at the lower left, the pane of glass rising across the right two thirds, the rubber seal running between them. Blue luminous pulses pass straight through the glass from right to left without bending it, clearly representing a radio signal the bodywork cannot stop. Camera: static macro at window height, shallow depth of field so the seal is sharp and the reflected street falls into bokeh. Lighting: warm street lamp from above right, cold neon reflection sliding across the pane, deep shadow at the seal. Materials: tinted glass, black rubber seal, brushed steel barrel, matte near-black paint. Aesthetic photorealistic 9:16 vertical frame with featureless smooth matte white blank mannequins, no facial features — mannequin 1 in a fitted dark black polo shirt, mannequin 2 in a heather grey pullover hoodie with drawstrings; moody dark cinematic night atmosphere with deep shadows, warm ambient light from street lamps, neon signs and subtle glowing tech LEDs, cinematic Parisian street setting with modern cars and dark interiors; shot on a 35mm lens at f/1.8 with shallow depth of field and realistic bokeh, high-end streetwear editorial photography, hyper-detailed fabric texture, realistic plastic skin shading, 8k, no text, no labels, no logos, no watermark.
```

### Prompt animation

```
The blue pulses travel steadily through the glass from right to left, and as each one crosses the seal the barrel below brightens faintly in answer, building over the shot into a rhythm the untouched metal keeps repeating. The glass, the seal and the barrel stay perfectly rigid. The camera holds still with a slow secondary drift. Preserve exact geometry, proportions and materials. No deformation, no floating parts.
```

---

## Plan 03 — 3s

**Voix** : Bienvenue dans le monde du hacking automobile.

**Fonction** : Nomme le sujet : quelqu'un agit sur la voiture à distance.

**Élément pédagogique** : a red glow travelling from the hacker's box across the street onto the car

**Intention de mouvement** : `energy_transfer`

### Le raisonnement, avant le prompt

1. **information** : quelqu'un agit sur la voiture sans la toucher
2. **physical element** : the small flat black box in the mannequin's hand
3. **secondary elements** : le mannequin en polo noir, la voiture au trottoir, l'enseigne néon
4. **visual behavior** : une lueur rouge quitte le boîtier et gagne la carrosserie
5. **animation movement** : la lueur rouge se propage du boîtier jusqu'à la voiture, puis la poignée s'allume
6. **camera position** : large statique à hauteur de poitrine, faible profondeur de champ
7. **composition** : le mannequin à gauche, la voiture à droite, la rue mouillée entre

### Prompt image

```
Wide night shot of a Parisian street, the same dark near-black car parked at the kerb at frame right and mannequin 1, a featureless smooth matte white figure in a fitted dark black polo shirt, standing at frame left with a small flat black box in one hand. Position: eight metres of wet cobblestone between the figure and the car, a neon sign glowing above the shopfront behind them both. A red luminous glow spreads outward from the box across the car's flank and settles along its panel seams, clearly representing the radio command reaching the vehicle. Camera: static wide view at chest height, shallow depth of field so the figure is sharp and the far end of the street falls into bokeh. Lighting: warm street lamp from above left, cold neon wash from the shopfront, deep shadow between them. Materials: matte white plastic skin, black cotton polo fabric, wet cobblestone, matte near-black paint, chrome trim. Aesthetic photorealistic 9:16 vertical frame with featureless smooth matte white blank mannequins, no facial features — mannequin 1 in a fitted dark black polo shirt, mannequin 2 in a heather grey pullover hoodie with drawstrings; moody dark cinematic night atmosphere with deep shadows, warm ambient light from street lamps, neon signs and subtle glowing tech LEDs, cinematic Parisian street setting with modern cars and dark interiors; shot on a 35mm lens at f/1.8 with shallow depth of field and realistic bokeh, high-end streetwear editorial photography, hyper-detailed fabric texture, realistic plastic skin shading, 8k, no text, no labels, no logos, no watermark.
```

### Prompt animation

```
The red glow spreads outward from the box, gradually travelling across the wet cobblestone and up the car's flank, until it settles along the panel seams and the door handle lights up in answer. The figure, the box and the car stay perfectly rigid. The camera holds still. Preserve exact geometry, proportions and materials. No deformation, no floating parts.
```

---

## Plan 04 — 2.5s

**Voix** : Première technique : l'attaque par relais.

**Fonction** : Pose le dispositif : deux boîtiers, une ligne entre la porte et la voiture.

**Élément pédagogique** : a red beam opening between the two boxes held by the two mannequins

**Intention de mouvement** : `energy_transfer`

### Le raisonnement, avant le prompt

1. **information** : l'attaque tient en deux boîtiers reliés entre eux
2. **physical element** : the red beam running between the two boxes
3. **secondary elements** : les deux mannequins, la porte de l'immeuble, la voiture
4. **visual behavior** : un faisceau rouge s'ouvre entre les deux boîtiers
5. **animation movement** : le faisceau rouge s'allume sur toute sa longueur et les LED des deux boîtiers se mettent à battre ensemble
6. **camera position** : large statique à hauteur de poitrine, faible profondeur de champ
7. **composition** : un mannequin à chaque bord du cadre, le faisceau en travers

### Prompt image

```
Wide night shot of a Parisian courtyard, the front door of a building at frame left and the dark near-black car parked at frame right. Position: mannequin 2, a featureless smooth matte white figure in a heather grey pullover hoodie with drawstrings, holds a flat black box against the door at chest height; mannequin 1 in the fitted dark black polo shirt holds an identical box against the car's driver door, eight metres away at the same height. A red luminous beam opens between the two boxes across the wet cobblestone, clearly representing the added link between them. Camera: static wide view at chest height, shallow depth of field so both figures are sharp and the courtyard gate falls into bokeh. Lighting: warm street lamp from above left, cold LED glow from each box, deep shadow across the ground. Materials: matte white plastic skin, grey brushed-cotton hoodie, black cotton polo, matte black plastic housings, wet cobblestone. Aesthetic photorealistic 9:16 vertical frame with featureless smooth matte white blank mannequins, no facial features — mannequin 1 in a fitted dark black polo shirt, mannequin 2 in a heather grey pullover hoodie with drawstrings; moody dark cinematic night atmosphere with deep shadows, warm ambient light from street lamps, neon signs and subtle glowing tech LEDs, cinematic Parisian street setting with modern cars and dark interiors; shot on a 35mm lens at f/1.8 with shallow depth of field and realistic bokeh, high-end streetwear editorial photography, hyper-detailed fabric texture, realistic plastic skin shading, 8k, no text, no labels, no logos, no watermark.
```

### Prompt animation

```
The red beam opens between the two boxes and steadily brightens along its whole length, and as it reaches full strength the LED on each housing begins to pulse in time with the other. The two figures, the boxes and the car stay perfectly rigid. The camera holds still. Preserve exact geometry, proportions and materials. No deformation, no floating parts.
```

---

## Plan 05 — 3s

**Voix** : Les voleurs ne touchent plus à la serrure.

**Fonction** : Montre que la serrure n'est jamais touchée : l'attaque est ailleurs.

**Élément pédagogique** : blue pulses crossing the air gap while the untouched lock barrel stays still

**Intention de mouvement** : `energy_flow`

### Le raisonnement, avant le prompt

1. **information** : aucun outil ne touche la serrure, elle reste intacte
2. **physical element** : the lock barrel of the driver's door
3. **secondary elements** : la main du mannequin, le boîtier noir, la poignée
4. **visual behavior** : des impulsions bleues traversent l'air puis la poignée
5. **animation movement** : les impulsions bleues parcourent la poignée de gauche à droite pendant que le barillet reste immobile
6. **camera position** : macro statique à hauteur de poignée, faible profondeur de champ
7. **composition** : le barillet en bas au centre, la main et le boîtier à gauche

### Prompt image

```
Macro shot of the driver's door handle and lock barrel of the dark near-black car, the gloved white plastic hand of mannequin 1 holding its flat black box a few centimetres from the panel without contact. Position: the barrel fills the lower centre of the frame, the hand and the box enter from frame left, a visible gap of air between the box and the paint. Blue luminous pulses cross that gap and pass through the handle from left to right, clearly representing the signal the car is listening for. Camera: static macro at handle height, shallow depth of field so the barrel is sharp and the hoodie behind falls into bokeh. Lighting: hard cold neon key raking along the metal, warm street lamp rim on the upper edge of the handle, deep shadow inside the barrel. Materials: matte white plastic skin, matte black plastic housing, brushed steel barrel, matte near-black paint, chrome handle. Aesthetic photorealistic 9:16 vertical frame with featureless smooth matte white blank mannequins, no facial features — mannequin 1 in a fitted dark black polo shirt, mannequin 2 in a heather grey pullover hoodie with drawstrings; moody dark cinematic night atmosphere with deep shadows, warm ambient light from street lamps, neon signs and subtle glowing tech LEDs, cinematic Parisian street setting with modern cars and dark interiors; shot on a 35mm lens at f/1.8 with shallow depth of field and realistic bokeh, high-end streetwear editorial photography, hyper-detailed fabric texture, realistic plastic skin shading, 8k, no text, no labels, no logos, no watermark.
```

### Prompt animation

```
The blue pulses cross the gap and travel steadily through the handle from left to right, and as each one passes the lock barrel the barrel stays perfectly still and unmoved, building over the shot into a rhythm the untouched metal never resists. The hand, the box and the barrel stay perfectly rigid. The camera holds still with a slow secondary drift. Preserve exact geometry, proportions and materials. No deformation, no floating parts.
```

---

## Plan 06 — 4.5s

**Voix** : Un complice capte le signal de ta clé à travers ta porte d'entrée.

**Fonction** : Montre le premier maillon : le signal de la clé est capté à travers la porte.

**Élément pédagogique** : blue key pulses crossing the wood into the box antenna, red glow building on it

**Intention de mouvement** : `energy_transfer`

### Le raisonnement, avant le prompt

1. **information** : le signal de la clé traverse la porte et se fait capter
2. **physical element** : the flat black box pressed against the front door
3. **secondary elements** : la clé au crochet, le panneau vitré, le bois peint
4. **visual behavior** : les impulsions bleues traversent le bois et entrent dans l'antenne, et le boîtier rougit
5. **animation movement** : les impulsions bleues traversent le bois et gagnent l'antenne, et la lueur rouge du boîtier monte à chaque impulsion reçue
6. **camera position** : moyen statique à hauteur de poitrine, foyer sur le boîtier
7. **composition** : le boîtier au centre, la clé visible derrière la vitre au-dessus

### Prompt image

```
Medium night shot of the building's front door from outside, mannequin 2 in the heather grey hoodie pressing a flat black box against the painted wood at chest height. Position: the car key hangs on its hook inside, framed through the glazed panel just above the box; the box's antenna face is pressed flat to the door, thirty centimetres from the key. Blue luminous pulses leave the key, cross the wood, and are drawn into the antenna face, clearly representing the key's own signal being picked up; a red luminous glow spreads across the housing itself. Camera: static medium view at chest height, shallow depth of field so the box is sharp and the courtyard behind falls into bokeh. Lighting: warm hallway glow behind the glazed panel, cold street lamp from above left, deep shadow on the wood. Materials: painted wood, glass, matte black plastic housing, brass key, matte white plastic skin, grey brushed-cotton hoodie. Aesthetic photorealistic 9:16 vertical frame with featureless smooth matte white blank mannequins, no facial features — mannequin 1 in a fitted dark black polo shirt, mannequin 2 in a heather grey pullover hoodie with drawstrings; moody dark cinematic night atmosphere with deep shadows, warm ambient light from street lamps, neon signs and subtle glowing tech LEDs, cinematic Parisian street setting with modern cars and dark interiors; shot on a 35mm lens at f/1.8 with shallow depth of field and realistic bokeh, high-end streetwear editorial photography, hyper-detailed fabric texture, realistic plastic skin shading, 8k, no text, no labels, no logos, no watermark.
```

### Prompt animation

```
The blue pulses leave the key, cross the wood one after another, and are drawn into the antenna face, and as each pulse enters the housing the red glow across it steadily builds until the whole box is lit. The door, the key and the figure stay perfectly rigid. The camera holds still. Preserve exact geometry, proportions and materials. No deformation, no floating parts.
```

---

## Plan 07 — 4.5s

**Voix** : Le complice le retransmet à un second boîtier posé contre ta voiture.

**Fonction** : Montre le deuxième maillon : le signal est reporté intact jusqu'à la voiture.

**Élément pédagogique** : blue pulses relayed along the red beam between the two boxes into the handle

**Intention de mouvement** : `energy_flow`

### Le raisonnement, avant le prompt

1. **information** : le signal capté est reporté tel quel jusqu'à la voiture
2. **physical element** : the red beam running between the two boxes
3. **secondary elements** : les deux boîtiers, les deux mannequins, la poignée
4. **visual behavior** : des impulsions bleues défilent le long du faisceau rouge et ressortent inchangées
5. **animation movement** : les impulsions bleues parcourent le faisceau rouge de gauche à droite et rejoignent la poignée
6. **camera position** : large statique à hauteur de poitrine, faible profondeur de champ
7. **composition** : un boîtier à chaque bord du cadre, le faisceau en travers

### Prompt image

```
Wide night shot of the same courtyard, the first flat black box against the building door at frame left and the second identical box held against the driver's door of the dark near-black car at frame right. Position: the two boxes face each other across eight metres of wet cobblestone at the same chest height, a mannequin standing beside each. A red luminous beam runs between them carrying blue pulses along its length from left to right, clearly representing the key's own signal being relayed across the gap; the blue pulses leave the second box and enter the door handle unchanged. Camera: static wide view at chest height, shallow depth of field so both boxes are sharp and the gate falls into bokeh. Lighting: warm street lamp from above left, cold LED glow from each housing, deep shadow across the ground. Materials: matte black plastic housings, wet cobblestone, matte near-black paint, chrome handle, matte white plastic skin. Aesthetic photorealistic 9:16 vertical frame with featureless smooth matte white blank mannequins, no facial features — mannequin 1 in a fitted dark black polo shirt, mannequin 2 in a heather grey pullover hoodie with drawstrings; moody dark cinematic night atmosphere with deep shadows, warm ambient light from street lamps, neon signs and subtle glowing tech LEDs, cinematic Parisian street setting with modern cars and dark interiors; shot on a 35mm lens at f/1.8 with shallow depth of field and realistic bokeh, high-end streetwear editorial photography, hyper-detailed fabric texture, realistic plastic skin shading, 8k, no text, no labels, no logos, no watermark.
```

### Prompt animation

```
The blue pulses begin to travel along the red beam from left to right, gradually building in rhythm, until they leave the second box and enter the door handle unchanged, which lights up in answer. The boxes, the two figures and the car stay perfectly rigid. The camera holds still. Preserve exact geometry, proportions and materials. No deformation, no floating parts.
```

---

## Plan 08 — 4.5s

**Voix** : La voiture croit que tu es à côté, et se déverrouille.

**Fonction** : Montre l'effet : la voiture reçoit le vrai signal et s'ouvre.

**Élément pédagogique** : blue pulses entering the handle, the repeater lighting and the mirror opening

**Intention de mouvement** : `cause_effect`

### Le raisonnement, avant le prompt

1. **information** : la voiture accepte le signal et s'ouvre
2. **physical element** : the folded wing mirror and its indicator repeater
3. **secondary elements** : la poignée, le boîtier resté contre la tôle, la cour
4. **visual behavior** : des impulsions bleues entrent dans la poignée puis le répétiteur s'allume
5. **animation movement** : les impulsions bleues parcourent la tôle jusqu'à la poignée, le répétiteur s'allume et le rétroviseur se déplie
6. **camera position** : moyen statique à hauteur de poignée, faible profondeur de champ
7. **composition** : la poignée au centre, le rétroviseur en haut à droite

### Prompt image

```
Medium night shot of the driver's door of the dark near-black car, the second flat black box held flat against the panel at frame left. Position: the door handle runs across the centre of the frame, the folded wing mirror sits above it at frame right with its indicator repeater along the lower edge of the housing, the courtyard behind. Blue luminous pulses leave the box and travel along the panel into the handle, clearly representing the signal the car accepts as its own. Camera: static medium view at handle height, shallow depth of field so the handle is sharp and the courtyard falls into bokeh. Lighting: warm street lamp raking along the paint from above left, cold LED rim from the housing, deep shadow beneath the sill. Materials: matte near-black paint, matte black plastic housing, chrome handle, gloss black mirror cap, tinted glass. Aesthetic photorealistic 9:16 vertical frame with featureless smooth matte white blank mannequins, no facial features — mannequin 1 in a fitted dark black polo shirt, mannequin 2 in a heather grey pullover hoodie with drawstrings; moody dark cinematic night atmosphere with deep shadows, warm ambient light from street lamps, neon signs and subtle glowing tech LEDs, cinematic Parisian street setting with modern cars and dark interiors; shot on a 35mm lens at f/1.8 with shallow depth of field and realistic bokeh, high-end streetwear editorial photography, hyper-detailed fabric texture, realistic plastic skin shading, 8k, no text, no labels, no logos, no watermark.
```

### Prompt animation

```
The blue pulses leave the box and travel steadily along the panel into the handle, and as the last of them arrives the indicator repeater lights up once and the folded mirror rotates outward until it stands fully open. The box, the panel and the glass stay perfectly rigid. The camera holds still. Preserve exact geometry, proportions and materials. No deformation, no floating parts.
```

---

## Plan 09 — 2.5s

**Voix** : Plus lourd encore : le bus CAN.

**Fonction** : Nomme l'objet dont parle la suite : le câble partagé qui relie tout.

**Élément pédagogique** : blue data pulses igniting along the CAN twisted pair toward the control unit

**Intention de mouvement** : `energy_flow`

### Le raisonnement, avant le prompt

1. **information** : un seul câble relie tous les composants de la voiture
2. **physical element** : the twisted pair of the CAN bus inside the loom
3. **secondary elements** : le phare, le faisceau tressé, le boîtier du calculateur
4. **visual behavior** : des impulsions bleues s'allument l'une après l'autre le long de la paire
5. **animation movement** : les impulsions bleues s'allument depuis le phare et se propagent vers le calculateur, dont les broches s'allument à leur tour
6. **camera position** : trois-quarts statique à hauteur de phare, foyer profond
7. **composition** : le phare à gauche, le calculateur à droite, le faisceau entre

### Prompt image

```
Medium technical semi-cutaway of the front left quarter of the dark near-black car at night, the wing panel ghosted to transparency so the wiring loom beneath it comes into view. Position: the braided loom runs from the headlight housing at frame left, back along the inner wing, to the engine control unit box at frame right; a single twisted pair inside the loom is separated out and reads clearly against the darker cables around it. Blue luminous pulses ignite one after another along that twisted pair and travel rightwards, clearly representing the data frames the components exchange. Camera: static three-quarter view at headlight height, deep enough focus to hold the whole run of the loom, the street behind falling into bokeh. Lighting: cold neon key from the upper left, warm street lamp rim along the painted panel edge, deep shadow in the wheel arch. Materials: matte near-black paint, braided grey cable sheath, brushed aluminium housing, copper connector pins. Aesthetic photorealistic 9:16 vertical frame with featureless smooth matte white blank mannequins, no facial features — mannequin 1 in a fitted dark black polo shirt, mannequin 2 in a heather grey pullover hoodie with drawstrings; moody dark cinematic night atmosphere with deep shadows, warm ambient light from street lamps, neon signs and subtle glowing tech LEDs, cinematic Parisian street setting with modern cars and dark interiors; shot on a 35mm lens at f/1.8 with shallow depth of field and realistic bokeh, high-end streetwear editorial photography, hyper-detailed fabric texture, realistic plastic skin shading, 8k, no text, no labels, no logos, no watermark.
```

### Prompt animation

```
The blue pulses ignite one after another along the twisted pair, starting at the headlight housing and steadily travelling rightwards along the pair, until the whole run is alive and the control unit connector pins brighten in answer. The loom, the panel and the control unit stay perfectly rigid. The camera holds still with a slow secondary drift. Preserve exact geometry, proportions and materials. No deformation, no floating parts.
```

---

## Plan 10 — 4.5s

**Voix** : C'est le réseau interne où tous les composants de ta voiture se parlent.

**Fonction** : Montre que le bus est partagé : ce qui y entre atteint tous les calculateurs.

**Élément pédagogique** : blue pulses travelling between every module along one continuous twisted pair

**Intention de mouvement** : `energy_flow`

### Le raisonnement, avant le prompt

1. **information** : tous les modules sont sur le même fil, du phare au coffre
2. **physical element** : the continuous twisted pair running the length of the car
3. **secondary elements** : le phare, le calculateur, le combiné de bord, le module de porte
4. **visual behavior** : des impulsions bleues circulent d'un module à l'autre
5. **animation movement** : les impulsions bleues parcourent la paire d'un module à l'autre et les broches de chacun s'allument à leur tour
6. **camera position** : profil statique à hauteur de taille, foyer profond
7. **composition** : le phare à gauche, le combiné au centre, le feu arrière à droite

### Prompt image

```
Wide technical semi-cutaway of the whole dark near-black car seen from the side at night, the bodywork ghosted to transparency so the full wiring loom reads from bumper to boot. Position: the headlight sits at frame left, the engine control unit behind it, the dashboard cluster at centre frame, the door module and the rear light at frame right, all strung on one continuous twisted pair running the length of the car. Blue luminous pulses travel along that pair in both directions between the modules, clearly representing the conversation the parts hold with each other. Camera: static side view at waist height, deep enough focus to hold the whole car, the street falling into bokeh. Lighting: cold neon key from above left, warm street lamp rim along the roofline, deep shadow beneath the sills. Materials: matte near-black paint, braided grey cable sheath, brushed aluminium housings, copper connector pins, tinted glass. Aesthetic photorealistic 9:16 vertical frame with featureless smooth matte white blank mannequins, no facial features — mannequin 1 in a fitted dark black polo shirt, mannequin 2 in a heather grey pullover hoodie with drawstrings; moody dark cinematic night atmosphere with deep shadows, warm ambient light from street lamps, neon signs and subtle glowing tech LEDs, cinematic Parisian street setting with modern cars and dark interiors; shot on a 35mm lens at f/1.8 with shallow depth of field and realistic bokeh, high-end streetwear editorial photography, hyper-detailed fabric texture, realistic plastic skin shading, 8k, no text, no labels, no logos, no watermark.
```

### Prompt animation

```
The blue pulses travel steadily along the twisted pair from module to module in both directions, and as each pulse reaches a module that module's connector pins brighten in turn, building over the shot until every module along the car has answered at least once. The bodywork, the loom and the modules stay perfectly rigid. The camera holds still. Preserve exact geometry, proportions and materials. No deformation, no floating parts.
```

---

## Plan 11 — 4.5s

**Voix** : Des pirates arrivent à se brancher sur ce réseau interne.

**Fonction** : Montre le point d'arrivée : quelque chose d'extérieur entre sur le réseau.

**Élément pédagogique** : red pulses entering the twisted pair from off-frame beside the blue ones

**Intention de mouvement** : `energy_flow`

### Le raisonnement, avant le prompt

1. **information** : quelque chose d'extérieur arrive à entrer sur le réseau
2. **physical element** : the twisted pair inside the wiring loom
3. **secondary elements** : la gaine tressée, le phare, le passage de roue
4. **visual behavior** : des impulsions rouges rejoignent les bleues sur la même paire
5. **animation movement** : les impulsions rouges entrent par le bas du cadre et parcourent la paire à côté des bleues
6. **camera position** : macro statique en contre-plongée, faible profondeur de champ
7. **composition** : la paire en diagonale, le phare derrière à gauche

### Prompt image

```
Macro shot of the wiring loom running along the inner wing of the dark near-black car at night, its braided sheath ghosted to transparency over a short length so the twisted pair inside reads clearly. Position: the loom crosses the frame from the lower left to the upper right, the headlight housing sits behind it at frame left, the edge of the wheel arch runs along the lower border. Blue luminous pulses travel rightwards along the twisted pair, clearly representing the frames already running on the network, and red luminous pulses enter the same pair from beyond the lower edge of the frame. Camera: static macro at low angle, shallow depth of field so the pair is sharp and the arch falls into bokeh. Lighting: hard cold neon key raking across the sheath, warm street lamp rim along the loom, deep shadow behind. Materials: braided grey sheath, copper conductors, textured black plastic liner, matte near-black paint. Aesthetic photorealistic 9:16 vertical frame with featureless smooth matte white blank mannequins, no facial features — mannequin 1 in a fitted dark black polo shirt, mannequin 2 in a heather grey pullover hoodie with drawstrings; moody dark cinematic night atmosphere with deep shadows, warm ambient light from street lamps, neon signs and subtle glowing tech LEDs, cinematic Parisian street setting with modern cars and dark interiors; shot on a 35mm lens at f/1.8 with shallow depth of field and realistic bokeh, high-end streetwear editorial photography, hyper-detailed fabric texture, realistic plastic skin shading, 8k, no text, no labels, no logos, no watermark.
```

### Prompt animation

```
The blue pulses travel steadily rightwards along the twisted pair, and red pulses begin to enter it from beyond the lower edge of the frame, gradually building in number until red and blue travel side by side at the same spacing. The loom, the sheath and the arch stay perfectly rigid. The camera holds still. Preserve exact geometry, proportions and materials. No deformation, no floating parts.
```

---

## Plan 12 — 3s

**Voix** : Les pirates injectent leurs propres trames sur ce câble.

**Fonction** : Montre la tromperie : les fausses trames prennent le même chemin que les vraies.

**Élément pédagogique** : red added pulses joining the blue ones on the same twisted pair

**Intention de mouvement** : `energy_flow`

### Le raisonnement, avant le prompt

1. **information** : les fausses trames circulent sur le même fil que les vraies
2. **physical element** : the twisted pair inside the wheel arch
3. **secondary elements** : la gaine tressée, les conducteurs de cuivre, le passage de roue
4. **visual behavior** : des impulsions rouges rejoignent les bleues et prennent la même cadence
5. **animation movement** : les impulsions rouges entrent par le coin du cadre et parcourent la paire mêlées aux bleues jusqu'à la même cadence
6. **camera position** : macro statique en contre-plongée, faible profondeur de champ
7. **composition** : la paire en diagonale, les conducteurs visibles sur toute sa longueur

### Prompt image

```
Macro shot of the twisted pair of the car's internal network inside the front left wheel arch of the dark near-black car, its braided sheath ghosted to transparency so both copper conductors read clearly. Position: the pair crosses the frame from the lower left to the upper right, the conductors visible along its whole length, the edge of the wheel arch along the lower border. Blue luminous pulses already travel rightwards along the pair; red luminous pulses enter from beyond the lower left corner of the frame and join the same pair, travelling in the same direction and the same shape, clearly representing frames added from outside. Camera: static macro at low angle, shallow depth of field so the conductors are sharp and the arch falls into bokeh. Lighting: hard cold neon key raking across the sheath, warm street lamp rim on the conductors, deep shadow behind. Materials: braided grey cable sheath around the pair, copper conductors, textured black plastic liner, matte near-black paint. Aesthetic photorealistic 9:16 vertical frame with featureless smooth matte white blank mannequins, no facial features — mannequin 1 in a fitted dark black polo shirt, mannequin 2 in a heather grey pullover hoodie with drawstrings; moody dark cinematic night atmosphere with deep shadows, warm ambient light from street lamps, neon signs and subtle glowing tech LEDs, cinematic Parisian street setting with modern cars and dark interiors; shot on a 35mm lens at f/1.8 with shallow depth of field and realistic bokeh, high-end streetwear editorial photography, hyper-detailed fabric texture, realistic plastic skin shading, 8k, no text, no labels, no logos, no watermark.
```

### Prompt animation

```
The red pulses enter from beyond the lower left corner, gradually build in number, and travel rightwards along the twisted pair mixed in with the blue ones, while the blue pulses keep travelling at their own spacing, until red and blue run side by side at the same speed. The pair, the sheath and the liner stay perfectly rigid. The camera holds still with a slow secondary drift. Preserve exact geometry, proportions and materials. No deformation, no floating parts.
```

---

## Plan 13 — 4.5s

**Voix** : Le calculateur les lit, croit reconnaître la vraie clé, et ouvre.

**Fonction** : Montre pourquoi ça marche : la voiture ne distingue pas les deux.

**Élément pédagogique** : blue and red pulses arriving together and the sill button rising behind the glass

**Intention de mouvement** : `cause_effect`

### Le raisonnement, avant le prompt

1. **information** : la voiture traite les fausses trames comme les vraies
2. **physical element** : the door sill button behind the window glass
3. **secondary elements** : la vitre, la garniture de porte, le siège, le volant
4. **visual behavior** : les impulsions bleues et rouges arrivent ensemble à la garniture
5. **animation movement** : les impulsions arrivent ensemble et le bouton de condamnation remonte, puis le plafonnier s'allume
6. **camera position** : moyen statique à hauteur de vitre, faible profondeur de champ
7. **composition** : le bouton en bas au centre, le siège et le volant à droite

### Prompt image

```
Medium night shot through the driver's window of the dark near-black car, the cabin dark behind the glass. Position: the door sill button stands at the lower centre of the frame just behind the pane, the seat and the lower rim of the steering wheel beyond it at frame right, the reflection of a neon sign sliding across the glass. Blue and red luminous pulses arrive together along the inside of the window frame and reach the door trim, clearly representing frames the car treats exactly the same way. Camera: static medium view at window height, shallow depth of field so the button is sharp and the cabin falls into bokeh. Lighting: warm street lamp from above left, cold neon reflection across the pane, deep shadow inside the cabin. Materials: tinted glass, matte black door trim, chrome button head, leather seat. Aesthetic photorealistic 9:16 vertical frame with featureless smooth matte white blank mannequins, no facial features — mannequin 1 in a fitted dark black polo shirt, mannequin 2 in a heather grey pullover hoodie with drawstrings; moody dark cinematic night atmosphere with deep shadows, warm ambient light from street lamps, neon signs and subtle glowing tech LEDs, cinematic Parisian street setting with modern cars and dark interiors; shot on a 35mm lens at f/1.8 with shallow depth of field and realistic bokeh, high-end streetwear editorial photography, hyper-detailed fabric texture, realistic plastic skin shading, 8k, no text, no labels, no logos, no watermark.
```

### Prompt animation

```
The blue and red pulses arrive together along the window frame and reach the door trim, and as they arrive the sill button rises steadily until it stands proud of the trim and the cabin light glows on behind it. The glass, the trim and the seat stay perfectly rigid. The camera holds still. Preserve exact geometry, proportions and materials. No deformation, no floating parts.
```

---

## Plan 14 — 2.5s

**Voix** : Même tes pneus sont vulnérables.

**Fonction** : Nomme l'objet : un émetteur radio vit dans chaque roue.

**Élément pédagogique** : blue pressure pulses leaving the in-rim sensor through the tyre wall

**Intention de mouvement** : `energy_flow`

### Le raisonnement, avant le prompt

1. **information** : chaque roue porte un émetteur radio à l'intérieur
2. **physical element** : the pressure sensor clamped inside the wheel rim
3. **secondary elements** : la valve, le flanc du pneu, le disque de frein
4. **visual behavior** : des impulsions bleues quittent le capteur et traversent le pneu
5. **animation movement** : les impulsions bleues partent du capteur et parcourent le flanc jusqu'au passage de roue, et le capteur s'allume derrière elles
6. **camera position** : macro statique à hauteur de moyeu, faible profondeur de champ
7. **composition** : le capteur en bas au centre, la valve au-dessus, le disque derrière les rayons

### Prompt image

```
Macro shot of the front left wheel of the dark near-black car at night, the tyre wall ghosted to transparency at the valve so the small sensor clamped inside the rim reads clearly. Position: the sensor sits at the lower centre of the frame on the inner face of the rim, the valve stem rising from it, the brake disc and caliper visible behind the spokes. Blue luminous pulses radiate outward from the sensor through the tyre wall and travel up toward the wheel arch, clearly representing the pressure reading it broadcasts. Camera: static macro at hub height, shallow depth of field so the sensor is sharp and the kerb falls into bokeh. Lighting: cold neon key from the upper left, warm street lamp rim along the rim edge, deep shadow inside the arch. Materials: black rubber tyre, brushed aluminium rim, matte grey sensor housing, cast iron brake disc. Aesthetic photorealistic 9:16 vertical frame with featureless smooth matte white blank mannequins, no facial features — mannequin 1 in a fitted dark black polo shirt, mannequin 2 in a heather grey pullover hoodie with drawstrings; moody dark cinematic night atmosphere with deep shadows, warm ambient light from street lamps, neon signs and subtle glowing tech LEDs, cinematic Parisian street setting with modern cars and dark interiors; shot on a 35mm lens at f/1.8 with shallow depth of field and realistic bokeh, high-end streetwear editorial photography, hyper-detailed fabric texture, realistic plastic skin shading, 8k, no text, no labels, no logos, no watermark.
```

### Prompt animation

```
The blue pulses leave the sensor in steady bursts and travel outward through the tyre wall toward the wheel arch, and as each burst clears the rim the sensor housing brightens faintly behind it, building over the shot into a regular beat. The wheel, the tyre and the disc stay perfectly rigid. The camera holds still with a slow secondary drift. Preserve exact geometry, proportions and materials. No deformation, no floating parts.
```

---

## Plan 15 — 4.5s

**Voix** : Des capteurs radio non chiffrés envoient la pression de chaque roue.

**Fonction** : Montre le trajet : les mesures arrivent en clair jusqu'au tableau de bord.

**Élément pédagogique** : blue pulses travelling from all four wheel sensors up to the dashboard receiver

**Intention de mouvement** : `energy_transfer`

### Le raisonnement, avant le prompt

1. **information** : les quatre mesures arrivent en clair au tableau de bord
2. **physical element** : the receiver module behind the dashboard
3. **secondary elements** : les capteurs dans les jantes, les passages de roue
4. **visual behavior** : des impulsions bleues montent de chaque roue vers le récepteur
5. **animation movement** : les impulsions bleues parcourent les passages de roue jusqu'au récepteur, qui s'allume à chaque arrivée
6. **camera position** : profil statique à hauteur de taille, foyer profond
7. **composition** : les roues en bas du cadre, le récepteur au centre, plus haut

### Prompt image

```
Wide technical semi-cutaway of the whole dark near-black car seen from the side at night, the bodywork ghosted to transparency so the four wheels and the dashboard receiver read at once. Position: the front and rear wheels sit at the lower left and lower right of the frame, each with its sensor visible inside the rim; the receiver module sits behind the dashboard at centre frame, higher up. Blue luminous pulses leave each sensor and travel up through the arches to that receiver, clearly representing four unencrypted readings arriving in the open. Camera: static side view at waist height, deep enough focus to hold both wheels and the receiver, the street falling into bokeh. Lighting: cold neon key from above left, warm street lamp rim along the roofline, deep shadow beneath the sills. Materials: black rubber tyres, brushed aluminium rims, matte grey sensor housings, matte near-black paint, tinted glass. Aesthetic photorealistic 9:16 vertical frame with featureless smooth matte white blank mannequins, no facial features — mannequin 1 in a fitted dark black polo shirt, mannequin 2 in a heather grey pullover hoodie with drawstrings; moody dark cinematic night atmosphere with deep shadows, warm ambient light from street lamps, neon signs and subtle glowing tech LEDs, cinematic Parisian street setting with modern cars and dark interiors; shot on a 35mm lens at f/1.8 with shallow depth of field and realistic bokeh, high-end streetwear editorial photography, hyper-detailed fabric texture, realistic plastic skin shading, 8k, no text, no labels, no logos, no watermark.
```

### Prompt animation

```
The blue pulses leave each sensor in turn and travel steadily up through the arches toward the receiver, and as each one arrives the receiver module brightens once, building over the shot until all four wheels have reported and the module holds a steady glow. The car, the wheels and the receiver stay perfectly rigid. The camera holds still. Preserve exact geometry, proportions and materials. No deformation, no floating parts.
```

---

## Plan 16 — 4.5s

**Voix** : Un pirate copie leur signal et annonce une crevaison qui n'existe pas.

**Fonction** : Montre la copie : le faux signal a exactement la forme du vrai.

**Élément pédagogique** : red pulses leaving the handheld unit in the same shape as the blue ones

**Intention de mouvement** : `energy_flow`

### Le raisonnement, avant le prompt

1. **information** : le faux signal a la même forme que celui du capteur
2. **physical element** : the handheld radio unit in the mannequin's hand
3. **secondary elements** : le mannequin accroupi, la roue, le passage de roue
4. **visual behavior** : des impulsions rouges quittent le boîtier au même rythme que les bleues
5. **animation movement** : les impulsions rouges partent du boîtier et parcourent le passage de roue à côté des bleues, au même rythme
6. **camera position** : moyen statique à hauteur de moyeu, faible profondeur de champ
7. **composition** : le mannequin à gauche, la roue à droite, l'écart entre les deux

### Prompt image

```
Medium night shot of mannequin 2 in the heather grey hoodie kneeling at the kerb beside the dark near-black car, a small handheld radio unit held toward the front wheel. Position: the figure fills frame left, the wheel and its arch fill frame right, half a metre of wet cobblestone between the unit and the tyre. Red luminous pulses leave the handheld unit and travel toward the wheel arch in exactly the same shape and spacing as the blue ones still leaving the sensor inside the rim, clearly representing a second reading sent from outside the wheel. Camera: static medium view at hub height, shallow depth of field so the unit and the tyre are sharp and the street falls into bokeh. Lighting: warm street lamp from above right, cold LED glow from the handheld unit, deep shadow in the arch. Materials: matte white plastic skin, grey brushed-cotton hoodie, matte black plastic unit, black rubber tyre, brushed aluminium rim. Aesthetic photorealistic 9:16 vertical frame with featureless smooth matte white blank mannequins, no facial features — mannequin 1 in a fitted dark black polo shirt, mannequin 2 in a heather grey pullover hoodie with drawstrings; moody dark cinematic night atmosphere with deep shadows, warm ambient light from street lamps, neon signs and subtle glowing tech LEDs, cinematic Parisian street setting with modern cars and dark interiors; shot on a 35mm lens at f/1.8 with shallow depth of field and realistic bokeh, high-end streetwear editorial photography, hyper-detailed fabric texture, realistic plastic skin shading, 8k, no text, no labels, no logos, no watermark.
```

### Prompt animation

```
The red pulses begin to leave the handheld unit, gradually matching the spacing of the blue ones, and travel steadily toward the wheel arch beside them until red and blue rise through the arch together at the same rhythm. The figure, the unit and the wheel stay perfectly rigid. The camera holds still. Preserve exact geometry, proportions and materials. No deformation, no floating parts.
```

---

## Plan 17 — 4.5s

**Voix** : Le tableau de bord alerte, et le conducteur s'arrête sur la bande d'arrêt.

**Fonction** : Montre l'effet réel : une fausse mesure arrête une vraie voiture.

**Élément pédagogique** : a red glow spreading across the instrument cluster as the sweeping light slows

**Intention de mouvement** : `cause_effect`

### Le raisonnement, avant le prompt

1. **information** : une donnée fausse suffit à faire arrêter la voiture
2. **physical element** : the instrument cluster behind the steering wheel
3. **secondary elements** : le volant, le pare-brise, la bande d'arrêt d'urgence
4. **visual behavior** : une lueur rouge gagne la face du combiné
5. **animation movement** : la lueur rouge se propage sur le combiné pendant que la lumière qui balaie le pare-brise ralentit et s'arrête
6. **camera position** : moyen statique depuis le siège passager, à hauteur de combiné
7. **composition** : le combiné à gauche, le pare-brise et la route à droite

### Prompt image

```
Interior night shot of the dark cabin of the dark near-black car from the passenger side, the instrument cluster filling frame left and the windscreen filling frame right. Position: the cluster sits below the steering wheel rim, its dials dark; beyond the glass the hard shoulder and its white line run away into the night. Red luminous pulses arrive at the cluster from below and spread across its face, clearly representing the reading the cluster accepts as its own; a red glow settles on the tyre-pressure indicator well. Camera: static medium view from the passenger seat at cluster height, shallow depth of field so the dials are sharp and the road beyond falls into bokeh. Lighting: cold cluster backlight from within, warm sodium light sweeping through the windscreen from the left, deep shadow across the dashboard top. Materials: matte black dashboard plastic, brushed aluminium trim, smoked instrument glass, leather wheel rim. Aesthetic photorealistic 9:16 vertical frame with featureless smooth matte white blank mannequins, no facial features — mannequin 1 in a fitted dark black polo shirt, mannequin 2 in a heather grey pullover hoodie with drawstrings; moody dark cinematic night atmosphere with deep shadows, warm ambient light from street lamps, neon signs and subtle glowing tech LEDs, cinematic Parisian street setting with modern cars and dark interiors; shot on a 35mm lens at f/1.8 with shallow depth of field and realistic bokeh, high-end streetwear editorial photography, hyper-detailed fabric texture, realistic plastic skin shading, 8k, no text, no labels, no logos, no watermark.
```

### Prompt animation

```
The red pulses arrive at the cluster from below and the glow spreads steadily across its face until the indicator well is fully lit, and as it reaches full strength the sodium light through the windscreen slows its sweep and settles, the car coming to rest on the hard shoulder. The dashboard, the wheel and the cluster stay perfectly rigid. The camera holds still. Preserve exact geometry, proportions and materials. No deformation, no floating parts.
```

---

## Plan 18 — 4s

**Voix** : Ce même bus CAN sert aussi à reprendre le contrôle.

**Fonction** : Retourne le sujet : le même câble porte aussi les commandes voulues.

**Élément pédagogique** : green command pulses travelling down the column into the moving steering rack

**Intention de mouvement** : `energy_flow`

### Le raisonnement, avant le prompt

1. **information** : le même bus peut porter des commandes voulues par le conducteur
2. **physical element** : the twisted pair inside the steering column
3. **secondary elements** : la jante du volant, la crémaillère en coupe, le combiné
4. **visual behavior** : des impulsions vertes descendent la colonne vers la crémaillère
5. **animation movement** : les impulsions vertes parcourent la colonne jusqu'à la crémaillère, qui se met à coulisser
6. **camera position** : moyen statique depuis le siège passager, à hauteur de volant
7. **composition** : la jante en haut, la colonne au centre, la crémaillère en bas

### Prompt image

```
Interior night shot of the dark cabin of the dark near-black car, the steering column ghosted to transparency below the wheel so the twisted pair of the CAN bus reads clearly inside it. Position: the wheel rim runs across the top of the frame, the column drops from it through the centre, the steering rack sits at the lower edge in technical semi-cutaway. Green luminous pulses travel down that pair from the top of the column toward the rack, clearly representing a command sent on purpose by the driver's own hardware. Camera: static medium view from the passenger seat at wheel height, shallow depth of field so the column is sharp and the windscreen falls into bokeh. Lighting: cold cluster backlight from the left, warm sodium light through the windscreen, deep shadow in the footwell. Materials: leather wheel rim, matte black column shroud, braided grey sheath, brushed steel rack. Aesthetic photorealistic 9:16 vertical frame with featureless smooth matte white blank mannequins, no facial features — mannequin 1 in a fitted dark black polo shirt, mannequin 2 in a heather grey pullover hoodie with drawstrings; moody dark cinematic night atmosphere with deep shadows, warm ambient light from street lamps, neon signs and subtle glowing tech LEDs, cinematic Parisian street setting with modern cars and dark interiors; shot on a 35mm lens at f/1.8 with shallow depth of field and realistic bokeh, high-end streetwear editorial photography, hyper-detailed fabric texture, realistic plastic skin shading, 8k, no text, no labels, no logos, no watermark.
```

### Prompt animation

```
The green pulses travel steadily down the twisted pair from the top of the column toward the rack, and as the first of them reaches the rack the rack shaft begins to slide sideways in its housing, building until it moves continuously. The wheel, the shroud and the dashboard stay perfectly rigid. The camera holds still. Preserve exact geometry, proportions and materials. No deformation, no floating parts.
```

---

## Plan 19 — 4.5s

**Voix** : Un boîtier à 900 euros et OpenPilot y branchent une conduite autonome.

**Fonction** : Montre le montage réel : un boîtier, un câble, et la commande part.

**Élément pédagogique** : green pulses leaving the aftermarket box down the pillar into the turning wheel

**Intention de mouvement** : `energy_transfer`

### Le raisonnement, avant le prompt

1. **information** : un boîtier du commerce écrit sur le même bus
2. **physical element** : the matte black box clipped behind the rear-view mirror
3. **secondary elements** : le câble tressé, le montant, la jante du volant
4. **visual behavior** : des impulsions vertes quittent le boîtier et descendent le câble
5. **animation movement** : les impulsions vertes parcourent le câble jusqu'à la colonne, et la jante du volant se met à tourner
6. **camera position** : moyen statique depuis le siège passager, à hauteur de rétroviseur
7. **composition** : le boîtier en haut au centre, le câble descendant à gauche

### Prompt image

```
Interior night shot of the top of the windscreen of the dark near-black car, a small matte black box clipped behind the rear-view mirror with a thin braided cable running down the A-pillar. Position: the box fills the upper centre of the frame, the mirror stem beside it, the cable dropping along the pillar at frame left; the steering wheel rim fills the lower edge of the frame, its leather grip and upper spokes clearly in shot below the column shroud. Green luminous pulses leave the box, travel down that cable and continue into the steering column, clearly representing the commands the box puts on the bus. Camera: static medium view from the passenger seat at mirror height, shallow depth of field so the box is sharp and the road beyond the glass falls into bokeh. Lighting: cold LED glow from the box itself, warm sodium light sweeping through the windscreen, deep shadow along the headliner. Materials: matte black plastic housing, braided grey cable, smoked mirror glass, matte black pillar trim. Aesthetic photorealistic 9:16 vertical frame with featureless smooth matte white blank mannequins, no facial features — mannequin 1 in a fitted dark black polo shirt, mannequin 2 in a heather grey pullover hoodie with drawstrings; moody dark cinematic night atmosphere with deep shadows, warm ambient light from street lamps, neon signs and subtle glowing tech LEDs, cinematic Parisian street setting with modern cars and dark interiors; shot on a 35mm lens at f/1.8 with shallow depth of field and realistic bokeh, high-end streetwear editorial photography, hyper-detailed fabric texture, realistic plastic skin shading, 8k, no text, no labels, no logos, no watermark.
```

### Prompt animation

```
The green pulses leave the box one after another and travel steadily down the cable along the pillar, and as they reach the column below the wheel rim begins to rotate slightly of its own accord, building until it holds a continuous correction. The box, the mirror and the pillar stay perfectly rigid. The camera holds still. Preserve exact geometry, proportions and materials. No deformation, no floating parts.
```

---

## Plan 20 — 2.5s

**Voix** : Abonne-toi pour la partie 2.

**Fonction** : Montre le résultat vécu : la voiture tient la route sans les mains.

**Élément pédagogique** : the wheel rim turning by itself beneath the lifted hands, green pulses in the column

**Intention de mouvement** : `cause_effect`

### Le raisonnement, avant le prompt

1. **information** : les commandes tiennent le volant à la place du conducteur
2. **physical element** : the steering wheel rim under the lifted hands
3. **secondary elements** : les mains du mannequin, la colonne, la route de nuit
4. **visual behavior** : des impulsions vertes circulent dans la colonne pendant que la jante tourne
5. **animation movement** : la jante tourne toute seule sous les mains levées pendant que les impulsions vertes parcourent la colonne
6. **camera position** : moyen statique à hauteur de volant, faible profondeur de champ
7. **composition** : le mannequin à gauche, la jante au centre, la route à droite

### Prompt image

```
Interior night shot from the passenger seat of the dark near-black car, mannequin 1, a featureless smooth matte white figure in a fitted dark black polo shirt, sitting at the wheel with both white plastic hands lifted clear of the rim. Position: the figure fills frame left, the wheel rim fills the centre, the windscreen and the night road fill frame right, the hands hover a few centimetres above the leather. Green luminous pulses run through the steering column below the rim, clearly representing the commands now steering in the driver's place. Camera: static medium view at wheel height, shallow depth of field so the hands are sharp and the road falls into bokeh. Lighting: cold cluster backlight from below, warm sodium light sweeping through the windscreen from the left, deep shadow across the seat. Materials: matte white plastic skin, black cotton polo fabric, leather wheel rim, matte black column shroud. Aesthetic photorealistic 9:16 vertical frame with featureless smooth matte white blank mannequins, no facial features — mannequin 1 in a fitted dark black polo shirt, mannequin 2 in a heather grey pullover hoodie with drawstrings; moody dark cinematic night atmosphere with deep shadows, warm ambient light from street lamps, neon signs and subtle glowing tech LEDs, cinematic Parisian street setting with modern cars and dark interiors; shot on a 35mm lens at f/1.8 with shallow depth of field and realistic bokeh, high-end streetwear editorial photography, hyper-detailed fabric texture, realistic plastic skin shading, 8k, no text, no labels, no logos, no watermark.
```

### Prompt animation

```
The green pulses travel steadily through the column, and as they do the wheel rim rotates slowly on its own beneath the lifted hands, which stay clear of it, the rotation building until the sodium light through the windscreen swings with it. The figure, the seat and the dashboard stay perfectly rigid. The camera holds still. Preserve exact geometry, proportions and materials. No deformation, no floating parts.
```

---

## Ce que tu fais maintenant

1. Génère chaque **image** avec l'outil de ton choix, à partir du prompt image.
2. Dépose les images dans `app/output/images` nommées `shot_01.png`, `shot_02.png`…
3. Lance `affiner-tout` : chaque prompt d'animation est réécrit sur ton image réelle, et non plus sur une image imaginée. **Les prompts ci-dessus sont alors remplacés** — reviens les lire ici.
4. Génère chaque **animation** à partir de ton image, avec le prompt animation.
5. Dépose les vidéos dans `app/output/videos` nommées `shot_01.mp4`, `shot_02.mp4`…
6. Reviens : `analyser-videos`, puis `juger`, puis `timeline`, puis `montage`.

**`juger`** est le contrôle qui ne se ment pas : un modèle qui ne sait rien regarde tes vidéos **sans la narration** et dit ce qu'il a compris. On compare à ce que chaque plan devait faire comprendre. Les plans compris entrent dans la mémoire et serviront aux vidéos suivantes.

Pour que l'objet reste le même d'un plan à l'autre, produis d'abord l'image maîtresse et dérive les autres : voir `app/output/identite.md`.
