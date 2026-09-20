"""
MediaPipe PoseLandmarker adapter for homecam.

Lazy-imports mediapipe so pure-logic tests never need native deps.
Outputs PersonObservation dataclasses that cross the seam to HumanMotionAnalyzer.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Sequence

import numpy as np

from .human_motion import Landmark, PersonObservation, Sensitivity

logger = logging.getLogger("homecam.pose")

MAX_INPUT_DIM = 320


class PoseDetectorError(Exception):
    """Raised when MediaPipe initialization or processing fails."""


class PoseDetector:
    """MediaPipe PoseLandmarker adapter.

    Uses VIDEO running mode, CPU delegate, up to 2 poses.
    Input frames are downscaled to max 320px (preserving aspect ratio)
    and converted to RGB before inference.

    Usage::

        with PoseDetector.open(model_path) as det:
            observations = det.detect(bgr_frame, timestamp_ms)
    """

    def __init__(self, model_path: Path) -> None:
        if not model_path.exists():
            raise PoseDetectorError(f"Model file not found: {model_path}")
        self._model_path = model_path
        self._landmarker: Optional[object] = None
        self._last_timestamp_ms: int = -1
        self._init_landmarker()

    def _init_landmarker(self) -> None:
        try:
            import mediapipe as mp
        except ImportError as exc:
            raise PoseDetectorError(
                "mediapipe not installed. Install mediapipe>=0.10.14"
            ) from exc

        mp_pose = mp.tasks.vision
        base_options = mp.tasks.BaseOptions(
            model_asset_path=str(self._model_path),
            delegate=mp.tasks.BaseOptions.Delegate.CPU,
        )
        options = mp_pose.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=mp_pose.RunningMode.VIDEO,
            num_poses=2,
            output_segmentation_masks=False,
        )
        try:
            self._landmarker = mp_pose.PoseLandmarker.create_from_options(options)
        except Exception as exc:
            raise PoseDetectorError(f"Failed to create PoseLandmarker: {exc}") from exc

    def detect(
        self,
        bgr_frame: np.ndarray,
        timestamp_ms: int,
    ) -> Sequence[PersonObservation]:
        """Run pose detection on a BGR frame.

        Args:
            bgr_frame: OpenCV BGR uint8 image.
            timestamp_ms: Strictly increasing monotonic timestamp in ms.

        Returns:
            Sequence of PersonObservation for each detected person.

        Raises:
            PoseDetectorError: On invalid timestamp or detection failure.
        """
        if timestamp_ms <= self._last_timestamp_ms:
            raise PoseDetectorError(
                f"Timestamps must be strictly increasing: "
                f"got {timestamp_ms}, last was {self._last_timestamp_ms}"
            )
        self._last_timestamp_ms = timestamp_ms

        resized = self._downscale(bgr_frame)
        rgb = resized[:, :, ::-1]  # BGR -> RGB

        import mediapipe as mp

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=np.ascontiguousarray(rgb),
        )

        try:
            result = self._landmarker.detect_for_video(mp_image, timestamp_ms)
        except Exception as exc:
            raise PoseDetectorError(f"Detection failed: {exc}") from exc

        return self._convert_result(result)

    def reset(self) -> None:
        """Reset timestamp tracking (e.g. after camera restart)."""
        self._last_timestamp_ms = -1

    def close(self) -> None:
        """Release MediaPipe resources. Safe to call multiple times."""
        if self._landmarker is not None:
            try:
                self._landmarker.close()
            except Exception:
                logger.debug("PoseLandmarker close raised; ignoring", exc_info=True)
            self._landmarker = None

    @classmethod
    @contextmanager
    def open(cls, model_path: Path):
        """Context manager that guarantees close on exit."""
        det = cls(model_path)
        try:
            yield det
        finally:
            det.close()

    # -- Internal -----------------------------------------------------------

    @staticmethod
    def _downscale(frame: np.ndarray) -> np.ndarray:
        """Downscale to max MAX_INPUT_DIM px preserving aspect ratio."""
        h, w = frame.shape[:2]
        if max(h, w) <= MAX_INPUT_DIM:
            return frame
        scale = MAX_INPUT_DIM / max(h, w)
        new_w = int(w * scale)
        new_h = int(h * scale)
        import cv2
        return cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

    @staticmethod
    def _convert_result(result) -> list[PersonObservation]:
        """Convert MediaPipe PoseLandmarkerResult to PersonObservation list."""
        observations: list[PersonObservation] = []
        for person_landmarks in result.pose_landmarks:
            lms: list[Landmark] = []
            for idx, lm in enumerate(person_landmarks):
                lms.append(Landmark(
                    index=idx,
                    x=lm.x,
                    y=lm.y,
                    visibility=lm.visibility,
                ))
            observations.append(PersonObservation(landmarks=tuple(lms)))
        return observations
