#!/usr/bin/env python
"""
Create the Business-EOS prices in Stripe TEST mode.

Run this once, with a test-mode secret key, and paste the three env vars it
prints into Railway (or .env) so checkout has something to sell.

    STRIPE_SECRET_KEY=sk_test_... python scripts/stripe_test_setup.py

It refuses to run against a live key. That refusal is the point of the script
existing rather than the steps living in a README: creating a product by hand
in the wrong mode is easy, and creating a live $29 subscription price you then
accidentally charge somebody with is not a mistake worth being one keystroke
away from.

Safe to run more than once. Everything is looked up by lookup_key first, so a
second run reports what already exists instead of creating a duplicate ladder.
"""

from __future__ import annotations

import os
import sys

FIRST_MODULE_CENTS = 2900   # $29 for the first billable module
EACH_MODULE_CENTS = 1000    # $10 for each one after
METER_EVENT_NAME = os.environ.get("STRIPE_METER_EVENT_NAME", "assistant_tokens")

# Stripe charges roughly $3 per million Sonnet input tokens. A little over cost
# so overage is not a loss leader, and small enough that nobody is surprised.
OVERAGE_CENTS_PER_1K_TOKENS = 1

LOOKUP_BASE = "eos_base_first_module"
LOOKUP_MODULE = "eos_additional_module"
LOOKUP_OVERAGE = "eos_assistant_overage"


def fail(message: str) -> None:
    print(f"\n  {message}\n", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    key = os.environ.get("STRIPE_SECRET_KEY", "").strip()

    if not key:
        fail(
            "STRIPE_SECRET_KEY is not set.\n"
            "  Get a test key from https://dashboard.stripe.com/test/apikeys\n"
            "  (make sure the dashboard's Test mode toggle is on — a test key "
            "starts with sk_test_)"
        )

    if key.startswith("sk_live_"):
        fail(
            "That is a LIVE key. This script only runs in test mode.\n"
            "  Switch the Stripe dashboard to Test mode and use the sk_test_ key."
        )

    if not key.startswith("sk_test_"):
        fail("That does not look like a Stripe secret key (expected sk_test_...).")

    try:
        import stripe
    except ImportError:
        fail("The stripe package is not installed. Run: pip install stripe")

    stripe.api_key = key

    try:
        account = stripe.Account.retrieve()
    except Exception as exc:  # noqa: BLE001 - any failure here means stop
        fail(f"Stripe rejected that key: {exc}")

    print(f"\nStripe test mode — account {account.get('id', 'unknown')}")
    print("=" * 62)

    product = _find_or_create_product(stripe)
    base = _find_or_create_price(
        stripe, LOOKUP_BASE, product.id,
        amount=FIRST_MODULE_CENTS, nickname="First billable module",
    )
    extra = _find_or_create_price(
        stripe, LOOKUP_MODULE, product.id,
        amount=EACH_MODULE_CENTS, nickname="Each additional module",
    )
    overage = _find_or_create_metered_price(stripe, product.id)

    print("\n" + "=" * 62)
    print("Paste these into Railway (or .env):\n")
    print(f"STRIPE_PRICE_BASE={base.id}")
    print(f"STRIPE_PRICE_MODULE={extra.id}")
    if overage:
        print(f"STRIPE_PRICE_AI_OVERAGE={overage.id}")
        print(f"STRIPE_METER_EVENT_NAME={METER_EVENT_NAME}")
    else:
        print("# STRIPE_PRICE_AI_OVERAGE — skipped, see the note above.")
        print("# Billing works without it; assistant overage simply is not metered.")

    print("\nStill needed, and not creatable from here:")
    print("  STRIPE_SECRET_KEY       the sk_test_ key you just used")
    print("  STRIPE_PUBLIC_KEY       the matching pk_test_ key")
    print("  STRIPE_WEBHOOK_SECRET   printed by `stripe listen` (see the runbook)")
    print("\nThen follow STRIPE_TEST_RUNBOOK.md to put a card through.\n")


def _find_or_create_product(stripe):
    for existing in stripe.Product.list(limit=100, active=True).auto_paging_iter():
        if existing.metadata.get("app") == "business-eos":
            print(f"  product   found    {existing.id}  {existing.name}")
            return existing

    product = stripe.Product.create(
        name="Business-EOS",
        description="Modular business operations platform",
        metadata={"app": "business-eos"},
    )
    print(f"  product   created  {product.id}")
    return product


def _find_or_create_price(stripe, lookup_key: str, product_id: str, amount: int, nickname: str):
    found = stripe.Price.list(lookup_keys=[lookup_key], limit=1).data
    if found:
        print(f"  price     found    {found[0].id}  {nickname}")
        return found[0]

    price = stripe.Price.create(
        product=product_id,
        unit_amount=amount,
        currency="usd",
        recurring={"interval": "month"},
        nickname=nickname,
        lookup_key=lookup_key,
    )
    print(f"  price     created  {price.id}  {nickname} (${amount / 100:.0f}/mo)")
    return price


def _find_or_create_metered_price(stripe, product_id: str):
    """
    The assistant overage price, billed against a Stripe meter.

    Optional on purpose. Meters are a newer Stripe feature and the API for them
    has moved around; if this account or this version of the library cannot
    create one, say so and carry on rather than failing a setup that otherwise
    succeeded. Everything except assistant overage still bills correctly.
    """
    found = stripe.Price.list(lookup_keys=[LOOKUP_OVERAGE], limit=1).data
    if found:
        print(f"  price     found    {found[0].id}  Assistant overage")
        return found[0]

    try:
        meter = _find_or_create_meter(stripe)
        price = stripe.Price.create(
            product=product_id,
            currency="usd",
            recurring={"interval": "month", "usage_type": "metered", "meter": meter.id},
            billing_scheme="per_unit",
            unit_amount=OVERAGE_CENTS_PER_1K_TOKENS,
            nickname="Assistant overage",
            lookup_key=LOOKUP_OVERAGE,
        )
        print(f"  price     created  {price.id}  Assistant overage")
        return price
    except Exception as exc:  # noqa: BLE001 - optional feature, never fatal
        print(f"\n  note: could not create the metered overage price ({exc}).")
        print("  This is not fatal. Set it up in the dashboard later if you want it.")
        return None


def _find_or_create_meter(stripe):
    for existing in stripe.billing.Meter.list(limit=100).auto_paging_iter():
        if existing.event_name == METER_EVENT_NAME and existing.status == "active":
            print(f"  meter     found    {existing.id}  {METER_EVENT_NAME}")
            return existing

    meter = stripe.billing.Meter.create(
        display_name="Assistant tokens",
        event_name=METER_EVENT_NAME,
        default_aggregation={"formula": "sum"},
        customer_mapping={"type": "by_id", "event_payload_key": "stripe_customer_id"},
        value_settings={"event_payload_key": "value"},
    )
    print(f"  meter     created  {meter.id}  {METER_EVENT_NAME}")
    return meter


if __name__ == "__main__":
    main()
