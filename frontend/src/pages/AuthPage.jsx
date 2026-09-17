import { useEffect, useRef, useState } from "react";

import { api, setToken } from "../api";

/**
 * Sign-in, first-run setup, and reset-code redemption.
 *
 * Three modes rather than three routes, because this screen is the only thing
 * an unauthenticated visitor can reach and routing would add a dependency for
 * one decision.
 */

function GoogleButton({ onCredential, onError }) {
  const [config, setConfig] = useState(null);
  const holder = useRef(null);

  useEffect(() => {
    api("/auth/google/config")
      .then((c) => c.enabled && setConfig(c))
      .catch(() => {});   // not configured is a normal state, not an error
  }, []);

  useEffect(() => {
    if (!config?.client_id || !holder.current) return undefined;

    let cancelled = false;

    function render() {
      if (cancelled || !window.google?.accounts?.id || !holder.current) return;
      window.google.accounts.id.initialize({
        client_id: config.client_id,
        callback: (response) => onCredential(response.credential),
      });
      window.google.accounts.id.renderButton(holder.current, {
        theme: "filled_black",
        size: "large",
        width: 320,
        text: "signin_with",
        shape: "pill",
      });
    }

    if (window.google?.accounts?.id) {
      render();
    } else {
      const script = document.createElement("script");
      script.src = "https://accounts.google.com/gsi/client";
      script.async = true;
      script.defer = true;
      script.onload = render;
      script.onerror = () => onError?.("Google sign-in could not load.");
      document.head.appendChild(script);
    }

    return () => { cancelled = true; };
  }, [config, onCredential, onError]);

  if (!config) return null;

  return (
    <div className="auth-google">
      <div className="auth-divider"><span>or</span></div>
      <div ref={holder} className="auth-google-button" />
      <small>For owners and managers. Staff use the credentials their manager issued.</small>
    </div>
  );
}

export default function AuthPage({ needsSetup, onAuthenticated }) {
  const [mode, setMode] = useState(needsSetup ? "setup" : "signin");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [code, setCode] = useState("");
  const [businessName, setBusinessName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => { setMode(needsSetup ? "setup" : "signin"); }, [needsSetup]);

  function reset(next) {
    setMode(next);
    setError("");
    setNotice("");
    setPassword("");
    setConfirm("");
    setCode("");
    setBusinessName("");
  }

  async function submit(event) {
    event.preventDefault();
    setError("");

    const needsConfirm = mode === "setup" || mode === "signup" || mode === "recover";
    if (needsConfirm && password !== confirm) return setError("Passwords do not match.");
    if (needsConfirm && password.length < 8) {
      return setError("Use at least 8 characters.");
    }

    setBusy(true);
    try {
      if (mode === "recover") {
        await api("/security/reset/redeem", {
          method: "POST",
          body: JSON.stringify({
            username: username.trim(),
            code: code.trim().toUpperCase(),
            new_password: password,
          }),
        });
        reset("signin");
        setNotice("Password changed. Sign in with your new password.");
        return;
      }

      const endpoint = {
        setup: "/auth/setup",
        signup: "/auth/signup",
        signin: "/auth/login",
      }[mode];
      const body =
        mode === "signup"
          ? { username: username.trim(), password, business_name: businessName.trim() }
          : { username: username.trim(), password };

      const result = await api(endpoint, { method: "POST", body: JSON.stringify(body) });
      setToken(result.token);
      onAuthenticated(result.user);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function googleSignIn(credential) {
    setBusy(true);
    setError("");
    try {
      const result = await api("/auth/google/login", {
        method: "POST",
        body: JSON.stringify({ credential }),
      });
      setToken(result.token);
      onAuthenticated(result.user);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const heading = {
    setup: "Create the manager account",
    signup: "Start your workspace",
    signin: "Welcome back",
    recover: "Reset your password",
  }[mode];

  const blurb = {
    setup: "This first account controls employees, schedules, and permissions.",
    signup: "One account, one bill, everything in one place. Takes about a minute.",
    signin: "Sign in with the username and password your manager created.",
    recover: "Enter the code your manager gave you, then choose a new password.",
  }[mode];

  const canSubmit =
    mode === "recover"
      ? username.trim() && code.trim() && password && confirm
      : username.trim() && password &&
        (mode === "signin" || confirm);

  return (
    <main className="auth-screen">
      <section className="auth-brand-panel">
        <div className="brand-orb brand-orb-one" />
        <div className="brand-orb brand-orb-two" />
        <div className="auth-brand-content">
          <div className="brand-mark">E</div>
          <span className="eyebrow light">BUSINESS-EOS</span>
          <h1>Run the whole business from one calm workspace.</h1>
          <p>
            Money, people, schedules, stock and daily work in one place — with an
            assistant that can actually answer, because it can see all of it.
          </p>
          <div className="auth-feature-row">
            <span>One login</span>
            <span>One bill</span>
            <span>Numbers that agree</span>
          </div>
        </div>
      </section>

      <section className="auth-form-panel">
        <form className="auth-card" onSubmit={submit}>
          <div className="auth-card-heading">
            <span className="eyebrow">SECURE WORKSPACE</span>
            <h2>{heading}</h2>
            <p>{blurb}</p>
          </div>

          {error && <div className="alert error">{error}</div>}
          {notice && <div className="alert notice">{notice}</div>}

          {mode === "signup" && (
            <label className="field-label">
              Business name
              <input
                autoFocus
                autoComplete="organization"
                placeholder="Kyle's Barbershop"
                value={businessName}
                onChange={(e) => setBusinessName(e.target.value)}
              />
            </label>
          )}

          <label className="field-label">
            Username
            <input
              autoFocus={mode !== "signup"}
              autoComplete="username"
              placeholder={
                mode === "setup"
                  ? "Choose a manager username"
                  : mode === "signup"
                  ? "Choose a username"
                  : "Enter username"
              }
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </label>

          {mode === "recover" && (
            <label className="field-label">
              Reset code
              <input
                placeholder="XXXX-XXXX"
                value={code}
                autoComplete="one-time-code"
                onChange={(e) => setCode(e.target.value.toUpperCase())}
              />
            </label>
          )}

          <label className="field-label">
            {mode === "signin" ? "Password" : "New password"}
            <input
              type="password"
              autoComplete={mode === "signin" ? "current-password" : "new-password"}
              placeholder="At least 8 characters"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>

          {(mode === "setup" || mode === "signup" || mode === "recover") && (
            <label className="field-label">
              Confirm password
              <input
                type="password"
                autoComplete="new-password"
                placeholder="Type it again"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
              />
            </label>
          )}

          <button className="primary-btn auth-submit" disabled={busy || !canSubmit}>
            {busy
              ? "Please wait…"
              : mode === "setup" || mode === "signup"
              ? "Create workspace"
              : mode === "recover"
              ? "Set new password"
              : "Sign in"}
          </button>

          {mode === "signin" && (
            <>
              <button type="button" className="auth-link" onClick={() => reset("signup")}>
                New here? Start a workspace
              </button>
              <button type="button" className="auth-link" onClick={() => reset("recover")}>
                Locked out? Use a reset code
              </button>
              <GoogleButton onCredential={googleSignIn} onError={setError} />
            </>
          )}

          {mode === "signup" && (
            <button type="button" className="auth-link" onClick={() => reset("signin")}>
              Already have an account? Sign in
            </button>
          )}

          {mode === "recover" && (
            <button type="button" className="auth-link" onClick={() => reset("signin")}>
              Back to sign in
            </button>
          )}
        </form>
      </section>
    </main>
  );
}
