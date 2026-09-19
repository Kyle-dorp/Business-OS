/**
 * Who gets the assistant, and how much of the month any one of them may spend.
 *
 * Off for staff by default. A workspace that does not want to pay for its team
 * to have an assistant should not be paying for its team to have an assistant —
 * "pay for what you use" has to cut both ways or it is just a tagline.
 *
 * The per-user cap is not a cost control for us: the wallet already bounds the
 * total, and nothing can spend past it. It exists so one curious employee
 * cannot get through the month in an afternoon and leave the manager without
 * an assistant on the day they need one.
 */

import { useCallback, useEffect, useState } from "react";
import { api } from "../api";

/**
 * Suggested caps, with what each actually buys.
 *
 * An employee question costs about $0.004 — their context is their own record
 * rather than the whole business, which is roughly fifty times smaller. So
 * these numbers are far more generous than they look, and saying so is the
 * difference between somebody picking one and somebody guessing.
 */
const CAPS = [
  { dollars: 0, label: "No limit", detail: "anyone can use whatever the workspace has left" },
  { dollars: 0.5, label: "$0.50", detail: "around 130 questions each" },
  { dollars: 1, label: "$1.00", detail: "around 260 questions each" },
  { dollars: 2, label: "$2.00", detail: "around 520 questions each" },
];

export default function AssistantAccess() {
  const [usage, setUsage] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setUsage(await api("/ai/usage"));
    } catch (problem) {
      setError(problem?.message || "Could not read the assistant settings.");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function save(patch) {
    setSaving(true);
    setError("");
    try {
      const next = await api("/ai/settings", {
        method: "PUT",
        body: JSON.stringify(patch),
      });
      setUsage(next);
      // The confirmation is set after the response, not before. A "Saved"
      // that appears before the server agreed is a lie about half the time.
      setSaved("Saved");
      setTimeout(() => setSaved(""), 2400);
    } catch (problem) {
      setError(problem?.message || "That did not save.");
    } finally {
      setSaving(false);
    }
  }

  if (error && !usage) return <p className="eos-error">{error}</p>;
  if (!usage) return null;

  return (
    <section className="card assistant-access">
      <div className="assistant-access-head">
        <div>
          <h2>The assistant, for your team</h2>
          <p>
            Staff see only their own record — their shifts, hours, pay and
            requests. Never the books, the suppliers or anyone else&rsquo;s pay.
          </p>
        </div>
        {saved && <span className="assistant-access-saved">{saved}</span>}
      </div>

      <label className="assistant-toggle">
        <input
          type="checkbox"
          checked={usage.employees_enabled}
          disabled={saving}
          onChange={(event) => save({ employees_enabled: event.target.checked })}
        />
        <span>
          <strong>Let staff use the assistant</strong>
          <small>
            It comes out of the same credit as yours — $
            {usage.remaining.toFixed(2)} left this month.
          </small>
        </span>
      </label>

      {usage.employees_enabled && (
        <div className="assistant-caps">
          <p className="eyebrow">How much each person may use</p>
          <div className="assistant-cap-row">
            {CAPS.map((cap) => {
              const on = Math.abs((usage.per_user_cap ?? 0) - cap.dollars) < 0.001;
              return (
                <button
                  key={cap.label}
                  className={`assistant-cap${on ? " is-on" : ""}`}
                  aria-pressed={on}
                  disabled={saving}
                  onClick={() => save({ per_user_cap_dollars: cap.dollars })}
                >
                  <strong>{cap.label}</strong>
                  <small>{cap.detail}</small>
                </button>
              );
            })}
          </div>
          <p className="assistant-cap-note">
            A limit stops one person using the month in an afternoon. It never
            stops you — yours comes out of the workspace credit, not a personal
            allowance.
          </p>
        </div>
      )}

      {error && <p className="eos-error">{error}</p>}
    </section>
  );
}
