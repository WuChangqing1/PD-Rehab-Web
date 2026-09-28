"""Hand landmark signal construction.

MediaPipe Hand landmark topology indices used by this module
=============================================================

The external repository (VideoBased-PD-Biomarkers) references landmarks through
`mp.solutions.hands.HandLandmark`. **mediapipe 1.0.1 removed `mp.solutions`
entirely**, so that file cannot run on the installed version. The canonical
indices are therefore defined here as module constants rather than imported, and
were verified against real inference (327/327 frames detected on the
repository's own demo video).

    0  WRIST
    4  THUMB_TIP
    5  INDEX_FINGER_MCP
    8  INDEX_FINGER_TIP

Normalization (PALM_REFERENCE)
=============================
Taken verbatim from the external repository's `_normalize_keypoints_distance`:
translate so WRIST is the origin, then divide by the 3D distance from WRIST to
INDEX_FINGER_MCP (the palm reference length). The divisor is clamped to 1e-5 to
avoid division by zero. This keeps the signal scale-invariant, so moving the
hand closer to or further from the camera does not change the amplitude.

Distance signal
==============
`d(t) = ||normalized(THUMB_TIP) - normalized(INDEX_FINGER_TIP)||` in 3D. This is
the thumb-index aperture: it opens and closes during finger tapping.

Filtering
=========
Butterworth low-pass, order 4, cutoff 9.0 Hz, applied with `filtfilt`
(zero-phase, so peak frame indices are not shifted in time).

Documented deviation from upstream: the repository hardcodes `fs = 30.0`
regardless of the video's real frame rate. Here the real fps is used, and the
value actually used is recorded in quality_json.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence

import numpy as np
from scipy.signal import butter, filtfilt

# ---------------------------------------------------------------- landmark ids
WRIST = 0
THUMB_TIP = 4
INDEX_FINGER_MCP = 5
INDEX_FINGER_TIP = 8

LANDMARK_COUNT = 21

# Divisor clamp, copied from the external repository.
_MIN_PALM_REFERENCE = 1e-5

DEFAULT_FILTER_ORDER = 4
DEFAULT_FILTER_CUTOFF_HZ = 9.0


class Landmark(Protocol):
    """Structural type for a MediaPipe NormalizedLandmark."""

    x: float
    y: float
    z: float


@dataclass
class HandObservation:
    """One frame's worth of normalized hand data."""

    frame_index: int
    timestamp_ms: int
    handedness_label: str | None
    handedness_score: float | None
    normalized: list[tuple[float, float, float]]
    raw: list[tuple[float, float, float]]
    palm_reference: float

    @property
    def thumb_tip(self) -> tuple[float, float, float]:
        return self.normalized[THUMB_TIP]

    @property
    def index_tip(self) -> tuple[float, float, float]:
        return self.normalized[INDEX_FINGER_TIP]


@dataclass
class DistanceSignal:
    """The aperture time series plus everything needed to interpret it."""

    values: np.ndarray
    frame_indices: np.ndarray
    timestamps_ms: np.ndarray
    handedness_labels: list[str | None] = field(default_factory=list)
    handedness_scores: list[float | None] = field(default_factory=list)
    palm_references: list[float] = field(default_factory=list)
    filtered: bool = False
    filter_fs_hz: float | None = None
    filter_order: int | None = None
    filter_cutoff_hz: float | None = None
    notes: list[str] = field(default_factory=list)

    def __len__(self) -> int:
        return int(self.values.size)

    def to_plain(self) -> dict[str, Any]:
        """JSON-safe summary (the full series lives in a .npz / raw_features)."""
        return {
            "sample_count": int(self.values.size),
            "filtered": self.filtered,
            "filter_fs_hz": self.filter_fs_hz,
            "filter_order": self.filter_order,
            "filter_cutoff_hz": self.filter_cutoff_hz,
            "notes": list(self.notes),
        }


def normalize_landmarks(landmarks: Sequence[Landmark]) -> tuple[list[tuple[float, float, float]], float]:
    """PALM_REFERENCE normalization, mirroring the external repository.

    Returns (normalized_points, palm_reference_length).
    """
    wrist = landmarks[WRIST]
    index_mcp = landmarks[INDEX_FINGER_MCP]

    palm_reference = float(
        np.sqrt(
            (index_mcp.x - wrist.x) ** 2
            + (index_mcp.y - wrist.y) ** 2
            + (index_mcp.z - wrist.z) ** 2
        )
    )
    if palm_reference < _MIN_PALM_REFERENCE:
        palm_reference = _MIN_PALM_REFERENCE

    normalized = [
        (
            (lm.x - wrist.x) / palm_reference,
            (lm.y - wrist.y) / palm_reference,
            (lm.z - wrist.z) / palm_reference,
        )
        for lm in landmarks
    ]
    return normalized, palm_reference


def aperture_from_normalized(normalized: Sequence[tuple[float, float, float]]) -> float:
    """3D distance between THUMB_TIP and INDEX_FINGER_TIP."""
    tx, ty, tz = normalized[THUMB_TIP]
    ix, iy, iz = normalized[INDEX_FINGER_TIP]
    return float(np.sqrt((tx - ix) ** 2 + (ty - iy) ** 2 + (tz - iz) ** 2))


def observations_to_signal(observations: Sequence[HandObservation]) -> DistanceSignal:
    """Build the raw (unfiltered) aperture series from per-frame observations."""
    if not observations:
        return DistanceSignal(
            values=np.empty(0),
            frame_indices=np.empty(0, dtype=int),
            timestamps_ms=np.empty(0, dtype=int),
            notes=["no_hand_detected"],
        )

    values = np.array(
        [aperture_from_normalized(o.normalized) for o in observations], dtype=float
    )
    return DistanceSignal(
        values=values,
        frame_indices=np.array([o.frame_index for o in observations], dtype=int),
        timestamps_ms=np.array([o.timestamp_ms for o in observations], dtype=int),
        handedness_labels=[o.handedness_label for o in observations],
        handedness_scores=[o.handedness_score for o in observations],
        palm_references=[o.palm_reference for o in observations],
    )


def lowpass_filter(
    signal: DistanceSignal,
    *,
    fps: float,
    order: int = DEFAULT_FILTER_ORDER,
    cutoff_hz: float = DEFAULT_FILTER_CUTOFF_HZ,
) -> DistanceSignal:
    """Zero-phase Butterworth low-pass.

    `filtfilt` is applied so peak positions are not shifted, which matters
    because peaks define cycle boundaries and therefore every feature.

    Falls back to an unfiltered signal (with a note) when the series is too
    short for the filter's padding requirements, rather than raising.
    """
    values = signal.values
    if values.size == 0:
        return signal

    if fps is None or fps <= 0:
        notes = [*signal.notes, "filter_skipped_invalid_fps"]
        return DistanceSignal(**{**signal.__dict__, "notes": notes})

    nyquist = 0.5 * fps
    if cutoff_hz >= nyquist:
        # Cutoff above Nyquist is meaningless; clamp and record it.
        cutoff_hz = nyquist * 0.99
        signal.notes.append("filter_cutoff_clamped_below_nyquist")

    normal_cutoff = cutoff_hz / nyquist
    try:
        b, a = butter(order, normal_cutoff, btype="low", analog=False)
        # filtfilt needs more than 3 * max(len(a), len(b)) samples.
        padlen = 3 * max(len(a), len(b))
        if values.size <= padlen:
            signal.notes.append("filter_skipped_series_too_short")
            return signal
        filtered = filtfilt(b, a, values)
    except Exception as exc:  # noqa: BLE001 - filtering must never break analysis
        signal.notes.append(f"filter_failed:{type(exc).__name__}")
        return signal

    return DistanceSignal(
        values=np.asarray(filtered, dtype=float),
        frame_indices=signal.frame_indices,
        timestamps_ms=signal.timestamps_ms,
        handedness_labels=signal.handedness_labels,
        handedness_scores=signal.handedness_scores,
        palm_references=signal.palm_references,
        filtered=True,
        filter_fs_hz=float(fps),
        filter_order=order,
        filter_cutoff_hz=float(cutoff_hz),
        notes=signal.notes,
    )


def speed_signal(signal: DistanceSignal, fps: float) -> np.ndarray:
    """First difference of the aperture divided by the sampling interval.

    `np.diff` shortens the array by one; values are indexed the same way the
    external repository does it (speed_signal[i] is the change between frame i
    and i+1).
    """
    if signal.values.size < 2 or fps is None or fps <= 0:
        return np.empty(0, dtype=float)
    return np.diff(signal.values) / (1.0 / fps)
