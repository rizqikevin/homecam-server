import { useEffect, useState, useRef } from "react";
import { useApp } from "../context/AppContext";
import { api } from "../api";

export default function Dashboard() {
  const {
    health,
    camera,
    backendOnline,
    cameraOnline,
    isRecording,
    motionDetected,
    triggerRefresh,
    loading,
    error,
  } = useApp();

  const [actionLoading, setActionLoading] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const recordingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Handle Recording Timer
  useEffect(() => {
    if (isRecording) {
      setRecordingSeconds(0);
      recordingIntervalRef.current = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
      }, 1000);
    } else {
      if (recordingIntervalRef.current) {
        clearInterval(recordingIntervalRef.current);
        recordingIntervalRef.current = null;
      }
      setRecordingSeconds(0);
    }

    return () => {
      if (recordingIntervalRef.current) {
        clearInterval(recordingIntervalRef.current);
      }
    };
  }, [isRecording]);

  const handleStartCamera = async () => {
    setActionLoading(true);
    try {
      await api.startCamera();
      await triggerRefresh();
    } catch {
      // Handled in Context
    } finally {
      setActionLoading(false);
    }
  };

  const handleStopCamera = async () => {
    setActionLoading(true);
    try {
      await api.stopCamera();
      await triggerRefresh();
    } catch {
      // Handled in Context
    } finally {
      setActionLoading(false);
    }
  };

  const toggleRecording = async () => {
    setActionLoading(true);
    try {
      if (isRecording) {
        await api.stopManualRecording();
      } else {
        await api.startManualRecording();
      }
      await triggerRefresh();
    } catch {
      // Error handling
    } finally {
      setActionLoading(false);
    }
  };

  const formatUptime = (seconds: number): string => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) return `${h}h ${m}m ${s}s`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
  };

  const formatTimer = (totalSeconds: number): string => {
    const m = Math.floor(totalSeconds / 60).toString().padStart(2, "0");
    const s = (totalSeconds % 60).toString().padStart(2, "0");
    return `${m}:${s}`;
  };

  if (loading) {
    return (
      <div className="page">
        <div className="loading-state">
          <div className="spinner" />
          <p>Connecting to HomeCam Server…</p>
        </div>
      </div>
    );
  }

  // Graceful Offline Fallback State
  if (!backendOnline) {
    return (
      <div className="page">
        <div className="offline-hero">
          <div className="offline-hero-icon">⚠️</div>
          <h2>CCTV Backend Offline</h2>
          <p>
            Could not connect to the HomeCam backend at the configured address.
            Please verify the server is running and accessible on your local network.
          </p>
          {error && <div className="error-banner">{error}</div>}
          <button className="btn btn-primary" onClick={triggerRefresh}>
            🔄 Retry Connection
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={`page ${isFullscreen ? "page-with-fullscreen" : ""}`}>
      <div className="page-header">
        <div className="title-area">
          <h1>Live Dashboard</h1>
          <p className="page-subtitle">Real-time CCTV feed and camera diagnostics</p>
        </div>
        {error && <div className="error-banner">{error}</div>}
      </div>

      {/* Main Status Grid */}
      <div className="status-grid">
        {/* Backend Status */}
        <div className={`status-card ${backendOnline ? "status-online" : "status-offline"}`}>
          <div className="status-icon">
            <span className={`dot ${backendOnline ? "dot-green" : "dot-red"}`} />
          </div>
          <div className="status-info">
            <span className="status-label">Backend</span>
            <span className="status-value">{backendOnline ? "Online" : "Offline"}</span>
          </div>
        </div>

        {/* Camera Status */}
        <div
          className={`status-card ${
            cameraOnline
              ? "status-online"
              : camera?.status === "error"
              ? "status-error"
              : "status-offline"
          }`}
        >
          <div className="status-icon">
            <span
              className={`dot ${
                cameraOnline
                  ? "dot-green"
                  : camera?.status === "error"
                  ? "dot-red"
                  : "dot-grey"
              }`}
            />
          </div>
          <div className="status-info">
            <span className="status-label">Camera</span>
            <span className="status-value">
              {camera?.status === "online"
                ? "Online"
                : camera?.status === "error"
                ? "Error"
                : "Offline"}
            </span>
          </div>
        </div>

        {/* Recording Status */}
        <div className={`status-card ${isRecording ? "status-active-rec" : ""}`}>
          <div className="status-icon">
            <span className={`dot-recording ${isRecording ? "active" : "inactive"}`} />
          </div>
          <div className="status-info">
            <span className="status-label">Recording</span>
            <span className="status-value">{isRecording ? "Active" : "Inactive"}</span>
          </div>
        </div>

        {/* Motion Detection Status */}
        <div className={`status-card ${motionDetected ? "status-active-motion" : ""}`}>
          <div className="status-icon">
            <span className={`dot-motion ${motionDetected ? "active" : "inactive"}`} />
          </div>
          <div className="status-info">
            <span className="status-label">Motion Sensor</span>
            <span className="status-value">{motionDetected ? "Detected" : "Idle"}</span>
          </div>
        </div>
      </div>

      {/* Stream Viewport Container */}
      <div className={`stream-container ${isFullscreen ? "fullscreen" : ""}`}>
        <div className="stream-header">
          <div className="stream-header-title">
            <h2>Live Camera Feed</h2>
            {isRecording && (
              <span className="live-rec-badge">
                <span className="blink-dot" /> REC {formatTimer(recordingSeconds)}
              </span>
            )}
            {motionDetected && <span className="live-motion-badge">⚠️ MOTION</span>}
          </div>
          <div className="stream-controls">
            {cameraOnline && (
              <button
                className={`btn ${isRecording ? "btn-danger" : "btn-primary"}`}
                onClick={toggleRecording}
              >
                {isRecording ? "⏹ Stop Rec" : "● Manual Rec"}
              </button>
            )}
            <button
              className="btn btn-secondary btn-icon-only"
              onClick={() => setIsFullscreen(!isFullscreen)}
              title={isFullscreen ? "Exit Fullscreen" : "Fullscreen View"}
            >
              {isFullscreen ? "🗖" : "🗖"}
            </button>
          </div>
        </div>

        <div className="stream-viewport">
          {cameraOnline ? (
            <img
              src={api.getStreamUrl()}
              alt="Live camera feed"
              className="stream-img"
              onDoubleClick={() => setIsFullscreen(!isFullscreen)}
            />
          ) : (
            <div className="stream-offline">
              <div className="offline-icon">📷</div>
              <p>Camera stream is offline</p>
              {camera?.error && <p className="offline-error">{camera.error}</p>}
              <button
                className="btn btn-primary"
                onClick={handleStartCamera}
                disabled={actionLoading}
              >
                ▶ Start Camera Device
              </button>
            </div>
          )}

          {/* Fullscreen Overlay HUD */}
          {isFullscreen && (
            <div className="fullscreen-hud">
              <div className="hud-top">
                <div className="hud-brand">
                  <span className="hud-dot" /> LIVE CAMERA — Front Gate
                </div>
                <div className="hud-status">
                  {isRecording && (
                    <span className="hud-badge-rec">● REC {formatTimer(recordingSeconds)}</span>
                  )}
                  {motionDetected && <span className="hud-badge-motion">MOTION</span>}
                </div>
              </div>
              <div className="hud-bottom">
                <div className="hud-controls">
                  <button
                    className="btn btn-danger"
                    onClick={handleStopCamera}
                    disabled={actionLoading}
                  >
                    Turn Off
                  </button>
                  {isRecording ? (
                    <button className="btn btn-danger" onClick={toggleRecording}>
                      Stop Rec
                    </button>
                  ) : (
                    <button className="btn btn-primary" onClick={toggleRecording}>
                      Record
                    </button>
                  )}
                  <button className="btn btn-secondary" onClick={() => setIsFullscreen(false)}>
                    Close
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Camera Operation controls */}
      {cameraOnline && (
        <div className="details-card control-panel-card">
          <h3>Camera Controls</h3>
          <div className="controls-grid">
            <button
              className="btn btn-danger"
              onClick={handleStopCamera}
              disabled={actionLoading}
            >
              ⏹ Stop Camera Device
            </button>
            <button className="btn btn-secondary" onClick={triggerRefresh}>
              🔄 Refresh Status
            </button>
          </div>
        </div>
      )}

      {/* Camera Details */}
      {camera && (
        <div className="details-card">
          <h3>Camera Device Details</h3>
          <div className="details-grid">
            <div className="detail-item">
              <span className="detail-label">Device Path</span>
              <span className="detail-value">{camera.device}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Resolution</span>
              <span className="detail-value">{camera.resolution}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Framerate</span>
              <span className="detail-value">{camera.fps} FPS</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Uptime</span>
              <span className="detail-value">
                {health ? formatUptime(health.uptime_seconds) : "—"}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
