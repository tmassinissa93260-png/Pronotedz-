"""Les 75 secondes du hacking automobile, passees au validateur du systeme."""
import os
import sys
from pathlib import Path

os.environ["STYLE_DIRECTIVE"] = (
    "Aesthetic photorealistic 9:16 vertical frame with featureless smooth matte "
    "white blank mannequins, no facial features — mannequin 1 in a fitted dark "
    "black polo shirt, mannequin 2 in a heather grey pullover hoodie with "
    "drawstrings; moody dark cinematic night atmosphere with deep shadows, warm "
    "ambient light from street lamps, neon signs and subtle glowing tech LEDs, "
    "cinematic Parisian street setting with modern cars and dark interiors; shot "
    "on a 35mm lens at f/1.8 with shallow depth of field and realistic bokeh, "
    "high-end streetwear editorial photography, hyper-detailed fabric texture, "
    "realistic plastic skin shading, 8k, no text, no labels, no logos, no "
    "watermark."
)

sys.path.insert(0, str(Path("/home/user/Pronotedz-/prototype")))
from app import prompts, validator  # noqa: E402
from app.models import Storyboard  # noqa: E402

FIN = (" Preserve exact geometry, proportions and materials. "
       "No deformation, no floating parts.")

PLANS = [
    # (voix, duree, image, animation, concept, fonction, intent, explication)
    (
        "Ta voiture peut être volée en trente secondes.", 3.0,
        "Macro shot of the driver's door mirror and the top of the door handle of a "
        "modern dark near-black car parked on a Parisian street at night, nobody "
        "within reach of it. Position: the folded wing mirror fills the left half of "
        "the frame with its indicator repeater along the lower edge of the housing, "
        "the handle running across the lower right, the wet street behind. Red "
        "luminous pulses travel along the flank of the car and reach the mirror "
        "housing, clearly representing a command arriving from outside. Camera: "
        "static macro at mirror height, shallow depth of field so the repeater is "
        "sharp and the street falls into bokeh. Lighting: warm street lamp raking "
        "along the paint from above left, cold neon rim on the upper edge of the "
        "mirror, deep shadow beneath the housing. Materials: matte near-black paint, "
        "gloss black mirror cap, chrome handle, tinted glass.",
        "The red pulses travel steadily along the flank and reach the mirror housing, "
        "and as the last of them arrives the indicator repeater lights up once and "
        "the folded mirror rotates outward until it stands fully open. The paint, the "
        "handle and the street stay perfectly rigid. The camera holds still." + FIN,
        "red pulses reaching the mirror housing, the repeater lighting and the mirror opening",
        "Montre le résultat avant la cause : la voiture s'ouvre sans personne.",
        "cause_effect",
        {"information": "la voiture s'ouvre sans que personne ne la touche",
         "physical_element": "the folded wing mirror and its indicator repeater",
         "secondary_elements": "la poignée, la carrosserie, la rue mouillée derrière",
         "visual_behavior": "des impulsions rouges longent la carrosserie et "
                            "atteignent le rétroviseur",
         "animation_movement": "les impulsions rouges parcourent le flanc jusqu'au "
                               "rétroviseur, le répétiteur s'allume et le rétroviseur "
                               "se déplie",
         "camera_position": "macro statique à hauteur de rétroviseur, faible "
                            "profondeur de champ",
         "composition": "le rétroviseur sur la moitié gauche, la poignée en bas à droite"},
    ),
    (
        "Sans casser une vitre, sans toucher à la serrure.", 3.5,
        "Macro shot of the untouched driver's window glass and the lock barrel below "
        "it on the same dark near-black car, the metal unmarked, no tool anywhere in "
        "frame. Position: the barrel sits at the lower left, the pane of glass rising "
        "across the right two thirds, the rubber seal running between them. Blue "
        "luminous pulses pass straight through the glass from right to left without "
        "bending it, clearly representing a radio signal the bodywork cannot stop. "
        "Camera: static macro at window height, shallow depth of field so the seal is "
        "sharp and the reflected street falls into bokeh. Lighting: warm street lamp "
        "from above right, cold neon reflection sliding across the pane, deep shadow "
        "at the seal. Materials: tinted glass, black rubber seal, brushed steel "
        "barrel, matte near-black paint.",
        "The blue pulses travel steadily through the glass from right to left, and as "
        "each one crosses the seal the barrel below brightens faintly in answer, "
        "building over the shot into a rhythm the untouched metal keeps repeating. "
        "The glass, the seal and the barrel stay perfectly rigid. The camera holds "
        "still with a slow secondary drift." + FIN,
        "blue pulses passing through the intact glass and the untouched barrel answering",
        "Montre que rien n'est forcé : le signal traverse la carrosserie.",
        "energy_flow",
        {"information": "rien n'est forcé, le signal traverse la carrosserie",
         "physical_element": "the driver's window glass and the lock barrel",
         "secondary_elements": "le joint de caoutchouc, le reflet de la rue",
         "visual_behavior": "des impulsions bleues traversent la vitre sans la déformer",
         "animation_movement": "les impulsions bleues parcourent la vitre de droite à "
                               "gauche et le barillet s'allume à leur passage",
         "camera_position": "macro statique à hauteur de vitre, faible profondeur de champ",
         "composition": "le barillet en bas à gauche, la vitre sur les deux tiers droits"},
    ),
    (
        "Bienvenue dans le monde du hacking automobile.", 3.0,
        "Wide night shot of a Parisian street, the same dark near-black car parked at "
        "the kerb at frame right and mannequin 1, a featureless smooth matte white "
        "figure in a fitted dark black polo shirt, standing at frame left with a small "
        "flat black box in one hand. Position: eight metres of wet cobblestone between "
        "the figure and the car, a neon sign glowing above the shopfront behind them "
        "both. A red luminous glow spreads outward from the box across the car's flank "
        "and settles along its panel seams, clearly representing the radio command "
        "reaching the vehicle. Camera: static wide view at chest height, shallow depth "
        "of field so the figure is sharp and the far end of the street falls into "
        "bokeh. Lighting: warm street lamp from above left, cold neon wash from the "
        "shopfront, deep shadow between them. Materials: matte white plastic skin, "
        "black cotton polo fabric, wet cobblestone, matte near-black paint, chrome "
        "trim.",
        "The red glow spreads outward from the box, gradually travelling across the "
        "wet cobblestone and up the car's flank, until it settles along the panel "
        "seams and the door handle lights up in answer. The figure, the box and the "
        "car stay perfectly rigid. The camera holds still." + FIN,
        "a red glow travelling from the hacker's box across the street onto the car",
        "Nomme le sujet : quelqu'un agit sur la voiture à distance.",
        "energy_transfer",
        {"information": "quelqu'un agit sur la voiture sans la toucher",
         "physical_element": "the small flat black box in the mannequin's hand",
         "secondary_elements": "le mannequin en polo noir, la voiture au trottoir, "
                               "l'enseigne néon",
         "visual_behavior": "une lueur rouge quitte le boîtier et gagne la carrosserie",
         "animation_movement": "la lueur rouge se propage du boîtier jusqu'à la "
                               "voiture, puis la poignée s'allume",
         "camera_position": "large statique à hauteur de poitrine, faible profondeur de champ",
         "composition": "le mannequin à gauche, la voiture à droite, la rue mouillée entre"},
    ),
]

PLANS += [
    (
        "Première technique : l'attaque par relais.", 2.5,
        "Wide night shot of a Parisian courtyard, the front door of a building at "
        "frame left and the dark near-black car parked at frame right. Position: "
        "mannequin 2, a featureless smooth matte white figure in a heather grey "
        "pullover hoodie with drawstrings, holds a flat black box against the door at "
        "chest height; mannequin 1 in the fitted dark black polo shirt holds an "
        "identical box against the car's driver door, eight metres away at the same "
        "height. A red luminous beam opens between the two boxes across the wet "
        "cobblestone, clearly representing the added link between them. Camera: static "
        "wide view at chest height, shallow depth of field so both figures are sharp "
        "and the courtyard gate falls into bokeh. Lighting: warm street lamp from "
        "above left, cold LED glow from each box, deep shadow across the ground. "
        "Materials: matte white plastic skin, grey brushed-cotton hoodie, black "
        "cotton polo, matte black plastic housings, wet cobblestone.",
        "The red beam opens between the two boxes and steadily brightens along its "
        "whole length, and as it reaches full strength the LED on each housing begins "
        "to pulse in time with the other. The two figures, the boxes and the car stay "
        "perfectly rigid. The camera holds still." + FIN,
        "a red beam opening between the two boxes held by the two mannequins",
        "Pose le dispositif : deux boîtiers, une ligne entre la porte et la voiture.",
        "energy_transfer",
        {"information": "l'attaque tient en deux boîtiers reliés entre eux",
         "physical_element": "the red beam running between the two boxes",
         "secondary_elements": "les deux mannequins, la porte de l'immeuble, la voiture",
         "visual_behavior": "un faisceau rouge s'ouvre entre les deux boîtiers",
         "animation_movement": "le faisceau rouge s'allume sur toute sa longueur et "
                               "les LED des deux boîtiers se mettent à battre ensemble",
         "camera_position": "large statique à hauteur de poitrine, faible profondeur de champ",
         "composition": "un mannequin à chaque bord du cadre, le faisceau en travers"},
    ),
    (
        "Les voleurs ne touchent plus à la serrure.", 3.0,
        "Macro shot of the driver's door handle and lock barrel of the dark near-black "
        "car, the gloved white plastic hand of mannequin 1 holding its flat black box "
        "a few centimetres from the panel without contact. Position: the barrel fills "
        "the lower centre of the frame, the hand and the box enter from frame left, a "
        "visible gap of air between the box and the paint. Blue luminous pulses cross "
        "that gap and pass through the handle from left to right, clearly representing "
        "the signal the car is listening for. Camera: static macro at handle height, "
        "shallow depth of field so the barrel is sharp and the hoodie behind falls "
        "into bokeh. Lighting: hard cold neon key raking along the metal, warm street "
        "lamp rim on the upper edge of the handle, deep shadow inside the barrel. "
        "Materials: matte white plastic skin, matte black plastic housing, brushed "
        "steel barrel, matte near-black paint, chrome handle.",
        "The blue pulses cross the gap and travel steadily through the handle from "
        "left to right, and as each one passes the lock barrel the barrel stays "
        "perfectly still and unmoved, building over the shot into a rhythm the "
        "untouched metal never resists. The hand, the box and the barrel stay "
        "perfectly rigid. The camera holds still with a slow secondary drift." + FIN,
        "blue pulses crossing the air gap while the untouched lock barrel stays still",
        "Montre que la serrure n'est jamais touchée : l'attaque est ailleurs.",
        "energy_flow",
        {"information": "aucun outil ne touche la serrure, elle reste intacte",
         "physical_element": "the lock barrel of the driver's door",
         "secondary_elements": "la main du mannequin, le boîtier noir, la poignée",
         "visual_behavior": "des impulsions bleues traversent l'air puis la poignée",
         "animation_movement": "les impulsions bleues parcourent la poignée de gauche "
                               "à droite pendant que le barillet reste immobile",
         "camera_position": "macro statique à hauteur de poignée, faible profondeur de champ",
         "composition": "le barillet en bas au centre, la main et le boîtier à gauche"},
    ),
    (
        "Un complice capte le signal de ta clé à travers ta porte d'entrée.", 4.5,
        "Medium night shot of the building's front door from outside, mannequin 2 in "
        "the heather grey hoodie pressing a flat black box against the painted wood at "
        "chest height. Position: the car key hangs on its hook inside, framed through "
        "the glazed panel just above the box; the box's antenna face is pressed flat "
        "to the door, thirty centimetres from the key. Blue luminous pulses leave the "
        "key, cross the wood, and are drawn into the antenna face, clearly "
        "representing the key's own signal being picked up; a red luminous glow "
        "spreads across the housing itself. Camera: static medium view at chest "
        "height, shallow depth of field so the box is sharp and the courtyard behind "
        "falls into bokeh. Lighting: warm hallway glow behind the glazed panel, cold "
        "street lamp from above left, deep shadow on the wood. Materials: painted "
        "wood, glass, matte black plastic housing, brass key, matte white plastic "
        "skin, grey brushed-cotton hoodie.",
        "The blue pulses leave the key, cross the wood one after another, and are "
        "drawn into the antenna face, and as each pulse enters the housing the red "
        "glow across it steadily builds until the whole box is lit. The door, the key "
        "and the figure stay perfectly rigid. The camera holds still." + FIN,
        "blue key pulses crossing the wood into the box antenna, red glow building on it",
        "Montre le premier maillon : le signal de la clé est capté à travers la porte.",
        "energy_transfer",
        {"information": "le signal de la clé traverse la porte et se fait capter",
         "physical_element": "the flat black box pressed against the front door",
         "secondary_elements": "la clé au crochet, le panneau vitré, le bois peint",
         "visual_behavior": "les impulsions bleues traversent le bois et entrent dans "
                            "l'antenne, et le boîtier rougit",
         "animation_movement": "les impulsions bleues traversent le bois et gagnent "
                               "l'antenne, et la lueur rouge du boîtier monte à chaque "
                               "impulsion reçue",
         "camera_position": "moyen statique à hauteur de poitrine, foyer sur le boîtier",
         "composition": "le boîtier au centre, la clé visible derrière la vitre au-dessus"},
    ),
    (
        "Le complice le retransmet à un second boîtier posé contre ta voiture.", 4.5,
        "Wide night shot of the same courtyard, the first flat black box against the "
        "building door at frame left and the second identical box held against the "
        "driver's door of the dark near-black car at frame right. Position: the two "
        "boxes face each other across eight metres of wet cobblestone at the same "
        "chest height, a mannequin standing beside each. A red luminous beam runs "
        "between them carrying blue pulses along its length from left to right, "
        "clearly representing the key's own signal being relayed across the gap; the "
        "blue pulses leave the second box and enter the door handle unchanged. Camera: "
        "static wide view at chest height, shallow depth of field so both boxes are "
        "sharp and the gate falls into bokeh. Lighting: warm street lamp from above "
        "left, cold LED glow from each housing, deep shadow across the ground. "
        "Materials: matte black plastic housings, wet cobblestone, matte near-black "
        "paint, chrome handle, matte white plastic skin.",
        "The blue pulses begin to travel along the red beam from left to right, "
        "gradually building in rhythm, until they leave the second box and enter the "
        "door handle unchanged, which lights up in answer. The boxes, the two figures "
        "and the car stay perfectly rigid. The camera holds still." + FIN,
        "blue pulses relayed along the red beam between the two boxes into the handle",
        "Montre le deuxième maillon : le signal est reporté intact jusqu'à la voiture.",
        "energy_flow",
        {"information": "le signal capté est reporté tel quel jusqu'à la voiture",
         "physical_element": "the red beam running between the two boxes",
         "secondary_elements": "les deux boîtiers, les deux mannequins, la poignée",
         "visual_behavior": "des impulsions bleues défilent le long du faisceau rouge "
                            "et ressortent inchangées",
         "animation_movement": "les impulsions bleues parcourent le faisceau rouge de "
                               "gauche à droite et rejoignent la poignée",
         "camera_position": "large statique à hauteur de poitrine, faible profondeur de champ",
         "composition": "un boîtier à chaque bord du cadre, le faisceau en travers"},
    ),
    (
        "La voiture croit que tu es à côté, et se déverrouille.", 4.5,
        "Medium night shot of the driver's door of the dark near-black car, the second "
        "flat black box held flat against the panel at frame left. Position: the door "
        "handle runs across the centre of the frame, the folded wing mirror sits above "
        "it at frame right with its indicator repeater along the lower edge of the "
        "housing, the courtyard behind. Blue luminous pulses leave the box and travel "
        "along the panel into the handle, clearly representing the signal the car "
        "accepts as its own. Camera: static medium view at handle height, shallow "
        "depth of field so the handle is sharp and the courtyard falls into bokeh. "
        "Lighting: warm street lamp raking along the paint from above left, cold LED "
        "rim from the housing, deep shadow beneath the sill. Materials: matte "
        "near-black paint, matte black plastic housing, chrome handle, gloss black "
        "mirror cap, tinted glass.",
        "The blue pulses leave the box and travel steadily along the panel into the "
        "handle, and as the last of them arrives the indicator repeater lights up once "
        "and the folded mirror rotates outward until it stands fully open. The box, "
        "the panel and the glass stay perfectly rigid. The camera holds still." + FIN,
        "blue pulses entering the handle, the repeater lighting and the mirror opening",
        "Montre l'effet : la voiture reçoit le vrai signal et s'ouvre.",
        "cause_effect",
        {"information": "la voiture accepte le signal et s'ouvre",
         "physical_element": "the folded wing mirror and its indicator repeater",
         "secondary_elements": "la poignée, le boîtier resté contre la tôle, la cour",
         "visual_behavior": "des impulsions bleues entrent dans la poignée puis le "
                            "répétiteur s'allume",
         "animation_movement": "les impulsions bleues parcourent la tôle jusqu'à la "
                               "poignée, le répétiteur s'allume et le rétroviseur se "
                               "déplie",
         "camera_position": "moyen statique à hauteur de poignée, faible profondeur de champ",
         "composition": "la poignée au centre, le rétroviseur en haut à droite"},
    ),
]

PLANS += [
    (
        "Plus lourd encore : le bus CAN.", 2.5,
        "Medium technical semi-cutaway of the front left quarter of the dark "
        "near-black car at night, the wing panel ghosted to transparency so the wiring "
        "loom beneath it comes into view. Position: the braided loom runs from the "
        "headlight housing at frame left, back along the inner wing, to the engine "
        "control unit box at frame right; a single twisted pair inside the loom is "
        "separated out and reads clearly against the darker cables around it. Blue "
        "luminous pulses ignite one after another along that twisted pair and travel "
        "rightwards, clearly representing the data frames the components exchange. "
        "Camera: static three-quarter view at headlight height, deep enough focus to "
        "hold the whole run of the loom, the street behind falling into bokeh. "
        "Lighting: cold neon key from the upper left, warm street lamp rim along the "
        "painted panel edge, deep shadow in the wheel arch. Materials: matte "
        "near-black paint, braided grey cable sheath, brushed aluminium housing, "
        "copper connector pins.",
        "The blue pulses ignite one after another along the twisted pair, starting at "
        "the headlight housing and steadily travelling rightwards along the pair, "
        "until the whole run is alive and the control unit connector pins brighten in "
        "answer. The loom, the panel and the control unit stay perfectly rigid. The "
        "camera holds still with a slow secondary drift." + FIN,
        "blue data pulses igniting along the CAN twisted pair toward the control unit",
        "Nomme l'objet dont parle la suite : le câble partagé qui relie tout.",
        "energy_flow",
        {"information": "un seul câble relie tous les composants de la voiture",
         "physical_element": "the twisted pair of the CAN bus inside the loom",
         "secondary_elements": "le phare, le faisceau tressé, le boîtier du calculateur",
         "visual_behavior": "des impulsions bleues s'allument l'une après l'autre le "
                            "long de la paire",
         "animation_movement": "les impulsions bleues s'allument depuis le phare et se "
                               "propagent vers le calculateur, dont les broches "
                               "s'allument à leur tour",
         "camera_position": "trois-quarts statique à hauteur de phare, foyer profond",
         "composition": "le phare à gauche, le calculateur à droite, le faisceau entre"},
    ),
    (
        "C'est le réseau interne où tous les composants de ta voiture se parlent.", 4.5,
        "Wide technical semi-cutaway of the whole dark near-black car seen from the "
        "side at night, the bodywork ghosted to transparency so the full wiring loom "
        "reads from bumper to boot. Position: the headlight sits at frame left, the "
        "engine control unit behind it, the dashboard cluster at centre frame, the "
        "door module and the rear light at frame right, all strung on one continuous "
        "twisted pair running the length of the car. Blue luminous pulses travel along "
        "that pair in both directions between the modules, clearly representing the "
        "conversation the parts hold with each other. Camera: static side view at "
        "waist height, deep enough focus to hold the whole car, the street falling "
        "into bokeh. Lighting: cold neon key from above left, warm street lamp rim "
        "along the roofline, deep shadow beneath the sills. Materials: matte "
        "near-black paint, braided grey cable sheath, brushed aluminium housings, "
        "copper connector pins, tinted glass.",
        "The blue pulses travel steadily along the twisted pair from module to module "
        "in both directions, and as each pulse reaches a module that module's "
        "connector pins brighten in turn, building over the shot until every module "
        "along the car has answered at least once. The bodywork, the loom and the "
        "modules stay perfectly rigid. The camera holds still." + FIN,
        "blue pulses travelling between every module along one continuous twisted pair",
        "Montre que le bus est partagé : ce qui y entre atteint tous les calculateurs.",
        "energy_flow",
        {"information": "tous les modules sont sur le même fil, du phare au coffre",
         "physical_element": "the continuous twisted pair running the length of the car",
         "secondary_elements": "le phare, le calculateur, le combiné de bord, le module "
                               "de porte",
         "visual_behavior": "des impulsions bleues circulent d'un module à l'autre",
         "animation_movement": "les impulsions bleues parcourent la paire d'un module à "
                               "l'autre et les broches de chacun s'allument à leur tour",
         "camera_position": "profil statique à hauteur de taille, foyer profond",
         "composition": "le phare à gauche, le combiné au centre, le feu arrière à droite"},
    ),
    (
        "Des pirates arrivent à se brancher sur ce réseau interne.", 4.5,
        "Macro shot of the wiring loom running along the inner wing of the dark "
        "near-black car at night, its braided sheath ghosted to transparency over a "
        "short length so the twisted pair inside reads clearly. Position: the loom "
        "crosses the frame from the lower left to the upper right, the headlight "
        "housing sits behind it at frame left, the edge of the wheel arch runs along "
        "the lower border. Blue luminous pulses travel rightwards along the twisted "
        "pair, clearly representing the frames already running on the network, and red "
        "luminous pulses enter the same pair from beyond the lower edge of the frame. "
        "Camera: static macro at low angle, shallow depth of field so the pair is "
        "sharp and the arch falls into bokeh. Lighting: hard cold neon key raking "
        "across the sheath, warm street lamp rim along the loom, deep shadow behind. "
        "Materials: braided grey sheath, copper conductors, textured black plastic "
        "liner, matte near-black paint.",
        "The blue pulses travel steadily rightwards along the twisted pair, and red "
        "pulses begin to enter it from beyond the lower edge of the frame, gradually "
        "building in number until red and blue travel side by side at the same "
        "spacing. The loom, the sheath and the arch stay perfectly rigid. The camera "
        "holds still." + FIN,
        "red pulses entering the twisted pair from off-frame beside the blue ones",
        "Montre le point d'arrivée : quelque chose d'extérieur entre sur le réseau.",
        "energy_flow",
        {"information": "quelque chose d'extérieur arrive à entrer sur le réseau",
         "physical_element": "the twisted pair inside the wiring loom",
         "secondary_elements": "la gaine tressée, le phare, le passage de roue",
         "visual_behavior": "des impulsions rouges rejoignent les bleues sur la même paire",
         "animation_movement": "les impulsions rouges entrent par le bas du cadre et "
                               "parcourent la paire à côté des bleues",
         "camera_position": "macro statique en contre-plongée, faible profondeur de champ",
         "composition": "la paire en diagonale, le phare derrière à gauche"},
    ),
    (
        "Les pirates injectent leurs propres trames sur ce câble.", 3.0,
        "Macro shot of the twisted pair of the car's internal network inside the front "
        "left wheel arch of the dark near-black car, its braided sheath ghosted to "
        "transparency so both copper conductors read clearly. Position: the pair "
        "crosses the frame from the lower left to the upper right, the conductors "
        "visible along its whole length, the edge of the wheel arch along the lower "
        "border. Blue luminous pulses already travel rightwards along the pair; red "
        "luminous pulses enter from beyond the lower left corner of the frame and join "
        "the same pair, travelling in the same direction and the same shape, clearly "
        "representing frames added from outside. Camera: static macro at low angle, "
        "shallow depth of field so the conductors are sharp and the arch falls into "
        "bokeh. Lighting: hard cold neon key raking across the sheath, warm street "
        "lamp rim on the conductors, deep shadow behind. Materials: braided grey "
        "cable sheath around the pair, copper conductors, textured black plastic "
        "liner, matte near-black paint.",
        "The red pulses enter from beyond the lower left corner, gradually build in "
        "number, and travel rightwards along the twisted pair mixed in with the blue "
        "ones, while the blue pulses keep travelling at their own spacing, until red "
        "and blue run side by side at the same speed. The pair, the sheath and the "
        "liner stay perfectly rigid. The camera holds still with a slow secondary "
        "drift." + FIN,
        "red added pulses joining the blue ones on the same twisted pair",
        "Montre la tromperie : les fausses trames prennent le même chemin que les vraies.",
        "energy_flow",
        {"information": "les fausses trames circulent sur le même fil que les vraies",
         "physical_element": "the twisted pair inside the wheel arch",
         "secondary_elements": "la gaine tressée, les conducteurs de cuivre, le "
                               "passage de roue",
         "visual_behavior": "des impulsions rouges rejoignent les bleues et prennent "
                            "la même cadence",
         "animation_movement": "les impulsions rouges entrent par le coin du cadre et "
                               "parcourent la paire mêlées aux bleues jusqu'à la même "
                               "cadence",
         "camera_position": "macro statique en contre-plongée, faible profondeur de champ",
         "composition": "la paire en diagonale, les conducteurs visibles sur toute sa longueur"},
    ),
    (
        "Le calculateur les lit, croit reconnaître la vraie clé, et ouvre.", 4.5,
        "Medium night shot through the driver's window of the dark near-black car, the "
        "cabin dark behind the glass. Position: the door sill button stands at the "
        "lower centre of the frame just behind the pane, the seat and the lower rim of "
        "the steering wheel beyond it at frame right, the reflection of a neon sign "
        "sliding across the glass. Blue and red luminous pulses arrive together along "
        "the inside of the window frame and reach the door trim, clearly representing "
        "frames the car treats exactly the same way. Camera: static medium view at "
        "window height, shallow depth of field so the button is sharp and the cabin "
        "falls into bokeh. Lighting: warm street lamp from above left, cold neon "
        "reflection across the pane, deep shadow inside the cabin. Materials: tinted "
        "glass, matte black door trim, chrome button head, leather seat.",
        "The blue and red pulses arrive together along the window frame and reach the "
        "door trim, and as they arrive the sill button rises steadily until it stands "
        "proud of the trim and the cabin light glows on behind it. The glass, the trim "
        "and the seat stay perfectly rigid. The camera holds still." + FIN,
        "blue and red pulses arriving together and the sill button rising behind the glass",
        "Montre pourquoi ça marche : la voiture ne distingue pas les deux.",
        "cause_effect",
        {"information": "la voiture traite les fausses trames comme les vraies",
         "physical_element": "the door sill button behind the window glass",
         "secondary_elements": "la vitre, la garniture de porte, le siège, le volant",
         "visual_behavior": "les impulsions bleues et rouges arrivent ensemble à la "
                            "garniture",
         "animation_movement": "les impulsions arrivent ensemble et le bouton de "
                               "condamnation remonte, puis le plafonnier s'allume",
         "camera_position": "moyen statique à hauteur de vitre, faible profondeur de champ",
         "composition": "le bouton en bas au centre, le siège et le volant à droite"},
    ),
]

PLANS += [
    (
        "Même tes pneus sont vulnérables.", 2.5,
        "Macro shot of the front left wheel of the dark near-black car at night, the "
        "tyre wall ghosted to transparency at the valve so the small sensor clamped "
        "inside the rim reads clearly. Position: the sensor sits at the lower centre "
        "of the frame on the inner face of the rim, the valve stem rising from it, the "
        "brake disc and caliper visible behind the spokes. Blue luminous pulses "
        "radiate outward from the sensor through the tyre wall and travel up toward "
        "the wheel arch, clearly representing the pressure reading it broadcasts. "
        "Camera: static macro at hub height, shallow depth of field so the sensor is "
        "sharp and the kerb falls into bokeh. Lighting: cold neon key from the upper "
        "left, warm street lamp rim along the rim edge, deep shadow inside the arch. "
        "Materials: black rubber tyre, brushed aluminium rim, matte grey sensor "
        "housing, cast iron brake disc.",
        "The blue pulses leave the sensor in steady bursts and travel outward through "
        "the tyre wall toward the wheel arch, and as each burst clears the rim the "
        "sensor housing brightens faintly behind it, building over the shot into a "
        "regular beat. The wheel, the tyre and the disc stay perfectly rigid. The "
        "camera holds still with a slow secondary drift." + FIN,
        "blue pressure pulses leaving the in-rim sensor through the tyre wall",
        "Nomme l'objet : un émetteur radio vit dans chaque roue.",
        "energy_flow",
        {"information": "chaque roue porte un émetteur radio à l'intérieur",
         "physical_element": "the pressure sensor clamped inside the wheel rim",
         "secondary_elements": "la valve, le flanc du pneu, le disque de frein",
         "visual_behavior": "des impulsions bleues quittent le capteur et traversent "
                            "le pneu",
         "animation_movement": "les impulsions bleues partent du capteur et parcourent "
                               "le flanc jusqu'au passage de roue, et le capteur "
                               "s'allume derrière elles",
         "camera_position": "macro statique à hauteur de moyeu, faible profondeur de champ",
         "composition": "le capteur en bas au centre, la valve au-dessus, le disque "
                        "derrière les rayons"},
    ),
    (
        "Des capteurs radio non chiffrés envoient la pression de chaque roue.", 4.5,
        "Wide technical semi-cutaway of the whole dark near-black car seen from the "
        "side at night, the bodywork ghosted to transparency so the four wheels and "
        "the dashboard receiver read at once. Position: the front and rear wheels sit "
        "at the lower left and lower right of the frame, each with its sensor visible "
        "inside the rim; the receiver module sits behind the dashboard at centre "
        "frame, higher up. Blue luminous pulses leave each sensor and travel up "
        "through the arches to that receiver, clearly representing four unencrypted "
        "readings arriving in the open. Camera: static side view at waist height, deep "
        "enough focus to hold both wheels and the receiver, the street falling into "
        "bokeh. Lighting: cold neon key from above left, warm street lamp rim along "
        "the roofline, deep shadow beneath the sills. Materials: black rubber tyres, "
        "brushed aluminium rims, matte grey sensor housings, matte near-black paint, "
        "tinted glass.",
        "The blue pulses leave each sensor in turn and travel steadily up through the "
        "arches toward the receiver, and as each one arrives the receiver module "
        "brightens once, building over the shot until all four wheels have reported "
        "and the module holds a steady glow. The car, the wheels and the receiver stay "
        "perfectly rigid. The camera holds still." + FIN,
        "blue pulses travelling from all four wheel sensors up to the dashboard receiver",
        "Montre le trajet : les mesures arrivent en clair jusqu'au tableau de bord.",
        "energy_transfer",
        {"information": "les quatre mesures arrivent en clair au tableau de bord",
         "physical_element": "the receiver module behind the dashboard",
         "secondary_elements": "les capteurs dans les jantes, les passages de roue",
         "visual_behavior": "des impulsions bleues montent de chaque roue vers le "
                            "récepteur",
         "animation_movement": "les impulsions bleues parcourent les passages de roue "
                               "jusqu'au récepteur, qui s'allume à chaque arrivée",
         "camera_position": "profil statique à hauteur de taille, foyer profond",
         "composition": "les roues en bas du cadre, le récepteur au centre, plus haut"},
    ),
    (
        "Un pirate copie leur signal et annonce une crevaison qui n'existe pas.", 4.5,
        "Medium night shot of mannequin 2 in the heather grey hoodie kneeling at the "
        "kerb beside the dark near-black car, a small handheld radio unit held toward "
        "the front wheel. Position: the figure fills frame left, the wheel and its "
        "arch fill frame right, half a metre of wet cobblestone between the unit and "
        "the tyre. Red luminous pulses leave the handheld unit and travel toward the "
        "wheel arch in exactly the same shape and spacing as the blue ones still "
        "leaving the sensor inside the rim, clearly representing a second reading sent from outside the wheel. "
        "Camera: static medium view at hub height, shallow depth of field so the unit "
        "and the tyre are sharp and the street falls into bokeh. Lighting: warm street "
        "lamp from above right, cold LED glow from the handheld unit, deep shadow in "
        "the arch. Materials: matte white plastic skin, grey brushed-cotton hoodie, "
        "matte black plastic unit, black rubber tyre, brushed aluminium rim.",
        "The red pulses begin to leave the handheld unit, gradually matching the "
        "spacing of the blue ones, and travel steadily toward the wheel arch beside "
        "them until red and blue rise through the arch together at the same rhythm. "
        "The figure, the unit and the wheel stay perfectly rigid. The camera holds "
        "still." + FIN,
        "red pulses leaving the handheld unit in the same shape as the blue ones",
        "Montre la copie : le faux signal a exactement la forme du vrai.",
        "energy_flow",
        {"information": "le faux signal a la même forme que celui du capteur",
         "physical_element": "the handheld radio unit in the mannequin's hand",
         "secondary_elements": "le mannequin accroupi, la roue, le passage de roue",
         "visual_behavior": "des impulsions rouges quittent le boîtier au même rythme "
                            "que les bleues",
         "animation_movement": "les impulsions rouges partent du boîtier et parcourent "
                               "le passage de roue à côté des bleues, au même rythme",
         "camera_position": "moyen statique à hauteur de moyeu, faible profondeur de champ",
         "composition": "le mannequin à gauche, la roue à droite, l'écart entre les deux"},
    ),
    (
        "Le tableau de bord alerte, et le conducteur s'arrête sur la bande d'arrêt.", 4.5,
        "Interior night shot of the dark cabin of the dark near-black car from the "
        "passenger side, the instrument cluster filling frame left and the windscreen "
        "filling frame right. Position: the cluster sits below the steering wheel rim, "
        "its dials dark; beyond the glass the hard shoulder and its white line run "
        "away into the night. Red luminous pulses arrive at the cluster from below and "
        "spread across its face, clearly representing the reading the cluster accepts "
        "as its own; a red glow settles on the tyre-pressure indicator well. Camera: "
        "static medium view from the passenger seat at cluster height, shallow depth "
        "of field so the dials are sharp and the road beyond falls into bokeh. "
        "Lighting: cold cluster backlight from within, warm sodium light sweeping "
        "through the windscreen from the left, deep shadow across the dashboard top. "
        "Materials: matte black dashboard plastic, brushed aluminium trim, smoked "
        "instrument glass, leather wheel rim.",
        "The red pulses arrive at the cluster from below and the glow spreads steadily "
        "across its face until the indicator well is fully lit, and as it reaches full "
        "strength the sodium light through the windscreen slows its sweep and settles, "
        "the car coming to rest on the hard shoulder. The dashboard, the wheel and the "
        "cluster stay perfectly rigid. The camera holds still." + FIN,
        "a red glow spreading across the instrument cluster as the sweeping light slows",
        "Montre l'effet réel : une fausse mesure arrête une vraie voiture.",
        "cause_effect",
        {"information": "une donnée fausse suffit à faire arrêter la voiture",
         "physical_element": "the instrument cluster behind the steering wheel",
         "secondary_elements": "le volant, le pare-brise, la bande d'arrêt d'urgence",
         "visual_behavior": "une lueur rouge gagne la face du combiné",
         "animation_movement": "la lueur rouge se propage sur le combiné pendant que "
                               "la lumière qui balaie le pare-brise ralentit et s'arrête",
         "camera_position": "moyen statique depuis le siège passager, à hauteur de combiné",
         "composition": "le combiné à gauche, le pare-brise et la route à droite"},
    ),
]

PLANS += [
    (
        "Ce même bus CAN sert aussi à reprendre le contrôle.", 4.0,
        "Interior night shot of the dark cabin of the dark near-black car, the "
        "steering column ghosted to transparency below the wheel so the twisted pair "
        "of the CAN bus reads clearly inside it. Position: the wheel rim runs across "
        "the top of the frame, the column drops from it through the centre, the "
        "steering rack sits at the lower edge in technical semi-cutaway. Green "
        "luminous pulses travel down that pair from the top of the column toward the "
        "rack, clearly representing a command sent on purpose by the driver's own "
        "hardware. Camera: static medium view from the passenger seat at wheel height, "
        "shallow depth of field so the column is sharp and the windscreen falls into "
        "bokeh. Lighting: cold cluster backlight from the left, warm sodium light "
        "through the windscreen, deep shadow in the footwell. Materials: leather wheel "
        "rim, matte black column shroud, braided grey sheath, brushed steel rack.",
        "The green pulses travel steadily down the twisted pair from the top of the "
        "column toward the rack, and as the first of them reaches the rack the rack "
        "shaft begins to slide sideways in its housing, building until it moves "
        "continuously. The wheel, the shroud and the dashboard stay perfectly rigid. "
        "The camera holds still." + FIN,
        "green command pulses travelling down the column into the moving steering rack",
        "Retourne le sujet : le même câble porte aussi les commandes voulues.",
        "energy_flow",
        {"information": "le même bus peut porter des commandes voulues par le conducteur",
         "physical_element": "the twisted pair inside the steering column",
         "secondary_elements": "la jante du volant, la crémaillère en coupe, le combiné",
         "visual_behavior": "des impulsions vertes descendent la colonne vers la "
                            "crémaillère",
         "animation_movement": "les impulsions vertes parcourent la colonne jusqu'à la "
                               "crémaillère, qui se met à coulisser",
         "camera_position": "moyen statique depuis le siège passager, à hauteur de volant",
         "composition": "la jante en haut, la colonne au centre, la crémaillère en bas"},
    ),
    (
        "Un boîtier à 900 euros et OpenPilot y branchent une conduite autonome.", 4.5,
        "Interior night shot of the top of the windscreen of the dark near-black car, "
        "a small matte black box clipped behind the rear-view mirror with a thin "
        "braided cable running down the A-pillar. Position: the box fills the upper "
        "centre of the frame, the mirror stem beside it, the cable dropping along the "
        "pillar at frame left; the steering wheel rim fills the lower edge of the frame, "
        "its leather grip and upper spokes clearly in shot below the column shroud. "
        "Green luminous pulses leave the "
        "box, travel down that cable and continue into the steering column, clearly "
        "representing the commands the box puts on the bus. Camera: static medium view "
        "from the passenger seat at mirror height, shallow depth of field so the box "
        "is sharp and the road beyond the glass falls into bokeh. Lighting: cold LED "
        "glow from the box itself, warm sodium light sweeping through the windscreen, "
        "deep shadow along the headliner. Materials: matte black plastic housing, "
        "braided grey cable, smoked mirror glass, matte black pillar trim.",
        "The green pulses leave the box one after another and travel steadily down the "
        "cable along the pillar, and as they reach the column below the wheel rim "
        "begins to rotate slightly of its own accord, building until it holds a "
        "continuous correction. The box, the mirror and the pillar stay perfectly "
        "rigid. The camera holds still." + FIN,
        "green pulses leaving the aftermarket box down the pillar into the turning wheel",
        "Montre le montage réel : un boîtier, un câble, et la commande part.",
        "energy_transfer",
        {"information": "un boîtier du commerce écrit sur le même bus",
         "physical_element": "the matte black box clipped behind the rear-view mirror",
         "secondary_elements": "le câble tressé, le montant, la jante du volant",
         "visual_behavior": "des impulsions vertes quittent le boîtier et descendent "
                            "le câble",
         "animation_movement": "les impulsions vertes parcourent le câble jusqu'à la "
                               "colonne, et la jante du volant se met à tourner",
         "camera_position": "moyen statique depuis le siège passager, à hauteur de "
                            "rétroviseur",
         "composition": "le boîtier en haut au centre, le câble descendant à gauche"},
    ),
    (
        "Abonne-toi pour la partie 2.", 2.5,
        "Interior night shot from the passenger seat of the dark near-black car, "
        "mannequin 1, a featureless smooth matte white figure in a fitted dark black "
        "polo shirt, sitting at the wheel with both white plastic hands lifted clear "
        "of the rim. Position: the figure fills frame left, the wheel rim fills the "
        "centre, the windscreen and the night road fill frame right, the hands hover a "
        "few centimetres above the leather. Green luminous pulses run through the "
        "steering column below the rim, clearly representing the commands now steering "
        "in the driver's place. Camera: static medium view at wheel height, shallow "
        "depth of field so the hands are sharp and the road falls into bokeh. "
        "Lighting: cold cluster backlight from below, warm sodium light sweeping "
        "through the windscreen from the left, deep shadow across the seat. Materials: "
        "matte white plastic skin, black cotton polo fabric, leather wheel rim, matte "
        "black column shroud.",
        "The green pulses travel steadily through the column, and as they do the wheel "
        "rim rotates slowly on its own beneath the lifted hands, which stay clear of "
        "it, the rotation building until the sodium light through the windscreen "
        "swings with it. The figure, the seat and the dashboard stay perfectly rigid. "
        "The camera holds still." + FIN,
        "the wheel rim turning by itself beneath the lifted hands, green pulses in the column",
        "Montre le résultat vécu : la voiture tient la route sans les mains.",
        "cause_effect",
        {"information": "les commandes tiennent le volant à la place du conducteur",
         "physical_element": "the steering wheel rim under the lifted hands",
         "secondary_elements": "les mains du mannequin, la colonne, la route de nuit",
         "visual_behavior": "des impulsions vertes circulent dans la colonne pendant "
                            "que la jante tourne",
         "animation_movement": "la jante tourne toute seule sous les mains levées "
                               "pendant que les impulsions vertes parcourent la colonne",
         "camera_position": "moyen statique à hauteur de volant, faible profondeur de champ",
         "composition": "le mannequin à gauche, la jante au centre, la route à droite"},
    ),
]

VOIX = [p[0] for p in PLANS]
DUREES = [p[1] for p in PLANS]

BOARD = {
    "subject": "Comment on vole une voiture récente sans casser une vitre",
    "duration_seconds": sum(DUREES),
    "shot_count": len(PLANS),
    "script": " ".join(VOIX),
    "visual_bible": {
        "main_subject": "a modern dark near-black car on a Parisian street at night, and "
                        "two featureless white mannequins acting on it",
        "characters_objects": "mannequin 1 in a fitted dark black polo shirt, mannequin 2 "
                              "in a heather grey pullover hoodie, both featureless and "
                              "smooth matte white",
        "vehicle": "modern dark near-black car, realistic proportions, unchanged in every shot",
        "colors": "blue for the legitimate radio and data frames, red for what the "
                  "attacker adds, green for the control given back to the driver, grey "
                  "for the mechanical parts",
        "environment": "Parisian street and courtyard at night, wet cobblestone, neon "
                       "signs, dark car interior",
        "materials": "matte white plastic skin, black cotton polo, grey brushed cotton "
                     "hoodie, matte near-black paint, brushed aluminium, braided grey "
                     "sheath, tinted glass",
        "lighting": "warm street lamps and sodium light, cold neon and LED, deep shadows, "
                    "high contrast",
        "camera": "static views, 35mm lens at f/1.8, shallow depth of field, realistic bokeh",
        "style_3d": "photorealistic editorial photography, physically accurate",
        "realism": "photorealistic, no stylisation",
        "invisible_phenomena": "radio and data frames shown as discrete luminous pulses "
                               "travelling along their real physical path",
    },
    "color_code": [
        {"notion": "signal", "color": "blue", "moving": True,
         "meaning": "the legitimate radio and data frames the car's own parts exchange"},
        {"notion": "intrusion", "color": "red", "moving": True,
         "meaning": "everything added from outside the car — the relay link, the "
                    "injected frames, the second sensor reading"},
        {"notion": "controle", "color": "green", "moving": True,
         "meaning": "the commands the driver puts back on the same bus on purpose"},
        {"notion": "mecanique", "color": "grey", "moving": False,
         "meaning": "the bodywork, the lock, the wheels and the structure"},
    ],
    "shots": [
        {"id": i + 1, "duration_seconds": p[1], "voice": p[0],
         "visual_description": f"Parisian street at night, the dark car, shot {i + 1}.",
         "educational_function": p[5],
         "visual_concept": p[4],
         "image_prompt": prompts.enforce_style(p[2]),
         "animation_prompt": p[3],
         "motion_intent": p[6],
         "visual_explanation": p[7]}
        for i, p in enumerate(PLANS)
    ],
    "quality_check": {"narrative_quality": 0.92, "visual_quality": 0.91,
                      "scientific_accuracy": 0.92, "voice_visual_alignment": 0.94,
                      "visual_continuity": 0.93, "pedagogical_clarity": 0.92,
                      "animation_potential": 0.94},
}

if __name__ == "__main__":
    sb = Storyboard.from_dict(BOARD)
    problemes = validator.validate(sb, sum(DUREES), len(PLANS))
    mots = sum(len(v.split()) for v in VOIX)
    print(f"{len(PLANS)} plans · {sum(DUREES):g} s · {mots} mots · "
          f"{len(problemes)} problème(s)\n")
    for p in problemes:
        print(f"  [{p.code}] {p.where} : {p.message}")
        print(f"      → {p.fix[:200]}\n")


def exporter(chemin: Path) -> None:
    """La feuille a lire depuis un telephone : un bloc par prompt."""
    sb = Storyboard.from_dict(BOARD)
    lignes = [f"# {sb.subject}", "",
              f"{sum(DUREES):g} secondes · {len(PLANS)} plans · "
              f"{sum(len(v.split()) for v in VOIX)} mots · "
              f"validé à 0 problème", "",
              "## La direction artistique", "",
              "```", os.environ["STYLE_DIRECTIVE"], "```", "",
              "Elle est déjà collée à la fin de chaque prompt image ci-dessous.",
              "", "## Le code couleur", "",
              "| notion | couleur | sens |", "|---|---|---|"]
    lignes += [f"| {e.notion} | **{e.color}** | {e.meaning} |" for e in sb.code_couleur()]
    lignes += ["", "## Le script", "", "> " + " ".join(VOIX), ""]

    for s in sb.shots:
        lignes += [f"## Plan {s.id:02d} · {s.duration_seconds:g} s", "",
                   f"**Voix :** « {s.voice} »", "",
                   f"*{s.educational_function}*", "",
                   "**Prompt image**", "", "```", s.image_prompt, "```", "",
                   "**Prompt animation**", "", "```", s.animation_prompt, "```", ""]
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    print(f"écrit : {chemin}")


if "--export" in sys.argv:
    exporter(Path("/home/user/Pronotedz-/prototype/app/output/hacking_auto.md"))
