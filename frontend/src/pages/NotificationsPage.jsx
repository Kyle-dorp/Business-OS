import { useEffect, useState } from "react";

import { api } from "../api";
import { DAY_NAMES, formatClock, formatDate } from "../utils";

function requestDescription(row) {
  if (row.request_type === "recurring_change") {
    const day = row.day_of_week === -1 ? "Every day" : DAY_NAMES[row.day_of_week];
    const time = row.start_time ? `${formatClock(row.start_time)} – ${formatClock(row.end_time)}` : "Full day";
    return `${day} · ${row.rule_type} · ${time}`;
  }
  const dates = row.start_date
    ? `${formatDate(row.start_date)}${row.end_date && row.end_date !== row.start_date ? ` – ${formatDate(row.end_date)}` : ""}`
    : "Date not set";
  const time = row.start_time ? `${formatClock(row.start_time)} – ${formatClock(row.end_time)}` : "Full day";
  return `${dates} · ${time}`;
}

export default function NotificationsPage({ onCountChange }) {
  const [requests, setRequests] = useState([]);
  const [notes, setNotes] = useState({});
  const [filter, setFilter] = useState("pending");
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState("");

  async function load() {
    try {
      setError("");
      const rows = await api(`/availability-requests${filter ? `?status=${filter}` : ""}`);
      setRequests(rows);
      const status = await api("/notifications");
      onCountChange?.(status.unread_count || 0);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => { load(); }, [filter]);

  async function review(id, status) {
    try {
      setBusyId(id);
      await api(`/availability-requests/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ status, manager_note: notes[id] || "" }),
      });
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <div><span className="eyebrow">MANAGER INBOX</span><h1>Notifications</h1><p>Review employee availability changes and days-off requests.</p></div>
        <div className="filter-pills">{["pending", "approved", "denied", ""].map((value) => <button key={value || "all"} className={filter === value ? "active" : ""} onClick={() => setFilter(value)}>{value ? value[0].toUpperCase() + value.slice(1) : "All"}</button>)}</div>
      </div>

      {error && <div className="alert error">{error}</div>}

      <div className="notification-list">
        {requests.map((row) => (
          <article className="notification-card" key={row.id}>
            <div className="notification-avatar">{row.employee_name?.slice(0, 1)?.toUpperCase() || "E"}</div>
            <div className="notification-content">
              <div className="notification-title-line"><div><strong>{row.employee_name}</strong><span>{row.title || row.request_type.replaceAll("_", " ")}</span></div><span className={`request-status ${row.status}`}>{row.status}</span></div>
              <p>{requestDescription(row)}</p>
              {row.reason && <blockquote>{row.reason}</blockquote>}
              {row.status === "pending" ? (
                <div className="review-controls">
                  <input placeholder="Optional response to employee" value={notes[row.id] || ""} onChange={(event) => setNotes((current) => ({ ...current, [row.id]: event.target.value }))} />
                  <button className="approve-btn small" disabled={busyId === row.id} onClick={() => review(row.id, "approved")}>Approve</button>
                  <button className="deny-btn" disabled={busyId === row.id} onClick={() => review(row.id, "denied")}>Deny</button>
                </div>
              ) : row.manager_note ? <div className="manager-response">Response: {row.manager_note}</div> : null}
            </div>
          </article>
        ))}
        {!requests.length && <section className="empty-state card"><div className="empty-icon">✓</div><h2>Nothing waiting here</h2><p>New employee requests will appear in this inbox.</p></section>}
      </div>
    </div>
  );
}
