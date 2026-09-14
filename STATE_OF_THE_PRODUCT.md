# State of the product

*Audited 14 September 2026 against commit `b134a5c`. Every figure below was
measured or probed, not recalled.*

---

## Scale

| | |
|---|---|
| Backend | ~12,000 lines across 24 modules |
| Frontend | 5,693 lines |
| Styling | 3,183 lines |
| **Tests** | **21 files · 278 functions · 405 passing** |
| CI | Full suite + reversed order + frontend build, on every push |
| Migrations | 4 |

The test suite runs in about twelve seconds and is verified order-independent —
forwards, repeated, and with the files deliberately reversed. That reversal is
now a CI step rather than something I remember to do.

---

## 1. The bugs found by testing

This is the part worth reading. **Eleven production bugs surfaced**, plus an entire parallel API that had never been run, and none of
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

### A cancelled customer kept every module
Found while setting up the Stripe test charge, which meant running the webhook
for the first time. It granted and revoked a module key named `"scheduler"`.
There is no such module — the registry calls it `"scheduling"` — so the row it
wrote matched nothing on the way in and nothing on the way out. Probed against
a real seeded workspace:

| | enabled modules | worth |
|---|---|---|
| after `subscription.created` | 13 | $119/mo |
| after `subscription.deleted` | **13** | **$119/mo** |

**A customer cancelled and kept everything, indefinitely.** The paying
direction was equally inert; nobody noticed because a fresh workspace has every
module switched on already, so a payment appeared to work. The same run turned
up duplicate subscription rows on Stripe retries, and a renewal date read from
a field newer API versions moved — yielding 1970.

### Payroll booked withheld tax as cash out of the bank
One payroll run produces three numbers that are not interchangeable: what it
costs the business (gross + employer taxes), what actually leaves the bank
today (net pay), and what is owed to the tax authority (withholding + employer
taxes). The entry was `DR payroll expense / CR cash`, both for the full cost.

On a $10,000 run with $800 employer taxes and $2,000 withheld:

| | the books said | the truth |
|---|---|---|
| cash out of the bank | $10,800 | **$8,000** |
| owed to the authority | **nothing** | $2,800 |

So the business looked $2,800 poorer than it was, exactly when an operator is
deciding whether they can afford something — and when that $2,800 was later
remitted it was expensed a second time. The ledger also disagreed with this
module's own cashflow report, which reads net pay from the payroll record. One
payroll run, two answers. Fixed with a three-line entry and a new
`Payroll Liabilities` account, created on demand for workspaces seeded before
it existed.

### Creating a ledger account returned `{}`
200, empty body. The audit commit expired every attribute and FastAPI
serialised the object after the request's session had closed. The account was
created; the response just said nothing about it, so nothing could select or
display the thing it had just made. One route, found by probing all of them
rather than trusting a scan that flagged five.

### And a 580-line API nothing had ever called
`routers.py` mounted 32 routes — inventory, customers, invoicing, payroll, team
comms, analytics, bookings. Calling each one exactly once:

- **three returned 500 on every call**, written against field names the models
  do not have (`item.quantity` where the column is `quantity_milli`)
- **one returned 200 and silently discarded five of the seven fields it was
  given**, so every item was created with zero stock, zero cost, zero price
- one returned `{}`

And the frontend referenced none of it. Every screen goes through `/platform/*`,
`/ops/*` and `/booking-admin/*`; these duplicated `/platform/invoices`,
`/platform/contacts`, `/platform/inventory` and `/platform/finance/payroll` —
except without posting anything to the ledger. Worse, the broken inventory route
wrote junk rows into the same `InventoryItem` table the working Stock
Intelligence page reads.

Deleted, along with the 351-line `modules/` package it was the only importer of.
**931 lines removed.** `tests/test_api_surface.py` now pins the shape so a
parallel surface cannot come back quietly — and that guard was itself verified
by mounting a rogue `/inventory` router and watching it fail.

**Seven of these eleven were invisible with one tenant, one user, one
workspace, or one customer who never cancelled.** They were all waiting for the
second customer.

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
| **The API surface** | No route under a deleted prefix · every route belongs to a declared surface · no shadowed method+path · one invoicing and one payroll implementation · the public booker and operator diary survived |
| **Payroll** | Cost, cash and liability kept separate · entry balances · ledger agrees with both the payroll record and the cashflow report · remitting does not expense twice · negative and impossible runs refused · cross-tenant payment account refused |
| **The assistant** | Budget shared with the agent · hard ceiling enforced through the real route · a workspace cannot spend its neighbour's allowance · both surfaces on one model |
| **The webhook** | Cancellation actually revokes · retries idempotent · a failed payment does *not* cut anyone off · dunning giving up does · resubscribing restores · tenant boundary held · renewal date read from both API shapes |
| **Email** | Never raises into the caller · HTML escaped against four injection shapes · duplicates blocked by reference |
| **Security** | Login throttling · reset codes (1.1 trillion keyspace, ~3.9M years against the throttle) · auth boundary pinned including near-misses |

---

## 3. Still untested

Honest list. These have **no test referencing them at all**:

| Module | Risk |
|---|---|
| `admin_routes.py` | Platform-admin surface. Small, but it crosses tenant boundaries by design, which is exactly where a mistake is worst. |


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

- **No card has been charged yet.** The handlers are now covered by 20 tests
  and the broken one is fixed, but nothing has been through Stripe Checkout in
  a browser. `STRIPE_TEST_RUNBOOK.md` walks it; it needs a human with a
  dashboard.
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
2. **A real Stripe test payment** — follow `STRIPE_TEST_RUNBOOK.md`. The
   handler side is fixed and covered; what remains is a card through Checkout
   in a browser, which needs a Stripe dashboard and twenty minutes.
3. **Cover `admin_routes.py`** — small, but it crosses tenant boundaries by
   design, which is exactly where a mistake is worst. The last untested
   module.
4. **A support ticket inbox.** Escalations reach your email; there is nowhere
   to work through them.
5. **Give the agent scheduling tools.** `ai_service.py` is not dead code — it
   is the Scheduling AI page, and it does twelve things the agent cannot
   (regenerate a rota, adjust a shift, swap an employee). Merging those into
   `ai_agent.py` as propose/confirm actions would leave one AI surface instead
   of two. Not urgent; both are now budgeted and on the same model.

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
