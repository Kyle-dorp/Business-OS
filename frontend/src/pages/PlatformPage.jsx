import { useEffect, useMemo, useState } from "react";
import { api } from "../api";

const money = (cents = 0) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(cents / 100);
const pct = (n) => `${n.toFixed(1)}%`;
const today = () => new Date().toISOString().slice(0, 10);
const monthStart = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-01`; };
const lastMonthStart = () => { const d = new Date(new Date().getFullYear(), new Date().getMonth()-1, 1); return d.toISOString().slice(0,10); };
const lastMonthEnd = () => { const d = new Date(new Date().getFullYear(), new Date().getMonth(), 0); return d.toISOString().slice(0,10); };
const yearStart = () => `${new Date().getFullYear()}-01-01`;

function Field({ label, children }) {
  return <label className="os-field"><span>{label}</span>{children}</label>;
}

export default function PlatformPage({ section = "overview" }) {
  const [data, setData] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [contacts, setContacts] = useState([]);
  const [message, setMessage] = useState("");
  const [form, setForm] = useState({});
  const [postingReport, setPostingReport] = useState(null);
  const [actionInvoice, setActionInvoice] = useState(null);
  const [actionBill, setActionBill] = useState(null);
  const [managerSettings, setManagerSettings] = useState(null);
  const [reportStart, setReportStart] = useState(monthStart());
  const [reportEnd, setReportEnd] = useState(today());

  async function load() {
    setMessage("");
    if (section === "overview") setData(await api("/platform/dashboard"));
    if (["contacts", "sales", "purchasing"].includes(section)) setContacts(await api("/platform/contacts"));
    if (["accounting", "sales", "purchasing"].includes(section)) setAccounts(await api("/platform/accounts"));
    if (section === "sales") setData(await api("/platform/invoices"));
    if (section === "purchasing") setData(await api("/platform/bills"));
    if (section === "accounting") setData({ expenses: await api("/platform/expenses"), report: await api("/platform/reports/profit-loss") });
    if (section === "tasks") {
      const [tasks, templates, runs, closingReports, accts, mgr] = await Promise.all([
        api("/platform/tasks"), api("/platform/checklists/templates"),
        api("/platform/checklists/runs"), api("/platform/closing-reports"),
        api("/platform/accounts"), api("/manager-settings"),
      ]);
      setData({ tasks, templates, runs, closingReports });
      setAccounts(accts);
      setManagerSettings(mgr);
    }
    if (section === "inventory") setData(await api("/platform/inventory"));
    if (section === "reports") {
      const qs = reportStart && reportEnd ? `?start=${reportStart}&end=${reportEnd}` : "";
      const [profit, balance, trial, arAging, apAging, foodCost] = await Promise.all([
        api(`/platform/reports/profit-loss${qs}`),
        api("/platform/reports/balance-sheet"),
        api("/platform/reports/trial-balance"),
        api("/platform/reports/ar-aging"),
        api("/platform/reports/ap-aging"),
        api(`/platform/reports/food-cost${qs}`),
      ]);
      setData({ profit, balance, trial, arAging, apAging, foodCost });
    }
  }

  useEffect(() => { load().catch((error) => setMessage(error.message)); }, [section, reportStart, reportEnd]);

  const expenseAccounts = useMemo(() => accounts.filter((x) => x.account_type === "expense"), [accounts]);
  const paymentAccounts = useMemo(() => accounts.filter((x) => ["cash", "credit_card"].includes(x.subtype)), [accounts]);
  const depositAccounts = useMemo(() => accounts.filter((x) => x.account_type === "asset" && ["cash", "cash_drawer"].includes(x.subtype)), [accounts]);

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

  async function postInvoice(id) {
    try { await api(`/platform/invoices/${id}/post`, { method: "POST" }); setActionInvoice(null); setMessage("Invoice posted to ledger."); await load(); }
    catch (error) { setMessage(error.message); }
  }
  async function payInvoice(id) {
    try {
      await api(`/platform/invoices/${id}/payments`, { method: "POST", body: JSON.stringify({ amount: Number(form.inv_amount || 0), account_id: Number(form.inv_account_id), payment_date: form.inv_date || today(), reference: "" }) });
      setActionInvoice(null); setForm({}); setMessage("Payment recorded."); await load();
    } catch (error) { setMessage(error.message); }
  }
  async function postBill(id) {
    try { await api(`/platform/bills/${id}/post`, { method: "POST" }); setActionBill(null); setMessage("Bill posted to AP."); await load(); }
    catch (error) { setMessage(error.message); }
  }
  async function payBill(id) {
    try {
      await api(`/platform/bills/${id}/payments`, { method: "POST", body: JSON.stringify({ amount: Number(form.bill_amount || 0), account_id: Number(form.bill_account_id), payment_date: form.bill_date || today(), reference: "" }) });
      setActionBill(null); setForm({}); setMessage("Bill payment recorded."); await load();
    } catch (error) { setMessage(error.message); }
  }
  async function remitSalesTax() {
    try {
      await api("/platform/accounting/sales-tax/remit", { method: "POST", body: JSON.stringify({ amount: Number(form.tax_amount || 0), period: form.tax_period || "", bank_account_id: Number(form.tax_account_id) }) });
      setForm({}); setMessage("Sales tax payment recorded and posted to ledger."); await load();
    } catch (error) { setMessage(error.message); }
  }

  async function postToBooks(reportId, bankAccountId) {
    try {
      await api(`/platform/closing-reports/${reportId}/post`, { method: "POST", body: JSON.stringify({ bank_account_id: bankAccountId }) });
      setPostingReport(null); setMessage("Daily sales posted to the ledger."); await load();
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
      <Notice text={message} />
      <section className="card os-table-wrap"><table className="os-table">
        <thead><tr><th>Invoice</th><th>Date</th><th>Due</th><th>Status</th><th>Total</th><th>Balance</th><th>Action</th></tr></thead>
        <tbody>
          {!(data || []).length && <tr><td colSpan={7} className="os-empty">No invoices yet.</td></tr>}
          {(data || []).map((x) => <tr key={x.id}>
            <td>{x.number}</td><td>{x.issue_date}</td><td>{x.due_date}</td><td>{x.status}</td>
            <td>{money(x.total_cents)}</td><td>{money(x.total_cents - x.paid_cents)}</td>
            <td>
              {x.status === "draft" && <button className="small-btn" onClick={() => postInvoice(x.id)}>Post</button>}
              {["sent","open","partial"].includes(x.status) && actionInvoice === x.id
                ? <span style={{ display:"flex", gap:"4px", alignItems:"center", flexWrap:"wrap" }}>
                    <input type="number" step="0.01" placeholder="Amount" style={{ width:"80px", fontSize:"0.8rem" }} value={form.inv_amount||""} onChange={(e)=>setForm({...form,inv_amount:e.target.value})} />
                    <select style={{ fontSize:"0.8rem" }} value={form.inv_account_id||""} onChange={(e)=>setForm({...form,inv_account_id:Number(e.target.value)})}><option value="">Deposit to…</option>{depositAccounts.map((a)=><option key={a.id} value={a.id}>{a.name}</option>)}</select>
                    <input type="date" style={{ fontSize:"0.8rem" }} value={form.inv_date||today()} onChange={(e)=>setForm({...form,inv_date:e.target.value})} />
                    <button className="small-btn" onClick={()=>payInvoice(x.id)} disabled={!form.inv_amount||!form.inv_account_id}>Save</button>
                    <button className="small-btn" onClick={()=>setActionInvoice(null)}>✕</button>
                  </span>
                : ["sent","open","partial"].includes(x.status) && <button className="small-btn" onClick={()=>setActionInvoice(x.id)}>Record payment</button>}
              {x.status === "paid" && <span style={{ color:"var(--green,#2a9d4e)" }}>✓ Paid</span>}
            </td>
          </tr>)}
        </tbody>
      </table></section>
    </div>;
  }

  if (section === "purchasing") {
    const vendors = contacts.filter((x) => ["vendor", "both"].includes(x.contact_type));
    return <div className="page os-page"><Header title="Bills & purchasing" copy="Record what vendors charge and what remains payable." />
      <section className="card os-form"><h2>Enter a bill</h2><div className="os-form-grid"><Field label="Vendor"><select value={form.vendor_id || ""} onChange={(e) => setForm({ ...form, vendor_id: Number(e.target.value) })}><option value="">Choose vendor</option>{vendors.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></Field><Field label="Due date"><input type="date" value={form.due_date || today()} onChange={(e) => setForm({ ...form, due_date: e.target.value })} /></Field><Field label="Expense category"><select value={form.account_id || ""} onChange={(e) => setForm({ ...form, account_id: Number(e.target.value) })}><option value="">Choose account</option>{expenseAccounts.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></Field><Field label="Amount"><input type="number" step="0.01" value={form.amount || ""} onChange={(e) => setForm({ ...form, amount: Number(e.target.value) })} /></Field></div><button className="primary-btn" onClick={() => submit("/platform/bills", { vendor_id: form.vendor_id, due_date: form.due_date || today(), lines: [{ description: form.description || "Vendor bill", quantity: 1, unit_price: form.amount || 0, account_id: form.account_id }] })}>Create draft</button></section>
      <Notice text={message} />
      <section className="card os-table-wrap"><table className="os-table">
        <thead><tr><th>Bill</th><th>Date</th><th>Due</th><th>Status</th><th>Total</th><th>Balance</th><th>Action</th></tr></thead>
        <tbody>
          {!(data || []).length && <tr><td colSpan={7} className="os-empty">No bills yet.</td></tr>}
          {(data || []).map((x) => <tr key={x.id}>
            <td>{x.number || `Bill ${x.id}`}</td><td>{x.bill_date}</td><td>{x.due_date}</td><td>{x.status}</td>
            <td>{money(x.total_cents)}</td><td>{money(x.total_cents - x.paid_cents)}</td>
            <td>
              {x.status === "draft" && <button className="small-btn" onClick={() => postBill(x.id)}>Post to AP</button>}
              {["open","partial"].includes(x.status) && actionBill === x.id
                ? <span style={{ display:"flex", gap:"4px", alignItems:"center", flexWrap:"wrap" }}>
                    <input type="number" step="0.01" placeholder="Amount" style={{ width:"80px", fontSize:"0.8rem" }} value={form.bill_amount||""} onChange={(e)=>setForm({...form,bill_amount:e.target.value})} />
                    <select style={{ fontSize:"0.8rem" }} value={form.bill_account_id||""} onChange={(e)=>setForm({...form,bill_account_id:Number(e.target.value)})}><option value="">Pay from…</option>{paymentAccounts.map((a)=><option key={a.id} value={a.id}>{a.name}</option>)}</select>
                    <input type="date" style={{ fontSize:"0.8rem" }} value={form.bill_date||today()} onChange={(e)=>setForm({...form,bill_date:e.target.value})} />
                    <button className="small-btn" onClick={()=>payBill(x.id)} disabled={!form.bill_amount||!form.bill_account_id}>Pay</button>
                    <button className="small-btn" onClick={()=>setActionBill(null)}>✕</button>
                  </span>
                : ["open","partial"].includes(x.status) && <button className="small-btn" onClick={()=>setActionBill(x.id)}>Pay</button>}
              {x.status === "paid" && <span style={{ color:"var(--green,#2a9d4e)" }}>✓ Paid</span>}
            </td>
          </tr>)}
        </tbody>
      </table></section>
    </div>;
  }

  if (section === "accounting") return <div className="page os-page"><Header title="Bookkeeping" copy="Capture day-to-day spending; every save posts a balanced journal entry." />
    <div className="os-metrics compact"><article><span>Income</span><strong>{money(data.report.total_income_cents)}</strong></article><article><span>Expenses</span><strong>{money(data.report.total_expenses_cents)}</strong></article><article><span>Net income</span><strong>{money(data.report.net_income_cents)}</strong></article></div>
    <section className="card os-form"><h2>Record an expense</h2><div className="os-form-grid"><Field label="Date"><input type="date" value={form.expense_date || today()} onChange={(e) => setForm({ ...form, expense_date: e.target.value })} /></Field><Field label="Category"><select value={form.account_id || ""} onChange={(e) => setForm({ ...form, account_id: Number(e.target.value) })}><option value="">Choose category</option>{expenseAccounts.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></Field><Field label="Paid from"><select value={form.payment_account_id || ""} onChange={(e) => setForm({ ...form, payment_account_id: Number(e.target.value) })}><option value="">Choose account</option>{paymentAccounts.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></Field><Field label="Amount"><input type="number" step="0.01" value={form.amount || ""} onChange={(e) => setForm({ ...form, amount: Number(e.target.value) })} /></Field><Field label="Description"><input value={form.description || ""} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field></div><button className="primary-btn" onClick={() => submit("/platform/expenses", { ...form, expense_date: form.expense_date || today() })}>Record expense</button></section>
    <section className="card os-form"><h2>Pay Colorado sales tax</h2>
      <p style={{ fontSize:"0.82rem", color:"var(--muted)", marginBottom:"8px" }}>CO state 2.9% + Rio Blanco County 3.6% = <strong>6.5%</strong>. Rangely relies on the county share — no additional city tax. Remittances due by the 20th after each quarter (Apr 20, Jul 20, Oct 20, Jan 20).</p>
      <div className="os-form-grid">
        <Field label="Quarter / period"><input placeholder="e.g. Q2 2025" value={form.tax_period||""} onChange={(e)=>setForm({...form,tax_period:e.target.value})} /></Field>
        <Field label="Amount due"><input type="number" step="0.01" value={form.tax_amount||""} onChange={(e)=>setForm({...form,tax_amount:e.target.value})} /></Field>
        <Field label="Pay from"><select value={form.tax_account_id||""} onChange={(e)=>setForm({...form,tax_account_id:Number(e.target.value)})}><option value="">Choose account</option>{depositAccounts.map((a)=><option key={a.id} value={a.id}>{a.name}</option>)}</select></Field>
      </div>
      <button className="primary-btn" onClick={remitSalesTax} disabled={!form.tax_amount||!form.tax_account_id||!form.tax_period}>Record payment to state</button>
    </section>
    <Notice text={message} />
    <Table headers={["Date", "Description", "Amount"]} rows={data.expenses.map((x) => [x.expense_date, x.description || "Expense", money(x.amount_cents)])} />
  </div>;

  if (section === "tasks") return <div className="page os-page">
    <Header title="Tasks, checklists & closing" copy="Keep daily work, repeatable procedures, and end-of-day reports together." />
    <Notice text={message} />

    <details className="card ops-disclosure" defaultOpen>
      <summary><div><span className="eyebrow">DAILY RECORD</span><h2>Closing report</h2><p>Record the day's numbers. Post to the ledger when ready.</p></div><b>⌄</b></summary>
      <div className="disclosure-body">
        <div className="os-form-grid">
          <Field label="Date"><input type="date" value={form.close_date || today()} onChange={(e) => setForm({ ...form, close_date: e.target.value })} /></Field>
          <Field label="Total sales"><input type="number" step="0.01" placeholder="0.00" value={form.close_sales ?? ""} onChange={(e) => setForm({ ...form, close_sales: e.target.value })} /></Field>
          <Field label="Card sales"><input type="number" step="0.01" placeholder="0.00" value={form.close_card ?? ""} onChange={(e) => setForm({ ...form, close_card: e.target.value })} /></Field>
          <Field label="Sales tax collected">
            <input type="number" step="0.01" placeholder="0.00" value={form.close_tax ?? ""} onChange={(e) => setForm({ ...form, close_tax: e.target.value })} />
            {form.close_sales > 0 && <small style={{ color:"var(--muted)", fontSize:"0.75rem" }}>6.5% of sales = {money(Math.round(Number(form.close_sales||0) * 6.5))}</small>}
          </Field>
          <Field label="Cash expected"><input type="number" step="0.01" placeholder="0.00" value={form.close_expected ?? ""} onChange={(e) => setForm({ ...form, close_expected: e.target.value })} /></Field>
          <Field label="Cash actually counted"><input type="number" step="0.01" placeholder="0.00" value={form.close_actual ?? ""} onChange={(e) => setForm({ ...form, close_actual: e.target.value })} /></Field>
          <Field label="Labor cost"><input type="number" step="0.01" placeholder="0.00" value={form.close_labor ?? ""} onChange={(e) => setForm({ ...form, close_labor: e.target.value })} /></Field>
          <Field label="Waste / loss"><input type="number" step="0.01" placeholder="0.00" value={form.close_waste ?? ""} onChange={(e) => setForm({ ...form, close_waste: e.target.value })} /></Field>
        </div>
        <div className="closing-notes-grid">
          <Field label="Problems or incidents"><textarea value={form.close_issues || ""} onChange={(e) => setForm({ ...form, close_issues: e.target.value })} /></Field>
          <Field label="Manager notes"><textarea value={form.close_notes || ""} onChange={(e) => setForm({ ...form, close_notes: e.target.value })} /></Field>
        </div>
        <button className="primary-btn" onClick={() => submit("/platform/closing-reports", {
          report_date: form.close_date || today(),
          sales: Number(form.close_sales || 0),
          card_sales: Number(form.close_card || 0),
          sales_tax: Number(form.close_tax || 0),
          cash_expected: Number(form.close_expected || 0),
          cash_actual: Number(form.close_actual || 0),
          labor_cost: Number(form.close_labor || 0),
          waste: Number(form.close_waste || 0),
          issues: form.close_issues || "",
          notes: form.close_notes || "",
        })}>Submit closing report</button>

        <section className="card os-table-wrap">
          <table className="os-table">
            <thead><tr><th>Date</th><th>Sales</th><th>Tax collected</th><th>Cash +/−</th><th>Labor</th><th>Issues</th><th>Books</th></tr></thead>
            <tbody>
              {data.closingReports.length === 0 && <tr><td colSpan={7} className="os-empty">Nothing here yet.</td></tr>}
              {data.closingReports.map((r) => (
                <tr key={r.id}>
                  <td>{r.report_date}</td>
                  <td>{money(r.sales_cents)}</td>
                  <td>{money(r.sales_tax_cents)}</td>
                  <td style={{ color: r.cash_actual_cents >= r.cash_expected_cents ? "var(--green, #2a9d4e)" : "var(--red, #c0392b)" }}>
                    {r.cash_actual_cents >= r.cash_expected_cents ? "+" : ""}{money(r.cash_actual_cents - r.cash_expected_cents)}
                  </td>
                  <td>{money(r.labor_cost_cents)}</td>
                  <td>{r.issues || "—"}</td>
                  <td>
                    {postingReport === r.id ? (
                      <span style={{ display: "flex", gap: "4px", alignItems: "center" }}>
                        <select style={{ fontSize: "0.8rem" }} value={form.post_bank_id || ""} onChange={(e) => setForm({ ...form, post_bank_id: Number(e.target.value) })}>
                          <option value="">Deposit to…</option>
                          {depositAccounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
                        </select>
                        <button className="small-btn" onClick={() => postToBooks(r.id, form.post_bank_id)} disabled={!form.post_bank_id}>Post</button>
                        <button className="small-btn" onClick={() => setPostingReport(null)}>✕</button>
                      </span>
                    ) : (
                      <button className="small-btn" onClick={() => setPostingReport(r.id)}>Post to books</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
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

  if (section === "reports") {
    const { profit, balance, trial, arAging, apAging, foodCost } = data;
    const agingLabels = { current: "Current", "1_30": "1–30 days", "31_60": "31–60 days", "61_90": "61–90 days", "over_90": "90+ days" };

    const periodLabel = reportStart && reportEnd ? `${reportStart} → ${reportEnd}` : "All time";
    return <div className="page os-page">
      <Header title="Financial reports" copy={`${periodLabel} — from the double-entry ledger.`} />
      <div style={{ display:"flex", gap:"8px", alignItems:"center", flexWrap:"wrap", marginBottom:"12px" }}>
        <button className="small-btn" onClick={()=>{setReportStart(monthStart());setReportEnd(today());}}>This month</button>
        <button className="small-btn" onClick={()=>{setReportStart(lastMonthStart());setReportEnd(lastMonthEnd());}}>Last month</button>
        <button className="small-btn" onClick={()=>{setReportStart(yearStart());setReportEnd(today());}}>This year</button>
        <button className="small-btn" onClick={()=>{setReportStart("");setReportEnd("");}}>All time</button>
        <input type="date" style={{ fontSize:"0.8rem" }} value={reportStart} onChange={(e)=>setReportStart(e.target.value)} />
        <span style={{ color:"var(--muted)" }}>→</span>
        <input type="date" style={{ fontSize:"0.8rem" }} value={reportEnd} onChange={(e)=>setReportEnd(e.target.value)} />
      </div>

      <div className="os-metrics compact">
        <article><span>Revenue</span><strong>{money(profit.total_income_cents)}</strong></article>
        <article><span>Expenses</span><strong>{money(profit.total_expenses_cents)}</strong></article>
        <article><span>Net income</span><strong>{money(profit.net_income_cents)}</strong></article>
        <article><span>Total assets</span><strong>{money(balance.totals.asset)}</strong></article>
      </div>

      <div className="os-metrics compact">
        <article><span>Food cost %</span><strong style={{ color: foodCost.food_cost_pct > 35 ? "var(--red, #c0392b)" : "inherit" }}>{pct(foodCost.food_cost_pct)}</strong><small>target under 35%</small></article>
        <article><span>Total food cost</span><strong>{money(foodCost.total_food_cost_cents)}</strong><small>of {money(foodCost.total_sales_cents)} sales</small></article>
        <article><span>AR outstanding</span><strong>{money(arAging.grand_total_cents)}</strong><small>accounts receivable</small></article>
        <article><span>AP outstanding</span><strong>{money(apAging.grand_total_cents)}</strong><small>bills to pay</small></article>
      </div>

      <section className="card">
        <h2>Food cost breakdown</h2>
        <Table
          headers={["Account", "Amount", "% of Sales"]}
          rows={foodCost.breakdown.filter((x) => x.amount_cents > 0).map((x) => [x.account_name, money(x.amount_cents), pct(x.pct_of_sales)])}
        />
      </section>

      <section className="card">
        <h2>AR aging — accounts receivable</h2>
        <table className="os-table">
          <thead><tr><th>Bucket</th><th>Count</th><th>Balance</th></tr></thead>
          <tbody>
            {Object.entries(agingLabels).map(([key, label]) => (
              <tr key={key} style={{ fontWeight: (key === "61_90" || key === "over_90") && arAging.totals[key] > 0 ? "bold" : undefined }}>
                <td>{label}</td>
                <td>{arAging.buckets[key].length}</td>
                <td>{money(arAging.totals[key])}</td>
              </tr>
            ))}
            <tr style={{ borderTop: "2px solid var(--border, #ddd)", fontWeight: "bold" }}>
              <td>Total</td><td></td><td>{money(arAging.grand_total_cents)}</td>
            </tr>
          </tbody>
        </table>
        {arAging.buckets.over_90.length > 0 && (
          <Table headers={["Invoice", "Customer", "Due", "Days past", "Balance"]}
            rows={arAging.buckets.over_90.map((x) => [x.invoice_number, x.customer, x.due_date, `${x.days_past_due}d`, money(x.balance_cents)])} />
        )}
      </section>

      <section className="card">
        <h2>AP aging — bills to pay</h2>
        <table className="os-table">
          <thead><tr><th>Bucket</th><th>Count</th><th>Balance</th></tr></thead>
          <tbody>
            {Object.entries(agingLabels).map(([key, label]) => (
              <tr key={key} style={{ fontWeight: (key === "61_90" || key === "over_90") && apAging.totals[key] > 0 ? "bold" : undefined }}>
                <td>{label}</td>
                <td>{apAging.buckets[key].length}</td>
                <td>{money(apAging.totals[key])}</td>
              </tr>
            ))}
            <tr style={{ borderTop: "2px solid var(--border, #ddd)", fontWeight: "bold" }}>
              <td>Total</td><td></td><td>{money(apAging.grand_total_cents)}</td>
            </tr>
          </tbody>
        </table>
        {apAging.buckets.over_90.length > 0 && (
          <Table headers={["Bill", "Vendor", "Due", "Days past", "Balance"]}
            rows={apAging.buckets.over_90.map((x) => [x.bill_number, x.vendor, x.due_date, `${x.days_past_due}d`, money(x.balance_cents)])} />
        )}
      </section>

      <section className="card"><h2>Profit & loss</h2>
        <Table headers={["Account", "Amount"]} rows={[
          ...profit.income.map((x) => [x.account.name, money(x.amount_cents)]),
          ["— Total income —", money(profit.total_income_cents)],
          ...profit.expenses.map((x) => [x.account.name, money(x.amount_cents)]),
          ["— Total expenses —", money(profit.total_expenses_cents)],
          ["Net income", money(profit.net_income_cents)],
        ]} />
      </section>

      <section className="card"><h2>Trial balance</h2>
        <Table headers={["Code", "Account", "Debit", "Credit"]} rows={trial.rows.map((x) => [x.account.code, x.account.name, money(x.debit_cents), money(x.credit_cents)])} />
      </section>
    </div>;
  }

  return null;
}

function Header({ title, copy }) { return <div className="os-heading"><div><span className="eyebrow">BUSINESS OS</span><h1>{title}</h1><p>{copy}</p></div></div>; }
function Notice({ text }) { return text ? <p className="os-alert">{text}</p> : null; }
function Table({ headers, rows }) { return <section className="card os-table-wrap"><table className="os-table"><thead><tr>{headers.map((x) => <th key={x}>{x}</th>)}</tr></thead><tbody>{rows.length ? rows.map((row, i) => <tr key={i}>{row.map((cell, j) => <td key={j}>{cell}</td>)}</tr>) : <tr><td colSpan={headers.length} className="os-empty">Nothing here yet.</td></tr>}</tbody></table></section>; }
