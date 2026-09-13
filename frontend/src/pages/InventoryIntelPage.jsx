import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";

/**
 * Recipes, counts, waste, and what the three of them together reveal.
 *
 * The chain is: sales x recipes = what *should* have been used. Minus logged
 * waste. Against a physical count. What is left over is product that walked out
 * without being sold, wasted or recorded — and that number is invisible to any
 * tool that cannot see sales and stock in the same place.
 *
 * The tabs are ordered the way the work actually happens, not by importance.
 */

const TABS = [
  ["variance", "Where it goes"],
  ["recipes", "Recipes"],
  ["count", "Count stock"],
  ["waste", "Waste log"],
  ["menu", "Menu margins"],
];

const money = (n) => `$${Math.abs(Number(n) || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

/* ------------------------------------------------------------- variance */

function Variance({ onGoToRecipes }) {
  const [data, setData] = useState(null);
  const [days, setDays] = useState(30);
  const [error, setError] = useState("");

  useEffect(() => {
    setData(null);
    api(`/ops/inventory/variance?days=${days}`).then(setData).catch((e) => setError(e.message));
  }, [days]);

  if (error) return <p className="sec-error">{error}</p>;
  if (!data) return <section className="card os-loading">Working out where it went…</section>;

  const leak = data.total_unexplained_value < 0;

  return (
    <>
      <div className="inv-toolbar">
        <div className="os-field">
          <span>Period</span>
          <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </div>
      </div>

      {data.items.length === 0 ? (
        <section className="card inv-empty-state">
          <h3>Nothing to compare against yet</h3>
          <p>{data.note}</p>
          <button className="primary-btn" onClick={onGoToRecipes}>Start with a recipe</button>
        </section>
      ) : (
        <>
          <section className={`card inv-headline ${leak ? "is-leak" : "is-fine"}`}>
            <div>
              <span className="inv-headline-label">
                {leak ? "Unexplained loss" : "Unexplained variance"}
              </span>
              <strong>{money(data.total_unexplained_value)}</strong>
              <small>over the last {data.period_days} days</small>
            </div>
            {leak && (
              <div className="inv-projection">
                <span>At this rate, a year costs</span>
                <strong>{money(data.annualized_projection)}</strong>
              </div>
            )}
          </section>

          {data.worst_offenders.length > 0 && (
            <section className="card">
              <h3>Worth chasing first</h3>
              <ul className="inv-offenders">
                {data.worst_offenders.map((o, i) => (
                  <li key={i} className={`sev-${o.severity}`}>
                    <div>
                      <strong>{o.item}</strong>
                      <small>{o.sku}</small>
                    </div>
                    <span className="inv-offender-value">{money(o.unexplained_value)}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section className="card">
            <h3>Every counted item</h3>
            <div className="os-table-wrap">
              <table className="os-table">
                <thead>
                  <tr>
                    <th>Item</th><th>Counted</th><th>Expected</th>
                    <th>Used (theory)</th><th>Waste logged</th><th>Unexplained</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((r, i) => (
                    <tr key={i}>
                      <td><strong>{r.item}</strong><small>{r.sku}</small></td>
                      <td>{r.counted}</td>
                      <td>{r.expected}</td>
                      <td>{r.theoretical_usage}</td>
                      <td>{r.logged_waste}</td>
                      <td className={r.unexplained_value < 0 ? "inv-neg" : "inv-pos"}>
                        {r.unexplained_value < 0 ? "−" : ""}{money(r.unexplained_value)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="inv-note">{data.note}</p>
          </section>
        </>
      )}
    </>
  );
}

/* -------------------------------------------------------------- recipes */

function RecipeCard({ recipe, items, onChanged }) {
  const [open, setOpen] = useState(false);
  const [adding, setAdding] = useState({ inventory_item_id: "", quantity: "", waste_factor_percent: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const byId = useMemo(() => Object.fromEntries(items.map((i) => [i.id, i])), [items]);

  async function addComponent(e) {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      await api(`/ops/inventory/recipes/${recipe.id}/components`, {
        method: "POST",
        body: JSON.stringify({
          inventory_item_id: Number(adding.inventory_item_id),
          quantity: Number(adding.quantity),
          waste_factor_percent: Number(adding.waste_factor_percent) || 0,
        }),
      });
      setAdding({ inventory_item_id: "", quantity: "", waste_factor_percent: "" });
      onChanged();
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }

  async function removeComponent(id) {
    setBusy(true); setError("");
    try {
      await api(`/ops/inventory/components/${id}`, { method: "DELETE" });
      onChanged();
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }

  const flag = recipe.flag;

  return (
    <section className={`card inv-recipe${open ? " is-open" : ""}`}>
      <button className="inv-recipe-head" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="inv-recipe-name">
          <strong>{recipe.name}</strong>
          <small>{recipe.component_count} ingredient{recipe.component_count === 1 ? "" : "s"}</small>
        </span>
        <span className="inv-recipe-figures">
          <span className="inv-fig"><small>cost</small><b>${recipe.cost?.toFixed(2) ?? "—"}</b></span>
          <span className="inv-fig"><small>sells</small><b>${recipe.sells_for?.toFixed(2) ?? "—"}</b></span>
          <span className={`inv-fig inv-flag-${flag}`}>
            <small>food cost</small>
            <b>{recipe.food_cost_percent != null ? `${recipe.food_cost_percent}%` : "—"}</b>
          </span>
        </span>
      </button>

      {open && (
        <div className="inv-recipe-body">
          {flag === "high_cost" && (
            <div className="alert error inv-inline-alert">
              Food cost above 35%. Most kitchens target 28–35% — this one is thin.
            </div>
          )}
          {flag === "no_price" && (
            <div className="alert notice inv-inline-alert">
              No sale price on the linked item, so margin cannot be worked out.
            </div>
          )}

          {recipe.components.length > 0 ? (
            <table className="os-table inv-components">
              <thead><tr><th>Ingredient</th><th>Qty</th><th>Waste</th><th>Cost</th><th></th></tr></thead>
              <tbody>
                {recipe.components.map((c) => {
                  const item = byId[c.inventory_item_id];
                  const effective = c.quantity * (1 + (c.waste_factor_percent || 0) / 100);
                  return (
                    <tr key={c.id}>
                      <td>{item?.name || "Unknown item"}</td>
                      <td>{c.quantity} {item?.unit}</td>
                      <td>{c.waste_factor_percent ? `+${c.waste_factor_percent}%` : "—"}</td>
                      <td>${(effective * (item?.unit_cost || 0)).toFixed(2)}</td>
                      <td className="inv-row-action">
                        <button className="ghost-btn" onClick={() => removeComponent(c.id)} disabled={busy}>
                          Remove
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : (
            <p className="inv-note">No ingredients yet. A recipe with none contributes nothing to variance.</p>
          )}

          <form className="inv-add-row" onSubmit={addComponent}>
            <select
              value={adding.inventory_item_id}
              onChange={(e) => setAdding({ ...adding, inventory_item_id: e.target.value })}
              required
            >
              <option value="">Add an ingredient…</option>
              {items.map((i) => <option key={i.id} value={i.id}>{i.name} ({i.unit})</option>)}
            </select>
            <input
              type="number" step="0.001" min="0" placeholder="Qty" required
              value={adding.quantity}
              onChange={(e) => setAdding({ ...adding, quantity: e.target.value })}
            />
            <input
              type="number" step="1" min="0" max="100" placeholder="Waste %"
              title="Trim, spillage and cooking loss, added on top"
              value={adding.waste_factor_percent}
              onChange={(e) => setAdding({ ...adding, waste_factor_percent: e.target.value })}
            />
            <button className="primary-btn" disabled={busy}>Add</button>
          </form>

          {error && <p className="sec-error">{error}</p>}
        </div>
      )}
    </section>
  );
}

function Recipes() {
  const [data, setData] = useState(null);
  const [creating, setCreating] = useState({ name: "", sells_as_item_id: "", yield_quantity: "1" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api("/ops/inventory/recipes").then(setData).catch((e) => setError(e.message));
  }, []);
  useEffect(() => { load(); }, [load]);

  async function create(e) {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      await api("/ops/inventory/recipes", {
        method: "POST",
        body: JSON.stringify({
          name: creating.name,
          sells_as_item_id: creating.sells_as_item_id ? Number(creating.sells_as_item_id) : null,
          yield_quantity: Number(creating.yield_quantity) || 1,
        }),
      });
      setCreating({ name: "", sells_as_item_id: "", yield_quantity: "1" });
      load();
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }

  if (!data) return <section className="card os-loading">Loading recipes…</section>;

  const sellable = data.items.filter((i) => i.sales_price > 0 || i.item_type === "service");

  return (
    <>
      <section className="card inv-create">
        <h3>New recipe</h3>
        <p className="inv-note">{data.why_it_matters}</p>
        <form className="inv-create-row" onSubmit={create}>
          <input
            placeholder="Recipe name" required
            value={creating.name}
            onChange={(e) => setCreating({ ...creating, name: e.target.value })}
          />
          <select
            value={creating.sells_as_item_id}
            onChange={(e) => setCreating({ ...creating, sells_as_item_id: e.target.value })}
          >
            <option value="">Sold as… (optional)</option>
            {sellable.map((i) => <option key={i.id} value={i.id}>{i.name}</option>)}
          </select>
          <input
            type="number" step="0.1" min="0.1" title="How many portions one batch makes"
            value={creating.yield_quantity}
            onChange={(e) => setCreating({ ...creating, yield_quantity: e.target.value })}
          />
          <button className="primary-btn" disabled={busy || !creating.name.trim()}>Create</button>
        </form>
        {error && <p className="sec-error">{error}</p>}
      </section>

      {data.recipes.length === 0 ? (
        <section className="card inv-empty-state">
          <h3>No recipes yet</h3>
          <p>
            Link what you sell to what it is made of. Every sale then implies a
            draw-down, and the gap between that and a physical count is the
            money you are losing without knowing it.
          </p>
        </section>
      ) : (
        data.recipes.map((r) => (
          <RecipeCard key={r.id} recipe={r} items={data.items} onChanged={load} />
        ))
      )}
    </>
  );
}

/* ---------------------------------------------------------------- count */

function CountStock() {
  const [items, setItems] = useState(null);
  const [counts, setCounts] = useState({});
  const [results, setResults] = useState({});
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("");

  useEffect(() => {
    api("/ops/inventory/recipes").then((d) => setItems(d.items)).catch((e) => setError(e.message));
  }, []);

  async function submit(item) {
    const raw = counts[item.id];
    if (raw === undefined || raw === "") return;
    setBusy(item.id); setError("");
    try {
      const res = await api("/ops/inventory/count", {
        method: "POST",
        body: JSON.stringify({ inventory_item_id: item.id, counted_quantity: Number(raw) }),
      });
      setResults({ ...results, [item.id]: res });
      setCounts({ ...counts, [item.id]: "" });
      setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, on_hand: res.counted } : i)));
    } catch (err) { setError(err.message); } finally { setBusy(""); }
  }

  if (!items) return <section className="card os-loading">Loading stock…</section>;

  const shown = filter
    ? items.filter((i) => `${i.name} ${i.sku}`.toLowerCase().includes(filter.toLowerCase()))
    : items;

  return (
    <section className="card">
      <h3>Physical count</h3>
      <p className="inv-note">
        Enter what is actually on the shelf. The system records what it believed
        at that moment, so the difference is measured against the right number
        rather than whatever stock has drifted to by the time anyone reads a report.
      </p>

      <input
        className="inv-filter"
        placeholder="Find an item…"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
      />

      {error && <p className="sec-error">{error}</p>}

      <div className="os-table-wrap">
        <table className="os-table">
          <thead><tr><th>Item</th><th>System says</th><th>Actually counted</th><th></th></tr></thead>
          <tbody>
            {shown.map((item) => {
              const res = results[item.id];
              return (
                <tr key={item.id}>
                  <td><strong>{item.name}</strong><small>{item.sku}</small></td>
                  <td>{item.on_hand} {item.unit}</td>
                  <td>
                    <input
                      type="number" step="0.001" min="0" placeholder="—"
                      value={counts[item.id] ?? ""}
                      onChange={(e) => setCounts({ ...counts, [item.id]: e.target.value })}
                      onKeyDown={(e) => e.key === "Enter" && submit(item)}
                    />
                  </td>
                  <td className="inv-row-action">
                    {res ? (
                      <span className={res.variance < 0 ? "inv-neg" : res.variance > 0 ? "inv-pos" : "inv-flat"}>
                        {res.variance === 0
                          ? "Matched"
                          : `${res.variance > 0 ? "+" : "−"}${Math.abs(res.variance)} · ${money(res.variance_value)}`}
                      </span>
                    ) : (
                      <button
                        className="primary-btn"
                        onClick={() => submit(item)}
                        disabled={busy === item.id || counts[item.id] === undefined || counts[item.id] === ""}
                      >
                        {busy === item.id ? "…" : "Record"}
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

/* ---------------------------------------------------------------- waste */

const REASON_LABEL = {
  spoilage: "Spoilage", breakage: "Breakage", comp: "Comped",
  staff_meal: "Staff meal", prep_error: "Prep error",
};

function Waste() {
  const [data, setData] = useState(null);
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({ inventory_item_id: "", quantity: "", reason: "spoilage", notes: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    Promise.all([api("/ops/inventory/waste"), api("/ops/inventory/recipes")])
      .then(([w, r]) => { setData(w); setItems(r.items); })
      .catch((e) => setError(e.message));
  }, []);
  useEffect(() => { load(); }, [load]);

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      await api("/ops/inventory/waste", {
        method: "POST",
        body: JSON.stringify({
          inventory_item_id: Number(form.inventory_item_id),
          quantity: Number(form.quantity),
          reason: form.reason,
          notes: form.notes,
        }),
      });
      setForm({ inventory_item_id: "", quantity: "", reason: "spoilage", notes: "" });
      load();
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }

  if (!data) return <section className="card os-loading">Loading waste log…</section>;

  return (
    <>
      <section className="card inv-create">
        <h3>Log waste</h3>
        <p className="inv-note">
          Recording waste is what makes variance mean something. Unexplained loss
          with no waste log is just noise — what is left after waste is accounted
          for is the number worth chasing.
        </p>
        <form className="inv-waste-row" onSubmit={submit}>
          <select
            value={form.inventory_item_id} required
            onChange={(e) => setForm({ ...form, inventory_item_id: e.target.value })}
          >
            <option value="">Item…</option>
            {items.map((i) => <option key={i.id} value={i.id}>{i.name} ({i.unit})</option>)}
          </select>
          <input
            type="number" step="0.001" min="0" placeholder="Qty" required
            value={form.quantity}
            onChange={(e) => setForm({ ...form, quantity: e.target.value })}
          />
          <select value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })}>
            {data.reasons.map((r) => <option key={r} value={r}>{REASON_LABEL[r] || r}</option>)}
          </select>
          <input
            placeholder="Note (optional)"
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
          />
          <button className="primary-btn" disabled={busy}>Log</button>
        </form>
        {error && <p className="sec-error">{error}</p>}
      </section>

      {Object.keys(data.by_reason).length > 0 && (
        <section className="card">
          <h3>Last {data.period_days} days — {money(data.total_value)}</h3>
          <div className="inv-reason-grid">
            {Object.entries(data.by_reason).map(([reason, value]) => (
              <div key={reason} className="inv-reason">
                <span>{REASON_LABEL[reason] || reason}</span>
                <strong>{money(value)}</strong>
              </div>
            ))}
          </div>
        </section>
      )}

      {data.entries.length > 0 && (
        <section className="card">
          <h3>Entries</h3>
          <div className="os-table-wrap">
            <table className="os-table">
              <thead><tr><th>When</th><th>Item</th><th>Qty</th><th>Reason</th><th>Value</th></tr></thead>
              <tbody>
                {data.entries.map((e) => (
                  <tr key={e.id}>
                    <td>{String(e.occurred_at).slice(0, 10)}</td>
                    <td><strong>{e.item}</strong>{e.notes && <small>{e.notes}</small>}</td>
                    <td>{e.quantity}</td>
                    <td>{REASON_LABEL[e.reason] || e.reason}</td>
                    <td className="inv-neg">{money(e.value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  );
}

/* ----------------------------------------------------------------- menu */

const QUADRANT = {
  star: ["Star", "Popular and profitable. Protect these."],
  workhorse: ["Workhorse", "Sells well, thin margin. Worth repricing."],
  puzzle: ["Puzzle", "Good margin, few takers. Promote it."],
  drop_or_rework: ["Rework", "Neither popular nor profitable."],
};

function Menu() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/ops/inventory/menu-engineering").then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="sec-error">{error}</p>;
  if (!data) return <section className="card os-loading">Ranking your menu…</section>;
  if (!data.recipes.length) {
    return (
      <section className="card inv-empty-state">
        <h3>Not enough to rank yet</h3>
        <p>{data.note}</p>
      </section>
    );
  }

  return (
    <section className="card">
      <h3>Last {data.period_days} days</h3>
      <p className="inv-note">
        Ranked by total margin — what each item actually contributed, not what it
        earns per plate. Needs recipe cost and sales volume together, which is
        why a standalone tool cannot do it.
      </p>
      <div className="os-table-wrap">
        <table className="os-table">
          <thead>
            <tr><th>Item</th><th>Sold</th><th>Cost</th><th>Sells</th><th>Margin</th><th>Contributed</th><th>Verdict</th></tr>
          </thead>
          <tbody>
            {data.recipes.map((r) => {
              const [label, hint] = QUADRANT[r.quadrant] || ["—", ""];
              return (
                <tr key={r.recipe_id}>
                  <td><strong>{r.recipe}</strong></td>
                  <td>{r.units_sold}</td>
                  <td>${r.cost?.toFixed(2)}</td>
                  <td>${r.sells_for?.toFixed(2)}</td>
                  <td>${r.margin?.toFixed(2)}</td>
                  <td className="inv-pos">{money(r.total_margin)}</td>
                  <td><span className={`inv-quadrant q-${r.quadrant}`} title={hint}>{label}</span></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------------- page */

export default function InventoryIntelPage() {
  const [tab, setTab] = useState("variance");

  return (
    <div className="page inv-page">
      <div className="os-heading">
        <div>
          <span className="eyebrow">INVENTORY</span>
          <h1>Where the money actually goes</h1>
          <p>What sold, what should have been used, and what is missing.</p>
        </div>
      </div>

      <div className="inv-tabs">
        {TABS.map(([id, label]) => (
          <button
            key={id}
            className={`inv-tab${tab === id ? " is-active" : ""}`}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "variance" && <Variance onGoToRecipes={() => setTab("recipes")} />}
      {tab === "recipes" && <Recipes />}
      {tab === "count" && <CountStock />}
      {tab === "waste" && <Waste />}
      {tab === "menu" && <Menu />}
    </div>
  );
}
