"""Direction artistique et prompts envoyes a OpenAI.

Tout le texte adresse a OpenAI vit ici : c'est le seul fichier a ouvrir
pour changer le ton, le style ou les regles de continuite.
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

# Signature courte servant a verifier que la direction artistique n'a pas ete oubliee.
STYLE_FINGERPRINT = "Photorealistic premium 3D engineering visualization"

CONTINUITY_RULES = """\
Continuity is mandatory across every shot:
- the SAME white electric car, identical body design, identical proportions
- the SAME dark studio environment and floor
- the SAME materials (white matte paint, brushed aluminium, dark composite, copper windings)
- the SAME lighting setup and colour temperature
- the SAME visual logic: each shot is a closer or different view of that one car
Never introduce a second car, a different colour, an outdoor location or a new style."""


def enforce_style(image_prompt: str) -> str:
    """Garantit que la direction artistique est bien dans le prompt photo."""
    if STYLE_FINGERPRINT.lower() in image_prompt.lower():
        return image_prompt
    return f"{image_prompt.rstrip().rstrip('.')}. {STYLE_DIRECTIVE}"


# ---------------------------------------------------------------------------
# ETAPE 2 - storyboard
# ---------------------------------------------------------------------------

STORYBOARD_SYSTEM = """\
You are a director of short vertical educational videos.
You answer with a single JSON object and nothing else. No markdown, no commentary."""


def storyboard_user(subject: str, duration: int, shot_count: int) -> str:
    per_shot = round(duration / shot_count, 1)
    return f"""\
Create the storyboard of a vertical 9:16 educational video.

SUBJECT: {subject}
TOTAL DURATION: {duration} seconds
NUMBER OF SHOTS: {shot_count} (about {per_shot} seconds each)

MANDATORY ART DIRECTION - copy this sentence verbatim at the end of EVERY image_prompt:
{STYLE_DIRECTIVE}

{CONTINUITY_RULES}

For each shot produce:
- "voice": the narration actually spoken during this shot, in French, natural spoken
  language, short enough to be said in about {per_shot} seconds (roughly 10 to 14 words).
- "visual_description": in English, what is literally visible on screen: subject,
  framing, camera angle, lens feel, lighting, visible components, their position.
- "image_prompt": in English, a very detailed still-image prompt for this exact shot.
  It must describe the same white electric car as the other shots, state the framing and
  the visible mechanical parts precisely, and end with the mandatory art direction
  sentence copied verbatim.

The image of a shot must show EXACTLY what the voice of that shot is talking about.
The {shot_count} shots must tell one continuous explanation, not {shot_count} isolated facts.

Answer with exactly this JSON shape:
{{
  "subject": "{subject}",
  "duration": {duration},
  "visual_style": "one sentence summarising the art direction",
  "visual_continuity": "one paragraph describing precisely the car, environment and \
materials that every shot must reuse",
  "shots": [
    {{
      "id": 1,
      "duration": "{per_shot}s",
      "voice": "...",
      "visual_description": "...",
      "image_prompt": "..."
    }}
  ]
}}
The "shots" array must contain exactly {shot_count} objects, with ids 1 to {shot_count}."""


# ---------------------------------------------------------------------------
# ETAPE 6 - analyse d'image et prompt d'animation
# ---------------------------------------------------------------------------

ANIMATION_SYSTEM = """\
You are an image-to-video director specialised in technical and educational animation.
You look at the image you are given, you describe nothing back, and you answer with a
single JSON object: {"animation_prompt": "..."} and nothing else."""


def animation_user(voice: str, visual_description: str) -> str:
    return f"""\
Here is the still image generated for one shot of an educational video.

The narration spoken over this shot is (French):
"{voice}"

The shot was meant to show:
{visual_description}

First, look at the image and identify what is ACTUALLY there: the car, its position and
framing, the visible mechanical components and where they are, the camera angle, the
lighting, every object present, and what must be preserved.

Then write ONE image-to-video animation prompt for THIS exact image.

Hard requirements for the animation prompt:
- It must be PEDAGOGICAL: the movement has to explain what the voice is saying.
  A plain "zoom in" or "cinematic camera move" is not acceptable on its own.
- Say explicitly WHAT MOVES and HOW it moves (rotation, energy flow, mechanical travel,
  progressive reveal), naming the real components you can see in the image.
- Say explicitly WHAT MUST STAY PERFECTLY STILL.
- Describe the camera movement, slow and controlled.
- If the narration mentions energy, describe a visible energy flow with a physically
  coherent direction (for example battery towards motor).
- If the narration mentions a mechanical part, describe its real mechanical motion
  (for example rotor rotating while the stator stays fixed).
- Demand preservation of geometry, proportions, materials and identity of the car.
- Forbid any deformation, morphing, warping, added or removed object, text or logo.

Answer only with: {{"animation_prompt": "..."}}"""
