"""Integration tests for Pose Lite detector integration in CameraManager."""

from __future__ import annotations

import asyncio
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from backend.app.human_motion import Landmark, PersonObservation
from backend.app.main import CameraManager, Settings, camera_status, camera as global_camera


def _make_landmarks(dx: float = 0.0, dy: float = 0.0) -> PersonObservation:
    landmarks = [
        Landmark(
            index=i,
            x=0.5 + (0.05 if i % 2 else 0.0) + (dx if i in (15, 16) else 0.0),
            y=0.4 + (0.04 * (i - 11)) + (dy if i in (15, 16) else 0.0),
            visibility=0.9,
        )
        for i in range(11, 33)
    ]
    return PersonObservation(landmarks=tuple(landmarks))


class TestCameraDetectorIntegration(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.recordings_dir = Path(self.tmpdir.name) / "recordings"
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        self.frame = np.zeros((480, 640, 3), dtype=np.uint8)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _make_settings(self, **kwargs) -> Settings:
        defaults = {
            "recordings_dir": str(self.recordings_dir),
            "motion_detection_enabled": True,
            "auto_record_enabled": True,
            "detection_sensitivity": "medium",
            "stop_recording_after_seconds": 2,
        }
        defaults.update(kwargs)
        return Settings(**defaults)

    def _make_camera(self, mock_detector=None) -> CameraManager:
        cam = CameraManager()
        cam.recordings_dir = str(self.recordings_dir)
        if mock_detector:
            cam._detector = mock_detector
            cam.detector_status = "ready"
        return cam

    def test_moving_pose_starts_auto_recording(self):
        obs = [
            _make_landmarks(0.0, 0.0),
            _make_landmarks(0.2, 0.2),
            _make_landmarks(0.4, 0.4),
        ]
        detector = MagicMock(detect=MagicMock(side_effect=[[person] for person in obs]))
        cam = self._make_camera(detector)

        with patch("backend.app.main.load_settings", return_value=self._make_settings()):
            for _ in range(3):
                cam._last_detection_time = 0.0
                cam._process_motion(self.frame)

        self.assertTrue(cam.motion_detected)
        self.assertTrue(cam.recording)
        self.assertEqual(cam.recording_type, "motion")
        cam.stop()

    def test_stationary_and_nonhuman_do_not_trigger_motion(self):
        st = [_make_landmarks(0.0, 0.0)]
        detector = MagicMock(detect=MagicMock(side_effect=[st, st, []]))
        cam = self._make_camera(detector)

        with patch("backend.app.main.load_settings", return_value=self._make_settings()):
            for _ in range(3):
                cam._last_detection_time = 0.0
                cam._process_motion(self.frame)

        self.assertFalse(cam.motion_detected)
        self.assertFalse(cam.recording)
        self.assertIsNone(cam.recording_type)
        cam.stop()

    def test_motion_timeout_clears_even_with_skipped_detection_frames(self):
        obs = [
            _make_landmarks(0.0, 0.0),
            _make_landmarks(0.2, 0.2),
            _make_landmarks(0.4, 0.4),
        ]
        detector = MagicMock(detect=MagicMock(side_effect=[[person] for person in obs]))
        cam = self._make_camera(detector)

        with patch("backend.app.main.load_settings", return_value=self._make_settings(stop_recording_after_seconds=1)):
            for _ in range(3):
                cam._last_detection_time = 0.0
                cam._process_motion(self.frame)
            self.assertTrue(cam.motion_detected)
            cam._last_motion_time = time.time() - 2.0
            cam._last_detection_time = time.time()
            cam._process_motion(self.frame)

        self.assertFalse(cam.motion_detected)
        self.assertFalse(cam.recording)
        cam.stop()

    def test_disabling_motion_resets_analyzer_and_stops_motion_recording(self):
        obs = [
            _make_landmarks(0.0, 0.0),
            _make_landmarks(0.2, 0.2),
            _make_landmarks(0.4, 0.4),
        ]
        detector = MagicMock(detect=MagicMock(side_effect=[[person] for person in obs]))
        cam = self._make_camera(detector)

        with patch("backend.app.main.load_settings", return_value=self._make_settings()):
            for _ in range(3):
                cam._last_detection_time = 0.0
                cam._process_motion(self.frame)
            self.assertTrue(cam.recording)

        disabled = self._make_settings(motion_detection_enabled=False)
        with patch("backend.app.main.load_settings", return_value=disabled):
            cam._process_motion(self.frame)

        self.assertFalse(cam.motion_detected)
        self.assertFalse(cam.recording)
        self.assertEqual(cam.detector_status, "disabled")
        self.assertIsNone(cam._detector)
        detector.close.assert_called_once()
        self.assertEqual(cam._analyzer._prev_observations, [])
        cam.stop()

    def test_missing_model_sets_error_status_and_manual_recording_still_works(self):
        cam = self._make_camera()
        cam.status = "online"

        with patch.dict("os.environ", {"POSE_MODEL_PATH": "/nonexistent/model.task"}):
            with patch("backend.app.main.load_settings", return_value=self._make_settings()):
                cam._process_motion(self.frame)

        self.assertEqual(cam.detector_status, "error")
        self.assertIn("not found", cam.detector_error.lower())
        self.assertFalse(cam.motion_detected)
        self.assertTrue(cam._detector_failed)

        with patch("backend.app.main.PoseDetector") as mock_cls:
            with patch("backend.app.main.load_settings", return_value=self._make_settings()):
                cam._process_motion(self.frame)
            mock_cls.assert_not_called()

        self.assertTrue(cam.start_manual_recording())
        self.assertTrue(cam.recording)
        self.assertEqual(cam.recording_type, "manual")
        cam.stop_manual_recording()
        self.assertFalse(cam.recording)
        cam.stop()

    def test_inference_failure_stops_motion_recording_and_sets_error_without_retry_loop(self):
        obs = [
            _make_landmarks(0.0, 0.0),
            _make_landmarks(0.2, 0.2),
            _make_landmarks(0.4, 0.4),
        ]
        detector = MagicMock(detect=MagicMock(side_effect=[[person] for person in obs] + [RuntimeError("Metal error")]))
        cam = self._make_camera(detector)

        with patch("backend.app.main.load_settings", return_value=self._make_settings()):
            for _ in range(3):
                cam._last_detection_time = 0.0
                cam._process_motion(self.frame)
            self.assertTrue(cam.recording)

            cam._last_detection_time = 0.0
            cam._process_motion(self.frame)

        self.assertEqual(cam.detector_status, "error")
        self.assertIn("Metal error", cam.detector_error)
        self.assertFalse(cam.recording)
        self.assertTrue(cam._detector_failed)

        with patch("backend.app.main.load_settings", return_value=self._make_settings()):
            cam._last_detection_time = 0.0
            cam._process_motion(self.frame)
        self.assertEqual(detector.detect.call_count, 4)

        disabled = self._make_settings(motion_detection_enabled=False)
        with patch("backend.app.main.load_settings", return_value=disabled):
            cam._process_motion(self.frame)
        self.assertFalse(cam._detector_failed)
        self.assertEqual(cam.detector_status, "disabled")
        cam.stop()

    def test_thread_shutdown_timeout_retains_live_handle_and_refuses_overlapping_start(self):
        cam = CameraManager()
        thread = MagicMock(is_alive=MagicMock(return_value=True))
        cam._thread, cam._running = thread, True
        cap = MagicMock()
        cam._cap = cap

        cam.stop()
        self.assertFalse(cam._running)
        self.assertIs(cam._thread, thread)
        cap.release.assert_not_called()

        with patch.dict("os.environ", {"MOCK_CAMERA": "true"}), patch("backend.app.main.load_settings", return_value=self._make_settings()):
            self.assertFalse(cam.start())

        thread.is_alive.return_value = False
        with patch.dict("os.environ", {"MOCK_CAMERA": "true"}), patch("backend.app.main.load_settings", return_value=self._make_settings()):
            self.assertTrue(cam.start())
            cap.release.assert_called_once()
        cam.stop()

    def test_camera_status_includes_detector_fields(self):
        global_camera.detector_status = "disabled"
        global_camera.detector_error = None

        with patch("backend.app.main.load_settings", return_value=self._make_settings()):
            s1 = asyncio.run(camera_status())
            self.assertEqual(s1["detector_status"], "disabled")
            self.assertIsNone(s1["detector_error"])

            global_camera.detector_status = "error"
            global_camera.detector_error = "Model file missing"
            s2 = asyncio.run(camera_status())
            self.assertEqual(s2["detector_status"], "error")
            self.assertEqual(s2["detector_error"], "Model file missing")

            global_camera.detector_status = "ready"
            global_camera.detector_error = None
            s3 = asyncio.run(camera_status())
            self.assertEqual(s3["detector_status"], "ready")
            self.assertIsNone(s3["detector_error"])


if __name__ == "__main__":
    unittest.main()
