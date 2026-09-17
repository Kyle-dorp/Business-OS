import { Component, useEffect, useMemo, useState } from "react";
import "./App.css";
// Loaded after App.css on purpose: App.css owns layout and structure, these own
// the look, and later import wins on equal specificity.
import "./theme.css";
import "./theme-pages.css";
import "./theme-security.css";
import "./theme-billing.css";
import "./theme-compliance.css";
import "./theme-inventory.css";
import "./theme-booking.css";
import "./theme-app.css";
import "./theme-bubble.css";
import "./theme-today.css";
import "./theme-charts.css";
import { api, getBusinessId, getToken, setBusinessId, setToken } from "./api";
import AssistantBubble from "./components/AssistantBubble";
import { mondayOf, toIsoDate } from "./utils";
import TodayPage from "./pages/TodayPage";
import AuthPage from "./pages/AuthPage";
import AgentPage from "./pages/AgentPage";
import PreflightPage from "./pages/PreflightPage";
import SecurityPage from "./pages/SecurityPage";
import BillingPage from "./pages/BillingPage";
import CompliancePage from "./pages/CompliancePage";
import InventoryIntelPage from "./pages/InventoryIntelPage";
import PublicBookingPage from "./pages/PublicBookingPage";
import BookingAdminPage from "./pages/BookingAdminPage";
import AssistantPage from "./pages/AssistantPage";
import AvailabilityPage from "./pages/AvailabilityPage";
import EmployeeAvailabilityPage from "./pages/EmployeeAvailabilityPage";
import EmployeeHomePage from "./pages/EmployeeHomePage";
import ManagerPage from "./pages/ManagerPage";
import NotificationsPage from "./pages/NotificationsPage";
import PlatformPage from "./pages/PlatformPage";
import RequestsPage from "./pages/RequestsPage";
import SettingsPage from "./pages/SettingsPage";
import FinancePage from "./pages/FinancePage";

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
  { id: "finance", label: "Finance", icon: "$", module: "accounting" },
  { id: "reports", label: "Reports", icon: "↗", module: "reports" },
  { id: "tasks", label: "Tasks", icon: "✓", module: "tasks" },
  { id: "inventory", label: "Inventory & assets", icon: "□", module: "inventory" },
  { id: "inventory-intel", label: "Stock intelligence", icon: "◉", module: "inventory" },
  { id: "availability", label: "Availability", icon: "◷", module: "scheduling" },
  { id: "manager", label: "Scheduling", icon: "▦", module: "scheduling" },
  { id: "preflight", label: "Preflight", icon: "◈", module: "scheduling" },
  { id: "compliance", label: "Labor rules", icon: "⚖", module: "scheduling" },
  { id: "bookings", label: "Bookings", icon: "◑", module: "booking" },
  { id: "ask", label: "Ask", icon: "✦" },
  { id: "assistant", label: "Scheduling AI", icon: "◇", module: "assistant" },
  { id: "notifications", label: "Notifications", icon: "●", module: "notifications" },
  { id: "billing", label: "Plan & billing", icon: "◉" },
  { id: "security", label: "Security", icon: "⛨" },
  { id: "settings", label: "Settings", icon: "⚙" },
];
const EMPLOYEE_TABS = [
  { id: "home", label: "Home", icon: "⌂" },
  { id: "my-availability", label: "My availability", icon: "◷" },
  { id: "requests", label: "Requests", icon: "+" },
  { id: "settings", label: "Settings", icon: "⚙" },
];

/**
 * A customer arriving at /book/123 is not a user and must never be shown a
 * sign-in screen. Read straight off the path rather than adding a router for
 * one public route.
 */
function publicBookingBusinessId() {
  const match = window.location.pathname.match(/^\/book\/(\d+)/);
  return match ? match[1] : null;
}

export default function App() {
  const bookingBusinessId = publicBookingBusinessId();
  const [initializing, setInitializing] = useState(true);
  const [needsSetup, setNeedsSetup] = useState(false);
  const [user, setUser] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("home");
  // What is actually waiting on somebody — an unpublishable rota, an overdue
  // invoice, stock about to run out. The bubble rings for this rather than for
  // the notification count, which the nav already carries and which is a
  // different question.
  const [attention, setAttention] = useState(0);
  const [notificationCount, setNotificationCount] = useState(0);
  const [businesses, setBusinesses] = useState([]);
  const [workspace, setWorkspace] = useState(null);
  const tabs = useMemo(() => {
    if (user?.role !== "manager") return EMPLOYEE_TABS;
    const configured = new Map((workspace?.modules || []).map((item) => [item.module_key, item.enabled]));
    return MANAGER_TABS.filter((tab) => !tab.module || configured.get(tab.module) !== false);
  }, [user?.role, workspace?.modules]);

  function restoreTab(nextUser) {
    const saved = localStorage.getItem(`business-eos.active-tab.${nextUser.id}`);
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

  useEffect(() => { if (!bookingBusinessId) bootstrap(); }, [bookingBusinessId]);
  useEffect(() => {
    const handler = () => { setToken(""); setBusinessId(""); setUser(null); setWorkspace(null); setDrawerOpen(false); };
    window.addEventListener("scheduler:unauthorized", handler);
    return () => window.removeEventListener("scheduler:unauthorized", handler);
  }, []);
  useEffect(() => {
    if (!user) return undefined;
    localStorage.setItem(`business-eos.active-tab.${user.id}`, activeTab);
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

  useEffect(() => {
    if (!user || user.role !== "manager") return;
    api("/platform/today")
      .then((d) => setAttention(d?.attention_count ?? 0))
      .catch(() => {});   // A dashboard that will not load must not break the shell.
  }, [user, activeTab]);
  async function switchBusiness(id) { setBusinessId(id); setWorkspace(await api("/platform/workspace")); setActiveTab("home"); }
  async function refreshWorkspace() { setWorkspace(await api("/platform/workspace")); }
  async function createBusiness() {
    const name = window.prompt("New business name");
    if (!name?.trim()) return;
    const business = await api("/platform/businesses", { method: "POST", body: JSON.stringify({ name: name.trim() }) });
    await loadWorkspace(); await switchBusiness(business.id);
  }

  if (bookingBusinessId) return <PublicBookingPage businessId={bookingBusinessId} />;
  if (initializing) return <div className="boot-screen"><div className="boot-mark">E</div><div className="boot-pulse" /><p>Opening business workspace…</p></div>;
  if (!user) return <AuthPage needsSetup={needsSetup} onAuthenticated={authenticated} />;
  const currentLabel = tabs.find((tab) => tab.id === activeTab)?.label || "Home";

  return <div className="app commercial-shell">
    {drawerOpen && <button className="drawer-backdrop" aria-label="Close navigation" onClick={() => setDrawerOpen(false)} />}
    <aside className={drawerOpen ? "drawer open" : "drawer"}>
      <div className="drawer-brand"><div className="drawer-logo">E</div><div><strong>{workspace?.business?.name || "Business-EOS"}</strong><span>Operations + accounting</span></div><button className="drawer-close" onClick={() => setDrawerOpen(false)}>×</button></div>
      <nav className="drawer-nav">
        <div className="workspace-switcher"><select className="workspace-select" value={workspace?.business?.id || ""} onChange={(e) => switchBusiness(e.target.value)}>{businesses.map((x) => <option key={x.business.id} value={x.business.id}>{x.business.name}</option>)}</select>{user.role === "manager" && <button title="Create another business" onClick={createBusiness}>+</button>}</div>
        <span className="drawer-section-label">WORKSPACE</span>
        {tabs.map((tab) => <button key={tab.id} className={activeTab === tab.id ? "nav-btn active" : "nav-btn"} onClick={() => changeTab(tab.id)}><span className="nav-icon">{tab.icon}</span><span>{tab.label}</span>{tab.id === "notifications" && notificationCount > 0 && <span className="notification-badge">{notificationCount}</span>}</button>)}
      </nav>
      <div className="drawer-footer account-footer"><div className="account-avatar">{user.username[0].toUpperCase()}</div><div><strong>{user.username}</strong><span>{workspace?.role || user.role}</span></div><button title="Log out" onClick={logout}>↪</button></div>
    </aside>
    <main className="main">
      <header className="topbar"><button className="hamburger" aria-label="Open navigation" onClick={() => setDrawerOpen(true)}><span /><span /><span /></button><div className="topbar-copy"><span>{workspace?.business?.name || "Business workspace"}</span><strong>{currentLabel}</strong></div><div className="topbar-actions">{user.role === "manager" && <button className="topbar-notification" onClick={() => changeTab("notifications")}>●{notificationCount > 0 && <b>{notificationCount}</b>}</button>}<button className="topbar-profile" onClick={() => changeTab("settings")}><span>{user.username[0].toUpperCase()}</span><div><strong>{user.username}</strong><small>{workspace?.role || user.role}</small></div></button></div></header>
      <PageErrorBoundary pageKey={activeTab}>
        {user.role === "manager" ? <>
          {activeTab === "home" && <TodayPage onNavigate={changeTab} />}
          {["contacts", "sales", "purchasing", "accounting", "reports", "tasks", "inventory"].includes(activeTab) && <PlatformPage section={activeTab} />}
          {activeTab === "availability" && <AvailabilityPage />}{activeTab === "manager" && <ManagerPage />}
          {activeTab === "finance" && <FinancePage />}
          {activeTab === "preflight" && <PreflightPage />}
          {activeTab === "ask" && <AgentPage />}
          {activeTab === "security" && <SecurityPage />}
          {activeTab === "billing" && <BillingPage onModulesChanged={refreshWorkspace} />}
          {activeTab === "compliance" && <CompliancePage />}
          {activeTab === "inventory-intel" && <InventoryIntelPage />}
          {activeTab === "bookings" && <BookingAdminPage />}
          {activeTab === "assistant" && <AssistantPage />}{activeTab === "notifications" && <NotificationsPage onCountChange={setNotificationCount} />}
          {activeTab === "settings" && <SettingsPage user={user} workspaceRole={workspace?.role} modules={workspace?.modules || []} onModulesChanged={refreshWorkspace} onUserChange={setUser} onLogout={logout} />}
        </> : <>{activeTab === "home" && <EmployeeHomePage />}{activeTab === "my-availability" && <EmployeeAvailabilityPage />}{activeTab === "requests" && <RequestsPage />}{activeTab === "settings" && <SettingsPage user={user} onUserChange={setUser} onLogout={logout} />}</>}
      </PageErrorBoundary>
    </main>

    {/* Outside <main> on purpose: it is fixed to the viewport, and nesting it
        in a scrolling region would carry it up the page. Employees get it too
        — "am I on this weekend" is the question they actually have. */}
    <AssistantBubble
      page={activeTab}
      pageLabel={currentLabel}
      weekStart={toIsoDate(mondayOf())}
      attention={attention}
    />
  </div>;
}
