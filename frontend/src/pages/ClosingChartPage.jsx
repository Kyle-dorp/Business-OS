import { useEffect, useState } from "react";
import { api } from "../api";

function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function mondayOf(dateStr) {
  const d = new Date(dateStr + "T12:00:00");
  const day = d.getDay();
  d.setDate(d.getDate() - (day === 0 ? 6 : day - 1));
  return d.toISOString().slice(0, 10);
}

const DEFAULT_CONFIG = {
  employees: ["Bam", "June", "Kyle", "Hunter"],
  bread_types: ["Italian", "Jalapeño", "Herb", "White"],
  sandwiches: [
    { name: "Dagwoods", sizes: ['6"', '12"'] },
    { name: "Bomb", sizes: ['6"', '12"'] },
  ],
  soups: ["Soups sold", "Ajous sold"],
  emp_sub_sizes: ['12"', '6"'],
  emp_sides: ["Chips", "Soda", "Brownie"],
};

function NumSelect({ value, onChange, max = 10 }) {
  return (
    <select className="cc-num-select" value={value ?? "0"} onChange={(e) => onChange(e.target.value)}>
      {Array.from({ length: max + 1 }, (_, i) => <option key={i} value={String(i)}>{i}</option>)}
    </select>
  );
}

function TimeRange({ value = {}, onChange }) {
  return (
    <span className="cc-time-range">
      <input className="cc-time-input" type="time" value={value.start || ""} onChange={(e) => onChange({ ...value, start: e.target.value })} />
      <span className="cc-time-dash">–</span>
      <input className="cc-time-input" type="time" value={value.end || ""} onChange={(e) => onChange({ ...value, end: e.target.value })} />
    </span>
  );
}

export default function ClosingChartPage({ config: rawConfig }) {
  const cfg = { ...DEFAULT_CONFIG, ...(rawConfig || {}) };
  const [date, setDate] = useState(todayISO);
  const [form, setForm] = useState({});
  const [applying, setApplying] = useState(false);
  const [applyMsg, setApplyMsg] = useState("");
  const [saved, setSaved] = useState(false);

  const storageKey = `closing-chart-v2-${date}`;

  useEffect(() => {
    try {
      const raw = localStorage.getItem(storageKey);
      setForm(raw ? JSON.parse(raw) : {});
    } catch {
      setForm({});
    }
    setSaved(false);
    setApplyMsg("");
  }, [date]);

  function setPath(path, value) {
    const keys = path.split(".");
    setForm((prev) => {
      const next = structuredClone(prev);
      let obj = next;
      for (let i = 0; i < keys.length - 1; i++) {
        obj[keys[i]] = obj[keys[i]] || {};
        obj = obj[keys[i]];
      }
      obj[keys[keys.length - 1]] = value;
      return next;
    });
    setSaved(false);
  }

  function getPath(path, def = "") {
    return path.split(".").reduce((obj, k) => (obj == null ? def : obj[k]), form) ?? def;
  }

  function save() {
    localStorage.setItem(storageKey, JSON.stringify(form));
    setSaved(true);
  }

  async function applyFromToday() {
    setApplying(true);
    setApplyMsg("");
    const msgs = [];
    try {
      const weekStart = mondayOf(date);
      const schedules = await api(`/schedules?week_start=${weekStart}`).catch(() => []);
      const latest = schedules[0];
      if (latest) {
        const detail = await api(`/schedules/${latest.id}`).catch(() => null);
        if (detail?.shifts?.length) {
          const dayIndex = new Date(date + "T12:00:00").getDay();
          const mapped = [1, 2, 3, 4, 5, 6, 0];
          const todayShifts = detail.shifts.filter((s) => {
            const sd = new Date(s.date + "T12:00:00").getDay();
            return sd === dayIndex;
          });
          if (todayShifts.length) {
            setForm((prev) => {
              const next = structuredClone(prev);
              next.who_worked = next.who_worked || {};
              todayShifts.forEach((shift) => {
                if (shift.employee_name) {
                  const start = shift.start_time ? shift.start_time.slice(0, 5) : "";
                  const end = shift.end_time ? shift.end_time.slice(0, 5) : "";
                  next.who_worked[shift.employee_name] = { start, end };
                }
              });
              return next;
            });
            msgs.push(`Filled ${todayShifts.length} shift(s) from schedule`);
          } else {
            msgs.push("No shifts found for today in the latest schedule");
          }
        }
      } else {
        msgs.push("No schedule found for this week");
      }
    } catch (err) {
      msgs.push("Could not load schedule");
    }
    setApplyMsg(msgs.join(" · ") || "Done");
    setApplying(false);
    setSaved(false);
  }

  return (
    <div className="page closing-chart-page">
      <div className="page-header cc-header">
        <div>
          <span className="eyebrow">DAILY OPERATIONS</span>
          <h1>Closing Chart</h1>
        </div>
        <div className="cc-header-actions">
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="cc-date-input" />
          <button className="secondary-btn compact no-print" disabled={applying} onClick={applyFromToday}>
            {applying ? "Loading…" : "Apply from today"}
          </button>
          <button className="secondary-btn compact no-print" onClick={() => window.print()}>Print</button>
          <button className="primary-btn no-print" onClick={save}>{saved ? "Saved ✓" : "Save"}</button>
        </div>
      </div>
      {applyMsg && <div className="cc-apply-msg">{applyMsg}</div>}

      <div className="cc-sheet">

        {/* Total Sales */}
        <div>
          <div className="cc-col-header">Total Sales</div>
          <div className="cc-sales-row">
            {[["Gross", "sales.gross"], ["Net", "sales.net"], ["Profit", "sales.profit"]].map(([label, path]) => (
              <span className="cc-sales-field" key={label}>
                <label className="cc-label">{label}:</label>
                <input className="cc-input cc-money" value={getPath(path)} onChange={(e) => setPath(path, e.target.value)} placeholder="$0.00" />
              </span>
            ))}
          </div>
        </div>

        <div className="cc-divider-h" />

        {/* Leftover Bread + Closing Temps */}
        <div className="cc-two-col">
          <div className="cc-col">
            <div className="cc-col-header">Leftover Bread</div>
            {cfg.bread_types.map((b) => (
              <div className="cc-field-row" key={b}>
                <label className="cc-label">{b}:</label>
                <NumSelect value={getPath(`bread.${b}`)} onChange={(v) => setPath(`bread.${b}`, v)} />
              </div>
            ))}
          </div>
          <div className="cc-divider" />
          <div className="cc-col">
            <div className="cc-col-header">Closing Temps</div>
            {cfg.bread_types.map((b) => (
              <div className="cc-field-row" key={b}>
                <label className="cc-label">{b}:</label>
                <input className="cc-input cc-temp" value={getPath(`temps.${b}`)} onChange={(e) => setPath(`temps.${b}`, e.target.value)} placeholder="°F" />
              </div>
            ))}
          </div>
        </div>

        <div className="cc-divider-h" />

        {/* Ingredients */}
        <div>
          <div className="cc-col-header">Ingredients</div>
          <div className="cc-ing-row">
            {["Meat", "Cheese", "Tomatoes", "Lettuce", "Onions"].map((ing) => (
              <div className="cc-ing-field" key={ing}>
                <label className="cc-label">{ing}:</label>
                <input className="cc-input" value={getPath(`ingredients.${ing}`)} onChange={(e) => setPath(`ingredients.${ing}`, e.target.value)} placeholder="__" />
              </div>
            ))}
          </div>
        </div>

        <div className="cc-divider-h" />

        {/* Items sold + Sandwiches sold */}
        <div className="cc-two-col">
          <div className="cc-col">
            <div className="cc-col-header">Items Sold</div>
            {cfg.soups.map((name) => (
              <div className="cc-field-row" key={name}>
                <label className="cc-label">{name}:</label>
                <NumSelect value={getPath(`soups.${name}`)} onChange={(v) => setPath(`soups.${name}`, v)} max={99} />
              </div>
            ))}
          </div>
          <div className="cc-divider" />
          <div className="cc-col">
            <div className="cc-col-header">Sandwiches Sold</div>
            {cfg.sandwiches.map((sw) => (
              <div className="cc-field-row" key={sw.name}>
                <label className="cc-label">{sw.name}:</label>
                {sw.sizes.map((sz) => (
                  <span className="cc-size-pair" key={sz}>
                    <span className="cc-size-label">{sz}</span>
                    <NumSelect value={getPath(`sandwiches.${sw.name}.${sz}`)} onChange={(v) => setPath(`sandwiches.${sw.name}.${sz}`, v)} max={99} />
                  </span>
                ))}
              </div>
            ))}
          </div>
        </div>

        <div className="cc-divider-h" />

        {/* Employee Subs + Sides */}
        <div className="cc-two-col">
          <div className="cc-col">
            <div className="cc-col-header">Employee Subs</div>
            <div className="cc-ing-row">
              {cfg.emp_sub_sizes.map((sz) => (
                <div className="cc-ing-field" key={sz}>
                  <label className="cc-label">{sz}:</label>
                  <NumSelect value={getPath(`emp_subs.${sz}`)} onChange={(v) => setPath(`emp_subs.${sz}`, v)} max={20} />
                </div>
              ))}
            </div>
          </div>
          <div className="cc-divider" />
          <div className="cc-col">
            <div className="cc-col-header">Employee Sides</div>
            <div className="cc-ing-row">
              {cfg.emp_sides.map((side) => (
                <div className="cc-ing-field" key={side}>
                  <label className="cc-label">{side}:</label>
                  <NumSelect value={getPath(`emp_sides.${side}`)} onChange={(v) => setPath(`emp_sides.${side}`, v)} max={20} />
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="cc-divider-h" />

        {/* Who Worked */}
        <div>
          <div className="cc-col-header">Who Worked</div>
          <div className="cc-who-grid">
            {cfg.employees.map((emp) => (
              <div className="cc-who-row" key={emp}>
                <label className="cc-label cc-emp-label">{emp}:</label>
                <TimeRange value={getPath(`who_worked.${emp}`, {})} onChange={(v) => setPath(`who_worked.${emp}`, v)} />
              </div>
            ))}
          </div>
        </div>

        <div className="cc-divider-h" />

        {/* Notes */}
        <div>
          <div className="cc-col-header">Notes</div>
          <textarea className="cc-notes" rows={3} value={getPath("notes")} onChange={(e) => setPath("notes", e.target.value)} placeholder="Issues, waste, incidents…" />
        </div>

      </div>
    </div>
  );
}
