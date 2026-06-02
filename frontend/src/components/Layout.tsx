import { NavLink, Outlet } from "react-router-dom";

export default function Layout() {
  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="brand-icon">🎥</span>
          <div className="brand-text">
            <span className="brand-name">HomeCam</span>
            <span className="brand-sub">Server</span>
          </div>
        </div>

        <nav className="sidebar-nav">
          <NavLink to="/" end className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
            <span className="nav-icon">📊</span>
            <span>Dashboard</span>
          </NavLink>
        </nav>

        <div className="sidebar-footer">
          <span className="version">v0.1.0</span>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
