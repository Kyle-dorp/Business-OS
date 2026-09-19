import { Component, useEffect, useMemo, useState } from "react";
// Loaded first, on purpose: it is legacy page CSS and the design language
// that follows must win every tie. See the header of the file itself.
import "./theme-legacy.css";
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
import "./theme-switch.css";
import "./theme-primitives.css";
import { api, getBusinessId, getToken, setBusinessId, setToken } from "./api";
import AssistantBubble from "./components/AssistantBubble";
import ThemeSwitch from "./components/ThemeSwitch";
import ModuleTag from "./components/ModuleTag";
import { useTheme } from "./hooks/useTheme";
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
import { Icon } from "./icons";

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

/**
 * Twenty-one flat entries was not a navigation, it was an inventory — and it
 * meant a new workspace's first impression was twenty-one things nobody had
 * set up yet. Ninety.io, the incumbent with comparable surface area, groups
 * everything behind six doors.
 *
 * The tab ids are unchanged on purpose. Routing, the saved-tab restore and
 * every onNavigate call in the app address these by id, so grouping is a
 * change to how the list is drawn and to nothing else.
 */
const MANAGER_TABS = [
  { id: "home", label: "Today", icon: "today" },

  { group: "Money", items: [
    { id: "sales", label: "Sales & invoices", icon: "sales", module: "sales" },
    { id: "purchasing", label: "Bills & purchasing", icon: "purchasing", module: "purchasing" },
    { id: "accounting", label: "Bookkeeping", icon: "bookkeeping", module: "accounting" },
    { id: "finance", label: "Finance", icon: "finance", module: "accounting" },
    { id: "reports", label: "Reports", icon: "reports", module: "reports" },
  ]},

  { group: "People", items: [
    { id: "manager", label: "Scheduling", icon: "scheduling", module: "scheduling" },
    { id: "availability", label: "Availability", icon: "availability", module: "scheduling" },
    { id: "preflight", label: "Preflight", icon: "preflight", module: "scheduling" },
    { id: "compliance", label: "Labor rules", icon: "compliance", module: "scheduling" },
    { id: "assistant", label: "Scheduling AI", icon: "assistant", module: "assistant" },
  ]},

  { group: "Stock", items: [
    { id: "inventory", label: "Inventory & assets", icon: "inventory", module: "inventory" },
    { id: "inventory-intel", label: "Stock intelligence", icon: "inventory-intel", module: "inventory" },
  ]},

  { group: "Guests", items: [
    { id: "bookings", label: "Bookings", icon: "bookings", module: "booking" },
    { id: "contacts", label: "Customers & vendors", icon: "contacts", module: "team" },
  ]},

  { group: "Work", items: [
    { id: "tasks", label: "Tasks", icon: "tasks", module: "tasks" },
    { id: "notifications", label: "Notifications", icon: "notifications", module: "notifications" },
  ]},

  { id: "ask", label: "Ask", icon: "ask" },

  { group: "Settings", items: [
    { id: "settings", label: "Workspace", icon: "settings" },
    { id: "billing", label: "Plan & billing", icon: "billing" },
    { id: "security", label: "Security", icon: "security" },
  ]},
];

/** Every leaf, flattened — for id lookups, which do not care about grouping. */
function flatten(entries) {
  return entries.flatMap((entry) => (entry.group ? entry.items : [entry]));
}
const EMPLOYEE_TABS = [
  { id: "home", label: "Home", icon: "today" },
  { id: "my-availability", label: "My availability", icon: "availability" },
  { id: "requests", label: "Requests", icon: "requests" },
  { id: "settings", label: "Settings", icon: "settings" },
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


/**
 * Which module the open tab belongs to.
 *
 * MANAGER_TABS already carries it — the nav has always known, it just never
 * said. Reading it from there rather than keeping a second mapping is what
 * stops the topbar disagreeing with the drawer.
 */
function moduleOfTab(tabId) {
  const entry = flatten(MANAGER_TABS).find((tab) => tab.id === tabId)
    || flatten(EMPLOYEE_TABS).find((tab) => tab.id === tabId);
  return entry?.module || null;
}


/**
 * Module key to the pages it unlocks.
 *
 * Billing lists ten things somebody is being charged for and, until this, said
 * nothing about what any of them put on screen. "Inventory — $10/mo" is a
 * line item; "Inventory — Inventory & assets, Stock intelligence" is an answer
 * to what am I paying for.
 */
function pagesByModule() {
  const map = {};
  for (const tab of [...flatten(MANAGER_TABS), ...flatten(EMPLOYEE_TABS)]) {
    if (!tab.module) continue;
    (map[tab.module] ||= []).push(tab.label);
  }
  // Employee and manager menus both contain Home and Settings; a module should
  // not claim the same page twice.
  for (const key of Object.keys(map)) map[key] = [...new Set(map[key])];
  return map;
}

export default function App() {
  const bookingBusinessId = publicBookingBusinessId();
  const [initializing, setInitializing] = useState(true);
  const [needsSetup, setNeedsSetup] = useState(false);
  const { theme, setTheme, accent, setAccent } = useTheme();
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
    const allowed = (tab) => !tab.module || configured.get(tab.module) !== false;

    return MANAGER_TABS.flatMap((entry) => {
      if (!entry.group) return allowed(entry) ? [entry] : [];
      // A heading with nothing under it is worse than no heading.
      const items = entry.items.filter(allowed);
      return items.length ? [{ ...entry, items }] : [];
    });
  }, [user?.role, workspace?.modules]);

  const flatTabs = useMemo(() => flatten(tabs), [tabs]);

  function restoreTab(nextUser) {
    const saved = localStorage.getItem(`business-eos.active-tab.${nextUser.id}`);
    const allowed = flatten(nextUser.role === "manager" ? MANAGER_TABS : EMPLOYEE_TABS).some((tab) => tab.id === saved);
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
    if (user && !flatTabs.some((tab) => tab.id === activeTab)) setActiveTab("home");
  }, [flatTabs, activeTab, user]);

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
  if (!user) {
    return (
      <>
        <div className="auth-theme-switch">
          <ThemeSwitch theme={theme} setTheme={setTheme} accent={accent} setAccent={setAccent} />
        </div>
        <AuthPage needsSetup={needsSetup} onAuthenticated={authenticated} />
      </>
    );
  }
  const currentLabel = flatTabs.find((tab) => tab.id === activeTab)?.label || "Today";

  return <div className="app commercial-shell">
    {drawerOpen && <button className="drawer-backdrop" aria-label="Close navigation" onClick={() => setDrawerOpen(false)} />}
    <aside className={drawerOpen ? "drawer open" : "drawer"}>
      <div className="drawer-brand"><div className="drawer-logo">E</div><div><strong>{workspace?.business?.name || "Business-EOS"}</strong><span>Operations + accounting</span></div><button className="drawer-close" onClick={() => setDrawerOpen(false)}>×</button></div>
      <nav className="drawer-nav">
        <div className="workspace-switcher"><select className="workspace-select" value={workspace?.business?.id || ""} onChange={(e) => switchBusiness(e.target.value)}>{businesses.map((x) => <option key={x.business.id} value={x.business.id}>{x.business.name}</option>)}</select>{user.role === "manager" && <button title="Create another business" onClick={createBusiness}>+</button>}</div>
        <span className="drawer-section-label">WORKSPACE</span>
        {tabs.map((entry) => {
          // The glyphs are decorative — several of them are announced as
          // punctuation by a screen reader, so the label carries the meaning
          // and the icon is hidden.
          const NavButton = (tab) => (
            <button
              key={tab.id}
              className={activeTab === tab.id ? "nav-btn active" : "nav-btn"}
              onClick={() => changeTab(tab.id)}
              aria-current={activeTab === tab.id ? "page" : undefined}
            >
              <Icon name={tab.icon} className="nav-icon" />
              <span>{tab.label}</span>
              {tab.id === "notifications" && notificationCount > 0 && (
                <span className="notification-badge" aria-label={`${notificationCount} unread`}>
                  {notificationCount}
                </span>
              )}
            </button>
          );

          if (!entry.group) return NavButton(entry);
          return (
            <div className="nav-group" key={entry.group}>
              <span className="nav-group-label">{entry.group}</span>
              {entry.items.map(NavButton)}
            </div>
          );
        })}
      </nav>
      <div className="drawer-footer account-footer"><div className="account-avatar">{user.username[0].toUpperCase()}</div><div><strong>{user.username}</strong><span>{workspace?.role || user.role}</span></div><button title="Log out" onClick={logout}>↪</button></div>
    </aside>
    <main className="main">
      <header className="topbar"><button className="hamburger" aria-label="Open navigation" onClick={() => setDrawerOpen(true)}><span /><span /><span /></button><div className="topbar-copy"><span>{workspace?.business?.name || "Business workspace"}</span><strong>{currentLabel}</strong></div><ModuleTag moduleKey={moduleOfTab(activeTab)} catalogue={workspace?.catalogue || []} modules={workspace?.modules || []} /><div className="topbar-actions"><ThemeSwitch theme={theme} setTheme={setTheme} accent={accent} setAccent={setAccent} />{user.role === "manager" && <button className="topbar-notification" onClick={() => changeTab("notifications")}>●{notificationCount > 0 && <b>{notificationCount}</b>}</button>}<button className="topbar-profile" onClick={() => changeTab("settings")}><span>{user.username[0].toUpperCase()}</span><div><strong>{user.username}</strong><small>{workspace?.role || user.role}</small></div></button></div></header>
      <PageErrorBoundary pageKey={activeTab}>
        {user.role === "manager" ? <>
          {activeTab === "home" && <TodayPage onNavigate={changeTab} />}
          {["contacts", "sales", "purchasing", "accounting", "reports", "tasks", "inventory"].includes(activeTab) && <PlatformPage section={activeTab} />}
          {activeTab === "availability" && <AvailabilityPage />}{activeTab === "manager" && <ManagerPage />}
          {activeTab === "finance" && <FinancePage />}
          {activeTab === "preflight" && <PreflightPage />}
          {activeTab === "ask" && <AgentPage />}
          {activeTab === "security" && <SecurityPage />}
          {activeTab === "billing" && <BillingPage onModulesChanged={refreshWorkspace} pages={pagesByModule()} />}
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
