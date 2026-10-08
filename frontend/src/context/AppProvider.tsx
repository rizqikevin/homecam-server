import React, { useState, useEffect, useCallback } from "react";
import { api } from "../api";
import type { CameraStatus, HealthStatus, SettingsData, ServerInfo } from "../api";

import { AppContext, type BeforeInstallPromptEvent } from "./AppContext";

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [camera, setCamera] = useState<CameraStatus | null>(null);
  const [serverInfo, setServerInfo] = useState<ServerInfo | null>(null);
  const [settings, setSettings] = useState<SettingsData | null>(null);
  
  const [backendOnline, setBackendOnline] = useState<boolean>(false);
  const [cameraOnline, setCameraOnline] = useState<boolean>(false);
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [motionDetected, setMotionDetected] = useState<boolean>(false);
  
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // PWA properties
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [isInstallable, setIsInstallable] = useState<boolean>(false);

  // Load initial settings and server info
  const loadInitialData = useCallback(() => {
    return Promise.all([api.getSettings(), api.getServerInfo()]).then(
      ([settings, info]) => {
        setSettings(settings);
        setServerInfo(info);
      },
      (err: unknown) => {
        console.error("[AppContext] Failed to load settings or server info:", err);
      },
    );
  }, []);

  const fetchServerInfo = useCallback(async () => {
    try {
      const info = await api.getServerInfo();
      setServerInfo(info);
    } catch (err) {
      console.error("Failed to fetch server info:", err);
    }
  }, []);

  // Poll camera/health status
  const fetchStatus = useCallback(() => {
    return Promise.all([api.getHealth(), api.getCameraStatus()]).then(
      ([h, c]) => {
        setHealth(h);
        setCamera(c);
        setBackendOnline(true);
        setCameraOnline(c.status === "online");
        setIsRecording(c.recording);
        setMotionDetected(c.motion_detected);
        setError(null);
        setLoading(false);
      },
      (err: unknown) => {
        setHealth(null);
        setCamera(null);
        setBackendOnline(false);
        setCameraOnline(false);
        setIsRecording(false);
        setMotionDetected(false);
        setError(err instanceof Error ? err.message : "Backend connection lost");
        setLoading(false);
      },
    );
  }, []);

  const triggerRefresh = useCallback(async () => {
    setLoading(true);
    await Promise.all([fetchStatus(), loadInitialData()]);
  }, [fetchStatus, loadInitialData]);

  // Run on mount
  useEffect(() => {
    fetchStatus();
    loadInitialData();
    
    // Poll status every 2 seconds as requested for real-time responsiveness
    const interval = setInterval(fetchStatus, 2000);
    return () => clearInterval(interval);
  }, [fetchStatus, loadInitialData]);

  // Update Settings via API
  const updateSettings = useCallback(async (newSettings: Partial<SettingsData>) => {
    try {
      const updated = await api.patchSettings(newSettings);
      setSettings(updated);
      await fetchServerInfo();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to save settings";
      throw new Error(msg, { cause: err });
    }
  }, [fetchServerInfo]);

  // Handle PWA installation trigger
  useEffect(() => {
    const handleBeforeInstallPrompt = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e as BeforeInstallPromptEvent);
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
        serverInfo,
        settings,
        backendOnline,
        cameraOnline,
        isRecording,
        motionDetected,
        loading,
        error,
        deferredPrompt,
        isInstallable,
        promptInstall,
        updateSettings,
        triggerRefresh,
        fetchServerInfo,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};
