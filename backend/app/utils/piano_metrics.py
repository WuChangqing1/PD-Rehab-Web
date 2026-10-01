"""Piano session metrics computed from raw events (spec V2 sections 18, 19).

This mirrors frontend/src/piano/metrics.ts. The frontend computes metrics for
instant feedback; the server recomputes from the stored raw events and its
result is the authoritative one. Keeping both and comparing them is deliberate:
a mismatch means one of the two drifted, which is exactly the kind of bug that
would otherwise silently corrupt a patient's trend line.

Formula notes:
  CV = std / mean with a guard when |mean| is near zero. This matters most for
  timing_error_cv, where early and late presses can cancel out and leave a mean
  close to zero; there the metric is None and timing_error_std_ms is the honest
  alternative.
  weak_finger_error_rate counts errors on cues whose finger_hint is RING or
  LITTLE. It is a TASK MAPPING metric: the keyboard reveals which mapping key was
  requested, not which physical finger was used.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Sequence

EPS = 1e-9
WEAK_FINGERS = {"RING", "LITTLE"}


def _finite(value: float | None) -> float | None:
    if value is None:
        return None
    return value if math.isfinite(value) else None


def _mean(values: Sequence[float]) -> float | None:
    usable = [v for v in values if v is not None and math.isfinite(v)]
    if not usable:
        return None
    return _finite(sum(usable) / len(usable))


def _median(values: Sequence[float]) -> float | None:
    usable = sorted(v for v in values if v is not None and math.isfinite(v))
    if not usable:
        return None
    mid = len(usable) // 2
    if len(usable) % 2:
        return _finite(float(usable[mid]))
    return _finite((usable[mid - 1] + usable[mid]) / 2.0)


def _std(values: Sequence[float]) -> float | None:
    usable = [v for v in values if v is not None and math.isfinite(v)]
    if len(usable) < 2:
        return None
    m = sum(usable) / len(usable)
    variance = sum((v - m) ** 2 for v in usable) / len(usable)
    return _finite(math.sqrt(variance))


def _cv(values: Sequence[float]) -> float | None:
    usable = [v for v in values if v is not None and math.isfinite(v)]
    if len(usable) < 2:
        return None
    m = sum(usable) / len(usable)
    if abs(m) < EPS:
        return None
    s = _std(usable)
    if s is None:
        return None
    return _finite(s / m)


def _timing_error_cv(values: Sequence[float]) -> tuple[float | None, str | None]:
    """CV of the signed timing error, or None when it is not interpretable.

    A mean timing error near zero is the *expected* result for a competent
    performer, because early and late presses cancel. Dividing by it produces an
    enormous, meaningless ratio: one real calibration round produced
    mean = 1.4 ms with sd = 82 ms, giving CV = 58.7.

    So the CV is only reported when the mean is large enough to be told apart
    from zero. The rule used is |mean| >= 0.25 * sd, i.e. the mean exceeds a
    quarter of the spread. When that fails, `timing_error_std_ms` is the honest
    measure of timing variability and a note says so.
    """
    usable = [v for v in values if v is not None and math.isfinite(v)]
    if len(usable) < 2:
        return None, None
    m = sum(usable) / len(usable)
    s = _std(usable)
    if s is None or s < EPS:
        # no spread at all: the mean is the whole story
        return (0.0 if abs(m) >= EPS else None), None
    if abs(m) < 0.25 * s:
        return None, (
            "平均节拍误差接近 0（提前与滞后互相抵消），CV 无法解释；"
            "请改看 timing_error_std_ms（节拍误差标准差）。"
        )
    return _finite(s / m), None


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return _finite(numerator / denominator)


@dataclass
class PianoMetrics:
    total_cues: int = 0
    correct_count: int = 0
    wrong_count: int = 0
    missed_count: int = 0

    accuracy: float | None = None
    miss_rate: float | None = None
    mean_timing_error_ms: float | None = None
    median_timing_error_ms: float | None = None
    timing_error_cv: float | None = None
    mean_response_latency_ms: float | None = None
    median_response_latency_ms: float | None = None
    response_latency_cv: float | None = None
    left_mean_latency: float | None = None
    right_mean_latency: float | None = None
    left_right_latency_difference: float | None = None
    left_accuracy: float | None = None
    right_accuracy: float | None = None
    weak_finger_error_rate: float | None = None
    session_completion_rate: float | None = None

    mean_absolute_timing_error_ms: float | None = None
    timing_error_std_ms: float | None = None
    early_press_rate: float | None = None
    late_press_rate: float | None = None
    error_streak_max: int | None = None
    key_hold_duration_ms: float | None = None
    sequence_completion_rate: float | None = None

    timing_error_cv_note: str | None = None
    planned_cues: int | None = None

    def to_db_fields(self) -> dict[str, Any]:
        """Map to the finger_tapping_results-style column names on piano_sessions."""
        return {
            "accuracy": self.accuracy,
            "miss_rate": self.miss_rate,
            "mean_response_latency_ms": self.mean_response_latency_ms,
            "median_response_latency_ms": self.median_response_latency_ms,
            "response_latency_cv": self.response_latency_cv,
            "mean_timing_error_ms": self.mean_timing_error_ms,
            "median_timing_error_ms": self.median_timing_error_ms,
            "timing_mae_ms": self.mean_absolute_timing_error_ms,
            "timing_error_cv": self.timing_error_cv,
            "early_press_rate": self.early_press_rate,
            "late_press_rate": self.late_press_rate,
            "left_mean_latency": self.left_mean_latency,
            "right_mean_latency": self.right_mean_latency,
            "left_right_latency_difference": self.left_right_latency_difference,
            "left_accuracy": self.left_accuracy,
            "right_accuracy": self.right_accuracy,
            "weak_finger_error_rate": self.weak_finger_error_rate,
            "sequence_completion_rate": self.sequence_completion_rate,
            "session_completion_rate": self.session_completion_rate,
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_metrics(
    events: Iterable[dict[str, Any]], *, planned_cues: int | None = None
) -> PianoMetrics:
    """Compute the metric set from raw event dictionaries."""
    rows = [e for e in events]
    # Cue rows are the targets the patient was asked to hit; wrong-key presses
    # are additional error rows and must not inflate the cue count.
    #
    # Prompt rows (memory mode) are demonstrations, not questions. The patient
    # was never allowed to answer them, so leaving them in the denominator would
    # report a miss rate that is partly an artefact of the mode rather than a
    # description of the patient. They are excluded from every cue statistic and
    # kept only in the raw timeline.
    cues = [e for e in rows if not e.get("is_wrong_key") and not e.get("is_prompt")]
    wrong = [e for e in rows if e.get("is_wrong_key")]

    total_cues = len(cues)
    correct = [e for e in cues if e.get("is_correct")]
    missed = [e for e in cues if e.get("is_missed")]

    latencies = [
        e["response_latency_ms"] for e in correct if e.get("response_latency_ms") is not None
    ]
    timing_errors = [
        e["timing_error_ms"] for e in correct if e.get("timing_error_ms") is not None
    ]
    timing_abs = [abs(v) for v in timing_errors]
    holds = [e["hold_duration_ms"] for e in rows if e.get("hold_duration_ms") is not None]

    def hand_correct(hand: str) -> list[dict[str, Any]]:
        return [e for e in correct if e.get("hand") == hand]

    def hand_cues(hand: str) -> list[dict[str, Any]]:
        return [e for e in cues if e.get("hand") == hand]

    left_lat = [e["response_latency_ms"] for e in hand_correct("LEFT")
                if e.get("response_latency_ms") is not None]
    right_lat = [e["response_latency_ms"] for e in hand_correct("RIGHT")
                 if e.get("response_latency_ms") is not None]
    left_mean = _mean(left_lat)
    right_mean = _mean(right_lat)

    weak_cues = [e for e in cues if e.get("finger_hint") in WEAK_FINGERS]
    weak_errors = [e for e in weak_cues if not e.get("is_correct")]

    # Early / late threshold derived from the data (median absolute error), not
    # invented: there is no clinical constant here.
    typical = _median(timing_abs) or 0.0
    early = sum(1 for v in timing_errors if v < -typical)
    late = sum(1 for v in timing_errors if v > typical)

    streak = 0
    max_streak = 0
    for row in cues:
        if row.get("is_correct"):
            streak = 0
        else:
            streak += 1
            max_streak = max(max_streak, streak)

    # Sequence completion: fraction of started note groups fully correct.
    #
    # The group key is the demonstrated group when the round has one (memory
    # mode), because there the sequence is the thing being reproduced. Elsewhere
    # the cue index stands in for a group of one, which is what the mapped
    # sequence mode produces.
    groups: dict[tuple[Any, Any], list[dict[str, Any]]] = {}
    for row in cues:
        pos = row.get("sequence_position")
        length = row.get("sequence_length")
        if pos is None or length is None:
            continue
        key = (row.get("memory_group", row.get("cue_index")), length)
        groups.setdefault(key, []).append(row)
    sequence_completion = None
    if groups:
        complete = sum(1 for group in groups.values() if all(g.get("is_correct") for g in group))
        sequence_completion = _ratio(complete, len(groups))

    planned = planned_cues if planned_cues and planned_cues > 0 else total_cues
    timing_cv, timing_cv_note = _timing_error_cv(timing_errors)

    return PianoMetrics(
        total_cues=total_cues,
        correct_count=len(correct),
        wrong_count=len(wrong),
        missed_count=len(missed),
        accuracy=_ratio(len(correct), total_cues),
        miss_rate=_ratio(len(missed), total_cues),
        mean_timing_error_ms=_mean(timing_errors),
        median_timing_error_ms=_median(timing_errors),
        timing_error_cv=timing_cv,
        mean_response_latency_ms=_mean(latencies),
        median_response_latency_ms=_median(latencies),
        response_latency_cv=_cv(latencies),
        left_mean_latency=left_mean,
        right_mean_latency=right_mean,
        left_right_latency_difference=(
            None if left_mean is None or right_mean is None else _finite(left_mean - right_mean)
        ),
        left_accuracy=_ratio(len(hand_correct("LEFT")), len(hand_cues("LEFT"))),
        right_accuracy=_ratio(len(hand_correct("RIGHT")), len(hand_cues("RIGHT"))),
        weak_finger_error_rate=_ratio(len(weak_errors), len(weak_cues)),
        session_completion_rate=_ratio(total_cues, planned),
        mean_absolute_timing_error_ms=_mean(timing_abs),
        timing_error_std_ms=_std(timing_errors),
        early_press_rate=_ratio(early, len(timing_errors)),
        late_press_rate=_ratio(late, len(timing_errors)),
        error_streak_max=max_streak if total_cues else None,
        key_hold_duration_ms=_mean(holds),
        sequence_completion_rate=sequence_completion,
        timing_error_cv_note=timing_cv_note,
        planned_cues=planned,
    )


def validation_warnings(metrics: PianoMetrics, events: Sequence[dict[str, Any]]) -> list[str]:
    """Sanity checks recorded with the session.

    These are warnings, not rejections: the data is stored as received, but
    anything implausible is flagged so it can be excluded from analysis rather
    than quietly skewing a trend.
    """
    warnings: list[str] = []

    # Raw events must be self-consistent.
    bad_latency = [
        e for e in events
        if e.get("response_latency_ms") is not None
        and e.get("cue_onset_time_ms") is not None
        and e.get("actual_time_ms") is not None
        and e["response_latency_ms"] != e["actual_time_ms"] - e["cue_onset_time_ms"]
    ]
    if bad_latency:
        warnings.append(f"{len(bad_latency)} 个事件的 response_latency_ms 与时间戳不一致")

    bad_error = [
        e for e in events
        if e.get("timing_error_ms") is not None
        and e.get("target_time_ms") is not None
        and e.get("actual_time_ms") is not None
        and e["timing_error_ms"] != e["actual_time_ms"] - e["target_time_ms"]
    ]
    if bad_error:
        warnings.append(f"{len(bad_error)} 个事件的 timing_error_ms 与时间戳不一致")

    missing_cue_times = [e for e in events if not e.get("is_wrong_key") and e.get("cue_onset_time_ms") is None]
    if missing_cue_times:
        warnings.append(f"{len(missing_cue_times)} 个目标事件缺少 cue_onset_time_ms")

    if metrics.total_cues == 0:
        warnings.append("没有可用的目标事件，无法计算指标")

    if metrics.mean_response_latency_ms is not None:
        if metrics.mean_response_latency_ms < 0:
            warnings.append("平均反应延迟为负，时间戳可能异常")
        elif metrics.mean_response_latency_ms > 3000:
            warnings.append("平均反应延迟超过 3 秒，请确认录制环境")

    if metrics.accuracy is not None and not (0.0 <= metrics.accuracy <= 1.0):
        warnings.append("准确率超出 0-1 范围")

    return warnings
