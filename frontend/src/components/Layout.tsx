import { NavLink, Outlet } from "react-router-dom";
import { useApp } from "../context/AppContext";
import { useState } from "react";
import { useAuth } from "../context/AuthContext";

export default function Layout() {
  const { backendOnline, isRecording, motionDetected, camera } = useApp();
  const { username, logout } = useAuth();
  const [loggingOut, setLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);

  async function signOut() {
    setLoggingOut(true);
    setLogoutError(null);
    try {
      await logout();
    } catch (err) {
      setLogoutError(err instanceof Error ? err.message : "Unable to sign out. Try again.");
      setLoggingOut(false);
    }
  }

  return (
    <div className="app-layout">
      {/* Mobile Top Header */}
      <header className="mobile-header">
        <div className="header-brand">
          <span className="brand-icon">🎥</span>
          <span className="brand-name">HomeCam</span>
        </div>
          <div className="header-indicators">
          {camera?.detector_status === "error" && (
            <span className="badge badge-danger" title={camera.detector_error || "Pose detector error"}>
              DETECTOR ERR
            </span>
          )}
          {motionDetected && <span className="badge-motion">MOTION</span>}
          {isRecording && <span className="badge-recording">● REC</span>}
          <span
            className={`dot ${backendOnline ? "dot-green" : "dot-red"}`}
            title={backendOnline ? "Backend Connected" : "Backend Offline"}
          />
        </div>
      </header>

      {/* Sidebar for Desktop */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="brand-icon">🎥</span>
          <div className="brand-text">
            <span className="brand-name">HomeCam</span>
            <span className="brand-sub">Server</span>
          </div>
        </div>

        <div className="sidebar-indicators">
          <div className="indicator-row">
            <span className="indicator-label">Backend</span>
            <span className={`dot ${backendOnline ? "dot-green" : "dot-red"}`} />
          </div>
          <div className="indicator-row">
            <span className="indicator-label">Human Detector</span>
            <span
              className={`dot ${
                camera?.detector_status === "ready"
                  ? "dot-green"
                  : camera?.detector_status === "initializing"
                  ? "dot-amber"
                  : camera?.detector_status === "error"
                  ? "dot-red"
                  : "dot-grey"
              }`}
              title={
                camera?.detector_status === "error" && camera.detector_error
                  ? camera.detector_error
                  : camera?.detector_status || "offline"
              }
            />
          </div>
          {motionDetected && (
            <div className="indicator-row animate-pulse">
              <span className="indicator-label text-amber">Motion Alert</span>
              <span className="dot dot-amber" />
            </div>
          )}
          {isRecording && (
            <div className="indicator-row animate-blink">
              <span className="indicator-label text-red">Recording</span>
              <span className="dot dot-red" />
            </div>
          )}
        </div>

        <nav className="sidebar-nav">
          <NavLink to="/" end className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
            <span className="nav-icon">📊</span>
            <span>Dashboard</span>
          </NavLink>
          <NavLink to="/recordings" className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
            <span className="nav-icon">📁</span>
            <span>Recordings</span>
          </NavLink>
          <NavLink to="/settings" className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
            <span className="nav-icon">⚙️</span>
            <span>Settings</span>
          </NavLink>
        </nav>

        <div className="sidebar-footer">
          <span className="version">v0.2.0 (PWA)</span>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        <div className="session-controls">
          <span>Signed in as <strong>{username}</strong></span>
          <button type="button" className="btn auth-logout" onClick={signOut} disabled={loggingOut}>{loggingOut ? "Signing out…" : "Sign out"}</button>
        </div>
        {logoutError && <p className="auth-error" role="alert">{logoutError}</p>}
        <Outlet />
      </main>

      {/* Bottom Nav for Mobile */}
      <nav className="bottom-nav">
        <NavLink to="/" end className={({ isActive }) => `bottom-nav-link ${isActive ? "active" : ""}`}>
          <span className="bottom-nav-icon">📊</span>
          <span className="bottom-nav-label">Dashboard</span>
        </NavLink>
        <NavLink to="/recordings" className={({ isActive }) => `bottom-nav-link ${isActive ? "active" : ""}`}>
          <span className="bottom-nav-icon">📁</span>
          <span className="bottom-nav-label">Recordings</span>
        </NavLink>
        <NavLink to="/settings" className={({ isActive }) => `bottom-nav-link ${isActive ? "active" : ""}`}>
          <span className="bottom-nav-icon">⚙️</span>
          <span className="bottom-nav-label">Settings</span>
        </NavLink>
      </nav>
    </div>
  );
}
