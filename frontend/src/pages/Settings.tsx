import { useState } from "react";
import { useApp } from "../context/AppContext";
import { API_BASE_URL } from "../api";

export default function Settings() {
  const {
    settings,
    updateSettings,
    isInstallable,
    promptInstall,
    backendOnline,
    serverInfo,
  } = useApp();

  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const [cacheCleared, setCacheCleared] = useState(false);
  const [updating, setUpdating] = useState(false);

  const triggerFeedback = (type: "success" | "error", message: string) => {
    setFeedback({ type, message });
    setTimeout(() => setFeedback(null), 3000);
  };

  const handleToggleMotion = async (enabled: boolean) => {
    setUpdating(true);
    try {
      // If turning off motion detection, also turn off auto-record to maintain consistency
      const patchData: any = { motion_detection_enabled: enabled };
      if (!enabled) {
        patchData.auto_record_enabled = false;
      }
      await updateSettings(patchData);
      triggerFeedback("success", "Motion detection settings updated");
    } catch (err) {
      triggerFeedback("error", err instanceof Error ? err.message : "Failed to update settings");
    } finally {
      setUpdating(false);
    }
  };

  const handleToggleAutoRecord = async (enabled: boolean) => {
    setUpdating(true);
    try {
      await updateSettings({ auto_record_enabled: enabled });
      triggerFeedback("success", "Auto-recording settings updated");
    } catch (err) {
      triggerFeedback("error", err instanceof Error ? err.message : "Failed to update settings");
    } finally {
      setUpdating(false);
    }
  };

  const handleChangeSensitivity = async (sensitivity: "low" | "medium" | "high") => {
    setUpdating(true);
    try {
      await updateSettings({ detection_sensitivity: sensitivity });
      triggerFeedback("success", `Sensitivity adjusted to ${sensitivity}`);
    } catch (err) {
      triggerFeedback("error", err instanceof Error ? err.message : "Failed to update settings");
    } finally {
      setUpdating(false);
    }
  };

  const handleClearCache = async () => {
    if ("caches" in window) {
      const keys = await caches.keys();
      await Promise.all(keys.map((key) => caches.delete(key)));
      setCacheCleared(true);
      setTimeout(() => {
        setCacheCleared(false);
        window.location.reload();
      }, 1500);
    }
  };

  const isStandalone = window.matchMedia("(display-mode: standalone)").matches;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Settings</h1>
        <p className="page-subtitle">Configure HomeCam Server parameters and PWA settings</p>
      </div>

      {feedback && (
        <div className={`error-banner ${feedback.type === "success" ? "badge-success" : ""}`} style={{ marginBottom: "20px" }}>
          {feedback.type === "success" ? "🟢" : "🔴"} {feedback.message}
        </div>
      )}

      <div className="settings-container">
        {/* PWA App Settings */}
        <section className="settings-section">
          <h2>📱 PWA Installation & App Info</h2>
          <div className="settings-card-body">
            <div className="settings-info-row">
              <div>
                <h4 className="info-title">PWA Status</h4>
                <p className="info-desc">
                  {isStandalone
                    ? "Running in Standalone App Window (Native Mode)"
                    : "Running in Web Browser"}
                </p>
              </div>
              <div>
                {isStandalone ? (
                  <span className="badge badge-success">✓ Installed</span>
                ) : isInstallable ? (
                  <button className="btn btn-primary" onClick={promptInstall}>
                    📥 Install App
                  </button>
                ) : (
                  <span className="badge badge-secondary">Ready / Added</span>
                )}
              </div>
            </div>

            <div className="settings-info-row">
              <div>
                <h4 className="info-title">Service Worker</h4>
                <p className="info-desc">Registered runtime handler caching assets for offline fallback.</p>
              </div>
              <div>
                <span className="badge badge-success">Active</span>
              </div>
            </div>

            <div className="settings-info-row">
              <div>
                <h4 className="info-title">Offline Cache</h4>
                <p className="info-desc">Force clear the cached assets and reload the application shell.</p>
              </div>
              <div>
                <button
                  className={`btn ${cacheCleared ? "btn-success" : "btn-danger"}`}
                  onClick={handleClearCache}
                  disabled={cacheCleared}
                >
                  {cacheCleared ? "✓ Reloading App..." : "🗑 Clear Cache"}
                </button>
              </div>
            </div>
          </div>
        </section>

        {/* Security & Analytics */}
        <section className="settings-section">
          <h2>🔒 Detection & Auto-Record</h2>
          <div className="settings-card-body">
            {settings ? (
              <>
                <div className="form-group">
                  <label className="toggle-label">
                    <input
                      type="checkbox"
                      checked={settings.motion_detection_enabled}
                      disabled={updating || !backendOnline}
                      onChange={(e) => handleToggleMotion(e.target.checked)}
                    />
                    <span className="toggle-slider"></span>
                    <span className="label-text">
                      <strong>Enable Motion Detection</strong>
                      <span className="label-sub">Analyzes live video stream frames for pixel variations</span>
                    </span>
                  </label>
                </div>

                <div className="form-group">
                  <label className="toggle-label">
                    <input
                      type="checkbox"
                      checked={settings.auto_record_enabled}
                      disabled={updating || !settings.motion_detection_enabled || !backendOnline}
                      onChange={(e) => handleToggleAutoRecord(e.target.checked)}
                    />
                    <span className="toggle-slider"></span>
                    <span className="label-text">
                      <strong>Auto-Record on Motion</strong>
                      <span className="label-sub">Automatically saves a 10s video clip when motion is detected</span>
                    </span>
                  </label>
                </div>

                <div className="form-group">
                  <label className="select-label">
                    <strong>Detection Sensitivity</strong>
                    <span className="label-sub">Adjust how sensitive the motion algorithm triggers (low, medium, high)</span>
                    <select
                      value={settings.detection_sensitivity}
                      disabled={updating || !settings.motion_detection_enabled || !backendOnline}
                      onChange={(e) =>
                        handleChangeSensitivity(e.target.value as "low" | "medium" | "high")
                      }
                    >
                      <option value="low">Low (Large objects only - 9000px threshold)</option>
                      <option value="medium">Medium (Standard - 5000px threshold)</option>
                      <option value="high">High (Breezes, shadows - 2500px threshold)</option>
                    </select>
                  </label>
                </div>
              </>
            ) : (
              <p style={{ color: "var(--text-muted)" }}>Connecting to Settings API...</p>
            )}
          </div>
        </section>

        {/* Backend API settings */}
        <section className="settings-section">
          <h2>⚙️ Backend Server Info</h2>
          <div className="settings-card-body">
            <div className="info-grid">
              <div className="info-item">
                <span className="info-label">API Base URL</span>
                <span className="info-value">{API_BASE_URL}</span>
              </div>
              <div className="info-item">
                <span className="info-label">Server Connection</span>
                <span className="info-value">
                  {backendOnline ? (
                    <span className="text-green">🟢 Connected</span>
                  ) : (
                    <span className="text-red">🔴 Offline</span>
                  )}
                </span>
              </div>
              <div className="info-item">
                <span className="info-label">Target Device</span>
                <span className="info-value">{serverInfo?.camera_device || "Connecting..."}</span>
              </div>
              <div className="info-item">
                <span className="info-label">Recordings Volume</span>
                <span className="info-value">{serverInfo?.recordings_dir || "Connecting..."}</span>
              </div>
              {serverInfo && (
                <>
                  <div className="info-item">
                    <span className="info-label">Total Files</span>
                    <span className="info-value">{serverInfo.storage.recordings_count} clips</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">Storage Consumed</span>
                    <span className="info-value">{serverInfo.storage.total_size_label}</span>
                  </div>
                </>
              )}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
