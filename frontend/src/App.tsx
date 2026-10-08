import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Recordings from "./pages/Recordings";
import Settings from "./pages/Settings";
import { AppProvider } from "./context/AppProvider";
import { useAuth } from "./context/AuthContext";
import { AuthProvider } from "./context/AuthProvider";
import Login from "./pages/Login";

function AuthenticatedApp() {
  const { username, checking } = useAuth();
  if (checking) return <main className="auth-page"><p role="status">Checking session…</p></main>;
  if (!username) return <Login />;
  return (
    <AppProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/recordings" element={<Recordings />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AppProvider>
  );
}

function App() {
  return <AuthProvider><AuthenticatedApp /></AuthProvider>;
}

export default App;
