/**
 * What the assistant has cost this month, and what is left.
 *
 * The thing it replaces read `tokens_used` against `included_allowance` and
 * told somebody they had used 43% of 650,000 tokens. Nobody can act on that.
 * Measured against the real context sizes, 650,000 tokens was sixty-five
 * questions on a small workspace and six on a large one — so the same
 * percentage meant wildly different things and looked identical.
 *
 * It is money now, at what we pay Anthropic. A number somebody can reason
 * about, in the units they already think in.
 *
 * Collapsed it is one line: what is left. Expanded it says where the month
 * went and offers more. The expansion matters because "you have used your
 * credit" is only a fair thing to say to somebody who could see it coming.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";

const money = (value) =>
  value >= 1 ? `$${value.toFixed(2)}` : `$${value.toFixed(3).replace(/0$/, "")}`;

/** Green while there is room, amber when it is close, rose when it is gone. */
function toneFor(percent) {
  if (percent >= 100) return "is-empty";
  if (percent >= 80) return "is-low";
  return "";
}

export default function CreditMeter({ refreshKey = 0 }) {
  const [usage, setUsage] = useState(null);
  const [open, setOpen] = useState(false);
  const [breakdown, setBreakdown] = useState(null);
  const [error, setError] = useState("");
  const root = useRef(null);

  const load = useCallback(async () => {
    try {
      setUsage(await api("/ai/usage"));
      setError("");
    } catch (problem) {
      // A meter that cannot load is not worth an error state in the middle of
      // somebody's conversation. It hides.
      setError(problem.message || "unavailable");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  useEffect(() => {
    if (!open) return undefined;
    const away = (event) => {
      if (root.current && !root.current.contains(event.target)) setOpen(false);
    };
    const escape = (event) => event.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  // Only fetched when somebody opens the panel — it is owner-only and most
  // people looking at the meter just want the number on the front of it.
  useEffect(() => {
    if (!open || breakdown) return;
    api("/ai/breakdown")
      .then(setBreakdown)
      .catch(() => setBreakdown({ denied: true }));
  }, [open, breakdown]);

  if (error || !usage) return null;

  const percent = Math.min(usage.percent_used ?? 0, 100);
  const tone = toneFor(usage.percent_used ?? 0);

  return (
    <div className="credit-meter" ref={root}>
      <button
        className={`credit-trigger ${tone}`.trim()}
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        title={`${money(usage.spent)} of ${money(usage.included + usage.topped_up)} used this month`}
      >
        <span className="credit-dial" aria-hidden="true">
          <span className="credit-dial-fill" style={{ width: `${percent}%` }} />
        </span>
        <span className="credit-left">{money(usage.remaining)}</span>
        <span className="credit-word">left</span>
      </button>

      {open && (
        <div className="credit-panel" role="dialog" aria-label="Assistant usage">
          <p className="credit-panel-title">Assistant usage</p>

          <dl className="credit-rows">
            <div>
              <dt>Included this month</dt>
              <dd>{money(usage.included)}</dd>
            </div>
            {usage.topped_up > 0 && (
              <div>
                <dt>Credit you bought</dt>
                <dd>{money(usage.topped_up)}</dd>
              </div>
            )}
            <div>
              <dt>Used</dt>
              <dd className={tone}>{money(usage.spent)}</dd>
            </div>
            <div className="credit-rows-total">
              <dt>Left</dt>
              <dd>{money(usage.remaining)}</dd>
            </div>
          </dl>

          {usage.your_spend !== undefined && (
            <p className="credit-yours">
              You have used {money(usage.your_spend)}
              {usage.your_cap !== undefined && ` of your ${money(usage.your_cap)}`}.
            </p>
          )}

          {breakdown && !breakdown.denied && breakdown.by_feature?.length > 0 && (
            <div className="credit-breakdown">
              <p className="credit-panel-title">Where it went</p>
              {breakdown.by_feature.map((row) => (
                <div className="credit-line" key={row.feature}>
                  <span>{labelFor(row.feature)}</span>
                  <span>{money(row.spent)}</span>
                </div>
              ))}
            </div>
          )}

          <p className="credit-note">
            Charged at what we pay for it, with no markup. Anything you buy does
            not expire.
          </p>
        </div>
      )}
    </div>
  );
}

/** The feature names are internal keys; these are what they are called on screen. */
function labelFor(feature) {
  return (
    {
      agent: "Ask",
      assistant: "Scheduling AI",
      "my-assistant": "Staff assistant",
    }[feature] || feature
  );
}
