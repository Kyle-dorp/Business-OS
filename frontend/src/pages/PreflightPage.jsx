import { useEffect, useState } from "react";
import { api } from "../api";

/**
 * Pre-publish check.
 *
 * Four questions answered at once — legal, staffed, affordable, servable —
 * because the schedule, the booking calendar, the ledger and the stockroom are
 * the same database. A scheduler that can only see shifts cannot do this.
 */

const VERDICT = {
  publish: { label: "Clear to publish", tone: "good" },
  review: { label: "Worth a look", tone: "warn" },
  fix: { label: "Needs sorting first", tone: "bad" },
};

function money(n) {
  if (n === null || n === undefined) return "—";
  return `$${Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

export default function PreflightPage() {
  const [schedules, setSchedules] = useState([]);
  const [selected, setSelected] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/schedules")
      .then((rows) => {
        const list = Array.isArray(rows) ? rows : [];
        setSchedules(list);
        if (list.length) setSelected(String(list[0].id));
      })
      .catch((err) => setError(err?.message || "Couldn't load schedules."));
  }, []);

  useEffect(() => {
    if (!selected) return;
    setLoading(true);
    setError("");
    api(`/ops/preflight/${selected}`)
      .then(setResult)
      .catch((err) => {
        setResult(null);
        setError(err?.message || "Preflight couldn't run on that schedule.");
      })
      .finally(() => setLoading(false));
  }, [selected]);

  const verdict = result ? VERDICT[result.verdict] || VERDICT.review : null;

  return (
    <div className="page preflight-page">
      <div className="os-heading">
        <div>
          <span className="eyebrow">PREFLIGHT</span>
          <h1>Before this goes out</h1>
          <p>Legal, staffing, cost and stock — checked together, against real data.</p>
        </div>
        <div className="os-field">
          <label htmlFor="pf-schedule">Schedule</label>
          <select id="pf-schedule" value={selected} onChange={(e) => setSelected(e.target.value)}>
            {schedules.length === 0 && <option value="">No schedules yet</option>}
            {schedules.map((s) => (
              <option key={s.id} value={s.id}>
                Week of {s.week_start} — {s.status}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && <div className="card preflight-error">{error}</div>}
      {loading && <div className="card os-loading">Running four checks…</div>}

      {result && !loading && (
        <>
          <section className={`card preflight-verdict tone-${verdict.tone}`}>
            <div>
              <span className="preflight-verdict-label">{verdict.label}</span>
              <h2>{result.headline}</h2>
            </div>
            {result.checks?.compliance?.estimated_exposure > 0 && (
              <div className="preflight-exposure">
                <span>Estimated exposure</span>
                <strong>{money(result.checks.compliance.estimated_exposure)}</strong>
              </div>
            )}
          </section>

          {result.blocking?.length > 0 && (
            <section className="card preflight-list is-blocking">
              <h3>Blocking</h3>
              <ul>{result.blocking.map((b, i) => <li key={i}>{b}</li>)}</ul>
            </section>
          )}

          {result.advisories?.length > 0 && (
            <section className="card preflight-list is-advisory">
              <h3>Worth knowing</h3>
              <ul>{result.advisories.map((a, i) => <li key={i}>{a}</li>)}</ul>
            </section>
          )}

          <div className="preflight-grid">
            {/* 1 — legal */}
            <section className="card">
              <h3>Labor law</h3>
              {result.checks.compliance.findings?.length === 0 ? (
                <p className="preflight-clear">Nothing flagged.</p>
              ) : (
                <ul className="preflight-findings">
                  {result.checks.compliance.findings.map((f, i) => (
                    <li key={i} className={`sev-${f.severity}`}>
                      <div className="finding-top">
                        <strong>{f.employee_name || f.date || "Schedule"}</strong>
                        {f.exposure > 0 && <span className="finding-cost">{money(f.exposure)}</span>}
                      </div>
                      <p>{f.message}</p>
                      {f.citation && <small>{f.citation}</small>}
                    </li>
                  ))}
                </ul>
              )}
              <p className="preflight-disclaimer">{result.checks.compliance.disclaimer}</p>
            </section>

            {/* 2 — staffing against bookings */}
            <section className="card">
              <h3>Staffed for what's booked</h3>
              {result.checks.coverage?.length === 0 ? (
                <p className="preflight-clear">No shifts on this schedule.</p>
              ) : (
                <table className="os-table">
                  <thead>
                    <tr><th>Day</th><th>Booked</th><th>Staffed</th><th>Status</th></tr>
                  </thead>
                  <tbody>
                    {result.checks.coverage.map((d) => (
                      <tr key={d.date}>
                        <td>{d.date}</td>
                        <td>{d.bookings} · {d.booked_hours}h</td>
                        <td>{d.staffed_hours}h</td>
                        <td className={`cov-${d.status}`}>{d.status.replace(/_/g, " ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>

            {/* 3 — affordability */}
            <section className="card">
              <h3>Cost against forecast</h3>
              <div className="os-metrics compact">
                <article>
                  <span>Labor cost</span>
                  <strong>{money(result.checks.cost.labor_cost)}</strong>
                  <small>scheduled</small>
                </article>
                <article>
                  <span>Forecast revenue</span>
                  <strong>{money(result.checks.cost.forecast_revenue)}</strong>
                  <small>bookings + trailing average</small>
                </article>
                <article>
                  <span>Labor share</span>
                  <strong className={`cost-${result.checks.cost.status}`}>
                    {result.checks.cost.labor_percent ?? "—"}%
                  </strong>
                  <small>{result.checks.cost.status?.replace(/_/g, " ")}</small>
                </article>
              </div>
            </section>

            {/* 4 — can you serve it */}
            <section className="card">
              <h3>Stock for the week</h3>
              {result.checks.stock?.length === 0 ? (
                <p className="preflight-clear">Nothing projected to run out.</p>
              ) : (
                <ul className="preflight-findings">
                  {result.checks.stock.map((s, i) => (
                    <li key={i} className={`sev-${s.severity === "high" ? "violation" : "warning"}`}>
                      <div className="finding-top">
                        <strong>{s.item}</strong>
                        <span className="finding-cost">{s.days_of_cover}d cover</span>
                      </div>
                      <p>
                        {s.on_hand} on hand, about {s.needed} needed — short by {s.shortfall}.
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  );
}
