"""Tout ce qui est adresse a OpenAI. Le seul fichier a ouvrir pour changer
le niveau d'exigence.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# STYLE VISUEL OBLIGATOIRE - present tel quel dans chaque image_prompt
# ---------------------------------------------------------------------------

STYLE_DIRECTIVE = (
    "Photorealistic premium 3D engineering visualization, modern electric vehicle, "
    "clean dark studio environment, realistic materials, physically accurate mechanical "
    "components, cinematic lighting, high contrast, subtle volumetric light, detailed "
    "engineering visualization, vertical 9:16 composition, no text, no labels, no logos, "
    "no watermark."
)

STYLE_FINGERPRINT = "Photorealistic premium 3D engineering visualization"

# Debit de parole vise, en mots par seconde de francais parle.
WORDS_PER_SECOND = 2.7


def enforce_style(image_prompt: str) -> str:
    """Filet : la direction artistique doit etre la, meme si le modele l'oublie."""
    if STYLE_FINGERPRINT.lower() in image_prompt.lower():
        return image_prompt
    return f"{image_prompt.rstrip().rstrip('.')}. {STYLE_DIRECTIVE}"


# ---------------------------------------------------------------------------
# STORYBOARD
# ---------------------------------------------------------------------------

STORYBOARD_SYSTEM = """\
You are a director of short vertical educational videos, working with an
engineering illustrator. You are rigorous about physics and about the link
between what is said and what is shown.

You answer with a single valid JSON object and nothing else: no markdown, no
code fence, no commentary."""


def storyboard_user(subject: str, duration: float, shot_count: int) -> str:
    per_shot = round(duration / shot_count, 1)
    words = int(per_shot * WORDS_PER_SECOND)
    return f"""\
Write the storyboard of a vertical 9:16 educational video.

SUBJECT: {subject}
TOTAL DURATION: {duration} seconds
SHOTS: {shot_count}

Every condition below is mandatory. A storyboard that misses one is rejected.

── CONDITION 1 — THE SCRIPT IS A CAUSAL CHAIN ──
Do not list components. Explain how one thing causes the next.
Each sentence must state a RELATION between elements, so that the {shot_count}
sentences read as one continuous explanation.

For an electric car the chain runs, for example:
  battery → electrical energy → accelerator pedal → power electronics →
  electric motor → rotation → wheels → movement
and optionally back: wheels → motor acting as generator → recovered energy → battery

Pick the chain that truly explains "{subject}", and cut it into {shot_count}
consecutive links. Shot 1 starts the chain, shot {shot_count} closes it.
A sentence that names a part without saying what it does to the next part is
a failure.

── CONDITION 2 — DURATION MATCHES THE NARRATION ──
duration_seconds must sum to EXACTLY {duration}.
Aim for {per_shot}s per shot, roughly {words} French words each.
Never write a tiny sentence to fill a shot. Never write a sentence too long to
be spoken in the time given. If a link deserves more time, give it more seconds
and take them from another shot — the total stays {duration}.

── CONDITION 3 — EVERY SHOT HAS A FUNCTION ──
No decorative shot. Each shot must advance understanding.
"educational_function" answers, in one full sentence: why does this shot exist,
and what does the viewer understand after it that they did not understand
before? Two shots must never claim the same function.

── CONDITION 4 — VISUAL BIBLE FIRST ──
Before writing any image prompt, fill "visual_bible": the one car, the one
environment, the one set of materials, the one lighting, the one palette and
the one camera language that EVERY shot reuses. Be concrete: a colour, a body
type, a floor, named materials.
Then inject that bible into EVERY image_prompt — restate the car, the
environment and the materials in each one. A viewer must believe the
{shot_count} images are {shot_count} views of the same physical car.

── CONDITION 5 — THE IMAGE PROMPT IS SPECIFIC ──
"Electric motor in a car" is rejected. Each image_prompt must state:
  · the subject and the visible components, named
  · where each component sits relative to the others
  · the framing (macro / close-up / medium / wide)
  · the camera angle and the lens feel
  · the depth: what is in focus, what falls off
  · the lighting and where it comes from
  · the environment
  · the materials
  · the relation between the components
  · what must be unmistakably visible
  · the continuity with the other shots
Write it in English. Make it usable as the first frame of an image-to-video
animation: the components that will have to move must already be visible.

── CONDITION 6 — WHAT IS SAID IS WHAT IS SHOWN ──
If the voice says "battery", the battery is clearly visible in that shot.
If it says "motor", the motor is visible. If it describes a flow, the flow is
visible. If it describes a rotation, the rotating part is visible.
Never narrate a component that the image does not show.
Then score it honestly in "semantic_alignment_score" (0 to 1). If your own
score is below 0.8, rewrite the shot BEFORE answering. Do not return a shot
you scored below 0.8.

── CONDITION 10 — NO TEXT IN THE IMAGE ──
Never ask for text, labels, arrows with words, logos or watermarks. Teaching
happens through the framing and the light, not through captions.

── MANDATORY ART DIRECTION ──
Copy this sentence VERBATIM at the end of every image_prompt:
{STYLE_DIRECTIVE}

── ANSWER FORMAT ──
Return only this JSON:
{{
  "subject": "{subject}",
  "duration_seconds": {duration},
  "shot_count": {shot_count},
  "visual_bible": {{
    "vehicle": "...",
    "environment": "...",
    "materials": "...",
    "lighting": "...",
    "color_palette": "...",
    "camera_language": "..."
  }},
  "shots": [
    {{
      "id": 1,
      "duration_seconds": {per_shot},
      "voice": "narration in French, spoken language",
      "visual_description": "in English, what is literally on screen",
      "educational_function": "why this shot exists",
      "image_prompt": "in English, very detailed, ending with the art direction",
      "semantic_alignment_score": 0.95
    }}
  ]
}}
"shots" holds exactly {shot_count} objects, ids 1 to {shot_count}."""


# ---------------------------------------------------------------------------
# ANALYSE DE L'IMAGE  (avant toute animation)
# ---------------------------------------------------------------------------

ANALYSIS_SYSTEM = """\
You are a technical image analyst. You report only what is actually visible in
the image you are given. You never infer, never assume, never describe what
you expect to be there.

You answer with a single valid JSON object and nothing else."""


ANALYSIS_USER = """\
Analyse ONLY what is actually visible in this image.

Do not use the brief that produced it. Do not guess hidden parts. If a
component is not visible, it does not belong in your answer.

Return only this JSON:
{
  "visible_subjects": ["every subject actually visible"],
  "composition": "framing, what sits where in the frame, depth",
  "camera": "apparent angle, height, distance, lens feel",
  "lighting": "direction, quality, contrast, where the light comes from",
  "important_components": ["the components that carry the meaning of the shot"],
  "preserve": ["what must survive an animation untouched: geometry, proportions, identity"],
  "possible_motion": ["motions this exact image could physically support"]
}"""


# ---------------------------------------------------------------------------
# PROMPT D'ANIMATION  (a partir de l'analyse, pas du brief)
# ---------------------------------------------------------------------------

ANIMATION_SYSTEM = """\
You are an image-to-video director for technical and educational animation.
You obey physics before you obey spectacle: a battery does not deform, cells
do not float, a stator stays fixed while its rotor turns, gears turn according
to their real mechanical relation, and energy flows in one coherent direction
without crossing components arbitrarily.

You answer with a single valid JSON object and nothing else."""


def animation_user(voice: str, educational_function: str, analysis_block: str,
                   motion_intents: tuple[str, ...]) -> str:
    return f"""\
Write the animation of ONE shot, from the analysis of the image that exists.

WHAT THE VOICE SAYS OVER THIS SHOT (French):
"{voice}"

WHAT THIS SHOT MUST TEACH:
{educational_function}

WHAT IS ACTUALLY IN THE IMAGE:
{analysis_block}

── THE MOVEMENT MUST EXPLAIN ──
A camera move alone is rejected. "slow zoom in" and "camera slowly moves
forward" are rejected when they carry no information. The motion must make the
viewer understand what the voice is saying.

Name the real components from the analysis above. Say what moves, how it moves,
and what stays perfectly still.

── PHYSICS ──
Nothing deforms, melts, morphs or floats. Geometry, proportions, materials and
the identity of the vehicle are preserved. A rotating part rotates about its
real axis. Its housing stays fixed. Energy travels in a physically coherent
direction, along the parts that actually carry it, never through thin air and
never backwards without a reason the voice gives.
No object is added or removed. No text, label, logo or watermark appears.

── MOTION INTENT ──
"motion_intent" must be exactly one of:
{", ".join(motion_intents)}
Pick the one that matches what the shot teaches. "zoom" is not in the list on
purpose.

── ANSWER FORMAT ──
Return only this JSON:
{{
  "animation_prompt": "the full prompt, in English, ready for an image-to-video model",
  "motion_intent": "one value from the list above",
  "camera_motion": "the camera movement, slow and controlled",
  "mechanical_motion": "which part moves mechanically, and how (or 'none' with the reason)",
  "energy_motion": "the visible energy flow and its direction (or 'none' with the reason)",
  "preserve": ["what must stay untouched"],
  "forbidden": ["deformations and artefacts explicitly banned"]
}}"""
