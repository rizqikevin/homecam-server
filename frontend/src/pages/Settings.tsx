import { useCallback, useEffect, useState } from "react";
import { useApp } from "../context/AppContext";
import { API_BASE_URL, type SettingsData } from "../api";

const MAX_RECORDING_DAYS_MIN = 1;
const MAX_RECORDING_DAYS_MAX = 365;
const MAX_RECORDING_DAYS_DEBOUNCE_MS = 700;

const clampMaxRecordingDays = (days: number) =>
  Math.min(MAX_RECORDING_DAYS_MAX, Math.max(MAX_RECORDING_DAYS_MIN, days));

export default function Settings() {
  const {
    settings,
    updateSettings,
    isInstallable,
    promptInstall,
    backendOnline,
    serverInfo,
  } = useApp();

  const [feedback, setFeedback] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);
  const [cacheCleared, setCacheCleared] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [savingMaxRecordingDays, setSavingMaxRecordingDays] = useState(false);
  const [maxRecordingDaysDraft, setMaxRecordingDaysDraft] = useState<
    string | null
  >(null);

  const triggerFeedback = useCallback(
    (type: "success" | "error", message: string) => {
      setFeedback({ type, message });
      setTimeout(() => setFeedback(null), 3000);
    },
    [],
  );

  const savedMaxRecordingDays = settings?.max_recording_days;
  const maxRecordingDaysValue =
    maxRecordingDaysDraft ?? (savedMaxRecordingDays?.toString() ?? "");
  const maxRecordingDaysNumber = Number(maxRecordingDaysValue);
  const maxRecordingDaysError =
    maxRecordingDaysValue.trim() === ""
      ? "Retention days is required"
      : !Number.isInteger(maxRecordingDaysNumber)
        ? "Use a whole number"
        : maxRecordingDaysNumber < MAX_RECORDING_DAYS_MIN ||
            maxRecordingDaysNumber > MAX_RECORDING_DAYS_MAX
          ? `Use ${MAX_RECORDING_DAYS_MIN}-${MAX_RECORDING_DAYS_MAX} days`
          : null;

  const handleToggleMotion = async (enabled: boolean) => {
    setUpdating(true);
    try {
      // If turning off motion detection, also turn off auto-record to maintain consistency
      const patchData: Partial<SettingsData> = {
        motion_detection_enabled: enabled,
      };
      if (!enabled) {
        patchData.auto_record_enabled = false;
      }
      await updateSettings(patchData);
      triggerFeedback("success", "Motion detection settings updated");
    } catch (err) {
      triggerFeedback(
        "error",
        err instanceof Error ? err.message : "Failed to update settings",
      );
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
      triggerFeedback(
        "error",
        err instanceof Error ? err.message : "Failed to update settings",
      );
    } finally {
      setUpdating(false);
    }
  };

  const handleChangeSensitivity = async (
    sensitivity: "low" | "medium" | "high",
  ) => {
    setUpdating(true);
    try {
      await updateSettings({ detection_sensitivity: sensitivity });
      triggerFeedback("success", `Sensitivity adjusted to ${sensitivity}`);
    } catch (err) {
      triggerFeedback(
        "error",
        err instanceof Error ? err.message : "Failed to update settings",
      );
    } finally {
      setUpdating(false);
    }
  };

  const handleChangeMaxRecordingDays = useCallback(async (days: number) => {
    setUpdating(true);
    setSavingMaxRecordingDays(true);
    try {
      await updateSettings({ max_recording_days: days });
      setMaxRecordingDaysDraft(null);
      triggerFeedback(
        "success",
        `Max recording retention set to ${days} day${days !== 1 ? "s" : ""}`,
      );
    } catch (err) {
      triggerFeedback(
        "error",
        err instanceof Error ? err.message : "Failed to update settings",
      );
    } finally {
      setSavingMaxRecordingDays(false);
      setUpdating(false);
    }
  }, [triggerFeedback, updateSettings]);

  useEffect(() => {
    if (
      !backendOnline ||
      maxRecordingDaysError ||
      savedMaxRecordingDays === undefined ||
      maxRecordingDaysNumber === savedMaxRecordingDays
    ) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      handleChangeMaxRecordingDays(maxRecordingDaysNumber);
    }, MAX_RECORDING_DAYS_DEBOUNCE_MS);

    return () => window.clearTimeout(timeoutId);
  }, [
    backendOnline,
    handleChangeMaxRecordingDays,
    maxRecordingDaysError,
    maxRecordingDaysNumber,
    savedMaxRecordingDays,
  ]);

  const handleMaxRecordingDaysInput = (value: string) => {
    setMaxRecordingDaysDraft(value.replace(/\D/g, ""));
  };

  const handleMaxRecordingDaysBlur = () => {
    const days = Number(maxRecordingDaysValue);
    if (
      maxRecordingDaysValue.trim() === "" ||
      !Number.isInteger(days)
    ) {
      setMaxRecordingDaysDraft(null);
      return;
    }

    setMaxRecordingDaysDraft(String(clampMaxRecordingDays(days)));
  };

  const handleStepMaxRecordingDays = (step: number) => {
    const days = Number(maxRecordingDaysValue);
    const fallbackDays = savedMaxRecordingDays ?? 7;
    const nextDays = Number.isInteger(days) ? days + step : fallbackDays + step;

    setMaxRecordingDaysDraft(String(clampMaxRecordingDays(nextDays)));
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
        <p className="page-subtitle">
          Configure HomeCam Server parameters and PWA settings
        </p>
      </div>

      {feedback && (
        <div
          className={`error-banner ${feedback.type === "success" ? "badge-success" : ""}`}
          style={{ marginBottom: "20px" }}
        >
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
                <p className="info-desc">
                  Registered runtime handler caching assets for offline
                  fallback.
                </p>
              </div>
              <div>
                <span className="badge badge-success">Active</span>
              </div>
            </div>

            <div className="settings-info-row">
              <div>
                <h4 className="info-title">Offline Cache</h4>
                <p className="info-desc">
                  Force clear the cached assets and reload the application
                  shell.
                </p>
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
                      <span className="label-sub">
                        Analyzes live video stream frames for pixel variations
                      </span>
                    </span>
                  </label>
                </div>

                <div className="form-group">
                  <label className="toggle-label">
                    <input
                      type="checkbox"
                      checked={settings.auto_record_enabled}
                      disabled={
                        updating ||
                        !settings.motion_detection_enabled ||
                        !backendOnline
                      }
                      onChange={(e) => handleToggleAutoRecord(e.target.checked)}
                    />
                    <span className="toggle-slider"></span>
                    <span className="label-text">
                      <strong>Auto-Record on Motion</strong>
                      <span className="label-sub">
                        Automatically saves a 10s video clip when motion is
                        detected
                      </span>
                    </span>
                  </label>
                </div>

                <div className="form-group">
                  <label className="select-label">
                    <strong>Detection Sensitivity</strong>
                    <span className="label-sub">
                      Adjust how sensitive the motion algorithm triggers (low,
                      medium, high)
                    </span>
                    <select
                      value={settings.detection_sensitivity}
                      disabled={
                        updating ||
                        !settings.motion_detection_enabled ||
                        !backendOnline
                      }
                      onChange={(e) =>
                        handleChangeSensitivity(
                          e.target.value as "low" | "medium" | "high",
                        )
                      }
                    >
                      <option value="low">
                        Low (Large objects only - 9000px threshold)
                      </option>
                      <option value="medium">
                        Medium (Standard - 5000px threshold)
                      </option>
                      <option value="high">
                        High (Breezes, shadows - 2500px threshold)
                      </option>
                    </select>
                  </label>
                </div>
              </>
            ) : (
              <p style={{ color: "var(--text-muted)" }}>
                Connecting to Settings API...
              </p>
            )}
          </div>
        </section>

        {/* Storage & Cleanup Settings */}
        <section className="settings-section">
          <h2>🗑️ Storage & Cleanup</h2>
          <div className="settings-card-body">
            {settings ? (
              <>
                <div className="form-group">
                  <label className="number-label">
                    <strong>Max Recording Retention (Days)</strong>
                    <span className="label-sub">
                      Videos older than this will be automatically deleted to
                      free up storage space
                    </span>
                    <div className="number-input-group">
                      <button
                        type="button"
                        className="btn-spinbox btn-spinbox-minus"
                        aria-label="Decrease max recording retention"
                        disabled={updating || !backendOnline}
                        onClick={() => handleStepMaxRecordingDays(-1)}
                      >
                        -
                      </button>
                      <input
                        type="text"
                        inputMode="numeric"
                        pattern="[0-9]*"
                        aria-invalid={maxRecordingDaysError ? "true" : "false"}
                        value={maxRecordingDaysValue}
                        disabled={updating || !backendOnline}
                        onBlur={handleMaxRecordingDaysBlur}
                        onChange={(e) =>
                          handleMaxRecordingDaysInput(e.target.value)
                        }
                      />
                      <button
                        type="button"
                        className="btn-spinbox btn-spinbox-plus"
                        aria-label="Increase max recording retention"
                        disabled={updating || !backendOnline}
                        onClick={() => handleStepMaxRecordingDays(1)}
                      >
                        +
                      </button>
                    </div>
                  </label>
                  <p
                    style={{
                      color: maxRecordingDaysError
                        ? "var(--red)"
                        : "var(--text-muted)",
                      fontSize: "0.85rem",
                      marginTop: "8px",
                    }}
                  >
                    {maxRecordingDaysError
                      ? maxRecordingDaysError
                      : savingMaxRecordingDays
                        ? "Saving..."
                        : `Current: ${settings.max_recording_days} day${
                            settings.max_recording_days !== 1 ? "s" : ""
                          }`}
                  </p>
                </div>
              </>
            ) : (
              <p style={{ color: "var(--text-muted)" }}>
                Connecting to Settings API...
              </p>
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
                <span className="info-value">
                  {serverInfo?.camera_device || "Connecting..."}
                </span>
              </div>
              <div className="info-item">
                <span className="info-label">Recordings Volume</span>
                <span className="info-value">
                  {serverInfo?.recordings_dir || "Connecting..."}
                </span>
              </div>
              {serverInfo && (
                <>
                  <div className="info-item">
                    <span className="info-label">Total Files</span>
                    <span className="info-value">
                      {serverInfo.storage.recordings_count} clips
                    </span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">Storage Consumed</span>
                    <span className="info-value">
                      {serverInfo.storage.total_size_label}
                    </span>
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
