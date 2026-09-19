"""
Buying assistant credit.

Top-ups are a one-off payment, not a plan change. Somebody who needs another
$10 this month should not be signing up to $10 a month forever.

The parts worth guarding are the ones where money and state meet:

  nothing is credited on the redirect, only on the webhook — crediting when
  somebody lands on a success URL credits anybody who can type one

  the same Stripe event credits once, however many times it arrives — Stripe
  redelivers routinely, on its own retry schedule and again if the endpoint is
  slow, and a $50 top-up credited three times is a bug only the customer finds

  a subscription event must not be mistaken for a top-up, and vice versa
"""

from __future__ import annotations

import uuid

import pytest
from sqlmodel import Session, select

from backend.app.ai_pricing import dollars
from backend.app.ai_wallet import TOPUP_CHOICES_DOLLARS, credit_from_checkout, get_wallet
from backend.app.database import engine
from backend.app.models import ApiUsage
from backend.app.tenancy import set_current_business_id


@pytest.fixture
def business_id(client):
    suffix = uuid.uuid4().hex[:6]
    response = client.post("/auth/signup", json={
        "username": f"top{suffix}", "password": "a-real-password-123",
        "business_name": f"Topup {suffix}",
    })
    assert response.status_code == 200, response.text
    bid = response.json()["business"]["id"]
    set_current_business_id(bid)
    yield bid
    set_current_business_id(1)


def _event(business_id: int, amount: int, session_id: str = "cs_test_1") -> dict:
    """A checkout.session.completed payload, shaped as Stripe sends it."""
    return {
        "id": session_id,
        "payment_status": "paid",
        "metadata": {
            "kind": "ai_topup",
            "business_id": str(business_id),
            "dollars": str(amount),
        },
    }


# ===========================================================================
# Crediting
# ===========================================================================

def test_a_paid_topup_credits_the_wallet(business_id):
    with Session(engine) as s:
        before = get_wallet(s, business_id).topped_up_milli
        assert credit_from_checkout(s, _event(business_id, 10)) is True
        after = get_wallet(s, business_id).topped_up_milli

    assert dollars(after - before) == 10.0


def test_the_same_event_twice_credits_once(business_id):
    """
    Stripe redelivers events routinely. Crediting a $50 top-up three times
    because of a retry is a bug nobody finds until a customer says their credit
    is wrong in their favour, and by then it has happened to everybody.
    """
    with Session(engine) as s:
        credit_from_checkout(s, _event(business_id, 25, "cs_test_repeat"))
        credit_from_checkout(s, _event(business_id, 25, "cs_test_repeat"))
        credit_from_checkout(s, _event(business_id, 25, "cs_test_repeat"))
        wallet = get_wallet(s, business_id)

    assert dollars(wallet.topped_up_milli) == 25.0


def test_two_different_payments_both_credit(business_id):
    """The other half: idempotency must not swallow a genuine second purchase."""
    with Session(engine) as s:
        credit_from_checkout(s, _event(business_id, 5, "cs_one"))
        credit_from_checkout(s, _event(business_id, 5, "cs_two"))
        wallet = get_wallet(s, business_id)

    assert dollars(wallet.topped_up_milli) == 10.0


def test_an_unpaid_session_credits_nothing(business_id):
    event = _event(business_id, 50)
    event["payment_status"] = "unpaid"

    with Session(engine) as s:
        assert credit_from_checkout(s, event) is False
        assert get_wallet(s, business_id).topped_up_milli == 0


def test_a_subscription_checkout_is_not_a_topup(business_id):
    """
    Both arrive as checkout.session.completed. Only the metadata says which is
    which, and a subscription treated as a top-up hands out free credit.

    The metadata here is exactly what billing.checkout sends.
    """
    event = {"id": "cs_sub", "payment_status": "paid",
             "metadata": {"business_id": str(business_id), "module_count": "10"}}

    with Session(engine) as s:
        assert credit_from_checkout(s, event) is False
        assert get_wallet(s, business_id).topped_up_milli == 0


def test_it_is_the_kind_that_decides_and_not_a_missing_field(business_id):
    """
    The test above passes for the wrong reason on its own. A subscription
    checkout has no `dollars` in its metadata, so removing the `kind` check
    entirely still leaves it failing on a KeyError — protected by accident
    rather than by the check that is supposed to protect it.

    This one carries every field a top-up needs and only gets the kind wrong,
    so the only thing that can refuse it is the check being tested.
    """
    event = {
        "id": "cs_not_a_topup",
        "payment_status": "paid",
        "metadata": {
            "kind": "something_else",
            "business_id": str(business_id),
            "dollars": "50",
        },
    }

    with Session(engine) as s:
        assert credit_from_checkout(s, event) is False
        assert get_wallet(s, business_id).topped_up_milli == 0


def test_a_malformed_event_credits_nothing(business_id):
    """Better to credit nothing and be asked than to guess at an amount."""
    with Session(engine) as s:
        for broken in (
            {"id": "a", "metadata": {"kind": "ai_topup"}},
            {"id": "b", "metadata": {"kind": "ai_topup", "business_id": "x", "dollars": "5"}},
            {"id": "c", "metadata": {"kind": "ai_topup", "business_id": "1", "dollars": "lots"}},
            {"metadata": {"kind": "ai_topup"}},
        ):
            assert credit_from_checkout(s, broken) is False


def test_the_credit_leaves_a_receipt(business_id):
    """
    Findable next to the spending it paid for, rather than in a table of its
    own — and the row doubles as the record that stops it being credited twice.
    """
    with Session(engine) as s:
        credit_from_checkout(s, _event(business_id, 10, "cs_receipt"))
        rows = s.exec(
            select(ApiUsage).where(ApiUsage.feature == "topup:cs_receipt")
        ).all()

    assert len(rows) == 1
    assert rows[0].cost_cents == -1000, "a credit is negative on the ledger"
    assert rows[0].vendor_cost_milli == 0, "buying credit costs us no tokens"


def test_credit_from_a_topup_does_not_expire(business_id):
    """
    The claim on the checkout page. It has to survive the month rolling over or
    it is not true.
    """
    from datetime import date

    with Session(engine) as s:
        credit_from_checkout(s, _event(business_id, 25, "cs_lasting"))
        rolled = get_wallet(s, business_id, today=date(2099, 3, 1))

    assert dollars(rolled.topped_up_milli) == 25.0


# ===========================================================================
# Starting one
# ===========================================================================

def test_only_an_owner_or_admin_can_buy(client):
    """Anybody who can spend the wallet should not be able to charge the card."""
    import inspect

    from backend.app.ai_wallet import start_topup

    source = inspect.getsource(start_topup)
    assert "SPEND_ROLES" in source
    assert "Only an owner or admin" in source


def test_the_amount_must_be_one_of_the_offered_ones():
    """
    An arbitrary amount is an arbitrary Stripe charge built from a request
    body, which is a shape worth never having.
    """
    import inspect

    from backend.app.ai_wallet import start_topup

    assert "TOPUP_CHOICES_DOLLARS" in inspect.getsource(start_topup)
    assert TOPUP_CHOICES_DOLLARS, "there has to be something to buy"


def test_nothing_is_credited_when_checkout_starts():
    """
    The redirect is not proof of payment. Crediting there credits anybody who
    can type the success URL.
    """
    import inspect

    from backend.app.ai_wallet import start_topup

    source = inspect.getsource(start_topup)
    assert "add_credit" not in source
    assert "success_url" in source


def test_the_price_is_the_credit(client):
    """
    Sold at cost, like the allowance. $10 buys $10 — if the charge and the
    credit ever diverge, "no markup" becomes a false claim on a payment page.
    """
    import inspect

    from backend.app.ai_wallet import start_topup

    source = inspect.getsource(start_topup)
    assert '"unit_amount": payload.dollars * 100' in source
    assert '"dollars": str(payload.dollars)' in source


def test_the_webhook_knows_about_the_event(client):
    """
    checkout.session.completed has to be registered in Stripe as well, or the
    payment succeeds and the credit never arrives — the same failure shape the
    subscription webhook was built to avoid.
    """
    import inspect

    from backend.app import stripe_service

    source = inspect.getsource(stripe_service.handle_webhook_event)
    assert "checkout.session.completed" in source
