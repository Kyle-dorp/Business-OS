import { useEffect, useMemo, useState } from "react";

import { api } from "../api";
import {
  formatClock,
  formatDate,
  formatRole,
  formatWeekRange,
  fromIsoDate,
  shiftWeek,
  statusLabel,
  toIsoDate,
  weekDates,
  confirmOncePerSession,
} from "../utils";


function emptySalesBlock(date) {
  return {
    clientId: `${Date.now()}-${Math.random()}`,
    date,
    whole_day: true,
    start_time: "10:30",
    end_time: "21:00",
    projected_sales: "",
  };
}

function projectionToSalesDraft(row) {
  return {
    ...row,
    whole_day: !row.start_time && !row.end_time,
    projected_sales: row.projected_sales ?? "",
  };
}

function SalesBlockEditor({ draft, onChange, onSave, onDelete, isNew = false }) {
  return (
    <div className="sales-block-editor">
      <div className={`sales-block-main ${draft.whole_day ? "whole-day" : "timed"}`}>
        <label className="switch-line compact-switch"><input type="checkbox" checked={draft.whole_day} onChange={(event) => onChange({ whole_day: event.target.checked })} /><span>Whole day</span></label>
        {!draft.whole_day && <><label>Start<input type="time" value={draft.start_time} onChange={(event) => onChange({ start_time: event.target.value })} /></label><label>End<input type="time" value={draft.end_time} onChange={(event) => onChange({ end_time: event.target.value })} /></label></>}
        <label className="sales-field">Projected sales<input type="text" inputMode="decimal" placeholder="9000" value={draft.projected_sales} onChange={(event) => onChange({ projected_sales: event.target.value })} /></label>
        <div className="sales-block-actions">
          <button className="small-btn" type="button" onClick={onSave}>{isNew ? "Add" : "Save"}</button>
          <button className="icon-delete" type="button" onClick={onDelete} aria-label="Remove sales block">×</button>
        </div>
      </div>
    </div>
  );
}

export default function HomePage() {
  const [weekStart, setWeekStart] = useState(() => {
    const saved = localStorage.getItem("scheduler.home.weekStart");
    if (saved) return saved;
    const today = new Date();
    const day = today.getDay();
    const difference = day === 0 ? -6 : 1 - day;
    today.setDate(today.getDate() + difference);
    return toIsoDate(today);
  });
  const [versions, setVersions] = useState([]);
  const [schedule, setSchedule] = useState(null);
  const [scope, setScope] = useState("problems");
  const [selectedDate, setSelectedDate] = useState("");
  const [staffingLevel, setStaffingLevel] = useState("balanced");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [employees, setEmployees] = useState([]);
  const [positions, setPositions] = useState([]);
  const [editingShiftId, setEditingShiftId] = useState(null);
  const [shiftDrafts, setShiftDrafts] = useState({});
  const [settings, setSettings] = useState(null);
  const [settingsSaved, setSettingsSaved] = useState(false);
  const [projections, setProjections] = useState([]);
  const [projectionDrafts, setProjectionDrafts] = useState({});
  const [newBlocks, setNewBlocks] = useState({});
  const [salesOpen, setSalesOpen] = useState(true);

  const dates = useMemo(() => weekDates(weekStart), [weekStart]);

  async function loadSalesPlan() {
    try {
      const rows = await api(`/labor-projections?week_start=${weekStart}`);
      setProjections(rows);
      setProjectionDrafts(Object.fromEntries(rows.map((row) => [row.id, projectionToSalesDraft(row)])));
      setNewBlocks({});
    } catch (err) {
      setError(err.message);
    }
  }

  async function loadVersions(preferredId = null) {
    try {
      setError("");
      const rows = await api(`/schedules?week_start=${weekStart}`);
      setVersions(rows);
      const targetId = preferredId || rows[0]?.id;
      if (targetId) {
        setSchedule(await api(`/schedules/${targetId}`));
      } else {
        setSchedule(null);
      }
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    localStorage.setItem("scheduler.home.weekStart", weekStart);
    setSelectedDate(dates[0]);
    loadVersions();
    loadSalesPlan();
  }, [weekStart]);

  useEffect(() => {
    Promise.all([api("/employees"), api("/positions"), api("/manager-settings")])
      .then(([employeeRows, positionRows, managerSettings]) => {
        setEmployees(employeeRows.filter((row) => row.active));
        setPositions(positionRows);
        setSettings(managerSettings);
      })
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    setShiftDrafts(
      Object.fromEntries(
        (schedule?.shifts || []).map((shift) => [
          shift.id,
          {
            employee_id: shift.employee_id,
            position_id: shift.position_id || "",
            start_time: shift.start_time,
            end_time: shift.end_time,
            locked: shift.locked,
          },
        ])
      )
    );
  }, [schedule?.id]);

  async function generateDraft(requestScope = "full_week") {
    try {
      setBusy(true);
      setError("");
      const payload = {
        week_start: weekStart,
        scope: requestScope,
        selected_date: requestScope === "selected_day" ? selectedDate : null,
        labor_tolerance_percent: 0,
        staffing_level: staffingLevel,
        source_schedule_id:
          requestScope === "full_week" && !schedule ? null : schedule?.id || null,
      };
      const result = await api("/schedules/generate", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      await loadVersions(result.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function projectionPayload(draft) {
    return {
      date: draft.date,
      start_time: draft.whole_day ? "" : draft.start_time,
      end_time: draft.whole_day ? "" : draft.end_time,
      projected_sales: draft.projected_sales === "" ? null : Number(draft.projected_sales),
      min_labor_percent: null,
      max_labor_percent: null,
      labor_percent: null,
      max_labor_hours: null,
      max_labor_dollars: null,
      note: "",
    };
  }

  function addSalesBlock(date) {
    setNewBlocks((current) => ({ ...current, [date]: [...(current[date] || []), emptySalesBlock(date)] }));
  }

  function patchNewSalesBlock(date, clientId, patch) {
    setNewBlocks((current) => ({ ...current, [date]: (current[date] || []).map((row) => row.clientId === clientId ? { ...row, ...patch } : row) }));
  }

  function removeNewSalesBlock(date, clientId) {
    setNewBlocks((current) => ({ ...current, [date]: (current[date] || []).filter((row) => row.clientId !== clientId) }));
  }

  async function createSalesBlock(date, clientId) {
    const draft = (newBlocks[date] || []).find((row) => row.clientId === clientId);
    if (!draft) return;
    try {
      await api("/labor-projections", { method: "POST", body: JSON.stringify(projectionPayload(draft)) });
      await loadSalesPlan();
    } catch (err) { setError(err.message); }
  }

  async function saveSalesBlock(id) {
    try {
      await api(`/labor-projections/${id}`, { method: "PATCH", body: JSON.stringify(projectionPayload(projectionDrafts[id])) });
      await loadSalesPlan();
    } catch (err) { setError(err.message); }
  }

  async function deleteSalesBlock(id) {
    try { await api(`/labor-projections/${id}`, { method: "DELETE" }); await loadSalesPlan(); } catch (err) { setError(err.message); }
  }

  async function saveLaborGoal() {
    if (!settings) return;
    try {
      setError("");
      const minimum = Number(settings.min_labor_percent || 18);
      const maximum = Number(settings.max_labor_percent || 20);
      const result = await api("/manager-settings", {
        method: "PUT",
        body: JSON.stringify({
          ...settings,
          min_labor_percent: Math.min(minimum, maximum),
          max_labor_percent: Math.max(minimum, maximum),
        }),
      });
      setSettings(result);
      setSettingsSaved(true);
      window.setTimeout(() => setSettingsSaved(false), 1800);
    } catch (err) {
      setError(err.message);
    }
  }

  async function publishSchedule() {
    if (!schedule) return;
    try {
      setBusy(true);
      setError("");
      const result = await api(`/schedules/${schedule.id}/publish`, {
        method: "POST",
      });
      setSchedule(result);
      await loadVersions(result.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }


  async function saveShift(shiftId) {
    try {
      setError("");
      const draft = shiftDrafts[shiftId];
      await api(`/schedule-shifts/${shiftId}`, {
        method: "PATCH",
        body: JSON.stringify({
          employee_id: Number(draft.employee_id),
          position_id: draft.position_id === "" ? null : Number(draft.position_id),
          start_time: draft.start_time,
          end_time: draft.end_time,
          locked: true,
        }),
      });
      setEditingShiftId(null);
      setSchedule(await api(`/schedules/${schedule.id}`));
    } catch (err) {
      setError(err.message);
    }
  }

  async function deleteShift(shiftId) {
    if (!confirmOncePerSession("destructive-schedule", "Remove this shift? You will only be asked once per session.")) return;
    try {
      await api(`/schedule-shifts/${shiftId}`, { method: "DELETE" });
      setSchedule(await api(`/schedules/${schedule.id}`));
    } catch (err) {
      setError(err.message);
    }
  }

  async function toggleLock(shift) {
    try {
      await api(`/schedule-shifts/${shift.id}`, {
        method: "PATCH",
        body: JSON.stringify({ locked: !shift.locked }),
      });
      setSchedule(await api(`/schedules/${schedule.id}`));
    } catch (err) {
      setError(err.message);
    }
  }

  const shiftsByDate = useMemo(() => {
    const map = {};
    for (const shift of schedule?.shifts || []) {
      (map[shift.date] ||= []).push(shift);
    }
    return map;
  }, [schedule]);

  const warningsByDate = useMemo(() => {
    const map = {};
    for (const warning of schedule?.warnings || []) {
      const key = warning.date || "general";
      (map[key] ||= []).push(warning);
    }
    return map;
  }, [schedule]);

  const scheduledDates = dates.filter(
    (date) => shiftsByDate[date]?.length || warningsByDate[date]?.length
  );

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <span className="eyebrow">WEEKLY OPERATIONS</span><h1>Home</h1>
          <p>Build the next schedule, compare staffing levels, review warnings, and publish the version your team should follow.</p>
        </div>
      </div>

      <section className="card week-toolbar">
        <button
          className="secondary-btn"
          onClick={() => setWeekStart(shiftWeek(weekStart, -1))}
        >
          ← Previous
        </button>

        <div className="week-heading">
          <strong>{formatWeekRange(weekStart)}</strong>
          <input
            aria-label="Week start"
            type="date"
            value={weekStart}
            onChange={(event) => setWeekStart(event.target.value)}
          />
        </div>

        <button
          className="secondary-btn"
          onClick={() => setWeekStart(shiftWeek(weekStart, 1))}
        >
          Next →
        </button>
      </section>

      {error && <div className="alert error">{error}</div>}

      <section className="home-command-center">
        <div className="labor-goal-card">
          <div>
            <span className="eyebrow">LABOR GOAL</span>
            <h2>Target range</h2>
            <p>Drafts compare staffing inside this range.</p>
          </div>
          <div className="labor-goal-inputs">
            <label>Minimum<input type="text" inputMode="decimal" placeholder="18" value={settings?.min_labor_percent ?? ""} onChange={(event) => setSettings((current) => ({ ...current, min_labor_percent: event.target.value }))} /><span>%</span></label>
            <div className="range-divider">to</div>
            <label>Maximum<input type="text" inputMode="decimal" placeholder="20" value={settings?.max_labor_percent ?? ""} onChange={(event) => setSettings((current) => ({ ...current, max_labor_percent: event.target.value }))} /><span>%</span></label>
            <button className="secondary-btn compact" onClick={saveLaborGoal}>{settingsSaved ? "Saved ✓" : "Save goal"}</button>
          </div>
        </div>

        <div className="generate-card">
          <div className="generate-card-copy">
            <span className="eyebrow">SCHEDULE BUILDER</span>
            <h2>{schedule ? "Create another draft" : "Generate this week"}</h2>
            <p>The solver follows availability, positions, crew targets, trainees, and labor.</p>
          </div>
          <label className="inline-label staffing-level-control">
            Draft style
            <select value={staffingLevel} onChange={(event) => setStaffingLevel(event.target.value)}>
              <option value="lean">Lean · near minimum</option>
              <option value="balanced">Balanced · recommended</option>
              <option value="full">Full · near maximum</option>
            </select>
          </label>
          <button className="primary-btn hero-action" disabled={busy} onClick={() => generateDraft("full_week")}>
            {busy ? "Building…" : schedule ? "Generate new draft" : "Generate schedule"}
          </button>
        </div>
      </section>

      <section className="card sales-plan-card">
        <button className="section-collapse-button" onClick={() => setSalesOpen((open) => !open)}>
          <div><span className="eyebrow">PROJECTED SALES</span><h2>Weekly sales plan</h2><p>Add one whole-day estimate or split any day into as many time blocks as needed.</p></div>
          <span>{salesOpen ? "⌃" : "⌄"}</span>
        </button>
        {salesOpen && <div className="sales-day-grid">{dates.map((date) => {
          const savedRows = projections.filter((row) => row.date === date);
          const newRows = newBlocks[date] || [];
          return <article className="sales-day-card" key={date}><div className="sales-day-head"><div><strong>{formatDate(date, { weekday: "short" })}</strong><span>{savedRows.length + newRows.length ? `${savedRows.length + newRows.length} block${savedRows.length + newRows.length === 1 ? "" : "s"}` : "No estimate"}</span></div><button className="ghost-add" onClick={() => addSalesBlock(date)}>+ Add block</button></div><div className="sales-block-list">{savedRows.map((row) => { const draft = projectionDrafts[row.id] || projectionToSalesDraft(row); return <SalesBlockEditor key={row.id} draft={draft} onChange={(patch) => setProjectionDrafts((current) => ({ ...current, [row.id]: { ...draft, ...patch } }))} onSave={() => saveSalesBlock(row.id)} onDelete={() => deleteSalesBlock(row.id)} />; })}{newRows.map((draft) => <SalesBlockEditor key={draft.clientId} draft={draft} isNew onChange={(patch) => patchNewSalesBlock(date, draft.clientId, patch)} onSave={() => createSalesBlock(date, draft.clientId)} onDelete={() => removeNewSalesBlock(date, draft.clientId)} />)}{!savedRows.length && !newRows.length && <div className="sales-empty">Add the forecast when you have it.</div>}</div></article>;
        })}</div>}
      </section>

      {schedule && (
        <section className="card schedule-actions streamlined">
          <div className="action-group">
            <select value={scope} onChange={(event) => setScope(event.target.value)}>
              <option value="problems">Repair warnings only</option>
              <option value="selected_day">Regenerate one day</option>
              <option value="full_week">Regenerate entire week</option>
            </select>
            {scope === "selected_day" && (
              <select value={selectedDate} onChange={(event) => setSelectedDate(event.target.value)}>
                {dates.map((date) => <option key={date} value={date}>{formatDate(date)}</option>)}
              </select>
            )}
            <button className="secondary-btn" disabled={busy} onClick={() => generateDraft(scope)}>Regenerate</button>
            <button className="publish-btn" disabled={busy || schedule.status === "published"} onClick={publishSchedule}>Publish schedule</button>
          </div>
          <div className="schedule-meta">
            <span className={`status-badge ${schedule.status}`}>{statusLabel(schedule.status)}</span>
            <span>Version {schedule.version}</span>
            <span className="staffing-chip">{schedule.staffing_level || "balanced"}</span>
          </div>
        </section>
      )}

      {schedule && versions.length > 1 && (
        <section className="card version-strip">
          <strong>Versions</strong>
          <div className="version-buttons">
            {versions.map((version) => (
              <button
                key={version.id}
                className={
                  version.id === schedule.id
                    ? "version-btn active"
                    : "version-btn"
                }
                onClick={async () => setSchedule(await api(`/schedules/${version.id}`))}
              >
                v{version.version} · {statusLabel(version.status)}
              </button>
            ))}
          </div>
        </section>
      )}

      {!schedule ? (
        <section className="empty-state card">
          <h2>No schedule draft yet</h2>
          <p>
            Add employees, crew targets, and projected sales, then generate the first reviewable draft.
          </p>
        </section>
      ) : (
        <>
          {warningsByDate.general?.length > 0 && (
            <section className="warning-panel">
              {warningsByDate.general.map((warning) => (
                <div className={`warning-item ${warning.severity}`} key={warning.id}>
                  {warning.message}
                </div>
              ))}
            </section>
          )}

          {scheduledDates.length === 0 ? (
            <section className="empty-state card">
              <h2>No scheduled days were produced</h2>
              <p>Check the notices and Manager → Projected Crew.</p>
            </section>
          ) : (
            <div className="week-schedule-list">
              {scheduledDates.map((date) => (
                <section className="schedule-day-card" key={date}>
                  <div className="schedule-day-header">
                    <div>
                      <h2>{formatDate(date)}</h2>
                      <span>
                        {shiftsByDate[date]?.length || 0} scheduled shifts
                      </span>
                    </div>
                  </div>

                  <div className="shift-table">
                    {(shiftsByDate[date] || []).map((shift) => {
                      const editing = editingShiftId === shift.id;
                      const draft = shiftDrafts[shift.id] || shift;
                      return (
                        <div className={editing ? "shift-row editing" : "shift-row"} key={shift.id}>
                          {editing ? (
                            <>
                              <select value={draft.employee_id} onChange={(event) => setShiftDrafts((current) => ({ ...current, [shift.id]: { ...draft, employee_id: event.target.value } }))}>
                                {employees.map((employee) => <option value={employee.id} key={employee.id}>{employee.name}</option>)}
                              </select>
                              <select value={draft.position_id} onChange={(event) => setShiftDrafts((current) => ({ ...current, [shift.id]: { ...draft, position_id: event.target.value } }))}>
                                <option value="">Role only</option>
                                {positions.map((position) => <option value={position.id} key={position.id}>{position.department} · {position.name}</option>)}
                              </select>
                              <div className="shift-edit-times"><input type="time" value={draft.start_time} onChange={(event) => setShiftDrafts((current) => ({ ...current, [shift.id]: { ...draft, start_time: event.target.value } }))} /><input type="time" value={draft.end_time} onChange={(event) => setShiftDrafts((current) => ({ ...current, [shift.id]: { ...draft, end_time: event.target.value } }))} /></div>
                              <div className="shift-edit-actions"><button className="small-btn" onClick={() => saveShift(shift.id)}>Save</button><button className="secondary-btn" onClick={() => setEditingShiftId(null)}>Cancel</button><button className="delete-btn" onClick={() => deleteShift(shift.id)}>×</button></div>
                            </>
                          ) : (
                            <>
                              <div><strong>{shift.employee_name}</strong><span>{formatRole(shift.role)}</span></div>
                              <div><strong>{shift.position_name || formatRole(shift.role)}</strong><span>{shift.department}</span></div>
                              <div className="shift-time">{formatClock(shift.start_time)} – {formatClock(shift.end_time)}</div>
                              <div className="shift-row-actions"><button className="secondary-btn" onClick={() => setEditingShiftId(shift.id)}>Edit</button><button className={shift.locked ? "lock-btn locked" : "lock-btn"} onClick={() => toggleLock(shift)} title="Locked shifts are preserved during regeneration">{shift.locked ? "Locked" : "Lock"}</button></div>
                            </>
                          )}
                        </div>
                      );
                    })}
                  </div>

                  {warningsByDate[date]?.length > 0 && (
                    <div className="day-warning-list">
                      {warningsByDate[date].map((warning) => (
                        <div
                          className={`warning-item ${warning.severity}`}
                          key={warning.id}
                        >
                          {warning.message}
                        </div>
                      ))}
                    </div>
                  )}
                </section>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
