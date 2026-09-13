# State of the product

*Audited 12 September 2026, against commit `e64461f`. Everything below was
verified by reading the code or probing the deployed API — nothing is assumed.*

---

## 1. What is built and working

### The three things nothing else on the market does

**Preflight** — `/ops/preflight/{schedule_id}`, with a UI.
Before a schedule publishes, four questions answered in one call: is it legal,
is it staffed for bookings actually taken, is it affordable against forecast
revenue, will the ingredients last. Verdict comes back as one word — publish,
review, or fix.

Deputy answers the first. A POS approximates the third. Nothing answers all
four, because it needs the schedule, the calendar, the ledger and the stockroom
in one database. **This is the demo.**

**The conversational agent** — `/agent/chat`, with a UI.
Ask in plain language, get answers computed from real records. Ask it to change
something and a proposal card appears with Approve / Discard. Every applied
change is written to `AuditEvent` with the prompt that produced it.

The boundary is deliberate and worth selling: the agent reads customer notes,
invoice memos and item descriptions — text other people wrote. If that text
could trigger a write, the ledger is one clever sentence from being wrong.

**Inventory variance** — `/ops/inventory/variance`, backend only.
Recipes turn sales into theoretical usage. Subtract logged waste, compare
against a physical count, and what remains is unexplained shrinkage in dollars,
ranked worst-first, with an annualised projection. A standalone tool cannot do
this — it sees stock fall with no idea what should have been consumed.

### Labor compliance — `compliance.py`, surfaced through Preflight

Federal FLSA plus eleven jurisdictions:

- **Fair Workweek** advance notice for NYC, Seattle, Chicago, Philadelphia,
  Oregon, SF — 14 days each
- **Clopening** rest gaps with the real premium (NYC $100 flat, Seattle
  time-and-a-half, Philadelphia $40)
- **California** daily overtime past 8 and double time past 12
- **Minors** — school-week vs non-school-week caps, 7am floor, and the curfew
  that shifts 7pm → 9pm between June and Labor Day
- **Day-of-rest** statutes in CA, NY, IL
- Ordinances gate on headcount and industry, so a 20-person Seattle café is not
  warned about a rule that only bites above 500 employees

Every finding carries its legal citation and a dollar exposure.

### Billing — complete backend, no UI yet

$29 first module + $10 each after, as two Stripe line items, plus metered
assistant overage via Billing Meters. `/billing/sync` pushes module count onto
the live subscription and Stripe prorates.

### Public booking — complete backend, no UI yet

Real slot generation from weekly availability, one-hour lead time, and
availability **re-checked inside the booking transaction** so two people cannot
take one slot. A booking from a new email also creates a CRM contact.

### The installable app

PWA with home-screen install, app shortcuts, and a service worker that
deliberately caches **no business data** — shared devices are normal in this
market.

### The look

Warm near-black ground, ambient light pooling from three sources, film grain.
Nav items invisible until approached, then they warm and mark themselves.
Fraunces for headlines, Figtree for everything else.

Colour has one job each: **amber** = interaction, **rose** = money leaving,
**mint** = money kept. That discipline is what stops a glow-heavy interface
becoming a fairground.

---

## 2. Broken or fixed today

| Issue | Status |
|---|---|
| **Frontend build failed on every deploy** — Button/Card exported default, seven pages imported named | Fixed `d5f95ce` |
| **Pages passed `icon`/`loading`/`hoverable` props the components never declared** | Implemented properly, not stubbed |
| **Stripe webhook returned 401 to every event** — `/billing/webhook` was never in `PUBLIC_PATHS`, so subscriptions would have gone through checkout and never activated | Fixed `59f0fd1` |
| **Public booking returned 401** — customers are not users; a booking link was unusable | Fixed `59f0fd1` |
| **Site served the old design** — `import App from './App'` with both `.jsx` and `.tsx` present; Vite resolves `.jsx` first, so every build compiled the wrong app | Fixed `e64461f` |
| **Fonts never loaded** — theme named Fraunces and Figtree, nothing fetched them, so it would have silently rendered as Georgia + system sans | Fixed `e64461f` |
| **Webhook path wrong in my own handoff** — I wrote `/webhooks/stripe`; the route is `/billing/webhook` | Corrected |
| **Migration listed as a task it never was** — `create_db_and_tables()` runs on startup | Corrected |

### Known-good, verified live

`/health` returns `ai_configured: true`, no startup errors, Postgres connected,
and all new routes present in the deployed OpenAPI schema.

---

## 3. Built but invisible — backend with no UI

These work if you curl them. A customer cannot reach any of them.

| Endpoint | What is missing |
|---|---|
| `/billing/quote`, `/preview`, `/checkout`, `/portal`, `/sync` | **The entire billing screen.** Nobody can subscribe from inside the app. |
| `/public/book/{id}` and friends | **The booking page.** The backend takes bookings; there is no page to take them on. |
| `/ops/inventory/variance` | The shrinkage report — arguably your strongest single feature — has no screen. |
| `/ops/inventory/menu-engineering` | Recipe margin ranking, no screen. |
| `/ops/inventory/count` | No way to submit a physical count, which means variance has nothing to measure against. |
| `/ops/compliance/profile` | No settings UI, so every workspace defaults to federal-only rules. **Jurisdiction rules do nothing until this exists.** |
| `/agent/support/tickets` | Tickets are created and nothing notifies you. |

**The two that matter most: billing and the compliance profile.** Without
billing you cannot take money inside the product. Without the profile picker,
the compliance engine — the thing that beats Deputy — runs in federal-only mode
for everyone and most of its value is dormant.

---

## 4. Completely missing

- **Notification on escalation.** `SupportTicket` rows pile up silently. Needs
  an email or SMS provider — Resend or Postmark for email, Twilio for SMS.
- **Recipe builder.** `Recipe` and `RecipeComponent` tables exist; there is no
  way to create one. Variance and menu engineering both depend on recipes, so
  both are inert until this exists.
- **Employee compliance data.** Date of birth and hourly rate live in
  `EmployeeCompliance` with no UI. Without DOB the minor rules never fire;
  without rates every exposure figure is $0.
- **Booking deposits and no-show protection.** Acuity has these; you do not.
- **AR auto-chase.** Invoices do not chase themselves.
- **Password reset.** There is no recovery flow. A locked-out owner needs you.
- **Email anywhere.** No invoice send, no booking confirmation, no receipt.
- **Onboarding.** A new workspace lands on an empty dashboard with no guidance.
- **Rate limiting on auth.** Login has no brute-force protection. Cloudflare
  will cover some of this; it is not a substitute.
- **Automated tests for the API.** `test_compliance.py` and
  `test_auth_boundary.py` cover rules and the auth boundary. The endpoints
  themselves have none.

---

## 5. Dead code to delete

Twelve orphan pages and two orphan components, none reachable from `App.jsx`:

```
pages/AdminDashboard.tsx   pages/AdminPanel.tsx    pages/Analytics.tsx
pages/CalendarPage.jsx     pages/Customers.tsx     pages/Dashboard.tsx
pages/HomePage.jsx         pages/Inventory.tsx     pages/Invoicing.tsx
pages/Login.tsx            pages/Payroll.tsx       pages/TeamChat.tsx
components/ChatBubble.tsx  components/Sidebar.tsx
```

These are the remains of the parallel `.tsx` shell. **They are the same dead
code that broke every build for weeks** — they still compile, so they are not
urgent, but they are a trap: the next person to touch them will not know which
app they belong to. Say the word and they go.

---

## 6. What I would do next, in order

1. **Billing screen.** You cannot charge anyone from inside the product. The
   backend is done; this is a single page against `/billing/preview` and
   `/billing/checkout`.
2. **Compliance profile picker.** One dropdown that turns the whole labor
   engine on. Highest value per line of code in the entire codebase.
3. **Booking page.** Your own module, replacing the third-party scheduler on
   the landing page, and usable for your own demo calls.
4. **Recipe builder + count entry.** Turns variance from a dormant endpoint
   into the number that closes sales.
5. **Escalation notification.** Tickets that reach your phone.
6. **Password reset and transactional email.** Unglamorous, and the first thing
   a real customer will hit.

---

## 7. Honest assessment

The backend is genuinely ahead of anything at this price point. Preflight and
the variance engine are real competitive moats — not marketing, structural
advantages a single-purpose competitor cannot copy without rebuilding as a
platform.

**The frontend is roughly 40% of the way there.** Two excellent new screens sit
on top of an app whose other pages have not been touched since the restyle —
they inherit the new tokens and look consistent, but they were not designed
against this language.

**The gap between "impressive backend" and "shippable product" is the billing
screen and the compliance profile picker.** Those two are the difference
between a demo that stuns people and a thing that takes money.

Nothing here is blocked. Nothing needs rearchitecting. It needs UI for what is
already built.
