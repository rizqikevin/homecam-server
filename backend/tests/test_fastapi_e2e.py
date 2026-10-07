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
from backend.app.auth import AuthManager, hash_password


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
        self.auth_env = patch.dict(os.environ, {
            "HOMECAM_ADMIN_USERNAME": "test-admin",
            "HOMECAM_ADMIN_PASSWORD_HASH": hash_password("test-password-only"),
            "HOMECAM_ALLOWED_ORIGINS": "http://testserver",
            "HOMECAM_COOKIE_SECURE": "false",
        })
        self.auth_env.start()
        self.original_auth = main.auth
        main.auth = AuthManager()
        for middleware in main.app.user_middleware:
            if middleware.cls is main.AuthMiddleware:
                middleware.kwargs["auth"] = main.auth
            elif middleware.cls is main.CORSMiddleware:
                self.original_origins = middleware.kwargs["allow_origins"]
                middleware.kwargs["allow_origins"] = main.auth.origins
        main.app.middleware_stack = None
        self.client = TestClient(main.app, raise_server_exceptions=False)
        self.client.headers["Origin"] = "http://testserver"
        response = self.client.post("/api/auth/login", json={"username": "test-admin", "password": "test-password-only"})
        self.assertEqual(response.status_code, 200)

    def tearDown(self):
        self.client.close()
        main.auth = self.original_auth
        for middleware in main.app.user_middleware:
            if middleware.cls is main.AuthMiddleware:
                middleware.kwargs["auth"] = main.auth
            elif middleware.cls is main.CORSMiddleware:
                middleware.kwargs["allow_origins"] = self.original_origins
        main.app.middleware_stack = None
        self.auth_env.stop()
        main.SETTINGS_PATH = self.orig_settings_path
        self.tmpdir.cleanup()

    def test_anonymous_requests_cannot_reach_private_routes(self):
        self.client.cookies.clear()
        for method, path in [
            ("GET", "/api/camera/status"), ("GET", "/api/camera/stream"),
            ("POST", "/api/camera/start"), ("POST", "/api/camera/stop"),
            ("GET", "/api/settings"), ("PATCH", "/api/settings"),
            ("GET", "/api/recordings"), ("GET", "/api/recordings/private.mp4"),
            ("GET", "/api/recordings/private.mp4?download=true"),
            ("DELETE", "/api/recordings/private.mp4"),
            ("POST", "/api/recordings/start"), ("POST", "/api/recordings/stop"),
            ("GET", "/api/server/info"), ("GET", "/api/auth/session"),
            ("GET", "/docs"), ("GET", "/openapi.json"),
        ]:
            with self.subTest(path=path, method=method):
                response = self.client.request(method, path)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(self.client.get("/api/health").status_code, 200)

    def test_login_cookie_and_logout_revocation(self):
        old_cookie = self.client.cookies.get("homecam_session")
        response = self.client.post("/api/auth/login", json={"username": "test-admin", "password": "test-password-only"})
        cookie = response.headers["set-cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=strict", cookie)
        self.assertIn("Path=/api", cookie)
        self.assertFalse(main.auth.valid(old_cookie))
        token = self.client.cookies.get("homecam_session")
        self.assertEqual(self.client.get("/api/auth/session").json(), {"username": "test-admin"})
        self.assertEqual(self.client.post("/api/auth/logout").status_code, 200)
        self.assertFalse(main.auth.valid(token))
        self.assertEqual(self.client.get("/api/settings", headers={"Cookie": f"homecam_session={token}"}).status_code, 401)

    def test_expired_and_forged_sessions_are_rejected(self):
        with patch("backend.app.auth.time.monotonic", return_value=10**15):
            self.assertEqual(self.client.get("/api/settings").status_code, 401)
        self.assertEqual(self.client.get("/api/settings", headers={"Cookie": "homecam_session=forged"}).status_code, 401)

    def test_mutations_require_allowed_origin(self):
        for path in ["/api/auth/login", "/api/auth/logout", "/api/camera/start"]:
            response = self.client.post(path, headers={"Origin": "https://attacker.example"})
            self.assertEqual(response.status_code, 403)
        del self.client.headers["Origin"]
        self.assertEqual(self.client.post("/api/camera/stop").status_code, 403)

    def test_wrong_password_and_throttling(self):
        self.client.cookies.clear()
        for _ in range(9):
            response = self.client.post("/api/auth/login", json={"username": "test-admin", "password": "wrong"})
            self.assertEqual(response.status_code, 401)
            self.assertNotIn("set-cookie", response.headers)
        response = self.client.post("/api/auth/login", json={"username": "test-admin", "password": "test-password-only"})
        self.assertEqual(response.status_code, 429)

    def test_missing_configuration_fails_closed(self):
        main.auth.configured = False
        self.assertEqual(self.client.get("/api/settings").status_code, 503)
        self.assertEqual(self.client.post("/api/auth/login", json={"username": "test-admin", "password": "test-password-only"}).status_code, 503)
        self.assertEqual(self.client.get("/api/health").status_code, 200)

    def test_secure_cookie_and_cors(self):
        main.auth.secure = True
        response = self.client.post("/api/auth/login", json={"username": "test-admin", "password": "test-password-only"})
        self.assertIn("Secure", response.headers["set-cookie"])
        self.assertEqual(response.headers["access-control-allow-origin"], "http://testserver")
        self.assertEqual(response.headers["access-control-allow-credentials"], "true")
        response = self.client.options("/api/settings", headers={"Origin": "https://attacker.example", "Access-Control-Request-Method": "PATCH"})
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_stream_stops_when_session_is_revoked(self):
        token = self.client.cookies.get("homecam_session")

        def frames():
            yield b"first-frame"
            main.auth.revoke(token)
            yield b"private-frame-after-logout"

        with patch.object(main.camera, "status", "online"), patch.object(main.camera, "generate_mjpeg", side_effect=frames):
            response = self.client.get("/api/camera/stream")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"first-frame")
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_recording_playback_and_download_require_session(self):
        (self.recordings_dir / "private.mp4").write_bytes(b"private-video")
        for suffix in ["", "?download=true"]:
            response = self.client.get(f"/api/recordings/private.mp4{suffix}")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, b"private-video")
            self.assertEqual(response.headers["cache-control"], "no-store")
        self.client.post("/api/auth/logout")
        self.assertEqual(self.client.get("/api/recordings/private.mp4").status_code, 401)

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
