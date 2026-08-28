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
    "Photorealistic premium 3D engineering visualization, modern car in technical "
    "semi-cutaway view, realistic bodywork with internal components visible where the "
    "explanation needs them, dark premium studio environment, cinematic blue and white "
    "lighting, realistic detailed materials, physically credible automotive mechanics, "
    "clearly visible electrical and mechanical components, cinematic depth of field, high "
    "contrast, premium high-end car commercial rendering, vertical 9:16 composition, no "
    "text, no labels, no logos, no watermark."
)

STYLE_DIRECTIVE = (os.getenv("STYLE_DIRECTIVE") or "").strip() or _DEFAUT
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


def storyboard_user(subject: str, duration: float, shot_count: int) -> str:
    par_plan = round(duration / shot_count, 1)
    mots = int(par_plan * WORDS_PER_SECOND)
    return f"""\
Write the complete pre-production of a vertical 9:16 educational video.

SUBJECT: {subject}
TOTAL DURATION: {duration} seconds
SHOTS: {shot_count}

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
Aim for {par_plan}s per shot, about {mots} French words of narration each; the
durations must sum to EXACTLY {duration}. Give a link more seconds if it
deserves them, and take those seconds from another shot.

── PART 3 — THE VISUAL BIBLE ──
Fill "visual_bible" BEFORE writing any prompt. It fixes, concretely: the main
visual subject, the characters or objects, the vehicle, the colours, the
environment, the materials, the lighting, the camera, the 3D style, the level
of realism, and — decisive — how invisible phenomena are represented.
Every image prompt then restates that bible. A viewer must believe the
{shot_count} shots are {shot_count} views of the same physical object.

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

── THE SAME REASONING, WORKED THROUGH ──
Weak, because it starts from the picture:
  "Focus on the electric car's internal layout with cables..."
The reasoning that replaces it:
  information        the battery supplies electricity to the motor
  physical_element   the battery pack
  secondary_elements the high-voltage cable, the electric motor
  visual_behavior    a yellow/orange electrical flow
  animation_movement the flow leaves the battery, crosses the cable, reaches
                     the motor
  camera_position    close enough to read the whole path in one frame
  composition        battery on one side, motor on the other, cable between
And the prompt that follows from it:
  "Technical semi-cutaway view focused on the energy path between the battery
  and the electric motor. The battery pack is clearly visible on one side and
  the electric motor on the other, connected by clearly visible high-voltage
  cables. A bright yellow-orange electrical energy stream travels visibly
  through the cables from the battery toward the motor. The energy stream is
  the main visual focus and must have a clearly readable direction. Mechanical
  components remain grey and secondary."
Its animation animates exactly those elements, and nothing else:
  "Animate the yellow-orange electrical energy stream continuously travelling
  from the battery through the high-voltage cables toward the electric motor.
  The flow must move visibly and directionally rather than simply glowing. As
  the energy reaches the motor, subtle electrical pulses appear inside the
  motor. Keep the battery, cables, motor and vehicle geometry completely rigid
  and unchanged. Slow controlled camera tracking following the energy path. No
  deformation, no invented components, no text."
Notice what makes it work: ONE object, ONE phenomenon, ONE action, and a frame
built so that action is legible. Everything else is grey and secondary.

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

── COLOUR CODE — one notion, one colour, stable throughout ──
{color_block()}
Never use a different colour for the same notion. Never reuse a colour for a
different notion.

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
End it with this sentence, copied VERBATIM:
{STYLE_DIRECTIVE}

── PART 5 — THE ANIMATION PROMPT ──
"animation_prompt", in English, written for THAT image. It must state: which
element moves, in which direction, at what speed, along what path; the
mechanical motion; the energy motion; the camera motion; what stays perfectly
still; the geometry to preserve; the deformations forbidden.

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
