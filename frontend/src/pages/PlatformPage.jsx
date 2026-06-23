import { useEffect, useMemo, useState } from "react";
import { api } from "../api";

const money = (cents = 0) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(cents / 100);
const today = () => new Date().toISOString().slice(0, 10);

function Field({ label, children }) {
  return <label className="os-field"><span>{label}</span>{children}</label>;
}

export default function PlatformPage({ section = "overview" }) {
  const [data, setData] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [contacts, setContacts] = useState([]);
  const [message, setMessage] = useState("");
  const [form, setForm] = useState({});

  async function load() {
    setMessage("");
    if (section === "overview") setData(await api("/platform/dashboard"));
    if (["contacts", "sales", "purchasing"].includes(section)) setContacts(await api("/platform/contacts"));
    if (["accounting", "sales", "purchasing"].includes(section)) setAccounts(await api("/platform/accounts"));
    if (section === "sales") setData(await api("/platform/invoices"));
    if (section === "purchasing") setData(await api("/platform/bills"));
    if (section === "accounting") setData({ expenses: await api("/platform/expenses"), report: await api("/platform/reports/profit-loss") });
    if (section === "tasks") {
      const [tasks, templates, runs, closingReports] = await Promise.all([
        api("/platform/tasks"), api("/platform/checklists/templates"),
        api("/platform/checklists/runs"), api("/platform/closing-reports"),
      ]);
      setData({ tasks, templates, runs, closingReports });
    }
    if (section === "inventory") setData(await api("/platform/inventory"));
    if (section === "reports") setData({ profit: await api("/platform/reports/profit-loss"), balance: await api("/platform/reports/balance-sheet"), trial: await api("/platform/reports/trial-balance") });
  }

  useEffect(() => { load().catch((error) => setMessage(error.message)); }, [section]);
  const expenseAccounts = useMemo(() => accounts.filter((x) => x.account_type === "expense"), [accounts]);
  const paymentAccounts = useMemo(() => accounts.filter((x) => ["cash", "credit_card"].includes(x.subtype)), [accounts]);

  async function submit(path, body) {
    try {
      await api(path, { method: "POST", body: JSON.stringify(body) });
      setForm({}); setMessage("Saved successfully."); await load();
    } catch (error) { setMessage(error.message); }
  }

  async function startChecklist(templateId) {
    await submit("/platform/checklists/runs", { template_id: templateId, run_date: today() });
  }

  async function updateChecklist(run, items, complete = false) {
    try {
      await api(`/platform/checklists/runs/${run.id}`, { method: "PATCH", body: JSON.stringify({ items, notes: run.notes || "", complete }) });
      setMessage(complete ? "Checklist completed." : "Checklist saved."); await load();
    } catch (error) { setMessage(error.message); }
  }

  if (!data && !["contacts"].includes(section)) return <div className="page"><div className="os-loading">Loading workspace…</div>{message && <p className="os-alert">{message}</p>}</div>;

  if (section === "overview") return <div className="page os-page">
    <div className="os-heading"><div><span className="eyebrow">BUSINESS COMMAND CENTER</span><h1>Today at a glance</h1><p>Money, work, and operations in one place.</p></div><button className="primary-btn" onClick={load}>Refresh</button></div>
    <div className="os-metrics">
      <article><span>Money coming in</span><strong>{money(data.receivables_cents)}</strong><small>{data.open_invoices} open invoices</small></article>
      <article><span>Bills to pay</span><strong>{money(data.payables_cents)}</strong><small>{data.open_bills} open bills</small></article>
      <article><span>Open work</span><strong>{data.open_tasks}</strong><small>tasks still active</small></article>
      <article><span>Stock alerts</span><strong>{data.low_stock_items}</strong><small>items at reorder level</small></article>
    </div>
    <section className="card os-welcome"><div><span className="eyebrow">THE OPERATING LOOP</span><h2>Sell. Deliver. Record. Understand.</h2><p>Create customers and invoices, capture bills and expenses, manage the work and inventory behind them, then use the reports to see what the business actually earned.</p></div><div className="os-loop"><b>1</b><span>Sales</span><b>2</b><span>Operations</span><b>3</b><span>Books</span><b>4</b><span>Reports</span></div></section>
  </div>;

  if (section === "contacts") return <div className="page os-page"><Header title="Customers & vendors" copy="The people and companies your business buys from and sells to." />
    <section className="card os-form"><h2>Add a contact</h2><div className="os-form-grid"><Field label="Name"><input value={form.name || ""} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field><Field label="Type"><select value={form.contact_type || "customer"} onChange={(e) => setForm({ ...form, contact_type: e.target.value })}><option value="customer">Customer</option><option value="vendor">Vendor</option><option value="both">Both</option></select></Field><Field label="Email"><input value={form.email || ""} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field><Field label="Phone"><input value={form.phone || ""} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></Field></div><button className="primary-btn" onClick={() => submit("/platform/contacts", form)}>Save contact</button></section>
    <Notice text={message} /><Table headers={["Name", "Type", "Email", "Phone"]} rows={contacts.map((x) => [x.name, x.contact_type, x.email || "—", x.phone || "—"])} />
  </div>;

  if (section === "sales") {
    const customers = contacts.filter((x) => ["customer", "both"].includes(x.contact_type));
    return <div className="page os-page"><Header title="Sales & invoices" copy="Bill customers and track what is still owed." />
      <section className="card os-form"><h2>New invoice</h2><div className="os-form-grid"><Field label="Customer"><select value={form.customer_id || ""} onChange={(e) => setForm({ ...form, customer_id: Number(e.target.value) })}><option value="">Choose customer</option>{customers.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></Field><Field label="Due date"><input type="date" value={form.due_date || today()} onChange={(e) => setForm({ ...form, due_date: e.target.value })} /></Field><Field label="Description"><input value={form.description || ""} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field><Field label="Amount"><input type="number" step="0.01" value={form.amount || ""} onChange={(e) => setForm({ ...form, amount: Number(e.target.value) })} /></Field></div><button className="primary-btn" onClick={() => submit("/platform/invoices", { customer_id: form.customer_id, due_date: form.due_date || today(), lines: [{ description: form.description || "Services", quantity: 1, unit_price: form.amount || 0 }] })}>Create draft</button></section>
      <Notice text={message} /><Table headers={["Invoice", "Date", "Due", "Status", "Total", "Balance"]} rows={(data || []).map((x) => [x.number, x.issue_date, x.due_date, x.status, money(x.total_cents), money(x.total_cents - x.paid_cents)])} />
    </div>;
  }

  if (section === "purchasing") {
    const vendors = contacts.filter((x) => ["vendor", "both"].includes(x.contact_type));
    return <div className="page os-page"><Header title="Bills & purchasing" copy="Record what vendors charge and what remains payable." />
      <section className="card os-form"><h2>Enter a bill</h2><div className="os-form-grid"><Field label="Vendor"><select value={form.vendor_id || ""} onChange={(e) => setForm({ ...form, vendor_id: Number(e.target.value) })}><option value="">Choose vendor</option>{vendors.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></Field><Field label="Due date"><input type="date" value={form.due_date || today()} onChange={(e) => setForm({ ...form, due_date: e.target.value })} /></Field><Field label="Expense category"><select value={form.account_id || ""} onChange={(e) => setForm({ ...form, account_id: Number(e.target.value) })}><option value="">Choose account</option>{expenseAccounts.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></Field><Field label="Amount"><input type="number" step="0.01" value={form.amount || ""} onChange={(e) => setForm({ ...form, amount: Number(e.target.value) })} /></Field></div><button className="primary-btn" onClick={() => submit("/platform/bills", { vendor_id: form.vendor_id, due_date: form.due_date || today(), lines: [{ description: form.description || "Vendor bill", quantity: 1, unit_price: form.amount || 0, account_id: form.account_id }] })}>Create draft</button></section>
      <Notice text={message} /><Table headers={["Bill", "Date", "Due", "Status", "Total", "Balance"]} rows={(data || []).map((x) => [x.number || `Bill ${x.id}`, x.bill_date, x.due_date, x.status, money(x.total_cents), money(x.total_cents - x.paid_cents)])} />
    </div>;
  }

  if (section === "accounting") return <div className="page os-page"><Header title="Bookkeeping" copy="Capture day-to-day spending; every save posts a balanced journal entry." />
    <div className="os-metrics compact"><article><span>Income</span><strong>{money(data.report.total_income_cents)}</strong></article><article><span>Expenses</span><strong>{money(data.report.total_expenses_cents)}</strong></article><article><span>Net income</span><strong>{money(data.report.net_income_cents)}</strong></article></div>
    <section className="card os-form"><h2>Record an expense</h2><div className="os-form-grid"><Field label="Date"><input type="date" value={form.expense_date || today()} onChange={(e) => setForm({ ...form, expense_date: e.target.value })} /></Field><Field label="Category"><select value={form.account_id || ""} onChange={(e) => setForm({ ...form, account_id: Number(e.target.value) })}><option value="">Choose category</option>{expenseAccounts.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></Field><Field label="Paid from"><select value={form.payment_account_id || ""} onChange={(e) => setForm({ ...form, payment_account_id: Number(e.target.value) })}><option value="">Choose account</option>{paymentAccounts.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></Field><Field label="Amount"><input type="number" step="0.01" value={form.amount || ""} onChange={(e) => setForm({ ...form, amount: Number(e.target.value) })} /></Field><Field label="Description"><input value={form.description || ""} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field></div><button className="primary-btn" onClick={() => submit("/platform/expenses", { ...form, expense_date: form.expense_date || today() })}>Record expense</button></section><Notice text={message} />
    <Table headers={["Date", "Description", "Amount"]} rows={data.expenses.map((x) => [x.expense_date, x.description || "Expense", money(x.amount_cents)])} />
  </div>;

  if (section === "tasks") return <div className="page os-page">
    <Header title="Tasks, checklists & closing" copy="Keep daily work, repeatable procedures, and end-of-day reports together." />
    <Notice text={message} />

    <details className="card ops-disclosure" defaultOpen>
      <summary><div><span className="eyebrow">DAILY RECORD</span><h2>Closing report</h2><p>Record the numbers and important notes from the end of the day.</p></div><b>⌄</b></summary>
      <div className="disclosure-body">
        <div className="os-form-grid">
          <Field label="Date"><input type="date" value={form.close_date || today()} onChange={(e) => setForm({ ...form, close_date: e.target.value })} /></Field>
          <Field label="Sales"><input type="number" step="0.01" placeholder="0.00" value={form.close_sales ?? ""} onChange={(e) => setForm({ ...form, close_sales: e.target.value })} /></Field>
          <Field label="Cash expected"><input type="number" step="0.01" placeholder="0.00" value={form.close_expected ?? ""} onChange={(e) => setForm({ ...form, close_expected: e.target.value })} /></Field>
          <Field label="Cash actually counted"><input type="number" step="0.01" placeholder="0.00" value={form.close_actual ?? ""} onChange={(e) => setForm({ ...form, close_actual: e.target.value })} /></Field>
          <Field label="Labor cost"><input type="number" step="0.01" placeholder="0.00" value={form.close_labor ?? ""} onChange={(e) => setForm({ ...form, close_labor: e.target.value })} /></Field>
          <Field label="Waste / loss"><input type="number" step="0.01" placeholder="0.00" value={form.close_waste ?? ""} onChange={(e) => setForm({ ...form, close_waste: e.target.value })} /></Field>
        </div>
        <div className="closing-notes-grid"><Field label="Problems or incidents"><textarea value={form.close_issues || ""} onChange={(e) => setForm({ ...form, close_issues: e.target.value })} /></Field><Field label="Manager notes"><textarea value={form.close_notes || ""} onChange={(e) => setForm({ ...form, close_notes: e.target.value })} /></Field></div>
        <button className="primary-btn" onClick={() => submit("/platform/closing-reports", { report_date: form.close_date || today(), sales: Number(form.close_sales || 0), cash_expected: Number(form.close_expected || 0), cash_actual: Number(form.close_actual || 0), labor_cost: Number(form.close_labor || 0), waste: Number(form.close_waste || 0), issues: form.close_issues || "", notes: form.close_notes || "" })}>Submit closing report</button>
        <Table headers={["Date", "Sales", "Cash difference", "Labor", "Issues"]} rows={data.closingReports.map((x) => [x.report_date, money(x.sales_cents), money(x.cash_actual_cents - x.cash_expected_cents), money(x.labor_cost_cents), x.issues || "—"])} />
      </div>
    </details>

    <details className="card ops-disclosure" defaultOpen>
      <summary><div><span className="eyebrow">REPEATABLE WORK</span><h2>Checklists</h2><p>Start the same opening, closing, safety, or cleaning steps whenever needed.</p></div><b>⌄</b></summary>
      <div className="disclosure-body">
        <div className="checklist-template-grid">{data.templates.map((template) => <article key={template.id}><div><strong>{template.name}</strong><span>{template.description || "Reusable checklist"}</span></div><button className="small-btn" onClick={() => startChecklist(template.id)}>Start</button></article>)}</div>
        {data.runs.filter((run) => run.status === "open").map((run) => <article className="active-checklist" key={run.id}><div className="section-title"><div><span className="eyebrow">IN PROGRESS</span><h3>{run.template_name}</h3></div><span>{run.run_date}</span></div>{run.items.map((item, index) => <label key={`${run.id}-${index}`}><input type="checkbox" checked={item.done} onChange={(e) => updateChecklist(run, run.items.map((row, i) => i === index ? { ...row, done: e.target.checked } : row))} />{item.label}</label>)}<button className="primary-btn" disabled={!run.items.every((item) => item.done)} onClick={() => updateChecklist(run, run.items, true)}>Complete checklist</button></article>)}
        <div className="checklist-builder"><h3>Create a reusable checklist</h3><div className="os-form-grid"><Field label="Checklist name"><input placeholder="Weekly safety check" value={form.checklist_name || ""} onChange={(e) => setForm({ ...form, checklist_name: e.target.value })} /></Field><Field label="One step per line"><textarea placeholder={"Inspect exits\nCheck equipment\nRecord issues"} value={form.checklist_items || ""} onChange={(e) => setForm({ ...form, checklist_items: e.target.value })} /></Field></div><button className="small-btn" onClick={() => submit("/platform/checklists/templates", { name: form.checklist_name || "", items: (form.checklist_items || "").split("\n") })}>Save checklist</button></div>
      </div>
    </details>

    <details className="card ops-disclosure">
      <summary><div><span className="eyebrow">ONE-TIME WORK</span><h2>Tasks</h2><p>Assignments that need to be completed once.</p></div><b>⌄</b></summary>
      <div className="disclosure-body"><div className="os-form-grid"><Field label="Task"><input value={form.title || ""} onChange={(e) => setForm({ ...form, title: e.target.value })} /></Field><Field label="Due"><input type="date" value={form.due_date || ""} onChange={(e) => setForm({ ...form, due_date: e.target.value })} /></Field><Field label="Priority"><select value={form.priority || "normal"} onChange={(e) => setForm({ ...form, priority: e.target.value })}><option>low</option><option>normal</option><option>high</option><option>urgent</option></select></Field></div><button className="primary-btn" onClick={() => submit("/platform/tasks", form)}>Add task</button><Table headers={["Task", "Due", "Priority", "Status"]} rows={data.tasks.map((x) => [x.title, x.due_date || "—", x.priority, x.status])} /></div>
    </details>
  </div>;

  if (section === "inventory") return <div className="page os-page"><Header title="Inventory & assets" copy="Track products, supplies, equipment, and reorder points." /><section className="card os-form"><div className="os-form-grid"><Field label="Item code (SKU)"><input placeholder="ITEM-001" value={form.sku || ""} onChange={(e) => setForm({ ...form, sku: e.target.value })} /></Field><Field label="Item name"><input value={form.name || ""} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field><Field label="Type"><select value={form.item_type || "inventory"} onChange={(e) => setForm({ ...form, item_type: e.target.value })}><option value="inventory">Inventory</option><option value="supply">Supply</option><option value="asset">Asset</option><option value="service">Service</option></select></Field><Field label="Starting quantity"><input type="number" placeholder="0" value={form.quantity ?? ""} onChange={(e) => setForm({ ...form, quantity: e.target.value })} /></Field><Field label="Reorder at"><input type="number" placeholder="0" value={form.reorder_level ?? ""} onChange={(e) => setForm({ ...form, reorder_level: e.target.value })} /></Field></div><button className="primary-btn" onClick={() => submit("/platform/inventory", { ...form, quantity: Number(form.quantity || 0), reorder_level: Number(form.reorder_level || 0) })}>Add item</button></section><Notice text={message} /><Table headers={["Item code", "Item", "Type", "On hand", "Reorder at"]} rows={(data || []).map((x) => [x.sku, x.name, x.item_type, x.quantity_milli / 1000, x.reorder_level_milli / 1000])} /></div>;

  if (section === "reports") return <div className="page os-page"><Header title="Financial reports" copy="A live view generated from the double-entry ledger." /><div className="os-metrics compact"><article><span>Revenue</span><strong>{money(data.profit.total_income_cents)}</strong></article><article><span>Expenses</span><strong>{money(data.profit.total_expenses_cents)}</strong></article><article><span>Net income</span><strong>{money(data.profit.net_income_cents)}</strong></article><article><span>Total assets</span><strong>{money(data.balance.totals.asset)}</strong></article></div><section className="card"><h2>Trial balance</h2><Table headers={["Code", "Account", "Debit", "Credit"]} rows={data.trial.rows.map((x) => [x.account.code, x.account.name, money(x.debit_cents), money(x.credit_cents)])} /></section></div>;

  return null;
}

function Header({ title, copy }) { return <div className="os-heading"><div><span className="eyebrow">BUSINESS OS</span><h1>{title}</h1><p>{copy}</p></div></div>; }
function Notice({ text }) { return text ? <p className="os-alert">{text}</p> : null; }
function Table({ headers, rows }) { return <section className="card os-table-wrap"><table className="os-table"><thead><tr>{headers.map((x) => <th key={x}>{x}</th>)}</tr></thead><tbody>{rows.length ? rows.map((row, i) => <tr key={i}>{row.map((cell, j) => <td key={j}>{cell}</td>)}</tr>) : <tr><td colSpan={headers.length} className="os-empty">Nothing here yet.</td></tr>}</tbody></table></section>; }
