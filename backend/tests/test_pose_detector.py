"""Tests for backend.app.pose_detector — adapter interface tests.

These test the PoseDetector seam (init validation, close safety, context manager,
downscale logic, result conversion) WITHOUT requiring native MediaPipe.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

sys.path.insert(0, "/Users/mymac/Documents/project_kevin/homecam-server")

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None  # type: ignore[assignment]

# pose_detector imports numpy at module level; stub if missing
if not HAS_NUMPY:
    import types as _t
    _np_stub = _t.ModuleType("numpy")
    _np_stub.ndarray = object  # type: ignore[attr-defined]
    _np_stub.uint8 = None  # type: ignore[attr-defined]
    _np_stub.zeros = lambda *a, **k: None  # type: ignore[attr-defined]
    _np_stub.ascontiguousarray = lambda x: x  # type: ignore[attr-defined]
    sys.modules["numpy"] = _np_stub
    import numpy as np  # type: ignore[no-redef]

from backend.app.pose_detector import PoseDetector, PoseDetectorError


class TestPoseDetectorInitValidation(unittest.TestCase):
    def test_missing_model_raises(self):
        """Given: model path does not exist.
        When: construct PoseDetector.
        Then: PoseDetectorError raised."""
        with self.assertRaises(PoseDetectorError) as ctx:
            PoseDetector(Path("/nonexistent/model.task"))
        self.assertIn("not found", str(ctx.exception))


class TestPoseDetectorMissingMediaPipe(unittest.TestCase):
    def test_no_mediapipe_raises_clear_error(self):
        """Given: mediapipe not importable.
        When: construct PoseDetector with valid path.
        Then: PoseDetectorError mentioning install."""
        with tempfile.NamedTemporaryFile(suffix=".task") as f:
            model_path = Path(f.name)
            with patch.dict(sys.modules, {"mediapipe": None}):
                with self.assertRaises(PoseDetectorError) as ctx:
                    PoseDetector(model_path)
            self.assertIn("mediapipe not installed", str(ctx.exception))


class TestPoseDetectorCloseSafety(unittest.TestCase):
    def test_close_twice_no_crash(self):
        """Given: PoseDetector with mock landmarker.
        When: close called twice.
        Then: no exception."""
        det = PoseDetector.__new__(PoseDetector)
        det._model_path = Path("/fake")
        det._last_timestamp_ms = -1
        mock_lm = MagicMock()
        det._landmarker = mock_lm

        det.close()
        det.close()  # second call safe

        mock_lm.close.assert_called_once()

    def test_close_with_failing_landmarker(self):
        """Given: landmarker.close() raises.
        When: close called.
        Then: no propagation (exception swallowed)."""
        det = PoseDetector.__new__(PoseDetector)
        det._model_path = Path("/fake")
        det._last_timestamp_ms = -1
        mock_lm = MagicMock()
        mock_lm.close.side_effect = RuntimeError("boom")
        det._landmarker = mock_lm

        det.close()  # should not raise
        self.assertIsNone(det._landmarker)


@unittest.skipUnless(HAS_NUMPY, "numpy required for array tests")
class TestPoseDetectorDownscale(unittest.TestCase):
    def test_small_frame_unchanged(self):
        """Given: 200x150 frame (below 320).
        When: _downscale.
        Then: returned as-is."""
        frame = np.zeros((150, 200, 3), dtype=np.uint8)
        result = PoseDetector._downscale(frame)
        self.assertEqual(result.shape, (150, 200, 3))

    def test_large_frame_downscaled(self):
        """Given: 640x480 frame.
        When: _downscale.
        Then: max dimension = 320, aspect preserved."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = PoseDetector._downscale(frame)
        self.assertEqual(max(result.shape[:2]), 320)
        self.assertEqual(result.shape[:2], (240, 320))


class TestPoseDetectorConvertResult(unittest.TestCase):
    def test_convert_result_two_persons(self):
        """Given: mock MediaPipe result with 2 persons.
        When: _convert_result.
        Then: 2 PersonObservation with correct landmark data."""
        lm1 = SimpleNamespace(x=0.1, y=0.2, visibility=0.9)
        lm2 = SimpleNamespace(x=0.3, y=0.4, visibility=0.8)
        person1 = [lm1, lm2]
        person2 = [SimpleNamespace(x=0.5, y=0.6, visibility=0.7)]
        result = SimpleNamespace(pose_landmarks=[person1, person2])

        observations = PoseDetector._convert_result(result)
        self.assertEqual(len(observations), 2)
        self.assertEqual(len(observations[0].landmarks), 2)
        self.assertEqual(observations[0].landmarks[0].x, 0.1)
        self.assertEqual(observations[0].landmarks[1].index, 1)
        self.assertEqual(len(observations[1].landmarks), 1)

    def test_convert_empty_result(self):
        """Given: no persons detected.
        When: _convert_result.
        Then: empty list."""
        result = SimpleNamespace(pose_landmarks=[])
        observations = PoseDetector._convert_result(result)
        self.assertEqual(observations, [])


class TestPoseDetectorTimestampMonotonic(unittest.TestCase):
    def test_non_increasing_timestamp_raises(self):
        """Given: PoseDetector with last_timestamp=100.
        When: detect called with timestamp<=100.
        Then: PoseDetectorError raised."""
        det = PoseDetector.__new__(PoseDetector)
        det._model_path = Path("/fake")
        det._last_timestamp_ms = 100
        det._landmarker = MagicMock()

        with self.assertRaises(PoseDetectorError) as ctx:
            frame_stub = object()
            det.detect(frame_stub, 100)
        self.assertIn("strictly increasing", str(ctx.exception))

    def test_reset_clears_timestamp(self):
        """Given: PoseDetector with last_timestamp=100.
        When: reset called.
        Then: last_timestamp back to -1."""
        det = PoseDetector.__new__(PoseDetector)
        det._last_timestamp_ms = 100
        det.reset()
        self.assertEqual(det._last_timestamp_ms, -1)


if __name__ == "__main__":
    unittest.main()
