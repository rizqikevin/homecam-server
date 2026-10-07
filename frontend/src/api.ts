export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    credentials: "include",
    cache: "no-store",
  });
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith("/api/auth/")) {
      window.dispatchEvent(new Event("homecam:unauthorized"));
    }
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, typeof body?.detail === "string" ? body.detail : `Request failed: ${res.status}`);
  }
  return res.json();
}

const get = <T,>(path: string) => request<T>(path);
const post = <T,>(path: string, body?: unknown) => request<T>(path, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  ...(body === undefined ? {} : { body: JSON.stringify(body) }),
});
const patch = <T,>(path: string, body: unknown) => request<T>(path, {
  method: "PATCH",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});
const del = <T,>(path: string) => request<T>(path, { method: "DELETE" });

// ---------------------------------------------------------------------------
// Type Definitions
// ---------------------------------------------------------------------------

export interface HealthStatus {
  status: string;
  uptime_seconds: number;
  timestamp: string;
}

export type DetectorStatus = "disabled" | "initializing" | "ready" | "error";

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
  detector_status?: DetectorStatus;
  detector_error?: string | null;
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
  getSession: () => get<{ username: string }>("/api/auth/session"),
  login: (username: string, password: string) => post<{ username: string }>("/api/auth/login", { username, password }),
  logout: () => post<{ message: string }>("/api/auth/logout"),
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
