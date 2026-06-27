import { useEffect, useState } from "react";

function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const DEFAULT_CONFIG = {
  sections: [
    { id: "leftover_bread", label: "Leftover Bread", inline: false, fields: ["Italian", "Jalapeño", "Herb", "White"] },
    { id: "closing_temps", label: "Closing Temps", inline: false, fields: ["Italian", "Jalapeño", "Herb", "White"] },
    { id: "ingredients", label: "Ingredients", inline: true, fields: ["Meat", "Cheese", "Tomatoes", "Lettuce", "Onions"] },
  ],
  paired: [["leftover_bread", "closing_temps"]],
};

function Section({ section, values, onChange }) {
  return (
    <div className="cc-col">
      <div className="cc-col-header">{section.label}</div>
      {section.inline ? (
        <div className="cc-ing-row">
          {section.fields.map((field) => (
            <div className="cc-ing-field" key={field}>
              <label className="cc-label">{field}:</label>
              <input className="cc-input" value={values[field] || ""} onChange={(e) => onChange(field, e.target.value)} placeholder="__" />
            </div>
          ))}
        </div>
      ) : (
        section.fields.map((field) => (
          <div className="cc-field-row" key={field}>
            <label className="cc-label">{field}:</label>
            <input className="cc-input" value={values[field] || ""} onChange={(e) => onChange(field, e.target.value)} placeholder="___" />
          </div>
        ))
      )}
    </div>
  );
}

export default function ClosingChartPage({ config: rawConfig }) {
  const config = rawConfig || DEFAULT_CONFIG;
  const [date, setDate] = useState(todayISO);
  const [form, setForm] = useState({});
  const [notes, setNotes] = useState("");
  const [saved, setSaved] = useState(false);

  const storageKey = `closing-chart-${date}`;

  useEffect(() => {
    try {
      const raw = localStorage.getItem(storageKey);
      const parsed = raw ? JSON.parse(raw) : {};
      setForm(parsed.fields || {});
      setNotes(parsed.notes || "");
    } catch {
      setForm({});
      setNotes("");
    }
    setSaved(false);
  }, [date, storageKey]);

  function setField(sectionId, field, value) {
    setForm((prev) => ({ ...prev, [sectionId]: { ...(prev[sectionId] || {}), [field]: value } }));
    setSaved(false);
  }

  function save() {
    localStorage.setItem(storageKey, JSON.stringify({ fields: form, notes }));
    setSaved(true);
  }

  // Build layout: paired groups + remaining full-width sections
  const pairedIds = new Set((config.paired || []).flat());
  const sectionMap = Object.fromEntries((config.sections || []).map((s) => [s.id, s]));
  const fullWidthSections = (config.sections || []).filter((s) => !pairedIds.has(s.id));

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
        {/* Paired (side-by-side) groups */}
        {(config.paired || []).map((group, idx) => {
          const sections = group.map((id) => sectionMap[id]).filter(Boolean);
          if (!sections.length) return null;
          return (
            <div key={idx}>
              {idx > 0 && <div className="cc-divider-h" />}
              <div className="cc-two-col" style={{ gridTemplateColumns: sections.length === 1 ? "1fr" : Array.from({ length: sections.length }, (_, i) => i < sections.length - 1 ? "1fr 1px" : "1fr").join(" ") }}>
                {sections.map((section, si) => (
                  <div key={section.id} style={{ display: "contents" }}>
                    {si > 0 && <div className="cc-divider" />}
                    <Section section={section} values={form[section.id] || {}} onChange={(f, v) => setField(section.id, f, v)} />
                  </div>
                ))}
              </div>
            </div>
          );
        })}

        {/* Full-width sections */}
        {fullWidthSections.map((section) => (
          <div key={section.id}>
            <div className="cc-divider-h" />
            <Section section={section} values={form[section.id] || {}} onChange={(f, v) => setField(section.id, f, v)} />
          </div>
        ))}

        {/* Notes — always at bottom */}
        <div className="cc-divider-h" />
        <div className="cc-notes-section">
          <div className="cc-col-header">Notes</div>
          <textarea
            className="cc-notes"
            rows={3}
            value={notes}
            onChange={(e) => { setNotes(e.target.value); setSaved(false); }}
            placeholder="Issues, waste, incidents…"
          />
        </div>
      </div>
    </div>
  );
}
