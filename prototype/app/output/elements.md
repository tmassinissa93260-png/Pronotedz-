# Fonctionnement d'une voiture électrique

16 secondes · 4 plans

## Ce que le sujet EST

Établi **avant** le script. Le storyboard suit cette chaîne.

- **components** : batterie, câbles haute tension, électronique de puissance, moteur électrique, boîte de transfert, roues
- **functions** : la batterie stocke l'énergie, les câbles transmettent l'électricité, l'électronique de puissance convertit et régule l'énergie, le moteur produit un couple électromagnétique, la boîte de transfert adapte la vitesse, les roues permettent le mouvement du véhicule
- **energy direction** : de la batterie vers le moteur, puis vers les roues lors de l'accélération; inversement lors du freinage régénératif
- **transformations** : chimique à électrique dans la batterie, électrique à mécanique dans le moteur, mécanique aux roues via la boîte de transfert
- **invisible phenomena** : flux d'énergie électrique, conversion électromagnétique
- **acceptable simplifications** : dire que la batterie alimente le moteur, représenter l'électricité comme un flux lumineux
- **common errors** : ignorer le rôle de l'inverseur et simplifier le moteur à une boîte noire

**Chaîne causale**

1. énergie chimique de la batterie
2. énergie électrique dans le circuit
3. conversion et contrôle par l'électronique de puissance
4. couple électromagnétique dans le moteur
5. rotation du moteur
6. transfert mécanique à la boîte
7. rotation des roues
8. mouvement du véhicule

## Script

Comment une voiture électrique fonctionne-t-elle? La batterie produit de l'énergie électrique dirigée vers le moteur. L'électronique de puissance convertit cette énergie en courant alternatif et gère l'intensité. Cela génère un couple qui fait tourner le moteur. Le mouvement est transmis aux roues pour propulser la voiture.

## Visual bible

À réutiliser dans **chaque** image. Les couleurs ont un sens fixe.

- **main subject** : énergie électrique dirigée vers le moteur
- **characters objects** : moteur, batterie, câblage, roues
- **vehicle** : un sedan électrique moderne de couleur noire
- **colors** : énergie électrique en jaune/orange, composantes mécaniques en gris
- **environment** : studio de rendu premium sombre
- **materials** : matériaux réalistes avec une attention aux détails
- **lighting** : cinématographique, avec éclairage bleu et blanc
- **camera** : mouvements subtils, suivant le flux d'information
- **style 3d** : vue en coupe technique semi-réaliste
- **realism** : visualisation en 3D de haute qualité
- **invisible phenomena** : représentation du flux d'énergie électrique lumineux jaune/orange

## Contrôle qualité

- narrative quality : 0.9
- visual quality : 0.9
- scientific accuracy : 0.9
- voice visual alignment : 0.9
- visual continuity : 0.9
- pedagogical clarity : 0.9
- animation potential : 0.9
- motion quality : 0.9
- causal clarity : 0.9
- physical plausibility : 0.9

---

## Plan 01 — 4s

**Voix** : Comment une voiture électrique fonctionne-t-elle en utilisant l’énergie stockée dans la batterie?

**Fonction** : Introduire le véhicule électrique et ses composantes clés visibles.

**Élément pédagogique** : introduction au véhicule avec une vue partielle en coupe

**Intention de mouvement** : `energy_transfer`

### Le raisonnement, avant le prompt

1. **information** : introduction à la coupe technique du véhicule
2. **cause** : découvrir les composants internes du véhicule
3. **effect** : révélation de la position du moteur et de la batterie
4. **physical element** : la voiture électrique
5. **secondary elements** : moteur, batterie
6. **visual behavior** : aucun flux d'énergie visible encore
7. **initial state** : voiture avec carrosserie partiellement coupée visible
8. **animation movement** : énergie quittant la batterie, provoquant la rotation du rotor
9. **secondary motion** : engagement progressif des roues, établissant un mouvement
10. **final state** : moteur et roues en mouvement stable
11. **camera position** : vue large, centrée sur la voiture
12. **composition** : voiture principalement au centre, avec espace pour les composants visibles

### Prompt image

```
Wide shot of the dark near-black electric sedan in technical semi-cutaway view, camera positioned centrally, highlighting the motor and battery materials. The bodywork appears smooth and realistic, with soft cinematic blue and white studio lighting. Controlled yellow-orange luminous streams for electrical energy show potential pathways for energy flow. Photorealistic premium 3D engineering visualization, the same modern dark near-black electric sedan in technical semi-cutaway view, realistic bodywork with internal components visible where the explanation needs them, dark premium studio environment, cinematic blue and white lighting, realistic detailed materials, physically credible automotive mechanics, clearly visible electrical and mechanical components, cinematic depth of field, high contrast, premium high-end car commercial rendering, vertical 9:16 composition, no text, no labels, no logos, no watermark.
```

### Prompt animation

```
The scene begins with the electric sedan at rest. The energy, represented by yellow-orange flow, starts at the battery, moving into the motor, causing the rotor to rotate and engage the wheels. The animation ends with the motor and wheels in steady motion. While this occurs, the camera subtly reveals these coordinated movements without being the primary dynamic.
```

---

## Plan 02 — 4s

**Voix** : La batterie produit de l'énergie électrique dirigée vers le moteur.

**Fonction** : Demonstrate how electrical energy from the battery initiates the system.

**Élément pédagogique** : yellow/orange energy streams leaving the battery through cables

**Intention de mouvement** : `energy_flow`

### Le raisonnement, avant le prompt

1. **information** : la batterie fournit de l'énergie
2. **cause** : l'énergie commence à être libérée de la batterie
3. **effect** : flux d'énergie visible vers le moteur
4. **physical element** : la batterie
5. **secondary elements** : câblage haute tension, moteur
6. **visual behavior** : flux lumineux jaune/orange quittant la batterie
7. **initial state** : batterie statique, flux d'énergie pas encore visible
8. **animation movement** : flux d'énergie clairement visible voyageant
9. **secondary motion** : le mouvement du flux suivi par la caméra
10. **final state** : flux d'énergie vers le moteur établi
11. **camera position** : plan rapproché sur la batterie et câbles
12. **composition** : batterie sur un côté, câbles conduisant vers le moteur

### Prompt image

```
Close-up of the battery pack with high-voltage cables clearly visible, depicting yellow/orange electrical energy streams moving outward. The scene is illuminated to focus on the cables and energy flow as the primary elements. The energy streams appear to originate from individual battery cells and travel toward the motor in a controlled manner, emphasizing the flow direction. Photorealistic premium 3D engineering visualization, the same modern dark near-black electric sedan in technical semi-cutaway view, realistic bodywork with internal components visible where the explanation needs them, dark premium studio environment, cinematic blue and white lighting, realistic detailed materials, physically credible automotive mechanics, clearly visible electrical and mechanical components, cinematic depth of field, high contrast, premium high-end car commercial rendering, vertical 9:16 composition, no text, no labels, no logos, no watermark.
```

### Prompt animation

```
Initially, the battery is dormant, with no visible motion. Yellow-orange electrical energy begins to flow from the illuminated battery cells, traveling along the high-voltage cables towards the motor. As the energy reaches the motor, the rotor begins to turn. While the battery and vehicle chassis remain static, the camera subtly follows the path of the energy along the cables toward the motor, illustrating the direction of the flow. The animation ends with the energy having reached the motor, and the rotor turning steadily.
```

---

## Plan 03 — 4s

**Voix** : L'électronique de puissance convertit cette énergie en courant alternatif et gère l'intensité.

**Fonction** : Illustrate the role of the power electronics in energy conversion and control.

**Élément pédagogique** : conversion de l'énergie dans l'électronique de puissance

**Intention de mouvement** : `energy_transfer`

### Le raisonnement, avant le prompt

1. **information** : énergie convertie et régulée
2. **cause** : énergie entrant dans l'unité électronique de puissance
3. **effect** : flux se transforme de DC à AC
4. **physical element** : l'unité d'électronique de puissance
5. **secondary elements** : flux d'énergie
6. **visual behavior** : changement de forme du flux d'énergie illustrant la conversion
7. **initial state** : énergie arrivant en flux continu
8. **animation movement** : conversion visible du flux énergétique
9. **secondary motion** : flux continuant vers le moteur
10. **final state** : flux converti et orienté vers le moteur
11. **camera position** : plan moyen sur l'unité électronique
12. **composition** : unité placée au centre, flux visible entrant et sortant

### Prompt image

```
Mid-range shot focusing on the power electronics unit within the vehicle, visibly processing the yellow/orange electrical energy flow. The energy stream appears to dynamically transform, representing the conversion from direct current (DC) to alternating current (AC) within the unit. The visualization should distinctly show the conversion process through changes in the form of the flow pattern. Photorealistic premium 3D engineering visualization, the same modern dark near-black electric sedan in technical semi-cutaway view, realistic bodywork with internal components visible where the explanation needs them, dark premium studio environment, cinematic blue and white lighting, realistic detailed materials, physically credible automotive mechanics, clearly visible electrical and mechanical components, cinematic depth of field, high contrast, premium high-end car commercial rendering, vertical 9:16 composition, no text, no labels, no logos, no watermark.
```

### Prompt animation

```
The shot begins with the yellow-orange electrical energy stream flowing continuously toward the power electronics unit. As the flow enters the unit, it visibly transforms, illustrating the conversion from direct to alternating current. This transformation is depicted through changes in the flow's structure and oscillation pattern. As the conversion process completes, the energy continues to flow toward the motor. The camera maintains a steady positioning, highlighting the conversion process within the electronics. The animation ends with the energy having been converted successfully and the flow continuing towards the motor.
```

---

## Plan 04 — 4s

**Voix** : Le couple généré tourne le moteur et propulse la voiture.

**Fonction** : Convey how electrical energy generates rotation in the motor and moves the car.

**Élément pédagogique** : yellow energy flow activating the motor's rotor

**Intention de mouvement** : `mechanical_rotation`

### Le raisonnement, avant le prompt

1. **information** : conversion de l'électricité en mouvement
2. **cause** : énergie électrique activant le moteur
3. **effect** : rotation mécanique transmise aux roues
4. **physical element** : moteur électrique
5. **secondary elements** : rotor, stator, transmission, roues
6. **visual behavior** : flux énergétique provoquant la rotation du rotor
7. **initial state** : rotor au repos, flux énergétique entrant
8. **animation movement** : rotation progressive du rotor
9. **secondary motion** : mouvement transféré aux roues, entraînant la voiture
10. **final state** : rotor en mouvement, voiture propulsée
11. **camera position** : vue détaillée sur le moteur et transmission
12. **composition** : éléments centrés avec flux d'énergie clairement montré

### Prompt image

```
Detailed view of the electric motor with visible stator and rotor components as yellow/orange energy enters and activates the rotor. The focus is on the interaction between the energy flow and the mechanical parts of the motor, demonstrating the transition from electrical energy to mechanical motion. The motor should appear central and active, with mechanical components in secondary focus, along with the gear and wheel in clear view. Photorealistic premium 3D engineering visualization, the same modern dark near-black electric sedan in technical semi-cutaway view, realistic bodywork with internal components visible where the explanation needs them, dark premium studio environment, cinematic blue and white lighting, realistic detailed materials, physically credible automotive mechanics, clearly visible electrical and mechanical components, cinematic depth of field, high contrast, premium high-end car commercial rendering, vertical 9:16 composition, no text, no labels, no logos, no watermark.
```

### Prompt animation

```
Initially, the electric motor's rotor is stationary. As the yellow-orange energy enters and energizes the stator, the rotor progressively begins to turn, illustrating the conversion from electrical energy to mechanical rotation. This rotational energy then flows through the drivetrain, shown with meshed gears transferring the motion to the wheels. The wheels begin to turn, initiating the car's movement. The camera follows the flow path from the motor through the drivetrain to the wheels, emphasizing the energy's direction and the mechanical process. The animation ends with the rotor and wheels turning steadily, demonstrating the car's propulsion.
```

---

## Ce que tu fais maintenant

1. Génère chaque **image** avec l'outil de ton choix, à partir du prompt image.
2. Génère chaque **animation** à partir de ton image, avec le prompt animation.
3. Dépose les vidéos dans `prototype/app/output/videos` nommées `shot_01.mp4`, `shot_02.mp4`…
4. Reviens : `analyser-videos`, puis `timeline`, puis `montage`.
