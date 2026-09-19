"""
The assistant wallet: what a workspace has left to spend, in money.

The allowance used to be a token count with a hard ceiling at five times it.
That had two problems. It was unreadable — nobody knows what 650,000 tokens
buys, and the answer turned out to be six questions on a large workspace and
sixty-five on a small one. And it could only ever stop; there was no way to buy
more, so the first thing a heavy user saw was the feature switching off.

It is money now. Every workspace gets $5 at the price we pay Anthropic, and
can buy more at the same price. Nothing is marked up, which is the whole pitch:
"pay for what you use" is only true if the number you are paying is the number
we are paying.

Three balances, not one
-----------------------
    included   what the plan gives. Resets on the first.
    topped_up  what they bought. Does NOT reset — money somebody paid for does
               not evaporate because a calendar page turned.
    spent      what has gone, taken from included first so the free allowance
               is always used before anything purchased.

A single balance would have to choose between resetting a customer's purchased
credit and never resetting the free allowance, and both are wrong.

Per-user caps
-------------
A workspace that switches the assistant on for staff can also say how much any
one person may spend. That is not a cost control for us — the wallet already
bounds the total — it is so that one curious employee cannot drain the month
in an afternoon and leave the manager without it.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from sqlmodel import Session, func, select

from backend.app.ai_pricing import MILLI_PER_DOLLAR, dollars
from backend.app.models import AiWallet, ApiUsage

# What every workspace gets each month, at cost. $5.00.
INCLUDED_MILLI = 5 * MILLI_PER_DOLLAR

# What a top-up buys. Same rate — no markup, by design.
TOPUP_CHOICES_DOLLARS = (5, 10, 25, 50)


def current_period(today: Optional[date] = None) -> str:
    return (today or date.today()).strftime("%Y-%m")


def get_wallet(session: Session, business_id: int, *, today: Optional[date] = None) -> AiWallet:
    """
    The workspace's wallet, rolled to the current month if it has fallen behind.

    Rolling on read rather than on a schedule: there is no cron in this
    deployment, and a balance that is only correct if a background job ran is a
    balance that is wrong the first time the job does not.
    """
    period = current_period(today)
    wallet = session.exec(
        select(AiWallet).where(AiWallet.business_id == business_id)
    ).first()

    if wallet is None:
        wallet = AiWallet(
            business_id=business_id,
            period=period,
            included_milli=INCLUDED_MILLI,
        )
        session.add(wallet)
        session.commit()
        session.refresh(wallet)
        return wallet

    if wallet.period != period:
        # New month: the allowance comes back and the meter resets. Purchased
        # credit is untouched on purpose.
        wallet.period = period
        wallet.included_milli = INCLUDED_MILLI
        wallet.spent_milli = 0
        session.add(wallet)
        session.commit()
        session.refresh(wallet)

    return wallet


def remaining_milli(wallet: AiWallet) -> int:
    return max(0, wallet.included_milli + wallet.topped_up_milli - wallet.spent_milli)


def spent_by_user_milli(session: Session, business_id: int, user_id: int,
                        *, today: Optional[date] = None) -> int:
    """This user's share of the month, for the per-user cap."""
    prefix = current_period(today)
    total = session.exec(
        select(func.coalesce(func.sum(ApiUsage.vendor_cost_milli), 0)).where(
            ApiUsage.business_id == business_id,
            ApiUsage.user_id == user_id,
            ApiUsage.date.startswith(prefix),
        )
    ).one()
    return int(total or 0)


class WalletEmpty(Exception):
    """The workspace has nothing left. Carries the sentence to show somebody."""

    def __init__(self, wallet: AiWallet):
        self.wallet = wallet
        super().__init__(
            "This workspace has used its assistant credit for the month. "
            "Everything else keeps working — only the assistant pauses. Add "
            "credit in Settings to carry on: it is charged at what we pay for "
            "it, with no markup, and anything you buy does not expire."
        )


class UserCapReached(Exception):
    """One person hit their own limit. The workspace still has credit."""

    def __init__(self, cap_milli: int):
        self.cap_milli = cap_milli
        super().__init__(
            f"You have used your ${dollars(cap_milli):.2f} of assistant credit "
            "for this month. Everything else keeps working — your manager can "
            "raise it in Settings."
        )


class AssistantOff(Exception):
    """The workspace has not switched the assistant on for staff."""

    def __init__(self) -> None:
        super().__init__(
            "The assistant is not switched on for staff in this workspace. "
            "Your manager can enable it in Settings."
        )


def check_can_spend(
    session: Session,
    business_id: int,
    *,
    user_id: Optional[int] = None,
    is_employee: bool = False,
    today: Optional[date] = None,
) -> AiWallet:
    """
    Whether this person may ask a question right now.

    Checked before the call rather than after, because the alternative is
    discovering the wallet is empty by spending money that is not there.
    """
    wallet = get_wallet(session, business_id, today=today)

    if is_employee and not wallet.employees_enabled:
        raise AssistantOff()

    if remaining_milli(wallet) <= 0:
        raise WalletEmpty(wallet)

    if is_employee and wallet.per_user_cap_milli > 0 and user_id is not None:
        used = spent_by_user_milli(session, business_id, user_id, today=today)
        if used >= wallet.per_user_cap_milli:
            raise UserCapReached(wallet.per_user_cap_milli)

    return wallet


def spend(session: Session, business_id: int, milli: int, *,
          today: Optional[date] = None) -> AiWallet:
    """
    Record what a call cost.

    Allowed to overshoot the balance by the cost of one call. The check runs
    before the request and the charge after it, so the last question of the
    month can finish rather than being cut off mid-sentence — which would cost
    us the tokens anyway and give the customer nothing for them.
    """
    wallet = get_wallet(session, business_id, today=today)
    wallet.spent_milli += max(0, milli)
    session.add(wallet)
    session.commit()
    session.refresh(wallet)
    return wallet


def add_credit(session: Session, business_id: int, milli: int) -> AiWallet:
    """Credit a top-up. Never resets, never expires."""
    wallet = get_wallet(session, business_id)
    wallet.topped_up_milli += max(0, milli)
    session.add(wallet)
    session.commit()
    session.refresh(wallet)
    return wallet


def summary(session: Session, business_id: int, *, user_id: Optional[int] = None,
            today: Optional[date] = None) -> dict:
    """
    Everything a usage meter needs, in dollars rather than thousandths.

    The interface should never have to know this is stored in hundred-thousandths
    of a dollar; that is an accuracy decision, not something to make a customer
    read.
    """
    wallet = get_wallet(session, business_id, today=today)
    left = remaining_milli(wallet)
    total = wallet.included_milli + wallet.topped_up_milli

    out = {
        "period": wallet.period,
        "included": dollars(wallet.included_milli),
        "topped_up": dollars(wallet.topped_up_milli),
        "spent": dollars(wallet.spent_milli),
        "remaining": dollars(left),
        "percent_used": round(wallet.spent_milli / total * 100, 1) if total else 0.0,
        "employees_enabled": wallet.employees_enabled,
        "per_user_cap": dollars(wallet.per_user_cap_milli),
        "topup_choices": list(TOPUP_CHOICES_DOLLARS),
    }

    if user_id is not None:
        used = spent_by_user_milli(session, business_id, user_id, today=today)
        out["your_spend"] = dollars(used)
        if wallet.per_user_cap_milli > 0:
            out["your_cap"] = dollars(wallet.per_user_cap_milli)
            out["your_remaining"] = dollars(max(0, wallet.per_user_cap_milli - used))

    return out


# ===========================================================================
# The endpoints behind the meter
# ===========================================================================

from fastapi import APIRouter, Depends, HTTPException  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from backend.app.auth import user_from_request  # noqa: E402
from backend.app.database import get_session  # noqa: E402
from backend.app.models import UserAccount  # noqa: E402
from backend.app.tenancy import current_business_id  # noqa: E402

router = APIRouter(prefix="/ai", tags=["ai"])

# Who may change what the workspace spends. Reading the meter is open to
# anybody who can use the assistant; changing the settings is not.
SPEND_ROLES = {"owner", "admin"}


def _role(session: Session, business_id: int, user_id: int) -> str:
    from backend.app.models import Membership

    membership = session.exec(
        select(Membership).where(
            Membership.business_id == business_id,
            Membership.user_id == user_id,
            Membership.active == True,  # noqa: E712
        )
    ).first()
    return membership.role if membership else ""


@router.get("/usage")
def ai_usage(
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """
    What the assistant has cost this month, and what is left.

    Open to everybody who can use it, because somebody being told "you have
    used your credit" needs to be able to see the number that sentence is
    about. Employees see their own spend alongside the workspace's.
    """
    bid = current_business_id()
    return summary(session, bid, user_id=user.id)


class SpendSettings(BaseModel):
    employees_enabled: Optional[bool] = None
    per_user_cap_dollars: Optional[float] = None


@router.put("/settings")
def update_spend_settings(
    payload: SpendSettings,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """Who gets the assistant, and how much any one of them may spend."""
    bid = current_business_id()
    if _role(session, bid, user.id) not in SPEND_ROLES:
        raise HTTPException(403, "Only an owner or admin can change assistant spending.")

    wallet = get_wallet(session, bid)
    if payload.employees_enabled is not None:
        wallet.employees_enabled = payload.employees_enabled
    if payload.per_user_cap_dollars is not None:
        if payload.per_user_cap_dollars < 0:
            raise HTTPException(400, "A cap cannot be negative.")
        wallet.per_user_cap_milli = int(payload.per_user_cap_dollars * MILLI_PER_DOLLAR)

    session.add(wallet)
    session.commit()
    return summary(session, bid, user_id=user.id)


@router.get("/breakdown")
def ai_breakdown(
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """
    Where the month went, by person and by feature.

    An owner asking "why is this gone" should not have to guess between the
    business assistant, the scheduling assistant and fifteen employees.
    """
    bid = current_business_id()
    if _role(session, bid, user.id) not in SPEND_ROLES:
        raise HTTPException(403, "Only an owner or admin can see the full breakdown.")

    prefix = current_period()
    rows = session.exec(
        select(ApiUsage).where(
            ApiUsage.business_id == bid,
            ApiUsage.date.startswith(prefix),
        )
    ).all()

    by_feature: dict[str, int] = {}
    by_user: dict[Optional[int], int] = {}
    for row in rows:
        by_feature[row.feature] = by_feature.get(row.feature, 0) + row.vendor_cost_milli
        by_user[row.user_id] = by_user.get(row.user_id, 0) + row.vendor_cost_milli

    names = {
        account.id: account.username
        for account in session.exec(
            select(UserAccount).where(UserAccount.id.in_([k for k in by_user if k]))
        ).all()
    } if any(by_user) else {}

    return {
        "period": prefix,
        "by_feature": sorted(
            ({"feature": key or "unknown", "spent": dollars(value)}
             for key, value in by_feature.items()),
            key=lambda item: -item["spent"],
        ),
        "by_person": sorted(
            ({"user": names.get(key, "Unknown" if key else "Before attribution"),
              "spent": dollars(value)}
             for key, value in by_user.items()),
            key=lambda item: -item["spent"],
        ),
    }
