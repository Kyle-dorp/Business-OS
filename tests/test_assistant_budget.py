"""
The Scheduling AI page, and what it costs.

There are two AI surfaces in the product: the newer agent behind "Ask", and the
older scheduling assistant behind "Scheduling AI". The agent was carefully
budgeted — a monthly allowance, a hard ceiling, overage metered to Stripe. The
assistant called Anthropic with no accounting of any kind.

That made the older page the cheap way to spend somebody else's key, and it was
the one page where the bill was invisible. These tests pin the fix: one
workspace, one allowance, drawn down by whichever page the customer happens to
use.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlmodel import Session, select

from backend.app import ai_service
from backend.app.ai_agent import (
    HARD_CEILING_MULTIPLIER,
    INCLUDED_INPUT_TOKENS,
    INCLUDED_OUTPUT_TOKENS,
    _check_budget,
    _month_usage,
    _record_usage,
)
from backend.app.database import engine
from backend.app.models import ApiUsage, Business
from backend.app.tenancy import set_current_business_id

INCLUDED = INCLUDED_INPUT_TOKENS + INCLUDED_OUTPUT_TOKENS


@pytest.fixture
def business_id():
    with Session(engine) as s:
        business = Business(
            name=f"Budget {uuid.uuid4().hex[:6]}", industry="general", active=True
        )
        s.add(business)
        s.commit()
        s.refresh(business)
        bid = business.id
    yield bid
    set_current_business_id(1)


# ------------------------------------------------------- the shared allowance

def test_the_two_ai_pages_draw_on_one_allowance(business_id):
    """
    A customer does not care which page spent their tokens. Two separate
    budgets would mean a workspace could quietly spend twice what it is sold.
    """
    with Session(engine) as s:
        _record_usage(s, business_id, 10_000, 2_000, feature="agent")
        _record_usage(s, business_id, 5_000, 1_000, feature="assistant")

    with Session(engine) as s:
        used, _ = _month_usage(s, business_id)
    assert used == 18_000, "the two surfaces are not sharing a pool"


def test_assistant_usage_is_attributed_to_the_assistant(business_id):
    """
    Shared pool, separate lines. Without this there is no way to answer
    "which half of the bill is the scheduling page?"
    """
    with Session(engine) as s:
        _record_usage(s, business_id, 3_000, 500, feature="assistant")

    with Session(engine) as s:
        rows = s.exec(
            select(ApiUsage).where(
                ApiUsage.business_id == business_id,
                ApiUsage.feature == "assistant",
            )
        ).all()
    assert rows, "assistant usage was not recorded under its own feature"
    assert sum(r.tokens_used for r in rows) == 3_500


def test_the_workspace_total_moves_too(business_id):
    with Session(engine) as s:
        before = s.get(Business, business_id).claude_api_tokens_used
        _record_usage(s, business_id, 1_000, 200, feature="assistant")

    with Session(engine) as s:
        after = s.get(Business, business_id).claude_api_tokens_used
    assert after - before == 1_200


# ------------------------------------------------------------- the ceiling

def test_a_workspace_inside_its_allowance_is_not_stopped(business_id):
    with Session(engine) as s:
        _record_usage(s, business_id, 20_000, 2_000, feature="assistant")
        _check_budget(s, business_id)   # must not raise


def test_spending_draws_the_wallet_down_by_what_the_call_cost(business_id):
    """
    The allowance is money now, not tokens. 650,000 tokens was unreadable —
    measured, it bought six questions on a large workspace and sixty-five on a
    small one — and a number nobody can convert into questions cannot be
    budgeted against by the person paying for it.
    """
    from backend.app.ai_pricing import cost_milli
    from backend.app.ai_wallet import get_wallet

    from backend.app.ai_agent import MODEL

    expected = cost_milli(MODEL, input_tokens=100_000, output_tokens=5_000)

    with Session(engine) as s:
        before = get_wallet(s, business_id).spent_milli
        _record_usage(s, business_id, 100_000, 5_000, feature="assistant")
        after = get_wallet(s, business_id).spent_milli

    assert after - before == expected


def test_the_last_question_of_the_month_is_allowed_to_finish(business_id):
    """
    The check runs before a request and the charge after it, so a call that
    empties the wallet completes rather than being cut off mid-sentence. Being
    cut off costs us the tokens anyway and gives the customer nothing for them.
    """
    from backend.app.ai_wallet import get_wallet, remaining_milli, spend

    with Session(engine) as s:
        wallet = get_wallet(s, business_id)
        spend(s, business_id, remaining_milli(wallet) - 1)
        _check_budget(s, business_id)   # one unit left: still allowed

        # And that call is permitted to overshoot.
        _record_usage(s, business_id, 50_000, 1_000, feature="assistant")
        assert remaining_milli(get_wallet(s, business_id)) == 0


def test_a_runaway_is_stopped_when_the_wallet_is_empty(business_id):
    """
    The ceiling exists for the loop that does not stop. Metering without one
    turns a bug into a five-figure invoice. 402 rather than 429 — this is not
    a rate limit, it is a balance.
    """
    from backend.app.ai_wallet import get_wallet, remaining_milli, spend

    with Session(engine) as s:
        spend(s, business_id, remaining_milli(get_wallet(s, business_id)))

    with Session(engine) as s, pytest.raises(HTTPException) as exc:
        _check_budget(s, business_id)
    assert exc.value.status_code == 402


def test_the_empty_message_says_the_rest_still_works(business_id):
    """
    A paused assistant is not an outage, and the wording has to say so. This
    assertion predates the wallet and survived the rewrite — the first version
    of the new message dropped the sentence and this caught it.
    """
    from backend.app.ai_wallet import get_wallet, remaining_milli, spend

    with Session(engine) as s:
        spend(s, business_id, remaining_milli(get_wallet(s, business_id)))

    with Session(engine) as s, pytest.raises(HTTPException) as exc:
        _check_budget(s, business_id)
    assert "keeps working" in exc.value.detail


def test_the_message_says_credit_can_be_bought(business_id):
    """
    The old ceiling could only stop. The first thing a heavy user saw was the
    feature switching off with nothing to do about it.
    """
    from backend.app.ai_wallet import get_wallet, remaining_milli, spend

    with Session(engine) as s:
        spend(s, business_id, remaining_milli(get_wallet(s, business_id)))
    with Session(engine) as s, pytest.raises(HTTPException) as exc:
        _check_budget(s, business_id)
    assert "credit" in exc.value.detail.lower()
    assert "no markup" in exc.value.detail.lower()


def test_purchased_credit_survives_the_month_rolling_over(business_id):
    """
    The allowance resets. Money somebody paid for does not evaporate because a
    calendar page turned — that is the difference between a plan and a debt.
    """
    from datetime import date

    from backend.app.ai_wallet import add_credit, get_wallet

    with Session(engine) as s:
        add_credit(s, business_id, 300_000)          # $3 bought
        wallet = get_wallet(s, business_id)
        wallet.spent_milli = wallet.included_milli   # allowance used up
        s.add(wallet)
        s.commit()

        next_month = date(2099, 1, 15)
        rolled = get_wallet(s, business_id, today=next_month)

    assert rolled.spent_milli == 0, "the meter should reset"
    assert rolled.included_milli == 500_000, "the allowance should come back"
    assert rolled.topped_up_milli == 300_000, "purchased credit must not be wiped"


def test_one_workspace_cannot_spend_anothers_allowance(business_id):
    """The tenant boundary, on the axis that costs money directly."""
    with Session(engine) as s:
        other = Business(name="Frugal", industry="general", active=True)
        s.add(other)
        s.commit()
        s.refresh(other)
        other_id = other.id

    with Session(engine) as s:
        _record_usage(s, business_id, int(INCLUDED * HARD_CEILING_MULTIPLIER) + 1, 0,
                      feature="assistant")

    with Session(engine) as s:
        _check_budget(s, other_id)      # the neighbour is unaffected
        used, _ = _month_usage(s, other_id)
    assert used == 0


# ----------------------------------------------------------- the call itself

def test_the_assistant_reports_what_it_spent():
    """
    decide_with_ai returns its token cost as a third value. Without it the
    endpoint has nothing to record, which is how this went uncounted.
    """
    decision, used_ai, tokens = ai_service.decide_with_ai("add an employee", {})
    assert isinstance(tokens, tuple)
    assert len(tokens) == 2


def test_an_unconfigured_assistant_costs_nothing():
    """
    conftest strips ANTHROPIC_API_KEY, so this is the fallback path. It never
    reaches Anthropic, so recording usage for it would bill a customer for
    keyword matching.
    """
    decision, used_ai, tokens = ai_service.decide_with_ai("add an employee", {})
    assert used_ai is False
    assert tokens == (0, 0)
    assert decision.reply, "the fallback still has to answer"


def test_the_fallback_still_proposes_something():
    """The page must work without an API key at all, or a misconfigured
    deployment looks like a broken product."""
    decision, _, _ = ai_service.decide_with_ai("regenerate the schedule", {})
    assert isinstance(decision, ai_service.AssistantDecision)


def test_both_surfaces_default_to_the_same_model():
    """
    They were on different defaults — the agent on claude-sonnet-5 and the
    assistant still pinned to a superseded one. Two models means two different
    behaviours for one product, and only one of them gets attention.
    """
    import inspect

    from backend.app.ai_agent import MODEL

    source = inspect.getsource(ai_service.decide_with_ai)
    assert MODEL in source, f"the assistant does not default to {MODEL}"


# ------------------------------------------------------------ the real route
#
# Everything above tests the budget machinery. This tests that the endpoint
# actually consults it — which is the part that was missing, and the part a
# unit test of the helpers would happily pass while the route stayed uncapped.

def test_the_chat_endpoint_refuses_past_the_ceiling(client):
    from backend.app.auth import hash_password
    from backend.app.models import UserAccount

    suffix = uuid.uuid4().hex[:6]
    creds = {"username": f"cap{suffix}", "password": "a-test-password-123"}

    with Session(engine) as s:
        user = UserAccount(
            username=creds["username"],
            password_hash=hash_password(creds["password"]),
            role="manager",
            active=True,
        )
        s.add(user)
        s.flush()
        business = Business(name=f"Cap {suffix}", industry="general", active=True)
        s.add(business)
        s.flush()
        bid = business.id
        set_current_business_id(bid)
        try:
            from backend.app.platform import seed_business

            seed_business(s, business, user, role="owner")
            s.commit()
        finally:
            set_current_business_id(1)

    login = client.post("/auth/login", json=creds)
    assert login.status_code == 200, login.text
    headers = {
        "Authorization": f"Bearer {login.json()['token']}",
        "X-Business-Id": str(bid),
    }

    within = client.post("/assistant/chat", headers=headers, json={"message": "hello"})
    assert within.status_code == 200, within.text

    from backend.app.ai_wallet import get_wallet, remaining_milli, spend

    with Session(engine) as s:
        spend(s, bid, remaining_milli(get_wallet(s, bid)))

    over = client.post("/assistant/chat", headers=headers, json={"message": "hello again"})
    assert over.status_code == 402, "the endpoint ignored the wallet"
    assert "keeps working" in over.json()["detail"]
