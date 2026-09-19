"""
The assistant wallet.

The allowance used to be 650,000 tokens with a hard ceiling at five times it.
Nobody knows what 650,000 tokens buys. Measured against the real context sizes
it was about sixty-five questions on a small workspace and six on a large one —
and there was no way to buy more, so the first thing a heavy user saw was the
feature switching off.

It is money now: $5 a month at what we pay Anthropic, top-ups at the same rate,
nothing marked up. "Pay for what you use" is only true if the number the
customer pays is the number we pay, so these tests check the arithmetic against
the published per-model rates rather than against a stored constant.

The three balances are the part worth guarding. A single balance would have to
choose between wiping purchased credit every month and never resetting the free
allowance, and both of those are somebody's money going the wrong way.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlmodel import Session, select

from backend.app.ai_pricing import (
    MILLI_PER_DOLLAR,
    MODEL_RATES,
    cost_milli,
    dollars,
    rates_for,
)
from backend.app.ai_wallet import (
    INCLUDED_MILLI,
    AssistantOff,
    UserCapReached,
    WalletEmpty,
    add_credit,
    check_can_spend,
    get_wallet,
    remaining_milli,
    spend,
    summary,
)
from backend.app.database import engine
from backend.app.models import AiWallet, ApiUsage
from backend.app.tenancy import set_current_business_id


@pytest.fixture
def business_id(client):
    suffix = uuid.uuid4().hex[:6]
    response = client.post("/auth/signup", json={
        "username": f"wal{suffix}",
        "password": "a-real-password-123",
        "business_name": f"Wallet {suffix}",
    })
    assert response.status_code == 200, response.text
    bid = response.json()["business"]["id"]
    set_current_business_id(bid)
    yield bid
    set_current_business_id(1)


# ===========================================================================
# What a call costs
# ===========================================================================

def test_the_price_is_the_published_price():
    """
    Not a stored average. If Anthropic's rates move and this table does not,
    the customer is being charged last quarter's price for this quarter's
    tokens — in whichever direction happens to be wrong.
    """
    sonnet = rates_for("claude-sonnet-5")
    assert (sonnet.input, sonnet.output) == (2.00, 10.00)

    opus = rates_for("claude-opus-5")
    assert (opus.input, opus.output) == (5.00, 25.00)


def test_a_million_input_tokens_costs_the_input_rate():
    for name, rate in MODEL_RATES.items():
        milli = cost_milli(name, input_tokens=1_000_000)
        assert dollars(milli) == pytest.approx(rate.input, abs=0.001), name


def test_cached_input_is_a_tenth_of_the_price():
    """The reason caching is worth doing at all, and the number it turns on."""
    fresh = cost_milli("claude-sonnet-5", input_tokens=100_000)
    cached = cost_milli("claude-sonnet-5", cache_read_tokens=100_000)
    assert cached == pytest.approx(fresh * 0.1, rel=0.01)


def test_a_call_that_cost_something_never_records_as_zero():
    """
    An employee question costs a fraction of a cent. Rounding those to zero
    would leave the meter reading nothing all month and then jumping.
    """
    assert cost_milli("claude-sonnet-5", input_tokens=1, output_tokens=1) >= 1


def test_nothing_spent_is_nothing_charged():
    assert cost_milli("claude-sonnet-5") == 0


def test_an_unknown_model_falls_back_rather_than_failing():
    """
    ANTHROPIC_MODEL is an environment variable. A model newer than this table
    should undercharge for a month, not take the assistant down — one is
    recoverable and the other is an outage on the feature the product is sold
    on.
    """
    assert rates_for("claude-something-not-released-yet") == rates_for("claude-sonnet-5")


def test_the_cost_is_an_integer():
    """It lands in an integer column. A float here becomes a float there."""
    assert isinstance(cost_milli("claude-sonnet-5", input_tokens=9428, output_tokens=600), int)


# ===========================================================================
# The three balances
# ===========================================================================

def test_a_new_workspace_starts_with_five_dollars(business_id):
    with Session(engine) as s:
        wallet = get_wallet(s, business_id)
    assert wallet.included_milli == INCLUDED_MILLI
    assert dollars(wallet.included_milli) == 5.0
    assert wallet.spent_milli == 0


def test_spending_comes_out_of_the_included_allowance_first(business_id):
    with Session(engine) as s:
        add_credit(s, business_id, 200_000)          # $2 bought
        spend(s, business_id, 100_000)               # $1 used
        wallet = get_wallet(s, business_id)

    assert wallet.topped_up_milli == 200_000, "a purchase should not be consumed first"
    assert wallet.spent_milli == 100_000
    assert dollars(remaining_milli(wallet)) == 6.0   # 5 + 2 - 1


def test_the_allowance_resets_and_the_purchase_does_not(business_id):
    """
    The distinction the whole model rests on. An allowance is what the plan
    gives each month; a top-up is money somebody handed over, and it does not
    evaporate because a calendar page turned.
    """
    with Session(engine) as s:
        add_credit(s, business_id, 400_000)
        spend(s, business_id, INCLUDED_MILLI)
        rolled = get_wallet(s, business_id, today=date(2099, 6, 1))

    assert rolled.spent_milli == 0
    assert rolled.included_milli == INCLUDED_MILLI
    assert rolled.topped_up_milli == 400_000


def test_rolling_the_month_happens_on_read(business_id):
    """
    There is no cron in this deployment. A balance that is only correct if a
    background job ran is wrong the first time it does not.
    """
    with Session(engine) as s:
        wallet = get_wallet(s, business_id)
        wallet.period = "1999-01"
        wallet.spent_milli = INCLUDED_MILLI
        s.add(wallet)
        s.commit()

        rolled = get_wallet(s, business_id)

    assert rolled.period != "1999-01"
    assert rolled.spent_milli == 0


def test_a_balance_never_goes_negative(business_id):
    with Session(engine) as s:
        spend(s, business_id, INCLUDED_MILLI * 3)
        assert remaining_milli(get_wallet(s, business_id)) == 0


# ===========================================================================
# Who may spend it
# ===========================================================================

def test_a_manager_may_ask_while_there_is_credit(business_id):
    with Session(engine) as s:
        check_can_spend(s, business_id)      # must not raise


def test_an_empty_wallet_stops_the_next_question(business_id):
    with Session(engine) as s:
        spend(s, business_id, INCLUDED_MILLI)
        with pytest.raises(WalletEmpty):
            check_can_spend(s, business_id)


def test_staff_are_off_until_the_workspace_says_otherwise(business_id):
    with Session(engine) as s:
        with pytest.raises(AssistantOff):
            check_can_spend(s, business_id, user_id=1, is_employee=True)


def test_a_per_user_cap_stops_one_person_without_stopping_the_workspace(business_id):
    with Session(engine) as s:
        wallet = get_wallet(s, business_id)
        wallet.employees_enabled = True
        wallet.per_user_cap_milli = 25_000            # 25 cents
        s.add(wallet)
        s.add(ApiUsage(business_id=business_id, date=date.today().isoformat(),
                       feature="my-assistant", user_id=7, vendor_cost_milli=25_000))
        s.commit()

        with pytest.raises(UserCapReached):
            check_can_spend(s, business_id, user_id=7, is_employee=True)

        # Somebody else is unaffected, and so is the workspace total.
        check_can_spend(s, business_id, user_id=8, is_employee=True)


def test_no_cap_means_no_cap(business_id):
    """Zero is "unlimited", not "nothing" — a cap of nothing would lock everybody out."""
    with Session(engine) as s:
        wallet = get_wallet(s, business_id)
        wallet.employees_enabled = True
        wallet.per_user_cap_milli = 0
        s.add(wallet)
        s.add(ApiUsage(business_id=business_id, date=date.today().isoformat(),
                       feature="my-assistant", user_id=9, vendor_cost_milli=400_000))
        s.commit()

        check_can_spend(s, business_id, user_id=9, is_employee=True)   # must not raise


def test_the_manager_is_not_subject_to_the_staff_cap(business_id):
    """The cap exists so staff cannot drain the month out from under the owner."""
    with Session(engine) as s:
        wallet = get_wallet(s, business_id)
        wallet.employees_enabled = True
        wallet.per_user_cap_milli = 1
        s.add(wallet)
        s.add(ApiUsage(business_id=business_id, date=date.today().isoformat(),
                       feature="agent", user_id=3, vendor_cost_milli=100_000))
        s.commit()

        check_can_spend(s, business_id, user_id=3, is_employee=False)   # must not raise


# ===========================================================================
# What the meter says
# ===========================================================================

def test_the_summary_is_in_dollars_not_hundred_thousandths(business_id):
    """
    Storing in thousandths of a cent is an accuracy decision. Nobody should
    have to read one.
    """
    with Session(engine) as s:
        spend(s, business_id, 123_456)
        out = summary(s, business_id)

    assert out["included"] == 5.0
    assert out["spent"] == 1.23456
    assert out["remaining"] == pytest.approx(3.76544)
    assert 0 < out["percent_used"] < 100


def test_the_summary_tells_a_person_their_own_share(business_id):
    with Session(engine) as s:
        s.add(ApiUsage(business_id=business_id, date=date.today().isoformat(),
                       feature="my-assistant", user_id=11, vendor_cost_milli=40_000))
        s.commit()
        out = summary(s, business_id, user_id=11)

    assert out["your_spend"] == 0.4


def test_the_summary_offers_somewhere_to_buy_more(business_id):
    with Session(engine) as s:
        out = summary(s, business_id)
    assert out["topup_choices"], "an empty wallet with nothing to do about it is the old design"


# ===========================================================================
# Tenancy
# ===========================================================================

def test_one_workspace_cannot_spend_anothers_credit(client):
    first = client.post("/auth/signup", json={
        "username": f"a{uuid.uuid4().hex[:6]}", "password": "a-real-password-123",
        "business_name": "First"}).json()["business"]["id"]
    second = client.post("/auth/signup", json={
        "username": f"b{uuid.uuid4().hex[:6]}", "password": "a-real-password-123",
        "business_name": "Second"}).json()["business"]["id"]

    try:
        with Session(engine) as s:
            spend(s, first, INCLUDED_MILLI)
            assert remaining_milli(get_wallet(s, first)) == 0
            assert remaining_milli(get_wallet(s, second)) == INCLUDED_MILLI
            check_can_spend(s, second)      # must not raise
    finally:
        set_current_business_id(1)


def test_each_workspace_gets_its_own_wallet_row(client):
    ids = []
    for _ in range(2):
        ids.append(client.post("/auth/signup", json={
            "username": f"w{uuid.uuid4().hex[:6]}", "password": "a-real-password-123",
            "business_name": "W"}).json()["business"]["id"])
    try:
        with Session(engine) as s:
            for bid in ids:
                get_wallet(s, bid)
            rows = s.exec(select(AiWallet).where(AiWallet.business_id.in_(ids))).all()
        assert len({row.business_id for row in rows}) == 2
    finally:
        set_current_business_id(1)
