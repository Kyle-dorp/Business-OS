import { useEffect, useState } from "react";

import { api } from "../api";
import { DAY_NAMES, formatClock, formatDate } from "../utils";

export default function EmployeeAvailabilityPage() {
  const [data, setData] = useState({ recurring: [], temporary: [] });
  const [error, setError] = useState("");

  useEffect(() => {
    api("/my/availability").then(setData).catch((err) => setError(err.message));
  }, []);

  return (
    <div className="page">
      <div className="page-header"><div><span className="eyebrow">CURRENT RULES</span><h1>My availability</h1><p>These are the rules currently used by the schedule generator. Submit a request to change them.</p></div></div>
      {error && <div className="alert error">{error}</div>}
      <div className="two-column portal-columns">
        <section className="card"><div className="section-title"><h2>Recurring</h2><span className="count-pill">{data.recurring.length}</span></div>{data.recurring.length ? <div className="request-list">{data.recurring.map((row) => <div className="request-summary" key={row.id}><strong>{row.rule_type === "preferred" ? "Preferred" : "Unavailable"}</strong><span>{row.day_of_week === -1 ? "Every day" : DAY_NAMES[row.day_of_week]}</span><small>{row.start_time ? `${formatClock(row.start_time)} – ${formatClock(row.end_time)}` : "Full day"}</small></div>)}</div> : <div className="empty-inline">No recurring rules.</div>}</section>
        <section className="card"><div className="section-title"><h2>Temporary</h2><span className="count-pill">{data.temporary.length}</span></div>{data.temporary.length ? <div className="request-list">{data.temporary.map((row) => <div className="request-summary" key={row.id}><strong>{formatDate(row.start_date)}</strong><span>{row.end_date && row.end_date !== row.start_date ? `through ${formatDate(row.end_date)}` : "One day"}</span><small>{row.start_time ? `${formatClock(row.start_time)} – ${formatClock(row.end_time)}` : "Full day"}</small></div>)}</div> : <div className="empty-inline">No temporary rules.</div>}</section>
      </div>
    </div>
  );
}
