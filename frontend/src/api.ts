const getApiBaseUrl = (): string => {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  // If envUrl is explicitly provided (even if it's empty, representing proxy), use it.
  if (envUrl !== undefined && envUrl !== null) {
    return envUrl;
  }
  // Default production API URL fallback
  return "http://192.168.1.10:8005";
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

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export interface HealthStatus {
  status: string;
  uptime_seconds: number;
  timestamp: string;
}

export interface CameraStatus {
  status: "online" | "offline" | "error";
  error: string | null;
  started_at: string | null;
  device: string;
  resolution: string;
  fps: number;
}

export const api = {
  getHealth: () => get<HealthStatus>("/api/health"),
  getCameraStatus: () => get<CameraStatus>("/api/camera/status"),
  startCamera: () => post<{ message: string }>("/api/camera/start"),
  stopCamera: () => post<{ message: string }>("/api/camera/stop"),
  getStreamUrl: () => `${API_BASE_URL}/api/camera/stream`,
};
