import { createContext, useContext } from "react";
import type { CameraStatus, HealthStatus, SettingsData, ServerInfo } from "../api";

export interface BeforeInstallPromptEvent extends Event {
  readonly platforms: string[];
  readonly userChoice: Promise<{
    outcome: "accepted" | "dismissed";
    platform: string;
  }>;
  prompt(): Promise<void>;
}

interface AppContextType {
  health: HealthStatus | null;
  camera: CameraStatus | null;
  serverInfo: ServerInfo | null;
  settings: SettingsData | null;
  backendOnline: boolean;
  cameraOnline: boolean;
  isRecording: boolean;
  motionDetected: boolean;
  loading: boolean;
  error: string | null;
  deferredPrompt: BeforeInstallPromptEvent | null;
  isInstallable: boolean;
  promptInstall: () => void;
  updateSettings: (newSettings: Partial<SettingsData>) => Promise<void>;
  triggerRefresh: () => Promise<void>;
  fetchServerInfo: () => Promise<void>;
}

export const AppContext = createContext<AppContextType | undefined>(undefined);

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error("useApp must be used within an AppProvider");
  }
  return context;
};
