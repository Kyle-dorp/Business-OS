# State of the product

*Audited 14 September 2026 against commit `b6c4b1c`. Every figure below was
measured or probed, not recalled.*

---

## Scale

| | |
|---|---|
| Backend | 12,901 lines across 26 modules |
| Frontend | 5,693 lines |
| Styling | 3,183 lines |
| **Tests** | **3,738 lines · 17 files · 203 functions · 330 passing** |
| CI | Full suite + reversed order + frontend build, on every push |
| Migrations | 4 |

The test suite runs in about twelve seconds and is verified order-independent —
forwards, repeated, and with the files deliberately reversed. That reversal is
now a CI step rather than something I remember to do.

---

## 1. The bugs found by testing

This is the part worth reading. **Eight production bugs surfaced**, and none of
them were found by looking at the code — every one came from running something.

### Every signup produced an unusable workspace
`/auth/setup` created the user, business and membership but never called
`seed_business`. Every account made through normal signup had **no chart of
accounts**, no location and no module rows: a business that could not post a
journal entry or issue an invoice from its first second. `/platform/bootstrap`
could not repair it, because its guard sees the membership, concludes the
workspace is set up, and returns.

Two tests had been failing on exactly this for some time. Nobody had run them.

### Booking gated on a module key that could not exist
`booking_public` checked for `module_key == "booking"`, but `"booking"` was not
in `platform.MODULES`, and the module endpoint rejects anything that is not. No
such row could ever be created, so **every booking page would have 404'd
forever.** A feature built, shipped, deployed and structurally unreachable.

### The booking page only worked for business #1
`Service`, `Booking` and `BookingAvailability` are tenant-scoped, so their
queries filter by `current_business_id()`. Public requests carry no workspace
header, leaving it at its default of 1. **Invisible with a single tenant**; it
would have surfaced as your second customer's link simply not working.

### The Stripe webhook returned 401 to every event
`/billing/webhook` was never in the public paths. A customer would have
completed checkout, been charged, and had their subscription never activate.

### An auth bypass on any path starting with `/docs`
`"/docs"` was a public *prefix*, so `/docsomething` and `/docs-internal`
bypassed authentication entirely. My own near-miss test caught it — written
three phases earlier and never executed until this session.

### The variance formula was wrong by 7×
Unexplained loss was computed as `(counted − expected) + logged waste`. Waste
had already been deducted, so it was counted twice; and what sales consumed was
never subtracted at all. A bar missing **1.5L of gin ($45)** was reported as
11L — **$330**. Wrong in the direction that makes an honest business look like
it is being robbed, which sends an operator hunting a thief who does not exist.

### Two module registries that disagreed
Billing validated against a set of modules the product did not have, while the
ones it did have went unbilled. The first subscription would have priced the
wrong things.

### A malformed time took down a whole week of scheduling
`parse_time` raised on any string without a colon — one row holding `"9"`
instead of `"09:00"` failed generation entirely. It also read `"25:00"` as 1500
minutes, which is worse: nothing failed, and the solver produced a rota that
was quietly wrong.

**Five of these eight were invisible with one tenant, one user, or one
workspace.** They were all waiting for the second customer.

---

## 2. What is verified working

Not "written" — **exercised against real code and real data.**

| Area | Coverage |
|---|---|
| **Ledger** | Debits equal credits · trial balance balances · accounting equation holds · unbalanced entries refused · cross-business account references refused · drafts excluded · closing date inclusive |
| **Scheduler** | Real OR-Tools solve · coverage rules filled · **unavailable staff never rostered** · holidays respected · nobody double-booked · deterministic · uncoverable rules reported by name |
| **Public booking** | Double-booking race held · overlapping slots blocked · tenant boundary on service ids · cancellation releases the slot · no field leakage |
| **The agent** | Cross-tenant confirm blocked · `business_id` smuggling filtered · double-confirm refused · every applied change audited with its prompt |
| **OAuth** | Audience check · issuer check · unverified email refused · empty `aud` cannot match an unset client id |
| **Compliance** | Eleven jurisdictions · every premium pinned · a bad week in NYC surfaces $145 before publishing |
| **Billing** | Ladder checked 0→10 modules · every multi-module stack cheaper than buying separately |
| **Email** | Never raises into the caller · HTML escaped against four injection shapes · duplicates blocked by reference |
| **Security** | Login throttling · reset codes (1.1 trillion keyspace, ~3.9M years against the throttle) · auth boundary pinned including near-misses |

---

## 3. Still untested

Honest list. These have **no test referencing them at all**:

| Module | Risk |
|---|---|
| `finance.py` | **Highest.** Budgets, cashflow and payroll routes. The accounting *core* in `platform.py` is well covered, but these seven endpoints are not — and payroll touches money. |
| `stripe_service.py` | Webhook handlers. Hard to test without Stripe fixtures; a bug means a subscription state that silently diverges from what Stripe believes. |
| `routers.py` | The module CRUD routers — inventory, customers, invoicing, payroll, team, analytics. Mostly thin, but large. |
| `admin_routes.py` | Platform-admin surface. Small, but it crosses tenant boundaries by design, which is exactly where a mistake is worst. |
| `ai_service.py` | The older scheduling assistant, largely superseded by `ai_agent.py`. Possibly worth deleting rather than testing. |

---

## 4. Built but not reachable

Down to two, from seven at the last audit:

- **`/agent/support/tickets`** — tickets are created and emailed, but there is
  no inbox screen to read or resolve them in.
- **`/billing/report-ai-usage`** — called internally when usage passes the
  allowance; no operator-facing view of it.

Everything else built now has a screen.

---

## 5. Genuinely missing

- **No test of a real Stripe payment.** Nothing has charged a card. The flow is
  built and unexercised end to end.
- **No onboarding.** A new workspace lands on an empty dashboard with no
  guidance. It now at least has a working chart of accounts.
- **No frontend tests.** The build is type-checked on every push, but nothing
  exercises a component.
- **No rate limiting beyond login.** Cloudflare will absorb volume; the agent
  endpoint has its own budget caps.
- **No accessibility pass.** Keyboard access was added to clickable cards ad
  hoc, never audited.

---

## 6. What I would do next, in order

1. ~~**Put the suite in CI.**~~ Done — `.github/workflows/tests.yml` runs the
   full suite on every push and pull request, then runs it again with the test
   files reversed, and type-checks and builds the frontend. Both were verified
   green locally before being committed. Everything in section 1 was found by
   running tests that already existed; now a push runs them.
2. **A real Stripe test payment**, in test mode, end to end — checkout through
   webhook to an active subscription. It is the one revenue path never
   exercised.
3. **Cover `finance.py`**, especially payroll.
4. **A support ticket inbox.** Escalations reach your email; there is nowhere
   to work through them.
5. **Delete `ai_service.py`** if `ai_agent.py` has genuinely replaced it.

---

## 7. Honest assessment

The backend is in materially better shape than at the last audit, and the
reason is specific: **the test suite is now the thing finding bugs, rather than
a customer.** Eight production faults, five of which only appear with more than
one tenant or user — the exact class that a solo developer with one test
workspace never sees.

The product's differentiators are real and now verified rather than asserted.
Preflight genuinely answers four questions no competitor answers together. The
variance engine genuinely computes a number a standalone tool cannot. The
compliance engine genuinely covers eleven jurisdictions with citations.

**What it is not yet:** proven against a real customer, a real payment, or a
second tenant in production. Everything above says the code is correct. None of
it says the business works.

The gap between here and a paying customer is no longer engineering. It is
Cloudflare, a domain, a Stripe test charge, and somebody to sell it to.
