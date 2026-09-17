import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { ErrorState, Loading } from "../components/States";
import { useCountUp } from "../hooks/useCountUp";

/**
 * The first screen.
 *
 * What was here answered four questions every small-business app answers —
 * what is owed, what is owing, how many tasks, how many low-stock items — and
 * then filled the rest of the page with a panel reading "Sell. Deliver.
 * Record. Understand.", which is marketing copy inside the product.
 *
 * This answers the four only this product can, and every tile is a door.
 */

const VERDICT = {
  publish: { label: "Clear to publish", tone: "good" },
  review: { label: "Worth a look", tone: "warn" },
  fix: { label: "Needs sorting", tone: "bad" },
};

function money(cents) {
  const value = Math.round((cents || 0) / 100);
  return `${value < 0 ? "−" : ""}$${Math.abs(value).toLocaleString()}`;
}

function CountingMoney({ cents }) {
  return <>{money(useCountUp(cents || 0))}</>;
}

/**
 * Thirty days of cash, as a shape.
 *
 * Money in above the line, money out below it. One total says a business made
 * something; thirty figures say whether it is climbing or sliding, which is
 * the question somebody actually has on a Monday.
 */
function CashShape({ series }) {
  if (!series?.length) return null;

  const peak = Math.max(1, ...series.map((d) => Math.max(d.in, d.out)));
  const anyIn = series.some((d) => d.in > 0);
  const anyOut = series.some((d) => d.out > 0);
  const width = 100;
  const mid = 18;
  const step = width / Math.max(series.length - 1, 1);

  const path = (key, direction) =>
    series
      .map((d, i) => {
        const x = (i * step).toFixed(2);
        const y = (mid - direction * (d[key] / peak) * 15).toFixed(2);
        return `${i === 0 ? "M" : "L"}${x},${y}`;
      })
      .join(" ");

  return (
    <svg className="today-cash" viewBox={`0 0 ${width} 36`} preserveAspectRatio="none"
         role="img" aria-label="Cash in and out over the last thirty days">
      <line x1="0" y1={mid} x2={width} y2={mid} className="today-cash-axis" />
      {anyIn && <path d={path("in", 1)} className="today-cash-in" />}
      {anyOut && <path d={path("out", -1)} className="today-cash-out" />}
    </svg>
  );
}

export default function TodayPage({ onNavigate }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  const [setup, setSetup] = useState(null);

  const load = useCallback(async () => {
    setError("");
    try {
      const [today, onboarding] = await Promise.all([
        api("/platform/today"),
        // A checklist that will not load must not take the dashboard with it.
        api("/platform/onboarding").catch(() => null),
      ]);
      setData(today);
      setSetup(onboarding);
    } catch (err) {
      setError(err?.message || "Couldn't load your workspace.");
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (error && !data) {
    return (
      <div className="page">
        <section className="card"><ErrorState error={error} onRetry={load} /></section>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="page">
        <section className="card"><Loading lines={5} label="Reading your workspace" /></section>
      </div>
    );
  }

  const { week, money: cash, stock, attention } = data;
  const verdict = week?.verdict ? VERDICT[week.verdict] || VERDICT.review : null;

  return (
    <div className="page today-page">
      <div className="os-heading">
        <div>
          <span className="eyebrow">TODAY</span>
          <h1>What needs you</h1>
          <p>Your rota, your money, your stock — checked against each other.</p>
        </div>
        <button className="ghost-btn" onClick={load}>Refresh</button>
      </div>

      {/* The first ninety seconds. It reads the workspace rather than tracking
          a wizard, so it is true whether somebody followed it, ignored it, or
          did the work months ago in a different order — and it disappears for
          good once there is nothing left on it. */}
      {setup && !setup.complete && (
        <section className="card today-setup">
          <div className="today-setup-head">
            <div>
              <span className="today-tile-label">GETTING SET UP</span>
              <strong className="today-tile-lead">{setup.next.title}</strong>
              <p className="today-tile-note">{setup.next.why}</p>
            </div>
            <div className="today-setup-progress">
              <span>{setup.done} of {setup.total}</span>
              <span className="today-setup-track" aria-hidden="true">
                <span style={{ width: `${(setup.done / setup.total) * 100}%` }} />
              </span>
            </div>
          </div>

          <button type="button" className="primary-btn"
                  onClick={() => onNavigate?.(setup.next.tab)}>
            {setup.next.action}
          </button>

          <ul className="today-setup-list">
            {setup.steps.map((s) => (
              <li key={s.key} className={s.done ? "is-done" : ""}>
                <button type="button" onClick={() => onNavigate?.(s.tab)} disabled={s.done}>
                  <span className="today-setup-tick" aria-hidden="true">{s.done ? "✓" : ""}</span>
                  <span>{s.title}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="today-grid">

        {/* ---------------------------------------------- 1. is it safe to publish */}
        <button
          type="button"
          className={
            "card today-tile is-rota"
            + (verdict ? ` tone-${verdict.tone}` : "")
            + (week?.state === "checked"
               && ((week.blocking?.length || 0) + (week.advisories?.length || 0)) > 0
                 ? " is-tall" : "")
          }
          onClick={() => onNavigate?.(week?.state === "none" ? "manager" : "preflight")}
        >
          <span className="today-tile-label">THIS WEEK'S ROTA</span>

          {week?.state === "none" && (
            <>
              <strong className="today-tile-lead">No rota yet</strong>
              <p className="today-tile-note">
                Nothing is scheduled for the week of {week.week_start}. Build one
                and it gets checked against labor law, bookings, cost and stock
                before it goes out.
              </p>
              <span className="today-tile-go">Build this week →</span>
            </>
          )}

          {week?.state === "unchecked" && (
            <>
              <strong className="today-tile-lead">Not checked yet</strong>
              <p className="today-tile-note">
                There is a rota for {week.week_start}, but preflight could not
                run on it. Open it to see why.
              </p>
              <span className="today-tile-go">Open preflight →</span>
            </>
          )}

          {week?.state === "checked" && (
            <>
              <span className={`today-verdict tone-${verdict.tone}`}>{verdict.label}</span>
              <strong className="today-tile-lead">{week.headline}</strong>

              {week.blocking?.length > 0 && (
                <ul className="today-tile-list">
                  {week.blocking.slice(0, 3).map((b, i) => <li key={i}>{b}</li>)}
                </ul>
              )}
              {week.blocking?.length === 0 && week.advisories?.length > 0 && (
                <ul className="today-tile-list is-quiet">
                  {week.advisories.slice(0, 2).map((a, i) => <li key={i}>{a}</li>)}
                </ul>
              )}
              {week.blocking?.length === 0 && week.advisories?.length === 0 && (
                <p className="today-tile-note">
                  Legal, staffed, affordable and servable. Nothing to sort.
                </p>
              )}

              <span className="today-tile-go">See the full check →</span>
            </>
          )}
        </button>

        {/* -------------------------------------------------------- 2. the money */}
        <button type="button" className="card today-tile is-money"
                onClick={() => onNavigate?.("reports")}>
          <span className="today-tile-label">LAST 30 DAYS</span>

          <strong className={`today-tile-lead ${cash.net_cents >= 0 ? "is-up" : "is-down"}`}>
            <CountingMoney cents={cash.net_cents} />
          </strong>
          <span className="today-tile-sub">
            {cash.net_cents >= 0 ? "more in than out" : "more out than in"}
          </span>

          <CashShape series={cash.series} />

          <div className="today-money-split">
            <span className="is-in">In <strong>{money(cash.in_cents)}</strong></span>
            <span className="is-out">Out <strong>{money(cash.out_cents)}</strong></span>
          </div>

          <div className="today-money-owed">
            <span>Owed to you <strong>{money(cash.receivables_cents)}</strong></span>
            <span>You owe <strong>{money(cash.payables_cents)}</strong></span>
          </div>
        </button>

        {/* ------------------------------------------------- 3. what needs a human */}
        <section className="card today-tile is-attention">
          <span className="today-tile-label">WAITING ON YOU</span>

          {attention.length === 0 ? (
            <>
              <strong className="today-tile-lead">Nothing waiting</strong>
              <p className="today-tile-note">
                No overdue invoices, no late bills, nothing blocking the rota.
              </p>
            </>
          ) : (
            <ul className="today-attention">
              {attention.map((a, i) => (
                <li key={i}>
                  <button type="button" className={`today-attention-row urgency-${a.urgency}`}
                          onClick={() => onNavigate?.(a.tab)}>
                    <span className="today-attention-dot" aria-hidden="true" />
                    <span className="today-attention-body">
                      <strong>{a.text}</strong>
                      {a.detail && <span>{a.detail}</span>}
                    </span>
                    <span className="today-attention-go" aria-hidden="true">→</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* --------------------------------------------------- 4. what runs out */}
        <button type="button" className="card today-tile is-stock"
                onClick={() => onNavigate?.("inventory-intel")}>
          <span className="today-tile-label">RUNS OUT FIRST</span>

          {stock.length === 0 ? (
            <>
              <strong className="today-tile-lead">Nothing running low</strong>
              <p className="today-tile-note">
                Stock covers the week ahead at the rate you have been using it.
              </p>
            </>
          ) : (
            <ul className="today-stock">
              {stock.map((s, i) => (
                <li key={i} className={`sev-${s.severity}`}>
                  <span className="today-stock-name">{s.item}</span>
                  <span className="today-stock-cover">
                    {s.days_of_cover != null ? `${s.days_of_cover}d left` : s.reason || "low"}
                  </span>
                  <span className="today-stock-bar" aria-hidden="true">
                    <span style={{
                      width: `${Math.max(4, Math.min(100,
                        s.days_of_cover != null ? (s.days_of_cover / 7) * 100
                                                : (s.on_hand / Math.max(s.needed, 1)) * 100))}%`,
                    }} />
                  </span>
                </li>
              ))}
            </ul>
          )}
          <span className="today-tile-go">Stock intelligence →</span>
        </button>
      </div>
    </div>
  );
}
