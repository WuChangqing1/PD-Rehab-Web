"""Pose landmark extraction (MediaPipe Pose Landmarker, Tasks API).

Mirrors the finger tapping approach: OpenCV decodes the video, MediaPipe returns
33 landmarks per frame in VIDEO mode, and everything downstream works on that
series. Nothing here interprets the movement; see `metrics.py` and `analyzer.py`.

MEASURED DIFFERENCES FROM THE HAND LANDMARKER (verified in Phase 6, not assumed)
==============================================================================
* The pose model **does** populate `visibility` (0..1) and `presence` (0..1).
  The hand landmarker in mediapipe 1.0.1 returns `None` for both on every frame,
  which forced a documented workaround in the finger tapping module. The pose
  pipeline can therefore gate on real visibility values, and does.
  Probe: one public-domain photograph, 33/33 landmarks returned,
  visibility min 0.311 / mean 0.747 / max 0.999 (legs were partly occluded,
  which is exactly what the value is for).
* Coordinates are normalised to the image (x, y in 0..1, z relative depth).
  Angles are computed after scaling x by width and y by height, otherwise a
  non-square frame would distort every angle.

WHY THIS RUNS IN IMAGE MODE, NOT VIDEO MODE
===========================================
Video mode tracks a pose across frames and is roughly twice as fast, which is
the obvious choice for a video pipeline. It is not usable for measurement here.

Measured on a motionless subject (one still photograph repeated into a clip, so
every variation is model noise), shoulder abduction:

    VIDEO mode (tracking)   mean 143.85 deg, range 62.41 deg
    IMAGE mode (stateless)  mean  92.86 deg, range  0.00 deg

The tracker drifts by more than 60 degrees on an input that does not move, which
is larger than the movement some of these exercises ask for. Image mode is
stateless, reproducible, and costs about 2.2x the time (38.6 ms vs 17.8 ms per
frame on the development machine). Correctness wins; `frame_stride` is the knob
for runtime instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

# Video-mode tracking is deliberately not used; see the module docstring.
RUNNING_MODE = "IMAGE"
DEFAULT_FRAME_STRIDE = 2

# MediaPipe Pose landmark indices. Pinned as constants for the same reason as
# the hand landmarks: `mp.solutions` no longer exists in mediapipe 1.0.1, so the
# indices cannot be taken from a solution wrapper.
NOSE = 0
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_ELBOW = 13
RIGHT_ELBOW = 14
LEFT_WRIST = 15
RIGHT_WRIST = 16
LEFT_HIP = 23
RIGHT_HIP = 24
LEFT_KNEE = 25
RIGHT_KNEE = 26
LEFT_ANKLE = 27
RIGHT_ANKLE = 28

POSE_LANDMARK_NAMES: tuple[str, ...] = (
    "nose",
    "left_eye_inner",
    "left_eye",
    "left_eye_outer",
    "right_eye_inner",
    "right_eye",
    "right_eye_outer",
    "left_ear",
    "right_ear",
    "mouth_left",
    "mouth_right",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_pinky",
    "right_pinky",
    "left_index",
    "right_index",
    "left_thumb",
    "right_thumb",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
    "left_heel",
    "right_heel",
    "left_foot_index",
    "right_foot_index",
)

LANDMARK_COUNT = len(POSE_LANDMARK_NAMES)

# Joints every exercise in this module depends on.
CORE_JOINTS: tuple[int, ...] = (
    LEFT_SHOULDER,
    RIGHT_SHOULDER,
    LEFT_ELBOW,
    RIGHT_ELBOW,
    LEFT_WRIST,
    RIGHT_WRIST,
    LEFT_HIP,
    RIGHT_HIP,
)

MIN_LANDMARK_VISIBILITY = 0.5


@dataclass(frozen=True)
class Landmark:
    """One of the 33 pose points, in image-normalised coordinates."""

    x: float
    y: float
    z: float
    visibility: float | None
    presence: float | None


@dataclass
class PoseSeries:
    """The landmark series for one video."""

    fps: float
    width: int
    height: int
    frame_count: int
    # One entry per analysed frame; None when no pose was found in that frame.
    frames: list[list[Landmark] | None]

    @property
    def valid_frame_count(self) -> int:
        return sum(1 for f in self.frames if f is not None)

    @property
    def valid_frame_ratio(self) -> float:
        if not self.frames:
            return 0.0
        return self.valid_frame_count / len(self.frames)

    @property
    def duration_sec(self) -> float:
        return len(self.frames) / self.fps if self.fps > 0 else 0.0

    def point(self, frame_index: int, landmark_index: int) -> Landmark | None:
        frame = self.frames[frame_index]
        if frame is None or landmark_index >= len(frame):
            return None
        return frame[landmark_index]

    def pixel_xy(self, frame_index: int, landmark_index: int) -> tuple[float, float] | None:
        """Landmark in pixel coordinates, so angles are not distorted by aspect."""
        lm = self.point(frame_index, landmark_index)
        if lm is None:
            return None
        return lm.x * self.width, lm.y * self.height

    def mean_visibility(self, indices: tuple[int, ...] | None = None) -> float | None:
        """Mean visibility across the given joints, ignoring missing values.

        Returns None when the model reported no visibility at all, so a caller
        can tell "not measured" apart from "measured as zero".
        """
        wanted = indices if indices is not None else tuple(range(LANDMARK_COUNT))
        values: list[float] = []
        for frame in self.frames:
            if frame is None:
                continue
            for index in wanted:
                if index >= len(frame):
                    continue
                value = frame[index].visibility
                if value is not None:
                    values.append(value)
        if not values:
            return None
        return sum(values) / len(values)


class PoseExtractionError(RuntimeError):
    """Raised when the video cannot be read or the model cannot run."""


def _import_mediapipe():
    try:
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision
    except Exception as exc:  # noqa: BLE001
        raise PoseExtractionError(
            f"MediaPipe 不可用，无法进行 Pose 关键点提取：{exc}"
        ) from exc
    return mp, mp_python, vision


def extract_landmarks(
    video_path: str | Path,
    *,
    model_path: str | Path,
    max_frames: int | None = None,
    frame_stride: int = DEFAULT_FRAME_STRIDE,
    min_detection_confidence: float = 0.3,
    min_presence_confidence: float = 0.3,
    min_tracking_confidence: float = 0.3,
) -> PoseSeries:
    """Run the pose landmarker over a video and return the raw series.

    Every `frame_stride`-th frame is analysed, independently of the others. The
    resulting fps is the effective rate, which is what the duration, hold time
    and repetition interval are computed against.
    """
    import cv2
    import numpy as np

    path = Path(video_path)
    if not path.is_file():
        raise PoseExtractionError(f"视频文件不存在：{path}")
    model = Path(model_path)
    if not model.is_file():
        raise PoseExtractionError(
            f"未找到 MediaPipe Pose Landmarker 模型文件：{model}"
        )

    mp, mp_python, vision = _import_mediapipe()

    stride = max(1, int(frame_stride))
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise PoseExtractionError(f"无法打开视频：{path}")

    try:
        source_fps = float(capture.get(cv2.CAP_PROP_FPS)) or 30.0
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)) or 0
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 0
        effective_fps = source_fps / stride

        options = vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(model)),
            running_mode=vision.RunningMode.IMAGE,
            num_poses=1,
            min_pose_detection_confidence=min_detection_confidence,
            min_pose_presence_confidence=min_presence_confidence,
            min_tracking_confidence=min_tracking_confidence,
            output_segmentation_masks=False,
        )

        frames: list[list[Landmark] | None] = []
        with vision.PoseLandmarker.create_from_options(options) as landmarker:
            source_index = 0
            analysed = 0
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                if source_index % stride != 0:
                    source_index += 1
                    continue
                if max_frames is not None and analysed >= max_frames:
                    break
                if not width or not height:
                    height, width = frame.shape[:2]

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=np.ascontiguousarray(rgb),
                )
                result = landmarker.detect(mp_image)

                if result.pose_landmarks:
                    frames.append(
                        [
                            Landmark(
                                x=float(lm.x),
                                y=float(lm.y),
                                z=float(lm.z),
                                visibility=None if lm.visibility is None else float(lm.visibility),
                                presence=None if lm.presence is None else float(lm.presence),
                            )
                            for lm in result.pose_landmarks[0]
                        ]
                    )
                else:
                    frames.append(None)
                analysed += 1
                source_index += 1
    finally:
        capture.release()

    return PoseSeries(
        fps=effective_fps,
        width=width,
        height=height,
        frame_count=len(frames),
        frames=frames,
    )


def iter_present_frames(series: PoseSeries) -> Iterator[tuple[int, list[Landmark]]]:
    """Yield (frame index, landmarks) for frames where a pose was found."""
    for index, frame in enumerate(series.frames):
        if frame is not None:
            yield index, frame
