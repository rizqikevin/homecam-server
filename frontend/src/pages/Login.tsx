import { useState } from "react";
import type { FormEvent } from "react";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const { login, error: sessionError, checkSession } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [visible, setVisible] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    setPending(true);
    setError(null);
    try {
      await login(username, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to sign in. Try again.");
      setPassword("");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-panel" aria-labelledby="login-title">
        <div className="auth-brand">HomeCam <span>Server</span></div>
        <h1 id="login-title">Sign in</h1>
        <p className="auth-description">Access your live camera, recordings, and settings.</p>
        <form onSubmit={submit} className="auth-form" aria-busy={pending}>
          <label htmlFor="username">Username</label>
          <input id="username" name="username" autoComplete="username" autoCapitalize="none" spellCheck={false} required maxLength={256} value={username} onChange={(event) => setUsername(event.target.value)} disabled={pending} autoFocus />
          <label htmlFor="password">Password</label>
          <input id="password" name="password" type={visible ? "text" : "password"} autoComplete="current-password" required maxLength={1024} value={password} onChange={(event) => setPassword(event.target.value)} disabled={pending} aria-describedby={error || sessionError ? "login-error" : undefined} />
          <label className="auth-show-password"><input type="checkbox" checked={visible} onChange={(event) => setVisible(event.target.checked)} />Show password</label>
          {(error || sessionError) && <p id="login-error" className="auth-error" role="alert">{error || sessionError}</p>}
          <button type="submit" className="btn auth-submit" disabled={pending}>{pending ? "Signing in…" : "Sign in"}</button>
        </form>
        {sessionError && <button type="button" className="btn auth-retry" onClick={() => void checkSession()}>Retry connection</button>}
      </section>
    </main>
  );
}
