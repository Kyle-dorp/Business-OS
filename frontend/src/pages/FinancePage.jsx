import { useEffect, useMemo, useState } from "react";
import { api } from "../api";

const money = (cents = 0, compact = false) => {
  if (compact && Math.abs(cents) >= 100000) {
    const k = cents / 100000;
    return `$${Math.abs(k) >= 10 ? Math.round(k) : k.toFixed(1)}k`;
  }
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(cents / 100);
};
const today = () => new Date().toISOString().slice(0, 10);
const monthStart = () => new Date().toISOString().slice(0, 8) + "01";
const yearStart = () => `${new Date().getFullYear()}-01-01`;

const TABS = [
  { id: "dashboard", label: "Dashboard", icon: "◈" },
  { id: "budget",    label: "Budget",    icon: "⊟" },
  { id: "cashflow",  label: "Cash Flow", icon: "⇌" },
  { id: "accounts",  label: "Accounts",  icon: "≡" },
  { id: "payroll",   label: "Payroll",   icon: "◎" },
];

function Field({ label, children }) {
  return (
    <label className="os-field">
      <span>{label}</span>{children}
    </label>
  );
}
function Notice({ text, ok }) {
  if (!text) return null;
  return <p className={`os-alert${ok ? " fin-ok" : ""}`}>{text}</p>;
}
function Table({ headers, rows, footer }) {
  return (
    <div className="os-table-wrap">
      <table className="os-table">
        <thead><tr>{headers.map((h) => <th key={h}>{h}</th>)}</tr></thead>
        <tbody>
          {rows.length
            ? rows.map((row, i) => <tr key={i}>{row.map((cell, j) => <td key={j}>{cell}</td>)}</tr>)
            : <tr><td colSpan={headers.length} className="os-empty">Nothing recorded yet.</td></tr>}
        </tbody>
        {footer && <tfoot><tr>{footer.map((cell, j) => <td key={j}><strong>{cell}</strong></td>)}</tr></tfoot>}
      </table>
    </div>
  );
}
function StatCard({ label, value, sub, color }) {
  return (
    <article className="fin-stat-card" style={color ? { borderTop: `3px solid ${color}` } : undefined}>
      <span>{label}</span>
      <strong>{value}</strong>
      {sub && <small>{sub}</small>}
    </article>
  );
}

const PERIODS = [
  { id: "mtd", label: "This month" },
  { id: "lm",  label: "Last month" },
  { id: "ytd", label: "This year" },
  { id: "all", label: "All time" },
];

function periodDates(id) {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const todayStr = d.toISOString().slice(0, 10);
  if (id === "mtd") return { start: `${y}-${m}-01`, end: todayStr };
  if (id === "lm") {
    const ld = new Date(y, d.getMonth() - 1, 1);
    const ly = ld.getFullYear(), lm2 = String(ld.getMonth() + 1).padStart(2, "0");
    const lastDay = new Date(y, d.getMonth(), 0).toISOString().slice(0, 10);
    return { start: `${ly}-${lm2}-01`, end: lastDay };
  }
  if (id === "ytd") return { start: `${y}-01-01`, end: todayStr };
  return { start: null, end: null };
}

function DashboardTab() {
  const [data, setData] = useState(null);
  const [msg, setMsg] = useState("");
  const [period, setPeriod] = useState("mtd");

  useEffect(() => {
    const { start, end } = periodDates(period);
    const qs = start ? `?start=${start}&end=${end}` : "";
    Promise.all([
      api(`/platform/reports/profit-loss${qs}`),
      api("/platform/reports/balance-sheet"),
      api("/platform/finance/summary"),
    ])
      .then(([pl, bs, sum]) => setData({ pl, bs, sum }))
      .catch((e) => setMsg(e.message));
  }, [period]);

  if (!data) return <div className="os-loading">Loading financial dashboard…</div>;
  const { pl, bs, sum } = data;
  const netMargin = pl.total_income_cents > 0
    ? ((pl.net_income_cents / pl.total_income_cents) * 100).toFixed(1) : 0;
  const periodLabel = PERIODS.find((p) => p.id === period)?.label || "";

  return (
    <div>
      <Notice text={msg} />
      <div style={{ display: "flex", gap: "6px", marginBottom: "14px" }}>
        {PERIODS.map((p) => (
          <button key={p.id} className={period === p.id ? "small-btn active" : "small-btn"} onClick={() => setPeriod(p.id)}>{p.label}</button>
        ))}
      </div>
      <div className="fin-stat-row">
        <StatCard label={`Revenue (${periodLabel})`} value={money(pl.total_income_cents, true)} color="#2f6fed" sub={`${pl.income?.length || 0} income accounts`} />
        <StatCard label={`Expenses (${periodLabel})`} value={money(pl.total_expenses_cents, true)} color="#c73535" sub={`${pl.expenses?.length || 0} expense categories`} />
        <StatCard label="Net Income" value={money(pl.net_income_cents, true)} color={pl.net_income_cents >= 0 ? "#14835f" : "#c73535"} sub={`${netMargin}% net margin`} />
        <StatCard label="Total Assets" value={money(bs.totals?.asset || 0, true)} color="#7259e9" sub="balance sheet" />
        <StatCard label="Liabilities" value={money(bs.totals?.liability || 0, true)} color="#e07a00" sub="owed to others" />
        <StatCard label="Net Worth" value={money((bs.totals?.asset || 0) - (bs.totals?.liability || 0), true)} color="#2e756b" sub="assets minus liabilities" />
      </div>
      <div className="fin-two-col">
        <section className="card fin-section">
          <h2 className="fin-section-title">Money coming &amp; going</h2>
          <div className="fin-mini-table">
            <div className="fin-mini-row header"><span>Category</span><span>Amount</span></div>
            <div className="fin-mini-row green"><span>Receivable (owed to you)</span><span>{money(sum.receivables_cents || 0)}</span></div>
            <div className="fin-mini-row red"><span>Payable (you owe)</span><span>{money(sum.payables_cents || 0)}</span></div>
            <div className="fin-mini-row"><span>Open invoices</span><span>{sum.open_invoices || 0}</span></div>
            <div className="fin-mini-row"><span>Open bills</span><span>{sum.open_bills || 0}</span></div>
            <div className="fin-mini-row highlight"><span>Net cash position</span><span>{money((sum.receivables_cents || 0) - (sum.payables_cents || 0))}</span></div>
          </div>
        </section>
        <section className="card fin-section">
          <h2 className="fin-section-title">P&amp;L — {periodLabel}</h2>
          <div className="fin-mini-table">
            <div className="fin-mini-row header"><span>Account</span><span>Amount</span></div>
            {(pl.income || []).map((item) => (
              <div key={item.account.id} className="fin-mini-row green">
                <span>{item.account.name}</span><span>{money(item.amount_cents)}</span>
              </div>
            ))}
            {(pl.expenses || []).map((item) => (
              <div key={item.account.id} className="fin-mini-row red">
                <span>{item.account.name}</span><span>({money(item.amount_cents)})</span>
              </div>
            ))}
            <div className="fin-mini-row highlight">
              <span>Net income</span>
              <span style={{ color: pl.net_income_cents >= 0 ? "#14835f" : "#c73535" }}>{money(pl.net_income_cents)}</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

function BudgetTab() {
  const [budgets, setBudgets] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [actuals, setActuals] = useState({});
  const [form, setForm] = useState({ period: monthStart().slice(0, 7), account_id: "", amount: "", notes: "" });
  const [msg, setMsg] = useState("");
  const [ok, setOk] = useState(false);

  const expenseAccounts = useMemo(() => accounts.filter((a) => a.account_type === "expense"), [accounts]);
  const incomeAccounts = useMemo(() => accounts.filter((a) => a.account_type === "income"), [accounts]);

  async function load() {
    const [b, a, pl] = await Promise.all([api("/platform/finance/budgets"), api("/platform/accounts"), api("/platform/reports/profit-loss")]);
    setBudgets(b); setAccounts(a);
    const map = {};
    [...(pl.income || []), ...(pl.expenses || [])].forEach((item) => { map[item.account.id] = item.amount_cents; });
    setActuals(map);
  }
  useEffect(() => { load().catch((e) => setMsg(e.message)); }, []);

  async function save() {
    try {
      setMsg(""); setOk(false);
      await api("/platform/finance/budgets", { method: "POST", body: JSON.stringify({ period: form.period + "-01", account_id: Number(form.account_id), amount: Number(form.amount), notes: form.notes }) });
      setOk(true); setMsg("Budget line saved.");
      setForm((f) => ({ ...f, account_id: "", amount: "", notes: "" }));
      await load();
    } catch (e) { setMsg(e.message); }
  }

  const byPeriod = useMemo(() => {
    const map = {};
    budgets.forEach((b) => { const p = b.period.slice(0, 7); if (!map[p]) map[p] = []; map[p].push(b); });
    return map;
  }, [budgets]);

  return (
    <div>
      <Notice text={msg} ok={ok} />
      <section className="card fin-section" style={{ marginBottom: 20 }}>
        <h2 className="fin-section-title">Set a budget line</h2>
        <p className="fin-hint">Enter how much you plan to spend or earn for a given account and month.</p>
        <div className="os-form-grid">
          <Field label="Month"><input type="month" value={form.period} onChange={(e) => setForm({ ...form, period: e.target.value })} /></Field>
          <Field label="Account">
            <select value={form.account_id} onChange={(e) => setForm({ ...form, account_id: e.target.value })}>
              <option value="">Choose account…</option>
              <optgroup label="Income">{incomeAccounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</optgroup>
              <optgroup label="Expense">{expenseAccounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</optgroup>
            </select>
          </Field>
          <Field label="Budget amount ($)"><input type="number" step="0.01" min="0" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} placeholder="0.00" /></Field>
          <Field label="Notes (optional)"><input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="e.g. Q2 target" /></Field>
        </div>
        <button className="primary-btn" onClick={save} disabled={!form.account_id || !form.amount}>Save budget line</button>
      </section>
      {Object.keys(byPeriod).sort().reverse().map((period) => {
        const rows = byPeriod[period];
        const totalBudget = rows.reduce((s, r) => s + r.budget_cents, 0);
        const totalActual = rows.reduce((s, r) => s + (actuals[r.account_id] || 0), 0);
        const variance = totalActual - totalBudget;
        return (
          <section key={period} className="card fin-section" style={{ marginBottom: 16 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
              <h2 className="fin-section-title" style={{ margin: 0 }}>{new Date(period + "-15").toLocaleDateString("en-US", { month: "long", year: "numeric" })}</h2>
              <span style={{ fontSize: ".78rem", fontWeight: 750, padding: "4px 10px", borderRadius: 9, background: variance >= 0 ? "#edf9f3" : "#fef2f2", color: variance >= 0 ? "#14835f" : "#c73535" }}>
                {variance >= 0 ? "▲" : "▼"} {money(Math.abs(variance))} {variance >= 0 ? "over" : "under"} budget
              </span>
            </div>
            <div className="os-table-wrap">
              <table className="os-table">
                <thead><tr><th>Account</th><th>Budget</th><th>Actual</th><th>Variance</th><th>Progress</th><th>Notes</th></tr></thead>
                <tbody>
                  {rows.map((row) => {
                    const actual = actuals[row.account_id] || 0;
                    const diff = actual - row.budget_cents;
                    const pctUsed = row.budget_cents > 0 ? Math.min((actual / row.budget_cents) * 100, 100) : 0;
                    const over = actual > row.budget_cents;
                    return (
                      <tr key={row.id}>
                        <td><strong>{row.account_name}</strong><br /><small style={{ color: "#8a98aa" }}>{row.account_type}</small></td>
                        <td>{money(row.budget_cents)}</td>
                        <td>{money(actual)}</td>
                        <td style={{ color: diff > 0 ? "#14835f" : diff < 0 ? "#c73535" : "inherit", fontWeight: 650 }}>{diff >= 0 ? "+" : ""}{money(diff)}</td>
                        <td style={{ minWidth: 120 }}>
                          <div style={{ height: 8, borderRadius: 4, background: "#e5e9f0", overflow: "hidden" }}>
                            <div style={{ height: "100%", borderRadius: 4, transition: "width .4s", width: `${pctUsed}%`, background: over ? "#c73535" : pctUsed > 80 ? "#e07a00" : "#2f6fed" }} />
                          </div>
                          <small style={{ color: "#66748d", fontSize: ".72rem" }}>{pctUsed.toFixed(0)}% used</small>
                        </td>
                        <td style={{ color: "#8a98aa", fontSize: ".83rem" }}>{row.notes || "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
                <tfoot><tr><td><strong>Total</strong></td><td><strong>{money(totalBudget)}</strong></td><td><strong>{money(totalActual)}</strong></td><td style={{ fontWeight: 750, color: variance >= 0 ? "#14835f" : "#c73535" }}>{variance >= 0 ? "+" : ""}{money(variance)}</td><td colSpan={2} /></tr></tfoot>
              </table>
            </div>
          </section>
        );
      })}
      {budgets.length === 0 && <section className="card fin-section" style={{ textAlign: "center", padding: 48, color: "#8a98aa" }}>No budget lines yet. Add your first one above to start tracking.</section>}
    </div>
  );
}

function CashFlowTab() {
  const [data, setData] = useState(null);
  const [form, setForm] = useState({ start: yearStart(), end: today() });
  const [msg, setMsg] = useState("");

  async function load() {
    try { setMsg(""); setData(await api(`/platform/finance/cashflow?start=${form.start}&end=${form.end}`)); }
    catch (e) { setMsg(e.message); }
  }
  useEffect(() => { load(); }, []);

  return (
    <div>
      <Notice text={msg} />
      <section className="card fin-section" style={{ marginBottom: 20 }}>
        <h2 className="fin-section-title">Date range</h2>
        <div style={{ display: "flex", gap: 14, alignItems: "flex-end", flexWrap: "wrap" }}>
          <Field label="From"><input type="date" value={form.start} onChange={(e) => setForm({ ...form, start: e.target.value })} /></Field>
          <Field label="To"><input type="date" value={form.end} onChange={(e) => setForm({ ...form, end: e.target.value })} /></Field>
          <button className="primary-btn" onClick={load}>Run report</button>
        </div>
      </section>
      {data && (
        <>
          <div className="fin-stat-row" style={{ gridTemplateColumns: "repeat(3,1fr)", marginBottom: 20 }}>
            <StatCard label="Cash inflows" value={money(data.inflows_cents)} color="#14835f" />
            <StatCard label="Cash outflows" value={money(data.outflows_cents)} color="#c73535" />
            <StatCard label="Net cash flow" value={money(data.net_cents)} color={data.net_cents >= 0 ? "#2f6fed" : "#c73535"} />
          </div>
          <section className="card fin-section" style={{ marginBottom: 18 }}>
            <h2 className="fin-section-title">Cash received</h2>
            <Table headers={["Date", "Source", "Description", "Amount"]} rows={(data.inflow_rows || []).map((r) => [r.date, r.source, r.description, money(r.amount_cents)])} footer={["", "", "Total inflows", money(data.inflows_cents)]} />
          </section>
          <section className="card fin-section">
            <h2 className="fin-section-title">Cash paid out</h2>
            <Table headers={["Date", "Source", "Description", "Amount"]} rows={(data.outflow_rows || []).map((r) => [r.date, r.source, r.description, money(r.amount_cents)])} footer={["", "", "Total outflows", money(data.outflows_cents)]} />
          </section>
        </>
      )}
    </div>
  );
}

function AccountsTab() {
  const [accounts, setAccounts] = useState([]);
  const [balances, setBalances] = useState({});
  const [form, setForm] = useState({ code: "", name: "", account_type: "expense", subtype: "" });
  const [msg, setMsg] = useState("");
  const [ok, setOk] = useState(false);
  const TYPES = ["asset", "liability", "equity", "income", "expense"];
  const SUBTYPES = { asset: ["cash", "accounts_receivable", "inventory", "fixed_asset", "other"], liability: ["accounts_payable", "credit_card", "loan", "other"], equity: ["owner_equity", "retained_earnings", "other"], income: ["sales", "services", "other"], expense: ["cost_of_goods_sold", "payroll", "rent", "utilities", "supplies", "other"] };

  async function load() {
    const [a, tb] = await Promise.all([api("/platform/accounts"), api("/platform/reports/trial-balance")]);
    setAccounts(a);
    const map = {};
    (tb.rows || []).forEach((r) => { map[r.account.id] = r.debit_cents - r.credit_cents; });
    setBalances(map);
  }
  useEffect(() => { load().catch((e) => setMsg(e.message)); }, []);

  async function save() {
    try {
      setMsg(""); setOk(false);
      await api("/platform/finance/accounts", { method: "POST", body: JSON.stringify(form) });
      setOk(true); setMsg("Account added."); setForm({ code: "", name: "", account_type: "expense", subtype: "" }); await load();
    } catch (e) { setMsg(e.message); }
  }

  const grouped = useMemo(() => { const map = {}; TYPES.forEach((t) => { map[t] = []; }); accounts.forEach((a) => { if (map[a.account_type]) map[a.account_type].push(a); }); return map; }, [accounts]);

  return (
    <div>
      <Notice text={msg} ok={ok} />
      <section className="card fin-section" style={{ marginBottom: 20 }}>
        <h2 className="fin-section-title">Add a custom account</h2>
        <p className="fin-hint">Add accounts beyond the defaults to match your chart of accounts.</p>
        <div className="os-form-grid">
          <Field label="Account code"><input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} placeholder="e.g. 6500" /></Field>
          <Field label="Account name"><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Marketing" /></Field>
          <Field label="Type"><select value={form.account_type} onChange={(e) => setForm({ ...form, account_type: e.target.value, subtype: "" })}>{TYPES.map((t) => <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>)}</select></Field>
          <Field label="Sub-type"><select value={form.subtype} onChange={(e) => setForm({ ...form, subtype: e.target.value })}><option value="">— optional —</option>{(SUBTYPES[form.account_type] || []).map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}</select></Field>
        </div>
        <button className="primary-btn" onClick={save} disabled={!form.code || !form.name}>Add account</button>
      </section>
      {TYPES.map((type) => {
        const rows = grouped[type] || [];
        if (!rows.length) return null;
        const total = rows.reduce((s, a) => s + Math.abs(balances[a.id] || 0), 0);
        return (
          <section key={type} className="card fin-section" style={{ marginBottom: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
              <h2 className="fin-section-title" style={{ margin: 0, textTransform: "capitalize" }}>{type} accounts</h2>
              <span style={{ fontWeight: 750 }}>{money(total)}</span>
            </div>
            <Table headers={["Code", "Account name", "Sub-type", "Balance", "Status"]} rows={rows.map((a) => [
              <code style={{ background: "#f0f4fa", padding: "2px 7px", borderRadius: 5, fontSize: ".8rem" }}>{a.code}</code>,
              <strong>{a.name}</strong>,
              <span style={{ color: "#8a98aa", fontSize: ".83rem" }}>{a.subtype || "—"}</span>,
              <span style={{ fontWeight: 650, color: (balances[a.id] || 0) < 0 ? "#c73535" : "#14835f" }}>{money(Math.abs(balances[a.id] || 0))}</span>,
              <span style={{ fontSize: ".72rem", fontWeight: 750, padding: "3px 8px", borderRadius: 7, background: a.active ? "#edf9f3" : "#fef2f2", color: a.active ? "#14835f" : "#c73535" }}>{a.active ? "Active" : "Inactive"}</span>,
            ])} />
          </section>
        );
      })}
    </div>
  );
}

function PayrollTab() {
  const [runs, setRuns] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [form, setForm] = useState({ period_start: monthStart(), period_end: today(), gross_wages: "", employer_taxes: "", deductions: "", payment_account_id: "", notes: "" });
  const [msg, setMsg] = useState("");
  const [ok, setOk] = useState(false);
  const cashAccounts = useMemo(() => accounts.filter((a) => ["cash", "credit_card"].includes(a.subtype)), [accounts]);

  async function load() {
    const [r, a] = await Promise.all([api("/platform/finance/payroll"), api("/platform/accounts")]);
    setRuns(r); setAccounts(a);
  }
  useEffect(() => { load().catch((e) => setMsg(e.message)); }, []);

  async function save() {
    try {
      setMsg(""); setOk(false);
      await api("/platform/finance/payroll", { method: "POST", body: JSON.stringify({ ...form, gross_wages: Number(form.gross_wages), employer_taxes: Number(form.employer_taxes || 0), deductions: Number(form.deductions || 0), payment_account_id: Number(form.payment_account_id) }) });
      setOk(true); setMsg("Payroll run recorded.");
      setForm({ period_start: monthStart(), period_end: today(), gross_wages: "", employer_taxes: "", deductions: "", payment_account_id: "", notes: "" });
      await load();
    } catch (e) { setMsg(e.message); }
  }

  const totalGross = runs.reduce((s, r) => s + r.gross_wages_cents, 0);
  const totalNet = runs.reduce((s, r) => s + r.net_pay_cents, 0);
  const totalTax = runs.reduce((s, r) => s + r.employer_taxes_cents, 0);

  return (
    <div>
      <Notice text={msg} ok={ok} />
      <div className="fin-stat-row" style={{ gridTemplateColumns: "repeat(3,1fr)", marginBottom: 20 }}>
        <StatCard label="Total gross wages" value={money(totalGross)} color="#2f6fed" />
        <StatCard label="Employer taxes" value={money(totalTax)} color="#e07a00" />
        <StatCard label="Total net pay" value={money(totalNet)} color="#14835f" />
      </div>
      <section className="card fin-section" style={{ marginBottom: 20 }}>
        <h2 className="fin-section-title">Record a payroll run</h2>
        <p className="fin-hint">Each run posts a journal entry to your Payroll Expense account automatically.</p>
        <div className="os-form-grid">
          <Field label="Period start"><input type="date" value={form.period_start} onChange={(e) => setForm({ ...form, period_start: e.target.value })} /></Field>
          <Field label="Period end"><input type="date" value={form.period_end} onChange={(e) => setForm({ ...form, period_end: e.target.value })} /></Field>
          <Field label="Paid from account">
            <select value={form.payment_account_id} onChange={(e) => setForm({ ...form, payment_account_id: e.target.value })}>
              <option value="">Choose account…</option>
              {cashAccounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
          </Field>
          <Field label="Gross wages ($)"><input type="number" step="0.01" min="0" value={form.gross_wages} onChange={(e) => setForm({ ...form, gross_wages: e.target.value })} placeholder="0.00" /></Field>
          <Field label="Employer taxes ($)"><input type="number" step="0.01" min="0" value={form.employer_taxes} onChange={(e) => setForm({ ...form, employer_taxes: e.target.value })} placeholder="0.00" /></Field>
          <Field label="Employee deductions ($)"><input type="number" step="0.01" min="0" value={form.deductions} onChange={(e) => setForm({ ...form, deductions: e.target.value })} placeholder="0.00" /></Field>
        </div>
        <Field label="Notes"><input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Optional notes or reference" style={{ maxWidth: 500 }} /></Field>
        <br />
        <button className="primary-btn" onClick={save} disabled={!form.gross_wages || !form.payment_account_id}>Post payroll run</button>
      </section>
      <section className="card fin-section">
        <h2 className="fin-section-title">Payroll history</h2>
        <Table headers={["Period", "Gross wages", "Employer taxes", "Deductions", "Net pay", "Paid from", "Notes"]} rows={runs.map((r) => [`${r.period_start} → ${r.period_end}`, money(r.gross_wages_cents), money(r.employer_taxes_cents), money(r.deductions_cents), <strong>{money(r.net_pay_cents)}</strong>, r.payment_account_name, r.notes || "—"])} footer={runs.length ? ["Total", money(totalGross), money(totalTax), "", money(totalNet), "", ""] : null} />
      </section>
    </div>
  );
}

export default function FinancePage() {
  const [tab, setTab] = useState("dashboard");
  return (
    <div className="page os-page fin-page">
      <div className="os-heading">
        <div>
          <span className="eyebrow">FINANCIAL CONTROL CENTER</span>
          <h1>Finance &amp; accounting</h1>
          <p>Budget vs. actual, cash flow, payroll, and your full chart of accounts.</p>
        </div>
      </div>
      <nav className="fin-subnav">
        {TABS.map((t) => (
          <button key={t.id} className={`fin-subnav-btn${tab === t.id ? " active" : ""}`} onClick={() => setTab(t.id)}>
            <span className="fin-subnav-icon">{t.icon}</span>{t.label}
          </button>
        ))}
      </nav>
      {tab === "dashboard" && <DashboardTab />}
      {tab === "budget"    && <BudgetTab />}
      {tab === "cashflow"  && <CashFlowTab />}
      {tab === "accounts"  && <AccountsTab />}
      {tab === "payroll"   && <PayrollTab />}
    </div>
  );
}
