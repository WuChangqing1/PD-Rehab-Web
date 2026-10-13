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

    # ------------------------------------------------------- recipe metrics
    # Populated only by rounds that used the matching recipe; None otherwise, so
    # a plain-mode session is unchanged and reports can tell "not applicable"
    # from "measured zero".

    # BIMANUAL_SYNC: |left − right| between the two hands of a pair, averaged
    # over pairs where both hands arrived. A pair with one hand missing is a miss
    # and contributes nothing here -- averaging in a zero would report perfect
    # synchrony for a press that never happened.
    inter_hand_sync_mean_ms: float | None = None
    inter_hand_sync_sd_ms: float | None = None
    inter_hand_pair_count: int | None = None

    # CFT_RHYTHM_HOLD: the cued warm-up and the un-cued continuation, reported
    # separately. Averaging them would hide the thing the practice measures --
    # staying on the beat once the support is withdrawn.
    cued_phase_accuracy: float | None = None
    free_phase_accuracy: float | None = None
    free_phase_timing_mae_ms: float | None = None
    free_phase_interval_cv: float | None = None
    free_phase_cue_count: int | None = None

    # ACCENT_GROUPING: how often the accented first beat of a bar was hit.
    accent_hit_rate: float | None = None
    accent_cue_count: int | None = None

    hold_duration_mae_ms: float | None = None
    hold_release_completion_rate: float | None = None
    inter_hand_phase_mae_ms: float | None = None
    offset_left_miss_rate: float | None = None
    offset_right_miss_rate: float | None = None
    reverse_position_accuracy: float | None = None
    reverse_completion_rate: float | None = None
    go_commission_count: int | None = None
    go_omission_count: int | None = None
    go_response_latency_ms: float | None = None
    tempo_segments: list[dict[str, Any]] = field(default_factory=list)
    tempo_segment_0_accuracy: float | None = None
    tempo_segment_1_accuracy: float | None = None
    tempo_segment_2_accuracy: float | None = None
    tempo_segment_3_accuracy: float | None = None
    tempo_segment_0_mae_ms: float | None = None
    tempo_segment_1_mae_ms: float | None = None
    tempo_segment_2_mae_ms: float | None = None
    tempo_segment_3_mae_ms: float | None = None

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
    missed = [e for e in cues if e.get("is_missed") and e.get("cue_type") != "NO_GO"]
    struck_correct = [e for e in correct if e.get("cue_type") != "NO_GO"]

    latencies = [
        e["response_latency_ms"] for e in struck_correct if e.get("response_latency_ms") is not None
    ]
    timing_errors = [
        e["timing_error_ms"] for e in struck_correct if e.get("timing_error_ms") is not None
    ]
    timing_abs = [abs(v) for v in timing_errors]
    holds = [e["hold_duration_ms"] for e in rows if e.get("hold_duration_ms") is not None]

    def hand_correct(hand: str) -> list[dict[str, Any]]:
        return [e for e in correct if e.get("hand") == hand]

    def hand_cues(hand: str) -> list[dict[str, Any]]:
        return [e for e in cues if e.get("hand") == hand]

    left_lat = [e["response_latency_ms"] for e in hand_correct("LEFT")
                if e.get("response_latency_ms") is not None and e.get("cue_type") != "NO_GO"]
    right_lat = [e["response_latency_ms"] for e in hand_correct("RIGHT")
                 if e.get("response_latency_ms") is not None and e.get("cue_type") != "NO_GO"]
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

    # --------------------------------------------------------- recipe metrics

    # Bimanual synchrony. Both rows of a pair carry the same value, so the pairs
    # are counted from the PRIMARY rows only; counting both would weight every
    # pair twice.
    sync_values = [
        e["inter_hand_onset_diff_ms"]
        for e in cues
        if e.get("pair_role") == "PRIMARY" and e.get("pair_id") is None
        and e.get("inter_hand_onset_diff_ms") is not None
    ]
    pair_count = sum(1 for e in cues if e.get("pair_role") == "PRIMARY" and e.get("pair_id") is None)

    # CFT splits on the cue onset, which is null exactly where the recipe removed
    # the cue. Deriving the split from the recipe id instead would break the
    # moment a second recipe reuses the policy.
    #
    # The split is reported only when the round ACTUALLY had two phases. A plain
    # round has an onset on every cue, so "cued phase accuracy" would just be the
    # overall accuracy under a heading that implies a CFT protocol ran. Absent is
    # the honest answer there.
    un_cued = [e for e in cues if e.get("cue_onset_time_ms") is None]
    cued = [e for e in cues if e.get("cue_onset_time_ms") is not None]
    has_two_phases = bool(cued) and bool(un_cued)
    free_correct = [e for e in un_cued if e.get("is_correct") and e.get("cue_type") != "NO_GO"]
    free_timing = [
        abs(e["timing_error_ms"]) for e in free_correct if e.get("timing_error_ms") is not None
    ]
    free_onsets = sorted(
        e["actual_time_ms"] for e in free_correct if e.get("actual_time_ms") is not None
    )
    free_intervals = [
        float(b - a) for a, b in zip(free_onsets, free_onsets[1:]) if b > a
    ]

    # An accent belongs to the BEAT, not to each hand.
    #
    # Grouping by cue index matters if an accent round ever pairs with a bimanual
    # one: two hands playing the same accented beat is one accent, and counting
    # rows would report 2/4 where the patient actually hit 2 of 3 beats. A beat
    # counts as hit only when every row belonging to it was correct.
    accent_beats: dict[Any, list[dict[str, Any]]] = {}
    for row in cues:
        if row.get("is_accent") is not True:
            continue
        accent_beats.setdefault(row.get("cue_index"), []).append(row)
    accent_hits = sum(1 for group in accent_beats.values() if all(g.get("is_correct") for g in group))

    result = PianoMetrics(
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
        # A recipe metric is None when the round did not produce it, which is what
        # keeps a plain round's report identical to before.
        inter_hand_sync_mean_ms=_mean(sync_values),
        inter_hand_sync_sd_ms=_std(sync_values),
        inter_hand_pair_count=pair_count or None,
        cued_phase_accuracy=(
            _ratio(len([e for e in cued if e.get("is_correct")]), len(cued))
            if has_two_phases
            else None
        ),
        free_phase_accuracy=_ratio(len(free_correct), len(un_cued)) if has_two_phases else None,
        free_phase_timing_mae_ms=_mean(free_timing) if has_two_phases and free_timing else None,
        free_phase_interval_cv=_cv(free_intervals) if has_two_phases and free_intervals else None,
        free_phase_cue_count=len(un_cued) if has_two_phases else None,
        accent_hit_rate=_ratio(accent_hits, len(accent_beats)) if accent_beats else None,
        accent_cue_count=len(accent_beats) or None,
    )
    _extended_recipe_metrics(result, cues)
    return result


def _extended_recipe_metrics(result: PianoMetrics, cues: list[dict[str, Any]]) -> None:
    """Add v2 recipe values from raw timestamps, never client aggregate fields."""
    hold_cues = [e for e in cues if e.get("target_hold_ms") is not None]
    released = [e for e in hold_cues if e.get("key_down_time_ms") is not None
                and e.get("key_up_time_ms") is not None
                and e["key_up_time_ms"] >= e["key_down_time_ms"]]
    result.hold_duration_mae_ms = _mean([
        abs(e["key_up_time_ms"] - e["key_down_time_ms"] - e["target_hold_ms"])
        for e in released
    ])
    result.hold_release_completion_rate = _ratio(len(released), len(hold_cues))

    pairs: dict[int, dict[str, dict]] = {}
    for row in cues:
        if row.get("pair_id") is not None and row.get("pair_role") is not None:
            pairs.setdefault(row["pair_id"], {})[row["pair_role"]] = row
    phases = []
    for pair in pairs.values():
        left, right = pair.get("PRIMARY"), pair.get("SECONDARY")
        if left is None or right is None:
            continue
        target = left.get("target_offset_ms")
        if (target is not None and left.get("actual_time_ms") is not None
                and right.get("actual_time_ms") is not None):
            phases.append(abs(right["actual_time_ms"] - left["actual_time_ms"] - target))
    result.inter_hand_phase_mae_ms = _mean(phases)
    if pairs:
        for role, metric in (("PRIMARY", "offset_left_miss_rate"),
                             ("SECONDARY", "offset_right_miss_rate")):
            misses = sum(1 for pair in pairs.values() if pair.get(role) is None
                         or pair[role].get("is_missed") or pair[role].get("actual_time_ms") is None)
            setattr(result, metric, _ratio(misses, len(pairs)))

    reverse = [e for e in cues if e.get("recipe_id") == "REVERSE_SEQUENCE"]
    result.reverse_position_accuracy = _ratio(sum(bool(e.get("is_correct")) for e in reverse), len(reverse))
    groups: dict[int, list[dict]] = {}
    for row in reverse:
        if row.get("memory_group") is not None:
            groups.setdefault(row["memory_group"], []).append(row)
    completed = 0
    for group in groups.values():
        length = group[0].get("sequence_length")
        positions = {e.get("sequence_position") for e in group}
        if length and positions == set(range(1, length + 1)) and all(e.get("is_correct") for e in group):
            completed += 1
    result.reverse_completion_rate = _ratio(completed, len(groups))

    go = [e for e in cues if e.get("cue_type") == "GO"]
    no_go = [e for e in cues if e.get("cue_type") == "NO_GO"]
    if go or no_go:
        result.go_commission_count = sum(e.get("actual_time_ms") is not None for e in no_go)
        result.go_omission_count = sum(e.get("actual_time_ms") is None for e in go)
        result.go_response_latency_ms = _mean([
            e["actual_time_ms"] - e["cue_onset_time_ms"] for e in go
            if e.get("is_correct") and e.get("actual_time_ms") is not None
            and e.get("cue_onset_time_ms") is not None
        ])

    for segment in range(4):
        group = [e for e in cues if e.get("tempo_segment") == segment]
        if not group:
            continue
        accuracy = _ratio(sum(bool(e.get("is_correct")) for e in group), len(group))
        mae = _mean([abs(e["actual_time_ms"] - e["target_time_ms"]) for e in group
                     if e.get("is_correct") and e.get("actual_time_ms") is not None
                     and e.get("target_time_ms") is not None and e.get("cue_type") != "NO_GO"])
        result.tempo_segments.append({"segment": segment, "accuracy": accuracy,
            "timing_mae_ms": mae, "miss_rate": _ratio(sum(bool(e.get("is_missed")) for e in group), len(group)),
            "cue_count": len(group)})
        setattr(result, f"tempo_segment_{segment}_accuracy", accuracy)
        setattr(result, f"tempo_segment_{segment}_mae_ms", mae)


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
