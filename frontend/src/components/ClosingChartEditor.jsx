import { useState } from "react";
import { EditableList } from "./EditableList";

const DEFAULTS = {
  employees: ["Bam", "June", "Kyle", "Hunter"],
  bread_types: ["Italian", "Jalapeño", "Herb", "White"],
  bread_count_columns: ["Leftover Bread"],
  sandwiches: [{ name: "Dagwoods", sizes: ['6"', '12"'] }, { name: "Bomb", sizes: ['6"', '12"'] }],
  soups: ["Soups sold", "Ajous sold"],
  emp_sub_sizes: ['12"', '6"'],
  emp_sides: ["Chips", "Soda", "Brownie"],
  finance_fields: [],
};

export default function ClosingChartEditor({ config, onSave, onClose }) {
  const [cfg, setCfg] = useState(() => ({ ...DEFAULTS, ...(config || {}) }));
  const [saving, setSaving] = useState(false);

  function set(key, val) { setCfg((prev) => ({ ...prev, [key]: val })); }

  function setSandwichName(i, name) {
    const next = cfg.sandwiches.map((sw, idx) => idx === i ? { ...sw, name } : sw);
    set("sandwiches", next);
  }
  function setSandwichSizes(i, sizes) {
    const next = cfg.sandwiches.map((sw, idx) => idx === i ? { ...sw, sizes } : sw);
    set("sandwiches", next);
  }
  function moveSandwich(i, dir) {
    const j = i + dir;
    if (j < 0 || j >= cfg.sandwiches.length) return;
    const next = [...cfg.sandwiches];
    [next[i], next[j]] = [next[j], next[i]];
    set("sandwiches", next);
  }
  function addSandwich() { set("sandwiches", [...cfg.sandwiches, { name: "New Sub", sizes: ['6"', '12"'] }]); }
  function removeSandwich(i) { set("sandwiches", cfg.sandwiches.filter((_, idx) => idx !== i)); }

  async function handleSave() {
    setSaving(true);
    await onSave(cfg);
    setSaving(false);
    onClose();
  }

  return (
    <div className="cfe-overlay" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="cfe-panel">
        <div className="cfe-header">
          <strong>Edit Closing Chart</strong>
          <button className="cfe-close" onClick={onClose}>×</button>
        </div>

        <div className="cfe-body">
          <Section label="Finance Fields" hint="Shown above Total Sales. Leave empty to hide.">
            <EditableList items={cfg.finance_fields || []} onChange={(v) => set("finance_fields", v)} placeholder="Opening Register" />
          </Section>

          <Section label="Employees" hint="Appear in Who Worked with time inputs.">
            <EditableList items={cfg.employees} onChange={(v) => set("employees", v)} placeholder="Name" />
          </Section>

          <Section label="Bread Types" hint="Rows in every bread column and Closing Temps.">
            <EditableList items={cfg.bread_types} onChange={(v) => set("bread_types", v)} placeholder="Bread type" />
          </Section>

          <Section label="Bread Count Columns" hint="Columns between Total Sales and Closing Temps. Closing Temps is always last.">
            <EditableList items={cfg.bread_count_columns || ["Leftover Bread"]} onChange={(v) => set("bread_count_columns", v)} placeholder="Column name" />
          </Section>

          <Section label="Sandwiches Sold">
            {cfg.sandwiches.map((sw, i) => (
              <div className="cfe-sandwich-row" key={i}>
                <div className="cfe-sandwich-arrows">
                  <button type="button" onClick={() => moveSandwich(i, -1)} disabled={i === 0}>↑</button>
                  <button type="button" onClick={() => moveSandwich(i, 1)} disabled={i === cfg.sandwiches.length - 1}>↓</button>
                </div>
                <div className="cfe-sandwich-fields">
                  <input className="edl-input" value={sw.name} onChange={(e) => setSandwichName(i, e.target.value)} placeholder="Name" />
                  <input className="edl-input cfe-sizes-input" value={sw.sizes.join(", ")} onChange={(e) => setSandwichSizes(i, e.target.value.split(",").map((s) => s.trim()).filter(Boolean))} placeholder={`6", 12"`} />
                </div>
                <button type="button" className="edl-remove" onClick={() => removeSandwich(i)}>×</button>
              </div>
            ))}
            <button type="button" className="edl-add" onClick={addSandwich}>+ Add sandwich</button>
            <p className="cfe-hint">Second field is a comma-separated list of sizes e.g. <code>6", 12"</code></p>
          </Section>

          <Section label="Items Sold" hint="Rows in the Items Sold column (soups, ajous, etc.).">
            <EditableList items={cfg.soups} onChange={(v) => set("soups", v)} placeholder="Item name" />
          </Section>

          <Section label="Employee Sub Sizes">
            <EditableList items={cfg.emp_sub_sizes} onChange={(v) => set("emp_sub_sizes", v)} placeholder={`12"`} />
          </Section>

          <Section label="Employee Sides">
            <EditableList items={cfg.emp_sides} onChange={(v) => set("emp_sides", v)} placeholder="Chips" />
          </Section>
        </div>

        <div className="cfe-footer">
          <button className="secondary-btn" onClick={onClose}>Cancel</button>
          <button className="primary-btn" disabled={saving} onClick={handleSave}>{saving ? "Saving…" : "Save changes"}</button>
        </div>
      </div>
    </div>
  );
}

function Section({ label, hint, children }) {
  return (
    <div className="cfe-section">
      <div className="cfe-section-label">{label}</div>
      {hint && <p className="cfe-hint">{hint}</p>}
      {children}
    </div>
  );
}
