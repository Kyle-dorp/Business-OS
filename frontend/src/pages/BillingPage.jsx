import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";

/**
 * Billing and modules, on one screen.
 *
 * These belong together: what you switch on *is* what you pay for, and
 * splitting them across two pages means somebody enables four modules in
 * Settings and finds out the price later on an invoice. Here the number moves
 * as they toggle, before anything is saved.
 */

const STATUS_COPY = {
  none: { label: "No subscription", tone: "neutral" },
  trialing: { label: "Trial", tone: "good" },
  active: { label: "Active", tone: "good" },
  past_due: { label: "Payment failed", tone: "warn" },
  incomplete: { label: "Awaiting payment", tone: "warn" },
  canceled: { label: "Cancelled", tone: "bad" },
  incomplete_expired: { label: "Expired", tone: "bad" },
};

function money(cents) {
  return `$${Math.round((cents || 0) / 100).toLocaleString()}`;
}

export default function BillingPage({ onModulesChanged }) {
  const [catalogue, setCatalogue] = useState(null);
  const [quote, setQuote] = useState(null);
  const [draft, setDraft] = useState(null);      // key -> enabled, pre-save
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const [cat, q] = await Promise.all([api("/billing/catalogue"), api("/billing/quote")]);
      setCatalogue(cat);
      setQuote(q);
      setDraft(Object.fromEntries(cat.modules.map((m) => [m.key, m.enabled])));
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const selectedKeys = useMemo(
    () => (draft ? Object.keys(draft).filter((k) => draft[k]) : []),
    [draft]
  );

  const dirty = useMemo(() => {
    if (!catalogue || !draft) return false;
    return catalogue.modules.some((m) => draft[m.key] !== m.enabled);
  }, [catalogue, draft]);

  // Re-price as the operator toggles. The server does the arithmetic so the
  // page can never disagree with the invoice.
  useEffect(() => {
    if (!draft) return undefined;
    let cancelled = false;
    const id = setTimeout(() => {
      api("/billing/preview", {
        method: "POST",
        body: JSON.stringify({ module_keys: selectedKeys }),
      })
        .then((p) => !cancelled && setPreview(p))
        .catch(() => {});
    }, 180);
    return () => { cancelled = true; clearTimeout(id); };
  }, [selectedKeys, draft]);

  function toggle(key, billable) {
    if (!billable) return;   // always-on modules are not negotiable
    setDraft((d) => ({ ...d, [key]: !d[key] }));
    setNotice("");
  }

  async function save() {
    if (!dirty) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const changed = catalogue.modules.filter((m) => draft[m.key] !== m.enabled);
      for (const m of changed) {
        await api(`/platform/modules/${m.key}`, {
          method: "PUT",
          body: JSON.stringify({ enabled: draft[m.key] }),
        });
      }

      // Push the new count at Stripe. Only meaningful once subscribed, and it
      // reports rather than throws when there is no subscription yet.
      let synced = null;
      try {
        synced = await api("/billing/sync", { method: "POST" });
      } catch {
        /* Module changes already saved; a sync failure must not undo them. */
      }

      await load();
      onModulesChanged?.();
      setNotice(
        synced?.synced
          ? "Saved. Your subscription was updated and Stripe will prorate the difference."
          : "Saved."
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function go(endpoint) {
    setBusy(true);
    setError("");
    try {
      const { url } = await api(endpoint, { method: "POST" });
      window.location.href = url;
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  if (error && !catalogue) {
    return <div className="page"><section className="card sec-card"><p className="sec-error">{error}</p></section></div>;
  }
  if (!catalogue || !quote) {
    return <div className="page"><section className="card os-loading">Loading your plan…</section></div>;
  }

  const status = STATUS_COPY[quote.status] || STATUS_COPY.none;
  const shown = preview || quote;
  const billableCount = shown.module_count ?? 0;

  return (
    <div className="page billing-page">
      <div className="os-heading">
        <div>
          <span className="eyebrow">PLAN</span>
          <h1>What you run, and what it costs</h1>
          <p>Switch modules on or off. The price moves before you save.</p>
        </div>
      </div>

      {quote.in_grace && (
        <div className="alert error billing-grace">
          <strong>A payment did not go through.</strong> Everything still works
          while Stripe retries the card. Update it in the billing portal to
          avoid interruption.
        </div>
      )}
      {notice && <div className="alert notice">{notice}</div>}
      {error && <div className="alert error">{error}</div>}

      <div className="billing-layout">
        <section className="billing-modules">
          {catalogue.modules.map((m) => {
            const on = draft[m.key];
            const changed = on !== m.enabled;
            return (
              <button
                key={m.key}
                type="button"
                className={`billing-module${on ? " is-on" : ""}${m.billable ? "" : " is-fixed"}${changed ? " is-changed" : ""}`}
                onClick={() => toggle(m.key, m.billable)}
                aria-pressed={on}
                disabled={!m.billable}
              >
                <span className="bm-check" aria-hidden="true">{on ? "✓" : ""}</span>
                <span className="bm-body">
                  <span className="bm-top">
                    <strong>{m.name}</strong>
                    {m.billable ? (
                      <span className="bm-price">
                        {m.market_price > 0 && <s>${m.market_price}</s>}
                        <em>{on ? "included" : "add"}</em>
                      </span>
                    ) : (
                      <span className="bm-always">always on</span>
                    )}
                  </span>
                  <span className="bm-tagline">{m.tagline}</span>
                  <span className="bm-desc">{m.description}</span>
                  {m.replaces && <span className="bm-replaces">Replaces {m.replaces}</span>}
                </span>
              </button>
            );
          })}
        </section>

        <aside className="billing-summary">
          <div className="card bs-card">
            <div className={`bs-status tone-${status.tone}`}>{status.label}</div>

            <div className="bs-price">
              <span className="bs-amount">{money(shown.monthly_cents)}</span>
              <span className="bs-per">/month</span>
            </div>
            <p className="bs-breakdown">
              {billableCount === 0
                ? "No billable modules selected."
                : `${billableCount} module${billableCount === 1 ? "" : "s"} — ` +
                  `${money(catalogue.first_module_cents)} for the first, ` +
                  `${money(catalogue.each_additional_cents)} each after.`}
            </p>

            {shown.stitched_cents > 0 && (
              <div className="bs-compare">
                <div>
                  <span>Bought separately</span>
                  <s>{money(shown.stitched_cents)}</s>
                </div>
                {shown.saving_cents > 0 && (
                  <div className="bs-saving">
                    <span>You keep</span>
                    <strong>{money(shown.saving_cents)}/mo</strong>
                  </div>
                )}
              </div>
            )}

            {dirty && (
              <div className="bs-actions">
                <button className="primary-btn" onClick={save} disabled={saving}>
                  {saving ? "Saving…" : "Save changes"}
                </button>
                <button
                  className="ghost-btn"
                  onClick={() => setDraft(Object.fromEntries(catalogue.modules.map((m) => [m.key, m.enabled])))}
                  disabled={saving}
                >
                  Reset
                </button>
              </div>
            )}

            {!dirty && (
              <div className="bs-actions">
                {quote.needs_subscription ? (
                  <button
                    className="primary-btn"
                    onClick={() => go("/billing/checkout")}
                    disabled={busy || billableCount === 0}
                  >
                    {busy ? "Opening…" : "Start subscription"}
                  </button>
                ) : (
                  <button className="ghost-btn" onClick={() => go("/billing/portal")} disabled={busy}>
                    {busy ? "Opening…" : "Manage billing"}
                  </button>
                )}
              </div>
            )}

            {quote.current_period_end && (
              <p className="bs-renews">Renews {String(quote.current_period_end).slice(0, 10)}</p>
            )}

            <p className="bs-fine">
              Unlimited users and every location, on every plan. The assistant is
              included with an allowance; heavy use is metered.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
