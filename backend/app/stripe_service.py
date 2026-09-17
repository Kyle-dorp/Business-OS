"""
Stripe integration for subscription management.

Setup:
1. Add 'stripe' to requirements.txt: pip install stripe
2. Set STRIPE_SECRET_KEY and STRIPE_PUBLIC_KEY in .env
3. Set STRIPE_WEBHOOK_SECRET in .env (from Stripe dashboard)
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session, select

from backend.app.database import engine
from backend.app.models import Business, BusinessModule, Subscription

try:
    import stripe
except ImportError:
    stripe = None

# Read through config.env, which strips the quotes a pasted value keeps. A key
# set as `"sk_live_..."` is truthy, so the app reported itself configured while
# every call to Stripe failed on an invalid key.
from backend.app.config import env

STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY") or None
STRIPE_PUBLIC_KEY = env("STRIPE_PUBLIC_KEY") or None
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET") or None

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY


def stripe_configured() -> bool:
    """
    Whether Stripe calls can actually be made.

    The secret key, and nothing else. This used to also require
    STRIPE_PUBLIC_KEY, which meant a missing *browser* credential answered
    every incoming webhook with 503 — the payment succeeds, the customer is
    charged, and access never switches on. Checkout here is a server-side
    redirect: Stripe.js never runs, and the publishable key is not sent to the
    frontend or passed to Stripe anywhere. It was required and unused.
    """
    return bool(stripe and STRIPE_SECRET_KEY)


# ---------------------------------------------------------------------------
# Webhooks
#
# This is the only thing that turns a payment into access, and the only thing
# that takes access away again. It used to write to a module key named
# "scheduler", which is not in the registry — so a paying customer had nothing
# switched on for them, and a cancelling customer kept everything. Both
# directions were silently inert.
# ---------------------------------------------------------------------------


def _billable_keys() -> list[str]:
    """
    Access is granted and revoked over the billable modules only. The free ones
    (home, settings, notifications) stay on for everybody, including a
    workspace that has cancelled: locking somebody out of their own settings
    page is not a dunning strategy.
    """
    from backend.app.modules_registry import ALL_MODULES

    return [key for key, module in ALL_MODULES.items() if module.billable]


# Stripe sends "active" and "trialing" for a subscription in good standing.
# "past_due" means a payment failed and Stripe is still retrying — that is a
# grace period, not a cancellation, and cutting a restaurant off mid-service
# over a card that expired yesterday is how you lose them permanently.
# Kept deliberately identical to billing.WORKING_STATES. Two files disagreeing
# about what counts as a paying customer is how the module registries diverged.
ACTIVE_STATUSES = {"active", "trialing", "past_due", "incomplete"}
DEAD_STATUSES = {"canceled", "unpaid", "incomplete_expired"}


def handle_webhook_event(event: dict) -> None:
    """
    Process a Stripe webhook event.

    Stripe redelivers events routinely — on its own retry schedule, and again
    if the endpoint is slow. Every handler below is therefore idempotent:
    running the same event twice must leave the same state as running it once.
    """
    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})

    with Session(engine) as session:
        if event_type in (
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.resumed",
        ):
            _handle_subscription_upsert(session, data)
        elif event_type == "customer.subscription.deleted":
            _handle_subscription_deleted(session, data)
        elif event_type == "invoice.payment_failed":
            _handle_payment_failed(session, data)
        elif event_type == "invoice.payment_succeeded":
            _handle_payment_succeeded(session, data)


def _period_end(data: dict) -> str:
    """
    Newer Stripe API versions moved current_period_end off the subscription and
    onto each subscription item. Reading only the old location yields 0, which
    becomes 1970 — a subscription that renewed yesterday would read as decades
    expired. Try both, and leave it blank rather than inventing a date.
    """
    stamp = data.get("current_period_end")
    if not stamp:
        items = (data.get("items") or {}).get("data") or []
        stamps = [i.get("current_period_end") for i in items if i.get("current_period_end")]
        stamp = max(stamps) if stamps else None
    if not stamp:
        return ""
    try:
        return datetime.fromtimestamp(int(stamp), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        return ""


def _subscription_id(data: dict) -> str:
    """
    The Stripe subscription id, wherever this particular object keeps it.

    An invoice carries it as "subscription"; newer API versions moved it to
    parent.subscription_details.subscription. A subscription object is itself
    the subscription, so its own "id" is the answer.
    """
    direct = data.get("subscription")
    if isinstance(direct, str) and direct:
        return direct

    parent = data.get("parent") or {}
    details = parent.get("subscription_details") or {}
    nested = details.get("subscription")
    if isinstance(nested, str) and nested:
        return nested

    own = data.get("id")
    if isinstance(own, str) and own.startswith("sub_"):
        return own
    # A subscription id that does not use the sub_ prefix is still valid in
    # tests and fixtures; fall back to it only when nothing else identified one.
    return own if isinstance(own, str) and not own.startswith(("in_", "ch_", "pi_")) else ""


def _find_subscription(session: Session, data: dict) -> Optional[Subscription]:
    """
    By the Stripe subscription id first.

    Two rows for one Stripe subscription is the shape a retry used to create,
    and .first() then picked whichever the database happened to return — so a
    cancellation could update the row nobody reads. Deduplicate on the way
    past, keeping the oldest.
    """
    # Order matters. On a subscription event, data.object IS the subscription
    # and "id" is what we want. On an invoice event, "id" is the invoice — and
    # taking it would look up a subscription that does not exist, so a failed
    # payment would silently do nothing.
    subscription_id = _subscription_id(data)
    if not subscription_id:
        return None

    rows = session.exec(
        select(Subscription)
        .where(Subscription.stripe_subscription_id == subscription_id)
        .order_by(Subscription.id)
    ).all()
    if not rows:
        return None
    for stale in rows[1:]:
        session.delete(stale)
    return rows[0]


def _business_id_for(session: Session, data: dict) -> int:
    """
    Checkout stamps business_id onto the metadata of the subscription itself,
    so that is the primary source. A subscription created by hand in the Stripe
    dashboard has no such metadata, so fall back to the customer id recorded
    when the workspace first reached checkout.
    """
    raw = (data.get("metadata") or {}).get("business_id")
    try:
        if raw and int(raw) > 0:
            return int(raw)
    except (TypeError, ValueError):
        pass

    customer_id = data.get("customer")
    if customer_id:
        existing = session.exec(
            select(Subscription).where(Subscription.stripe_customer_id == customer_id)
        ).first()
        if existing:
            return existing.business_id
    return 0


def _handle_subscription_upsert(session: Session, data: dict) -> None:
    """created, updated and resumed are one operation: make our row match."""
    business_id = _business_id_for(session, data)
    if not business_id:
        return

    status = data.get("status", "unknown")
    subscription = _find_subscription(session, data)
    if subscription is None:
        subscription = Subscription(
            business_id=business_id,
            stripe_customer_id=data.get("customer") or "",
            stripe_subscription_id=data.get("id") or "",
            status=status,
            plan=(data.get("metadata") or {}).get("plan", ""),
            current_period_end=_period_end(data),
        )
    else:
        subscription.business_id = business_id
        subscription.status = status
        subscription.stripe_customer_id = (
            data.get("customer") or subscription.stripe_customer_id
        )
        period_end = _period_end(data)
        if period_end:
            subscription.current_period_end = period_end
        subscription.updated_at = datetime.now(timezone.utc).isoformat()

    session.add(subscription)

    if status in ACTIVE_STATUSES:
        _set_billable_modules(session, business_id, enabled=True)
    elif status in DEAD_STATUSES:
        _set_billable_modules(session, business_id, enabled=False)

    session.commit()


def _handle_subscription_deleted(session: Session, data: dict) -> None:
    subscription = _find_subscription(session, data)
    if not subscription:
        return

    subscription.status = "canceled"
    subscription.updated_at = datetime.now(timezone.utc).isoformat()
    session.add(subscription)
    _set_billable_modules(session, subscription.business_id, enabled=False)
    session.commit()


def _handle_payment_failed(session: Session, data: dict) -> None:
    """
    Record it; do not revoke.

    Stripe retries a failed payment over roughly two weeks. If it gives up it
    sends subscription.updated with "unpaid", or subscription.deleted, and
    those revoke. Cutting access off the first failed attempt punishes an
    expired card exactly as hard as a refusal to pay.
    """
    subscription = _find_subscription(session, data)
    if not subscription:
        return

    subscription.status = "past_due"
    subscription.updated_at = datetime.now(timezone.utc).isoformat()
    session.add(subscription)
    session.commit()


def _handle_payment_succeeded(session: Session, data: dict) -> None:
    """A recovered payment puts access back without waiting for anything else."""
    subscription = _find_subscription(session, data)
    if not subscription:
        return

    if subscription.status == "past_due":
        subscription.status = "active"
        subscription.updated_at = datetime.now(timezone.utc).isoformat()
        session.add(subscription)
    _set_billable_modules(session, subscription.business_id, enabled=True)
    session.commit()


def _set_billable_modules(session: Session, business_id: int, enabled: bool) -> None:
    """
    Write an explicit row per billable module.

    Explicit matters: a workspace with no rows at all is treated as having
    everything switched on, so revoking access by deleting rows would grant it
    instead.
    """
    rows = session.exec(
        select(BusinessModule).where(BusinessModule.business_id == business_id)
    ).all()
    by_key = {row.module_key: row for row in rows}

    for key in _billable_keys():
        row = by_key.get(key)
        if row is None:
            row = BusinessModule(business_id=business_id, module_key=key, enabled=enabled)
        else:
            row.enabled = enabled
        session.add(row)
