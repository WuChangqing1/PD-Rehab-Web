"""Pose metric tests.

The maths is tested with a synthetic landmark series that is generated from a
known geometry, so the expected angle is known exactly and a failure points at
the code rather than at a model. Detection itself is verified separately against
a real photograph (see docs/metric_definitions.md section 3, Phase 6 notes).
"""

from __future__ import annotations

import math
import random

import pytest

from app.ml.pose.analyzer import (
    GATE_INSUFFICIENT_REPETITIONS,
    GATE_LOW_LANDMARK_VISIBILITY,
    GATE_LOW_VALID_FRAME_RATIO,
    GATE_NO_MOVEMENT_DETECTED,
    GATE_NO_POSE_DETECTED,
    GATE_VIDEO_TOO_SHORT,
    analyse,
)
from app.ml.pose.landmarks import (
    LEFT_ELBOW,
    LEFT_HIP,
    LEFT_SHOULDER,
    LEFT_WRIST,
    LANDMARK_COUNT,
    RIGHT_ELBOW,
    RIGHT_HIP,
    RIGHT_SHOULDER,
    RIGHT_WRIST,
    Landmark,
    PoseSeries,
)
from app.ml.pose.metrics import (
    ANALYSIS_CONFIG,
    abduction_series,
    analyse_series,
    angle_deg,
    count_repetitions,
    elbow_series,
    hold_time_sec,
    left_right_difference_deg,
    midpoint,
    moving_average,
    movement_speed_deg_per_sec,
    percentile,
    tilt_from_vertical_deg,
    trunk_tilt_series,
)

FPS = 30.0
WIDTH = 640
HEIGHT = 480


# --------------------------------------------------------------------------- #
# synthetic subjects
# --------------------------------------------------------------------------- #
def _blank_frame(visibility: float = 0.9) -> list[Landmark]:
    return [Landmark(0.5, 0.5, 0.0, visibility, visibility) for _ in range(LANDMARK_COUNT)]


def _set(frame: list[Landmark], index: int, x: float, y: float, visibility: float | None = None) -> None:
    previous = frame[index]
    frame[index] = Landmark(
        x, y, previous.z, previous.visibility if visibility is None else visibility,
        previous.presence if visibility is None else visibility,
    )


def arm_frame(
    *,
    left_abduction: float = 0.0,
    right_abduction: float = 0.0,
    left_elbow: float = 180.0,
    right_elbow: float = 180.0,
    trunk_tilt: float = 0.0,
    visibility: float = 0.9,
) -> list[Landmark]:
    """One frame with the arms placed at an exactly known abduction angle.

    `abduction` is the angle at the shoulder between the hip and the elbow:
    0 = arm hanging down, 90 = horizontal, 180 = straight up.

    The geometry is built in PIXEL coordinates and only then converted to the
    normalised coordinates MediaPipe returns. Building it in normalised space
    would be wrong: x and y have different pixel scales, so a 20 degree lean in
    normalised space is not a 20 degree lean in the image, and the metrics --
    which correctly measure in pixel space -- would report something else.
    """
    frame = _blank_frame(visibility)

    torso = 120.0  # shoulder to hip, pixels
    upper = 67.0
    fore = 67.0
    half_shoulder = 32.0

    lean = math.radians(trunk_tilt)
    hip_left = (0.46 * WIDTH, 0.70 * HEIGHT)
    hip_right = (0.54 * WIDTH, 0.70 * HEIGHT)
    hip_mid = midpoint(hip_left, hip_right)
    shoulder_mid = (
        hip_mid[0] + torso * math.sin(lean),
        hip_mid[1] - torso * math.cos(lean),
    )
    across = (math.cos(lean), math.sin(lean))
    left_shoulder = (
        shoulder_mid[0] - half_shoulder * across[0],
        shoulder_mid[1] - half_shoulder * across[1],
    )
    right_shoulder = (
        shoulder_mid[0] + half_shoulder * across[0],
        shoulder_mid[1] + half_shoulder * across[1],
    )

    def rotate(vector: tuple[float, float], degrees: float) -> tuple[float, float]:
        theta = math.radians(degrees)
        return (
            vector[0] * math.cos(theta) - vector[1] * math.sin(theta),
            vector[0] * math.sin(theta) + vector[1] * math.cos(theta),
        )

    def limb(hip, shoulder, abduction_deg: float, elbow_deg: float, sign: float):
        ux, uy = hip[0] - shoulder[0], hip[1] - shoulder[1]
        norm = math.hypot(ux, uy) or 1.0
        u = (ux / norm, uy / norm)
        upper_dir = rotate(u, sign * abduction_deg)
        elbow = (shoulder[0] + upper * upper_dir[0], shoulder[1] + upper * upper_dir[1])
        fore_dir = rotate(upper_dir, sign * (180.0 - elbow_deg))
        wrist = (elbow[0] + fore * fore_dir[0], elbow[1] + fore * fore_dir[1])
        return elbow, wrist

    left_elbow_pt, left_wrist_pt = limb(hip_left, left_shoulder, left_abduction, left_elbow, -1.0)
    right_elbow_pt, right_wrist_pt = limb(hip_right, right_shoulder, right_abduction, right_elbow, 1.0)

    def put(index: int, point: tuple[float, float]) -> None:
        _set(frame, index, point[0] / WIDTH, point[1] / HEIGHT)

    put(LEFT_HIP, hip_left)
    put(RIGHT_HIP, hip_right)
    put(LEFT_SHOULDER, left_shoulder)
    put(RIGHT_SHOULDER, right_shoulder)
    put(LEFT_ELBOW, left_elbow_pt)
    put(RIGHT_ELBOW, right_elbow_pt)
    put(LEFT_WRIST, left_wrist_pt)
    put(RIGHT_WRIST, right_wrist_pt)
    return frame


def series_from_frames(frames: list[list[Landmark] | None], fps: float = FPS) -> PoseSeries:
    return PoseSeries(
        fps=fps, width=WIDTH, height=HEIGHT, frame_count=len(frames), frames=frames
    )


def constant_subject(frames: int = 90, **kwargs) -> PoseSeries:
    return series_from_frames([arm_frame(**kwargs) for _ in range(frames)])


def raise_cycles(
    cycles: int = 3,
    *,
    frames_per_cycle: int = 30,
    low: float = 10.0,
    high: float = 170.0,
    fps: float = FPS,
) -> PoseSeries:
    """A subject raising both arms and lowering them, `cycles` times."""
    frames: list[list[Landmark] | None] = []
    for _ in range(cycles):
        for i in range(frames_per_cycle):
            phase = 2 * math.pi * i / frames_per_cycle
            angle = low + (high - low) * (1 - math.cos(phase)) / 2
            frames.append(arm_frame(left_abduction=angle, right_abduction=angle))
    return series_from_frames(frames, fps=fps)


# --------------------------------------------------------------------------- #
# geometry
# --------------------------------------------------------------------------- #
def test_angle_deg_right_angle_and_straight_line():
    assert angle_deg((0, 1), (0, 0), (1, 0)) == pytest.approx(90.0)
    assert angle_deg((0, 1), (0, 0), (0, -1)) == pytest.approx(180.0)
    assert angle_deg((0, 0.5), (0, 0), (0, 1)) == pytest.approx(0.0)


def test_angle_deg_returns_nan_for_degenerate_input():
    assert math.isnan(angle_deg((0, 0), (0, 0), (1, 1)))


def test_tilt_from_vertical_is_signed():
    # Upper point to the image-right of the lower point.
    assert tilt_from_vertical_deg((0.5, 0.7), (0.6, 0.5)) == pytest.approx(26.565, abs=1e-3)
    assert tilt_from_vertical_deg((0.5, 0.7), (0.4, 0.5)) == pytest.approx(-26.565, abs=1e-3)
    assert tilt_from_vertical_deg((0.5, 0.7), (0.5, 0.4)) == pytest.approx(0.0)


def test_midpoint():
    assert midpoint((0.0, 0.0), (1.0, 2.0)) == (0.5, 1.0)


def test_percentile_interpolates():
    values = [0.0, 10.0, 20.0, 30.0, 40.0]
    assert percentile(values, 0.0) == 0.0
    assert percentile(values, 1.0) == 40.0
    assert percentile(values, 0.5) == pytest.approx(20.0)
    assert percentile(values, 0.25) == pytest.approx(10.0)
    assert math.isnan(percentile([], 0.5))


def test_moving_average_ignores_nan():
    values = [1.0, float("nan"), 3.0, 4.0, 5.0]
    smoothed = moving_average(values, 3)
    assert len(smoothed) == len(values)
    assert all(not math.isnan(v) for v in smoothed)
    # The centred window at index 1 only has 1.0 and 3.0 in range.
    assert smoothed[1] == pytest.approx(2.0)


# --------------------------------------------------------------------------- #
# repetition counting
# --------------------------------------------------------------------------- #
def test_count_repetitions_counts_clean_cycles():
    series = raise_cycles(cycles=3, frames_per_cycle=30)
    values = moving_average(abduction_series(series, "left"), 5)
    count, intervals = count_repetitions(values, low=40.0, high=140.0, fps=FPS)
    assert count == 3
    assert len(intervals) == 2
    for interval in intervals:
        assert interval == pytest.approx(30, abs=3)


def test_count_repetitions_ignores_a_flat_signal():
    """A patient holding still must not be credited with repetitions."""
    series = constant_subject(left_abduction=90.0)
    values = moving_average(abduction_series(series, "left"), 5)
    count, intervals = count_repetitions(values, low=40.0, high=140.0, fps=FPS)
    assert count == 0
    assert intervals == []


def test_count_repetitions_ignores_noise_around_one_level():
    random.seed(20260929)
    frames = [arm_frame(left_abduction=90.0 + random.uniform(-3, 3)) for _ in range(120)]
    values = moving_average(abduction_series(series_from_frames(frames), "left"), 5)
    count, _ = count_repetitions(values, low=40.0, high=140.0, fps=FPS)
    assert count == 0


def test_count_repetitions_merges_peaks_that_are_too_close():
    min_gap = int(ANALYSIS_CONFIG["min_repetition_interval_frames"])
    values = [0.0] * 3 + [200.0] + [0.0] * 3 + [200.0] + [0.0] * 3
    count, _ = count_repetitions(values, low=50.0, high=150.0, fps=FPS)
    # The two peaks are only 4 frames apart, so the second is not counted.
    assert min_gap > 4
    assert count == 1


def test_count_repetitions_rejects_an_empty_or_inverted_band():
    assert count_repetitions([], low=1.0, high=2.0, fps=FPS) == (0, [])
    assert count_repetitions([1.0, 2.0], low=2.0, high=2.0, fps=FPS) == (0, [])


# --------------------------------------------------------------------------- #
# hold time and speed
# --------------------------------------------------------------------------- #
def test_hold_time_measures_the_longest_plateau():
    # 30 frames down, 60 frames held at the top, 30 frames down, at 30 fps.
    frames = (
        [arm_frame(left_abduction=10.0) for _ in range(30)]
        + [arm_frame(left_abduction=170.0) for _ in range(60)]
        + [arm_frame(left_abduction=10.0) for _ in range(30)]
    )
    values = moving_average(abduction_series(series_from_frames(frames), "left"), 5)
    peak = max(v for v in values if not math.isnan(v))
    measured = hold_time_sec(values, peak=peak, fps=FPS)
    assert measured is not None

    # The plateau is 60 frames = 2.00 s. The centred moving average trims
    # `hold_time_smoothing_bias_frames` from each end, which is the documented,
    # reproducible relationship -- not a tolerance to hide a drift behind.
    bias_frames = int(ANALYSIS_CONFIG["hold_time_smoothing_bias_frames"])
    expected = (60 - 2 * bias_frames) / FPS
    assert measured == pytest.approx(expected, abs=1.0 / FPS)
    assert measured == pytest.approx(1.867, abs=0.04)


def test_hold_time_bias_is_documented_and_matches_the_measurement():
    """Locks the documented bias to what the code actually does."""
    window = int(ANALYSIS_CONFIG["smoothing_window_frames"])
    documented = int(ANALYSIS_CONFIG["hold_time_smoothing_bias_frames"])
    assert documented == (window - 1) // 2


def test_movement_speed_is_zero_for_a_held_position():
    series = constant_subject(left_abduction=120.0)
    values = moving_average(abduction_series(series, "left"), 5)
    speed = movement_speed_deg_per_sec(values, fps=FPS)
    assert speed is not None
    assert speed == pytest.approx(0.0, abs=1e-6)


def test_movement_speed_matches_a_known_ramp():
    # 10 degrees per frame at 30 fps is 300 deg/s.
    frames = [arm_frame(left_abduction=10.0 + 10.0 * i) for i in range(16)]
    frames = [arm_frame(left_abduction=10.0 + 10.0 * i) for i in range(16)]
    values = abduction_series(series_from_frames(frames), "left")
    speed = movement_speed_deg_per_sec(values, fps=FPS)
    assert speed == pytest.approx(300.0, rel=0.02)


def test_left_right_difference_deg():
    assert left_right_difference_deg(150.0, 140.0) == pytest.approx(10.0)
    assert left_right_difference_deg(None, 140.0) is None


# --------------------------------------------------------------------------- #
# series analysis
# --------------------------------------------------------------------------- #
def test_analyse_series_recovers_a_known_movement():
    series = raise_cycles(cycles=4, frames_per_cycle=30, low=10.0, high=170.0)
    values = abduction_series(series, "left")
    stats = analyse_series(values, FPS)

    assert stats.peak_deg == pytest.approx(170.0, abs=8.0)
    assert stats.min_deg == pytest.approx(10.0, abs=8.0)
    assert stats.range_deg == pytest.approx(160.0, abs=12.0)
    assert stats.repetition_count == 4
    assert stats.movement_speed_deg_per_sec is not None
    assert stats.movement_speed_deg_per_sec > 100
    assert stats.valid_sample_ratio == 1.0


def test_analyse_series_on_an_empty_series_returns_nothing():
    stats = analyse_series([], FPS)
    assert stats.peak_deg is None
    assert stats.repetition_count == 0
    assert stats.valid_sample_ratio == 0.0


def test_analyse_series_never_returns_nan():
    series = series_from_frames([None] * 30)
    stats = analyse_series(abduction_series(series, "left"), FPS)
    for value in (stats.peak_deg, stats.min_deg, stats.range_deg, stats.hold_time_sec):
        assert value is None


def test_trunk_tilt_series_is_signed_and_matches_the_input():
    frames = [arm_frame(trunk_tilt=20.0) for _ in range(30)]
    values = [v for v in trunk_tilt_series(series_from_frames(frames)) if not math.isnan(v)]
    assert values
    assert all(v == pytest.approx(20.0, abs=1.0) for v in values)

    frames = [arm_frame(trunk_tilt=-15.0) for _ in range(30)]
    values = [v for v in trunk_tilt_series(series_from_frames(frames)) if not math.isnan(v)]
    assert all(v == pytest.approx(-15.0, abs=1.0) for v in values)


def test_elbow_series_recovers_the_modelled_elbow_angle():
    frames = [arm_frame(left_abduction=90.0, left_elbow=90.0) for _ in range(10)]
    values = [v for v in elbow_series(series_from_frames(frames), "left") if not math.isnan(v)]
    assert values
    assert values[0] == pytest.approx(90.0, abs=2.0)


# --------------------------------------------------------------------------- #
# quality gates
# --------------------------------------------------------------------------- #
def test_no_pose_gate():
    outcome = analyse(series_from_frames([None] * 60), "MOUNTAIN_ARMS_UP")
    assert not outcome.accepted
    assert GATE_NO_POSE_DETECTED in outcome.gate_failures
    assert outcome.metrics["valid_pose_frame_ratio"] == 0.0


def test_video_too_short_gate():
    series = series_from_frames([arm_frame() for _ in range(10)], fps=FPS)
    outcome = analyse(series, "MOUNTAIN_ARMS_UP")
    assert GATE_VIDEO_TOO_SHORT in outcome.gate_failures


def test_low_valid_frame_ratio_gate():
    frames = [arm_frame() for _ in range(10)] + [None] * 50
    outcome = analyse(series_from_frames(frames), "MOUNTAIN_ARMS_UP")
    assert GATE_LOW_VALID_FRAME_RATIO in outcome.gate_failures


def test_holding_still_fails_the_movement_gate():
    outcome = analyse(constant_subject(left_abduction=90.0, right_abduction=90.0), "MOUNTAIN_ARMS_UP")
    assert not outcome.accepted
    assert GATE_NO_MOVEMENT_DETECTED in outcome.gate_failures
    assert GATE_INSUFFICIENT_REPETITIONS in outcome.gate_failures


def test_low_visibility_gate():
    frames = [
        arm_frame(left_abduction=10.0 + (160.0 * i / 29), right_abduction=10.0 + (160.0 * i / 29), visibility=0.2)
        for i in range(30)
    ]
    outcome = analyse(series_from_frames(frames), "MOUNTAIN_ARMS_UP")
    assert GATE_LOW_LANDMARK_VISIBILITY in outcome.gate_failures


def test_missing_visibility_is_not_treated_as_zero():
    """The hand model reports no visibility at all; that must not fail the gate."""
    frame = arm_frame(left_abduction=20.0, right_abduction=20.0)
    stripped = [
        Landmark(lm.x, lm.y, lm.z, None, None) for lm in frame
    ]
    series = series_from_frames([stripped] * 60)
    assert series.mean_visibility() is None
    outcome = analyse(series, "MOUNTAIN_ARMS_UP")
    assert GATE_LOW_LANDMARK_VISIBILITY not in outcome.gate_failures


def test_a_good_recording_is_accepted():
    outcome = analyse(raise_cycles(cycles=4), "MOUNTAIN_ARMS_UP")
    assert outcome.accepted, outcome.gate_failures
    assert outcome.metrics["repetition_count"] == 4
    assert outcome.metrics["left_shoulder_max_angle_deg"] == pytest.approx(170.0, abs=8.0)
    assert outcome.metrics["right_shoulder_max_angle_deg"] == pytest.approx(170.0, abs=8.0)
    assert outcome.metrics["left_right_angle_difference_deg"] == pytest.approx(0.0, abs=2.0)


# --------------------------------------------------------------------------- #
# per-exercise behaviour
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "exercise_key",
    [
        "MOUNTAIN_ARMS_UP",
        "ARMS_LATERAL_RAISE",
        "SIDE_BEND_STRETCH",
        "SEATED_TRUNK_ROTATION",
        "SEATED_ALTERNATING_ARM_RAISE",
    ],
)
def test_every_exercise_analyses_an_arm_recording(exercise_key):
    outcome = analyse(raise_cycles(cycles=3), exercise_key)
    assert outcome.exercise_key == exercise_key
    # The ten raw metrics of spec V2 section 28 must all be present as keys.
    for key in (
        "left_shoulder_max_angle_deg",
        "right_shoulder_max_angle_deg",
        "left_right_angle_difference_deg",
        "trunk_angle_deg",
        "hold_time_sec",
        "repetition_count",
        "repetition_interval_ms",
        "movement_speed_deg_per_sec",
        "angle_std_deg",
        "valid_pose_frame_ratio",
    ):
        assert key in outcome.metrics, key


def test_unknown_exercise_is_rejected():
    with pytest.raises(KeyError):
        analyse(raise_cycles(cycles=2), "NOT_AN_EXERCISE")


def test_trunk_angle_is_only_reported_for_the_bending_exercise():
    arms = analyse(raise_cycles(cycles=3), "MOUNTAIN_ARMS_UP")
    assert arms.metrics["trunk_angle_deg"] is None

    frames = []
    for _ in range(3):
        for i in range(30):
            phase = 2 * math.pi * i / 30
            frames.append(arm_frame(trunk_tilt=25.0 * math.sin(phase)))
    bend = analyse(series_from_frames(frames), "SIDE_BEND_STRETCH")
    assert bend.metrics["trunk_angle_deg"] is not None
    assert bend.metrics["trunk_angle_deg"] > 10.0
    assert bend.metrics["drive_series"] == "trunk_tilt"


def test_exercise_definitions_without_formulas_never_produce_scores():
    """The source documents give illustrative 82/88/79 values and no formulas.

    Until a formula exists and is versioned, no 0-100 number may appear, so the
    analyzer output must not contain any score key at all.
    """
    outcome = analyse(raise_cycles(cycles=3), "MOUNTAIN_ARMS_UP")
    forbidden = (
        "completion_score",
        "range_of_motion",
        "symmetry_score",
        "stability_score",
        "rom_score",
        "score",
    )
    for key in forbidden:
        assert key not in outcome.metrics, f"{key} must not be produced"
        assert key not in outcome.quality

    from app.ml.pose.exercises import EXERCISES

    for exercise in EXERCISES:
        assert exercise.completion_formula is None
        assert exercise.rom_formula is None
        assert exercise.symmetry_formula is None
        assert exercise.stability_formula is None
        assert exercise.scores_available is False


def test_quality_carries_the_config_used():
    outcome = analyse(raise_cycles(cycles=3), "MOUNTAIN_ARMS_UP")
    config = outcome.quality["analysis_config"]
    assert config["algorithm_version"] == "pose-metrics-v1.0.0"
    assert config["trunk_rotation_is_monocular_proxy"] is True
    assert outcome.quality["visibility_measured"] is True
    assert outcome.quality["gate_failures"] == []


def test_trunk_exercises_warn_about_the_camera_view():
    outcome = analyse(raise_cycles(cycles=3), "SIDE_BEND_STRETCH")
    assert any("髋部" in w for w in outcome.warnings)

    rotation = analyse(raise_cycles(cycles=3), "SEATED_TRUNK_ROTATION")
    assert any("单目" in w for w in rotation.warnings)
