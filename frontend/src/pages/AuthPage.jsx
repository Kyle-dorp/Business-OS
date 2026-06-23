import { useState } from "react";

import { api, setToken } from "../api";

export default function AuthPage({ needsSetup, onAuthenticated }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event) {
    event.preventDefault();
    if (needsSetup && password !== confirm) {
      setError("Passwords do not match");
      return;
    }
    try {
      setBusy(true);
      setError("");
      const result = await api(needsSetup ? "/auth/setup" : "/auth/login", {
        method: "POST",
        body: JSON.stringify({ username: username.trim(), password }),
      });
      setToken(result.token);
      onAuthenticated(result.user);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-screen">
      <section className="auth-brand-panel">
        <div className="brand-orb brand-orb-one" />
        <div className="brand-orb brand-orb-two" />
        <div className="auth-brand-content">
          <div className="brand-mark">O</div>
          <span className="eyebrow light">BUSINESS OS</span>
          <h1>Run the whole business from one calm workspace.</h1>
          <p>
            Manage money, people, schedules, inventory, and daily work with a configurable
            assistant and one reliable source of truth.
          </p>
          <div className="auth-feature-row">
            <span>Flexible departments</span>
            <span>Connected operations</span>
            <span>Clear approvals</span>
          </div>
        </div>
      </section>

      <section className="auth-form-panel">
        <form className="auth-card" onSubmit={submit}>
          <div className="auth-card-heading">
            <span className="eyebrow">SECURE WORKSPACE</span>
            <h2>{needsSetup ? "Create the manager account" : "Welcome back"}</h2>
            <p>
              {needsSetup
                ? "This first account controls employees, schedules, and permissions."
                : "Sign in with the username and password your manager created."}
            </p>
          </div>

          {error && <div className="alert error">{error}</div>}

          <label className="field-label">
            Username
            <input
              autoFocus
              autoComplete="username"
              placeholder={needsSetup ? "Choose a manager username" : "Enter username"}
              value={username}
              onChange={(event) => setUsername(event.target.value)}
            />
          </label>

          <label className="field-label">
            Password
            <input
              type="password"
              autoComplete={needsSetup ? "new-password" : "current-password"}
              placeholder="At least 8 characters"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>

          {needsSetup && (
            <label className="field-label">
              Confirm password
              <input
                type="password"
                autoComplete="new-password"
                placeholder="Type it again"
                value={confirm}
                onChange={(event) => setConfirm(event.target.value)}
              />
            </label>
          )}

          <button className="primary-btn auth-submit" disabled={busy || !username.trim() || !password}>
            {busy ? "Please wait…" : needsSetup ? "Create workspace" : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}
