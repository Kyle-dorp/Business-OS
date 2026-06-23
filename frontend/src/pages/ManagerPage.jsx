import { useEffect, useMemo, useState } from "react";

import { api } from "../api";
import {
  DAYS,
  DAY_NAMES,
  formatDate,
  formatRole,
  formatClock,
  formatWeekRange,
  shiftWeek,
  toIsoDate,
  weekDates,
  confirmOncePerSession,
} from "../utils";

function currentMonday() {
  const today = new Date();
  const day = today.getDay();
  today.setDate(today.getDate() + (day === 0 ? -6 : 1 - day));
  return toIsoDate(today);
}

function emptyLaborBlock(date) {
  return {
    clientId: `${Date.now()}-${Math.random()}`,
    date,
    whole_day: false,
    start_time: "10:30",
    end_time: "21:00",
    budget_mode: "sales_percent",
    projected_sales: "",
    min_labor_percent: "",
    max_labor_percent: "",
    max_labor_hours: "",
    max_labor_dollars: "",
  };
}

function projectionToDraft(row) {
  let budget_mode = "sales_percent";
  if (row.max_labor_hours !== null) budget_mode = "max_hours";
  if (row.max_labor_dollars !== null) budget_mode = "max_dollars";
  return {
    ...row,
    whole_day: !row.start_time && !row.end_time,
    budget_mode,
    projected_sales: row.projected_sales ?? "",
    min_labor_percent: row.min_labor_percent ?? row.labor_percent ?? "",
    max_labor_percent: row.max_labor_percent ?? row.labor_percent ?? "",
    max_labor_hours: row.max_labor_hours ?? "",
    max_labor_dollars: row.max_labor_dollars ?? "",
  };
}

const EMPTY_CREW = {
  name: "",
  apply_mode: "date",
  date: "",
  day_of_week: -1,
  start_time: "10:30",
  end_time: "21:00",
  position_ids: [],
  departments: [],
  roles: [],
  minimum_count: 1,
  preferred_count: 4,
  hard_minimum: true,
  active: true,
};

function crewToDraft(row) {
  return {
    ...row,
    apply_mode: row.date ? "date" : "recurring",
    position_ids: row.position_ids || [],
    departments: row.departments || [],
    roles: row.roles || [],
  };
}


function toggleArray(source, value) {
  return source.includes(value) ? source.filter((item) => item !== value) : [...source, value];
}

function LaborEditor({
  draft,
  onChange,
  onSave,
  onDelete,
  isNew = false,
  defaultMin = 18,
  defaultMax = 20,
}) {
  return (
    <div className="labor-block-editor">
      <div className="labor-block-head">
        <label className="switch-line">
          <input
            type="checkbox"
            checked={draft.whole_day}
            onChange={(event) => onChange({ whole_day: event.target.checked })}
          />
          <span>Whole day</span>
        </label>
        <select
          value={draft.budget_mode}
          onChange={(event) => onChange({ budget_mode: event.target.value })}
        >
          <option value="sales_percent">Sales + labor range</option>
          <option value="max_hours">Maximum labor hours</option>
          <option value="max_dollars">Maximum labor dollars</option>
        </select>
        <button className="icon-delete" type="button" onClick={onDelete} aria-label="Remove block">×</button>
      </div>

      {!draft.whole_day && (
        <div className="time-window-grid">
          <label>Start<input type="time" value={draft.start_time} onChange={(event) => onChange({ start_time: event.target.value })} /></label>
          <label>End<input type="time" value={draft.end_time} onChange={(event) => onChange({ end_time: event.target.value })} /></label>
        </div>
      )}

      {draft.budget_mode === "sales_percent" && (
        <div className="labor-range-grid">
          <label>Projected sales<input type="text" inputMode="decimal" placeholder="9000" value={draft.projected_sales} onChange={(event) => onChange({ projected_sales: event.target.value })} /></label>
          <label>Minimum %<input type="text" inputMode="decimal" placeholder={String(defaultMin)} value={draft.min_labor_percent} onChange={(event) => onChange({ min_labor_percent: event.target.value })} /></label>
          <label>Maximum %<input type="text" inputMode="decimal" placeholder={String(defaultMax)} value={draft.max_labor_percent} onChange={(event) => onChange({ max_labor_percent: event.target.value })} /></label>
        </div>
      )}

      {draft.budget_mode === "max_hours" && (
        <label className="single-value-field">Maximum labor hours<input type="text" inputMode="decimal" placeholder="32" value={draft.max_labor_hours} onChange={(event) => onChange({ max_labor_hours: event.target.value })} /></label>
      )}
      {draft.budget_mode === "max_dollars" && (
        <label className="single-value-field">Maximum labor dollars<input type="text" inputMode="decimal" placeholder="600" value={draft.max_labor_dollars} onChange={(event) => onChange({ max_labor_dollars: event.target.value })} /></label>
      )}

      <button className="small-btn" type="button" onClick={onSave}>{isNew ? "Add block" : "Save changes"}</button>
    </div>
  );
}

function CrewForm({ value, onChange, onSubmit, submitLabel, positions, departments }) {
  return (
    <div className="crew-form">
      <div className="crew-basic-grid">
        <label>Name<input placeholder="Lunch rush, catering opener…" value={value.name} onChange={(event) => onChange({ ...value, name: event.target.value })} /></label>
        <label>Applies to<select value={value.apply_mode} onChange={(event) => onChange({ ...value, apply_mode: event.target.value })}><option value="date">Specific date</option><option value="recurring">Recurring weekday</option></select></label>
        {value.apply_mode === "date" ? (
          <label>Date<input type="date" value={value.date} onChange={(event) => onChange({ ...value, date: event.target.value })} /></label>
        ) : (
          <label>Day<select value={value.day_of_week} onChange={(event) => onChange({ ...value, day_of_week: Number(event.target.value) })}><option value={-1}>Every day</option>{DAY_NAMES.map((day, index) => <option value={index} key={day}>{day}</option>)}</select></label>
        )}
        <label>Start<input type="time" value={value.start_time} onChange={(event) => onChange({ ...value, start_time: event.target.value })} /></label>
        <label>End<input type="time" value={value.end_time} onChange={(event) => onChange({ ...value, end_time: event.target.value })} /></label>
        <label>Minimum crew<input type="text" inputMode="numeric" placeholder="1" value={value.minimum_count} onChange={(event) => onChange({ ...value, minimum_count: event.target.value })} /></label>
        <label>Target crew<input type="text" inputMode="numeric" placeholder="4" value={value.preferred_count} onChange={(event) => onChange({ ...value, preferred_count: event.target.value })} /></label>
      </div>

      <div className="crew-filter-grid">
        <fieldset><legend>Department (optional)</legend>{departments.map((item) => <label className="check-chip" key={item.id}><input type="checkbox" checked={value.departments.includes(item.name)} onChange={() => onChange({ ...value, departments: toggleArray(value.departments, item.name) })} />{item.name}</label>)}</fieldset>
        <fieldset><legend>Role (optional)</legend>{["employee", "shift_lead", "gm"].map((item) => <label className="check-chip" key={item}><input type="checkbox" checked={value.roles.includes(item)} onChange={() => onChange({ ...value, roles: toggleArray(value.roles, item) })} />{formatRole(item)}</label>)}</fieldset>
        <fieldset className="position-filter"><legend>Positions (optional)</legend>{positions.map((position) => <label className="check-chip" key={position.id}><input type="checkbox" checked={value.position_ids.includes(position.id)} onChange={() => onChange({ ...value, position_ids: toggleArray(value.position_ids, position.id) })} />{position.department} · {position.name}</label>)}</fieldset>
      </div>

      <label className="switch-line crew-hard"><input type="checkbox" checked={value.hard_minimum} onChange={(event) => onChange({ ...value, hard_minimum: event.target.checked })} /><span>Minimum is required; target stays flexible with labor</span></label>
      <button className="primary-btn" type="button" onClick={onSubmit}>{submitLabel}</button>
    </div>
  );
}

export default function ManagerPage() {
  const [section, setSection] = useState("positions");
  const [weekStart, setWeekStart] = useState(currentMonday);
  const [settings, setSettings] = useState(null);
  const [departments, setDepartments] = useState([]);
  const [newDepartment, setNewDepartment] = useState("");
  const [positions, setPositions] = useState([]);
  const [positionDrafts, setPositionDrafts] = useState({});
  const [newPositionNames, setNewPositionNames] = useState({});
  const [projections, setProjections] = useState([]);
  const [projectionDrafts, setProjectionDrafts] = useState({});
  const [newBlocks, setNewBlocks] = useState({});
  const [crewTargets, setCrewTargets] = useState([]);
  const [crewDrafts, setCrewDrafts] = useState({});
  const [crewForm, setCrewForm] = useState({ ...EMPTY_CREW });
  const [editingCrewId, setEditingCrewId] = useState(null);
  const [saved, setSaved] = useState("");
  const [error, setError] = useState("");

  const dates = useMemo(() => weekDates(weekStart), [weekStart]);

  async function loadBase() {
    try {
      setError("");
      const [manager, departmentRows, positionRows, crewRows] = await Promise.all([
        api("/manager-settings"),
        api("/departments"),
        api("/positions"),
        api("/crew-targets"),
      ]);
      setSettings(manager);
      setDepartments(departmentRows);
      setNewPositionNames((current) => Object.fromEntries(departmentRows.map((row) => [row.name, current[row.name] || ""])));
      setPositions(positionRows.filter((row) => row.active));
      setPositionDrafts(
        Object.fromEntries(positionRows.map((row) => [row.id, { name: row.name, department: row.department }]))
      );
      setCrewTargets(crewRows);
      setCrewDrafts(Object.fromEntries(crewRows.map((row) => [row.id, crewToDraft(row)])));
    } catch (err) {
      setError(err.message);
    }
  }

  async function loadLabor() {
    try {
      const rows = await api(`/labor-projections?week_start=${weekStart}`);
      setProjections(rows);
      setProjectionDrafts(Object.fromEntries(rows.map((row) => [row.id, projectionToDraft(row)])));
      setNewBlocks({});
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    loadBase();
  }, []);

  useEffect(() => {
    loadLabor();
  }, [weekStart]);

  function flashSaved(text = "Saved") {
    setSaved(text);
    window.setTimeout(() => setSaved(""), 1400);
  }

  function laborPayload(draft) {
    const payload = {
      date: draft.date,
      start_time: draft.whole_day ? "" : draft.start_time,
      end_time: draft.whole_day ? "" : draft.end_time,
      projected_sales: null,
      min_labor_percent: null,
      max_labor_percent: null,
      labor_percent: null,
      max_labor_hours: null,
      max_labor_dollars: null,
      note: "",
    };
    if (draft.budget_mode === "sales_percent") {
      payload.projected_sales = draft.projected_sales === "" ? null : Number(draft.projected_sales);
      payload.min_labor_percent = draft.min_labor_percent === "" ? null : Number(draft.min_labor_percent);
      payload.max_labor_percent = draft.max_labor_percent === "" ? null : Number(draft.max_labor_percent);
    } else if (draft.budget_mode === "max_hours") {
      payload.max_labor_hours = draft.max_labor_hours === "" ? null : Number(draft.max_labor_hours);
    } else {
      payload.max_labor_dollars = draft.max_labor_dollars === "" ? null : Number(draft.max_labor_dollars);
    }
    return payload;
  }

  async function saveProjection(id) {
    try {
      await api(`/labor-projections/${id}`, {
        method: "PATCH",
        body: JSON.stringify(laborPayload(projectionDrafts[id])),
      });
      flashSaved("Labor block saved");
      await loadLabor();
    } catch (err) {
      setError(err.message);
    }
  }

  async function createProjection(date, clientId) {
    const draft = (newBlocks[date] || []).find((row) => row.clientId === clientId);
    if (!draft) return;
    try {
      await api("/labor-projections", {
        method: "POST",
        body: JSON.stringify(laborPayload(draft)),
      });
      flashSaved("Labor block added");
      await loadLabor();
    } catch (err) {
      setError(err.message);
    }
  }

  async function deleteProjection(id) {
    try {
      await api(`/labor-projections/${id}`, { method: "DELETE" });
      await loadLabor();
    } catch (err) {
      setError(err.message);
    }
  }

  function addNewBlock(date) {
    setNewBlocks((current) => ({
      ...current,
      [date]: [...(current[date] || []), emptyLaborBlock(date)],
    }));
  }

  function patchNewBlock(date, clientId, patch) {
    setNewBlocks((current) => ({
      ...current,
      [date]: (current[date] || []).map((row) =>
        row.clientId === clientId ? { ...row, ...patch } : row
      ),
    }));
  }

  function removeNewBlock(date, clientId) {
    setNewBlocks((current) => ({
      ...current,
      [date]: (current[date] || []).filter((row) => row.clientId !== clientId),
    }));
  }

  async function savePosition(id) {
    try {
      await api(`/positions/${id}`, {
        method: "PATCH",
        body: JSON.stringify(positionDrafts[id]),
      });
      flashSaved("Position saved");
      await loadBase();
    } catch (err) {
      setError(err.message);
    }
  }

  async function addPosition(department) {
    const name = (newPositionNames[department] || "").trim();
    if (!name) return;
    try {
      await api("/positions", {
        method: "POST",
        body: JSON.stringify({ name, department, active: true }),
      });
      setNewPositionNames((current) => ({ ...current, [department]: "" }));
      await loadBase();
    } catch (err) {
      setError(err.message);
    }
  }

  async function addDepartment() {
    const name = newDepartment.trim();
    if (!name) return;
    try {
      await api("/departments", { method: "POST", body: JSON.stringify({ name, active: true }) });
      setNewDepartment(""); await loadBase(); flashSaved("Department added");
    } catch (err) { setError(err.message); }
  }

  async function deleteDepartment(department) {
    if (!window.confirm(`Remove the ${department.name} department?`)) return;
    try { await api(`/departments/${department.id}`, { method: "DELETE" }); await loadBase(); }
    catch (err) { setError(err.message); }
  }

  async function deletePosition(id) {
    if (!confirmOncePerSession("destructive-manager", "Remove this item? You will only be asked once per session.")) return;
    try {
      await api(`/positions/${id}`, { method: "DELETE" });
      flashSaved("Position removed");
      await loadBase();
    } catch (err) {
      setError(err.message);
    }
  }

  function crewPayload(value) {
    const minimum = Number(value.minimum_count || 0);
    const preferred = Number(value.preferred_count || minimum);
    return {
      name: String(value.name || "").trim(),
      date: value.apply_mode === "date" ? (value.date || dates[0]) : "",
      day_of_week: value.apply_mode === "recurring" ? Number(value.day_of_week ?? -1) : -1,
      start_time: value.start_time || "",
      end_time: value.end_time || "",
      position_ids: (value.position_ids || []).map(Number),
      departments: value.departments || [],
      roles: value.roles || [],
      minimum_count: minimum,
      preferred_count: Math.max(minimum, preferred),
      hard_minimum: Boolean(value.hard_minimum),
      active: value.active !== false,
    };
  }

  async function addCrewTarget() {
    try {
      setError("");
      const created = await api("/crew-targets", {
        method: "POST",
        body: JSON.stringify(crewPayload({ ...crewForm, date: crewForm.date || dates[0] })),
      });
      setCrewForm({ ...EMPTY_CREW, date: dates[0] });
      setEditingCrewId(created.id);
      flashSaved("Crew target added");
      await loadBase();
    } catch (err) {
      setError(err.message);
    }
  }

  async function saveCrewTarget(id) {
    try {
      setError("");
      const updated = await api(`/crew-targets/${id}`, {
        method: "PATCH",
        body: JSON.stringify(crewPayload(crewDrafts[id])),
      });
      setCrewDrafts((current) => ({ ...current, [id]: crewToDraft(updated) }));
      flashSaved("Crew target saved");
      await loadBase();
    } catch (err) {
      setError(err.message);
    }
  }

  async function deleteCrewTarget(id) {
    if (!confirmOncePerSession("destructive-manager", "Remove this item? You will only be asked once per session.")) return;
    try {
      setError("");
      await api(`/crew-targets/${id}`, { method: "DELETE" });
      setEditingCrewId(null);
      flashSaved("Crew target removed");
      await loadBase();
    } catch (err) {
      setError(err.message);
    }
  }

  async function saveSettings(event) {
    event.preventDefault();
    try {
      setError("");
      const baseRate = Number(settings.employee_hourly_rate || 18.2);
      const updated = await api("/manager-settings", {
        method: "PUT",
        body: JSON.stringify({
          ...settings,
          employee_hourly_rate: baseRate,
          shift_lead_hourly_rate: baseRate + 1,
          gm_hourly_rate: baseRate + 1,
          min_labor_percent: Number(settings.min_labor_percent || 18),
          max_labor_percent: Number(settings.max_labor_percent || 20),
        }),
      });
      setSettings(updated);
      flashSaved("Operations settings saved");
    } catch (err) {
      setError(err.message);
    }
  }

  if (!settings) return <div className="page"><div className="loading-card">Loading manager setup…</div></div>;

  return (
    <div className="page">
      <div className="page-header manager-heading">
        <div><span className="eyebrow">WORKFORCE SETUP</span><h1>Scheduling</h1><p>Create departments and positions, then manage staffing targets and scheduling behavior.</p></div>
        {saved && <div className="save-toast">✓ {saved}</div>}
      </div>

      <div className="segmented-tabs manager-sections">
        <button className={section === "positions" ? "active" : ""} onClick={() => setSection("positions")}>Positions</button>
        <button className={section === "crew" ? "active" : ""} onClick={() => setSection("crew")}>Crew targets</button>
        <button className={section === "operations" ? "active" : ""} onClick={() => setSection("operations")}>Operations</button>
      </div>

      {error && <div className="alert error">{error}</div>}


      {section === "positions" && (
        <div className="stack">
          <section className="card position-add-compact"><input placeholder="New department name" value={newDepartment} onChange={(event) => setNewDepartment(event.target.value)} /><button className="primary-btn" onClick={addDepartment}>Add department</button></section>
          <div className="position-columns">
          {departments.map((department) => (
            <section className="card position-column" key={department.id}>
              <div className="position-column-title"><div><span>DEPARTMENT</span><h2>{department.name}</h2></div><span className="count-pill">{positions.filter((row) => row.department === department.name).length}</span></div>
              <div className="position-add-compact"><input placeholder={`Add a ${department.name} position`} value={newPositionNames[department.name] || ""} onChange={(event) => setNewPositionNames((current) => ({ ...current, [department.name]: event.target.value }))} /><button className="small-btn" onClick={() => addPosition(department.name)}>Add</button></div>
              <div className="position-edit-list">
                {positions.filter((row) => row.department === department.name).map((position) => {
                  const draft = positionDrafts[position.id] || position;
                  return <div className="position-edit-row compact" key={position.id}><input value={draft.name} onChange={(event) => setPositionDrafts((current) => ({ ...current, [position.id]: { ...draft, name: event.target.value } }))} /><button className="icon-save" onClick={() => savePosition(position.id)}>✓</button><button className="icon-delete" onClick={() => deletePosition(position.id)}>×</button></div>;
                })}
              </div>
              {!positions.some((row) => row.department === department.name) && <button className="danger-text-btn" onClick={() => deleteDepartment(department)}>Remove empty department</button>}
            </section>
          ))}
          </div>
        </div>
      )}

      {section === "crew" && (
        <div className="stack">
          <section className="info-banner crew-info"><div className="info-icon">↗</div><div><strong>Crew targets describe demand—not training.</strong><p>Set a minimum and a flexible target for a time window. Leave filters blank for any team member, or narrow the target to one of your departments, roles, or positions.</p></div></section>
          <section className="card"><div className="section-title"><div><span className="eyebrow">NEW DEMAND</span><h2>Add crew target</h2></div></div><CrewForm positions={positions} departments={departments} value={{ ...crewForm, date: crewForm.date || dates[0] }} onChange={setCrewForm} onSubmit={addCrewTarget} submitLabel="Add crew target" /></section>
          <section className="card"><div className="section-title"><div><span className="eyebrow">SAVED</span><h2>Crew targets</h2></div><span className="count-pill">{crewTargets.length}</span></div><div className="crew-target-list">
            {crewTargets.map((target) => {
              const open = editingCrewId === target.id;
              const draft = crewDrafts[target.id] || crewToDraft(target);
              const applies = target.date ? formatDate(target.date) : target.day_of_week === -1 ? "Every day" : DAY_NAMES[target.day_of_week];
              return <article className="crew-target-card" key={target.id}><button className="crew-target-summary" onClick={() => setEditingCrewId(open ? null : target.id)}><div><strong>{target.name}</strong><span>{applies} · {formatClock(target.start_time)}–{formatClock(target.end_time)}</span><small>Minimum {target.minimum_count} · target {target.preferred_count}</small></div><span>{open ? "⌃" : "⌄"}</span></button>{open && <div className="crew-target-edit"><CrewForm positions={positions} departments={departments} value={draft} onChange={(next) => setCrewDrafts((current) => ({ ...current, [target.id]: next }))} onSubmit={() => saveCrewTarget(target.id)} submitLabel="Save changes" /><button className="danger-text-btn" onClick={() => deleteCrewTarget(target.id)}>Delete target</button></div>}</article>;
            })}
            {!crewTargets.length && <div className="empty-inline">No crew targets yet. The AI can build these from a real schedule or a sentence like “Tuesday lunch needs six people, but four is the minimum.”</div>}
          </div></section>
        </div>
      )}

      {section === "operations" && (
        <form className="card settings-card operations-card" onSubmit={saveSettings}>
          <div className="section-title"><div><span className="eyebrow">BUSINESS-WIDE</span><h2>Operations settings</h2></div></div>
          <div className="settings-grid">
            <label>Base employee wage<input type="text" inputMode="decimal" placeholder="18.20" value={settings.employee_hourly_rate} onChange={(event) => setSettings({ ...settings, employee_hourly_rate: event.target.value })} /></label>
            <div className="computed-rate-card"><span>Shift Lead / GM</span><strong>${(Number(settings.employee_hourly_rate || 0) + 1).toFixed(2)}/hr</strong><small>Base wage + $1.00</small></div>
            <label>Store opens<input type="time" value={settings.store_open_time} onChange={(event) => setSettings({ ...settings, store_open_time: event.target.value })} /></label>
            <label>Store closes<input type="time" value={settings.store_close_time} onChange={(event) => setSettings({ ...settings, store_close_time: event.target.value })} /></label>
          </div>
          <label className="trainee-setting"><input type="checkbox" checked={settings.schedule_extra_with_trainee} onChange={(event) => setSettings({ ...settings, schedule_extra_with_trainee: event.target.checked })} /><span><strong>Schedule an extra person with a trainee when possible</strong><small>This stays a preference—not a hard requirement.</small></span></label>
          <button className="primary-btn">Save settings</button>
        </form>
      )}
    </div>
  );
}
