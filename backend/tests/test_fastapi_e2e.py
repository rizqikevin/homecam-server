"""End-to-end FastAPI API tests with TestClient and mock camera."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

import backend.app.main as main


class TestFastAPIEndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.recordings_dir = Path(self.tmpdir.name) / "recordings"
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        self.settings_path = Path(self.tmpdir.name) / "settings.json"

        self.orig_settings_path = main.SETTINGS_PATH
        main.SETTINGS_PATH = str(self.settings_path)

        # Initial clean settings
        s = main.Settings(
            recordings_dir=str(self.recordings_dir),
            motion_detection_enabled=False,
            auto_record_enabled=False,
        )
        main.save_settings(s)
        self.client = TestClient(main.app, raise_server_exceptions=False)

    def tearDown(self):
        main.SETTINGS_PATH = self.orig_settings_path
        self.tmpdir.cleanup()

    def test_health_endpoint(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("uptime_seconds", data)

    def test_camera_status_fields_when_offline(self):
        resp = self.client.get("/api/camera/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("detector_status", data)
        self.assertIn("detector_error", data)
        self.assertIn("status", data)
        self.assertIn("motion_detected", data)

    def test_detector_error_visible_while_camera_online_and_manual_recording_works(self):
        with patch.dict(os.environ, {"MOCK_CAMERA": "true", "POSE_MODEL_PATH": "/nonexistent/model.task"}):
            main.camera.stop()
            start_resp = self.client.post("/api/camera/start")
            self.assertEqual(start_resp.status_code, 200)

            # Enable motion detection to trigger detector init error
            patch_resp = self.client.patch("/api/settings", json={"motion_detection_enabled": True})
            self.assertEqual(patch_resp.status_code, 200)

            # Wait briefly for capture thread to attempt detector init
            import time
            for _ in range(20):
                time.sleep(0.05)
                status_resp = self.client.get("/api/camera/status")
                data = status_resp.json()
                if data.get("detector_status") == "error":
                    break

            status_resp = self.client.get("/api/camera/status")
            self.assertEqual(status_resp.status_code, 200)
            status_data = status_resp.json()

            # Camera online, detector in error, error message visible
            self.assertTrue(status_data["online"])
            self.assertEqual(status_data["detector_status"], "error")
            self.assertIsNotNone(status_data["detector_error"])
            self.assertIn("not found", status_data["detector_error"].lower())

            # Manual recording still works despite detector error
            rec_start = self.client.post("/api/recordings/start")
            self.assertEqual(rec_start.status_code, 200)
            rec_data = rec_start.json()
            self.assertIn("Manual recording started", rec_data["message"])

            # Verify camera reports recording active
            status_during_rec = self.client.get("/api/camera/status").json()
            self.assertTrue(status_during_rec["recording"])

            # Stop manual recording
            rec_stop = self.client.post("/api/recordings/stop")
            self.assertEqual(rec_stop.status_code, 200)

            main.camera.stop()


if __name__ == "__main__":
    unittest.main()
