import { useEffect, useMemo, useRef, useState } from "react";

import { api } from "../api";
import { DAYS, formatRole, confirmOncePerSession } from "../utils";

const EMPTY_EMPLOYEE = { name: "", role: "employee" };
const EMPTY_RECURRING = { day_of_week: -1, start_time: "", end_time: "" };
const EMPTY_TEMPORARY = {
  start_date: "",
  end_date: "",
  start_time: "",
  end_time: "",
};

export default function AvailabilityPage() {
  const [employees, setEmployees] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [positions, setPositions] = useState([]);
  const [employeePositions, setEmployeePositions] = useState([]);
  const [availability, setAvailability] = useState([]);
  const [temporary, setTemporary] = useState([]);
  const [settings, setSettings] = useState(null);
  const [openDepartments, setOpenDepartments] = useState({});
  const [openEmployees, setOpenEmployees] = useState(new Set());
  const [openDetailKey, setOpenDetailKey] = useState(null);
  const [addForms, setAddForms] = useState({});
  const [employeeDrafts, setEmployeeDrafts] = useState({});
  const [employeeSaveState, setEmployeeSaveState] = useState({});
  const [availabilityDrafts, setAvailabilityDrafts] = useState({});
  const [temporaryDrafts, setTemporaryDrafts] = useState({});
  const [newRules, setNewRules] = useState({});
  const [error, setError] = useState("");
  const saveTimers = useRef({});

  async function loadData() {
    try {
      setError("");
      const [departmentRows, employeeRows, positionRows, abilityRows, availabilityRows, tempRows, manager] =
        await Promise.all([
          api("/departments"),
          api("/employees"),
          api("/positions"),
          api("/employee-positions"),
          api("/availability"),
          api("/temporary-unavailability"),
          api("/manager-settings"),
        ]);

      const activeEmployees = employeeRows.filter((employee) => employee.active);
      setDepartments(departmentRows);
      setOpenDepartments((current) => Object.fromEntries(departmentRows.map((row, index) => [row.name, current[row.name] ?? index === 0])));
      setAddForms((current) => Object.fromEntries(departmentRows.map((row) => [row.name, current[row.name] || { ...EMPTY_EMPLOYEE }])));
      setEmployees(activeEmployees);
      setPositions(positionRows);
      setEmployeePositions(abilityRows);
      setAvailability(availabilityRows);
      setTemporary(tempRows);
      setSettings(manager);
      setEmployeeDrafts(
        Object.fromEntries(
          activeEmployees.map((employee) => [
            employee.id,
            {
              name: employee.name,
              role: employee.role,
              min_hours_per_week: employee.min_hours_per_week,
              max_hours_per_week: employee.max_hours_per_week,
            },
          ])
        )
      );
      setAvailabilityDrafts(
        Object.fromEntries(
          availabilityRows.map((row) => [
            row.id,
            {
              day_of_week: row.day_of_week,
              start_time: row.start_time,
              end_time: row.end_time,
            },
          ])
        )
      );
      setTemporaryDrafts(
        Object.fromEntries(
          tempRows.map((row) => [
            row.id,
            {
              start_date: row.start_date,
              end_date: row.end_date,
              start_time: row.start_time,
              end_time: row.end_time,
            },
          ])
        )
      );
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    loadData();
    return () => Object.values(saveTimers.current).forEach(window.clearTimeout);
  }, []);

  const employeePositionMap = useMemo(() => {
    const map = {};
    for (const row of employeePositions) (map[row.employee_id] ||= []).push(row);
    return map;
  }, [employeePositions]);

  function hourlyRate(employee) {
    const base = Number(settings?.employee_hourly_rate || 0);
    return base + (employee.role === "employee" ? 0 : 1);
  }

  function setAddForm(department, patch) {
    setAddForms((current) => ({
      ...current,
      [department]: { ...current[department], ...patch },
    }));
  }

  async function addEmployee(event, department) {
    event.preventDefault();
    const form = addForms[department] || EMPTY_EMPLOYEE;
    if (!form.name.trim()) return;
    try {
      await api("/employees", {
        method: "POST",
        body: JSON.stringify({
          name: form.name.trim(),
          department,
          role: form.role,
          min_hours_per_week: 0,
          max_hours_per_week: 40,
          active: true,
        }),
      });
      setAddForm(department, { ...EMPTY_EMPLOYEE });
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  }

  function queueEmployeeSave(employeeId, nextDraft) {
    window.clearTimeout(saveTimers.current[employeeId]);
    setEmployeeSaveState((current) => ({ ...current, [employeeId]: "saving" }));
    saveTimers.current[employeeId] = window.setTimeout(async () => {
      if (!nextDraft.name.trim()) {
        setEmployeeSaveState((current) => ({ ...current, [employeeId]: "name-required" }));
        return;
      }
      try {
        await api(`/employees/${employeeId}`, {
          method: "PATCH",
          body: JSON.stringify({
            name: nextDraft.name.trim(),
            role: nextDraft.role,
            min_hours_per_week: Number(nextDraft.min_hours_per_week || 0),
            max_hours_per_week: Number(nextDraft.max_hours_per_week || 40),
          }),
        });
        setEmployeeSaveState((current) => ({ ...current, [employeeId]: "saved" }));
        window.setTimeout(
          () => setEmployeeSaveState((current) => ({ ...current, [employeeId]: "" })),
          1200
        );
      } catch (err) {
        setEmployeeSaveState((current) => ({ ...current, [employeeId]: "error" }));
        setError(err.message);
      }
    }, 650);
  }

  function patchEmployee(employeeId, patch) {
    setEmployeeDrafts((current) => {
      const nextDraft = { ...current[employeeId], ...patch };
      queueEmployeeSave(employeeId, nextDraft);
      return { ...current, [employeeId]: nextDraft };
    });
  }

  async function deleteEmployee(employeeId) {
    if (!confirmOncePerSession("destructive-availability", "Remove this employee? You will only be asked once per session.")) return;
    try {
      await api(`/employees/${employeeId}`, { method: "DELETE" });
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  }

  function toggleEmployee(employeeId) {
    setOpenEmployees((current) => {
      const next = new Set(current);
      if (next.has(employeeId)) next.delete(employeeId);
      else next.add(employeeId);
      return next;
    });
  }

  function currentPositionRows(employeeId) {
    return employeePositionMap[employeeId] || [];
  }

  async function savePositionRows(employeeId, rows) {
    try {
      await api(`/employees/${employeeId}/positions`, {
        method: "PUT",
        body: JSON.stringify({
          positions: rows.map((row) => ({
            position_id: row.position_id,
            trainee: Boolean(row.trainee),
            preferred: Boolean(row.preferred),
          })),
        }),
      });
      const refreshed = await api("/employee-positions");
      setEmployeePositions(refreshed);
    } catch (err) {
      setError(err.message);
    }
  }

  function togglePosition(employeeId, positionId, checked) {
    const current = currentPositionRows(employeeId).map((row) => ({ ...row }));
    const next = checked
      ? [...current, { employee_id: employeeId, position_id: positionId, trainee: false, preferred: current.length === 0 }]
      : current.filter((row) => row.position_id !== positionId);
    if (next.length && !next.some((row) => row.preferred)) next[0].preferred = true;
    savePositionRows(employeeId, next);
  }

  function updatePositionFlag(employeeId, positionId, field, value) {
    const current = currentPositionRows(employeeId).map((row) => ({ ...row }));
    const next = current.map((row) => {
      if (field === "preferred") {
        return { ...row, preferred: row.position_id === positionId ? value : false };
      }
      return row.position_id === positionId ? { ...row, [field]: value } : row;
    });
    savePositionRows(employeeId, next);
  }

  function newRuleKey(employeeId, type) {
    return `${employeeId}-${type}`;
  }

  function getNewRule(employeeId, type) {
    return newRules[newRuleKey(employeeId, type)] ||
      (type === "temporary" ? { ...EMPTY_TEMPORARY } : { ...EMPTY_RECURRING });
  }

  function patchNewRule(employeeId, type, patch) {
    const key = newRuleKey(employeeId, type);
    setNewRules((current) => ({
      ...current,
      [key]: { ...getNewRule(employeeId, type), ...patch },
    }));
  }

  async function addRecurring(employeeId, ruleType) {
    const draft = getNewRule(employeeId, ruleType);
    try {
      await api("/availability", {
        method: "POST",
        body: JSON.stringify({ employee_id: employeeId, rule_type: ruleType, ...draft }),
      });
      patchNewRule(employeeId, ruleType, { ...EMPTY_RECURRING });
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function saveRecurring(id) {
    try {
      await api(`/availability/${id}`, {
        method: "PATCH",
        body: JSON.stringify(availabilityDrafts[id]),
      });
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function deleteRecurring(id) {
    try {
      await api(`/availability/${id}`, { method: "DELETE" });
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function addTemporary(employeeId) {
    const draft = getNewRule(employeeId, "temporary");
    if (!draft.start_date) return;
    try {
      await api("/temporary-unavailability", {
        method: "POST",
        body: JSON.stringify({
          employee_id: employeeId,
          ...draft,
          end_date: draft.end_date || draft.start_date,
        }),
      });
      patchNewRule(employeeId, "temporary", { ...EMPTY_TEMPORARY });
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function saveTemporary(id) {
    try {
      await api(`/temporary-unavailability/${id}`, {
        method: "PATCH",
        body: JSON.stringify(temporaryDrafts[id]),
      });
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function deleteTemporary(id) {
    try {
      await api(`/temporary-unavailability/${id}`, { method: "DELETE" });
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  }

  function renderRecurring(employee, ruleType, label) {
    const key = `${employee.id}-${ruleType}`;
    const isOpen = openDetailKey === key;
    const rows = availability.filter(
      (row) => row.employee_id === employee.id && row.rule_type === ruleType
    );
    const newDraft = getNewRule(employee.id, ruleType);

    return (
      <section className="detail-section">
        <button className="detail-toggle" onClick={() => setOpenDetailKey(isOpen ? null : key)}>
          <span>{label}</span><span>{isOpen ? "⌃" : "⌄"}</span>
        </button>
        {isOpen && (
          <div className="detail-body">
            {rows.map((row) => {
              const draft = availabilityDrafts[row.id] || row;
              return (
                <div className="editable-rule-row" key={row.id}>
                  <select
                    value={draft.day_of_week}
                    onChange={(event) =>
                      setAvailabilityDrafts((current) => ({
                        ...current,
                        [row.id]: { ...draft, day_of_week: Number(event.target.value) },
                      }))
                    }
                  >
                    <option value={-1}>Any day</option>
                    {DAYS.map((day, index) => <option value={index} key={day}>{day}</option>)}
                  </select>
                  <input type="time" value={draft.start_time} onChange={(event) => setAvailabilityDrafts((current) => ({ ...current, [row.id]: { ...draft, start_time: event.target.value } }))} />
                  <input type="time" value={draft.end_time} onChange={(event) => setAvailabilityDrafts((current) => ({ ...current, [row.id]: { ...draft, end_time: event.target.value } }))} />
                  <button className="small-btn" onClick={() => saveRecurring(row.id)}>Save</button>
                  <button className="delete-btn" onClick={() => deleteRecurring(row.id)}>×</button>
                </div>
              );
            })}
            <div className="editable-rule-row new-row">
              <select value={newDraft.day_of_week} onChange={(event) => patchNewRule(employee.id, ruleType, { day_of_week: Number(event.target.value) })}>
                <option value={-1}>Any day</option>
                {DAYS.map((day, index) => <option value={index} key={day}>{day}</option>)}
              </select>
              <input type="time" value={newDraft.start_time} onChange={(event) => patchNewRule(employee.id, ruleType, { start_time: event.target.value })} />
              <input type="time" value={newDraft.end_time} onChange={(event) => patchNewRule(employee.id, ruleType, { end_time: event.target.value })} />
              <button className="small-btn" onClick={() => addRecurring(employee.id, ruleType)}>Add</button>
              <span />
            </div>
          </div>
        )}
      </section>
    );
  }

  function renderTemporary(employee) {
    const key = `${employee.id}-temporary`;
    const isOpen = openDetailKey === key;
    const rows = temporary.filter((row) => row.employee_id === employee.id);
    const newDraft = getNewRule(employee.id, "temporary");
    return (
      <section className="detail-section">
        <button className="detail-toggle" onClick={() => setOpenDetailKey(isOpen ? null : key)}>
          <span>Temporary Unavailability</span><span>{isOpen ? "⌃" : "⌄"}</span>
        </button>
        {isOpen && (
          <div className="detail-body">
            {rows.map((row) => {
              const draft = temporaryDrafts[row.id] || row;
              return (
                <div className="editable-temp-row" key={row.id}>
                  <input type="date" value={draft.start_date} onChange={(event) => setTemporaryDrafts((current) => ({ ...current, [row.id]: { ...draft, start_date: event.target.value } }))} />
                  <input type="date" value={draft.end_date} onChange={(event) => setTemporaryDrafts((current) => ({ ...current, [row.id]: { ...draft, end_date: event.target.value } }))} />
                  <input type="time" value={draft.start_time} onChange={(event) => setTemporaryDrafts((current) => ({ ...current, [row.id]: { ...draft, start_time: event.target.value } }))} />
                  <input type="time" value={draft.end_time} onChange={(event) => setTemporaryDrafts((current) => ({ ...current, [row.id]: { ...draft, end_time: event.target.value } }))} />
                  <button className="small-btn" onClick={() => saveTemporary(row.id)}>Save</button>
                  <button className="delete-btn" onClick={() => deleteTemporary(row.id)}>×</button>
                </div>
              );
            })}
            <div className="editable-temp-row new-row">
              <input type="date" value={newDraft.start_date} onChange={(event) => patchNewRule(employee.id, "temporary", { start_date: event.target.value })} />
              <input type="date" value={newDraft.end_date} onChange={(event) => patchNewRule(employee.id, "temporary", { end_date: event.target.value })} />
              <input type="time" value={newDraft.start_time} onChange={(event) => patchNewRule(employee.id, "temporary", { start_time: event.target.value })} />
              <input type="time" value={newDraft.end_time} onChange={(event) => patchNewRule(employee.id, "temporary", { end_time: event.target.value })} />
              <button className="small-btn" onClick={() => addTemporary(employee.id)}>Add</button>
              <span />
            </div>
          </div>
        )}
      </section>
    );
  }

  function renderDepartment(department, label) {
    const departmentPositions = positions.filter((position) => position.department === department);
    const departmentEmployees = employees.filter((employee) => employee.department === department);
    const form = addForms[department] || EMPTY_EMPLOYEE;
    const isOpen = openDepartments[department];

    return (
      <section className="department-panel" key={department}>
        <button className="department-header" onClick={() => setOpenDepartments((current) => ({ ...current, [department]: !current[department] }))}>
          <span>{label}</span><span>{isOpen ? "⌃" : "⌄"}</span>
        </button>
        {isOpen && (
          <div className="department-body">
            <form className="department-add-form" onSubmit={(event) => addEmployee(event, department)}>
              <input placeholder="Employee name…" value={form.name} onChange={(event) => setAddForm(department, { name: event.target.value })} />
              <select value={form.role} onChange={(event) => setAddForm(department, { role: event.target.value })}>
                <option value="employee">Employee</option>
                <option value="shift_lead">Shift Lead</option>
                <option value="gm">GM</option>
              </select>
              <button className="primary-btn">Add Employee</button>
            </form>

            <div className="employee-list">
              {departmentEmployees.length === 0 && <div className="blank-rule">No employees in this department yet.</div>}
              {departmentEmployees.map((employee) => {
                const open = openEmployees.has(employee.id);
                const draft = employeeDrafts[employee.id] || employee;
                const positionRows = currentPositionRows(employee.id);
                return (
                  <article className="employee-card" key={employee.id}>
                    <button className="employee-header" onClick={() => toggleEmployee(employee.id)}>
                      <span>{draft.name || employee.name}</span>
                      <span className="employee-summary">{formatRole(draft.role)} · ${hourlyRate(draft).toFixed(2)}/hr · {open ? "⌃" : "⌄"}</span>
                    </button>
                    {open && (
                      <div className="employee-body">
                        <div className="employee-settings-grid">
                          <label>Name<input value={draft.name} onChange={(event) => patchEmployee(employee.id, { name: event.target.value })} /></label>
                          <label>Role<select value={draft.role} onChange={(event) => patchEmployee(employee.id, { role: event.target.value })}><option value="employee">Employee</option><option value="shift_lead">Shift Lead</option><option value="gm">GM</option></select></label>
                          <label>Min hours<input type="number" min="0" value={draft.min_hours_per_week} onChange={(event) => patchEmployee(employee.id, { min_hours_per_week: event.target.value })} /></label>
                          <label>Max hours<input type="number" min="0" value={draft.max_hours_per_week} onChange={(event) => patchEmployee(employee.id, { max_hours_per_week: event.target.value })} /></label>
                          <div className="computed-wage"><span>Calculated wage</span><strong>${hourlyRate(draft).toFixed(2)}/hr</strong></div>
                        </div>
                        <div className={`autosave-status ${employeeSaveState[employee.id] || ""}`}>{employeeSaveState[employee.id] || "Changes save automatically"}</div>

                        <section className="position-panel">
                          <h3>Positions and preferred shift type</h3>
                          <div className="position-choice-list">
                            {departmentPositions.map((position) => {
                              const row = positionRows.find((item) => item.position_id === position.id);
                              return (
                                <div className="position-choice" key={position.id}>
                                  <label className="checkbox-label"><input type="checkbox" checked={Boolean(row)} onChange={(event) => togglePosition(employee.id, position.id, event.target.checked)} />{position.name}</label>
                                  <label className="checkbox-label secondary"><input type="checkbox" disabled={!row} checked={Boolean(row?.trainee)} onChange={(event) => updatePositionFlag(employee.id, position.id, "trainee", event.target.checked)} />Trainee?</label>
                                  <label className="checkbox-label secondary"><input type="radio" name={`preferred-${employee.id}`} disabled={!row} checked={Boolean(row?.preferred)} onChange={() => updatePositionFlag(employee.id, position.id, "preferred", true)} />Preferred</label>
                                </div>
                              );
                            })}
                          </div>
                        </section>

                        {renderRecurring(employee, "unavailable", "Recurring Unavailability")}
                        {renderRecurring(employee, "preferred", "Preferred Availability")}
                        {renderTemporary(employee)}

                        <button className="danger-text-btn" onClick={() => deleteEmployee(employee.id)}>Remove employee</button>
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          </div>
        )}
      </section>
    );
  }

  return (
    <div className="page">
      <div className="page-header"><div><span className="eyebrow">TEAM SETUP</span><h1>Availability</h1><p>Add your crew, mark what they can work, and edit availability without rebuilding anything.</p></div></div>
      {error && <div className="alert error">{error}</div>}
      <div className="stack">
        {departments.map((department) => renderDepartment(department.name, department.name))}
        {!departments.length && <div className="empty-inline">Add a department under Scheduling → Positions first.</div>}
      </div>
    </div>
  );
}
