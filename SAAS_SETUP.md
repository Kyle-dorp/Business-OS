# Scheduler Micro-SaaS Setup Guide

This guide covers launching the Scheduler as a standalone, multi-tenant SaaS product.

## What's Been Built

### ✅ Step 1: Tenancy Resolution (Completed)
- `/auth/setup` now creates a Business + Membership for the first user
- Middleware validates that users only access businesses they're members of
- `/auth/memberships` endpoint lets clients show a workspace switcher
- No more hardcoded `business_id=1` fallback

### ✅ Step 2: Subscription Model (Completed)
- `Subscription` table stores Stripe subscription details per business
- Tracks: `stripe_customer_id`, `stripe_subscription_id`, `status`, `plan`, `current_period_end`

### ✅ Step 3: Stripe Integration (Completed)
- `POST /billing/checkout-session` — create a Stripe Checkout for subscription signup
- `POST /billing/webhook` — handle Stripe lifecycle events (created/updated/canceled/payment_failed)
- Subscription status is wired to `BusinessModule("scheduler").enabled` (auto-enable/disable)

### ✅ Step 4: Admin Provisioning (Completed)
- **Script:** `python provision_tenant.py` — interactive one-time setup for each new customer
- **API Endpoint:** `POST /admin/provision-tenant` — requires `ADMIN_API_KEY` header
- Both create: Business, Location, Manager UserAccount, Membership, ManagerSettings, BusinessModule

---

## Environment Variables

Add these to `.env`:

```bash
# Database (use the existing connection string)
DATABASE_URL=postgresql://...

# JWT & Auth
JWT_SECRET=your-secret-key-at-least-32-bytes
TOKEN_HOURS=168

# AI (Claude API, if using ai_service.py)
ANTHROPIC_API_KEY=sk-ant-...

# **NEW: Stripe**
STRIPE_SECRET_KEY=sk_live_... (or sk_test_... for testing)
STRIPE_PUBLIC_KEY=pk_live_... (or pk_test_...)
STRIPE_WEBHOOK_SECRET=whsec_...

# **NEW: Admin provisioning API key**
ADMIN_API_KEY=your-secret-admin-key
```

### Getting Stripe Keys

1. Go to [Stripe Dashboard](https://dashboard.stripe.com/)
2. Navigate to **Developers** → **API Keys**
3. Copy `Secret Key` and `Publishable Key`
4. For webhook secret:
   - Go to **Developers** → **Webhooks**
   - Add endpoint: `https://yourdomain.com/billing/webhook`
   - Events to listen for: `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed`
   - Copy the **Signing Secret** from the endpoint details

---

## Database Migrations

The existing Alembic setup should handle schema changes automatically on app startup (via `create_db_and_tables()`). If using a production database:

```bash
alembic upgrade head
```

The new tables added:
- `subscription` — stores Stripe subscription data per business

---

## Onboarding a New Customer (MVP Flow)

### Option A: Using the Provisioning Script

```bash
python provision_tenant.py
```

This will:
1. Prompt for business name, location, manager credentials
2. Create Business, Location, UserAccount, Membership, ManagerSettings
3. Enable the Scheduler module
4. Print the tenant details (Business ID, Manager ID, etc.)

### Option B: Using the API Endpoint (if backend is running)

```bash
curl -X POST http://localhost:8000/admin/provision-tenant \
  -H "Authorization: Bearer $ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "business_name": "Mile High Delis",
    "location_name": "South Broadway",
    "manager_username": "manager1",
    "manager_password": "SecurePassword123",
    "store_name": "Store #1",
    "timezone": "America/Denver"
  }'
```

---

## Subscription Flow (for UI/Frontend)

### 1. User Initiates Checkout

Frontend calls:
```bash
POST /billing/checkout-session
Authorization: Bearer <token>
X-Business-Id: <business_id>

{
  "plan": "professional",
  "success_url": "https://app.yourdomain.com/billing/success",
  "cancel_url": "https://app.yourdomain.com/billing/cancel"
}
```

Response:
```json
{
  "checkout_url": "https://checkout.stripe.com/..."
}
```

### 2. Redirect User to Checkout

Redirect user to the `checkout_url`. Stripe handles payment.

### 3. Stripe Webhook Handles Subscription

When subscription is created/updated/canceled, Stripe sends a webhook to `/billing/webhook`.
The backend:
- Updates the `Subscription` row
- Auto-enables/disables `BusinessModule("scheduler")`

### 4. Check Subscription Status

Frontend can check if the business is subscribed:
```bash
GET /billing/subscription
Authorization: Bearer <token>
X-Business-Id: <business_id>
```

Response:
```json
{
  "subscription": {
    "id": 1,
    "business_id": 5,
    "status": "active",
    "plan": "professional",
    "current_period_end": "2026-09-19T...",
    "created_at": "2026-08-19T..."
  }
}
```

If `status` is not `active`, the Scheduler module is disabled.

---

## Feature Gating (Scheduler Only)

Existing feature-gating via `BusinessModule`:

```python
# In any endpoint, check if scheduler is enabled
with Session(engine) as session:
    module = session.exec(
        select(BusinessModule).where(
            BusinessModule.business_id == current_business_id(),
            BusinessModule.module_key == "scheduler"
        )
    ).first()
    if not module or not module.enabled:
        raise HTTPException(status_code=403, detail="Scheduler not enabled for this business")
```

The existing scheduler endpoints (`/schedules`, `/employees`, etc.) should already use `current_business_id()` for tenant isolation, so they're already secure.

---

## Deployment Notes

### Critical: Sync to Deploy Repo

The brief mentions Railway deploys from `D:\projects\Business-EOS-GitHub`, **NOT** the working copy at `D:\projects\Business-EOS-complete\backend\app\`.

**Before deploying, sync changes:**

```bash
# Copy the updated backend files
cp -r D:\projects\Business-EOS-complete\backend\* D:\projects\Business-EOS-GitHub\backend\

# Or if you have git set up:
cd D:\projects\Business-EOS-GitHub
git add .
git commit -m "Add Stripe + multi-tenant provisioning"
git push origin main
```

### Environment in Railway

Add these to Railway project env vars:
- `STRIPE_SECRET_KEY`
- `STRIPE_PUBLIC_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `ADMIN_API_KEY`

(Keep existing vars: `DATABASE_URL`, `JWT_SECRET`, `ANTHROPIC_API_KEY`, etc.)

---

## Mobile & PWA (Next Steps)

For offline scheduling view, consider:

1. **Progressive Web App (PWA)**
   - Add `manifest.json` to frontend
   - Enable service workers for caching
   - Works on mobile without app store
   - Easiest for MVP

2. **Native Mobile App (React Native / Flutter)**
   - More work, better UX/performance
   - Consider after MVP validates market fit

3. **Electron Desktop App**
   - Shares frontend code
   - Good for managers' desktop use

---

## Pricing Strategy (Recommendation)

For a versatile platform like Scheduler serving different business types:

### Option: Tiered Feature-Based Pricing

```
Starter: $99/month
  - Up to 3 locations
  - Basic scheduling
  - Email notifications

Professional: $299/month
  - Unlimited locations
  - Advanced labor forecasting
  - Slack integration
  - API access

Enterprise: $999/month
  - Everything above
  - Dedicated support
  - SSO/SSO
  - Custom integrations
```

**Alternative: Per-Location Pricing** (since McAlister's organizes by location)

```
$79/month per location
+ Volume discount (4+ locations = 15% off)
```

### Why Not Per-Service?

Most successful SaaS platforms use **tiered plans**, not per-service, because:
- **Customers prefer predictability** — flat monthly fee beats "surprise charges"
- **Simpler billing** — easier to manage
- **Better margins** — bundling avoids feature fragmentation

Start with tiered plans. If data shows per-feature metering (e.g., "some customers only want forecasting"), add it later.

---

## Testing the Setup

### 1. Start the backend
```bash
python -m uvicorn backend.app.main:app --reload
```

### 2. Provision a test tenant
```bash
python provision_tenant.py
```
(Enter test data when prompted)

### 3. Login as the manager
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "manager1", "password": "SecurePassword123"}'
```

### 4. Get a token and check memberships
```bash
curl -X GET http://localhost:8000/auth/memberships \
  -H "Authorization: Bearer <token>"
```

### 5. Create a checkout session (requires Stripe keys in .env)
```bash
curl -X POST http://localhost:8000/billing/checkout-session \
  -H "Authorization: Bearer <token>" \
  -d '{
    "plan": "professional",
    "success_url": "http://localhost:3000/success",
    "cancel_url": "http://localhost:3000/cancel"
  }'
```

---

## Troubleshooting

### "You are not assigned to any business"
- The user's `Membership` wasn't created or is marked `active=false`
- Use `provision_tenant.py` to create a new tenant with a user

### Stripe webhook not working
- Verify `STRIPE_WEBHOOK_SECRET` is set correctly
- Check that your Stripe webhook endpoint is publicly accessible
- Test using Stripe CLI: `stripe listen --forward-to localhost:8000/billing/webhook`

### "Scheduler not enabled"
- Check `BusinessModule` row for this business with `module_key="scheduler"`
- Subscription status may not be `active` — check the `Subscription` row

---

## Next Steps

1. **Frontend work:** Build UI for workspace switcher, billing portal, checkout
2. **Testing:** Thoroughly test multi-tenant isolation, subscription lifecycle
3. **Documentation:** Write user onboarding docs for McAlister's
4. **Monitoring:** Set up alerts for failed Stripe webhooks, subscription issues
5. **Scale considerations:** Monitor database performance with multiple tenants

---

## Files Changed/Added

- **main.py** — tenancy middleware fix, auth/memberships endpoints, billing endpoints, admin provisioning
- **models.py** — added `Subscription` table
- **stripe_service.py** — new file for Stripe integration logic
- **provision_tenant.py** — new file for admin provisioning script
- **requirements.txt** — added `stripe`

---

## Questions?

Refer to:
- Stripe docs: https://stripe.com/docs
- SQLModel docs: https://sqlmodel.tiangolo.com/
- FastAPI docs: https://fastapi.tiangolo.com/
