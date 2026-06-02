"""
HomeCam Server — Backend API
Lightweight home CCTV system using FastAPI and OpenCV.
"""

import logging
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import cv2
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("homecam")

# ---------------------------------------------------------------------------
# Camera Manager
# ---------------------------------------------------------------------------
CAMERA_DEVICE = "/dev/video0"
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 15


class CameraManager:
    """Manages the USB webcam lifecycle and frame capture."""

    def __init__(self) -> None:
        self._cap: cv2.VideoCapture | None = None
        self._lock = threading.Lock()
        self._frame: bytes | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self.status = "offline"
        self.error: str | None = None
        self.started_at: datetime | None = None

    # -- Public API ----------------------------------------------------------

    def start(self) -> bool:
        """Open the camera and begin capturing frames."""
        if self._running:
            logger.info("Camera already running")
            return True

        try:
            cap = cv2.VideoCapture(CAMERA_DEVICE)
            if not cap.isOpened():
                self.status = "error"
                self.error = f"Cannot open camera device {CAMERA_DEVICE}"
                logger.error(self.error)
                return False

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
            cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)

            self._cap = cap
            self._running = True
            self.status = "online"
            self.error = None
            self.started_at = datetime.now(timezone.utc)

            self._thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._thread.start()

            logger.info("Camera started on %s", CAMERA_DEVICE)
            return True

        except Exception as exc:
            self.status = "error"
            self.error = str(exc)
            logger.error("Failed to start camera: %s", exc)
            return False

    def stop(self) -> None:
        """Stop capturing and release the camera."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._frame = None
        self.status = "offline"
        self.started_at = None
        logger.info("Camera stopped")

    def get_frame(self) -> bytes | None:
        """Return the latest JPEG-encoded frame, or None."""
        with self._lock:
            return self._frame

    def generate_mjpeg(self):
        """Yield MJPEG multipart frames for streaming."""
        while self._running:
            frame = self.get_frame()
            if frame is not None:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                )
            time.sleep(1 / CAMERA_FPS)

    # -- Internal ------------------------------------------------------------

    def _capture_loop(self) -> None:
        """Background thread: continuously read frames from the camera."""
        while self._running and self._cap is not None:
            ret, frame = self._cap.read()
            if not ret:
                logger.warning("Failed to read frame from camera")
                time.sleep(0.1)
                continue

            _, jpeg = cv2.imencode(".jpg", frame)
            with self._lock:
                self._frame = jpeg.tobytes()

            time.sleep(1 / CAMERA_FPS)

        logger.info("Capture loop exited")


# Singleton
camera = CameraManager()

# ---------------------------------------------------------------------------
# App start-up time (for uptime calculation)
# ---------------------------------------------------------------------------
_app_start_time: float = 0.0

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Start camera on boot, stop on shutdown."""
    global _app_start_time
    _app_start_time = time.time()
    logger.info("HomeCam Server starting up …")
    camera.start()
    yield
    logger.info("HomeCam Server shutting down …")
    camera.stop()


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="HomeCam Server",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/api/health")
async def health():
    """Health check with uptime."""
    uptime = round(time.time() - _app_start_time, 1) if _app_start_time else 0
    return {
        "status": "ok",
        "uptime_seconds": uptime,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/camera/status")
async def camera_status():
    """Return current camera state."""
    return {
        "status": camera.status,
        "error": camera.error,
        "started_at": camera.started_at.isoformat() if camera.started_at else None,
        "device": CAMERA_DEVICE,
        "resolution": f"{CAMERA_WIDTH}x{CAMERA_HEIGHT}",
        "fps": CAMERA_FPS,
    }


@app.post("/api/camera/start")
async def camera_start():
    """Start the camera."""
    ok = camera.start()
    if ok:
        return {"message": "Camera started"}
    return JSONResponse(
        status_code=503,
        content={"message": "Failed to start camera", "error": camera.error},
    )


@app.post("/api/camera/stop")
async def camera_stop():
    """Stop the camera."""
    camera.stop()
    return {"message": "Camera stopped"}


@app.get("/api/camera/stream")
async def camera_stream():
    """MJPEG live stream."""
    if camera.status != "online":
        return JSONResponse(
            status_code=503,
            content={"message": "Camera is not online", "status": camera.status},
        )
    return StreamingResponse(
        camera.generate_mjpeg(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
