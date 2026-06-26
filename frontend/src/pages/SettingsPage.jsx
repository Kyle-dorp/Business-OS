import { useEffect, useState } from "react";
import { api, setToken } from "../api";

const MODULE_OPTIONS = [
  ["team", "Customers & vendors", "People and companies you buy from or sell to."],
  ["sales", "Sales & invoices", "Invoices and customer payments."],
  ["purchasing", "Bills & purchasing", "Vendor bills and payments."],
  ["accounting", "Bookkeeping", "Expenses, accounts, and journal entries."],
  ["reports", "Financial reports", "Profit and loss, balance sheet, and trial balance."],
  ["tasks", "Tasks", "Daily work and reusable checklists."],
  ["inventory", "Inventory & assets", "Stock, supplies, equipment, and reorder levels."],
  ["scheduling", "Team scheduling", "Departments, availability, staffing, and schedules."],
  ["assistant", "AI assistant", "Business-wide questions and reviewable changes."],
  ["notifications", "Notifications", "Requests, approvals, and warnings."],
];
const SIMPLE_MODULES = new Set(["team", "sales", "accounting", "assistant"]);

export default function SettingsPage({ user, workspaceRole, modules = [], onModulesChanged, onUserChange, onLogout }) {
  const [account, setAccount] = useState({ username: user.username, current_password: "", new_password: "" });
  const [users, setUsers] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [newUser, setNewUser] = useState({ username: "", password: "", role: "", employee_id: "" });
  const [moduleState, setModuleState] = useState({});
  const [presets, setPresets] = useState([]);
  const [businessDescription, setBusinessDescription] = useState("");
  const [recommendation, setRecommendation] = useState(null);
  const [modulesBusy, setModulesBusy] = useState(false);
  const [businessName, setBusinessName] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  useEffect(() => {
    const configured = new Map(modules.map((item) => [item.module_key, item.enabled]));
    setModuleState(Object.fromEntries(MODULE_OPTIONS.map(([key]) => [key, configured.get(key) !== false])));
  }, [modules]);

  async function loadTeam() {
    if (user.role !== "manager") return;
    try {
      const [accountRows, employeeRows] = await Promise.all([api("/auth/users"), api("/employees")]);
      setUsers(accountRows); setEmployees(employeeRows.filter((row) => row.active));
    } catch (err) { setError(err.message); }
  }
  useEffect(() => { loadTeam(); }, [user.role]);
  useEffect(() => {
    if (["owner", "admin"].includes(workspaceRole)) {
      api("/platform/presets").then(setPresets).catch((err) => setError(err.message));
      api("/platform/workspace").then((ws) => setBusinessName(ws?.business?.name || "")).catch(() => {});
    }
  }, [workspaceRole]);

  function flash(message) { setSaved(message); window.setTimeout(() => setSaved(""), 1800); }

  async function saveAccount(event) {
    event.preventDefault();
    try {
      setError(""); const result = await api("/auth/me", { method: "PATCH", body: JSON.stringify(account) });
      setToken(result.token); onUserChange(result.user);
      setAccount({ username: result.user.username, current_password: "", new_password: "" }); flash("Account updated");
    } catch (err) { setError(err.message); }
  }

  async function createUser(event) {
    event.preventDefault();
    if (!newUser.username.trim() || !newUser.password || !newUser.role || (newUser.role === "employee" && !newUser.employee_id)) return;
    try {
      setError(""); await api("/auth/users", { method: "POST", body: JSON.stringify({ ...newUser, username: newUser.username.trim(), employee_id: newUser.employee_id ? Number(newUser.employee_id) : null }) });
      setNewUser({ username: "", password: "", role: "", employee_id: "" }); flash("Team login created"); await loadTeam();
    } catch (err) { setError(err.message); }
  }

  async function toggleUser(row) {
    try { await api(`/auth/users/${row.id}`, { method: "PATCH", body: JSON.stringify({ active: !row.active }) }); await loadTeam(); }
    catch (err) { setError(err.message); }
  }

  async function setModule(key, enabled) {
    try {
      setModulesBusy(true); setError("");
      await api(`/platform/modules/${key}`, { method: "PUT", body: JSON.stringify({ enabled }) });
      setModuleState((current) => ({ ...current, [key]: enabled })); await onModulesChanged?.();
      flash(enabled ? "Tool shown in the menu" : "Tool hidden from the menu");
    } catch (err) { setError(err.message); } finally { setModulesBusy(false); }
  }

  async function applyPreset(simple) {
    try {
      setModulesBusy(true); setError("");
      await Promise.all(MODULE_OPTIONS.map(([key]) => api(`/platform/modules/${key}`, { method: "PUT", body: JSON.stringify({ enabled: simple ? SIMPLE_MODULES.has(key) : true }) })));
      await onModulesChanged?.(); flash(simple ? "Simple menu applied" : "All tools are visible");
    } catch (err) { setError(err.message); } finally { setModulesBusy(false); }
  }

  async function choosePreset(key) {
    try {
      setModulesBusy(true); setError("");
      await api(`/platform/presets/${key}/apply`, { method: "POST" });
      await onModulesChanged?.(); flash("Business setup applied — reload to see branding changes");
    } catch (err) { setError(err.message); } finally { setModulesBusy(false); }
  }

  async function saveBusinessName() {
    try {
      setError("");
      await api("/platform/business", { method: "PATCH", body: JSON.stringify({ name: businessName }) });
      flash("Business name updated — reload to see it in the sidebar");
    } catch (err) { setError(err.message); }
  }

  async function askAiForPreset() {
    if (!businessDescription.trim()) return;
    try {
      setModulesBusy(true); setError("");
      setRecommendation(await api("/platform/presets/recommend", { method: "POST", body: JSON.stringify({ description: businessDescription }) }));
    } catch (err) { setError(err.message); } finally { setModulesBusy(false); }
  }

  return <div className="page">
    <div className="page-header"><div><span className="eyebrow">WORKSPACE CONTROLS</span><h1>Settings</h1><p>Choose what appears, manage your sign-in, and control access.</p></div>{saved && <div className="save-toast">✓ {saved}</div>}</div>
    {error && <div className="alert error">{error}</div>}

    {user.role === "manager" && ["owner", "admin"].includes(workspaceRole) && <>
      <section className="card os-form" style={{ borderTop: "3px solid var(--blue, #2f6fed)" }}>
        <span className="eyebrow">BUSINESS PROFILE</span>
        <h2 style={{ marginTop: "4px" }}>Business name</h2>
        <div style={{ display: "flex", gap: "8px", alignItems: "center", marginTop: "8px" }}>
          <input value={businessName} onChange={(e) => setBusinessName(e.target.value)} placeholder="e.g. Bam's Sub Shoppe" style={{ flex: 1 }} />
          <button className="primary-btn" onClick={saveBusinessName} disabled={!businessName.trim()}>Save</button>
        </div>
      </section>

      <details className="card ops-disclosure setup-disclosure" defaultOpen>
        <summary><div><span className="eyebrow">QUICK SETUP</span><h2>What kind of business is this?</h2><p>A preset configures the right tools, departments, closing checklist, and branding in one click.</p></div><b>⌄</b></summary>
        <div className="disclosure-body">
          <div className="preset-grid">{presets.map((preset) => <button key={preset.key} disabled={modulesBusy} onClick={() => choosePreset(preset.key)} style={preset.key === "sub_shop" ? { borderColor: "var(--blue,#2f6fed)", background: "var(--blue,#2f6fed)11" } : undefined}><strong>{preset.label}</strong><span>{preset.description}</span></button>)}</div>
          <div className="ai-preset-box"><div><span className="eyebrow">LET CLAUDE CHOOSE</span><h3>Describe the business normally</h3><p>Claude will recommend a preset. Nothing changes until you approve it.</p></div><textarea placeholder="Example: We run a warehouse that receives pallets, stores inventory, and ships customer orders." value={businessDescription} onChange={(event) => setBusinessDescription(event.target.value)} /><button className="primary-btn" disabled={modulesBusy || !businessDescription.trim()} onClick={askAiForPreset}>Recommend my setup</button>{recommendation && <div className="preset-recommendation"><div><strong>{recommendation.label}</strong><span>{recommendation.description}</span></div><button className="small-btn" onClick={() => choosePreset(recommendation.key)}>Apply this setup</button></div>}</div>
        </div>
      </details>

      <details className="card ops-disclosure module-settings-card">
        <summary><div><span className="eyebrow">CUSTOM SETUP</span><h2>Choose tools one by one</h2><p>Open this only when you want precise control over the menu.</p></div><b>⌄</b></summary>
        <div className="disclosure-body"><div className="module-preset-actions"><button className="secondary-btn compact" disabled={modulesBusy} onClick={() => applyPreset(true)}>Use a simple menu</button><button className="secondary-btn compact" disabled={modulesBusy} onClick={() => applyPreset(false)}>Show everything</button></div><div className="module-toggle-grid">{MODULE_OPTIONS.map(([key, label, description]) => <label className="module-toggle-row" key={key}><div><strong>{label}</strong><span>{description}</span></div><input type="checkbox" checked={moduleState[key] !== false} disabled={modulesBusy} onChange={(event) => setModule(key, event.target.checked)} /></label>)}</div><p className="module-safety-note">Overview and Settings always remain visible.</p></div>
      </details>
    </>}

    <div className="settings-layout">
      <form className="card account-card" onSubmit={saveAccount}>
        <div className="section-title"><div><span className="eyebrow">MY ACCOUNT</span><h2>Sign-in details</h2></div><span className={`role-chip ${user.role}`}>{user.role}</span></div>
        <label>Username<input value={account.username} onChange={(event) => setAccount({ ...account, username: event.target.value })} /></label>
        <label>Current password<input type="password" placeholder="Required to change password" value={account.current_password} onChange={(event) => setAccount({ ...account, current_password: event.target.value })} /></label>
        <label>New password<input type="password" placeholder="Leave blank to keep current password" value={account.new_password} onChange={(event) => setAccount({ ...account, new_password: event.target.value })} /></label>
        <div className="settings-actions"><button className="primary-btn">Save account</button><button type="button" className="danger-outline-btn" onClick={onLogout}>Log out</button></div>
      </form>

      {user.role === "manager" && <section className="card team-access-card">
        <div className="section-title"><div><span className="eyebrow">TEAM ACCESS</span><h2>Manager & employee logins</h2></div><span className="count-pill">{users.length}</span></div>
        <form className="team-account-form" onSubmit={createUser} autoComplete="off">
          <input placeholder="New username" value={newUser.username} onChange={(event) => setNewUser({ ...newUser, username: event.target.value })} />
          <input type="password" placeholder="Temporary password" value={newUser.password} onChange={(event) => setNewUser({ ...newUser, password: event.target.value })} />
          <select value={newUser.role} onChange={(event) => setNewUser({ ...newUser, role: event.target.value, employee_id: event.target.value === "manager" ? "" : newUser.employee_id })}><option value="">Select account type…</option><option value="employee">Employee</option><option value="manager">Manager</option></select>
          {newUser.role === "employee" ? <select value={newUser.employee_id} onChange={(event) => setNewUser({ ...newUser, employee_id: event.target.value })}><option value="">Link employee profile…</option>{employees.map((employee) => <option value={employee.id} key={employee.id}>{employee.name}</option>)}</select> : <div className="team-profile-placeholder">{newUser.role === "manager" ? "Manager account" : "Choose account type"}</div>}
          <button className="small-btn">Create login</button>
        </form>
        <div className="team-account-list">{users.map((row) => <article className="team-account-row" key={row.id}><div className="account-avatar">{row.username[0].toUpperCase()}</div><div><strong>{row.username}</strong><span>{row.role}</span></div><span className={row.active ? "account-state active" : "account-state"}>{row.active ? "Active" : "Disabled"}</span><button className="secondary-btn compact" disabled={row.id === user.id} onClick={() => toggleUser(row)}>{row.active ? "Disable" : "Enable"}</button></article>)}</div>
      </section>}
    </div>
  </div>;
}
