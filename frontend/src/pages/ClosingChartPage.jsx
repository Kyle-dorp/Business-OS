import { useEffect, useState } from "react";

function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const EMPTY = {
  bread: { italian: "", jalapeno: "", herb: "", white: "" },
  temps: { italian: "", jalapeno: "", herb: "", white: "" },
  ingredients: { meat: "", cheese: "", tomatoes: "", lettuce: "", onions: "" },
  notes: "",
};

const BREAD_TYPES = ["italian", "jalapeno", "herb", "white"];
const BREAD_LABELS = { italian: "Italian", jalapeno: "Jalapeño", herb: "Herb", white: "White" };
const ING_TYPES = ["meat", "cheese", "tomatoes", "lettuce", "onions"];
const ING_LABELS = { meat: "Meat", cheese: "Cheese", tomatoes: "Tomatoes", lettuce: "Lettuce", onions: "Onions" };

export default function ClosingChartPage() {
  const [date, setDate] = useState(todayISO);
  const [form, setForm] = useState(EMPTY);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(`closing-chart-${date}`);
      setForm(raw ? { ...EMPTY, ...JSON.parse(raw) } : EMPTY);
    } catch {
      setForm(EMPTY);
    }
    setSaved(false);
  }, [date]);

  function setField(section, key, value) {
    setForm((prev) => ({ ...prev, [section]: { ...prev[section], [key]: value } }));
    setSaved(false);
  }

  function save() {
    localStorage.setItem(`closing-chart-${date}`, JSON.stringify(form));
    setSaved(true);
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
          <button className="secondary-btn compact no-print" onClick={() => window.print()}>Print</button>
          <button className="primary-btn no-print" onClick={save}>{saved ? "Saved ✓" : "Save"}</button>
        </div>
      </div>

      <div className="cc-sheet">
        {/* Bread + Temps */}
        <div className="cc-two-col">
          <div className="cc-col">
            <div className="cc-col-header">Leftover Bread</div>
            {BREAD_TYPES.map((t) => (
              <div className="cc-field-row" key={t}>
                <label className="cc-label">{BREAD_LABELS[t]}:</label>
                <input className="cc-input" value={form.bread[t]} onChange={(e) => setField("bread", t, e.target.value)} placeholder="___" />
              </div>
            ))}
          </div>
          <div className="cc-divider" />
          <div className="cc-col">
            <div className="cc-col-header">Closing Temps</div>
            {BREAD_TYPES.map((t) => (
              <div className="cc-field-row" key={t}>
                <label className="cc-label">{BREAD_LABELS[t]}:</label>
                <input className="cc-input cc-input-temp" value={form.temps[t]} onChange={(e) => setField("temps", t, e.target.value)} placeholder="°F" />
              </div>
            ))}
          </div>
        </div>

        <div className="cc-divider-h" />

        {/* Ingredients */}
        <div className="cc-ing-section">
          <div className="cc-col-header">Ingredients</div>
          <div className="cc-ing-row">
            {ING_TYPES.map((t) => (
              <div className="cc-ing-field" key={t}>
                <label className="cc-label">{ING_LABELS[t]}:</label>
                <input className="cc-input" value={form.ingredients[t]} onChange={(e) => setField("ingredients", t, e.target.value)} placeholder="__" />
              </div>
            ))}
          </div>
        </div>

        <div className="cc-divider-h" />

        {/* Notes */}
        <div className="cc-notes-section">
          <div className="cc-col-header">Notes</div>
          <textarea
            className="cc-notes"
            rows={3}
            value={form.notes}
            onChange={(e) => setForm((prev) => ({ ...prev, notes: e.target.value }))}
            placeholder="Issues, waste, incidents…"
          />
        </div>
      </div>
    </div>
  );
}
