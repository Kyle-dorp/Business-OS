"""
The revenue path.

The webhook is the only thing in the product that converts a payment into
access, and the only thing that takes access away again. Everything else about
billing — the ladder, the quote, the checkout line items — is arithmetic that
can be checked by reading. This cannot: it is a conversation with Stripe, and
until these tests existed nothing had ever run it.

What running it found, in the direction that costs real money:

    A customer cancelled, and kept every module.

The handler enabled and disabled a module key named "scheduler". There is no
such module — the registry calls it "scheduling" — so the row it wrote matched
nothing on the way in and nothing on the way out. A cancelling customer
retained $119/month of product indefinitely, and a paying one was granted
nothing, which only went unnoticed because a fresh workspace has everything
switched on anyway.

These tests assert on what the workspace can actually *do* after an event,
never on which rows were written. A webhook that records a subscription
perfectly and grants the wrong access is still broken.
"""

from __future__ import annotations

import uuid

import pytest
from sqlmodel import Session, select

from backend.app.billing import WORKING_STATES, billable_modules, enabled_modules, quote_cents
from backend.app.database import engine
from backend.app.models import Business, BusinessModule, Subscription, UserAccount
from backend.app.modules_registry import ALL_MODULES
from backend.app.platform import seed_business
from backend.app.stripe_service import (
    ACTIVE_STATUSES,
    DEAD_STATUSES,
    handle_webhook_event,
)
from backend.app.tenancy import set_current_business_id

FREE_MODULES = {key for key, module in ALL_MODULES.items() if not module.billable}


@pytest.fixture
def workspace():
    """A seeded workspace, as signup produces one: every module switched on."""
    suffix = uuid.uuid4().hex[:6]
    with Session(engine) as s:
        user = UserAccount(
            username=f"payer{suffix}", password_hash="x", role="manager", active=True
        )
        s.add(user)
        s.flush()
        business = Business(name=f"Payer {suffix}", industry="general", active=True)
        s.add(business)
        s.flush()
        bid = business.id

        set_current_business_id(bid)
        try:
            seed_business(s, business, user, role="owner")
            s.commit()
        finally:
            set_current_business_id(1)

    yield {"business_id": bid, "customer": f"cus_{suffix}", "subscription": f"sub_{suffix}"}
    set_current_business_id(1)


# ------------------------------------------------------------------ payloads
#
# Shaped like the real thing. Stripe sends the subscription object itself as
# data.object, with business_id in metadata because checkout puts it there via
# subscription_data.

def _subscription_event(workspace, event_type, status="active", **overrides):
    data = {
        "id": workspace["subscription"],
        "customer": workspace["customer"],
        "status": status,
        "current_period_end": 1789000000,
        "metadata": {"business_id": str(workspace["business_id"]), "plan": "modular"},
    }
    data.update(overrides)
    return {"type": event_type, "data": {"object": data}}


def _invoice_event(workspace, event_type):
    return {
        "type": event_type,
        "data": {"object": {
            "id": f"in_{uuid.uuid4().hex[:8]}",
            "customer": workspace["customer"],
            "subscription": workspace["subscription"],
        }},
    }


def _access(business_id):
    with Session(engine) as s:
        return set(enabled_modules(s, business_id))


def _monthly_value(business_id):
    with Session(engine) as s:
        return quote_cents(len(billable_modules(s, business_id)))


def _subscriptions(business_id):
    with Session(engine) as s:
        return s.exec(
            select(Subscription).where(Subscription.business_id == business_id)
        ).all()


# --------------------------------------------------------------- the bug
#
# The one that was live. Kept first, and named for what it cost.

def test_a_cancelled_customer_loses_the_modules_they_stopped_paying_for(workspace):
    bid = workspace["business_id"]
    handle_webhook_event(_subscription_event(workspace, "customer.subscription.created"))
    assert _monthly_value(bid) > 0, "the workspace should be worth something while paying"

    handle_webhook_event(_subscription_event(
        workspace, "customer.subscription.deleted", status="canceled"
    ))

    assert _access(bid) == FREE_MODULES, "a cancelled workspace kept billable modules"
    assert _monthly_value(bid) == 0


def test_cancelling_never_locks_someone_out_of_their_own_settings(workspace):
    """
    Revoking access must not revoke the ability to come back and pay. Home,
    settings and notifications stay on: somebody who cancelled by accident, or
    whose card lapsed, needs a door back in.
    """
    bid = workspace["business_id"]
    handle_webhook_event(_subscription_event(workspace, "customer.subscription.created"))
    handle_webhook_event(_subscription_event(
        workspace, "customer.subscription.deleted", status="canceled"
    ))

    still_on = _access(bid)
    assert "settings" in still_on
    assert "home" in still_on
    assert "notifications" in still_on


def test_no_module_key_is_written_that_the_registry_does_not_know(workspace):
    """
    The shape of the original fault, pinned directly. A row for a key nothing
    reads is not a permission — it is a silent no-op that looks like one.
    """
    bid = workspace["business_id"]
    for event in ("customer.subscription.created", "customer.subscription.deleted"):
        handle_webhook_event(_subscription_event(workspace, event))

    with Session(engine) as s:
        rows = s.exec(select(BusinessModule).where(BusinessModule.business_id == bid)).all()
    unknown = sorted({r.module_key for r in rows} - set(ALL_MODULES))
    assert not unknown, f"wrote module rows nothing reads: {unknown}"


# ------------------------------------------------------------- idempotency
#
# Stripe redelivers. Not rarely, and not only on failure.

def test_the_same_event_twice_leaves_one_subscription(workspace):
    bid = workspace["business_id"]
    event = _subscription_event(workspace, "customer.subscription.created")

    handle_webhook_event(event)
    handle_webhook_event(event)

    assert len(_subscriptions(bid)) == 1, "a Stripe retry created a duplicate subscription"


def test_a_duplicate_row_cannot_outlive_a_cancellation(workspace):
    """
    The reason duplicates mattered. Lookup took the first row it found, so a
    cancellation could update one row while a stale 'active' one stayed behind
    for whatever read it next.
    """
    bid = workspace["business_id"]
    with Session(engine) as s:
        for _ in range(2):
            s.add(Subscription(
                business_id=bid,
                stripe_customer_id=workspace["customer"],
                stripe_subscription_id=workspace["subscription"],
                status="active", plan="modular", current_period_end="",
            ))
        s.commit()

    handle_webhook_event(_subscription_event(
        workspace, "customer.subscription.deleted", status="canceled"
    ))

    rows = _subscriptions(bid)
    assert len(rows) == 1
    assert rows[0].status == "canceled"
    assert not any(r.status == "active" for r in rows), "a stale active row survived"


def test_cancelling_twice_is_not_an_error(workspace):
    handle_webhook_event(_subscription_event(workspace, "customer.subscription.created"))
    for _ in range(2):
        handle_webhook_event(_subscription_event(
            workspace, "customer.subscription.deleted", status="canceled"
        ))
    assert _access(workspace["business_id"]) == FREE_MODULES


# ------------------------------------------------------------ the lifecycle

def test_a_trial_is_granted_access(workspace):
    """Somebody on a trial is a customer. Charging first is not the deal."""
    handle_webhook_event(_subscription_event(
        workspace, "customer.subscription.created", status="trialing"
    ))
    assert _monthly_value(workspace["business_id"]) > 0


def test_a_failed_payment_does_not_cut_anyone_off(workspace):
    """
    Stripe retries a failed payment for about two weeks. Revoking on the first
    attempt treats an expired card exactly like a refusal to pay, and does it
    to a restaurant in the middle of service.
    """
    bid = workspace["business_id"]
    handle_webhook_event(_subscription_event(workspace, "customer.subscription.created"))
    before = _access(bid)

    handle_webhook_event(_invoice_event(workspace, "invoice.payment_failed"))

    assert _access(bid) == before, "one failed payment revoked access"
    assert _subscriptions(bid)[0].status == "past_due"


def test_a_recovered_payment_restores_access(workspace):
    bid = workspace["business_id"]
    handle_webhook_event(_subscription_event(workspace, "customer.subscription.created"))
    handle_webhook_event(_invoice_event(workspace, "invoice.payment_failed"))
    handle_webhook_event(_invoice_event(workspace, "invoice.payment_succeeded"))

    assert _subscriptions(bid)[0].status == "active"
    assert _monthly_value(bid) > 0


def test_dunning_giving_up_does_revoke(workspace):
    """
    The other half of the grace period. 'unpaid' is Stripe saying it has
    stopped trying, and that is the point where access ends.
    """
    bid = workspace["business_id"]
    handle_webhook_event(_subscription_event(workspace, "customer.subscription.created"))
    handle_webhook_event(_subscription_event(
        workspace, "customer.subscription.updated", status="unpaid"
    ))
    assert _access(bid) == FREE_MODULES


def test_resubscribing_gives_the_modules_back(workspace):
    """A customer who leaves and returns must not have to rebuild their workspace."""
    bid = workspace["business_id"]
    handle_webhook_event(_subscription_event(workspace, "customer.subscription.created"))
    handle_webhook_event(_subscription_event(
        workspace, "customer.subscription.deleted", status="canceled"
    ))
    assert _access(bid) == FREE_MODULES

    handle_webhook_event(_subscription_event(
        workspace, "customer.subscription.created", status="active"
    ))
    assert _monthly_value(bid) > 0


# -------------------------------------------------------------- addressing

def test_an_event_for_an_unknown_business_changes_nothing(workspace):
    """
    A webhook endpoint is a public URL. An event that cannot be tied to a
    workspace must be a no-op, not a guess.
    """
    bid = workspace["business_id"]
    before = _access(bid)

    handle_webhook_event({
        "type": "customer.subscription.deleted",
        "data": {"object": {"id": "sub_nobody", "customer": "cus_nobody", "status": "canceled"}},
    })

    assert _access(bid) == before


def test_a_subscription_without_metadata_is_matched_by_customer(workspace):
    """
    A subscription created by hand in the Stripe dashboard carries no
    business_id. The customer id is the only thread back, and dropping the
    event would leave somebody paying for nothing.
    """
    bid = workspace["business_id"]
    handle_webhook_event(_subscription_event(workspace, "customer.subscription.created"))
    handle_webhook_event(_subscription_event(
        workspace, "customer.subscription.deleted", status="canceled", metadata={}
    ))
    assert _access(bid) == FREE_MODULES


def test_one_businesss_cancellation_does_not_touch_another(workspace):
    """The tenant boundary, on the path where a mistake bills the wrong people."""
    other = None
    suffix = uuid.uuid4().hex[:6]
    with Session(engine) as s:
        user = UserAccount(username=f"other{suffix}", password_hash="x",
                           role="manager", active=True)
        s.add(user); s.flush()
        business = Business(name=f"Other {suffix}", industry="general", active=True)
        s.add(business); s.flush()
        other = business.id
        set_current_business_id(other)
        try:
            seed_business(s, business, user, role="owner")
            s.commit()
        finally:
            set_current_business_id(1)

    handle_webhook_event(_subscription_event(workspace, "customer.subscription.created"))
    handle_webhook_event(_subscription_event(
        workspace, "customer.subscription.deleted", status="canceled"
    ))

    assert _monthly_value(other) > 0, "cancelling one workspace disabled another"


# ------------------------------------------------------------ period dates

def test_the_renewal_date_is_read_from_the_subscription_item(workspace):
    """
    Newer Stripe API versions moved current_period_end onto each subscription
    item. Reading only the old location gives 0, and 0 becomes 1970 — a
    subscription that renews next month reading as decades expired.
    """
    handle_webhook_event(_subscription_event(
        workspace, "customer.subscription.created",
        current_period_end=None,
        items={"data": [{"current_period_end": 1789000000}]},
    ))
    row = _subscriptions(workspace["business_id"])[0]
    assert row.current_period_end.startswith("20"), f"got {row.current_period_end!r}"


def test_a_missing_renewal_date_is_blank_rather_than_1970(workspace):
    handle_webhook_event(_subscription_event(
        workspace, "customer.subscription.created", current_period_end=None
    ))
    row = _subscriptions(workspace["business_id"])[0]
    assert row.current_period_end == "", f"invented a date: {row.current_period_end!r}"
    assert "1970" not in row.current_period_end


def test_an_unparseable_renewal_date_does_not_raise(workspace):
    handle_webhook_event(_subscription_event(
        workspace, "customer.subscription.created", current_period_end="not-a-timestamp"
    ))
    assert _subscriptions(workspace["business_id"])[0].current_period_end == ""


# ------------------------------------------------------------ agreement
#
# Two files deciding separately what counts as a paying customer is how the
# module registries diverged in the first place.

def test_billing_and_the_webhook_agree_on_who_is_paying():
    assert ACTIVE_STATUSES == WORKING_STATES


def test_no_status_is_both_alive_and_dead():
    assert not (ACTIVE_STATUSES & DEAD_STATUSES)


def test_an_unrecognised_event_is_ignored_quietly(workspace):
    """Stripe sends far more event types than these. The rest must be inert."""
    bid = workspace["business_id"]
    before = _access(bid)
    handle_webhook_event({"type": "charge.dispute.created", "data": {"object": {}}})
    handle_webhook_event({})
    assert _access(bid) == before
