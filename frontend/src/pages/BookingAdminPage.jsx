import { useCallback, useEffect, useState } from "react";
import { api, API, getBusinessId } from "../api";

/**
 * The operator's side of bookings: the diary, services, opening hours, and
 * what no-shows are costing.
 *
 * Customer history is surfaced on the booking itself rather than buried in a
 * report, because the moment it is useful is the moment somebody is deciding
 * whether to ask for a deposit.
 */

const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const TABS = [["diary", "Diary"], ["services", "Services"], ["hours", "Opening hours"], ["noshows", "No-shows"]];

const money = (n) => `$${Number(n || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;

function prettyDate(iso) {
  return new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, {
    weekday: "short", month: "short", day: "numeric",
  });
}

/* ----------------------------------------------------------------- diary */

const STATUS_ACTIONS = [
  ["confirmed", "Confirm"],
  ["completed", "Completed"],
  ["no_show", "No-show"],
  ["cancelled", "Cancel"],
];

function BookingRow({ row, onChanged }) {
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  async function setStatus(status) {
    setBusy(status); setError("");
    try {
      await api(`/booking-admin/bookings/${row.id}/status`, {
        method: "PUT",
        body: JSON.stringify({ status }),
      });
      onChanged();
    } catch (err) { setError(err.message); } finally { setBusy(""); }
  }

  const open = row.status === "pending" || row.status === "confirmed";

  return (
    <div className={`bk-booking status-${row.status}`}>
      <div className="bk-when">
        <strong>{prettyDate(row.date)}</strong>
        <span>{row.time}</span>
        <small>{row.duration_minutes} min</small>
      </div>

      <div className="bk-who">
        <strong>{row.customer_name}</strong>
        <small>{row.service}</small>
        {row.customer_phone && <small className="bk-phone">{row.customer_phone}</small>}
        {row.notes && <p className="bk-notes">{row.notes}</p>}
      </div>

      <div className="bk-meta">
        <span className={`bk-rating r-${row.history.rating}`} title={row.history.suggestion}>
          {row.history.rating === "risky" && `${row.history.no_shows} no-shows`}
          {row.history.rating === "watch" && "1 no-show"}
          {row.history.rating === "reliable" && "Reliable"}
          {row.history.rating === "new" && "First visit"}
        </span>
        {row.price > 0 && <span className="bk-price">{money(row.price)}</span>}
        {row.deposit > 0 && (
          <span className={`bk-deposit d-${row.deposit_status}`}>
            {money(row.deposit)} {row.deposit_status}
          </span>
        )}
      </div>

      <div className="bk-actions">
        {error && <span className="bk-error">{error}</span>}
        {open ? (
          STATUS_ACTIONS.filter(([s]) => s !== row.status).map(([status, label]) => (
            <button
              key={status}
              className={status === "no_show" || status === "cancelled" ? "ghost-btn" : "primary-btn"}
              onClick={() => setStatus(status)}
              disabled={Boolean(busy)}
            >
              {busy === status ? "…" : label}
            </button>
          ))
        ) : (
          <span className={`bk-final f-${row.status}`}>{row.status.replace("_", " ")}</span>
        )}
      </div>
    </div>
  );
}

function Diary() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api("/booking-admin/diary").then(setData).catch((e) => setError(e.message));
  }, []);
  useEffect(() => { load(); }, [load]);

  if (error) return <p className="sec-error">{error}</p>;
  if (!data) return <section className="card os-loading">Loading the diary…</section>;

  const bookingUrl = `${API}/book/${getBusinessId()}`;

  return (
    <>
      <section className="card bk-link-card">
        <h3>Your booking link</h3>
        <p className="bk-note">Share this anywhere — a bio, a QR code on the counter, an email footer.</p>
        <div className="bk-link-row">
          <code>{bookingUrl}</code>
          <button className="ghost-btn" onClick={() => navigator.clipboard?.writeText(bookingUrl)}>Copy</button>
          <a className="ghost-btn" href={bookingUrl} target="_blank" rel="noreferrer">Open</a>
        </div>
      </section>

      {data.at_risk.length > 0 && (
        <div className="alert error bk-risk">
          <strong>{data.at_risk.length} upcoming booking{data.at_risk.length === 1 ? "" : "s"} from customers who have not shown before.</strong>
          {" "}Worth asking for a deposit.
        </div>
      )}

      <div className="bk-stats">
        <div><span>Upcoming</span><strong>{data.upcoming_count}</strong></div>
        <div><span>Committed</span><strong>{money(data.committed_revenue)}</strong></div>
      </div>

      {data.bookings.length === 0 ? (
        <section className="card inv-empty-state">
          <h3>Nothing booked yet</h3>
          <p>Once somebody books through your link, they will show up here with their history attached.</p>
        </section>
      ) : (
        <div className="bk-list">
          {data.bookings.map((row) => <BookingRow key={row.id} row={row} onChanged={load} />)}
        </div>
      )}
    </>
  );
}

/* -------------------------------------------------------------- services */

const BLANK_SERVICE = {
  name: "", description: "", duration_minutes: 30, price: "",
  requires_deposit: false, deposit: "", cancellation_hours: 24,
};

function Services() {
  const [rows, setRows] = useState(null);
  const [form, setForm] = useState(BLANK_SERVICE);
  const [editing, setEditing] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api("/booking-admin/services").then((d) => setRows(d.services)).catch((e) => setError(e.message));
  }, []);
  useEffect(() => { load(); }, [load]);

  async function save(e) {
    e.preventDefault();
    setBusy(true); setError("");
    const payload = {
      name: form.name,
      description: form.description,
      duration_minutes: Number(form.duration_minutes) || 30,
      price: Number(form.price) || 0,
      requires_deposit: form.requires_deposit,
      deposit: Number(form.deposit) || 0,
      cancellation_hours: Number(form.cancellation_hours) || 24,
    };
    try {
      if (editing) {
        await api(`/booking-admin/services/${editing}`, { method: "PUT", body: JSON.stringify(payload) });
      } else {
        await api("/booking-admin/services", { method: "POST", body: JSON.stringify(payload) });
      }
      setForm(BLANK_SERVICE); setEditing(null); load();
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }

  async function archive(id) {
    setError("");
    try {
      await api(`/booking-admin/services/${id}`, { method: "DELETE" });
      load();
    } catch (err) { setError(err.message); }
  }

  if (!rows) return <section className="card os-loading">Loading services…</section>;

  return (
    <>
      <section className="card">
        <h3>{editing ? "Edit service" : "Add a service"}</h3>
        <form className="bk-service-form" onSubmit={save}>
          <div className="bk-field-row">
            <label className="os-field bk-grow">
              <span>Name</span>
              <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </label>
            <label className="os-field">
              <span>Minutes</span>
              <input type="number" min="5" max="600" step="5"
                     value={form.duration_minutes}
                     onChange={(e) => setForm({ ...form, duration_minutes: e.target.value })} />
            </label>
            <label className="os-field">
              <span>Price</span>
              <input type="number" min="0" step="0.01" placeholder="0.00"
                     value={form.price}
                     onChange={(e) => setForm({ ...form, price: e.target.value })} />
            </label>
          </div>

          <label className="os-field">
            <span>Description <em>shown to customers</em></span>
            <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </label>

          <label className="cmp-toggle">
            <input type="checkbox" checked={form.requires_deposit}
                   onChange={(e) => setForm({ ...form, requires_deposit: e.target.checked })} />
            <span>
              <strong>Require a deposit</strong>
              <small>The only thing that reliably stops no-shows on longer slots.</small>
            </span>
          </label>

          {form.requires_deposit && (
            <div className="bk-field-row">
              <label className="os-field">
                <span>Deposit</span>
                <input type="number" min="0" step="0.01" required
                       value={form.deposit}
                       onChange={(e) => setForm({ ...form, deposit: e.target.value })} />
              </label>
              <label className="os-field">
                <span>Free cancellation until</span>
                <input type="number" min="0" max="336"
                       value={form.cancellation_hours}
                       onChange={(e) => setForm({ ...form, cancellation_hours: e.target.value })} />
              </label>
              <span className="bk-hint-inline">hours before the appointment</span>
            </div>
          )}

          {error && <p className="sec-error">{error}</p>}

          <div className="bk-form-actions">
            <button className="primary-btn" disabled={busy || !form.name.trim()}>
              {busy ? "Saving…" : editing ? "Save changes" : "Add service"}
            </button>
            {editing && (
              <button type="button" className="ghost-btn"
                      onClick={() => { setEditing(null); setForm(BLANK_SERVICE); }}>
                Cancel
              </button>
            )}
          </div>
        </form>
      </section>

      {rows.map((s) => (
        <section key={s.id} className="card bk-service">
          <div>
            <strong>{s.name}</strong>
            {s.description && <small>{s.description}</small>}
            <div className="bk-service-meta">
              <span>{s.duration_minutes} min</span>
              {s.price > 0 && <span>{money(s.price)}</span>}
              {s.requires_deposit && <span className="bk-deposit-tag">{money(s.deposit)} deposit</span>}
              <span className="bk-faint">free cancel {s.cancellation_hours}h before</span>
            </div>
          </div>
          <div className="bk-service-actions">
            <button className="ghost-btn" onClick={() => {
              setEditing(s.id);
              setForm({ ...s, price: s.price || "", deposit: s.deposit || "" });
              window.scrollTo({ top: 0, behavior: "smooth" });
            }}>Edit</button>
            <button className="ghost-btn" onClick={() => archive(s.id)}>Archive</button>
          </div>
        </section>
      ))}
    </>
  );
}

/* ----------------------------------------------------------------- hours */

function Hours() {
  const [data, setData] = useState(null);
  const [adding, setAdding] = useState({ day_of_week: 0, start_time: "09:00", end_time: "17:00" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api("/booking-admin/availability").then(setData).catch((e) => setError(e.message));
  }, []);
  useEffect(() => { load(); }, [load]);

  async function add(e) {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      await api("/booking-admin/availability", {
        method: "POST",
        body: JSON.stringify({ ...adding, day_of_week: Number(adding.day_of_week) }),
      });
      load();
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }

  async function remove(id) {
    setError("");
    try {
      await api(`/booking-admin/availability/${id}`, { method: "DELETE" });
      load();
    } catch (err) { setError(err.message); }
  }

  if (!data) return <section className="card os-loading">Loading hours…</section>;

  return (
    <>
      <section className="card">
        <h3>When can people book?</h3>
        <p className="bk-note">
          Slots are only offered inside these windows, so nobody books a time
          you are shut. Overlapping windows on the same day are rejected — they
          would generate the same slot twice.
        </p>
        <form className="bk-hours-form" onSubmit={add}>
          <select value={adding.day_of_week} onChange={(e) => setAdding({ ...adding, day_of_week: e.target.value })}>
            {DAY_NAMES.map((n, i) => <option key={n} value={i}>{n}</option>)}
          </select>
          <input type="time" value={adding.start_time}
                 onChange={(e) => setAdding({ ...adding, start_time: e.target.value })} />
          <span className="bk-to">to</span>
          <input type="time" value={adding.end_time}
                 onChange={(e) => setAdding({ ...adding, end_time: e.target.value })} />
          <button className="primary-btn" disabled={busy}>Add</button>
        </form>
        {error && <p className="sec-error">{error}</p>}
      </section>

      <section className="card">
        <div className="bk-days">
          {data.days.map((d) => (
            <div key={d.day_of_week} className={`bk-day-row${d.windows.length ? "" : " is-closed"}`}>
              <strong>{d.name}</strong>
              {d.windows.length === 0 ? (
                <span className="bk-closed">Closed</span>
              ) : (
                <div className="bk-windows">
                  {d.windows.map((w) => (
                    <span key={w.id} className="bk-window">
                      {w.start_time}–{w.end_time}
                      <button onClick={() => remove(w.id)} aria-label="Remove">×</button>
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </section>
    </>
  );
}

/* -------------------------------------------------------------- no-shows */

function NoShows() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/booking-admin/no-shows").then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="sec-error">{error}</p>;
  if (!data) return <section className="card os-loading">Counting the cost…</section>;

  if (data.no_show_count === 0) {
    return (
      <section className="card inv-empty-state">
        <h3>No no-shows on record</h3>
        <p>Either everyone turns up, or nobody has been marked yet. Mark them in the diary and the cost shows here.</p>
      </section>
    );
  }

  return (
    <>
      <section className="card inv-headline is-leak">
        <div>
          <span className="inv-headline-label">Lost to no-shows</span>
          <strong>{money(data.lost_revenue)}</strong>
          <small>{data.no_show_count} missed over {data.period_days} days · {data.lost_hours} hours of empty slots</small>
        </div>
        <div className="inv-projection">
          <span>No-show rate</span>
          <strong>{data.no_show_rate}%</strong>
        </div>
      </section>

      {data.deposits_recovered > 0 && (
        <section className="card">
          <h3>Deposits recovered</h3>
          <p className="bk-note">
            {money(data.deposits_recovered)} of that was covered by forfeited
            deposits — the difference deposits make, in one number.
          </p>
        </section>
      )}

      {data.repeat_offenders.length > 0 && (
        <section className="card">
          <h3>More than once</h3>
          <p className="bk-note">Ask these customers for a deposit before confirming.</p>
          <table className="os-table">
            <thead><tr><th>Customer</th><th>No-shows</th><th>Value lost</th></tr></thead>
            <tbody>
              {data.repeat_offenders.map((c, i) => (
                <tr key={i}>
                  <td><strong>{c.name}</strong><small>{c.email}</small></td>
                  <td>{c.count}</td>
                  <td className="inv-neg">{money(c.value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </>
  );
}

/* ------------------------------------------------------------------ page */

export default function BookingAdminPage() {
  const [tab, setTab] = useState("diary");

  return (
    <div className="page bk-page">
      <div className="os-heading">
        <div>
          <span className="eyebrow">BOOKINGS</span>
          <h1>Appointments</h1>
          <p>Your diary, what you offer, when you are open, and who does not turn up.</p>
        </div>
      </div>

      <div className="inv-tabs">
        {TABS.map(([id, label]) => (
          <button key={id} className={`inv-tab${tab === id ? " is-active" : ""}`} onClick={() => setTab(id)}>
            {label}
          </button>
        ))}
      </div>

      {tab === "diary" && <Diary />}
      {tab === "services" && <Services />}
      {tab === "hours" && <Hours />}
      {tab === "noshows" && <NoShows />}
    </div>
  );
}
