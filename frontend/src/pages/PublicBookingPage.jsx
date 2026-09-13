import { useEffect, useMemo, useState } from "react";
import { API } from "../api";

/**
 * The page a customer sees.
 *
 * Rendered before any authentication, because the person using it is not a
 * user and never will be. It calls /public/book/* directly rather than through
 * the api() helper, which attaches a bearer token and a workspace header that
 * do not exist here.
 *
 * Three screens, one at a time: pick a service, pick a time, leave details.
 * A booking form that shows everything at once is how people abandon halfway.
 */

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

async function publicGet(path) {
  const res = await fetch(`${API}${path}`);
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(data?.detail || "Something went wrong.");
  return data;
}

async function publicPost(path, body) {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(data?.detail || "Something went wrong.");
  return data;
}

function money(n) {
  return `$${Number(n || 0).toFixed(2).replace(/\.00$/, "")}`;
}

function prettyDate(iso) {
  const d = new Date(`${iso}T12:00:00`);
  return d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

function prettyTime(hhmm) {
  const [h, m] = hhmm.split(":").map(Number);
  const period = h >= 12 ? "pm" : "am";
  const hour = h % 12 === 0 ? 12 : h % 12;
  return m === 0 ? `${hour}${period}` : `${hour}:${String(m).padStart(2, "0")}${period}`;
}

export default function PublicBookingPage({ businessId }) {
  const [page, setPage] = useState(null);
  const [fatal, setFatal] = useState("");

  const [service, setService] = useState(null);
  const [day, setDay] = useState(null);
  const [slots, setSlots] = useState(null);
  const [time, setTime] = useState(null);

  const [details, setDetails] = useState({ customer_name: "", customer_email: "", customer_phone: "", notes: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirmed, setConfirmed] = useState(null);

  useEffect(() => {
    publicGet(`/public/book/${businessId}`)
      .then(setPage)
      .catch((e) => setFatal(e.message));
  }, [businessId]);

  // Only offer days the business is actually open, so nobody picks a date and
  // is told nothing is free.
  const days = useMemo(() => {
    if (!page) return [];
    const out = [];
    const openDays = new Set(page.open_days);
    for (let i = 0; i < Math.min(page.max_days_ahead, 28); i += 1) {
      const d = new Date();
      d.setDate(d.getDate() + i);
      if (openDays.has((d.getDay() + 6) % 7)) {
        out.push(d.toISOString().slice(0, 10));
      }
    }
    return out;
  }, [page]);

  useEffect(() => {
    if (!service || !day) return undefined;
    let cancelled = false;
    setSlots(null);
    setTime(null);
    publicGet(`/public/book/${businessId}/slots?service_id=${service.id}&on=${day}`)
      .then((r) => !cancelled && setSlots(r.slots))
      .catch((e) => !cancelled && setError(e.message));
    return () => { cancelled = true; };
  }, [service, day, businessId]);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await publicPost(`/public/book/${businessId}/book`, {
        service_id: service.id,
        booking_date: day,
        booking_time: time,
        ...details,
      });
      setConfirmed(result);
    } catch (err) {
      setError(err.message);
      // The slot may have gone while they were typing. Refresh so the list
      // they are looking at is true.
      if (/just taken/i.test(err.message)) {
        publicGet(`/public/book/${businessId}/slots?service_id=${service.id}&on=${day}`)
          .then((r) => { setSlots(r.slots); setTime(null); })
          .catch(() => {});
      }
    } finally {
      setBusy(false);
    }
  }

  if (fatal) {
    return (
      <main className="pb-screen">
        <section className="pb-card pb-message">
          <h1>Not available</h1>
          <p>{fatal}</p>
        </section>
      </main>
    );
  }

  if (!page) {
    return <main className="pb-screen"><section className="pb-card os-loading">Loading…</section></main>;
  }

  if (confirmed) {
    return (
      <main className="pb-screen">
        <section className="pb-card pb-confirmed">
          <div className="pb-tick" aria-hidden="true">✓</div>
          <h1>You&rsquo;re booked</h1>
          <p className="pb-confirm-line">
            <strong>{confirmed.service}</strong> at {page.business_name}
          </p>
          <div className="pb-confirm-when">
            {prettyDate(confirmed.booking_date)} at {prettyTime(confirmed.booking_time)}
          </div>

          <dl className="pb-summary">
            <div><dt>Length</dt><dd>{confirmed.duration_minutes} minutes</dd></div>
            {confirmed.price > 0 && <div><dt>Price</dt><dd>{money(confirmed.price)}</dd></div>}
            {confirmed.deposit_required && (
              <div><dt>Deposit</dt><dd>{money(confirmed.deposit)} due</dd></div>
            )}
          </dl>

          {confirmed.deposit_required && (
            <p className="pb-deposit-note">
              This booking holds your slot. A {money(confirmed.deposit)} deposit is
              due, and is not refundable if you cancel within {confirmed.cancellation_hours} hours.
            </p>
          )}
          <p className="pb-fine">
            Need to change it? Reply to your confirmation or call {page.business_name}.
            Free cancellation up to {confirmed.cancellation_hours} hours before.
          </p>
        </section>
      </main>
    );
  }

  const step = !service ? 1 : !time ? 2 : 3;

  return (
    <main className="pb-screen">
      <header className="pb-header">
        <h1>{page.business_name}</h1>
        <p>Book an appointment</p>
        <ol className="pb-steps" aria-label="Progress">
          {["Service", "Time", "Details"].map((label, i) => (
            <li key={label} className={step > i + 1 ? "is-done" : step === i + 1 ? "is-current" : ""}>
              <span>{label}</span>
            </li>
          ))}
        </ol>
      </header>

      {error && <div className="pb-card alert error">{error}</div>}

      {step === 1 && (
        <section className="pb-card">
          <h2>What do you need?</h2>
          {page.services.length === 0 ? (
            <p className="pb-empty">Nothing is bookable online just now.</p>
          ) : (
            <div className="pb-services">
              {page.services.map((s) => (
                <button key={s.id} className="pb-service" onClick={() => setService(s)}>
                  <span className="pb-service-main">
                    <strong>{s.name}</strong>
                    {s.description && <small>{s.description}</small>}
                  </span>
                  <span className="pb-service-meta">
                    <span className="pb-duration">{s.duration_minutes} min</span>
                    {s.price > 0 && <span className="pb-price">{money(s.price)}</span>}
                    {s.requires_deposit && (
                      <span className="pb-deposit-tag">{money(s.deposit)} deposit</span>
                    )}
                  </span>
                </button>
              ))}
            </div>
          )}
        </section>
      )}

      {step === 2 && (
        <section className="pb-card">
          <button className="pb-back" onClick={() => { setService(null); setDay(null); }}>
            ← {service.name}
          </button>
          <h2>When suits?</h2>

          <div className="pb-days">
            {days.map((d) => {
              const dt = new Date(`${d}T12:00:00`);
              return (
                <button
                  key={d}
                  className={`pb-day${day === d ? " is-active" : ""}`}
                  onClick={() => setDay(d)}
                >
                  <small>{DAY_NAMES[(dt.getDay() + 6) % 7]}</small>
                  <strong>{dt.getDate()}</strong>
                </button>
              );
            })}
          </div>

          {!day && <p className="pb-hint">Pick a day to see available times.</p>}
          {day && slots === null && <p className="pb-hint">Finding times…</p>}
          {day && slots?.length === 0 && (
            <p className="pb-hint">Nothing free on {prettyDate(day)}. Try another day.</p>
          )}
          {day && slots?.length > 0 && (
            <div className="pb-slots">
              {slots.map((t) => (
                <button key={t} className="pb-slot" onClick={() => setTime(t)}>
                  {prettyTime(t)}
                </button>
              ))}
            </div>
          )}
        </section>
      )}

      {step === 3 && (
        <section className="pb-card">
          <button className="pb-back" onClick={() => setTime(null)}>
            ← {prettyDate(day)} at {prettyTime(time)}
          </button>
          <h2>Your details</h2>

          <form className="pb-form" onSubmit={submit}>
            <label className="field-label">
              Name
              <input
                required autoFocus autoComplete="name"
                value={details.customer_name}
                onChange={(e) => setDetails({ ...details, customer_name: e.target.value })}
              />
            </label>
            <label className="field-label">
              Email
              <input
                required type="email" autoComplete="email"
                value={details.customer_email}
                onChange={(e) => setDetails({ ...details, customer_email: e.target.value })}
              />
            </label>
            <label className="field-label">
              Phone <span className="pb-optional">optional</span>
              <input
                type="tel" autoComplete="tel"
                value={details.customer_phone}
                onChange={(e) => setDetails({ ...details, customer_phone: e.target.value })}
              />
            </label>
            <label className="field-label">
              Anything we should know? <span className="pb-optional">optional</span>
              <textarea
                rows={3}
                value={details.notes}
                onChange={(e) => setDetails({ ...details, notes: e.target.value })}
              />
            </label>

            {service.requires_deposit && (
              <div className="pb-deposit-warn">
                A {money(service.deposit)} deposit is required, and is not
                refundable if you cancel within {service.cancellation_hours} hours.
              </div>
            )}

            <button className="primary-btn pb-submit" disabled={busy}>
              {busy ? "Booking…" : `Confirm ${prettyDate(day)} at ${prettyTime(time)}`}
            </button>
          </form>
        </section>
      )}

      <footer className="pb-footer">Powered by Business-EOS</footer>
    </main>
  );
}
