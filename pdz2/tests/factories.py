"""Constructeurs d'objets valides pour les tests.

Chaque fabrique retourne un contrat *valide*. Les tests d'invariant partent
d'un objet valide et cassent une seule chose à la fois : l'échec attendu
désigne alors sans ambiguïté la règle testée.
"""

from __future__ import annotations

from pdz2.contracts import (
    AnchorKind,
    AnchorSpec,
    AttributeBinding,
    CameraMove,
    CameraProgram,
    Claim,
    ClaimKind,
    Composition,
    Curve,
    CurvePoint,
    Degradation,
    DirectorState,
    Easing,
    Evidence,
    EvidenceStance,
    Framing,
    IdentityAttribute,
    MotionDescriptor,
    MotionPrimitive,
    MotionProgram,
    NarrativeFunction,
    Pacing,
    PerceptualTarget,
    RenderSpecExecutable,
    RenderSpecRequested,
    RenderStrategy,
    Resolution,
    ScriptLine,
    ScriptState,
    ShotIntent,
    ShotSpec,
    SourceKind,
    SourceReference,
    Tone,
    Trajectory,
    Vec3,
    VerificationStatus,
    VisualEvidencePlan,
    VisualLanguage,
    VoiceSegment,
    VoiceTimeline,
)
from pdz2.contracts.script import TimingSource

VERTICAL = Resolution(width=1080, height=1920)


def source(**overrides) -> SourceReference:
    payload = {
        "title": "Fonctionnement d'un moteur synchrone",
        "kind": SourceKind.DOCUMENTATION,
        "url": "https://example.org/moteur",
        "authority": 0.8,
    }
    return SourceReference(**(payload | overrides))


def evidence(source_id: str, **overrides) -> Evidence:
    payload = {
        "source_id": source_id,
        "stance": EvidenceStance.SUPPORTS,
        "quote": "Le champ tournant du stator entraîne le rotor.",
        "strength": 0.8,
    }
    return Evidence(**(payload | overrides))


def claim(evidence_ids: list[str] | None = None, **overrides) -> Claim:
    ids = evidence_ids or []
    payload = {
        "text": "Le moteur transforme l'électricité en mouvement.",
        "kind": ClaimKind.MECHANISM,
        "evidence_ids": ids,
        "verification": (
            VerificationStatus.CORROBORATED if ids else VerificationStatus.UNVERIFIED
        ),
        "confidence": 0.85 if ids else 0.0,
        "load_bearing": True,
        "causal_mechanism": "Le courant crée un champ magnétique tournant.",
        # Les appelants qui construisent plusieurs preuves doivent varier ce
        # texte : deux preuves au même mécanisme sont refusées par le brief.
        "evidence_required": "Voir le courant, le champ, puis la rotation.",
        "visual_proof": (
            "Coupe transparente du moteur montrant le courant, le champ "
            "magnétique et la rotation du rotor."
        ),
        "visually_demonstrable": True,
    }
    return Claim(**(payload | overrides))


def anchor(**overrides) -> AnchorSpec:
    payload = {
        "name": "moteur-coupe",
        "kind": AnchorKind.MACHINE,
        "canonical_description": "Moteur synchrone en coupe, carter bleu nuit.",
        "identity": [
            IdentityAttribute(name="carter", value="bleu nuit mat"),
            IdentityAttribute(
                name="angle", value="trois quarts", binding=AttributeBinding.SOFT
            ),
        ],
    }
    return AnchorSpec(**(payload | overrides))


def curve(name: str = "emotional") -> Curve:
    return Curve(
        name=name,
        points=[
            CurvePoint(t=0.0, value=0.4),
            CurvePoint(t=0.5, value=0.7),
            CurvePoint(t=1.0, value=0.9),
        ],
    )


def shot_intent(order: int = 0, claim_id: str | None = None, **overrides) -> ShotIntent:
    payload = {
        "order": order,
        "narrative_function": NarrativeFunction.MECHANISM,
        "claim_id": claim_id,
        "what_the_viewer_must_understand": "Le courant devient rotation.",
        "what_the_viewer_must_see": "Le rotor tourne quand le courant circule.",
        "target_duration_s": 6.0,
    }
    return ShotIntent(**(payload | overrides))


def director_state(**overrides) -> DirectorState:
    a_claim = claim([evidence(source().id).id])
    an_anchor = anchor()
    payload = {
        "research_state_id": "research_state-x",
        "topic_request_id": "topic_request-x",
        "thesis": "Une voiture électrique convertit de l'énergie stockée en rotation.",
        "audience": "grand public curieux",
        "tone": Tone.DOCUMENTARY,
        "pacing": Pacing.MEASURED,
        "causal_chain": [a_claim.id],
        "claim_ids": [a_claim.id],
        "evidence_plan": [
            VisualEvidencePlan(
                claim_id=a_claim.id,
                causal_mechanism=a_claim.causal_mechanism,
                evidence_required=a_claim.evidence_required,
                visual_proof=a_claim.visual_proof,
            )
        ],
        "visual_language": VisualLanguage(visual_register="documentaire technique"),
        "continuity_anchors": [an_anchor],
        "shot_intents": [
            shot_intent(0, a_claim.id, anchor_ids=[an_anchor.id]),
        ],
        "emotional_curve": curve(),
        "information_density": 0.6,
        "ending_payoff": "On comprend pourquoi le couple est immédiat.",
    }
    return DirectorState(**(payload | overrides))


def script_line(index: int = 0, **overrides) -> ScriptLine:
    payload = {
        "index": index,
        "text": "Le courant traverse le stator et fait tourner le rotor.",
        "function": NarrativeFunction.MECHANISM,
        "energy": 0.6,
        "emphasis_words": ["rotor"],
        "visual_requirement": "Coupe du moteur, courant visible.",
        "estimated_duration_s": 4.0,
    }
    return ScriptLine(**(payload | overrides))


def script_state(lines: int = 2, **overrides) -> ScriptState:
    payload = {
        "director_state_id": "director_state-x",
        "lines": [script_line(index) for index in range(lines)],
    }
    return ScriptState(**(payload | overrides))


def voice_timeline(script: ScriptState | None = None, **overrides) -> VoiceTimeline:
    script = script or script_state()
    segments = []
    cursor = 0.0
    for line in script.lines:
        segments.append(
            VoiceSegment(
                line_id=line.id,
                line_index=line.index,
                start_s=cursor,
                end_s=cursor + 3.5,
            )
        )
        cursor += 3.6
    payload = {
        "script_state_id": script.id,
        "audio_path": "voice.wav",
        "sample_rate": 48000,
        "total_duration_s": cursor,
        "timing_source": TimingSource.MEASURED_TTS,
        "segments": segments,
    }
    return VoiceTimeline(**(payload | overrides))


def camera_program(**overrides) -> CameraProgram:
    payload = {"move": CameraMove.LOCK, "locked": True}
    return CameraProgram(**(payload | overrides))


def moving_camera_program(**overrides) -> CameraProgram:
    payload = {
        "move": CameraMove.PUSH_IN,
        "locked": False,
        "velocity": 0.4,
        "trajectory": Trajectory(
            primitive=MotionPrimitive.LINEAR,
            control_points=[Vec3(z=0.0), Vec3(z=1.2)],
            amplitude=1.2,
            easing=Easing.EASE_IN_OUT,
        ),
    }
    return CameraProgram(**(payload | overrides))


def motion_descriptor(moving: bool = False) -> MotionDescriptor:
    if not moving:
        return MotionDescriptor()
    return MotionDescriptor(
        primitive=MotionPrimitive.ROTATE,
        magnitude=1.0,
        direction=Vec3(y=1.0),
        trajectory=Trajectory(
            primitive=MotionPrimitive.ROTATE,
            amplitude=360.0,
            axis=Vec3(y=1.0),
        ),
    )


def motion_program(shot_id: str = "S01", **overrides) -> MotionProgram:
    payload = {
        "shot_id": shot_id,
        "camera_program_id": camera_program().id,
        "subject_motion": motion_descriptor(moving=True),
        "intensity": 0.5,
        "must_preserve": ["identité du moteur"],
        "may_change": ["éclairage"],
        "forbidden": ["changement de couleur du carter"],
        "perceptual_target": PerceptualTarget(
            motion_energy=0.5, visual_novelty=0.4, readability=0.9
        ),
    }
    return MotionProgram(**(payload | overrides))


def composition(**overrides) -> Composition:
    payload = {"framing": Framing.CUTAWAY_DIAGRAM}
    return Composition(**(payload | overrides))


def shot_spec(shot_id: str = "S01", **overrides) -> ShotSpec:
    payload = {
        "shot_id": shot_id,
        "duration_s": 6.0,
        "narrative_function": NarrativeFunction.MECHANISM,
        "claim_id": "claim-x",
        "evidence_required": "Voir le rotor tourner sous l'effet du courant.",
        "visual_subject": "Moteur synchrone en coupe.",
        "composition": composition(),
        "camera_program_id": camera_program().id,
    }
    return ShotSpec(**(payload | overrides))


def render_spec_requested(**overrides) -> RenderSpecRequested:
    payload = {
        "shot_id": "S01",
        "motion_program_id": "motion_program-x",
        "camera_program_id": "camera_program-x",
        "duration_s": 6.0,
        "resolution": VERTICAL,
        "fps": 24,
        "requested_camera": CameraMove.ORBIT,
    }
    return RenderSpecRequested(**(payload | overrides))


def render_spec_executable(
    requested: RenderSpecRequested | None = None,
    **overrides,
) -> RenderSpecExecutable:
    requested = requested or render_spec_requested()
    payload = {
        "requested_spec_id": requested.id,
        "shot_id": requested.shot_id,
        "requested": requested.echo(),
        "strategy": RenderStrategy.PARALLAX_2_5D,
        "execution_camera": requested.requested_camera,
        "duration_s": requested.duration_s,
        "resolution": requested.resolution,
        "fps": requested.fps,
    }
    fusion = payload | overrides
    # Nommer un fournisseur exige de montrer sur quoi on s'est fondé : les
    # fabriques qui en posent un fournissent donc un instantané.
    if fusion.get("provider") and not fusion.get("capability_snapshot_id"):
        fusion["capability_snapshot_id"] = "capability_matrix-fabrique"
    return RenderSpecExecutable(**fusion)


def camera_degradation(**overrides) -> Degradation:
    payload = {
        "field": "camera",
        "requested": "orbit",
        "executed": "none",
        "reason": "provider does not expose required camera control",
        "description": "camera orbit replaced by deterministic 2.5D approximation",
    }
    return Degradation(**(payload | overrides))


__all__ = [name for name in dir() if not name.startswith("_")]
