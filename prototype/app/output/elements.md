# Comment on vole une voiture récente sans casser une vitre

46.472 secondes · 5 plans

## Script

Ta voiture récente peut se faire voler en moins de 30 secondes, sans casser une vitre. Bienvenue dans le hacking automobile. Première technique : l'attaque par relais. Un complice capte le signal de ta clé à travers la porte, et ta voiture s'ouvre. Plus lourd : le bus CAN, le réseau où tous les composants de ta voiture se parlent. Des pirates s'y branchent et imitent ta clé. Même tes pneus sont vulnérables : leurs capteurs radio sont en clair. Une fausse crevaison peut arrêter un convoi entier. Mais ce bus sert aussi à reprendre le contrôle. Avec OpenPilot et un boîtier à 900 euros, tu ajoutes une conduite autonome.

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

## Plan 01 — 9.283s

**Voix** : Ta voiture récente peut se faire voler en moins de 30 secondes, sans casser une vitre. Bienvenue dans le hacking automobile.

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

## Plan 02 — 9.973s

**Voix** : Première technique : l'attaque par relais. Un complice capte le signal de ta clé à travers la porte, et ta voiture s'ouvre.

**Fonction** : Montre le premier maillon : le signal de la clé est capté à travers la porte.

**Élément pédagogique** : blue key pulses crossing the wood into the box antenna, red glow building on it

**Intention de mouvement** : `energy_transfer`

### Le raisonnement, avant le prompt

1. **information** : le signal de la clé est capté puis reporté jusqu'à la voiture
2. **physical element** : the flat black box pressed against the front door
3. **secondary elements** : la clé au crochet, le panneau vitré, le second boîtier contre la voiture au fond
4. **visual behavior** : les impulsions bleues traversent le bois, entrent dans l'antenne, puis longent le faisceau rouge
5. **animation movement** : les impulsions bleues traversent le bois et gagnent l'antenne, puis parcourent le faisceau rouge jusqu'à la poignée de la voiture
6. **camera position** : moyen statique à hauteur de poitrine, foyer profond
7. **composition** : la porte et le boîtier au centre, la voiture au fond à droite

### Prompt image

```
Medium night shot of the building's front door from outside, mannequin 2 in the heather grey hoodie pressing a flat black box against the painted wood at chest height. Position: the car key hangs on its hook inside, framed through the glazed panel just above the box; the antenna face is pressed flat to the door, and beyond the figure, eight metres away at frame right, the dark near-black car waits at the kerb with a second identical box held against its driver door. Blue luminous pulses leave the key, cross the wood, and are drawn into the antenna face, clearly representing the key's own signal being picked up; a red luminous beam runs from that box across the courtyard to the second one. Camera: static medium view at chest height, deep enough focus to hold both the door and the car, the gate falling into bokeh. Lighting: warm hallway glow behind the glazed panel, cold street lamp from above left, deep shadow on the wood. Materials: painted wood, glass, matte black plastic housings, brass key, matte near-black paint, wet cobblestone. Aesthetic photorealistic 9:16 vertical frame with featureless smooth matte white blank mannequins, no facial features — mannequin 1 in a fitted dark black polo shirt, mannequin 2 in a heather grey pullover hoodie with drawstrings; moody dark cinematic night atmosphere with deep shadows, warm ambient light from street lamps, neon signs and subtle glowing tech LEDs, cinematic Parisian street setting with modern cars and dark interiors; shot on a 35mm lens at f/1.8 with shallow depth of field and realistic bokeh, high-end streetwear editorial photography, hyper-detailed fabric texture, realistic plastic skin shading, 8k, no text, no labels, no logos, no watermark.
```

### Prompt animation

```
The blue pulses leave the key, cross the wood one after another, and are drawn into the antenna face, and as each one enters, the red beam across the courtyard steadily brightens; then the blue pulses begin to travel along that beam from left to right until they reach the second box at the car and enter its door handle unchanged. The door, the key, the boxes and the car stay perfectly rigid. The camera holds still. Preserve exact geometry, proportions and materials. No deformation, no floating parts.
```

---

## Plan 03 — 8.547s

**Voix** : Plus lourd : le bus CAN, le réseau où tous les composants de ta voiture se parlent. Des pirates s'y branchent et imitent ta clé.

**Fonction** : Montre la tromperie : les fausses trames prennent le même chemin que les vraies.

**Élément pédagogique** : red added pulses joining the blue ones on the same twisted pair

**Intention de mouvement** : `energy_flow`

### Le raisonnement, avant le prompt

1. **information** : les fausses trames prennent le même fil que les vraies et arrivent au calculateur
2. **physical element** : the twisted pair ending at the control unit connector
3. **secondary elements** : la gaine tressée, les broches de cuivre, le passage de roue
4. **visual behavior** : des impulsions rouges rejoignent les bleues puis allument les mêmes broches
5. **animation movement** : les impulsions rouges entrent par le coin du cadre, parcourent la paire mêlées aux bleues, et les broches du connecteur s'allument pareil pour les deux
6. **camera position** : macro statique en contre-plongée, faible profondeur de champ
7. **composition** : la paire en diagonale, le connecteur en haut à droite

### Prompt image

```
Macro shot of the twisted pair of the car's internal network inside the front left wheel arch of the dark near-black car, its braided sheath ghosted to transparency so both copper conductors read clearly. Position: the pair crosses the frame from the lower left to the upper right and ends at the control unit connector at the top right, its row of copper pins visible through the ghosted aluminium lid; the edge of the wheel arch runs along the lower border. Blue luminous pulses already travel rightwards along the pair; red luminous pulses enter from beyond the lower left corner of the frame and join the same pair, travelling in the same direction and the same shape, clearly representing frames added from outside. Camera: static macro at low angle, shallow depth of field so the conductors are sharp and the arch falls into bokeh. Lighting: hard cold neon key raking across the sheath, warm street lamp rim on the conductors, deep shadow behind. Materials: braided grey cable sheath around the pair, copper conductors, brushed aluminium lid, textured black plastic liner. Aesthetic photorealistic 9:16 vertical frame with featureless smooth matte white blank mannequins, no facial features — mannequin 1 in a fitted dark black polo shirt, mannequin 2 in a heather grey pullover hoodie with drawstrings; moody dark cinematic night atmosphere with deep shadows, warm ambient light from street lamps, neon signs and subtle glowing tech LEDs, cinematic Parisian street setting with modern cars and dark interiors; shot on a 35mm lens at f/1.8 with shallow depth of field and realistic bokeh, high-end streetwear editorial photography, hyper-detailed fabric texture, realistic plastic skin shading, 8k, no text, no labels, no logos, no watermark.
```

### Prompt animation

```
The red pulses enter from beyond the lower left corner, gradually build in number, and travel rightwards along the twisted pair mixed in with the blue ones, while the blue pulses keep travelling at their own spacing; then red and blue reach the connector together and its copper pins light up identically for both, until the whole row is glowing. The pair, the sheath and the connector stay perfectly rigid. The camera holds still. Preserve exact geometry, proportions and materials. No deformation, no floating parts.
```

---

## Plan 04 — 8.634s

**Voix** : Même tes pneus sont vulnérables : leurs capteurs radio sont en clair. Une fausse crevaison peut arrêter un convoi entier.

**Fonction** : Montre la copie : le faux signal a exactement la forme du vrai.

**Élément pédagogique** : red pulses leaving the handheld unit in the same shape as the blue ones

**Intention de mouvement** : `energy_flow`

### Le raisonnement, avant le prompt

1. **information** : un faux signal envoyé de loin suffit à arrêter la voiture
2. **physical element** : the handheld radio unit in the mannequin's hand
3. **secondary elements** : la roue, le passage de roue, le répétiteur de clignotant sur l'aile
4. **visual behavior** : des impulsions rouges quittent le boîtier au rythme des bleues, puis le répétiteur s'allume
5. **animation movement** : les impulsions rouges parcourent le passage de roue à côté des bleues, le répétiteur s'allume et la roue s'arrête de tourner
6. **camera position** : moyen statique à hauteur de moyeu, faible profondeur de champ
7. **composition** : le mannequin à gauche, la roue à droite, le répétiteur au-dessus

### Prompt image

```
Medium night shot of mannequin 2 in the heather grey hoodie kneeling at the kerb beside the dark near-black car, a small handheld radio unit held toward the front wheel. Position: the figure fills frame left, the wheel and its arch fill frame right, the side indicator repeater sits on the wing just above the arch, half a metre of wet cobblestone between the unit and the tyre. Red luminous pulses leave the handheld unit and travel toward the wheel arch in exactly the same shape and spacing as the blue ones still leaving the sensor inside the rim, clearly representing a second reading sent from outside the wheel. Camera: static medium view at hub height, shallow depth of field so the unit and the tyre are sharp and the street falls into bokeh. Lighting: warm street lamp from above right, cold LED glow from the handheld unit, deep shadow in the arch. Materials: matte white plastic skin, grey brushed-cotton hoodie, matte black plastic unit, black rubber tyre, brushed aluminium rim. Aesthetic photorealistic 9:16 vertical frame with featureless smooth matte white blank mannequins, no facial features — mannequin 1 in a fitted dark black polo shirt, mannequin 2 in a heather grey pullover hoodie with drawstrings; moody dark cinematic night atmosphere with deep shadows, warm ambient light from street lamps, neon signs and subtle glowing tech LEDs, cinematic Parisian street setting with modern cars and dark interiors; shot on a 35mm lens at f/1.8 with shallow depth of field and realistic bokeh, high-end streetwear editorial photography, hyper-detailed fabric texture, realistic plastic skin shading, 8k, no text, no labels, no logos, no watermark.
```

### Prompt animation

```
The red pulses begin to leave the handheld unit, gradually matching the spacing of the blue ones, and travel steadily toward the wheel arch beside them; as they rise through the arch together the side indicator repeater above it lights up and holds, and the wheel slows until it stops turning. The figure, the unit and the car stay perfectly rigid. The camera holds still. Preserve exact geometry, proportions and materials. No deformation, no floating parts.
```

---

## Plan 05 — 10.035s

**Voix** : Mais ce bus sert aussi à reprendre le contrôle. Avec OpenPilot et un boîtier à 900 euros, tu ajoutes une conduite autonome.

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

## Ce que tu fais maintenant

1. Génère chaque **image** avec l'outil de ton choix, à partir du prompt image.
2. Dépose les images dans `app/output/images` nommées `shot_01.png`, `shot_02.png`…
3. Lance `affiner-tout` : chaque prompt d'animation est réécrit sur ton image réelle, et non plus sur une image imaginée. **Les prompts ci-dessus sont alors remplacés** — reviens les lire ici.
4. Génère chaque **animation** à partir de ton image, avec le prompt animation.
5. Dépose les vidéos dans `app/output/videos` nommées `shot_01.mp4`, `shot_02.mp4`…
6. Reviens : `analyser-videos`, puis `juger`, puis `timeline`, puis `montage`.

**`juger`** est le contrôle qui ne se ment pas : un modèle qui ne sait rien regarde tes vidéos **sans la narration** et dit ce qu'il a compris. On compare à ce que chaque plan devait faire comprendre. Les plans compris entrent dans la mémoire et serviront aux vidéos suivantes.

Pour que l'objet reste le même d'un plan à l'autre, produis d'abord l'image maîtresse et dérive les autres : voir `app/output/identite.md`.
