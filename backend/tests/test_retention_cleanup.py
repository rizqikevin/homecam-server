import asyncio
import importlib
import json
import os
import sys
import tempfile
import time
import types
import unittest


class FakeBaseModel:
    def __init__(self, **kwargs):
        fields = getattr(self, "__annotations__", {})
        self._set_fields = set(kwargs)
        for name in fields:
            if name in kwargs:
                value = kwargs[name]
            elif hasattr(type(self), name):
                value = getattr(type(self), name)
            else:
                value = None
            setattr(self, name, value)

    def model_dump(self, exclude_unset=False):
        fields = self._set_fields if exclude_unset else self.__annotations__
        return {name: getattr(self, name) for name in fields}

    def model_dump_json(self, indent=None):
        return json.dumps(self.model_dump(), indent=indent)


class FakeHTTPException(Exception):
    def __init__(self, status_code, detail):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class FakeFastAPI:
    def __init__(self, *args, **kwargs):
        pass

    def add_middleware(self, *args, **kwargs):
        pass

    def get(self, *args, **kwargs):
        return self._decorator

    def post(self, *args, **kwargs):
        return self._decorator

    def patch(self, *args, **kwargs):
        return self._decorator

    def delete(self, *args, **kwargs):
        return self._decorator

    def _decorator(self, func):
        return func


def install_dependency_stubs():
    fastapi = types.ModuleType("fastapi")
    fastapi.FastAPI = FakeFastAPI
    fastapi.HTTPException = FakeHTTPException
    fastapi.Query = lambda default=None, **kwargs: default
    fastapi.Response = object
    fastapi.Path = lambda default=None, **kwargs: default
    sys.modules["fastapi"] = fastapi

    middleware = types.ModuleType("fastapi.middleware")
    cors = types.ModuleType("fastapi.middleware.cors")
    cors.CORSMiddleware = object
    sys.modules["fastapi.middleware"] = middleware
    sys.modules["fastapi.middleware.cors"] = cors

    responses = types.ModuleType("fastapi.responses")
    responses.JSONResponse = dict
    responses.StreamingResponse = object
    responses.FileResponse = object
    sys.modules["fastapi.responses"] = responses

    pydantic = types.ModuleType("pydantic")
    pydantic.BaseModel = FakeBaseModel
    pydantic.Field = lambda default=None, **kwargs: default
    sys.modules["pydantic"] = pydantic

    cv2 = types.ModuleType("cv2")
    cv2.VideoCapture = object
    cv2.VideoWriter = object
    sys.modules["cv2"] = cv2

    numpy = types.ModuleType("numpy")
    numpy.ndarray = object
    sys.modules["numpy"] = numpy


def import_main_module():
    install_dependency_stubs()
    sys.modules.pop("backend.app.main", None)
    return importlib.import_module("backend.app.main")


class RetentionCleanupTests(unittest.TestCase):
    def test_cleanup_old_recordings_skips_raw_conversion_files(self):
        main = import_main_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            old_final = os.path.join(tmpdir, "manual_20260101.mp4")
            old_raw = os.path.join(tmpdir, "manual_20260101_raw.mp4")
            new_final = os.path.join(tmpdir, "manual_today.mp4")

            for path in (old_final, old_raw, new_final):
                with open(path, "wb") as f:
                    f.write(b"video")

            old_mtime = time.time() - (3 * 24 * 3600)
            os.utime(old_final, (old_mtime, old_mtime))
            os.utime(old_raw, (old_mtime, old_mtime))

            main.cleanup_old_recordings(tmpdir, max_days=1)

            self.assertFalse(os.path.exists(old_final))
            self.assertTrue(os.path.exists(old_raw))
            self.assertTrue(os.path.exists(new_final))

    def test_patch_settings_runs_cleanup_when_retention_changes(self):
        main = import_main_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = os.path.join(tmpdir, "settings.json")
            recordings_dir = os.path.join(tmpdir, "recordings")
            os.mkdir(recordings_dir)
            current = main.Settings(recordings_dir=recordings_dir, max_recording_days=7)
            with open(settings_path, "w") as f:
                f.write(current.model_dump_json(indent=2))

            cleanup_calls = []
            main.SETTINGS_PATH = settings_path
            main.cleanup_old_recordings = lambda path, days: cleanup_calls.append((path, days))
            main.camera = types.SimpleNamespace(status="online", stop=lambda: None, start=lambda: True)

            result = asyncio.run(
                main.patch_settings(main.SettingsPatch(max_recording_days=2))
            )

            self.assertEqual(result.max_recording_days, 2)
            self.assertEqual(cleanup_calls, [(recordings_dir, 2)])

    def test_patch_settings_rejects_invalid_retention_days(self):
        main = import_main_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = os.path.join(tmpdir, "settings.json")
            current = main.Settings(recordings_dir=tmpdir, max_recording_days=7)
            with open(settings_path, "w") as f:
                f.write(current.model_dump_json(indent=2))

            main.SETTINGS_PATH = settings_path
            with self.assertRaises(FakeHTTPException) as ctx:
                asyncio.run(main.patch_settings(main.SettingsPatch(max_recording_days=0)))

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail, "Max recording days must be between 1 and 365")

    def test_patch_settings_rejects_fps_above_camera_limit(self):
        main = import_main_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = os.path.join(tmpdir, "settings.json")
            current = main.Settings(recordings_dir=tmpdir, fps=15)
            with open(settings_path, "w") as f:
                f.write(current.model_dump_json(indent=2))

            main.SETTINGS_PATH = settings_path
            with self.assertRaises(FakeHTTPException) as ctx:
                asyncio.run(main.patch_settings(main.SettingsPatch(fps=31)))

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail, "FPS must be between 1 and 30")

    def test_patch_settings_accepts_1080p_at_30_fps(self):
        main = import_main_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = os.path.join(tmpdir, "settings.json")
            current = main.Settings(recordings_dir=tmpdir, width=640, height=480, fps=15)
            with open(settings_path, "w") as f:
                f.write(current.model_dump_json(indent=2))

            main.SETTINGS_PATH = settings_path
            main.camera = types.SimpleNamespace(status="offline", stop=lambda: None, start=lambda: True)
            result = asyncio.run(
                main.patch_settings(main.SettingsPatch(width=1920, height=1080, fps=30))
            )

        self.assertEqual(result.width, 1920)
        self.assertEqual(result.height, 1080)
        self.assertEqual(result.fps, 30)


if __name__ == "__main__":
    unittest.main()
