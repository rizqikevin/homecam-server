const getApiBaseUrl = (): string => {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  // If envUrl is explicitly provided and is NOT an empty string, use it.
  if (envUrl && envUrl.trim() !== "") {
    return envUrl;
  }
  // Default production API URL fallback (since served on 3005 and API is on 8005, it is not proxied)
  return "https://api.e-prostock.com";
};

export const API_BASE_URL = getApiBaseUrl();

/** GET JSON from the API. */
async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`);
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
  return res.json();
}

/** POST to the API (no body). */
async function post<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, { method: "POST" });
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`);
  return res.json();
}

/** PATCH to the API. */
async function patch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`PATCH ${path} failed: ${res.status}`);
  return res.json();
}

/** DELETE from the API. */
async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`DELETE ${path} failed: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Type Definitions
// ---------------------------------------------------------------------------

export interface HealthStatus {
  status: string;
  uptime_seconds: number;
  timestamp: string;
}

export interface CameraStatus {
  status: "online" | "offline" | "error";
  online: boolean;
  error: string | null;
  started_at: string | null;
  device: string;
  resolution: string;
  fps: number;
  motion_detection_enabled: boolean;
  motion_detected: boolean;
  auto_record_enabled: boolean;
  recording: boolean;
  recording_filename: string | null;
  recordings_count: number;
}

export interface SettingsData {
  camera_device: string;
  width: number;
  height: number;
  fps: number;
  motion_detection_enabled: boolean;
  auto_record_enabled: boolean;
  detection_sensitivity: "low" | "medium" | "high";
  motion_threshold: number;
  stop_recording_after_seconds: number;
  recording_clip_seconds: number;
  recordings_dir: string;
  max_recording_days: number;
}

export interface RecordingItem {
  filename: string;
  url: string;
  download_url: string;
  size_bytes: number;
  size_label: string;
  created_at: string;
  duration_seconds: number | null;
  type: "motion" | "manual" | "schedule" | "unknown";
}

export interface ServerInfo {
  api_base_url: string;
  server_time: string;
  recordings_dir: string;
  camera_device: string;
  storage: {
    recordings_count: number;
    total_size_bytes: number;
    total_size_label: string;
  };
  features: {
    motion_detection: boolean;
    auto_record: boolean;
    manual_record: boolean;
    pwa: boolean;
  };
}

export const api = {
  getHealth: () => get<HealthStatus>("/api/health"),
  getCameraStatus: () => get<CameraStatus>("/api/camera/status"),
  startCamera: () => post<{ message: string }>("/api/camera/start"),
  stopCamera: () => post<{ message: string }>("/api/camera/stop"),
  getStreamUrl: () => `${API_BASE_URL}/api/camera/stream`,

  // Settings API
  getSettings: () => get<SettingsData>("/api/settings"),
  patchSettings: (data: Partial<SettingsData>) =>
    patch<SettingsData>("/api/settings", data),

  // Manual Recording Controls
  startManualRecording: () =>
    post<{ message: string; filename: string }>("/api/recordings/start"),
  stopManualRecording: () =>
    post<{ message: string; filename: string }>("/api/recordings/stop"),

  // Recordings API
  getRecordings: () =>
    get<{ items: RecordingItem[]; total: number }>("/api/recordings"),
  deleteRecording: (filename: string) =>
    del<{ message: string; filename: string }>(`/api/recordings/${filename}`),
  getPlaybackUrl: (filename: string) =>
    `${API_BASE_URL}/api/recordings/${filename}`,
  getDownloadUrl: (filename: string) =>
    `${API_BASE_URL}/api/recordings/${filename}?download=true`,

  // Server Diagnostics
  getServerInfo: () => get<ServerInfo>("/api/server/info"),
};
