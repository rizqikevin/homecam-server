import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { api, ApiError } from "../api";

import { AuthContext } from "./AuthContext";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [username, setUsername] = useState<string | null>(null);
  const [checking, setChecking] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const generation = useRef(0);

  const checkSession = useCallback(() => {
    const current = generation.current;
    return api.getSession().then(
      (session) => {
        if (current !== generation.current) return;
        setUsername(session.username);
        setError(null);
        setChecking(false);
      },
      (err: unknown) => {
        if (current !== generation.current) return;
        if (err instanceof ApiError && err.status === 401) {
          setUsername(null);
          setError(null);
        } else {
          setError(err instanceof Error ? err.message : "Unable to check session. Try again.");
        }
        setChecking(false);
      },
    );
  }, []);

  useEffect(() => {
    const unauthorized = () => {
      generation.current += 1;
      setUsername(null);
      setError("Your session has ended. Sign in again.");
      setChecking(false);
    };
    window.addEventListener("homecam:unauthorized", unauthorized);
    void checkSession();
    return () => {
      generation.current += 1;
      window.removeEventListener("homecam:unauthorized", unauthorized);
    };
  }, [checkSession]);

  useEffect(() => {
    if (!username) return;
    const interval = window.setInterval(() => void checkSession(), 30000);
    const onFocus = () => void checkSession();
    window.addEventListener("focus", onFocus);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener("focus", onFocus);
    };
  }, [username, checkSession]);

  const login = async (name: string, password: string) => {
    generation.current += 1;
    const session = await api.login(name, password);
    setUsername(session.username);
    setError(null);
  };

  const logout = async () => {
    generation.current += 1;
    await api.logout();
    setUsername(null);
    setError(null);
  };

  return <AuthContext.Provider value={{ username, checking, error, checkSession, login, logout }}>{children}</AuthContext.Provider>;
}
