# Billing + Assistant — Setup Checklist

Two new files are wired and waiting on configuration:

- `backend/app/billing.py` — Stripe subscriptions matching the $29 + $10/module ladder
- `backend/app/ai_chat.py` — Claude assistant with hard spend caps

Neither contains a secret. Both read from environment variables.

---

## 1. Rotate the keys that were pasted in chat

Do this before anything else.

| Key | Where | Action |
|---|---|---|
| `sk_live_...` | Stripe → Developers → API keys | **Roll key** |
| `apikey_01Jhae...` | Anthropic Console → API keys | **Delete + create new** |
| `sk-ant-api03-...` | Anthropic Console → API keys | **Delete + create new** |

The publishable key (`pk_live_...`) is safe — it's designed to be public.

---

## 2. Create the two Stripe prices

Stripe Dashboard → **Product catalogue** → Add product.

**Product 1 — "Business-EOS base"**
- Recurring, monthly
- **$29.00**
- Copy the price ID → `STRIPE_PRICE_BASE`

**Product 2 — "Additional module"**
- Recurring, monthly
- **$10.00**
- Under *More options*, set usage to **package/per-unit** so quantity multiplies
- Copy the price ID → `STRIPE_PRICE_MODULE`

The subscription carries base × 1 plus module × (module count − 1). One module = $29. Six = $79. Ten = $119.

---

## 3. Create the webhook endpoint

Stripe Dashboard → **Developers → Webhooks → Add endpoint**

- URL: `https://<your-api-domain>/billing/webhook`
- Events to send:
  - `checkout.session.completed`
  - `customer.subscription.created`
  - `customer.subscription.updated`
  - `customer.subscription.deleted`
  - `invoice.payment_failed`
- Copy the signing secret (`whsec_...`) → `STRIPE_WEBHOOK_SECRET`

The endpoint verifies this signature on every call. Without it, anyone could POST a fake "payment succeeded" event and unlock a workspace for free.

---

## 4. Railway environment variables

**API service:**
```
STRIPE_SECRET_KEY=sk_live_...          (the NEW rolled one)
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_BASE=price_...
STRIPE_PRICE_MODULE=price_...
APP_URL=https://<your-frontend-domain>

ANTHROPIC_API_KEY=sk-ant-...           (the NEW one)
ANTHROPIC_MODEL=claude-sonnet-5
```

**Frontend service:**
```
VITE_STRIPE_PUBLISHABLE_KEY=pk_live_...
```

Optional assistant tuning (sensible defaults are built in):
```
AI_MONTHLY_INPUT_TOKENS=400000
AI_MONTHLY_OUTPUT_TOKENS=120000
AI_MESSAGES_PER_HOUR=40
AI_MAX_TOKENS_PER_REPLY=1024
```

---

## 5. Database columns

`Business` needs four fields for billing state:

```python
stripe_customer_id: Optional[str] = Field(default=None, index=True)
stripe_subscription_id: Optional[str] = Field(default=None, index=True)
subscription_status: Optional[str] = Field(default=None)   # active | past_due | canceled
current_period_end: Optional[int] = Field(default=None)    # unix timestamp
```

The two assistant tables (`ai_usage`, `ai_message_log`) are declared inside `ai_chat.py` and are created by the same migration.

```bash
alembic revision --autogenerate -m "billing + ai usage"
alembic upgrade head
```

---

## 6. Mount the routers

In `backend/app/main.py`:

```python
from .billing import router as billing_router
from .ai_chat import router as assistant_router

app.include_router(billing_router)
app.include_router(assistant_router)
```

**Important:** the webhook route must be reachable *without* auth — Stripe isn't logged in. If your auth middleware covers everything by default, exempt `/billing/webhook` and rely on the signature check instead.

---

## 7. Keep the subscription in sync

Whenever a module is switched on or off in the admin panel, call:

```
POST /billing/sync
```

Stripe prorates automatically, so switching a module on mid-month charges only the remaining days. Switching one off credits the difference.

---

## How the spend caps work

Three gates before any request reaches Anthropic:

1. **Burst** — 40 messages per user per hour. Stops one person hammering it.
2. **Monthly budget** — 400k input / 120k output tokens per *workspace* per month. That's roughly **$2.50 of model spend** against a minimum $29 plan, and enough for a few hundred real conversations.
3. **Response cap** — `max_tokens=1024` on every call, so no single reply can run away.

When a workspace hits its ceiling it gets a plain-language message and the rest of the platform keeps working. Check remaining allowance any time:

```
GET /assistant/budget
```

Budget is per workspace, not per user, because plans include unlimited users — otherwise a 30-person restaurant would cost 30× a 5-person one for the same subscription.
