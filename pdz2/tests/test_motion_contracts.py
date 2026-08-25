"""Programmes de mouvement, caméra et grammaire de mouvement."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pdz2.contracts import (
    CameraMove,
    CameraProgram,
    DepthOfField,
    MotionDescriptor,
    MotionPrimitive,
    MotionProgram,
    PerceptualTarget,
    Trajectory,
    Vec3,
)
from pdz2.tests import factories


class TestCameraContradictions:
    def test_locked_camera_cannot_pan(self) -> None:
        """L'exemple exact du cahier des charges §13."""
        with pytest.raises(ValidationError, match="locked=true et move=pan"):
            CameraProgram(locked=True, move=CameraMove.PAN, velocity=0.3)

    def test_locked_camera_cannot_have_velocity(self) -> None:
        with pytest.raises(ValidationError, match="velocity"):
            CameraProgram(locked=True, move=CameraMove.LOCK, velocity=0.3)

    def test_locked_camera_cannot_have_a_moving_trajectory(self) -> None:
        with pytest.raises(ValidationError, match="trajectoire"):
            CameraProgram(
                locked=True,
                move=CameraMove.LOCK,
                trajectory=Trajectory(
                    primitive=MotionPrimitive.LINEAR,
                    control_points=[Vec3(), Vec3(z=1.0)],
                    amplitude=1.0,
                ),
            )

    def test_a_move_without_velocity_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="sans vitesse"):
            CameraProgram(move=CameraMove.DOLLY, velocity=0.0)

    def test_orbit_requires_an_orbital_trajectory(self) -> None:
        with pytest.raises(ValidationError, match="orbit exige"):
            CameraProgram(
                move=CameraMove.ORBIT,
                velocity=0.5,
                trajectory=Trajectory(
                    primitive=MotionPrimitive.LINEAR,
                    control_points=[Vec3(), Vec3(x=1.0)],
                    amplitude=1.0,
                ),
            )

    def test_a_valid_moving_camera_is_accepted(self) -> None:
        program = factories.moving_camera_program()
        assert program.move is CameraMove.PUSH_IN
        assert program.velocity > 0


class TestMotionGrammar:
    """Chaque primitive est paramétrée numériquement, jamais par une phrase."""

    def test_static_primitive_refuses_amplitude(self) -> None:
        with pytest.raises(ValidationError, match="'static' avec un mouvement"):
            Trajectory(primitive=MotionPrimitive.STATIC, amplitude=2.0)

    def test_linear_needs_two_control_points(self) -> None:
        with pytest.raises(ValidationError, match="deux points de contrôle"):
            Trajectory(
                primitive=MotionPrimitive.LINEAR,
                control_points=[Vec3()],
                amplitude=1.0,
            )

    def test_arc_needs_three_control_points(self) -> None:
        with pytest.raises(ValidationError, match="trois points de contrôle"):
            Trajectory(
                primitive=MotionPrimitive.ARC,
                control_points=[Vec3(), Vec3(x=1.0)],
                amplitude=1.0,
            )

    def test_oscillate_needs_a_frequency(self) -> None:
        with pytest.raises(ValidationError, match="fréquence"):
            Trajectory(primitive=MotionPrimitive.OSCILLATE, amplitude=0.2)

    def test_orbit_needs_an_axis(self) -> None:
        with pytest.raises(ValidationError, match="axe de rotation"):
            Trajectory(primitive=MotionPrimitive.ORBIT, amplitude=90.0)

    def test_a_moving_primitive_needs_amplitude(self) -> None:
        with pytest.raises(ValidationError, match="amplitude"):
            Trajectory(
                primitive=MotionPrimitive.LINEAR,
                control_points=[Vec3(), Vec3(x=1.0)],
                amplitude=0.0,
            )

    def test_a_fully_parameterised_orbit_is_accepted(self) -> None:
        trajectory = Trajectory(
            primitive=MotionPrimitive.ORBIT,
            amplitude=120.0,
            axis=Vec3(y=1.0),
        )
        assert trajectory.amplitude == 120.0


class TestDepthOfField:
    def test_focus_pull_needs_a_target(self) -> None:
        with pytest.raises(ValidationError, match="distance cible"):
            DepthOfField(focus_distance_m=1.0, f_stop=2.8, focus_pull=True)

    def test_target_without_pull_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="sans bascule"):
            DepthOfField(focus_distance_m=1.0, f_stop=2.8, focus_target_m=3.0)


class TestMotionDescriptor:
    def test_static_descriptor_refuses_magnitude(self) -> None:
        with pytest.raises(ValidationError, match="'static' avec une magnitude"):
            MotionDescriptor(primitive=MotionPrimitive.STATIC, magnitude=1.0)

    def test_descriptor_and_trajectory_must_agree(self) -> None:
        with pytest.raises(ValidationError, match="divergentes"):
            MotionDescriptor(
                primitive=MotionPrimitive.ROTATE,
                magnitude=1.0,
                trajectory=Trajectory(
                    primitive=MotionPrimitive.LINEAR,
                    control_points=[Vec3(), Vec3(x=1.0)],
                    amplitude=1.0,
                ),
            )


class TestMotionProgram:
    def test_must_preserve_and_forbidden_cannot_overlap(self) -> None:
        with pytest.raises(ValidationError, match="must_preserve/forbidden"):
            factories.motion_program(
                must_preserve=["couleur du carter"],
                may_change=[],
                forbidden=["couleur du carter"],
            )

    def test_must_preserve_and_may_change_cannot_overlap(self) -> None:
        with pytest.raises(ValidationError, match="must_preserve/may_change"):
            factories.motion_program(
                must_preserve=["angle"], may_change=["angle"], forbidden=[]
            )

    def test_a_moving_shot_declares_an_intensity(self) -> None:
        with pytest.raises(ValidationError, match="intensité nulle"):
            factories.motion_program(intensity=0.0)

    def test_a_static_shot_cannot_claim_intensity(self) -> None:
        with pytest.raises(ValidationError, match="statique avec une intensité"):
            MotionProgram(
                shot_id="S01",
                camera_program_id="camera_program-x",
                intensity=0.4,
                perceptual_target=PerceptualTarget(
                    motion_energy=0.0, visual_novelty=0.0, readability=1.0
                ),
            )

    def test_a_fully_static_program_is_accepted(self) -> None:
        program = MotionProgram(
            shot_id="S01",
            camera_program_id="camera_program-x",
            perceptual_target=PerceptualTarget(
                motion_energy=0.0, visual_novelty=0.0, readability=1.0
            ),
        )
        assert program.intensity == 0.0

    def test_a_valid_moving_program_is_accepted(self) -> None:
        program = factories.motion_program()
        assert program.intensity > 0
        assert program.subject_motion.primitive is MotionPrimitive.ROTATE
