import { useEffect, useMemo, useRef, useState } from "react";

import { api } from "../api";
import { formatWeekRange, shiftWeek, toIsoDate } from "../utils";

function currentMonday() {
  const today = new Date();
  const day = today.getDay();
  today.setDate(today.getDate() + (day === 0 ? -6 : 1 - day));
  return toIsoDate(today);
}

function readableRole(role) {
  if (role === "shift_lead") return "Shift Lead";
  if (role === "gm") return "GM";
  return "Employee";
}

function actionSummary(action) {
  switch (action.type) {
    case "create_employee":
      return `Add ${action.name || action.employee_name || "employee"} to ${action.department || "the team"} as ${readableRole(action.role)}`;
    case "update_employee":
      return `Update ${action.employee_name || action.name || "employee"}`;
    case "create_position":
      return `Add missing ${action.department || ""} position: ${action.name || action.position_name || "position"}`.trim();
    case "set_employee_positions":
      return `Set ${action.employee_name || action.name || "employee"} positions: ${(action.position_names || []).join(", ") || "none"}`;
    case "add_recurring_availability":
      return `Add ${action.rule_type || "availability"} for ${action.employee_name || action.name || "employee"}`;
    case "add_temporary_unavailability":
      return `Add temporary unavailability for ${action.employee_name || action.name || "employee"}`;
    case "create_labor_projection":
      return `Add projected sales/labor block for ${action.date || "a date"}`;
    case "create_crew_target":
      return `Add crew target: ${action.name || "crew target"}`;
    case "update_manager_settings":
      return "Update scheduling settings";
    case "regenerate_schedule":
      return `Regenerate ${String(action.scope || "problems").replaceAll("_", " ")} as a ${action.staffing_level || "balanced"} draft`;
    case "adjust_shift":
      return `Adjust ${action.employee_name || "the employee"}${action.new_end_time ? ` to end at ${action.new_end_time}` : ""}`;
    case "replace_shift_employee":
      return `Replace ${action.employee_name || "the scheduled employee"} with ${action.replacement_employee_name || "another employee"}`;
    case "toggle_module": {
      const label = { team: "Customers & vendors", scheduling: "Scheduling", accounting: "Accounting & Finance", sales: "Sales & invoices", purchasing: "Bills & purchasing", tasks: "Tasks", inventory: "Inventory", reports: "Reports", assistant: "AI Assistant", notifications: "Notifications" }[action.module_key] || action.module_key;
      return `${action.module_enabled ? "Show" : "Hide"} ${label}`;
    }
    case "update_ui_config": {
      const sections = Object.keys(action.ui_config_patch || {});
      if (sections.includes("theme")) return `Update theme colors`;
      if (sections.includes("branding")) return `Update branding (logo / tagline)`;
      if (sections.includes("nav_labels")) return `Rename nav labels`;
      return `Update appearance (${sections.join(", ") || "no changes"})`;
    }
    default:
      return String(action.type || "change").replaceAll("_", " ");
  }
}

export default function AssistantPage() {
  const [weekStart, setWeekStart] = useState(() => localStorage.getItem("scheduler.ai.week") || currentMonday());
  const [schedules, setSchedules] = useState([]);
  const [scheduleId, setScheduleId] = useState(() => localStorage.getItem("scheduler.ai.scheduleId") || "");
  const [status, setStatus] = useState({ ai_configured: false, mode: "fallback" });
  const [threadId, setThreadId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [memory, setMemory] = useState("");
  const [memoryOpen, setMemoryOpen] = useState(false);
  const [memorySaved, setMemorySaved] = useState(false);
  const [input, setInput] = useState(() => localStorage.getItem("scheduler.ai.draft") || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [appliedParts, setAppliedParts] = useState({});
  const [schedPanelOpen, setSchedPanelOpen] = useState(false);
  const chatEndRef = useRef(null);
  const textareaRef = useRef(null);

  async function loadThread() {
    try {
      const result = await api("/assistant/thread");
      setThreadId(result.thread.id);
      setMemory(result.memory || "");
      setMessages(result.messages || []);
    } catch (err) { setError(err.message); }
  }

  async function loadSchedules(preferredId = null) {
    try {
      const rows = await api(`/schedules?week_start=${weekStart}`);
      setSchedules(rows);
      const available = new Set(rows.map((row) => String(row.id)));
      const next = preferredId ? String(preferredId) : available.has(String(scheduleId)) ? String(scheduleId) : rows[0]?.id ? String(rows[0].id) : "";
      setScheduleId(next);
    } catch (err) { setError(err.message); }
  }

  useEffect(() => {
    Promise.all([api("/assistant/status"), api("/assistant/thread")])
      .then(([statusResult, threadResult]) => {
        setStatus(statusResult);
        setThreadId(threadResult.thread.id);
        setMemory(threadResult.memory || "");
        setMessages(threadResult.messages || []);
      })
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    localStorage.setItem("scheduler.ai.week", weekStart);
    loadSchedules();
  }, [weekStart]);

  useEffect(() => {
    localStorage.setItem("scheduler.ai.scheduleId", scheduleId || "");
  }, [scheduleId]);

  useEffect(() => {
    localStorage.setItem("scheduler.ai.draft", input);
    const element = textareaRef.current;
    if (element) {
      element.style.height = "auto";
      element.style.height = `${Math.min(Math.max(element.scrollHeight, 62), 190)}px`;
    }
  }, [input]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  async function sendText(text) {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    const optimistic = { role: "user", content: trimmed, id: `temp-${Date.now()}` };
    setMessages((current) => [...current, optimistic]);
    setInput("");
    setBusy(true);
    setError("");
    try {
      const result = await api("/assistant/chat", {
        method: "POST",
        body: JSON.stringify({
          message: trimmed,
          week_start: weekStart,
          schedule_id: scheduleId ? Number(scheduleId) : null,
          thread_id: threadId,
        }),
      });
      setThreadId(result.thread_id);
      await loadThread();
    } catch (err) {
      setError(err.message);
      setMessages((current) => current.filter((message) => message.id !== optimistic.id));
    } finally { setBusy(false); }
  }

  async function applyActions(actions, message, onlyIndex = null) {
    const selectedActions = onlyIndex === null ? actions : [actions[onlyIndex]];
    try {
      setBusy(true); setError("");
      const result = await api("/assistant/apply", {
        method: "POST",
        body: JSON.stringify({
          schedule_id: scheduleId ? Number(scheduleId) : null,
          week_start: weekStart,
          message_id: onlyIndex === null ? message.id : null,
          actions: selectedActions,
        }),
      });
      if (onlyIndex !== null) setAppliedParts((current) => ({ ...current, [`${message.id}-${onlyIndex}`]: true }));
      if (result.schedule?.id) await loadSchedules(result.schedule.id);
      await loadThread();
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }

  async function saveMemory() {
    try {
      await api("/assistant/memory", { method: "PUT", body: JSON.stringify({ content: memory }) });
      setMemorySaved(true); window.setTimeout(() => setMemorySaved(false), 1800);
    } catch (err) { setError(err.message); }
  }

  async function clearChat() {
    if (!window.confirm("Clear this chat? Your Always Remember notes will stay saved.")) return;
    try { await api("/assistant/thread", { method: "DELETE" }); setMessages([]); } catch (err) { setError(err.message); }
  }

  const selectedSchedule = useMemo(() => schedules.find((row) => String(row.id) === String(scheduleId)), [schedules, scheduleId]);

  return (
    <div className="assistant-fullscreen">
      {/* Slim control bar */}
      <div className="asst-bar">
        <div className="asst-bar-left">
          <div className="ai-avatar asst-avatar">✦</div>
          <div>
            <strong>Business Assistant</strong>
            <span className={status.ai_configured ? "asst-status on" : "asst-status off"}>
              {status.ai_configured ? "● Claude connected" : "● Fallback mode"}
            </span>
          </div>
        </div>
        <div className="asst-bar-right">
          <button className={schedPanelOpen ? "asst-sched-toggle active" : "asst-sched-toggle"} onClick={() => setSchedPanelOpen((v) => !v)} title="Scheduling context">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true"><rect x="1" y="2" width="12" height="11" rx="2" stroke="currentColor" strokeWidth="1.5"/><path d="M1 6h12" stroke="currentColor" strokeWidth="1.5"/><path d="M4 1v2M10 1v2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
            Schedule
          </button>
          <button className="secondary-btn compact" onClick={() => setMemoryOpen((v) => !v)}>Always remember</button>
          <button className="secondary-btn compact" onClick={clearChat}>Clear</button>
        </div>
      </div>

      {error && <div className="asst-error">{error}</div>}

      {/* Schedule context panel */}
      {schedPanelOpen && (
        <div className="asst-sched-drawer">
          <div className="context-week-control">
            <button onClick={() => setWeekStart(shiftWeek(weekStart, -1))}>←</button>
            <label><span>Select week</span><strong>{formatWeekRange(weekStart)}</strong><input type="date" value={weekStart} onChange={(event) => setWeekStart(event.target.value)} /></label>
            <button onClick={() => setWeekStart(shiftWeek(weekStart, 1))}>→</button>
          </div>
          <label className="schedule-context-select"><span>Schedule version <small>optional</small></span><select value={scheduleId} onChange={(event) => setScheduleId(event.target.value)}><option value="">No schedule selected</option>{schedules.map((row) => <option value={row.id} key={row.id}>Version {row.version} · {row.status.replaceAll("_", " ")}</option>)}</select></label>
          <div className="context-summary"><span>Context</span><strong>{selectedSchedule ? `Business + schedule ${selectedSchedule.version}` : "Whole business"}</strong></div>
        </div>
      )}

      {/* Always-remember panel */}
      {memoryOpen && (
        <div className="asst-memory-panel">
          <div><span className="eyebrow">DURABLE CONTEXT</span><p>Stays attached to every request — good for standing rules like "prep works 8–4".</p></div>
          <textarea placeholder="Example: Prep always works 8–4. Avoid scheduling Sandra after 3 PM." value={memory} onChange={(event) => setMemory(event.target.value)} />
          <button className="small-btn" onClick={saveMemory}>{memorySaved ? "Saved ✓" : "Save memory"}</button>
        </div>
      )}

      {/* Full-height chat */}
      <section className="ai-chat-panel asst-full-panel">
        <div className="chat-thread">
          {!messages.length && <div className="chat-welcome"><div className="welcome-spark">✦</div><h2>Ask in plain English.</h2><p>Try "What do customers owe us?", "How profitable are we?", "What needs attention?", or describe a scheduling change.</p></div>}
          {messages.map((message, index) => {
            const actions = message.actions || [];
            return (
              <div className={`chat-message-row ${message.role}`} key={message.id || `${message.role}-${index}`}>
                {message.role === "assistant" && <div className="message-avatar">AI</div>}
                <div className="message-stack">
                  <div className="message-bubble"><p>{message.content}</p></div>
                  {actions.length > 0 && (
                    <div className="proposal-card">
                      <div className="proposal-heading"><div><span>Review changes</span><strong>{actions.length} proposed</strong></div>{message.applied && <span className="applied-badge">Applied</span>}</div>
                      <div className="proposal-list">{actions.map((action, actionIndex) => {
                        const partApplied = appliedParts[`${message.id}-${actionIndex}`];
                        const missingPosition = action.type === "create_position";
                        return <div className={`proposal-item ${missingPosition ? "missing-position" : ""}`} key={actionIndex}><span className="proposal-number">{actionIndex + 1}</span><div><p>{actionSummary(action)}</p>{action.reason && <small>{action.reason}</small>}</div>{!message.applied && <button className={missingPosition ? "position-approve-btn" : "mini-apply-btn"} disabled={busy || partApplied} onClick={() => applyActions(actions, message, actionIndex)}>{partApplied ? "Applied ✓" : missingPosition ? "Add position" : "Apply"}</button>}</div>;
                      })}</div>
                      {!message.applied && <button className="approve-btn" disabled={busy} onClick={() => applyActions(actions, message)}>Approve all changes</button>}
                    </div>
                  )}
                </div>
                {message.role === "user" && <div className="message-avatar user">You</div>}
              </div>
            );
          })}
          {busy && <div className="chat-message-row assistant"><div className="message-avatar">AI</div><div className="typing-bubble"><span /><span /><span /></div></div>}
          <div ref={chatEndRef} />
        </div>
        <form className="composer modern-composer" onSubmit={(event) => { event.preventDefault(); sendText(input); }}>
          <textarea ref={textareaRef} rows="1" value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); sendText(input); } }} placeholder="Ask about your business…" />
          <div className="composer-footer"><span>Shift+Enter for a new line</span><button className="send-button" disabled={busy || !input.trim()} aria-label="Send message">↑</button></div>
        </form>
      </section>
    </div>
  );
}
