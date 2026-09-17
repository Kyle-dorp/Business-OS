"""
Module-count subscription billing.

Pricing: $29 for the first enabled module, $10 for each one after.
On Stripe that's two recurring prices on one subscription —

    BASE   x 1                       ($29/mo)
    MODULE x (module_count - 1)      ($10/mo each)

plus an optional metered price for assistant usage past the included
allowance. Switching a module on or off changes the MODULE quantity and
Stripe prorates the difference, so the bill always matches what's actually
switched on.

Webhook handling lives in stripe_service.py — one handler, one source of
truth. This module is the pricing and checkout layer on top of it.

All secrets come from the environment:
    STRIPE_SECRET_KEY, STRIPE_PRICE_BASE, STRIPE_PRICE_MODULE,
    STRIPE_PRICE_AI_OVERAGE (optional), APP_URL
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.app.auth import user_from_request
from backend.app.database import get_session
from backend.app.models import (
    Business,
    BusinessModule,
    Membership,
    Subscription,
    UserAccount,
    utc_now_iso,
)
from backend.app.modules_registry import (
    ALL_MODULES,
    EACH_MODULE_CENTS,
    FIRST_MODULE_CENTS,
    billable,
    catalogue_payload,
    quote_cents as catalogue_quote,
    stitched_cents,
)
from backend.app.tenancy import current_business_id

log = logging.getLogger(__name__)

from backend.app.config import env

PRICE_BASE = env("STRIPE_PRICE_BASE")
PRICE_MODULE = env("STRIPE_PRICE_MODULE")
PRICE_AI_OVERAGE = env("STRIPE_PRICE_AI_OVERAGE")
# Billing Meter event name — must match the meter created in the Stripe dashboard.
METER_EVENT_NAME = env("STRIPE_METER_EVENT_NAME", "assistant_tokens")
APP_URL = os.environ.get("APP_URL", "http://localhost:5173").rstrip("/")

BILLING_ROLES = {"owner", "admin"}

router = APIRouter(prefix="/billing", tags=["billing"])


# ------------------------------------------------------------------ helpers

def _stripe_ready() -> None:
    if not env("STRIPE_SECRET_KEY"):
        raise HTTPException(503, "Billing isn't configured on this deployment.")
    if not (PRICE_BASE and PRICE_MODULE):
        raise HTTPException(503, "Stripe price IDs are missing from the environment.")
    # env(), not os.environ — the raw value is where the quotes still are,
    # and assigning it here would undo the cleaning done one line above.
    stripe.api_key = env("STRIPE_SECRET_KEY")


def _require_billing_role(session: Session, bid: int, user: UserAccount) -> Membership:
    m = session.exec(
        select(Membership).where(
            Membership.business_id == bid,
            Membership.user_id == user.id,
            Membership.active == True,  # noqa: E712
        )
    ).first()
    if not m:
        raise HTTPException(403, "You don't have access to this workspace.")
    if m.role not in BILLING_ROLES:
        raise HTTPException(403, "Only an owner or admin can manage billing.")
    return m


def enabled_modules(session: Session, bid: int) -> list[str]:
    """
    Every module switched on, billable or not.

    A workspace that has never touched module settings has no BusinessModule
    rows at all, and the app treats absent-as-enabled. Billing must agree, or a
    brand-new workspace would be quoted $0 while using everything.
    """
    rows = session.exec(
        select(BusinessModule).where(BusinessModule.business_id == bid)
    ).all()
    explicit = {r.module_key: r.enabled for r in rows}
    return [key for key in ALL_MODULES if explicit.get(key, True)]


def billable_modules(session: Session, bid: int) -> list[str]:
    return billable(enabled_modules(session, bid))


def quote_cents(billable_count: int) -> int:
    return catalogue_quote(billable_count)


def _extra_units(module_count: int) -> int:
    return max(module_count - 1, 0)


def _subscription(session: Session, bid: int) -> Optional[Subscription]:
    return session.exec(
        select(Subscription).where(Subscription.business_id == bid)
    ).first()


def _ensure_customer(session: Session, business: Business, user: UserAccount) -> str:
    sub = _subscription(session, business.id)
    if sub and sub.stripe_customer_id:
        return sub.stripe_customer_id

    customer = stripe.Customer.create(
        email=getattr(user, "email", None) or None,
        name=business.name,
        metadata={"business_id": str(business.id)},
    )
    if sub:
        sub.stripe_customer_id = customer.id
        sub.updated_at = utc_now_iso()
        session.add(sub)
        session.commit()
    return customer.id


# ------------------------------------------------------------------ schemas

class UrlOut(BaseModel):
    url: str


class PreviewIn(BaseModel):
    module_keys: list[str]


# Subscription states in which the product should keep working. Stripe reports
# `past_due` while it retries a card — cutting someone off mid-service over a
# card that expired is how you lose a customer who wanted to pay.
WORKING_STATES = {"active", "trialing", "past_due", "incomplete"}
GRACE_STATES = {"past_due", "incomplete"}


def _money(cents: int) -> str:
    return f"${cents / 100:,.0f}"


# ------------------------------------------------------------------ routes

@router.get("/catalogue")
def catalogue(
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """
    Every module, what it costs here, what it replaces, and whether this
    workspace has it on. One call powers the whole billing screen.
    """
    bid = current_business_id()
    on = set(enabled_modules(session, bid))
    return {
        "modules": [{**m, "enabled": m["key"] in on} for m in catalogue_payload()],
        "first_module_cents": FIRST_MODULE_CENTS,
        "each_additional_cents": EACH_MODULE_CENTS,
    }


@router.get("/quote")
def get_quote(
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """What this workspace owes, and what the same set would cost elsewhere."""
    bid = current_business_id()
    on = enabled_modules(session, bid)
    chargeable = billable(on)
    cents = quote_cents(len(chargeable))
    elsewhere = stitched_cents(on)
    sub = _subscription(session, bid)
    status = sub.status if sub else "none"

    return {
        "module_count": len(chargeable),
        "modules": chargeable,
        "always_on": [k for k in on if k not in chargeable],
        "monthly_cents": cents,
        "monthly_display": _money(cents),
        "stitched_cents": elsewhere,
        "stitched_display": _money(elsewhere),
        "saving_cents": max(elsewhere - cents, 0),
        "saving_display": _money(max(elsewhere - cents, 0)),
        "first_module_cents": FIRST_MODULE_CENTS,
        "each_additional_cents": EACH_MODULE_CENTS,
        "status": status,
        "working": status in WORKING_STATES or status == "none",
        "in_grace": status in GRACE_STATES,
        "needs_subscription": status in ("none", "canceled", "incomplete_expired"),
        "current_period_end": sub.current_period_end if sub else None,
    }


@router.post("/preview")
def preview(
    body: PreviewIn,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """
    Price a hypothetical set without changing anything — what the module picker
    calls as somebody toggles things on and off.
    """
    chargeable = billable(body.module_keys)
    cents = quote_cents(len(chargeable))
    current = quote_cents(len(billable_modules(session, current_business_id())))
    elsewhere = stitched_cents(body.module_keys)

    return {
        "module_count": len(chargeable),
        "modules": chargeable,
        "monthly_cents": cents,
        "monthly_display": _money(cents),
        "stitched_cents": elsewhere,
        "stitched_display": _money(elsewhere),
        "saving_cents": max(elsewhere - cents, 0),
        "saving_display": _money(max(elsewhere - cents, 0)),
        "difference_cents": cents - current,
        "unknown_keys": [k for k in body.module_keys if k not in ALL_MODULES],
    }


@router.post("/checkout", response_model=UrlOut)
def checkout(
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    _stripe_ready()
    bid = current_business_id()
    _require_billing_role(session, bid, user)

    business = session.get(Business, bid)
    if not business:
        raise HTTPException(404, "Workspace not found.")

    mods = billable_modules(session, bid)
    if not mods:
        raise HTTPException(400, "Switch on at least one billable module before subscribing.")

    customer_id = _ensure_customer(session, business, user)

    line_items = [{"price": PRICE_BASE, "quantity": 1}]
    extra = _extra_units(len(mods))
    if extra:
        line_items.append({"price": PRICE_MODULE, "quantity": extra})
    if PRICE_AI_OVERAGE:
        # Metered — no quantity. Usage is reported as it accrues.
        line_items.append({"price": PRICE_AI_OVERAGE})

    try:
        s = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            line_items=line_items,
            success_url=f"{APP_URL}/settings/billing?checkout=success",
            cancel_url=f"{APP_URL}/settings/billing?checkout=cancelled",
            subscription_data={"metadata": {"business_id": str(bid)}},
            metadata={"business_id": str(bid), "module_count": str(len(mods))},
            allow_promotion_codes=True,
        )
    except stripe.error.StripeError as exc:
        log.exception("Checkout failed for business %s", bid)
        raise HTTPException(502, f"Couldn't start checkout: {exc.user_message or 'Stripe error'}")

    return UrlOut(url=s.url)


@router.post("/portal", response_model=UrlOut)
def portal(
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """Stripe's hosted portal — card changes, invoices, cancellation."""
    _stripe_ready()
    bid = current_business_id()
    _require_billing_role(session, bid, user)

    sub = _subscription(session, bid)
    if not sub or not sub.stripe_customer_id:
        raise HTTPException(400, "This workspace has no billing set up yet.")

    p = stripe.billing_portal.Session.create(
        customer=sub.stripe_customer_id,
        return_url=f"{APP_URL}/settings/billing",
    )
    return UrlOut(url=p.url)


@router.post("/sync")
def sync(
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """
    Push the current module count onto the live subscription.

    Call this every time a module is switched on or off. Stripe prorates, so
    enabling mid-cycle charges only the remaining days and disabling credits
    the difference.
    """
    _stripe_ready()
    bid = current_business_id()
    _require_billing_role(session, bid, user)

    sub = _subscription(session, bid)
    if not sub or not sub.stripe_subscription_id:
        return {"synced": False, "reason": "no active subscription"}

    count = len(billable_modules(session, bid))
    wanted = _extra_units(count)

    live = stripe.Subscription.retrieve(sub.stripe_subscription_id)
    item = next((i for i in live["items"]["data"] if i["price"]["id"] == PRICE_MODULE), None)

    if wanted == 0 and item:
        stripe.SubscriptionItem.delete(item["id"], proration_behavior="create_prorations")
    elif wanted and item and item["quantity"] != wanted:
        stripe.SubscriptionItem.modify(
            item["id"], quantity=wanted, proration_behavior="create_prorations"
        )
    elif wanted and not item:
        stripe.SubscriptionItem.create(
            subscription=sub.stripe_subscription_id,
            price=PRICE_MODULE,
            quantity=wanted,
            proration_behavior="create_prorations",
        )

    business = session.get(Business, bid)
    if business:
        business.monthly_price_cents = quote_cents(count)
        session.add(business)
        session.commit()

    return {"synced": True, "module_count": count, "monthly_cents": quote_cents(count)}


def report_meter_usage(session: Session, business_id: int, tokens: int) -> dict:
    """
    Report metered assistant usage to Stripe, in 1,000-token units.

    Stripe's modern metered billing is Billing Meters, not the old usage-record
    API — you send a meter event naming the customer and Stripe aggregates it
    against whatever price is bound to that meter. Called by the agent as usage
    accrues past the included allowance.

    Every failure path here is soft. A metering hiccup must never break someone's
    conversation: worst case we under-bill, which is the right way to be wrong.
    """
    if not (METER_EVENT_NAME and PRICE_AI_OVERAGE):
        return {"reported": False, "reason": "metering not configured"}

    units = max(round(tokens / 1000), 0)
    if units <= 0:
        return {"reported": False, "reason": "below one billable unit"}

    sub = _subscription(session, business_id)
    if not sub or not sub.stripe_customer_id:
        return {"reported": False, "reason": "no stripe customer"}

    try:
        stripe.api_key = env("STRIPE_SECRET_KEY")
        stripe.billing.MeterEvent.create(
            event_name=METER_EVENT_NAME,
            payload={
                "stripe_customer_id": sub.stripe_customer_id,
                "value": str(units),
            },
        )
    except Exception as exc:
        log.warning("Meter report failed for business %s: %s", business_id, exc)
        return {"reported": False, "reason": str(exc)}

    return {"reported": True, "units": units}


@router.post("/report-ai-usage")
def report_ai_usage_route(
    tokens: int,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """Manual trigger, mostly for testing the meter wiring end to end."""
    _stripe_ready()
    return report_meter_usage(session, current_business_id(), tokens)
