import { useEffect, useState } from "react";

import { api } from "../api";
import { DAY_NAMES, formatClock, formatDate } from "../utils";

const EMPTY = { request_type: "day_off", title: "", start_date: "", end_date: "", day_of_week: 0, start_time: "", end_time: "", rule_type: "unavailable", reason: "" };

export default function RequestsPage() {
  const [form, setForm] = useState(EMPTY);
  const [requests, setRequests] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  async function load() {
    try { setRequests(await api("/my/requests")); } catch (err) { setError(err.message); }
  }
  useEffect(() => { load(); }, []);

  async function submit(event) {
    event.preventDefault();
    try {
      setBusy(true); setError("");
      await api("/my/requests", { method: "POST", body: JSON.stringify(form) });
      setForm(EMPTY); setSaved(true); window.setTimeout(() => setSaved(false), 1800); await load();
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }

  return (
    <div className="page">
      <div className="page-header"><div><span className="eyebrow">TEAM REQUESTS</span><h1>Request a change</h1><p>Send a day-off or availability change to your manager for approval.</p></div>{saved && <div className="save-toast">✓ Request sent</div>}</div>
      {error && <div className="alert error">{error}</div>}
      <div className="request-layout">
        <form className="card request-form" onSubmit={submit}>
          <label>Request type<select value={form.request_type} onChange={(event) => setForm({ ...form, request_type: event.target.value })}><option value="day_off">Day off</option><option value="temporary_change">Temporary availability</option><option value="recurring_change">Recurring availability</option></select></label>
          <label>Short title<input placeholder="Doctor appointment, school schedule…" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} /></label>
          {form.request_type === "recurring_change" ? <><label>Weekday<select value={form.day_of_week} onChange={(event) => setForm({ ...form, day_of_week: Number(event.target.value) })}>{DAY_NAMES.map((day, index) => <option value={index} key={day}>{day}</option>)}</select></label><label>Rule<select value={form.rule_type} onChange={(event) => setForm({ ...form, rule_type: event.target.value })}><option value="unavailable">Unavailable</option><option value="preferred">Preferred</option></select></label></> : <div className="request-date-grid"><label>Start date<input type="date" value={form.start_date} onChange={(event) => setForm({ ...form, start_date: event.target.value })} /></label><label>End date<input type="date" value={form.end_date} onChange={(event) => setForm({ ...form, end_date: event.target.value })} /></label></div>}
          <div className="request-date-grid"><label>Start time <small>blank = full day</small><input type="time" value={form.start_time} onChange={(event) => setForm({ ...form, start_time: event.target.value })} /></label><label>End time<input type="time" value={form.end_time} onChange={(event) => setForm({ ...form, end_time: event.target.value })} /></label></div>
          <label>Reason<textarea placeholder="Anything your manager should know…" value={form.reason} onChange={(event) => setForm({ ...form, reason: event.target.value })} /></label>
          <button className="primary-btn" disabled={busy}>{busy ? "Sending…" : "Submit request"}</button>
        </form>
        <section className="card"><div className="section-title"><h2>My requests</h2><span className="count-pill">{requests.length}</span></div><div className="request-list">{requests.map((row) => <article className="request-card" key={row.id}><div><strong>{row.title || row.request_type.replaceAll("_", " ")}</strong><span className={`request-status ${row.status}`}>{row.status}</span></div><p>{row.start_date ? `${formatDate(row.start_date)}${row.end_date && row.end_date !== row.start_date ? ` – ${formatDate(row.end_date)}` : ""}` : row.day_of_week >= 0 ? DAY_NAMES[row.day_of_week] : ""}</p>{row.start_time && <small>{formatClock(row.start_time)} – {formatClock(row.end_time)}</small>}{row.manager_note && <div className="manager-response">Manager: {row.manager_note}</div>}</article>)}{!requests.length && <div className="empty-inline">No requests yet.</div>}</div></section>
      </div>
    </div>
  );
}
