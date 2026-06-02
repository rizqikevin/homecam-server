import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { CameraStatus, HealthStatus } from "../api";

export default function Dashboard() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [camera, setCamera] = useState<CameraStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchStatus = async () => {
    try {
      const [h, c] = await Promise.all([
        api.getHealth(),
        api.getCameraStatus(),
      ]);
      setHealth(h);
      setCamera(c);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to connect");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    intervalRef.current = setInterval(fetchStatus, 5000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  const handleStart = async () => {
    setActionLoading(true);
    try {
      await api.startCamera();
      await fetchStatus();
    } catch {
      setError("Failed to start camera");
    } finally {
      setActionLoading(false);
    }
  };

  const handleStop = async () => {
    setActionLoading(true);
    try {
      await api.stopCamera();
      await fetchStatus();
    } catch {
      setError("Failed to stop camera");
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

  return (
    <div className="page">
      <div className="page-header">
        <h1>Live Dashboard</h1>
        {error && <div className="error-banner">{error}</div>}
      </div>

      {/* Status Cards */}
      <div className="status-grid">
        <div className={`status-card ${health ? "status-online" : "status-offline"}`}>
          <div className="status-icon">
            <span className={`dot ${health ? "dot-green" : "dot-red"}`} />
          </div>
          <div className="status-info">
            <span className="status-label">Backend</span>
            <span className="status-value">{health ? "Online" : "Offline"}</span>
          </div>
        </div>

        <div className={`status-card ${camera?.status === "online" ? "status-online" : "status-offline"}`}>
          <div className="status-icon">
            <span className={`dot ${camera?.status === "online" ? "dot-green" : "dot-red"}`} />
          </div>
          <div className="status-info">
            <span className="status-label">Camera</span>
            <span className="status-value">
              {camera?.status === "online" ? "Online" : camera?.status === "error" ? "Error" : "Offline"}
            </span>
          </div>
        </div>

        <div className="status-card">
          <div className="status-icon">⏱</div>
          <div className="status-info">
            <span className="status-label">Uptime</span>
            <span className="status-value">
              {health ? formatUptime(health.uptime_seconds) : "—"}
            </span>
          </div>
        </div>

        <div className="status-card">
          <div className="status-icon">📷</div>
          <div className="status-info">
            <span className="status-label">Resolution</span>
            <span className="status-value">{camera?.resolution || "—"}</span>
          </div>
        </div>
      </div>

      {/* Live Stream */}
      <div className="stream-container">
        <div className="stream-header">
          <h2>Live Feed</h2>
          <div className="stream-controls">
            <button
              className="btn btn-success"
              onClick={handleStart}
              disabled={actionLoading || camera?.status === "online"}
            >
              ▶ Start
            </button>
            <button
              className="btn btn-danger"
              onClick={handleStop}
              disabled={actionLoading || camera?.status !== "online"}
            >
              ⏹ Stop
            </button>
          </div>
        </div>

        <div className="stream-viewport">
          {camera?.status === "online" ? (
            <img
              src={api.getStreamUrl()}
              alt="Live camera feed"
              className="stream-img"
            />
          ) : (
            <div className="stream-offline">
              <div className="offline-icon">📷</div>
              <p>Camera is {camera?.status || "offline"}</p>
              {camera?.error && (
                <p className="offline-error">{camera.error}</p>
              )}
              <button
                className="btn btn-primary"
                onClick={handleStart}
                disabled={actionLoading}
              >
                Start Camera
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Camera Details */}
      {camera && (
        <div className="details-card">
          <h3>Camera Details</h3>
          <div className="details-grid">
            <div className="detail-item">
              <span className="detail-label">Device</span>
              <span className="detail-value">{camera.device}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Resolution</span>
              <span className="detail-value">{camera.resolution}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">FPS</span>
              <span className="detail-value">{camera.fps}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Started At</span>
              <span className="detail-value">
                {camera.started_at
                  ? new Date(camera.started_at).toLocaleString()
                  : "—"}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
