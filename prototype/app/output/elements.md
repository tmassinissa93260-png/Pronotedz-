# Fonctionnement d'une voiture électrique

16 secondes · 4 plans

## Ce que le sujet EST

Établi **avant** le script. Le storyboard suit cette chaîne.

- **components** : battery, inverter, electric motor, reduction gear, drivetrain, wheels
- **functions** : battery stores and supplies electrical energy, inverter converts and controls electrical energy, motor transforms electrical energy into mechanical energy, reduction gear and drivetrain transmit torque to wheels, wheels enable vehicular motion
- **energy direction** : from battery to wheels while driving; from wheels to battery during regenerative braking
- **transformations** : chemical to electrical energy in battery, DC to AC conversion in inverter, electrical to mechanical energy in motor
- **invisible phenomena** : electricity flow, electromagnetic fields in motor
- **acceptable simplifications** : motor as a key converter without detailing rotor-stator interaction at every mention
- **common errors** : ignoring inverter's role, depicting energy circulation, overly simplifying motor function

**Chaîne causale**

1. battery chemical energy -> electrical energy in the circuit
2. electrical energy -> power electronics and inverter action
3. inverter converts DC to AC -> motor receives AC
4. motor converts electrical energy to mechanical -> motor rotation
5. reduction gear and drivetrain transmit torque -> wheel rotation
6. wheel rotation -> vehicle motion
7. during regenerative braking: vehicle kinetic energy -> motor as generator
8. motor as generator -> electrical energy back to battery

## Script

Imaginez une voiture électrique silencieuse, mais puissante. La batterie stocke l'énergie chimique qui devient électrique. Cette énergie traverse l'inverseur qui la convertit et la contrôle, alimentant le moteur électrique. Le moteur transforme cette énergie en mouvement des roues, propulsant ainsi votre véhicule. Lors du freinage, le moteur récupère l'énergie pour recharger la batterie.

## Visual bible

À réutiliser dans **chaque** image. Les couleurs ont un sens fixe.

- **main subject** : Modern electric sedan
- **characters objects** : battery, inverter, motor, wires, wheels
- **vehicle** : same modern dark/black electric sedan
- **colors** : yellow/orange for electricity, green for energy recovery
- **environment** : dark premium studio
- **materials** : realistic automotive materials
- **lighting** : cinematic blue and white lighting
- **camera** : dynamic, revealing essential components
- **style 3d** : technical semi-cutaway view
- **realism** : high, photorealistic
- **invisible phenomena** : electricity as yellow/orange flow

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

**Voix** : Imaginez une voiture électrique silencieuse, mais puissante.

**Fonction** : Introduce the electric car and its key components.

**Élément pédagogique** : Semi-transparent view showing the main components of the electric car.

**Intention de mouvement** : `reveal`

### Le raisonnement, avant le prompt

1. **information** : Introduce the car and its essential components.
2. **physical mechanism** : The layout of electric car's internal components is crucial.
3. **cause** : The need to understand the fundamental setup of an electric car.
4. **effect** : The viewer sees the primary components of an electric car.
5. **physical element** : Semi-transparent car body
6. **secondary elements** : Battery, inverter, motor
7. **visual behavior** : Internal components gently illuminated to guide attention
8. **initial state** : Car body highlighted with non-visible components shaded.
9. **animation movement** : Illumination accentuates key components
10. **secondary motion** : Subtle pulsing light to draw attention to parts
11. **final state** : Components are defined by lighting within a static car
12. **camera position** : Profile view to encompass the entirety of components
13. **composition** : Car occupies the majority of the frame, components aligned vertically

### Prompt image

```
Side view of a modern dark electric sedan with a semi-transparent body revealing internal components: battery at the rear, inverter in the middle, and electric motor at the front. The car is stationary in a dark premium studio, illuminated with cinematic blue and white lighting. The internal components are visible with realistic material rendering, highlighting their placement within the car. Photorealistic premium 3D engineering visualization, the same modern dark near-black electric sedan in technical semi-cutaway view, realistic bodywork with internal components visible where the explanation needs them, dark premium studio environment, cinematic blue and white lighting, realistic detailed materials, physically credible automotive mechanics, clearly visible electrical and mechanical components, cinematic depth of field, high contrast, premium high-end car commercial rendering, vertical 9:16 composition, no text, no labels, no logos, no watermark.
```

### Prompt animation

```
Start with a stationary view of the car's interior components. As the narration introduces the car's power, emphasize the battery, inverter, and motor's role by adding soft pulsing light effects on these components without changing their position. The car and components remain physically unchanged. No movement beyond subtle lighting enhancements to focus attention.
```

---

## Ce que tu fais maintenant

1. Génère chaque **image** avec l'outil de ton choix, à partir du prompt image.
2. Génère chaque **animation** à partir de ton image, avec le prompt animation.
3. Dépose les vidéos dans `prototype/app/output/videos` nommées `shot_01.mp4`, `shot_02.mp4`…
4. Reviens : `analyser-videos`, puis `timeline`, puis `montage`.
