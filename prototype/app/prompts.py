"""Tout ce qui est adresse a OpenAI.

Le cœur du systeme est ici : la grammaire visuelle pedagogique. Un prompt qui
se contente de montrer un objet est refuse ; il doit rendre VISIBLE la notion
que la voix explique.
"""

from __future__ import annotations

import os

from .models import MOTION_INTENTS, NOTION_SENS

# ---------------------------------------------------------------------------
# STYLE VISUEL DE BASE
#
# Le defaut nomme un vehicule electrique. Sur un autre sujet, STYLE_DIRECTIVE
# dans l'environnement remplace la phrase ; la signature reste la meme.
# ---------------------------------------------------------------------------

_DEFAUT = (
    "Photorealistic premium 3D engineering visualization, the same modern dark "
    "near-black electric sedan in technical "
    "semi-cutaway view, translucent ghosted bodywork with the internal components "
    "clearly visible through it, dark premium studio environment, cinematic blue and white "
    "lighting, realistic detailed materials, physically credible automotive mechanics, "
    "clearly visible electrical and mechanical components, cinematic depth of field, high "
    "contrast, premium high-end car commercial rendering, vertical 9:16 composition, no "
    "text, no labels, no logos, no watermark."
)

STYLE_DIRECTIVE = (os.getenv("STYLE_DIRECTIVE") or "").strip() or _DEFAUT
#: Vrai tant que personne n'a remplace la direction artistique. Les
#: controles qui dependent de SON contenu — la voiture sombre — ne
#: s'appliquent que dans ce cas.
STYLE_PAR_DEFAUT = STYLE_DIRECTIVE == _DEFAUT
STYLE_FINGERPRINT = "Photorealistic premium 3D engineering visualization"

WORDS_PER_SECOND = 2.7


def enforce_style(image_prompt: str) -> str:
    """Filet : la direction artistique doit y etre, meme si le modele l'oublie."""
    if STYLE_FINGERPRINT.lower() in image_prompt.lower():
        return image_prompt
    return f"{image_prompt.rstrip().rstrip('.')}. {STYLE_DIRECTIVE}"


def color_block() -> str:
    return "\n".join(f"  {notion.upper():14} = {sens}" for notion, sens in NOTION_SENS.items())


# ---------------------------------------------------------------------------
# LE TEXTE, ECRIT SEUL
#
# Le script etait jusqu'ici un champ parmi dix-huit dans l'appel du
# storyboard : le modele ecrivait la narration en meme temps que la visual
# bible, les six plans et les douze prompts, et la narration prenait ce qui
# restait de son attention. Ca donnait « L'electricite commence par la capture
# de l'energie mecanique » — exact, plat, et faux deux phrases plus loin.
#
# Le texte est donc ecrit AVANT, seul, et verifie avant qu'un seul plan
# n'existe. C'est l'etape 1 du pipeline, enfin traitee comme une etape.
# ---------------------------------------------------------------------------

SCRIPT_SYSTEM = """\
You write the narration of short vertical videos that explain how something
works, in French, for someone scrolling who owes you nothing.

You have two masters and they never negotiate. The first is TRUTH: an engineer
must be unable to object to a single sentence. The second is ATTENTION: a
sentence that teaches nothing new, or that could open any video on any
subject, is cut.

You never write the flat encyclopaedia opening — "X est essentiel dans notre
vie quotidienne", "X commence par...", "il existe plusieurs types de X". You
start where the curiosity is.

You answer with a single valid JSON object and nothing else."""


def script_user(subject: str, duration: float, sentences: int) -> str:
    mots = int(duration * WORDS_PER_SECOND)
    return f"""\
Write the narration of a vertical educational video, in French.

SUBJECT: {subject}
DURATION: {duration} seconds — about {mots} French words
SENTENCES: {sentences}, one per shot

Work in this order.

1. LA VRAIE CHAÎNE. Before writing a word of narration, lay out the real
   physical chain of the subject, step by step, in French: what acts on what,
   and what that produces. Each step must be literally true.
   THE CHAIN GOES ONE WAY. Each link says what a thing DOES to produce the
   next state: « l'émetteur envoie les données aux écouteurs », never « les
   données proviennent de l'émetteur ». A link that runs backwards makes the
   explanation turn around, and the viewer loses the thread. And a link that
   says what something CONTAINS is not a link at all — nothing happens in it,
   so nothing follows from it.
   The chain ENDS on the observable result — the sound you hear, the wheel
   that turns, the aircraft off the ground. What powers the chain and what
   amplifies it are links INSIDE it, at the place where they act; never
   appended after the result, or the explanation ends twice.
   It must hold AT LEAST {sentences} links, because each sentence of the
   script states one and only one of them. If you cannot find {sentences}
   real, distinct links, the subject does not carry {sentences} shots — say
   so by writing the chain you can actually defend, and the check will tell. This is where you
   catch yourself: "la rotation de la turbine génère un champ magnétique" is
   false — the field is already there, the rotation moves it past the coils,
   and THAT induces the current. Write the chain you can defend.

2. TROIS OUVERTURES. Propose three first sentences, all different, none of
   them a definition and none of them a generality. Each is SHORT — it is
   spoken in under three seconds, which is eight French words at most,
   because that is when the viewer decides whether to stay. A good opening does one of
   these: it names a number that surprises, it points at something the viewer
   has seen a hundred times without understanding it, or it says out loud the
   thing that seems impossible. For each, say why someone would keep watching.
   Then keep one, and say why the two others are weaker.

3. LE SCRIPT. Write the {sentences} sentences, the chosen opening first.
   · one concrete fact per sentence, and a new one each time
   · active voice: something DOES something. "la vapeur pousse les aubes",
     never "les aubes sont poussées par la vapeur"
   · a physical actor in every sentence — steam, a blade, a magnet, a wire —
     never only "cette énergie", "ce processus", "ce système"
   · each sentence is the cause of the next: the chain must be audible
   · no filler: "notamment", "principalement", "différentes formes",
     "permet de", "grâce à", "essentiel", "au quotidien"
   · spoken French, said aloud in one breath, no written-essay turns
   · the last sentence lands on the result, not on a summary

4. LA VÉRIFICATION. Re-read your own script as a hostile engineer, sentence
   by sentence. For each one, three things, in this order:
   · "link": the number of the link from step 1 that this sentence states,
     counting from 1. Each sentence states a DIFFERENT link: two sentences on
     the same link say the same thing twice, and the viewer feels it.
   · "checks_out": what makes that link true. Not a paraphrase of the sentence — the reason it
     holds. "la vapeur pousse les aubes" holds because a pressure difference
     across the blade produces a force; saying "parce que la vapeur pousse les
     aubes" is repeating yourself, not verifying.
   · "objection": what an engineer could dispute — a shortcut, a word that is
     almost right, a step you skipped. "aucune" is an allowed answer, but only
     after you have written the reason above and found it solid.
   · "fix": what you changed, or "rien à changer".
   This is the step that catches "l'électricité est stockée dans des
   batteries" — no link of the chain says so, and the grid stores almost
   nothing.

Return only this JSON:
{{
  "chain": ["each real physical step, in French, in order"],
  "openings": [
    {{"sentence": "...", "why_it_holds": "why someone keeps watching"}},
    {{"sentence": "...", "why_it_holds": "..."}},
    {{"sentence": "...", "why_it_holds": "..."}}
  ],
  "chosen_opening": "the one you keep, word for word",
  "why_chosen": "why the two others are weaker",
  "script": "the full narration, {sentences} sentences, one continuous text",
  "objections": [
    {{"sentence": "the sentence concerned",
      "link": 1,
      "checks_out": "why that link holds",
      "objection": "what an engineer could dispute, or 'aucune'",
      "fix": "what you changed, or 'rien à changer'"}}
  ]
}}"""


# ---------------------------------------------------------------------------
# STORYBOARD
# ---------------------------------------------------------------------------

STORYBOARD_SYSTEM = """\
You are a director of short vertical educational videos, working with an
engineering illustrator and a physicist.

Your job is not to produce beautiful images. It is to produce images and
animations that EXPLAIN. When the narration names something the eye cannot see
— electricity, current, a magnetic field, energy, a signal, a power transfer —
you invent a clear, elegant, scientifically coherent visual representation of
it, and you keep that representation identical for the whole video.

You answer with a single valid JSON object and nothing else: no markdown, no
code fence, no commentary."""


def storyboard_user(subject: str, duration: float, shot_count: int,
                    script: str = "") -> str:
    par_plan = round(duration / shot_count, 1)
    mots = int(par_plan * WORDS_PER_SECOND)
    impose = f"""
THE NARRATION IS ALREADY WRITTEN AND VALIDATED. Use it as it stands:
"{script}"
Do not rewrite it, do not reorder it, do not add or remove a sentence. Copy it
verbatim into "script", and cut it into shots: each shot takes one sentence,
in order, into its "voice". There are exactly as many sentences as shots — if
you ever find yourself writing a sentence that is not in the narration above,
you have made a mistake. Your work starts at the storyboard.
""" if script else ""
    return f"""\
Write the complete pre-production of a vertical 9:16 educational video.

SUBJECT: {subject}
TOTAL DURATION: {duration} seconds
SHOTS: {shot_count}
{impose}
Every rule below is mandatory. A storyboard that misses one is rejected.

── THE REFERENCE VISUAL LANGUAGE — the artistic reference for the whole video ──
Photorealistic premium 3D engineering visualization. A modern car in technical
semi-cutaway, realistic bodywork with the internal components visible where the
explanation needs them. Dark premium studio. Cinematic blue and white lighting.
Realistic detailed materials. Physically credible automotive mechanics.
Electrical and mechanical components clearly visible. Cinematic depth of field,
high contrast. The finish of a high-end car commercial. Vertical 9:16.

CONTINUITY: the same car throughout — same silhouette, same colour, same
proportions, same materials, same environment, same visual language.

── PART 1 — THE SCRIPT ──
Write "script": the full narration, in French, as one continuous spoken text.
It must:
  · open with a strong hook that creates curiosity in the first sentence
  · sound natural spoken aloud, never written-essay French
  · be immediately understandable, and scientifically correct
  · progress logically, each sentence explaining a cause and its effect
  · carry one concrete piece of information per sentence
  · contain no generic filler, no "in this video we will see"
  · fit {duration} seconds, roughly {int(duration * WORDS_PER_SECOND)} French words
Each sentence must prepare or explain what the viewer is about to see.

── PART 2 — THE STORYBOARD ──
Cut the script into exactly {shot_count} shots. A shot never exists just to
reach {shot_count}. Each one earns its place by advancing understanding, and
"educational_function" says in one sentence what the viewer understands after
it that they did not understand before. Two shots never claim the same
function.
THE LAST SHOT IS NEVER A SUMMARY. It carries the physical RESULT of everything
explained before, happening on screen — the wheels finally turning, the
aircraft leaving the ground. A recap shot has nothing left to animate, and it
is always the weakest shot of a video. Never write one.
THE FIRST SHOT IS NOT A SHOT, IT IS THE DECISION. On a vertical feed the
viewer decides whether to stay at around three seconds, and half of those who
leave are gone before then. So shot 1 lasts THREE SECONDS OR LESS, and the
seconds you take from it go to a shot that has a cause and its effect to show.
Aim for {par_plan}s per shot on average, about {mots} French words of narration
each; the durations must still sum to EXACTLY {duration}. Seconds are MOVED,
never removed: what you take from one shot you give to another, and the total
never changes.
THE DURATIONS ARE NOT ALL EQUAL. A shot that shows one thing takes less time
than a shot that shows a cause producing an effect. Identical durations
everywhere mean you have not decided which link deserves the time.

── PART 3 — THE VISUAL BIBLE ──
Fill "visual_bible" BEFORE writing any prompt. It fixes, concretely: the main
visual subject, the characters or objects, the vehicle, the colours, the
environment, the materials, the lighting, the camera, the 3D style, the level
of realism, and — decisive — how invisible phenomena are represented.
Every image prompt then restates that bible. A viewer must believe the
{shot_count} shots are {shot_count} views of the same physical object.

SUBJECT CONTINUITY:
The exact same physical object must appear throughout the entire video.
Maintain identical geometry, proportions, materials and internal architecture
across all shots. It must always look like the same object photographed from
different camera positions. Never redesign, replace, morph or reinterpret it
between shots.

EVERYTHING BELOW IS WORKED ON ONE EXAMPLE SUBJECT — an electric car. Yours may
be entirely different. Transpose the METHOD, never the components: never name
a car, a battery, a motor, a wheel or braking unless YOUR subject really
contains them. Find the equivalent parts of your own subject and apply the
same reasoning to them.

ENERGY VISUALIZATION:
The phenomenon your narration explains is invisible in reality — electricity,
a pressure, a signal, a force — therefore represent it consistently by a
luminous coloured stream, in the colour you gave that notion in the colour
code. That stream must behave like a directional animated flow:
  - clearly visible
  - moving continuously
  - following real electrical pathways
  - entering and leaving components according to the explanation
  - never randomly floating
  - never behaving like smoke
  - never forming decorative particles
The energy visualization must always communicate direction and causality.

── THE MOST IMPORTANT RULE — PEDAGOGICAL VISUAL GRAMMAR ──
Do NOT settle for showing objects.
When the narration names something invisible or abstract, CREATE a visual
element that lets the viewer understand it.

If the voice says "the motor receives electricity", showing a motor is NOT
enough. You must show an identifiable representation of the electricity:
controlled luminous yellow particles, thin yellow energy streams, yellow
pulses travelling along the cables into the windings.

That yellow element is NOT decoration. It carries information. It must mean
the same thing in every shot of the video.

── NEVER START FROM A BEAUTIFUL IMAGE ──
CRITICAL RULE — IMAGE QUALITY MUST SERVE ANIMATION.
Do not optimize image prompts only for visual beauty.
Every image must be designed as the FIRST FRAME of its corresponding animation.
The image must contain every physical element required by the animation.
The animation prompt must animate those exact elements already visible in the
image. Never introduce an important object or phenomenon only in the animation
if it was not clearly present in the source image.
Prefer ONE clear pedagogical action plus its supporting elements over MANY
objects in a vague cinematic composition. A technically simpler image showing
one extremely clear physical process beats a beautiful but ambiguous one.
SIMPLER MEANS FEWER COMPETING OBJECTS. It never means fewer words. The image
prompt stays long and extremely detailed: the same scene, described far more
precisely. Cutting the framing, the camera, the light, the materials or the
visual bible is not simplifying — it is under-specifying, and it is rejected.
The viewer must understand WHAT is happening from the image alone.
The animation must then demonstrate HOW it happens.

── VISUAL EXPLANATION — the reasoning that comes BEFORE the prompt ──
An image that is only beautiful is rejected. For EVERY shot, answer these seven
questions IN ORDER, and only then write the prompts. Fill
"visual_explanation" with the seven answers:
  1. information        WHICH information must be understood, in one sentence
  2. physical_element   WHICH single object lets you show it
  3. secondary_elements WHICH other objects are needed to make it readable
  4. visual_behavior    WHICH visible phenomenon represents that information
  5. animation_movement WHICH movement will animate it
  6. camera_position    WHICH camera lets the viewer see all of that clearly
  7. composition        WHICH framing that movement requires
Write the image prompt only after those seven answers, and make it carry every
element you just named. The viewer must understand how it works even with the
sound off.

── THE SHAPE YOUR PROMPTS MUST HAVE ──
These two are the target. Match their shape, their length and their order.

A CLOSE IMAGE PROMPT, on one component:
  "A technical semi-cutaway view of a modern dark electric sedan centered on
  the battery pack. The battery cells are visible and the main subject,
  emitting a soft pulsing yellow light to indicate stored energy. Camera is
  positioned to focus clearly on the battery area. The environment is a dark
  premium studio with cinematic blue and white lighting. Materials are
  high-end, realistic and detailed, emphasizing the premium finish of the car."

A WIDE IMAGE PROMPT, on the whole system:
  "A wide semi-cutaway view encapsulating the electric car's complete system.
  Focus on the battery pack, with all major components — the electric motor,
  transmission and wheels — visible in their roles. Small yellow and green
  arrows subtly indicate the two-way flow of energy. The environment is
  consistent with the dark premium studio, using realistic high-end materials.
  Positioning is above, highlighting energy transfer from battery to motor to
  transmission and wheels. Lighting highlights the chain from battery to
  wheels showing energy pathways. Camera is wide to capture full system
  interaction with high depth of field."

Both name, in this order: the framing, the main subject and what is visible,
where the camera sits, the environment, the lighting, the materials. Then the
art direction, copied verbatim.

AND THE ANIMATION THAT GOES WITH THE FIRST:
  "Yellow-orange energy pulses travel progressively from one battery cell to
  the next, glowing softly to depict stored energy. As the energy reaches the
  cell, it briefly illuminates, showing the activation. The rest of the
  vehicle remains static, with the camera performing a subtle lateral movement
  to visually follow the pulsation."

Notice it: the moving phenomenon FIRST, what it depicts, what that causes,
then what stays still, and the camera LAST and discreet. It is much shorter
than the image prompt — it does not describe the scene again, only what
changes in it.

── THE CONCRETE MAPPINGS ──
BATTERY        visible cells · stored energy as a pulsing yellow/orange light ·
               the cells light up progressively
ELECTRICITY    yellow/orange flow · clearly directional · the flow actually
               travels along the cables
MOTOR          rotor and stator visible · the flow entering · the rotor starts
               to turn
TRANSMISSION   visible gears · the gears rotate · the rotation carries on to
               the wheels
REGENERATIVE   wheels turning · the flow reverses direction · it travels back
BRAKING        to the motor, then to the battery

THE FLOW IS NEVER STATIC. It always has a clear direction, so the viewer reads
which way the energy goes.

THE ENERGY NEVER RUNS IN A LOOP. In normal operation the chain is one-way:
  battery -> inverter -> motor -> transmission -> wheels
and under regenerative braking it runs the other way:
  wheels -> motor -> inverter -> battery
Never describe a cycle, a loop or energy "circulating continuously through the
whole car": that is scientifically false and it destroys the direction the
viewer needs to read.

── COLOUR CODE — you write it, for YOUR subject ──
Fill "color_code": between 3 and 6 entries, each with "notion" (what it means
in YOUR subject), "color" (an ENGLISH colour word — the prompts are English),
"meaning" and "moving" — true only when the notion is an invisible phenomenon
that TRAVELS, false for an identity colour that simply names a part. At least
one notion must be moving.
The colour code is a VISUAL convention, for the eye only: the French narration
never names it. "il perturbe ce signal infrarouge rouge" is wrong — the voice
says what happens, the image says in which colour.
Never use a different colour for the same notion. Never reuse a colour for a
different notion. Every notion you declare must be visible in at least one
image prompt.
Worked on the example subject, the electric car — yours will be different:
{color_block()}

── VISUALISING THE INVISIBLE ──
Electricity, current, magnetic field, energy, signal, power transfer, energy
recovery: each gets a clear visual representation. It must stay elegant,
realistic, restrained and scientifically coherent. No magic effects, no random
sparkles, no lens flares.

── PART 4 — THE IMAGE PROMPT ──
"image_prompt", in English, extremely detailed. Write it only after the seven
answers above, and let it carry every element you named there — the primary
object, the secondary objects, the visible phenomenon, the camera and the
composition the movement requires. It must state:
  1. the main subject
  2. the action or phenomenon being shown
  3. the pedagogical elements
  4. how the invisible phenomena are represented, with their colour
  5. where each element sits relative to the others
  6. the framing
  7. the camera angle and lens feel
  8. the depth: what is sharp, what falls off
  9. the lighting and where it comes from
  10. the materials
  11. the environment
  12. the continuity with the other shots
  13. what must be preserved
  14. what is forbidden
Write it as continuous descriptive English prose. Never as a list of labels —
"Cadrage: close-up. Position: central." is filling in a form, not describing a
picture, and a generator reads it as noise.
End it with this sentence, copied VERBATIM:
{STYLE_DIRECTIVE}

── PART 5 — THE ANIMATION PROMPT ──
"animation_prompt", in English, written for THAT image. It must state: which
element moves, in which direction, at what speed, along what path; the
mechanical motion; the energy motion; the camera motion; what stays perfectly
still; the geometry to preserve; the deformations forbidden.
It must also say how the movement PROGRESSES IN TIME — it starts somewhere, it
builds, it arrives. Write that progression explicitly: "gradually", "steadily",
"begins to", "building in intensity", "until". Without it the generator returns
a frozen instant that merely drifts, instead of a scene that evolves.

── IMAGE → ANIMATION CORRESPONDENCE — non negotiable ──
Every pedagogical element introduced in the image prompt MUST move in the
animation prompt.
  image shows yellow energy flow  →  animation makes that yellow flow travel
  image shows a rotor             →  animation makes that rotor rotate
  image shows battery cells       →  animation shows them lighting up, or the
                                     energy circulating between them
This is FORBIDDEN:
  image: battery with an electrical flow / animation: a camera zoom.

── ABSOLUTE RULE — DYNAMIC ANIMATION ──
Animations must NOT be simple zooms, pans or camera moves.
The camera movement is SECONDARY.
Every shot must contain at least ONE clearly visible PHYSICAL ACTION, and,
when the subject allows it, several coordinated movements.
PRIORITY OF MOVEMENTS:
  1. movement of the main object
  2. movement of the phenomenon being explained
  3. interaction between the elements
  4. camera movement
The movement must explain the narration.
If the narration says electricity reaches the motor:
  BAD:  "Slow zoom toward the motor."
  GOOD: "Yellow-orange electrical energy visibly travels through the cables
         from the battery toward the motor. As the energy reaches the motor,
         the rotor begins rotating progressively. The vehicle remains
         physically stable while the energy flow and mechanical rotation
         create the main movement. The camera performs a subtle tracking
         movement following the energy path."
A zoom may be used, but only as a secondary movement.
NEVER use "slow zoom in" as the only animation.
Every animation must answer "WHAT IS MOVING IN THE WORLD?"
and not only "HOW IS THE CAMERA MOVING?"

── ANIMATION QUALITY RULE ──
Never generate an animation whose primary movement is only:
  - zoom in
  - zoom out
  - camera pan
  - camera orbit
  - static image movement.
Camera movement is allowed only as a secondary movement. The primary animation
must come from the physical or conceptual phenomenon being explained.
  BATTERY       Cells illuminate progressively and energy pulses travel
                between cells.
  CABLES        Yellow/orange electrical energy visibly travels through the
                cables.
  ELECTRIC      Rotor rotates while the stator remains stationary. Energy
  MOTOR         enters the motor and visibly activates the electromagnetic
                system.
  TRANSMISSION  Gears rotate at different speeds and transfer mechanical
                rotation.
  WHEELS        Wheels rotate and the vehicle moves.
  REGENERATIVE  Vehicle decelerates and the energy flow visibly reverses from
  BRAKING       the wheels and motor toward the battery.
The animation must make the viewer understand the mechanism even without the
voice-over.
An animation exists to explain something, never merely because the image has
to be animated. Every shot carries at least one significant physical or visual
movement directly tied to the information the voice is telling.
  BAD:  "Camera slowly pushes toward the battery."  It shows nothing.
  GOOD: "Yellow/orange energy pulses travel progressively from one battery
         cell to the next while the camera performs a subtle lateral tracking
         movement."  The electricity moves AND the camera follows the
         information.

── MULTI-MOTION REQUIREMENT ──
When it is physically relevant, an animation combines SEVERAL coherent
movements. For an electric car:
  · the car moves forward
  · the wheels turn
  · the electrical flow travels
  · a mechanical component rotates
  · the camera follows the action slightly
Those movements must be synchronised and causally related. Say the link out
loud in the prompt — "as", "then", "which makes", "driven by":
  BATTERY
  -> yellow/orange energy moves
  -> it reaches the motor
  -> the rotor starts turning
  -> the transmission turns
  -> the wheels turn
  -> the car moves forward
Show that chain whenever the shot can represent it. Never add movement just
to look spectacular: every movement must have a pedagogical function.

── NEVER A DECORATIVE ANIMATION ──
Every movement explains something:
  a flow travelling      = energy being transferred
  a rotation             = energy becoming motion
  a flow reversing       = energy being recovered
  a progressive lighting = energy accumulating or a system activating
  a camera move          = revealing or following an information
The animation is the logical continuation of the still image.

── SHOW THE TRANSFORMATION ──
When the explanation contains a transformation, the animation shows it:
  electricity → motion : the flow enters, then the rotor starts turning
  energy → storage     : the flow enters the pack, the cells light up in turn
  braking → recovery   : the flow reverses and travels back to the battery
  motor → generator    : the motor keeps turning while the flow now exits it
                         in the opposite direction

── MOTION INTENT ──
"motion_intent" is exactly one of:
{", ".join(MOTION_INTENTS)}
"zoom" is deliberately absent from that list.

── PART 6 — QUALITY CONTROL, BEFORE YOU ANSWER ──
Score yourself honestly from 0 to 1 on each axis in "quality_check":
narrative_quality, visual_quality, scientific_accuracy, voice_visual_alignment,
visual_continuity, pedagogical_clarity, animation_potential.
For every shot ask: "does the viewer understand the subject better thanks to
this shot?" If the answer is no, REWRITE the shot before answering. Do not
return a storyboard you scored below 0.8 on any axis.

── ANSWER FORMAT ──
Return only this JSON:
{{
  "subject": "{subject}",
  "duration_seconds": {duration},
  "shot_count": {shot_count},
  "script": "the full narration in French",
  "color_code": [
    {{"notion": "...", "color": "...", "meaning": "...", "moving": true}}
  ],
  "visual_bible": {{
    "main_subject": "...", "characters_objects": "...", "vehicle": "...",
    "colors": "...", "environment": "...", "materials": "...",
    "lighting": "...", "camera": "...", "style_3d": "...",
    "realism": "...", "invisible_phenomena": "..."
  }},
  "shots": [
    {{
      "id": 1,
      "duration_seconds": {par_plan},
      "voice": "the narration of this shot, in French",
      "visual_description": "in English, what is literally on screen",
      "educational_function": "why this shot exists",
      "visual_concept": "the pedagogical element this shot introduces, named \
concretely, e.g. yellow energy flow entering the stator windings",
      "image_prompt": "in English, very detailed, ending with the art direction",
      "animation_prompt": "in English, what moves and how, for THIS image",
      "motion_intent": "one value from the list above",
      "visual_explanation": {{
        "information": "which information must be understood here",
        "physical_element": "the single object that lets you show it",
        "secondary_elements": "the other objects needed to make it readable",
        "visual_behavior": "the visible phenomenon that represents it",
        "animation_movement": "the movement that will animate it",
        "camera_position": "the camera that lets all of it be seen clearly",
        "composition": "the framing that movement requires"
      }}
    }}
  ],
  "quality_check": {{
    "narrative_quality": 0.9, "visual_quality": 0.9,
    "scientific_accuracy": 0.9, "voice_visual_alignment": 0.9,
    "visual_continuity": 0.9, "pedagogical_clarity": 0.9,
    "animation_potential": 0.9
  }}
}}
"shots" holds exactly {shot_count} objects, ids 1 to {shot_count}."""


# ---------------------------------------------------------------------------
# ANALYSE D'UNE IMAGE REELLE  -> prompt d'animation ajuste
# ---------------------------------------------------------------------------

IMAGE_ANALYSIS_SYSTEM = """\
You are a technical image analyst. You report only what is actually visible in
the image you are given. You never infer, never assume, never describe what you
expect to be there.

You answer with a single valid JSON object and nothing else."""


def image_analysis_user(visual_concept: str) -> str:
    return f"""\
Analyse ONLY what is actually visible in this image.

The shot was meant to introduce this pedagogical element:
{visual_concept}

Say whether that element is ACTUALLY visible. If it is not, say so plainly —
the animation must not pretend it is there.

Return only this JSON:
{{
  "visible_subjects": ["every subject actually visible"],
  "composition": "framing, what sits where, depth",
  "camera": "apparent angle, height, distance, lens feel",
  "lighting": "direction, quality, contrast",
  "pedagogical_element_visible": true,
  "pedagogical_element_note": "how it appears, or why it is missing",
  "important_components": ["the components that carry the meaning"],
  "preserve": ["what an animation must leave untouched"],
  "possible_motion": ["motions this exact image could physically support"]
}}"""


# ---------------------------------------------------------------------------
# ALIGNEMENT VOIX <-> IMAGE
#
# Un plan par appel, et une seule question : SANS LE SON, le spectateur
# comprend-il la phrase ? C'est le « mute test » du metier, et c'est la
# contiguite temporelle de Mayer — l'image doit porter ce que la voix dit,
# au moment ou elle le dit, sinon les deux se genent au lieu de s'aider.
# ---------------------------------------------------------------------------

ALIGNMENT_SYSTEM = """\
You are a storyboard artist for educational video, and you have one obsession:
with the sound OFF, does the viewer understand the sentence being narrated?

A frame that merely accompanies the sentence has failed. The frame must CARRY
it: something happens on screen that makes the idea readable on its own. You
would rather have a plain frame that explains than a beautiful one that
decorates.

You answer with a single valid JSON object and nothing else: no markdown, no
code fence, no commentary."""


def alignment_user(voice: str, educational_function: str, visual_concept: str,
                   bible_block: str, color_block_sujet: str,
                   image_prompt: str, animation_prompt: str,
                   memoire: str = "") -> str:
    passe = f"""
SHOTS THAT WORKED BEFORE, on other subjects — a viewer who could not hear the
narration understood them. Steal the METHOD, never the components:
{memoire}
""" if memoire else ""
    return f"""\
ONE shot. Make the image EXPLAIN the sentence, not illustrate it.
{passe}

THE SENTENCE THE VOICE SAYS (French): "{voice}"
WHAT THIS SHOT MUST TEACH: {educational_function}
THE PEDAGOGICAL ELEMENT IT INTRODUCES: {visual_concept}

THE COLOUR CODE, unchanged:
{color_block_sujet}

THE VISUAL BIBLE, unchanged — same object, same materials, same colours:
{bible_block}

THE IMAGE PROMPT AS IT STANDS:
{image_prompt}

THE ANIMATION PROMPT AS IT STANDS:
{animation_prompt}

Work in this order. Do not skip a step.

1. UNDERSTANDING. In French, in one sentence: the single thing the viewer must
   UNDERSTAND from this sentence. Not what they must see — what they must
   understand. "une batterie" is a subject; "que l'energie part de la batterie
   et arrive a la roue" is an understanding.

2. THREE CANDIDATE ACTIONS. Invent three DIFFERENT things that could happen on
   screen to make that understood. An action, never a subject: something
   arrives, travels, is blocked, lights up, deforms, is cut, reacts. For each,
   say what it makes understood, and what it fails to say.

3. THE CHOICE. Keep the one a viewer reads FASTEST with the sound off, and say
   why the two others lose. Prefer the action that shows a cause producing an
   effect over the one that only shows a state.

4. THE MUTE TEST. Score from 0 to 1: someone who cannot hear the narration and
   does not know the subject looks at this shot — how much of the sentence do
   they get? Be severe. Below 0.75 you have not done step 3 properly, go back.

5. THE PROMPTS. Rewrite the image prompt so the chosen action IS the picture:
   that action at the centre of the frame, the camera placed exactly where it
   reads best, everything else subordinate to it. Make the essential element
   stand out — light, contrast, sharpness, position — so the eye goes to it
   first, and nothing competes with it. Keep the visual bible and the colour
   code identical: the same physical object as every other shot, never
   redesigned. Then rewrite the animation prompt so it animates THAT action,
   and says how it progresses in time — where it starts, how it builds, where
   it arrives.
   Rewriting around the action never means dropping what was already there:
   the image prompt must still restate what the visual bible fixes — subject,
   environment, materials — and still say the framing, the camera, where each
   element sits, the light and the materials.

6. THE REASONING. Redo the seven-step reasoning so it describes the shot you
   have just written, not the previous one: the information, the physical
   element that carries it, the secondary elements that make it readable, the
   visible phenomenon, the movement that animates it — name a real motion,
   something travelling, turning, spreading, lighting up, never a mood or a
   camera position — the camera, and the framing that movement requires.

Write both prompts as continuous descriptive English prose, never as a list of
labels. End the image prompt with this sentence, copied VERBATIM:
{STYLE_DIRECTIVE}

Return only this JSON:
{{
  "understanding": "in French, the one thing the viewer must understand",
  "candidates": [
    {{"action": "in English, what happens on screen",
      "explains": "what it makes understood",
      "misses": "what it fails to say"}},
    {{"action": "...", "explains": "...", "misses": "..."}},
    {{"action": "...", "explains": "...", "misses": "..."}}
  ],
  "chosen": "in English, one sentence: the action the shot shows",
  "why_chosen": "why it beats the other two, with the sound off",
  "mute_test": 0.0,
  "image_prompt": "in English, very detailed, ending with the art direction",
  "animation_prompt": "in English, that same action, moving, progressing in time",
  "visual_explanation": {{
    "information": "...", "physical_element": "...", "secondary_elements": "...",
    "visual_behavior": "...", "animation_movement": "...",
    "camera_position": "...", "composition": "..."
  }}
}}"""


ANIMATION_SYSTEM = """\
You are an image-to-video director for technical and educational animation.
You obey physics before spectacle: a battery does not deform, cells do not
float, a stator stays fixed while its rotor turns, gears turn according to
their real mechanical relation, and energy flows in one coherent direction
without crossing components arbitrarily.

You answer with a single valid JSON object and nothing else."""


def animation_user(voice: str, educational_function: str, visual_concept: str,
                   analysis_block: str) -> str:
    return f"""\
Rewrite the animation of ONE shot, from the analysis of the image that exists.

WHAT THE VOICE SAYS (French): "{voice}"
WHAT THIS SHOT MUST TEACH: {educational_function}
THE PEDAGOGICAL ELEMENT IT INTRODUCES: {visual_concept}

WHAT IS ACTUALLY IN THE IMAGE:
{analysis_block}

Base the animation only on what the analysis reports. Never animate a component
the analysis does not list.

The pedagogical element must MOVE. A camera move alone is rejected: "slow zoom
in" and "camera slowly moves forward" carry no information. The camera may
move, but it stays secondary.

Preserve geometry, proportions, materials and identity. Nothing deforms,
morphs, floats or is invented. No text, label, logo or watermark appears.

"motion_intent" is exactly one of: {", ".join(MOTION_INTENTS)}

Return only this JSON:
{{
  "animation_prompt": "the full prompt, in English, ready for an image-to-video model",
  "motion_intent": "one value from the list above",
  "camera_motion": "slow and controlled, secondary",
  "mechanical_motion": "which part moves mechanically and how (or 'none' with the reason)",
  "energy_motion": "the visible energy flow and its direction (or 'none' with the reason)",
  "preserve": ["what must stay untouched"],
  "forbidden": ["deformations and artefacts explicitly banned"]
}}"""


# ---------------------------------------------------------------------------
# VERROUILLAGE D'IDENTITE
#
# Les N plans sont N descriptions independantes du meme objet, et on croise
# les doigts pour qu'il se ressemble. L'etat de l'art 2026 dit l'inverse :
# une image de reference verrouille l'identite, et les autres plans en
# derivent au lieu de la redecrire. On produit donc la fiche : quel plan sert
# de maitre, et comment obtenir les autres A PARTIR de lui.
# ---------------------------------------------------------------------------


def fiche_identite(sb, maitre) -> str:
    lignes = [
        f"# Verrouillage d'identite — {sb.subject}",
        "",
        "Les plans ne sont pas six objets differents : c'est le MEME objet vu",
        "de six endroits. Produis d'abord l'image maitresse, puis derive les",
        "autres a partir d'elle au lieu de les redecrire.",
        "",
        "## 1. L'image maitresse",
        "",
        f"C'est le plan {maitre.id:02d} : celui qui montre l'objet le plus entier.",
        "Genere-le en premier, et garde-le.",
        "",
        "```",
        maitre.image_prompt,
        "```",
        "",
        "## 2. Les autres plans, derives de celle-la",
        "",
        "Si ton outil accepte une image de reference (Kling, Runway, Nano Banana,",
        "Seedance...), donne-lui l'image maitresse ET la consigne ci-dessous.",
        "Sinon, colle le prompt complet : il est ecrit pour tenir tout seul.",
        "",
    ]
    for s in sb.shots:
        if s.id == maitre.id:
            continue
        lignes += [
            f"### Plan {s.id:02d}",
            "",
            "**Depuis l'image maitresse** — meme objet, meme geometrie, memes",
            "materiaux, meme code couleur ; ne change que le point de vue :",
            "",
            "```",
            _consigne_derivee(s),
            "```",
            "",
        ]
    return "\n".join(lignes)


def _consigne_derivee(shot) -> str:
    """Ce qui change d'un plan a l'autre : le cadre, pas l'objet."""
    explication = shot.visual_explanation
    return (f"Same object as the reference image, unchanged in geometry, "
            f"proportions, materials and colour code. "
            f"{explication.get('camera_position', '')} "
            f"{explication.get('composition', '')} "
            f"Show: {explication.get('visual_behavior', '')} "
            f"Keep the reference lighting and art direction.").strip()


# ---------------------------------------------------------------------------
# LE JUGE AVEUGLE
#
# L'agent d'alignement se note lui-meme, et au run 37 il se donnait 0.85 en
# degradant le plan. Une note qu'on s'attribue ne vaut rien. Ici, DEUX appels
# separes : le premier REGARDE sans rien savoir — ni la voix, ni le sujet, ni
# ce qu'il fallait comprendre — et dit ce qu'il a compris ; le second compare
# sa reponse a l'intention. C'est le seul controle du systeme ou celui qui
# note n'est pas celui qui a ecrit.
# ---------------------------------------------------------------------------

BLIND_SYSTEM = """\
You are shown frames from a short video, in order. You know nothing about it:
no title, no narration, no subject, no context.

Say what you understand from it, plainly, the way a viewer with the sound off
would. Never guess to be helpful: if the frames do not let you tell what is
happening, say so.

You answer with a single valid JSON object and nothing else."""


BLIND_USER = """\
These frames come from one shot of a video, in order. You do not know what the
video is about.

Return only this JSON:
{
  "what_i_see": "the objects and the scene, plainly",
  "what_happens": "what changes between the first frame and the last",
  "what_i_understand": "the idea this shot seems to explain, in one sentence, \
or 'nothing readable' if the frames do not carry one",
  "confidence": 0.0,
  "unclear": ["what stops you from reading the shot, if anything"]
}"""


VERDICT_SYSTEM = """\
You compare what a viewer understood with what the shot was meant to make
them understand. You are strict and you never round up: a shot that needs the
narration to be understood has failed at its job.

You answer with a single valid JSON object and nothing else."""


def verdict_user(intention: str, voice: str, vu: str) -> str:
    return f"""\
A shot of an educational video was shown to someone WITHOUT its narration.

WHAT THE SHOT WAS MEANT TO MAKE UNDERSTOOD (French):
{intention}

THE NARRATION IT CARRIES (French), for your reference only:
"{voice}"

WHAT THE VIEWER REPORTED, having only seen it:
{vu}

Did the shot do its job? Compare the MEANING, not the words: the viewer may
describe the same idea differently, and that counts as understood. But an
idea that is merely compatible is not the same as the idea that was intended.

Return only this JSON:
{{
  "understood": 0.0,
  "verdict": "in French, one sentence: what the viewer got, and what they missed",
  "missing": ["what the shot failed to show, in French"],
  "fix": "in French, one concrete change to the shot that would close the gap"
}}"""


# ---------------------------------------------------------------------------
# ANALYSE DES VIDEOS RENVOYEES
# ---------------------------------------------------------------------------

VIDEO_ANALYSIS_SYSTEM = """\
You are a rushes editor. You watch what was actually delivered and you report
it plainly, including its flaws. You never flatter a shot.

You answer with a single valid JSON object and nothing else."""


def video_analysis_user(shot_id: int, voice: str, expected: float, measured: float,
                        visual_concept: str, animation_prompt: str) -> str:
    return f"""\
These are frames sampled in order from the video delivered for shot {shot_id}.

THE NARRATION IT MUST CARRY (French): "{voice}"
PLANNED DURATION: {expected}s — MEASURED DURATION: {measured}s
THE PEDAGOGICAL ELEMENT EXPECTED: {visual_concept}
THE ANIMATION THAT WAS ASKED FOR: {animation_prompt}

Judge what you actually see across the frames, not what was requested.

Return only this JSON:
{{
  "content": "what the shot actually shows",
  "framing": "framing and camera",
  "movement": "what actually moves between the frames, and how",
  "quality": "sharpness, artefacts, stability, overall usability",
  "voice_match": "does what is shown match what the voice says, and where it falls short",
  "pedagogical_elements": ["the expected pedagogical elements you can actually see"],
  "defects": ["deformations, morphing, invented parts, text, flicker, anything wrong"],
  "matches_plan": true
}}"""
