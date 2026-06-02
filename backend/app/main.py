"""
HomeCam Server — Backend API
Lightweight home CCTV system using FastAPI and OpenCV.
"""

import logging
import threading
import time
import os
import json
import glob
import math
import subprocess
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional, Literal, List
import numpy as np

import cv2
from fastapi import FastAPI, HTTPException, Query, Response, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("homecam")

def convert_to_h264(raw_path: str, final_path: str):
    logger.info(f"Background thread starting conversion: {raw_path} -> {final_path}")
    if not os.path.exists(raw_path) or os.path.getsize(raw_path) == 0:
        logger.error(f"Cannot convert: raw file {raw_path} does not exist or is empty")
        if os.path.exists(final_path):
            try:
                os.remove(final_path)
            except Exception:
                pass
        return

    try:
        cmd = [
            "ffmpeg", "-y",
            "-i", raw_path,
            "-vcodec", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "ultrafast",
            "-loglevel", "error",
            final_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0 and os.path.exists(final_path) and os.path.getsize(final_path) > 0:
            logger.info(f"Successfully converted recording to H.264 MP4: {final_path}")
            try:
                os.remove(raw_path)
            except Exception as e:
                logger.warning(f"Failed to remove raw file {raw_path}: {e}")
        else:
            logger.error(f"FFmpeg conversion failed (exit code {result.returncode}): {result.stderr}")
            if os.path.exists(raw_path):
                logger.info(f"Fallback: keeping raw recording file as {final_path}")
                if os.path.exists(final_path):
                    try:
                        os.remove(final_path)
                    except Exception:
                        pass
                os.rename(raw_path, final_path)
    except Exception as e:
        logger.error(f"Error during video conversion: {e}")
        if os.path.exists(raw_path):
            logger.info(f"Fallback: keeping raw recording file as {final_path}")
            if os.path.exists(final_path):
                try:
                    os.remove(final_path)
                except Exception:
                    pass
            os.rename(raw_path, final_path)

# ---------------------------------------------------------------------------
# Settings Management
# ---------------------------------------------------------------------------
SETTINGS_PATH = "/recordings/settings.json"

class Settings(BaseModel):
    camera_device: str = "/dev/video0"
    width: int = 640
    height: int = 480
    fps: int = 15
    motion_detection_enabled: bool = False
    auto_record_enabled: bool = False
    detection_sensitivity: Literal["low", "medium", "high"] = "medium"
    motion_threshold: int = 5000
    stop_recording_after_seconds: int = 10
    recording_clip_seconds: int = 10
    recordings_dir: str = "/recordings"
    max_recording_days: int = 7

class SettingsPatch(BaseModel):
    camera_device: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[int] = None
    motion_detection_enabled: Optional[bool] = None
    auto_record_enabled: Optional[bool] = None
    detection_sensitivity: Optional[Literal["low", "medium", "high"]] = None
    motion_threshold: Optional[int] = None
    stop_recording_after_seconds: Optional[int] = None
    recording_clip_seconds: Optional[int] = None
    recordings_dir: Optional[str] = None
    max_recording_days: Optional[int] = None

def load_settings() -> Settings:
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r") as f:
                data = json.load(f)
                return Settings(**data)
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")
    
    # Save default settings
    s = Settings()
    save_settings(s)
    return s

def save_settings(s: Settings):
    try:
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
        with open(SETTINGS_PATH, "w") as f:
            f.write(s.model_dump_json(indent=2))
    except Exception as e:
        logger.error(f"Failed to save settings: {e}")

# ---------------------------------------------------------------------------
# Storage Cleanup Utility
# ---------------------------------------------------------------------------
def cleanup_old_recordings(recordings_dir: str, max_days: int):
    try:
        if not os.path.exists(recordings_dir):
            return
        now = time.time()
        max_seconds = max_days * 24 * 3600
        for f in os.listdir(recordings_dir):
            if f.endswith((".mp4", ".avi", ".mkv", ".mov")):
                filepath = os.path.join(recordings_dir, f)
                file_age = now - os.path.getmtime(filepath)
                if file_age > max_seconds:
                    logger.info(f"Cleaning up old recording: {f} (age: {file_age / 3600:.1f} hours)")
                    os.remove(filepath)
    except Exception as e:
        logger.error(f"Failed to clean up old recordings: {e}")

# ---------------------------------------------------------------------------
# Camera Manager
# ---------------------------------------------------------------------------
class CameraManager:
    """Manages the USB webcam lifecycle, motion detection, and recording."""

    def __init__(self) -> None:
        self._cap: cv2.VideoCapture | None = None
        self._lock = threading.Lock()
        self._frame: bytes | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        
        self.status = "offline"
        self.error: str | None = None
        self.started_at: datetime | None = None
        
        # Camera specs set dynamically from settings
        self.device = "/dev/video0"
        self.width = 640
        self.height = 480
        self.fps = 15
        self.recordings_dir = "/recordings"
        
        # Motion detection fields
        self.motion_detected = False
        self._prev_frame: np.ndarray | None = None
        self._last_motion_time = 0.0
        
        # Recording fields
        self._writer: cv2.VideoWriter | None = None
        self.recording = False
        self.recording_type: Literal["motion", "manual"] | None = None
        self.recording_filename: str | None = None
        self._recording_raw_filepath: str | None = None
        
        # Mock mode fallback (useful for developer containers)
        self._mock = False

    def start(self) -> bool:
        """Open the camera (or mock) and begin capturing frames."""
        if self._running:
            logger.info("Camera already running")
            return True

        settings = load_settings()
        self.device = settings.camera_device
        self.width = settings.width
        self.height = settings.height
        self.fps = settings.fps
        self.recordings_dir = settings.recordings_dir

        # Run age cleanup on boot
        cleanup_old_recordings(self.recordings_dir, settings.max_recording_days)

        mock_env = os.environ.get("MOCK_CAMERA", "false").lower() == "true"

        if mock_env:
            logger.info("MOCK_CAMERA is enabled. Running in mock mode.")
            self._mock = True
        else:
            self._mock = False
            try:
                cap = cv2.VideoCapture(self.device)
                if not cap.isOpened():
                    self.status = "error"
                    self.error = f"Cannot open camera device {self.device}"
                    logger.error(self.error)
                    return False

                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                cap.set(cv2.CAP_PROP_FPS, self.fps)
                self._cap = cap
            except Exception as exc:
                self.status = "error"
                self.error = str(exc)
                logger.error("Failed to start camera device: %s", exc)
                return False

        self._running = True
        self.status = "online"
        self.error = None
        self.started_at = datetime.now(timezone.utc)

        # Reset capture loop fields
        self.motion_detected = False
        self._prev_frame = None
        self._writer = None
        self.recording = False
        self.recording_type = None
        self.recording_filename = None

        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

        logger.info("Camera started on %s (%dx%d @ %d FPS)", self.device, self.width, self.height, self.fps)
        return True

    def stop(self) -> None:
        """Stop capturing, release resources, and close recording stream."""
        self._running = False
        
        # Safety: Close active VideoWriter
        if self.recording:
            self._stop_recording()

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
        """Return the latest JPEG-encoded frame bytes."""
        with self._lock:
            return self._frame

    def generate_mjpeg(self):
        """Yield MJPEG multipart frames for HTTP streaming."""
        while self._running:
            frame = self.get_frame()
            if frame is not None:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                )
            time.sleep(1 / self.fps)

    # -- Internal Operations -------------------------------------------------

    def _capture_loop(self) -> None:
        """Background loop reading frames, writing video, and running motion logic."""
        while self._running:
            frame = None
            if self._mock:
                # 1. Create simulated mock test card
                frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                cv2.putText(frame, f"HomeCam MOCK: {now_str}", (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (241, 245, 249), 2)
                cv2.putText(frame, f"Device: {self.device} (Mock)", (30, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (148, 163, 184), 1)
                
                # Draw simple animations for visual verification
                t = time.time()
                cx = int(self.width / 2 + math.sin(t * 1.5) * (self.width / 4))
                cy = int(self.height / 2 + math.cos(t * 2.2) * (self.height / 5))
                cv2.circle(frame, (cx, cy), 25, (59, 130, 246), -1) # Accent bouncing circle
                
                # Mock moving rectangle (triggers motion detection simulator periodically)
                settings = load_settings()
                if settings.motion_detection_enabled:
                    if int(t) % 6 < 2:
                        cv2.rectangle(frame, (80, 150), (160, 230), (34, 197, 94), -1)
                        
                time.sleep(1 / self.fps)
            else:
                if self._cap is None:
                    break
                ret, frame = self._cap.read()
                if not ret:
                    logger.warning("Failed to read frame from camera")
                    time.sleep(0.1)
                    continue

            # 2. Process OpenCV motion differencing
            self._process_motion(frame)

            # 3. Write active frames
            with self._lock:
                if self._writer is not None:
                    try:
                        self._writer.write(frame)
                    except Exception as e:
                        logger.error(f"VideoWriter write failed: {e}")

            # 4. Generate MJPEG JPEG Frame
            _, jpeg = cv2.imencode(".jpg", frame)
            with self._lock:
                self._frame = jpeg.tobytes()

            if not self._mock:
                time.sleep(1 / self.fps)

        logger.info("Capture loop exited")

    def _process_motion(self, frame: np.ndarray) -> None:
        """Run OpenCV lightweight motion differencing and toggle auto-recording."""
        settings = load_settings()
        if not settings.motion_detection_enabled:
            self.motion_detected = False
            self._prev_frame = None
            if self.recording and self.recording_type == "motion":
                self._stop_recording()
            return

        # Convert to grayscale & blur
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if self._prev_frame is None:
            self._prev_frame = gray
            return

        # Frame difference & threshold
        frame_delta = cv2.absdiff(self._prev_frame, gray)
        thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)
        non_zero = cv2.countNonZero(thresh)

        self._prev_frame = gray

        # Motion threshold match
        threshold = settings.motion_threshold
        if non_zero > threshold:
            if not self.motion_detected:
                logger.info(f"Motion alert triggered: non-zero pixels {non_zero} > {threshold}")
            self.motion_detected = True
            self._last_motion_time = time.time()

            if settings.auto_record_enabled and not self.recording:
                self._start_recording("motion")
        else:
            if self.motion_detected:
                if time.time() - self._last_motion_time > settings.stop_recording_after_seconds:
                    logger.info("Motion alert cleared (timeout reached)")
                    self.motion_detected = False
                    
                    if self.recording and self.recording_type == "motion":
                        self._stop_recording()

    def _start_recording(self, r_type: Literal["motion", "manual"]) -> bool:
        """Initialize VideoWriter stream to output an MP4 file."""
        with self._lock:
            if self.recording:
                logger.warning("Rejecting start recording: already recording")
                return False

            now_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"{now_str}_{r_type}.mp4"
            raw_filename = f"{now_str}_{r_type}_raw.mp4"
            raw_filepath = os.path.join(self.recordings_dir, raw_filename)

            # Ensure recordings dir exists
            os.makedirs(self.recordings_dir, exist_ok=True)

            try:
                # Use mp4v which is 100% supported by OpenCV out of the box
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                self._writer = cv2.VideoWriter(
                    raw_filepath, fourcc, float(self.fps), (self.width, self.height)
                )
                if not self._writer.isOpened():
                    logger.error(f"Failed to open VideoWriter with mp4v codec for path {raw_filepath}")
                    self._writer = None
                    self.recording = False
                    self.recording_type = None
                    self.recording_filename = None
                    return False

                self.recording = True
                self.recording_type = r_type
                self.recording_filename = filename
                self._recording_raw_filepath = raw_filepath
                logger.info(f"Started {r_type} VideoWriter stream output (raw): {raw_filepath}")
                return True
            except Exception as e:
                logger.error(f"Failed to start VideoWriter stream: {e}")
                self._writer = None
                self.recording = False
                self.recording_type = None
                self.recording_filename = None
                self._recording_raw_filepath = None
                return False

    def _stop_recording(self) -> None:
        """Stop VideoWriter stream and release file handles."""
        with self._lock:
            if not self.recording:
                return

            logger.info(f"Stopping VideoWriter stream for {self.recording_filename}")
            if self._writer is not None:
                try:
                    self._writer.release()
                except Exception as e:
                    logger.error(f"Failed to release VideoWriter: {e}")
                self._writer = None
            
            raw_path = self._recording_raw_filepath
            final_path = os.path.join(self.recordings_dir, self.recording_filename)
            
            if raw_path:
                threading.Thread(
                    target=convert_to_h264,
                    args=(raw_path, final_path),
                    daemon=True
                ).start()

            self.recording = False
            self.recording_type = None
            self.recording_filename = None
            self._recording_raw_filepath = None

    def start_manual_recording(self) -> bool:
        return self._start_recording("manual")

    def stop_manual_recording(self) -> None:
        if self.recording and self.recording_type == "manual":
            self._stop_recording()


# Singleton Instance
camera = CameraManager()

# ---------------------------------------------------------------------------
# App Lifespan
# ---------------------------------------------------------------------------
_app_start_time: float = 0.0

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Load settings and start the camera on server start, stop on shutdown."""
    global _app_start_time
    _app_start_time = time.time()
    logger.info("HomeCam Server starting up …")
    
    # Pre-load settings
    load_settings()
    
    camera.start()
    yield
    logger.info("HomeCam Server shutting down …")
    camera.stop()


# ---------------------------------------------------------------------------
# FastAPI Router App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="HomeCam Server",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helpers
def get_size_label(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"

# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    """Health check with uptime metrics."""
    uptime = round(time.time() - _app_start_time, 1) if _app_start_time else 0
    return {
        "status": "ok",
        "uptime_seconds": uptime,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/camera/status")
async def camera_status():
    """Return status updates for live stream and detectors."""
    settings = load_settings()
    
    # Get actual recordings count in the output volume
    count = 0
    if os.path.exists(settings.recordings_dir):
        count = len([
            f for f in os.listdir(settings.recordings_dir)
            if f.endswith((".mp4", ".avi", ".mkv", ".mov")) and "_raw" not in f
        ])
        
    return {
        "status": camera.status,
        "online": camera.status == "online",
        "error": camera.error,
        "started_at": camera.started_at.isoformat() if camera.started_at else None,
        "device": camera.device,
        "resolution": f"{camera.width}x{camera.height}",
        "fps": camera.fps,
        "motion_detection_enabled": settings.motion_detection_enabled,
        "motion_detected": camera.motion_detected,
        "auto_record_enabled": settings.auto_record_enabled,
        "recording": camera.recording,
        "recording_filename": camera.recording_filename,
        "recordings_count": count
    }


@app.post("/api/camera/start")
async def camera_start():
    """Activate the camera capture thread."""
    ok = camera.start()
    if ok:
        return {"message": "Camera started"}
    return JSONResponse(
        status_code=503,
        content={"message": "Failed to start camera", "error": camera.error},
    )


@app.post("/api/camera/stop")
async def camera_stop():
    """Deactivate the camera capture thread."""
    camera.stop()
    return {"message": "Camera stopped"}


@app.get("/api/camera/stream")
async def camera_stream():
    """MJPEG live camera visual stream feed."""
    if camera.status != "online":
        return JSONResponse(
            status_code=503,
            content={"message": "Camera is not online", "status": camera.status},
        )
    return StreamingResponse(
        camera.generate_mjpeg(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


# -- Settings Endpoints ---------------------------------------------------

@app.get("/api/settings")
async def get_settings():
    """Return persistent configuration parameters."""
    return load_settings()


@app.patch("/api/settings")
async def patch_settings(payload: SettingsPatch):
    """Modify selected settings fields and reload camera state if required."""
    current = load_settings()
    updates = payload.model_dump(exclude_unset=True)

    # Sensitivity mapping
    if "detection_sensitivity" in updates:
        sensitivity = updates["detection_sensitivity"]
        if sensitivity == "low":
            updates["motion_threshold"] = 9000
        elif sensitivity == "medium":
            updates["motion_threshold"] = 5000
        elif sensitivity == "high":
            updates["motion_threshold"] = 2500

    # Validation
    if "width" in updates and updates["width"] <= 0:
        raise HTTPException(status_code=400, detail="Width must be greater than 0")
    if "height" in updates and updates["height"] <= 0:
        raise HTTPException(status_code=400, detail="Height must be greater than 0")
    if "fps" in updates and (updates["fps"] <= 0 or updates["fps"] > 60):
        raise HTTPException(status_code=400, detail="FPS must be between 1 and 60")
    if "motion_threshold" in updates and updates["motion_threshold"] <= 0:
        raise HTTPException(status_code=400, detail="Motion threshold must be greater than 0")

    # Apply updates
    for key, val in updates.items():
        setattr(current, key, val)

    save_settings(current)

    # If stream specification parameters changed, restart camera if online
    stream_params_changed = any(k in updates for k in ["camera_device", "width", "height", "fps"])
    if stream_params_changed and camera.status == "online":
        logger.info("Restarting camera thread to apply configuration updates")
        camera.stop()
        camera.start()

    return current


# -- Recording Endpoints --------------------------------------------------

@app.post("/api/recordings/start")
async def manual_record_start():
    """Trigger manual recording output."""
    if camera.status != "online":
        raise HTTPException(status_code=400, detail="Camera is offline")
    
    if camera.recording:
        return JSONResponse(
            status_code=400,
            content={"message": "Already recording", "filename": camera.recording_filename}
        )

    ok = camera.start_manual_recording()
    if ok:
        return {"message": "Manual recording started", "filename": camera.recording_filename}
    raise HTTPException(status_code=500, detail="Failed to start recording")


@app.post("/api/recordings/stop")
async def manual_record_stop():
    """Deactivate manual recording output."""
    if not camera.recording or camera.recording_type != "manual":
        raise HTTPException(status_code=400, detail="No active manual recording stream")
        
    filename = camera.recording_filename
    camera.stop_manual_recording()
    return {"message": "Manual recording stopped", "filename": filename}


@app.get("/api/recordings")
async def list_recordings():
    """Scan and list recordings inside the recordings directory."""
    settings = load_settings()
    if not os.path.exists(settings.recordings_dir):
        return {"items": [], "total": 0}

    # Retrieve all supported video files
    extensions = ("*.mp4", "*.avi", "*.mkv", "*.mov")
    files = []
    for ext in extensions:
        files.extend(glob.glob(os.path.join(settings.recordings_dir, ext)))

    # Sort files by modification time (newest first)
    files.sort(key=os.path.getmtime, reverse=True)

    items = []
    for filepath in files:
        filename = os.path.basename(filepath)
        if "_raw" in filename:
            continue
        size_bytes = os.path.getsize(filepath)
        mtime = os.path.getmtime(filepath)
        created_at_dt = datetime.fromtimestamp(mtime, timezone.utc)

        # Detect category classification
        if "motion" in filename.lower():
            rec_type = "motion"
        elif "manual" in filename.lower():
            rec_type = "manual"
        elif "schedule" in filename.lower():
            rec_type = "schedule"
        else:
            rec_type = "unknown"

        items.append({
            "filename": filename,
            "url": f"/api/recordings/{filename}",
            "download_url": f"/api/recordings/{filename}?download=true",
            "size_bytes": size_bytes,
            "size_label": get_size_label(size_bytes),
            "created_at": created_at_dt.isoformat(),
            "duration_seconds": None,  # Optional metadata
            "type": rec_type
        })

    return {
        "items": items,
        "total": len(items)
    }


@app.get("/api/recordings/{filename}")
async def get_recording_file(
    filename: str = Path(..., description="The name of the recording file"),
    download: bool = Query(False, description="Forces attachment download headers")
):
    """Retrieve video files securely with browser playback (range) and download support."""
    # Prevent directory traversal attacks
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Path traversal attempt blocked")

    settings = load_settings()
    filepath = os.path.join(settings.recordings_dir, filename)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Recording file not found")

    headers = {}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'

    return FileResponse(filepath, headers=headers)


@app.delete("/api/recordings/{filename}")
async def delete_recording_file(
    filename: str = Path(..., description="The name of the recording file to delete")
):
    """Securely delete a specific recording file from the disk."""
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Path traversal attempt blocked")

    settings = load_settings()
    filepath = os.path.join(settings.recordings_dir, filename)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Recording file not found")

    try:
        os.remove(filepath)
        logger.info(f"Deleted recording: {filename}")
        return {"message": "Recording deleted", "filename": filename}
    except Exception as e:
        logger.error(f"Failed to delete recording {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")


# -- Server Info Endpoint -------------------------------------------------

@app.get("/api/server/info")
async def get_server_info():
    """Retrieve system diagnostics, storage specifications, and feature sets."""
    settings = load_settings()
    
    # Calculate storage capacity metrics
    total_size = 0
    count = 0
    if os.path.exists(settings.recordings_dir):
        extensions = ("*.mp4", "*.avi", "*.mkv", "*.mov")
        for ext in extensions:
            for f in glob.glob(os.path.join(settings.recordings_dir, ext)):
                if "_raw" in os.path.basename(f):
                    continue
                total_size += os.path.getsize(f)
                count += 1

    return {
        "api_base_url": "https://api.rizqikevin.my.id",
        "server_time": datetime.now(timezone.utc).isoformat(),
        "recordings_dir": settings.recordings_dir,
        "camera_device": settings.camera_device,
        "storage": {
            "recordings_count": count,
            "total_size_bytes": total_size,
            "total_size_label": get_size_label(total_size)
        },
        "features": {
            "motion_detection": True,
            "auto_record": True,
            "manual_record": True,
            "pwa": True
        }
    }
