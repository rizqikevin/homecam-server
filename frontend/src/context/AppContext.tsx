import React, { createContext, useContext, useState, useEffect } from "react";
import { api } from "../api";
import type { CameraStatus, HealthStatus } from "../api";

interface AppSettings {
  motionDetectionEnabled: boolean;
  autoRecord: boolean;
  sensitivity: "low" | "medium" | "high";
  fpsLimit: number;
}

interface AppContextType {
  health: HealthStatus | null;
  camera: CameraStatus | null;
  backendOnline: boolean;
  cameraOnline: boolean;
  isRecording: boolean;
  motionDetected: boolean;
  settings: AppSettings;
  updateSettings: (newSettings: Partial<AppSettings>) => void;
  setIsRecording: (recording: boolean) => void;
  triggerRefresh: () => Promise<void>;
  loading: boolean;
  error: string | null;
  deferredPrompt: any;
  isInstallable: boolean;
  promptInstall: () => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error("useApp must be used within an AppProvider");
  }
  return context;
};

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [camera, setCamera] = useState<CameraStatus | null>(null);
  const [backendOnline, setBackendOnline] = useState<boolean>(false);
  const [cameraOnline, setCameraOnline] = useState<boolean>(false);
  const [isRecording, setIsRecordingState] = useState<boolean>(false);
  const [motionDetected, setMotionDetected] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // PWA Install properties
  const [deferredPrompt, setDeferredPrompt] = useState<any>(null);
  const [isInstallable, setIsInstallable] = useState<boolean>(false);

  // Settings state persisted to localStorage
  const [settings, setSettings] = useState<AppSettings>(() => {
    const saved = localStorage.getItem("homecam_settings");
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {
        // use default
      }
    }
    return {
      motionDetectionEnabled: true,
      autoRecord: true,
      sensitivity: "medium",
      fpsLimit: 15,
    };
  });

  const updateSettings = (newSettings: Partial<AppSettings>) => {
    setSettings((prev) => {
      const updated = { ...prev, ...newSettings };
      localStorage.setItem("homecam_settings", JSON.stringify(updated));
      return updated;
    });
  };

  const setIsRecording = (recording: boolean) => {
    setIsRecordingState(recording);
    localStorage.setItem("homecam_is_recording", recording ? "true" : "false");
  };

  // Load recording state
  useEffect(() => {
    const savedRecording = localStorage.getItem("homecam_is_recording");
    if (savedRecording === "true") {
      setIsRecordingState(true);
    }
  }, []);

  // Fetch API status
  const fetchStatus = async () => {
    try {
      const [h, c] = await Promise.all([
        api.getHealth(),
        api.getCameraStatus(),
      ]);
      setHealth(h);
      setCamera(c);
      setBackendOnline(true);
      setCameraOnline(c.status === "online");
      setError(null);
    } catch (err) {
      setHealth(null);
      setCamera(null);
      setBackendOnline(false);
      setCameraOnline(false);
      setError(err instanceof Error ? err.message : "Backend connection lost");
    } finally {
      setLoading(false);
    }
  };

  const triggerRefresh = async () => {
    setLoading(true);
    await fetchStatus();
  };

  // Poll status every 5 seconds
  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  // Simulate Motion Detection if enabled
  useEffect(() => {
    if (!settings.motionDetectionEnabled || !cameraOnline) {
      setMotionDetected(false);
      return;
    }

    const interval = setInterval(() => {
      // 15% chance to toggle motion when online
      const shouldDetect = Math.random() < 0.15;
      setMotionDetected((prev) => {
        const next = shouldDetect ? !prev : prev;
        
        // Auto-record if motion is detected and auto-record is enabled
        if (next && settings.autoRecord && !isRecording) {
          setIsRecording(true);
          // Auto-stop recording after 10 seconds of motion
          setTimeout(() => {
            setIsRecording(false);
          }, 10000);
        }
        return next;
      });
    }, 4000);

    return () => clearInterval(interval);
  }, [settings.motionDetectionEnabled, settings.autoRecord, cameraOnline, isRecording]);

  // Handle PWA installation trigger
  useEffect(() => {
    const handleBeforeInstallPrompt = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e);
      setIsInstallable(true);
    };

    window.addEventListener("beforeinstallprompt", handleBeforeInstallPrompt);

    return () => {
      window.removeEventListener("beforeinstallprompt", handleBeforeInstallPrompt);
    };
  }, []);

  const promptInstall = () => {
    if (deferredPrompt) {
      deferredPrompt.prompt();
      deferredPrompt.userChoice.then((choiceResult: { outcome: string }) => {
        if (choiceResult.outcome === "accepted") {
          console.log("User accepted the install prompt");
        } else {
          console.log("User dismissed the install prompt");
        }
        setDeferredPrompt(null);
        setIsInstallable(false);
      });
    }
  };

  return (
    <AppContext.Provider
      value={{
        health,
        camera,
        backendOnline,
        cameraOnline,
        isRecording,
        motionDetected,
        settings,
        updateSettings,
        setIsRecording,
        triggerRefresh,
        loading,
        error,
        deferredPrompt,
        isInstallable,
        promptInstall,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};
