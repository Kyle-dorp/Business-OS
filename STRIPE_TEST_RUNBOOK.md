# Putting a card through, in test mode

The one revenue path that had never been exercised end to end. This walks it
from an empty Stripe test account to a subscription that actually switches
modules on, and then to a cancellation that switches them off again.

Nothing here touches live mode. The setup script refuses a live key outright.

Budget about twenty minutes.

---

## What you need first

- A Stripe account. The test-mode dashboard is at
  [dashboard.stripe.com/test](https://dashboard.stripe.com/test/apikeys) — check
  the **Test mode** toggle is on, top right. Test keys start with `sk_test_`
  and `pk_test_`.
- The Stripe CLI: [stripe.com/docs/stripe-cli](https://stripe.com/docs/stripe-cli).
  On Windows: `scoop install stripe` or grab the release binary.
- The app running somewhere you can reach.

---

## 1. Create the prices

```bash
STRIPE_SECRET_KEY=sk_test_your_key_here python scripts/stripe_test_setup.py
```

It creates a Business-EOS product and three prices — $29 for the first
billable module, $10 for each one after, and a metered price for assistant
overage — then prints the env vars. Safe to run twice; it finds what already
exists rather than making a second ladder.

If the metered price fails to create, that is fine and the script says so. The
$29 + $10 ladder is what matters; overage metering can wait.

---

## 2. Set the environment

Paste what the script printed, plus the keys themselves:

```
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_PRICE_BASE=price_...
STRIPE_PRICE_MODULE=price_...
STRIPE_PRICE_AI_OVERAGE=price_...
STRIPE_METER_EVENT_NAME=assistant_tokens
APP_URL=http://localhost:5173
```

`APP_URL` is where Stripe sends the customer back after checkout. Check it has
exactly one `https://` on the front — a doubled one silently breaks the return
trip, and the symptom is a customer who pays and lands on a dead page.

`STRIPE_WEBHOOK_SECRET` comes from the next step.

---

## 3. Forward webhooks to your machine

In its own terminal, left running:

```bash
stripe listen --forward-to localhost:8000/billing/webhook
```

It prints `Ready! Your webhook signing secret is whsec_...`. That is
`STRIPE_WEBHOOK_SECRET`. Set it and **restart the API** — it is read at import.

The path is `/billing/webhook`. Not `/webhooks/stripe`.

> Why forwarding rather than a real webhook endpoint: `stripe listen` signs
> events with a secret only it knows, so you are testing the real signature
> verification path, not bypassing it.

---

## 4. Put a card through

1. Sign in, go to **Plan & billing**.
2. Switch on the modules you want. The quote should read $29 for one, $39 for
   two, $119 for all ten.
3. Click subscribe. You land on Stripe Checkout.
4. Pay with:

   | | |
   |---|---|
   | Card | `4242 4242 4242 4242` |
   | Expiry | any future date |
   | CVC | any three digits |
   | ZIP | any |

You should be returned to `/settings/billing?checkout=success`, and the
`stripe listen` terminal should show `customer.subscription.created` forwarded
with a `200`.

---

## 5. Check it actually did something

This is the part that was broken, so check the effect rather than the receipt.

```bash
python - <<'EOF'
from sqlmodel import Session, select
from backend.app.database import engine
from backend.app.models import Subscription
from backend.app.billing import enabled_modules, billable_modules, quote_cents

with Session(engine) as s:
    for sub in s.exec(select(Subscription)).all():
        bid = sub.business_id
        print(f"business {bid}: {sub.status}  renews {sub.current_period_end or '(unknown)'}")
        print(f"  enabled : {enabled_modules(s, bid)}")
        print(f"  billable: {len(billable_modules(s, bid))} -> ${quote_cents(len(billable_modules(s, bid)))/100:.0f}/mo")
EOF
```

Expect: status `active`, a renewal date in the near future (**not 1970** — that
was one of the bugs), and the modules you paid for enabled.

---

## 6. Then cancel, and check it took the modules back

This is the direction that was silently doing nothing, so do not skip it.

Click **Manage billing** to open the Stripe portal, cancel immediately, and
re-run the check above.

Expect: status `canceled`, and only `home`, `settings` and `notifications`
still enabled. Those three stay on deliberately — somebody who cancelled by
accident needs a way back in to pay again.

---

## 7. Worth also trying

Without the browser, using the CLI:

```bash
# a card that fails on renewal — access should NOT be revoked yet
stripe trigger invoice.payment_failed

# dunning gives up — access should be revoked now
stripe trigger customer.subscription.deleted
```

And with the browser, these test cards do specific things:

| Card | What happens |
|---|---|
| `4242 4242 4242 4242` | succeeds |
| `4000 0000 0000 0002` | declined at checkout |
| `4000 0000 0000 3220` | forces a 3D Secure challenge |
| `4000 0000 0000 0341` | attaches fine, then fails on the first charge |

That last one is the interesting one: the subscription is created `incomplete`
and the customer keeps working while Stripe retries, which is the grace
behaviour the handler is written for.

---

## When it is time to go live

1. Rerun `scripts/stripe_test_setup.py` against live mode — it will refuse, on
   purpose. Create the live prices by hand in the dashboard so it is a
   deliberate act, and copy their ids.
2. Swap the four `STRIPE_*` keys and price ids for live ones.
3. Register a real webhook endpoint at
   `https://your-domain/billing/webhook`, subscribed to:
   `customer.subscription.created`, `customer.subscription.updated`,
   `customer.subscription.deleted`, `customer.subscription.resumed`,
   `invoice.payment_succeeded`, `invoice.payment_failed`.
4. Use that endpoint's signing secret as `STRIPE_WEBHOOK_SECRET`.
5. Charge yourself once, on a real card, and refund it.

---

## If something goes wrong

**Checkout returns 503.** `STRIPE_SECRET_KEY` or the price ids are missing from
the environment the API actually loaded. Restart it after setting them.

**Webhook returns 400 "Invalid signature".** `STRIPE_WEBHOOK_SECRET` does not
match the `stripe listen` session currently running. The secret changes each
time you start a new one.

**Webhook returns 401.** `/billing/webhook` has fallen out of `PUBLIC_PATHS` in
`main.py`. It was missing once already, and the symptom is a customer who pays
and never gets activated.

**Payment succeeds, nothing switches on.** Check the `stripe listen` output
shows the event being forwarded at all. If it is arriving and still nothing
changes, the business id is not reaching the handler — checkout sets it via
`subscription_data.metadata.business_id`, and a subscription created by hand in
the dashboard will not have it.

**Nothing at all happens and there is no error.** That was the original bug.
`tests/test_stripe_webhook.py` pins it now; run `python -m pytest
tests/test_stripe_webhook.py -q` and see whether the suite disagrees with the
deployment.
