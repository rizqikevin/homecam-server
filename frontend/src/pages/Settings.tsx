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
    camera,
  } = useApp();

  const [cacheCleared, setCacheCleared] = useState(false);

  const handleClearCache = async () => {
    if ("caches" in window) {
      const keys = await caches.keys();
      await Promise.all(keys.map((key) => caches.delete(key)));
      setCacheCleared(true);
      setTimeout(() => setCacheCleared(false), 3000);
    }
  };

  const isStandalone = window.matchMedia("(display-mode: standalone)").matches;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Settings</h1>
        <p className="page-subtitle">Configure HomeCam Server parameters and PWA settings</p>
      </div>

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
                  {cacheCleared ? "✓ Cache Cleared" : "🗑 Clear Cache"}
                </button>
              </div>
            </div>
          </div>
        </section>

        {/* Security & Analytics */}
        <section className="settings-section">
          <h2>🔒 Detection & Auto-Record</h2>
          <div className="settings-card-body">
            <div className="form-group">
              <label className="toggle-label">
                <input
                  type="checkbox"
                  checked={settings.motionDetectionEnabled}
                  onChange={(e) =>
                    updateSettings({ motionDetectionEnabled: e.target.checked })
                  }
                />
                <span className="toggle-slider"></span>
                <span className="label-text">
                  <strong>Enable Motion Detection</strong>
                  <span className="label-sub">Simulates motion events and checks for camera pixel changes</span>
                </span>
              </label>
            </div>

            <div className="form-group">
              <label className="toggle-label">
                <input
                  type="checkbox"
                  checked={settings.autoRecord}
                  disabled={!settings.motionDetectionEnabled}
                  onChange={(e) => updateSettings({ autoRecord: e.target.checked })}
                />
                <span className="toggle-slider"></span>
                <span className="label-text">
                  <strong>Auto-Record on Motion</strong>
                  <span className="label-sub">Automatically records a 10s video clip when motion is detected</span>
                </span>
              </label>
            </div>

            <div className="form-group">
              <label className="select-label">
                <strong>Detection Sensitivity</strong>
                <span className="label-sub">Adjust how sensitive the motion algorithm triggers</span>
                <select
                  value={settings.sensitivity}
                  disabled={!settings.motionDetectionEnabled}
                  onChange={(e) =>
                    updateSettings({
                      sensitivity: e.target.value as "low" | "medium" | "high",
                    })
                  }
                >
                  <option value="low">Low (Large objects only)</option>
                  <option value="medium">Medium (Standard)</option>
                  <option value="high">High (Breezes, bugs, shadows)</option>
                </select>
              </label>
            </div>
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
                <span className="info-value">{camera?.device || "/dev/video0"}</span>
              </div>
              <div className="info-item">
                <span className="info-label">Stream Resolution</span>
                <span className="info-value">{camera?.resolution || "640x480"}</span>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
