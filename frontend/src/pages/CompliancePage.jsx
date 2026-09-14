import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { ErrorState, Loading } from "../components/States";

/**
 * Labor rules and the employee facts they depend on.
 *
 * The rule engine covers eleven jurisdictions, but it can only apply what it
 * has been told. Without a jurisdiction it runs federal-only; without a date of
 * birth the minor rules never fire; without an hourly rate every violation
 * reads $0 and a real problem looks free.
 *
 * So this screen leads with what is *missing*, not with what is configured.
 */

const INDUSTRIES = [
  ["general", "General"],
  ["food_service", "Food service"],
  ["retail", "Retail"],
  ["hospitality", "Hospitality"],
  ["manufacturing", "Manufacturing"],
  ["professional", "Professional services"],
  ["healthcare", "Healthcare"],
];

function Rule({ label, value, suffix = "" }) {
  if (value === null || value === undefined || value === false) return null;
  return (
    <div className="cmp-rule">
      <span>{label}</span>
      <strong>{value}{suffix}</strong>
    </div>
  );
}

function Jurisdiction({ profile, options, onSaved }) {
  const [draft, setDraft] = useState({
    jurisdiction: profile.jurisdiction,
    industry: profile.industry,
    track_minors: profile.track_minors,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const dirty =
    draft.jurisdiction !== profile.jurisdiction ||
    draft.industry !== profile.industry ||
    draft.track_minors !== profile.track_minors;

  const chosen = options.find((o) => o.key === draft.jurisdiction);

  async function save() {
    setSaving(true);
    setError("");
    try {
      await api("/ops/compliance/profile", {
        method: "PUT",
        body: JSON.stringify({ ...draft, employee_count: profile.actual_headcount }),
      });
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="card cmp-card">
      <h3>Where you operate</h3>
      <p className="cmp-blurb">
        Picks which labor rules apply. Get this wrong and every warning is wrong.
      </p>

      <div className="cmp-fields">
        <label className="os-field">
          <span>Jurisdiction</span>
          <select
            value={draft.jurisdiction}
            onChange={(e) => setDraft({ ...draft, jurisdiction: e.target.value })}
          >
            {options.map((o) => (
              <option key={o.key} value={o.key}>
                {o.name}{o.predictive_scheduling ? " — Fair Workweek" : ""}
              </option>
            ))}
          </select>
        </label>

        <label className="os-field">
          <span>Industry</span>
          <select
            value={draft.industry}
            onChange={(e) => setDraft({ ...draft, industry: e.target.value })}
          >
            {INDUSTRIES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
      </div>

      <label className="cmp-toggle">
        <input
          type="checkbox"
          checked={draft.track_minors}
          onChange={(e) => setDraft({ ...draft, track_minors: e.target.checked })}
        />
        <span>
          <strong>Check minor-hours rules</strong>
          <small>School-week caps, the 7am floor, and the summer curfew extension.</small>
        </span>
      </label>

      {/* Chosen is not always effective. Several ordinances only bite above a
          headcount or within an industry, and letting somebody believe they are
          covered when they are not is worse than not offering the feature. */}
      {profile.falling_back && (
        <div className="alert error cmp-fallback">
          <strong>{chosen?.name} is not in force here.</strong>{" "}
          {chosen?.applies_above_employees > 0 &&
            `It applies above ${chosen.applies_above_employees} employees and you have ${profile.actual_headcount}. `}
          Federal rules are being applied instead.
        </div>
      )}

      <div className="cmp-effective">
        <span className="cmp-effective-label">Currently enforcing</span>
        <strong>{profile.effective.name}</strong>
        <div className="cmp-rules">
          <Rule label="Advance notice" value={profile.effective.advance_notice_days || null} suffix=" days" />
          <Rule label="Rest between shifts" value={profile.effective.min_rest_hours} suffix=" hrs" />
          <Rule label="Daily overtime after" value={profile.effective.daily_overtime_hours} suffix=" hrs" />
          <Rule label="Meal break after" value={profile.effective.meal_break_after_hours} suffix=" hrs" />
          <Rule label="Rest day after" value={profile.effective.max_consecutive_days} suffix=" days" />
        </div>
        {profile.effective.citation && <small>{profile.effective.citation}</small>}
      </div>

      {error && <p className="sec-error">{error}</p>}
      {dirty && (
        <div className="cmp-actions">
          <button className="primary-btn" onClick={save} disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      )}
    </section>
  );
}

function EmployeeRow({ row, onSaved }) {
  const [draft, setDraft] = useState({
    date_of_birth: row.date_of_birth,
    hourly_rate: row.hourly_rate || "",
    exempt: row.exempt,
    is_student: row.is_student,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const dirty =
    draft.date_of_birth !== row.date_of_birth ||
    Number(draft.hourly_rate || 0) !== row.hourly_rate ||
    draft.exempt !== row.exempt ||
    draft.is_student !== row.is_student;

  async function save() {
    setSaving(true);
    setError("");
    try {
      await api("/ops/compliance/employees", {
        method: "PUT",
        body: JSON.stringify({
          employee_id: row.employee_id,
          date_of_birth: draft.date_of_birth || "",
          hourly_rate: Number(draft.hourly_rate) || 0,
          exempt: draft.exempt,
          is_student: draft.is_student,
        }),
      });
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <tr className={row.missing.length ? "cmp-incomplete" : ""}>
      <td>
        <strong>{row.name}</strong>
        <small>{row.department}</small>
      </td>
      <td>
        <input
          type="date"
          value={draft.date_of_birth}
          onChange={(e) => setDraft({ ...draft, date_of_birth: e.target.value })}
        />
      </td>
      <td>
        <div className="cmp-rate">
          <span>$</span>
          <input
            type="number" min="0" step="0.25" placeholder="0.00"
            value={draft.hourly_rate}
            onChange={(e) => setDraft({ ...draft, hourly_rate: e.target.value })}
          />
        </div>
      </td>
      <td className="cmp-flags">
        <label title="Salaried-exempt staff are outside overtime rules">
          <input type="checkbox" checked={draft.exempt}
                 onChange={(e) => setDraft({ ...draft, exempt: e.target.checked })} />
          <span>Exempt</span>
        </label>
        <label title="School-week hour limits apply to student minors">
          <input type="checkbox" checked={draft.is_student}
                 onChange={(e) => setDraft({ ...draft, is_student: e.target.checked })} />
          <span>Student</span>
        </label>
      </td>
      <td className="cmp-row-action">
        {error && <span className="cmp-row-error">{error}</span>}
        {dirty ? (
          <button className="primary-btn" onClick={save} disabled={saving}>
            {saving ? "…" : "Save"}
          </button>
        ) : row.missing.length ? (
          <span className="cmp-missing">Needs {row.missing.join(" + ")}</span>
        ) : (
          <span className="cmp-done">Complete</span>
        )}
      </td>
    </tr>
  );
}

export default function CompliancePage() {
  const [profile, setProfile] = useState(null);
  const [options, setOptions] = useState([]);
  const [staff, setStaff] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [p, j, e] = await Promise.all([
        api("/ops/compliance/profile"),
        api("/ops/compliance/jurisdictions"),
        api("/ops/compliance/employees"),
      ]);
      setProfile(p);
      setOptions(j.jurisdictions);
      setStaff(e);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const readiness = useMemo(() => {
    if (!staff || staff.total === 0) return null;
    return Math.round((staff.complete / staff.total) * 100);
  }, [staff]);

  if (error) return <div className="page"><section className="card"><ErrorState error={error} onRetry={load} /></section></div>;
  if (!profile || !staff) return <div className="page"><section className="card"><Loading lines={4} label="Loading rules" /></section></div>;

  return (
    <div className="page compliance-page">
      <div className="os-heading">
        <div>
          <span className="eyebrow">LABOR RULES</span>
          <h1>What the law expects of you</h1>
          <p>Set this once. Every schedule gets checked against it before it publishes.</p>
        </div>
        {readiness !== null && (
          <div className="cmp-readiness">
            <div className="cmp-readiness-bar">
              <span style={{
                width: `${readiness}%`,
                background: readiness === 100 ? "var(--mint)" : "var(--amber)",
              }} />
            </div>
            <small>{staff.complete} of {staff.total} employees ready to check</small>
          </div>
        )}
      </div>

      <Jurisdiction profile={profile} options={options} onSaved={load} />

      <section className="card cmp-card">
        <h3>Employee details</h3>
        <p className="cmp-blurb">{staff.why_it_matters}</p>

        {staff.total === 0 ? (
          <p className="cmp-empty">No active employees yet. Add staff first and they will appear here.</p>
        ) : (
          <div className="os-table-wrap cmp-table-wrap">
            <table className="os-table cmp-table">
              <thead>
                <tr>
                  <th>Employee</th>
                  <th>Date of birth</th>
                  <th>Hourly rate</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {staff.employees.map((row) => (
                  <EmployeeRow key={row.employee_id} row={row} onSaved={load} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
