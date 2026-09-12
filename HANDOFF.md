# Handoff — what's built, what needs you

Everything below is written, compiles, and is wired into `main.py`. What remains
is the set of things only you can do: keys, Stripe objects, DNS, and a few
judgement calls.

---

## What needs your input

### 1. Rotate three keys (do this first)

All three were pasted into a chat, which means they're in history and should be
treated as burned. None of them were ever written into code — every file reads
from the environment.

| Key | Where | Action |
|---|---|---|
| `sk_live_51U6eJz...` | Stripe → Developers → API keys | **Roll** |
| `apikey_01Jhae...` | Anthropic Console → API keys | **Delete, create new** |
| `sk-ant-api03-kJas...` | Anthropic Console → API keys | **Delete, create new** |

The publishable key (`pk_live_...`) is fine — it's meant to be public.

### 2. Create three Stripe prices

Product catalogue → Add product. Recurring, monthly, each one.

| Product | Price | Type | Env var |
|---|---|---|---|
| Business-EOS base | **$29.00** | Standard | `STRIPE_PRICE_BASE` |
| Additional module | **$10.00** | Standard, per-unit | `STRIPE_PRICE_MODULE` |
| Assistant overage | **$0.02** | **Usage-based (metered)**, per unit = 1,000 tokens | `STRIPE_PRICE_AI_OVERAGE` |

The subscription carries base × 1 + module × (count − 1). One module = $29, six = $79, ten = $119.

### 3. Webhook endpoint

Developers → Webhooks → Add endpoint → `https://<api-domain>/webhooks/stripe`

Events: `checkout.session.completed`, `customer.subscription.created`,
`customer.subscription.updated`, `customer.subscription.deleted`,
`invoice.payment_failed`

Copy the signing secret → `STRIPE_WEBHOOK_SECRET`.

> The existing `stripe_service.handle_webhook_event` already handles these. I did
> **not** add a second webhook route — two handlers for the same events is how you
> get double-charges and phantom state.

### 4. Railway env vars

**API service**
```
STRIPE_SECRET_KEY=sk_live_...        (the NEW one)
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_BASE=price_...
STRIPE_PRICE_MODULE=price_...
STRIPE_PRICE_AI_OVERAGE=price_...
APP_URL=https://<your-frontend-domain>

ANTHROPIC_API_KEY=sk-ant-...         (the NEW one)
ANTHROPIC_MODEL=claude-sonnet-5
```

Optional tuning — sensible defaults are compiled in:
```
AI_MONTHLY_INPUT_TOKENS=500000
AI_MONTHLY_OUTPUT_TOKENS=150000
AI_MESSAGES_PER_HOUR=40
AI_OVERAGE_CENTS_PER_1K=2
AI_HARD_CEILING_MULTIPLIER=5
```

### 5. Migration

Three new tables: `agentproposal`, `supportticket`, `agentthread`.

```bash
alembic revision --autogenerate -m "agent proposals, support tickets, threads"
alembic upgrade head
```

### 6. Two PNG icons

`frontend/public/icons/` has `icon.svg`. Export it at 192×192 and 512×512 as
`icon-192.png`, `icon-512.png`, plus `maskable-512.png` (same art, ~20% padding
so Android's circle mask doesn't crop it). Without these the app installs with a
generic icon.

### 7. Decisions I couldn't make for you

- **Contact email.** The landing page uses `hello@business-eos.com` as a placeholder.
  I deliberately did not hardcode your personal Gmail into a public page — that's
  hard to undo once indexed. Swap it for whatever you'll actually read.
- **Domain.** Needed before Cloudflare and before Stripe redirect URLs are real.
- **Overage rate.** I set $0.02 per 1,000 tokens. Sonnet costs you roughly $0.006
  blended, so that's about a 3× markup. Raise or lower it in `AI_OVERAGE_CENTS_PER_1K`.

---

## What got built

### `backend/app/ai_agent.py` — the conversational agent

The differentiator. Ask questions in plain language, get answers computed from real
records. Tools: `get_metrics`, `search_records`, `get_record`, `propose_change`,
`escalate_to_human`.

**Two design decisions worth understanding:**

**Every tool is bound to the caller's workspace at the query, not filtered afterwards.**
The agent has no way to express "some other business", so cross-tenant leakage isn't a
bug someone can introduce later.

**The agent never writes.** Write requests become `AgentProposal` rows that a human
confirms. This is not caution for its own sake: the agent reads customer notes, invoice
memos and item descriptions — text other people wrote. If that text could trigger a
write, your ledger is one clever sentence away from being wrong. Proposals show exactly
what will change, confirmation runs the same permission checks a human click would, and
every applied change lands in `AuditEvent` with the prompt that produced it.

Endpoints: `POST /agent/chat`, `POST /agent/proposals/{id}/confirm`,
`POST /agent/proposals/{id}/reject`, `GET /agent/usage`, `GET /agent/support/tickets`

### `backend/app/billing.py` — module-count subscriptions

$29 + $10/module as two Stripe line items, plus metered assistant overage. `POST
/billing/sync` pushes the current module count onto the live subscription and Stripe
prorates, so switching a module on mid-month charges only the remaining days.

`POST /billing/preview` prices a hypothetical module set without changing anything —
that's what the in-app module picker calls as someone toggles things.

### `backend/app/booking_public.py` — public booking

Unauthenticated, because customers aren't users. Real slot generation that walks weekly
availability, subtracts booked time, and honours a one-hour lead time. Availability is
**re-checked inside the booking request**, not trusted from the browser — between
rendering a page and clicking confirm, someone else may have taken the slot.

A booking with a new email also creates a CRM contact, so the modules actually connect.

Endpoints: `GET /public/book/{business_id}`, `/slots`, `/next-available`,
`POST /public/book/{business_id}/book`, `/cancel/{booking_id}`

This is also what replaces Cal.com for your own demo scheduling. You were right —
selling a booking tool and then sending prospects to a competitor's is indefensible.

### Installable app (PWA)

`manifest.webmanifest`, `sw.js`, `offline.html`, `icon.svg`, and the registration in
`index.html`. Installs to a phone home screen or a desktop dock with app shortcuts
for schedule, assistant and new invoice.

**The service worker deliberately caches no business data.** A POS tablet or a
manager's phone is often a shared device; invoices, payroll and customer records never
touch the cache. Only the app shell and static assets, so it opens instantly and
degrades to a readable offline screen instead of a browser error.

Registration is skipped on localhost — a cached shell fighting the dev server produces
confusing stale reloads.

### Landing page

Section 04 is now the assistant, shown as a real conversation ending in a proposal card
awaiting approval. The "it proposes, you approve" boundary is sold as the trust feature
it is. Contact points at `/book` — your own module.

---

## Two things I corrected mid-build

**I wrote code against a schema I'd assumed rather than read.** My first pass at
`billing.py` and an `ai_chat.py` imported `require_business`, `require_role` and
`require_user` from `tenancy.py`. None of those exist — tenancy here is context-var
based and auth is `user_from_request`. Both files were rewritten against the real
thing, and `ai_chat.py` was deleted rather than left as a second half-working chat
endpoint.

**My metrics tool used invented field names.** I had `invoice.total`,
`payment.amount`, `inventory.quantity_on_hand`. The real schema stores money as
integer cents (`total_cents`, `amount_cents`) and stock in thousandths
(`quantity_milli`, `reorder_level_milli`) — which is the correct design, no float
money. Fixed, and the serializer now hands the model both forms so it quotes "$1,240"
instead of "124000".

Also added `email-validator` to `requirements.txt` — `EmailStr` in the booking schema
needs it, and it would have failed at deploy rather than at compile.

---

## What I'd do next, in order

1. **Frontend for the agent** — chat panel with proposal cards. The backend is the hard
   part and it's done; the UI is the part customers actually touch.
2. **Booking page UI** — public page against `/public/book/*`, in the warm-glow language.
3. **Billing screen** — module picker calling `/billing/preview` live, then checkout.
4. **Notification on escalation** — `SupportTicket` rows exist but nothing emails you yet.
   Needs an email provider decision (Resend or Postmark; both have free tiers).
5. **Test the booking race** — two concurrent requests for one slot. The re-check should
   hold, but it should be proven rather than assumed.

---

## Honest status

Written and compiling. **Not yet run against a live database or a real Stripe account.**
The first deploy will surface things a compile check can't: a migration that needs a
manual tweak, a Stripe price configured as the wrong type, an availability row that
doesn't exist yet so every slot list comes back empty.

Budget an hour for that and it'll be fine. Anyone who tells you a build this size goes
green on the first deploy is selling something.
