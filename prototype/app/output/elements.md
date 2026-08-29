# Fonctionnement d'une voiture électrique

12 secondes · 3 plans

## Ce que le sujet EST

Établi **avant** le script. Le storyboard suit cette chaîne.

- **components** : battery, inverter, electric motor, transmission, wheels
- **functions** : battery stores energy, inverter converts DC to AC and controls power, motor converts electrical energy to mechanical, transmission transfers mechanical energy, wheels enable car motion
- **energy direction** : from battery to wheels while driving; from wheels to battery during regenerative braking
- **transformations** : chemical to electrical in battery, electrical to mechanical in motor, mechanical to kinetic in wheels
- **invisible phenomena** : electricity flow, electromagnetic fields
- **acceptable simplifications** : generalize electromagnetic field interactions
- **common errors** : oversimplifying the inverter's role, depicting the motor as a simple black box

**Chaîne causale**

1. battery chemical energy -> electrical energy in the circuit
2. power electronics / inverter converts DC to AC and controls the power
3. electromagnetic torque in the motor
4. motor rotation
5. reduction gear and drivetrain
6. wheel rotation
7. vehicle motion
8. vehicle kinetic energy -> motor acting as a generator
9. electrical energy -> power electronics -> battery charging

## Script

Voyez comment une voiture électrique fonctionne: l'électricité passe de la batterie au moteur. Celle-ci active le moteur qui fait tourner les roues. En freinage, l'énergie est renvoyée vers la batterie.

## Visual bible

À réutiliser dans **chaque** image. Les couleurs ont un sens fixe.

- **main subject** : electric car operation
- **characters objects** : battery, cables, motor, wheels, inverter
- **vehicle** : modern dark/black electric sedan
- **colors** : yellow/orange for electricity, blue for battery, grey for mechanics, green for regenerative energy
- **environment** : dark premium studio
- **materials** : realistic detailed materials
- **lighting** : cinematic blue and white lighting
- **camera** : close-up, medium, tracking shots
- **style 3d** : premium 3D engineering visualization
- **realism** : high
- **invisible phenomena** : yellow/orange energy flows, green return flows

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

**Voix** : Voyez comment une voiture électrique fonctionne: l'électricité passe de la batterie au moteur.

**Fonction** : Understand how electricity flows from the battery.

**Élément pédagogique** : Yellow energy flow from the battery cells into cables

**Intention de mouvement** : `energy_flow`

### Le raisonnement, avant le prompt

1. **information** : The battery supplies electricity to the motor.
2. **physical mechanism** : Electrical energy is released from the battery.
3. **cause** : The battery begins supplying electricity.
4. **effect** : Yellow-orange energy streams start flowing through cables.
5. **physical element** : Battery pack
6. **secondary elements** : High-voltage cables
7. **visual behavior** : Yellow/orange flow traveling along cables
8. **initial state** : Stationary battery and visible cables
9. **animation movement** : Energy flowing through the cables
10. **secondary motion** : Camera subtly tracks the flow path
11. **final state** : Energy continuing to travel through cables
12. **camera position** : Close enough to read the whole path
13. **composition** : Battery on one side, cables leading out to the motor

### Prompt image

```
Technical semi-cutaway view of an electric car's battery showing visible cells on one side and high-voltage cables on the other. The engine, identified as the 'moteur,' appears connected by visible cables. Yellow-orange energy streams flow visibly from the battery cells into the cables, moving outward. The battery is blue, and high-voltage cables are realistically rendered and clearly visible. The battery, cables, and motor maintain geometric consistency. Photorealistic premium 3D engineering visualization, the same modern dark near-black electric sedan in technical semi-cutaway view, realistic bodywork with internal components visible where the explanation needs them, dark premium studio environment, cinematic blue and white lighting, realistic detailed materials, physically credible automotive mechanics, clearly visible electrical and mechanical components, cinematic depth of field, high contrast, premium high-end car commercial rendering, vertical 9:16 composition, no text, no labels, no logos, no watermark.
```

### Prompt animation

```
The scene starts with blue-lit battery cells, stationary. Yellow-orange energy pulses gradually begin inside the battery, traveling with directionality through high-voltage cables toward the motor, accelerating smoothly. As the energy reaches the motor, it initiates a slight vibration in the motor, indicating activation. Yellow-orange streams continue pulsating along the cables. The camera makes a subtle tracking movement following the energy flow path. No deformation, battery cells and vehicle geometry remain fixed.
```

---

## Plan 02 — 4s

**Voix** : Celle-ci active le moteur qui fait tourner les roues.

**Fonction** : Demonstrate how electrical energy converts to mechanical motion.

**Élément pédagogique** : Energy flow into the motor and rotor rotation

**Intention de mouvement** : `electromagnetic_rotation`

### Le raisonnement, avant le prompt

1. **information** : Electricity activates motor rotation.
2. **physical mechanism** : Electrical energy converts to mechanical torque.
3. **cause** : Electricity reaches the motor.
4. **effect** : Rotor inside the motor starts rotating.
5. **physical element** : Electric motor
6. **secondary elements** : Stator windings, rotor, electric flow
7. **visual behavior** : Yellow/orange energy enters and rotor rotation begins
8. **initial state** : Motor with visible rotor and stator from energy received
9. **animation movement** : Rotor starts rotating as energy enters
10. **secondary motion** : Drivetrain begins turning
11. **final state** : Rotor and drivetrain in smooth rotational motion
12. **camera position** : Close-up with slightly lower angle to capture rotor
13. **composition** : Full view of rotor and incoming energy flow

### Prompt image

```
Technical semi-cutaway view focused on the electric motor within the vehicle. The motor showcases visible rotor and stator with yellow-orange energy streams entering the stator windings. As the energy enters, visible electromagnetic effects occur around the rotor and the connected drivetrain is visible. Yellow-orange energy streams from the high-voltage cables enter the motor, with visible initial position of the adjacent wheel 'roue.' The battery connection leads to the motor, reinforcing continuity. Photorealistic premium 3D engineering visualization, the same modern dark near-black electric sedan in technical semi-cutaway view, realistic bodywork with internal components visible where the explanation needs them, dark premium studio environment, cinematic blue and white lighting, realistic detailed materials, physically credible automotive mechanics, clearly visible electrical and mechanical components, cinematic depth of field, high contrast, premium high-end car commercial rendering, vertical 9:16 composition, no text, no labels, no logos, no watermark.
```

### Prompt animation

```
Initially, the rotor is stationary. Yellow-orange electrical energy streams enter the motor windings; as they reach the motor, the rotor starts slowly rotating, accelerating smoothly, and gradually making the wheel rotate. The rotor's rotation causes the connected drivetrain to begin turning. Energy continues moving from the battery through the cables. The camera performs a controlled tracking movement around the rotor focusing on the energy transformation. Stator, casing, and chassis remain rigid. No deformation.
```

---

## Plan 03 — 4s

**Voix** : En freinage, l'énergie est renvoyée vers la batterie.

**Fonction** : Show how energy is recovered during braking.

**Élément pédagogique** : Regenerative braking with green energy return

**Intention de mouvement** : `regenerative_braking`

### Le raisonnement, avant le prompt

1. **information** : Energy is recovered in braking and returned to the battery.
2. **physical mechanism** : Mechanical energy converts to electrical and returns to battery.
3. **cause** : Brakes are applied, slowing down the car.
4. **effect** : Green energy visibly reverses toward the battery.
5. **physical element** : Wheels
6. **secondary elements** : Motor, cables, battery
7. **visual behavior** : Green energy flow travels backward through the circuit
8. **initial state** : Wheels rotating, energy flowing from prior state
9. **animation movement** : Green energy reverses along cables
10. **secondary motion** : Battery begins to recharge visually
11. **final state** : Green energy reaches battery, charging it
12. **camera position** : Dynamic overhead shot tracking energy flow backward
13. **composition** : Focus on wheels, cables, and path to battery

### Prompt image

```
A sectional dynamic overhead view of the car focusing on wheel assembly, brake system, and motor connection. Wheels visibly decelerate as green energy streams move from the wheels back through visible cables toward the motor and battery. The brake system is clearly visible as the point of deceleration initiation. The battery and motor remain visible, providing continuity of energy flow. Photorealistic premium 3D engineering visualization, the same modern dark near-black electric sedan in technical semi-cutaway view, realistic bodywork with internal components visible where the explanation needs them, dark premium studio environment, cinematic blue and white lighting, realistic detailed materials, physically credible automotive mechanics, clearly visible electrical and mechanical components, cinematic depth of field, high contrast, premium high-end car commercial rendering, vertical 9:16 composition, no text, no labels, no logos, no watermark.
```

### Prompt animation

```
Initially, the wheels are rotating smoothly. As brakes are applied, the wheels decelerate visibly and green energy streams in reverse, traveling from the wheels via cables back toward the motor, converting mechanical to electrical energy. That stream continues back to the battery, making the battery cells visibly active in accepting the charge. The camera follows the energy reversal path, allowing a clear view of this transformation, with the battery and motor geometry consistent. Wheels, chassis, cables, and vehicle structure remain steady.
```

---

## Ce que tu fais maintenant

1. Génère chaque **image** avec l'outil de ton choix, à partir du prompt image.
2. Génère chaque **animation** à partir de ton image, avec le prompt animation.
3. Dépose les vidéos dans `prototype/app/output/videos` nommées `shot_01.mp4`, `shot_02.mp4`…
4. Reviens : `analyser-videos`, puis `timeline`, puis `montage`.
