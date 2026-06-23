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

export default function CalendarPage() {
  const [weekStart, setWeekStart] = useState(() => {
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
  const [laborTolerance, setLaborTolerance] = useState(0);
  const [staffingLevel, setStaffingLevel] = useState("balanced");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [employees, setEmployees] = useState([]);
  const [positions, setPositions] = useState([]);
  const [editingShiftId, setEditingShiftId] = useState(null);
  const [shiftDrafts, setShiftDrafts] = useState({});

  const dates = useMemo(() => weekDates(weekStart), [weekStart]);

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
    setSelectedDate(dates[0]);
    loadVersions();
  }, [weekStart]);

  useEffect(() => {
    Promise.all([api("/employees"), api("/positions")])
      .then(([employeeRows, positionRows]) => {
        setEmployees(employeeRows.filter((row) => row.active));
        setPositions(positionRows);
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
        labor_tolerance_percent: Number(laborTolerance || 0),
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
          <span className="eyebrow">WEEKLY WORKSPACE</span><h1>Schedule</h1>
          <p>Create lean, balanced, or full-staffing drafts, repair problem days, and publish the approved version.</p>
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

      <section className="card schedule-actions">
        <div className="action-group">
          <label className="inline-label staffing-level-control">
            Draft style
            <select value={staffingLevel} onChange={(event) => setStaffingLevel(event.target.value)}>
              <option value="lean">Lean · minimum labor %</option>
              <option value="balanced">Balanced · middle of range</option>
              <option value="full">Full · maximum labor %</option>
            </select>
          </label>

          <button
            className="primary-btn"
            disabled={busy}
            onClick={() => generateDraft("full_week")}
          >
            {schedule ? "Create New Full Draft" : "Create Draft"}
          </button>

          {schedule && (
            <>
              <select value={scope} onChange={(event) => setScope(event.target.value)}>
                <option value="problems">Regenerate problem shifts</option>
                <option value="selected_day">Regenerate selected day</option>
                <option value="full_week">Regenerate entire week</option>
              </select>

              {scope === "selected_day" && (
                <select
                  value={selectedDate}
                  onChange={(event) => setSelectedDate(event.target.value)}
                >
                  {dates.map((date) => (
                    <option key={date} value={date}>
                      {formatDate(date)}
                    </option>
                  ))}
                </select>
              )}

              <label className="inline-label">
                Labor slip %
                <input
                  type="number"
                  min="0"
                  step="0.5"
                  value={laborTolerance}
                  onChange={(event) => setLaborTolerance(event.target.value)}
                />
              </label>

              <button
                className="secondary-btn"
                disabled={busy}
                onClick={() => generateDraft(scope)}
              >
                Regenerate
              </button>

              <button
                className="publish-btn"
                disabled={busy || schedule.status === "published"}
                onClick={publishSchedule}
              >
                Publish
              </button>
            </>
          )}
        </div>

        {schedule && (
          <div className="schedule-meta">
            <span className={`status-badge ${schedule.status}`}>
              {statusLabel(schedule.status)}
            </span>
            <span>Version {schedule.version}</span>
            <span className="staffing-chip">{schedule.staffing_level || "balanced"}</span>
          </div>
        )}
      </section>

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
            Add employees, Projected Crew targets, and labor limits, then create the first draft.
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
