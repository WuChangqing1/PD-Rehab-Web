"""Finger Tapping analysis pipeline.

PHASE 4 PLACEHOLDER.

The real pipeline is:

    Video -> OpenCV -> MediaPipe HandLandmarker -> 21 keypoints
          -> palm-reference normalisation -> distance series
          -> Butterworth low-pass (order 4, 9 Hz) -> peaks / troughs
          -> cycle split -> 12 motor features -> QC gate

Algorithm semantics come from the external repository
D:\\CodingData\\Github\\VideoBased-PD-Biomarkers (Apache-2.0, unmodified) and are
documented in docs/metric_definitions.md section 1.

This module deliberately does NOT return any metrics. Implementing a stub that
returned plausible numbers would be exactly the fabrication the specification
forbids, so it raises NOT_IMPLEMENTED until Phase 4 wires up the real pipeline.
"""

from __future__ import annotations

from app.core.errors import APIError

PHASE = "Phase 4"


def analyze_video(video_path: str, hand: str) -> dict:
    """Analyse one finger tapping video for one hand.

    Raises 501 until the real pipeline exists.
    """
    raise APIError(
        501,
        "NOT_IMPLEMENTED",
        "Finger Tapping 分析流水线尚未实现（计划于 Phase 4）。"
        "系统不会返回任何推测或示例指标。",
        {
            "phase": PHASE,
            "hand": hand,
            "video_registered": bool(video_path),
            "requirements": [
                "opencv（opencv-contrib-python）",
                "mediapipe",
                "hand_landmarker.task",
            ],
            "planned_steps": [
                "video_qc",
                "hand_landmarker_inference",
                "palm_reference_normalisation",
                "distance_timeseries",
                "butterworth_lowpass",
                "peak_trough_detection",
                "cycle_segmentation",
                "feature_extraction",
                "quality_gate",
            ],
        },
    )
