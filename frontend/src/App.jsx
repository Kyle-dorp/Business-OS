import { Component, useEffect, useMemo, useState } from "react";
import "./App.css";
import { api, getBusinessId, getToken, setBusinessId, setToken } from "./api";
import AuthPage from "./pages/AuthPage";
import AssistantPage from "./pages/AssistantPage";
import AvailabilityPage from "./pages/AvailabilityPage";
import EmployeeAvailabilityPage from "./pages/EmployeeAvailabilityPage";
import EmployeeHomePage from "./pages/EmployeeHomePage";
import ManagerPage from "./pages/ManagerPage";
import NotificationsPage from "./pages/NotificationsPage";
import PlatformPage from "./pages/PlatformPage";
import RequestsPage from "./pages/RequestsPage";
import SettingsPage from "./pages/SettingsPage";

class PageErrorBoundary extends Component {
  constructor(props) { super(props); this.state = { error: null }; }
  static getDerivedStateFromError(error) { return { error }; }
  componentDidUpdate(previousProps) {
    if (previousProps.pageKey !== this.props.pageKey && this.state.error) this.setState({ error: null });
  }
  render() {
    if (!this.state.error) return this.props.children;
    return <div className="page"><section className="card crash-card"><div className="crash-icon">!</div><h1>This page hit a snag</h1><p>{this.state.error.message}</p><button className="primary-btn" onClick={() => window.location.reload()}>Reload workspace</button></section></div>;
  }
}

const MANAGER_TABS = [
  { id: "home", label: "Overview", icon: "⌂" },
  { id: "contacts", label: "Customers & vendors", icon: "◎", module: "team" },
  { id: "sales", label: "Sales & invoices", icon: "$", module: "sales" },
  { id: "purchasing", label: "Bills & purchasing", icon: "↓", module: "purchasing" },
  { id: "accounting", label: "Bookkeeping", icon: "≡", module: "accounting" },
  { id: "reports", label: "Reports", icon: "↗", module: "reports" },
  { id: "tasks", label: "Tasks", icon: "✓", module: "tasks" },
  { id: "inventory", label: "Inventory & assets", icon: "□", module: "inventory" },
  { id: "availability", label: "Availability", icon: "◷", module: "scheduling" },
  { id: "manager", label: "Scheduling", icon: "▦", module: "scheduling" },
  { id: "assistant", label: "AI Assistant", icon: "✦", module: "assistant" },
  { id: "notifications", label: "Notifications", icon: "●", module: "notifications" },
  { id: "settings", label: "Settings", icon: "⚙" },
];
const EMPLOYEE_TABS = [
  { id: "home", label: "Home", icon: "⌂" },
  { id: "my-availability", label: "My availability", icon: "◷" },
  { id: "requests", label: "Requests", icon: "+" },
  { id: "settings", label: "Settings", icon: "⚙" },
];
const MANAGER_NAV_GROUPS = [
  { label: "Money & records", ids: ["contacts", "sales", "purchasing", "accounting", "reports"] },
  { label: "Daily operations", ids: ["tasks", "inventory"] },
  { label: "People & scheduling", ids: ["availability", "manager"] },
];

export default function App() {
  const [initializing, setInitializing] = useState(true);
  const [needsSetup, setNeedsSetup] = useState(false);
  const [user, setUser] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("home");
  const [notificationCount, setNotificationCount] = useState(0);
  const [businesses, setBusinesses] = useState([]);
  const [workspace, setWorkspace] = useState(null);
  const tabs = useMemo(() => {
    if (user?.role !== "manager") return EMPLOYEE_TABS;
    const configured = new Map((workspace?.modules || []).map((item) => [item.module_key, item.enabled]));
    return MANAGER_TABS.filter((tab) => !tab.module || configured.get(tab.module) !== false);
  }, [user?.role, workspace?.modules]);

  function restoreTab(nextUser) {
    const saved = localStorage.getItem(`business-os.active-tab.${nextUser.id}`);
    const allowed = (nextUser.role === "manager" ? MANAGER_TABS : EMPLOYEE_TABS).some((tab) => tab.id === saved);
    setActiveTab(allowed ? saved : "home");
  }

  async function loadWorkspace() {
    let list = await api("/platform/businesses");
    if (!list.length) list = await api("/platform/bootstrap", { method: "POST" });
    setBusinesses(list);
    const selected = list.some((x) => String(x.business.id) === String(getBusinessId())) ? getBusinessId() : list[0]?.business.id;
    if (selected) { setBusinessId(selected); setWorkspace(await api("/platform/workspace")); }
  }

  async function bootstrap() {
    try {
      const setup = await api("/auth/setup-status");
      setNeedsSetup(setup.needs_setup);
      if (!setup.needs_setup && getToken()) {
        try { const current = await api("/auth/me"); setUser(current); restoreTab(current); await loadWorkspace(); }
        catch { setToken(""); setBusinessId(""); }
      }
    } finally { setInitializing(false); }
  }

  useEffect(() => { bootstrap(); }, []);
  useEffect(() => {
    const handler = () => { setToken(""); setBusinessId(""); setUser(null); setWorkspace(null); setDrawerOpen(false); };
    window.addEventListener("scheduler:unauthorized", handler);
    return () => window.removeEventListener("scheduler:unauthorized", handler);
  }, []);
  useEffect(() => {
    if (!user) return undefined;
    localStorage.setItem(`business-os.active-tab.${user.id}`, activeTab);
    const loadCount = () => api("/notifications").then((x) => setNotificationCount(x.unread_count || 0)).catch(() => {});
    loadCount(); const interval = window.setInterval(loadCount, 30000);
    return () => window.clearInterval(interval);
  }, [user, activeTab]);
  useEffect(() => {
    if (user && !tabs.some((tab) => tab.id === activeTab)) setActiveTab("home");
  }, [tabs, activeTab, user]);

  async function authenticated(nextUser) { setUser(nextUser); setNeedsSetup(false); restoreTab(nextUser); await loadWorkspace(); }
  function logout() { setToken(""); setBusinessId(""); setUser(null); setWorkspace(null); setDrawerOpen(false); }
  function changeTab(id) { setActiveTab(id); setDrawerOpen(false); }
  async function switchBusiness(id) { setBusinessId(id); setWorkspace(await api("/platform/workspace")); setActiveTab("home"); }
  async function refreshWorkspace() { setWorkspace(await api("/platform/workspace")); }
  async function createBusiness() {
    const name = window.prompt("New business name");
    if (!name?.trim()) return;
    const business = await api("/platform/businesses", { method: "POST", body: JSON.stringify({ name: name.trim() }) });
    await loadWorkspace(); await switchBusiness(business.id);
  }

  if (initializing) return <div className="boot-screen"><div className="boot-mark">O</div><div className="boot-pulse" /><p>Opening business workspace…</p></div>;
  if (!user) return <AuthPage needsSetup={needsSetup} onAuthenticated={authenticated} />;
  const currentLabel = tabs.find((tab) => tab.id === activeTab)?.label || "Home";
  const tabButton = (tab) => <button key={tab.id} className={activeTab === tab.id ? "nav-btn active" : "nav-btn"} onClick={() => changeTab(tab.id)}><span className="nav-icon">{tab.icon}</span><span>{tab.label}</span>{tab.id === "notifications" && notificationCount > 0 && <span className="notification-badge">{notificationCount}</span>}</button>;
  const groupedTabIds = new Set(MANAGER_NAV_GROUPS.flatMap((group) => group.ids));

  return <div className="app commercial-shell">
    {drawerOpen && <button className="drawer-backdrop" aria-label="Close navigation" onClick={() => setDrawerOpen(false)} />}
    <aside className={drawerOpen ? "drawer open" : "drawer"}>
      <div className="drawer-brand"><div className="drawer-logo">O</div><div><strong>{workspace?.business?.name || "Business OS"}</strong><span>Operations + accounting</span></div><button className="drawer-close" onClick={() => setDrawerOpen(false)}>×</button></div>
      <nav className="drawer-nav">
        <div className="workspace-switcher"><select className="workspace-select" value={workspace?.business?.id || ""} onChange={(e) => switchBusiness(e.target.value)}>{businesses.map((x) => <option key={x.business.id} value={x.business.id}>{x.business.name}</option>)}</select>{user.role === "manager" && <button title="Create another business" onClick={createBusiness}>+</button>}</div>
        <span className="drawer-section-label">WORKSPACE</span>
        {user.role !== "manager" ? tabs.map(tabButton) : <>
          {tabs.filter((tab) => tab.id === "home").map(tabButton)}
          {MANAGER_NAV_GROUPS.map((group) => {
            const groupTabs = tabs.filter((tab) => group.ids.includes(tab.id));
            if (!groupTabs.length) return null;
            return <details className="nav-group" key={group.label} defaultOpen={groupTabs.some((tab) => tab.id === activeTab)}>
              <summary>{group.label}<span aria-hidden="true">⌄</span></summary>
              <div>{groupTabs.map(tabButton)}</div>
            </details>;
          })}
          {tabs.filter((tab) => !groupedTabIds.has(tab.id) && !["home", "settings"].includes(tab.id)).map(tabButton)}
          {tabs.filter((tab) => tab.id === "settings").map(tabButton)}
        </>}
      </nav>
      <div className="drawer-footer account-footer"><div className="account-avatar">{user.username[0].toUpperCase()}</div><div><strong>{user.username}</strong><span>{workspace?.role || user.role}</span></div><button title="Log out" onClick={logout}>↪</button></div>
    </aside>
    <main className="main">
      <header className="topbar"><button className="hamburger" aria-label="Open navigation" onClick={() => setDrawerOpen(true)}><span /><span /><span /></button><div className="topbar-copy"><span>{workspace?.business?.name || "Business workspace"}</span><strong>{currentLabel}</strong></div><div className="topbar-actions">{user.role === "manager" && <button className="topbar-notification" onClick={() => changeTab("notifications")}>●{notificationCount > 0 && <b>{notificationCount}</b>}</button>}<button className="topbar-profile" onClick={() => changeTab("settings")}><span>{user.username[0].toUpperCase()}</span><div><strong>{user.username}</strong><small>{workspace?.role || user.role}</small></div></button></div></header>
      <PageErrorBoundary pageKey={activeTab}>
        {user.role === "manager" ? <>
          {activeTab === "home" && <PlatformPage section="overview" />}
          {["contacts", "sales", "purchasing", "accounting", "reports", "tasks", "inventory"].includes(activeTab) && <PlatformPage section={activeTab} />}
          {activeTab === "availability" && <AvailabilityPage />}{activeTab === "manager" && <ManagerPage />}
          {activeTab === "assistant" && <AssistantPage />}{activeTab === "notifications" && <NotificationsPage onCountChange={setNotificationCount} />}
          {activeTab === "settings" && <SettingsPage user={user} workspaceRole={workspace?.role} modules={workspace?.modules || []} onModulesChanged={refreshWorkspace} onUserChange={setUser} onLogout={logout} />}
        </> : <>{activeTab === "home" && <EmployeeHomePage />}{activeTab === "my-availability" && <EmployeeAvailabilityPage />}{activeTab === "requests" && <RequestsPage />}{activeTab === "settings" && <SettingsPage user={user} onUserChange={setUser} onLogout={logout} />}</>}
      </PageErrorBoundary>
    </main>
  </div>;
}
