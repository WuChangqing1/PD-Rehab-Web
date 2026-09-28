"""Finger Tapping video quality control.

Gates run before any feature is computed, because a video that cannot support
the analysis must produce an explicit error rather than a plausible-looking set
of numbers.

Thresholds come from docs/metric_definitions.md section 1.4:

  1. video readable                     VIDEO_UNREADABLE
  2. fps > 0                            VIDEO_FPS_INVALID
  3. frame_count >= 4 * fps             VIDEO_TOO_SHORT   (upstream rule)
  4. duration >= FT_MIN_DURATION_SEC    VIDEO_TOO_SHORT
  5. detected_frames > 0                HAND_NOT_DETECTED
  6. valid_frame_ratio >= 0.5           LOW_VALID_FRAME_RATIO  (upstream rule)
  7. landmark continuity                LANDMARK_DISCONTINUOUS
  8. cycle count >= 2                   INSUFFICIENT_CYCLES

Gate 7 is the only threshold upstream does not define. It uses the longest
consecutive run of detected frames, expressed as a fraction of all frames:
    longest_run / frame_count >= FT_MIN_CONTINUOUS_FRAME_RATIO
The default lives in configuration so it can be tuned on real recordings
without touching the code, and the value used is recorded in analysis_config.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

# --- thresholds (mirrored into analysis_config_json for reproducibility) ---
MIN_VALID_FRAME_RATIO = 0.5
MIN_FRAMES_PER_FPS = 4
MIN_DURATION_SEC = 3.0
MIN_CYCLE_COUNT = 2
# Not defined upstream; see module docstring.
MIN_CONTINUOUS_FRAME_RATIO = 0.25

# Handedness confidence: the Tasks API exposes no per-landmark confidence (both
# visibility and presence are None in mediapipe 1.0.1). The handedness
# classification score is real and varies, and is recorded as
# `avg_landmark_confidence` with that meaning stated explicitly.
MIN_HANDEDNESS_SCORE = 0.5


@dataclass
class QualityReport:
    """Measured properties of the input, plus any gate failures."""

    passed: bool = False

    fps: float | None = None
    frame_count: int = 0
    width: int | None = None
    height: int | None = None
    duration_sec: float | None = None

    detected_frames: int = 0
    total_frames: int = 0
    valid_frame_ratio: float | None = None
    longest_continuous_run: int = 0
    continuous_frame_ratio: float | None = None

    analyzed_samples: int = 0
    cycle_count: int | None = None

    avg_landmark_confidence: float | None = None
    landmark_confidence_meaning: str = (
        "MediaPipe handedness classification score (left/right), not a per-landmark "
        "visibility score; the Tasks API returns null for visibility and presence."
    )

    normalization_method: str = "PALM_REFERENCE"
    filter_method: str = "BUTTERWORTH"
    filter_order: int | None = None
    filter_cutoff_hz: float | None = None
    filter_fs_used_hz: float | None = None
    feature_schema_version: str = "1.0"

    error_code: str | None = None
    error_message: str | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def analysis_config(self) -> dict[str, Any]:
        """The tunable parameters actually used, stored with the result."""
        return {
            "normalization_method": self.normalization_method,
            "filter_method": self.filter_method,
            "filter_order": self.filter_order,
            "filter_cutoff_hz": self.filter_cutoff_hz,
            "filter_fs_source": "video_fps",
            "filter_fs_used_hz": self.filter_fs_used_hz,
            "peak_distance": 5,
            "peak_height_factor": 0.5,
            "peak_prominence_factor": 0.5,
            "interruption_threshold_factor": 1.5,
            "interruption_threshold_basis": "median_cycle_duration",
            "interruption_rule_version": "v1.0.0",
            "min_valid_frame_ratio": MIN_VALID_FRAME_RATIO,
            "min_frames_per_fps": MIN_FRAMES_PER_FPS,
            "min_duration_sec": MIN_DURATION_SEC,
            "min_cycle_count": MIN_CYCLE_COUNT,
            "min_continuous_frame_ratio": MIN_CONTINUOUS_FRAME_RATIO,
            "min_handedness_score": MIN_HANDEDNESS_SCORE,
            # Unverified question carried over from Phase 0: mediapipe's
            # handedness follows the mirrored/webcam convention. The external
            # repository compares it directly without correction.
            "handedness_convention": "TBD",
        }


def evaluate_video_metadata(
    *,
    fps: float | None,
    frame_count: int,
    width: int | None = None,
    height: int | None = None,
) -> QualityReport:
    """Gates 1-4, evaluated before decoding frames."""
    report = QualityReport(
        fps=fps, frame_count=frame_count, width=width, height=height
    )

    if not frame_count or frame_count <= 0:
        report.error_code = "VIDEO_UNREADABLE"
        report.error_message = "无法读取视频帧，请确认文件未损坏。"
        return report

    if not fps or fps <= 0:
        report.error_code = "VIDEO_FPS_INVALID"
        report.error_message = "视频帧率无效（FPS <= 0），无法进行时间分析。"
        return report

    report.duration_sec = frame_count / fps

    if frame_count < MIN_FRAMES_PER_FPS * fps:
        report.error_code = "VIDEO_TOO_SHORT"
        report.error_message = (
            f"视频过短：至少需要 {MIN_FRAMES_PER_FPS} 秒（{MIN_FRAMES_PER_FPS * fps:.0f} 帧），"
            f"当前 {frame_count} 帧。"
        )
        return report

    if report.duration_sec < MIN_DURATION_SEC:
        report.error_code = "VIDEO_TOO_SHORT"
        report.error_message = (
            f"视频过短：至少需要 {MIN_DURATION_SEC:.0f} 秒，当前 {report.duration_sec:.1f} 秒。"
        )
        return report

    return report


def longest_continuous_run(detected_flags: list[bool]) -> int:
    """Longest streak of consecutive True values."""
    best = current = 0
    for flag in detected_flags:
        current = current + 1 if flag else 0
        best = max(best, current)
    return best


def evaluate_detection(
    report: QualityReport,
    *,
    detected_flags: list[bool],
    handedness_scores: list[float | None],
    filter_fs_hz: float | None,
    filter_order: int | None,
    filter_cutoff_hz: float | None,
) -> QualityReport:
    """Gates 5-7, evaluated after processing every frame."""
    total = len(detected_flags)
    detected = sum(1 for f in detected_flags if f)

    report.detected_frames = detected
    report.total_frames = total
    report.valid_frame_ratio = (detected / total) if total else None
    report.longest_continuous_run = longest_continuous_run(detected_flags)
    report.continuous_frame_ratio = (
        report.longest_continuous_run / total if total else None
    )
    report.filter_fs_used_hz = filter_fs_hz
    report.filter_order = filter_order
    report.filter_cutoff_hz = filter_cutoff_hz

    usable = [s for s in handedness_scores if s is not None]
    report.avg_landmark_confidence = (
        float(sum(usable) / len(usable)) if usable else None
    )

    if detected == 0:
        report.error_code = "HAND_NOT_DETECTED"
        report.error_message = "未能在任何视频帧中检测到目标手，请重新录制。"
        return report

    if report.valid_frame_ratio is not None and report.valid_frame_ratio < MIN_VALID_FRAME_RATIO:
        report.error_code = "LOW_VALID_FRAME_RATIO"
        report.error_message = (
            f"检测到目标手的帧比例过低（{report.valid_frame_ratio:.0%}，"
            f"至少需要 {MIN_VALID_FRAME_RATIO:.0%}），请重新录制。"
        )
        return report

    if (
        report.continuous_frame_ratio is not None
        and report.continuous_frame_ratio < MIN_CONTINUOUS_FRAME_RATIO
    ):
        report.error_code = "LANDMARK_DISCONTINUOUS"
        report.error_message = (
            "关键点时间序列连续性不足（最长连续检测段过短），"
            "请保持手掌完整出现在画面中后重新录制。"
        )
        return report

    if (
        report.avg_landmark_confidence is not None
        and report.avg_landmark_confidence < MIN_HANDEDNESS_SCORE
    ):
        report.notes.append("low_handedness_confidence")

    report.passed = True
    return report


def evaluate_cycles(report: QualityReport, cycle_count: int | None) -> QualityReport:
    """Gate 8: enough complete cycles to compute variability and slope."""
    report.cycle_count = cycle_count
    if cycle_count is None or cycle_count < MIN_CYCLE_COUNT:
        report.passed = False
        report.error_code = "INSUFFICIENT_CYCLES"
        report.error_message = (
            f"有效敲击周期过少（{cycle_count or 0} 个，至少需要 {MIN_CYCLE_COUNT} 个），"
            "请重新录制并保持规律的张开—闭合动作。"
        )
    return report
