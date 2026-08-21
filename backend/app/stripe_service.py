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

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY


def stripe_configured() -> bool:
    """Check if Stripe is properly configured."""
    return bool(stripe and STRIPE_SECRET_KEY and STRIPE_PUBLIC_KEY)


def create_checkout_session(
    business_id: int,
    plan: str,
    success_url: str,
    cancel_url: str,
) -> Optional[str]:
    """
    Create a Stripe Checkout session for a business.

    Args:
        business_id: The Business.id to subscribe
        plan: Plan key (e.g., "starter", "professional", "enterprise")
        success_url: URL to redirect to after successful payment
        cancel_url: URL to redirect to if user cancels

    Returns:
        Checkout session URL, or None if Stripe is not configured
    """
    if not stripe_configured():
        return None

    # Define pricing for each plan (in cents)
    # These should match your Stripe Product/Price IDs; for MVP, using placeholder amounts
    PLAN_PRICES = {
        "starter": 9900,  # $99/month
        "professional": 29900,  # $299/month
        "enterprise": 99900,  # $999/month
    }

    if plan not in PLAN_PRICES:
        raise ValueError(f"Unknown plan: {plan}")

    with Session(engine) as session:
        business = session.get(Business, business_id)
        if not business:
            raise ValueError(f"Business {business_id} not found")

        # Create or retrieve Stripe customer
        existing_sub = session.exec(
            select(Subscription).where(Subscription.business_id == business_id)
        ).first()

        if existing_sub and existing_sub.stripe_customer_id:
            customer_id = existing_sub.stripe_customer_id
        else:
            customer = stripe.Customer.create(
                email=f"billing@{business.name.lower().replace(' ', '')}.local",
                metadata={"business_id": business_id, "business_name": business.name},
            )
            customer_id = customer.id

        # Create checkout session
        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": f"Scheduler {plan.title()} Plan",
                            "description": f"Scheduler module - {plan} tier",
                        },
                        "unit_amount": PLAN_PRICES[plan],
                        "recurring": {"interval": "month"},
                    },
                    "quantity": 1,
                }
            ],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"business_id": business_id, "plan": plan},
        )

        return checkout_session.url


def handle_webhook_event(event: dict) -> None:
    """
    Process a Stripe webhook event.

    Handles:
    - customer.subscription.created
    - customer.subscription.updated
    - customer.subscription.deleted
    - invoice.payment_failed
    """
    event_type = event["type"]
    data = event["data"]["object"]

    with Session(engine) as session:
        if event_type == "customer.subscription.created":
            _handle_subscription_created(session, data)
        elif event_type == "customer.subscription.updated":
            _handle_subscription_updated(session, data)
        elif event_type == "customer.subscription.deleted":
            _handle_subscription_deleted(session, data)
        elif event_type == "invoice.payment_failed":
            _handle_payment_failed(session, data)


def _handle_subscription_created(session: Session, data: dict) -> None:
    """Handle customer.subscription.created event."""
    business_id = int(data.get("metadata", {}).get("business_id", 0))
    if not business_id:
        return

    plan = data.get("metadata", {}).get("plan", "")
    status = data.get("status", "unknown")
    current_period_end = datetime.fromtimestamp(
        data.get("current_period_end", 0), tz=timezone.utc
    ).isoformat()

    subscription = Subscription(
        business_id=business_id,
        stripe_customer_id=data.get("customer"),
        stripe_subscription_id=data.get("id"),
        status=status,
        plan=plan,
        current_period_end=current_period_end,
    )
    session.add(subscription)
    _enable_scheduler_module(session, business_id)
    session.commit()


def _handle_subscription_updated(session: Session, data: dict) -> None:
    """Handle customer.subscription.updated event."""
    subscription_id = data.get("id")
    subscription = session.exec(
        select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
    ).first()

    if not subscription:
        return

    subscription.status = data.get("status", subscription.status)
    subscription.updated_at = datetime.now(timezone.utc).isoformat()

    # Update period end if provided
    if data.get("current_period_end"):
        subscription.current_period_end = datetime.fromtimestamp(
            data["current_period_end"], tz=timezone.utc
        ).isoformat()

    session.add(subscription)

    # Enable/disable based on status
    if subscription.status in ("active", "trialing"):
        _enable_scheduler_module(session, subscription.business_id)
    elif subscription.status in ("canceled", "past_due", "incomplete"):
        _disable_scheduler_module(session, subscription.business_id)

    session.commit()


def _handle_subscription_deleted(session: Session, data: dict) -> None:
    """Handle customer.subscription.deleted event."""
    subscription_id = data.get("id")
    subscription = session.exec(
        select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
    ).first()

    if not subscription:
        return

    subscription.status = "canceled"
    subscription.updated_at = datetime.now(timezone.utc).isoformat()
    session.add(subscription)
    _disable_scheduler_module(session, subscription.business_id)
    session.commit()


def _handle_payment_failed(session: Session, data: dict) -> None:
    """Handle invoice.payment_failed event."""
    subscription_id = data.get("subscription")
    if not subscription_id:
        return

    subscription = session.exec(
        select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
    ).first()

    if not subscription:
        return

    subscription.status = "past_due"
    subscription.updated_at = datetime.now(timezone.utc).isoformat()
    session.add(subscription)
    _disable_scheduler_module(session, subscription.business_id)
    session.commit()


def _enable_scheduler_module(session: Session, business_id: int) -> None:
    """Enable the scheduler module for a business."""
    module = session.exec(
        select(BusinessModule).where(
            BusinessModule.business_id == business_id,
            BusinessModule.module_key == "scheduler",
        )
    ).first()

    if module:
        module.enabled = True
    else:
        module = BusinessModule(
            business_id=business_id,
            module_key="scheduler",
            enabled=True,
        )
    session.add(module)


def _disable_scheduler_module(session: Session, business_id: int) -> None:
    """Disable the scheduler module for a business."""
    module = session.exec(
        select(BusinessModule).where(
            BusinessModule.business_id == business_id,
            BusinessModule.module_key == "scheduler",
        )
    ).first()

    if module:
        module.enabled = False
        session.add(module)
