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
from backend.app.modules_registry import ALL_MODULES
from backend.app.tenancy import current_business_id

log = logging.getLogger(__name__)

PRICE_BASE = os.environ.get("STRIPE_PRICE_BASE", "")
PRICE_MODULE = os.environ.get("STRIPE_PRICE_MODULE", "")
PRICE_AI_OVERAGE = os.environ.get("STRIPE_PRICE_AI_OVERAGE", "")
APP_URL = os.environ.get("APP_URL", "http://localhost:5173").rstrip("/")

FIRST_MODULE_CENTS = 2900
EACH_MODULE_CENTS = 1000

BILLING_ROLES = {"owner", "admin"}

router = APIRouter(prefix="/billing", tags=["billing"])


# ------------------------------------------------------------------ helpers

def _stripe_ready() -> None:
    if not os.environ.get("STRIPE_SECRET_KEY"):
        raise HTTPException(503, "Billing isn't configured on this deployment.")
    if not (PRICE_BASE and PRICE_MODULE):
        raise HTTPException(503, "Stripe price IDs are missing from the environment.")
    stripe.api_key = os.environ["STRIPE_SECRET_KEY"]


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
    rows = session.exec(
        select(BusinessModule).where(
            BusinessModule.business_id == bid,
            BusinessModule.enabled == True,  # noqa: E712
        )
    ).all()
    return [r.module_key for r in rows]


def quote_cents(module_count: int) -> int:
    if module_count <= 0:
        return 0
    return FIRST_MODULE_CENTS + (module_count - 1) * EACH_MODULE_CENTS


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

class QuoteOut(BaseModel):
    module_count: int
    modules: list[str]
    monthly_cents: int
    monthly_display: str
    first_module_cents: int = FIRST_MODULE_CENTS
    each_additional_cents: int = EACH_MODULE_CENTS
    status: str
    current_period_end: Optional[str] = None


class UrlOut(BaseModel):
    url: str


class PreviewIn(BaseModel):
    module_keys: list[str]


# ------------------------------------------------------------------ routes

@router.get("/quote", response_model=QuoteOut)
def get_quote(
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """What this workspace owes for the modules it currently has switched on."""
    bid = current_business_id()
    mods = enabled_modules(session, bid)
    cents = quote_cents(len(mods))
    sub = _subscription(session, bid)
    return QuoteOut(
        module_count=len(mods),
        modules=mods,
        monthly_cents=cents,
        monthly_display=f"${cents / 100:,.0f}",
        status=sub.status if sub else "none",
        current_period_end=sub.current_period_end if sub else None,
    )


@router.post("/preview")
def preview(
    body: PreviewIn,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """
    Price a hypothetical module set without changing anything — this is what
    the in-app module picker calls as the operator toggles things on and off.
    """
    valid = [k for k in body.module_keys if k in ALL_MODULES]
    cents = quote_cents(len(valid))
    current = quote_cents(len(enabled_modules(session, current_business_id())))
    return {
        "module_count": len(valid),
        "modules": valid,
        "monthly_cents": cents,
        "monthly_display": f"${cents / 100:,.0f}",
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

    mods = enabled_modules(session, bid)
    if not mods:
        raise HTTPException(400, "Switch on at least one module before subscribing.")

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

    count = len(enabled_modules(session, bid))
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


@router.post("/report-ai-usage")
def report_ai_usage(
    tokens: int,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """
    Report metered assistant usage to Stripe, in 1,000-token units.

    Called by the agent once a workspace passes its included allowance. If no
    metered price is configured this is a no-op, so overage simply isn't
    charged rather than silently failing.
    """
    if not PRICE_AI_OVERAGE:
        return {"reported": False, "reason": "no metered price configured"}

    _stripe_ready()
    bid = current_business_id()
    sub = _subscription(session, bid)
    if not sub or not sub.stripe_subscription_id:
        return {"reported": False, "reason": "no active subscription"}

    live = stripe.Subscription.retrieve(sub.stripe_subscription_id)
    item = next((i for i in live["items"]["data"] if i["price"]["id"] == PRICE_AI_OVERAGE), None)
    if not item:
        return {"reported": False, "reason": "metered item not on subscription"}

    units = max(round(tokens / 1000), 0)
    if units:
        stripe.SubscriptionItem.create_usage_record(
            item["id"], quantity=units, action="increment"
        )
    return {"reported": True, "units": units}
