import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";

/**
 * Account security: who is locked out, issuing reset codes, and linking Google.
 *
 * Reset codes are shown exactly once. The server stores only a hash, so if this
 * screen is dismissed before the code is read out, nobody can recover it — a
 * new one has to be issued. The UI says so plainly rather than letting someone
 * discover it later.
 */

function ResetIssuer() {
  const [username, setUsername] = useState("");
  const [issued, setIssued] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  async function issue(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setIssued(null);
    try {
      setIssued(await api("/security/reset/issue", {
        method: "POST",
        body: JSON.stringify({ username: username.trim() }),
      }));
      setUsername("");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(issued.code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);   // clipboard is blocked in some contexts; the code is on screen
    }
  }

  return (
    <section className="card sec-card">
      <h3>Reset someone&rsquo;s password</h3>
      <p className="sec-blurb">
        Issues a one-time code. Read it to them directly — it is shown once and
        cannot be retrieved afterwards.
      </p>

      <form className="sec-inline-form" onSubmit={issue}>
        <input
          placeholder="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="off"
        />
        <button className="primary-btn" disabled={busy || !username.trim()}>
          {busy ? "Issuing…" : "Issue code"}
        </button>
      </form>

      {error && <p className="sec-error">{error}</p>}

      {issued && (
        <div className="sec-code-panel">
          <span className="sec-code-label">Code for {issued.username}</span>
          <div className="sec-code-row">
            <code>{issued.code}</code>
            <button type="button" className="ghost-btn" onClick={copy}>
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <small>
            Expires in {issued.expires_in_minutes} minutes. {issued.note}
          </small>
        </div>
      )}
    </section>
  );
}

function Lockouts() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api("/security/lockouts").then(setData).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, [load]);

  if (error) return <section className="card sec-card"><p className="sec-error">{error}</p></section>;
  if (!data) return <section className="card sec-card os-loading">Checking sign-in attempts…</section>;

  return (
    <section className="card sec-card">
      <h3>Sign-in attempts</h3>
      <p className="sec-blurb">
        {data.max_attempts} failed attempts within {data.window_minutes} minutes
        locks an account. One successful sign-in clears it.
      </p>

      {data.accounts.length === 0 ? (
        <p className="sec-clear">No failed sign-ins right now.</p>
      ) : (
        <table className="os-table">
          <thead><tr><th>Username</th><th>Failed</th><th>Status</th></tr></thead>
          <tbody>
            {data.accounts.map((a) => (
              <tr key={a.username}>
                <td>{a.username}</td>
                <td>{a.failed_attempts}</td>
                <td className={a.locked ? "sec-locked" : "sec-ok"}>
                  {a.locked ? "Locked" : "Watching"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function GoogleLink() {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const holder = useRef(null);

  const load = useCallback(() => {
    api("/auth/google/status").then(setStatus).catch(() => setStatus({ configured: false }));
  }, []);

  useEffect(() => { load(); }, [load]);

  const onCredential = useCallback(async (credential) => {
    setBusy(true);
    setError("");
    try {
      await api("/auth/google/link", { method: "POST", body: JSON.stringify({ credential }) });
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }, [load]);

  useEffect(() => {
    if (!status?.configured || status.linked || !holder.current) return undefined;
    let cancelled = false;

    function render() {
      if (cancelled || !window.google?.accounts?.id || !holder.current) return;
      api("/auth/google/config").then((cfg) => {
        if (cancelled || !cfg.client_id) return;
        window.google.accounts.id.initialize({
          client_id: cfg.client_id,
          callback: (r) => onCredential(r.credential),
        });
        window.google.accounts.id.renderButton(holder.current, {
          theme: "filled_black", size: "large", text: "continue_with", shape: "pill",
        });
      }).catch(() => {});
    }

    if (window.google?.accounts?.id) render();
    else {
      const s = document.createElement("script");
      s.src = "https://accounts.google.com/gsi/client";
      s.async = true; s.defer = true; s.onload = render;
      document.head.appendChild(s);
    }
    return () => { cancelled = true; };
  }, [status, onCredential]);

  async function unlink() {
    setBusy(true);
    setError("");
    try {
      await api("/auth/google/unlink", { method: "POST" });
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (!status) return null;

  if (!status.configured) {
    return (
      <section className="card sec-card">
        <h3>Google sign-in</h3>
        <p className="sec-blurb">
          Not configured on this deployment. Set <code>GOOGLE_CLIENT_ID</code> to enable it.
        </p>
      </section>
    );
  }

  return (
    <section className="card sec-card">
      <h3>Google sign-in</h3>
      {status.linked ? (
        <>
          <p className="sec-blurb">
            Linked to <strong>{status.email}</strong>. You can sign in with Google
            or your password.
          </p>
          <button className="ghost-btn" onClick={unlink} disabled={busy}>
            {busy ? "Working…" : "Unlink Google"}
          </button>
        </>
      ) : (
        <>
          <p className="sec-blurb">
            Link a Google account to sign in with one click. Available to owners,
            admins and managers.
          </p>
          <div ref={holder} />
        </>
      )}
      {error && <p className="sec-error">{error}</p>}
    </section>
  );
}

function EmailHealth() {
  const [data, setData] = useState(null);

  useEffect(() => {
    api("/email/status").then(setData).catch(() => setData({ configured: false, recent: [] }));
  }, []);

  if (!data) return null;

  return (
    <section className="card sec-card">
      <h3>Email</h3>
      {!data.configured ? (
        <>
          <p className="sec-blurb">
            Not configured. Bookings still work — nobody is told about them.
            Set <code>RESEND_API_KEY</code> and <code>EMAIL_FROM</code> to turn it on.
          </p>
        </>
      ) : (
        <>
          <p className="sec-blurb">Sending as <strong>{data.from_address}</strong>.</p>
          <div className="sec-email-stats">
            <span className="sec-ok">{data.sent} sent</span>
            {data.failed > 0 && <span className="sec-locked">{data.failed} failed</span>}
            {data.skipped > 0 && <span>{data.skipped} skipped</span>}
          </div>
        </>
      )}

      {data.recent?.length > 0 && (
        <table className="os-table sec-email-log">
          <thead><tr><th>To</th><th>What</th><th>Status</th></tr></thead>
          <tbody>
            {data.recent.slice(0, 8).map((r, i) => (
              <tr key={i}>
                <td>{r.to}</td>
                <td>{r.template.replace(/_/g, " ")}</td>
                <td className={r.status === "sent" ? "sec-ok" : r.status === "failed" ? "sec-locked" : ""}>
                  {r.status}
                  {r.error && <small title={r.error}> · {r.error.slice(0, 40)}</small>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

export default function SecurityPage() {
  return (
    <div className="page security-page">
      <div className="os-heading">
        <div>
          <span className="eyebrow">SECURITY</span>
          <h1>Accounts and access</h1>
          <p>Who is locked out, how to get them back in, and how you sign in.</p>
        </div>
      </div>

      <div className="sec-grid">
        <ResetIssuer />
        <Lockouts />
        <GoogleLink />
        <EmailHealth />
      </div>
    </div>
  );
}
