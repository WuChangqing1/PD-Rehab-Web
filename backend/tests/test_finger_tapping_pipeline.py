"""Finger Tapping pipeline and quality-control tests.

The integration tests run the real pipeline (OpenCV + MediaPipe) on a 7-second
clip taken from the external repository's own demo video. That clip is committed
so the checks do not depend on the external checkout being present.

The tests skip cleanly when opencv or mediapipe are unavailable, so the suite
still runs on a machine without the CV stack.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ml.finger_tapping import quality as qc

FIXTURE_VIDEO = Path(__file__).resolve().parent / "fixtures" / "finger_tapping_sample.mp4"


def _cv_available() -> bool:
    try:
        import cv2  # noqa: F401
        import mediapipe  # noqa: F401

        return True
    except Exception:  # noqa: BLE001
        return False


def _landmarker_available() -> bool:
    from app.ml.finger_tapping.pipeline import resolve_landmarker_path

    try:
        return resolve_landmarker_path().is_file()
    except Exception:  # noqa: BLE001
        return False


requires_cv = pytest.mark.skipif(
    not _cv_available(), reason="opencv / mediapipe not installed"
)
requires_pipeline = pytest.mark.skipif(
    not (_cv_available() and _landmarker_available() and FIXTURE_VIDEO.is_file()),
    reason="opencv / mediapipe / landmarker / fixture video not all available",
)


# ============================================================== quality gates
def test_metadata_gate_rejects_invalid_fps():
    report = qc.evaluate_video_metadata(fps=0, frame_count=100)
    assert report.error_code == "VIDEO_FPS_INVALID"
    assert report.passed is False


def test_metadata_gate_rejects_unreadable_video():
    report = qc.evaluate_video_metadata(fps=30, frame_count=0)
    assert report.error_code == "VIDEO_UNREADABLE"


def test_metadata_gate_rejects_short_video_by_frames():
    # upstream rule: at least 4 seconds worth of frames
    report = qc.evaluate_video_metadata(fps=30, frame_count=40)
    assert report.error_code == "VIDEO_TOO_SHORT"


def test_metadata_gate_rejects_short_video_by_duration():
    report = qc.evaluate_video_metadata(fps=5, frame_count=18)  # 3.6 s < 4*5 frames
    assert report.error_code == "VIDEO_TOO_SHORT"


def test_metadata_gate_accepts_a_suitable_video():
    report = qc.evaluate_video_metadata(fps=30, frame_count=300, width=640, height=480)
    assert report.error_code is None
    assert report.duration_sec == pytest.approx(10.0)


def test_detection_gate_rejects_no_hand():
    report = qc.evaluate_video_metadata(fps=30, frame_count=300)
    report = qc.evaluate_detection(
        report,
        detected_flags=[False] * 300,
        handedness_scores=[None] * 300,
        filter_fs_hz=30,
        filter_order=4,
        filter_cutoff_hz=9,
    )
    assert report.error_code == "HAND_NOT_DETECTED"
    assert report.valid_frame_ratio == 0.0


def test_detection_gate_rejects_low_valid_frame_ratio():
    """Below the upstream 0.5 threshold."""
    flags = [True] * 100 + [False] * 200  # 0.33
    report = qc.evaluate_video_metadata(fps=30, frame_count=300)
    report = qc.evaluate_detection(
        report,
        detected_flags=flags,
        handedness_scores=[0.9] * 300,
        filter_fs_hz=30,
        filter_order=4,
        filter_cutoff_hz=9,
    )
    assert report.error_code == "LOW_VALID_FRAME_RATIO"


def test_detection_gate_rejects_intermittent_detection():
    """A 0.5 ratio passes the upstream gate but the signal is not continuous."""
    flags = [i % 2 == 0 for i in range(300)]
    report = qc.evaluate_video_metadata(fps=30, frame_count=300)
    report = qc.evaluate_detection(
        report,
        detected_flags=flags,
        handedness_scores=[0.9] * 300,
        filter_fs_hz=30,
        filter_order=4,
        filter_cutoff_hz=9,
    )
    assert report.valid_frame_ratio == pytest.approx(0.5)
    assert report.error_code == "LANDMARK_DISCONTINUOUS"


def test_detection_gate_passes_for_continuous_detection():
    report = qc.evaluate_video_metadata(fps=30, frame_count=300)
    report = qc.evaluate_detection(
        report,
        detected_flags=[True] * 300,
        handedness_scores=[0.95] * 300,
        filter_fs_hz=30,
        filter_order=4,
        filter_cutoff_hz=9,
    )
    assert report.passed is True
    assert report.avg_landmark_confidence == pytest.approx(0.95)


def test_cycle_gate_rejects_too_few_cycles():
    report = qc.QualityReport(passed=True)
    report = qc.evaluate_cycles(report, 1)
    assert report.error_code == "INSUFFICIENT_CYCLES"
    assert report.passed is False


def test_cycle_gate_accepts_enough_cycles():
    report = qc.QualityReport(passed=True)
    report = qc.evaluate_cycles(report, 12)
    assert report.error_code is None
    assert report.passed is True


def test_longest_continuous_run():
    assert qc.longest_continuous_run([True, True, False, True, True, True]) == 3
    assert qc.longest_continuous_run([False, False]) == 0
    assert qc.longest_continuous_run([]) == 0


def test_analysis_config_records_every_tunable_parameter():
    """A single analysis must be reproducible from its stored config."""
    report = qc.QualityReport(
        filter_order=4, filter_cutoff_hz=9.0, filter_fs_used_hz=30.0
    )
    config = report.analysis_config
    for key in (
        "normalization_method",
        "filter_method",
        "filter_order",
        "filter_cutoff_hz",
        "filter_fs_used_hz",
        "peak_distance",
        "interruption_threshold_factor",
        "interruption_threshold_basis",
        "min_valid_frame_ratio",
        "min_cycle_count",
        "min_continuous_frame_ratio",
        "handedness_convention",
    ):
        assert key in config, f"{key} missing from analysis_config"
    assert config["normalization_method"] == "PALM_REFERENCE"
    assert config["handedness_convention"] == "TBD"


def test_quality_report_documents_confidence_meaning():
    """avg_landmark_confidence is the handedness score, and must say so."""
    report = qc.QualityReport()
    assert "handedness" in report.landmark_confidence_meaning.lower()
    assert "not a per-landmark" in report.landmark_confidence_meaning.lower()


# ============================================================== pipeline paths
def test_missing_video_is_rejected(monkeypatch):
    from app.core.errors import APIError
    from app.ml.finger_tapping.pipeline import analyze_video

    with pytest.raises(APIError) as exc:
        analyze_video("does-not-exist.mp4", "RIGHT")
    assert exc.value.code == "VIDEO_UNREADABLE"


@pytest.mark.skipif(not _cv_available(), reason="opencv / mediapipe not installed")
def test_invalid_hand_argument_is_rejected():
    """hand must be LEFT or RIGHT, checked before any decoding happens."""
    import tempfile
    from pathlib import Path as P

    from app.core.errors import APIError
    from app.ml.finger_tapping.pipeline import analyze_video

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(b"not a video")
        name = tmp.name
    try:
        with pytest.raises(APIError) as exc:
            analyze_video(name, "MIDDLE")
        assert exc.value.status_code == 422
        assert exc.value.code == "VALIDATION_ERROR"
        # the rejected value is echoed back for debugging
        assert exc.value.detail_payload["hand"] == "MIDDLE"
    finally:
        P(name).unlink(missing_ok=True)


@pytest.mark.skipif(not _cv_available(), reason="opencv / mediapipe not installed")
def test_non_video_file_is_rejected():
    """A file with a .mp4 name that is not a video must fail cleanly."""
    import tempfile
    from pathlib import Path as P

    from app.core.errors import APIError
    from app.ml.finger_tapping.pipeline import analyze_video

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(b"definitely not a video")
        name = tmp.name
    try:
        with pytest.raises(APIError) as exc:
            analyze_video(name, "RIGHT")
        assert exc.value.code in ("VIDEO_UNREADABLE", "VIDEO_TOO_SHORT", "VIDEO_FPS_INVALID")
    finally:
        P(name).unlink(missing_ok=True)


# ======================================================== real-video integration
@requires_pipeline
def test_real_video_produces_all_features():
    from app.ml.finger_tapping.pipeline import analyze_video

    outcome = analyze_video(str(FIXTURE_VIDEO), "RIGHT")
    features = outcome.features

    assert set(features) == {
        "tapping_frequency",
        "avg_amplitude",
        "avg_speed",
        "avg_cycle_duration",
        "amplitude_cv",
        "speed_cv",
        "cycle_cv",
        "amplitude_slope",
        "speed_slope",
        "cycle_slope",
        "interruptions",
    }
    for key, value in features.items():
        assert value is not None, f"{key} is None on a good recording"
        if isinstance(value, float):
            assert value == value, f"{key} is NaN"


@requires_pipeline
def test_real_video_frequency_is_physiologically_plausible():
    from app.ml.finger_tapping.pipeline import analyze_video

    outcome = analyze_video(str(FIXTURE_VIDEO), "RIGHT")
    freq = outcome.features["tapping_frequency"]
    assert 1.0 <= freq <= 6.0, f"{freq} Hz is outside the plausible tapping range"

    # the two independent frequency definitions must agree
    cycle_based = outcome.raw_features["tapping_frequency_cycle_based"]
    assert freq == pytest.approx(cycle_based, rel=0.05)


@requires_pipeline
def test_real_video_quality_report():
    from app.ml.finger_tapping.pipeline import analyze_video

    outcome = analyze_video(str(FIXTURE_VIDEO), "RIGHT")
    quality = outcome.quality
    assert quality["valid_frame_ratio"] == pytest.approx(1.0)
    assert quality["detected_frames"] == quality["total_frames"]
    assert quality["fps"] == pytest.approx(30.0, abs=1.0)
    assert quality["error_code"] is None


@requires_pipeline
def test_severity_is_never_populated():
    """No trained severity model exists upstream, so this must stay None."""
    from app.ml.finger_tapping.pipeline import analyze_video

    outcome = analyze_video(str(FIXTURE_VIDEO), "RIGHT")
    assert outcome.severity_score is None
    assert outcome.severity_label is None


@requires_pipeline
def test_wrong_hand_is_rejected_not_substituted():
    """The clip contains one hand; asking for the other must fail honestly."""
    from app.core.errors import APIError
    from app.ml.finger_tapping.pipeline import analyze_video

    with pytest.raises(APIError) as exc:
        analyze_video(str(FIXTURE_VIDEO), "LEFT")
    assert exc.value.code == "HAND_NOT_DETECTED"


@requires_pipeline
def test_analysis_is_deterministic():
    from app.ml.finger_tapping.pipeline import analyze_video

    first = analyze_video(str(FIXTURE_VIDEO), "RIGHT")
    second = analyze_video(str(FIXTURE_VIDEO), "RIGHT")
    assert first.features == second.features
    assert first.raw_features["peak_frames"] == second.raw_features["peak_frames"]


@requires_pipeline
def test_outcome_carries_versions_and_config():
    from app.ml.finger_tapping.pipeline import analyze_video

    outcome = analyze_video(str(FIXTURE_VIDEO), "RIGHT")
    assert outcome.analyzer_version
    assert outcome.qc_version
    assert outcome.feature_schema_version
    assert outcome.analysis_config["normalization_method"] == "PALM_REFERENCE"
    assert outcome.analysis_config["filter_fs_used_hz"] == pytest.approx(30.0, abs=1.0)
    assert outcome.raw_features["landmarker_sha256"]


@requires_pipeline
def test_timeseries_is_returned_for_plotting():
    from app.ml.finger_tapping.pipeline import analyze_video

    outcome = analyze_video(str(FIXTURE_VIDEO), "RIGHT")
    series = outcome.timeseries
    assert len(series["aperture_filtered"]) == len(series["aperture_raw"])
    assert len(series["frame_index"]) == len(series["aperture_raw"])
    assert len(series["aperture_raw"]) > 100


@requires_pipeline
def test_handedness_convention_is_flagged_as_unverified():
    from app.ml.finger_tapping.pipeline import analyze_video

    outcome = analyze_video(str(FIXTURE_VIDEO), "RIGHT")
    assert outcome.analysis_config["handedness_convention"] == "TBD"
    assert "镜像" in outcome.handedness_note
