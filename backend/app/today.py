"""
The dashboard, assembled.

What was here before answered four questions every small-business app answers:
what is owed, what is owing, how many tasks, how many low-stock items. Four
numbers that are true and that nobody does anything about. Alongside them sat a
panel reading "Sell. Deliver. Record. Understand." — marketing copy inside the
product, which is what a screen puts there when it has nothing real to say.

This answers the four questions this product can answer and its competitors
cannot, because only a system that holds the rota, the booking diary, the
ledger and the stockroom at once can join them up:

    Is this week's rota safe to publish?
    Is money going the right way?
    What runs out before the week does?
    What is waiting for a human?

Every figure here is something to act on, and every one of them names where to
go and do it.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from backend.app.database import get_session
from backend.app.models import (
    Bill,
    Expense,
    Invoice,
    InventoryItem,
    Payment,
    Schedule,
    TaskItem,
)
from backend.app.platform import business_context

log = logging.getLogger(__name__)

router = APIRouter(prefix="/platform", tags=["platform"])


def _this_week(session: Session, business_id: int) -> Optional[dict]:
    """
    The rota for the week we are in, and whether it is safe to publish.

    Preflight is the product's clearest differentiator and it lived three
    clicks away behind a dropdown, which meant the answer to "can I publish
    this?" was only ever seen by somebody who already went looking. It belongs
    on the first screen.

    A failure here must not take the dashboard down with it: preflight touches
    the solver, the compliance engine and the stockroom, and any of those can
    be misconfigured on a young workspace. The tile disappears; the page does
    not.
    """
    monday = (date.today() - timedelta(days=date.today().weekday())).isoformat()

    schedule = session.exec(
        select(Schedule)
        .where(Schedule.business_id == business_id, Schedule.week_start == monday)
        .order_by(Schedule.version.desc())
    ).first()

    # No rota for this week yet is itself worth saying, rather than an empty
    # tile — it is the single most actionable thing on a Monday morning.
    if not schedule:
        return {"state": "none", "week_start": monday}

    try:
        from backend.app.preflight import preflight as run_preflight

        report = run_preflight(schedule.id, session=session, user=None)
        data = report.model_dump() if hasattr(report, "model_dump") else report
        return {
            "state": "checked",
            "schedule_id": schedule.id,
            "week_start": schedule.week_start,
            "status": schedule.status,
            "verdict": data["verdict"],
            "headline": data["headline"],
            "blocking": data["blocking"],
            "advisories": data["advisories"],
        }
    except Exception:
        log.warning("Preflight failed on the dashboard for business %s", business_id,
                    exc_info=True)
        return {
            "state": "unchecked",
            "schedule_id": schedule.id,
            "week_start": schedule.week_start,
            "status": schedule.status,
        }


def _money(session: Session, business_id: int, days: int = 30) -> dict:
    """
    Cash in and out per day, and what is still owed either way.

    A shape rather than a number: thirty figures say whether a business is
    climbing or sliding, and one total says neither.
    """
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    today = date.today().isoformat()

    payments = session.exec(
        select(Payment).where(
            Payment.business_id == business_id,
            Payment.payment_date >= since,
            Payment.payment_date <= today,
        )
    ).all()
    expenses = session.exec(
        select(Expense).where(
            Expense.business_id == business_id,
            Expense.expense_date >= since,
            Expense.expense_date <= today,
        )
    ).all()

    # Every day in the window, including the empty ones — a series with gaps
    # draws a chart that lies about its own shape.
    series: Dict[str, Dict[str, int]] = {
        (date.today() - timedelta(days=offset)).isoformat(): {"in": 0, "out": 0}
        for offset in range(days)
    }

    for payment in payments:
        row = series.get(payment.payment_date)
        if row is None:
            continue
        if payment.direction == "received":
            row["in"] += payment.amount_cents
        else:
            row["out"] += payment.amount_cents

    for expense in expenses:
        row = series.get(expense.expense_date)
        if row is not None:
            row["out"] += expense.amount_cents

    ordered = [{"date": d, **series[d]} for d in sorted(series)]
    total_in = sum(r["in"] for r in ordered)
    total_out = sum(r["out"] for r in ordered)

    invoices = session.exec(
        select(Invoice).where(Invoice.business_id == business_id, Invoice.status != "void")
    ).all()
    bills = session.exec(
        select(Bill).where(Bill.business_id == business_id, Bill.status != "void")
    ).all()

    return {
        "days": days,
        "series": ordered,
        "in_cents": total_in,
        "out_cents": total_out,
        "net_cents": total_in - total_out,
        "receivables_cents": sum(max(0, x.total_cents - x.paid_cents) for x in invoices),
        "payables_cents": sum(max(0, x.total_cents - x.paid_cents) for x in bills),
    }


def _running_out(session: Session, business_id: int, limit: int = 4) -> List[dict]:
    """
    What will not last the week, soonest first.

    Falls back to the reorder level when there is not enough movement history
    to project a burn rate. A new workspace has no usage to extrapolate from,
    and "nothing is running out" would be a guess dressed as an answer.
    """
    horizon = [(date.today() + timedelta(days=offset)).isoformat() for offset in range(7)]

    try:
        from backend.app.preflight import _stock_risk

        risks = _stock_risk(session, business_id, horizon)
        if risks:
            return risks[:limit]
    except Exception:
        log.warning("Stock projection failed for business %s", business_id, exc_info=True)

    items = session.exec(
        select(InventoryItem).where(
            InventoryItem.business_id == business_id,
            InventoryItem.active == True,  # noqa: E712
        )
    ).all()
    low = [
        {
            "item": item.name,
            "sku": item.sku,
            "on_hand": round(item.quantity_milli / 1000, 2),
            "needed": round(item.reorder_level_milli / 1000, 2),
            "shortfall": round((item.reorder_level_milli - item.quantity_milli) / 1000, 2),
            "days_of_cover": None,
            "severity": "high" if item.quantity_milli <= 0 else "medium",
            "reason": "at reorder level",
        }
        for item in items
        if item.reorder_level_milli > 0 and item.quantity_milli <= item.reorder_level_milli
    ]
    low.sort(key=lambda r: r["shortfall"], reverse=True)
    return low[:limit]


def _needs_a_human(session: Session, business_id: int, week: Optional[dict]) -> List[dict]:
    """
    The things software cannot clear on its own.

    Ordered by what it costs to ignore: a rota that cannot legally be published
    outranks an overdue invoice, which outranks a task.
    """
    items: List[dict] = []
    today = date.today().isoformat()

    if week and week.get("verdict") == "fix":
        items.append({
            "kind": "rota",
            "urgency": "high",
            "text": week["headline"],
            "detail": week["blocking"][0] if week["blocking"] else "",
            "tab": "preflight",
        })

    overdue = session.exec(
        select(Invoice).where(
            Invoice.business_id == business_id,
            Invoice.status != "void",
            Invoice.due_date < today,
        )
    ).all()
    unpaid = [x for x in overdue if x.total_cents > x.paid_cents]
    if unpaid:
        owed = sum(x.total_cents - x.paid_cents for x in unpaid)
        items.append({
            "kind": "invoices",
            "urgency": "high",
            "text": f"{len(unpaid)} invoice{'s' if len(unpaid) != 1 else ''} overdue",
            "detail": f"${owed / 100:,.0f} outstanding past its due date",
            "tab": "sales",
        })

    due_bills = session.exec(
        select(Bill).where(
            Bill.business_id == business_id,
            Bill.status != "void",
            Bill.due_date < today,
        )
    ).all()
    owing = [x for x in due_bills if x.total_cents > x.paid_cents]
    if owing:
        amount = sum(x.total_cents - x.paid_cents for x in owing)
        items.append({
            "kind": "bills",
            "urgency": "medium",
            "text": f"{len(owing)} bill{'s' if len(owing) != 1 else ''} past due",
            "detail": f"${amount / 100:,.0f} owed",
            "tab": "purchasing",
        })

    tasks = session.exec(
        select(TaskItem).where(TaskItem.business_id == business_id)
    ).all()
    open_tasks = [t for t in tasks if t.status not in {"done", "cancelled"}]
    late = [t for t in open_tasks if t.due_date and t.due_date < today]
    if late:
        items.append({
            "kind": "tasks",
            "urgency": "medium",
            "text": f"{len(late)} task{'s' if len(late) != 1 else ''} overdue",
            "detail": late[0].title,
            "tab": "tasks",
        })
    elif open_tasks:
        items.append({
            "kind": "tasks",
            "urgency": "low",
            "text": f"{len(open_tasks)} open task{'s' if len(open_tasks) != 1 else ''}",
            "detail": open_tasks[0].title,
            "tab": "tasks",
        })

    return items


@router.get("/today")
def today(context=Depends(business_context), session: Session = Depends(get_session)):
    """Everything the first screen needs, in one request."""
    business_id = context[0]

    week = _this_week(session, business_id)
    money = _money(session, business_id)
    stock = _running_out(session, business_id)
    attention = _needs_a_human(session, business_id, week)

    if stock:
        worst = stock[0]
        cover = worst.get("days_of_cover")
        attention.append({
            "kind": "stock",
            "urgency": "high" if worst.get("severity") == "high" else "medium",
            "text": f"{worst['item']} runs out"
                    + (f" in {cover} days" if cover is not None else " soon"),
            "detail": f"{worst['on_hand']} on hand",
            "tab": "inventory-intel",
        })

    order = {"high": 0, "medium": 1, "low": 2}
    attention.sort(key=lambda a: order.get(a["urgency"], 3))

    return {
        "week": week,
        "money": money,
        "stock": stock,
        "attention": attention,
        # The count the assistant bubble rings for. Only the things that
        # actually cost something if ignored.
        "attention_count": sum(1 for a in attention if a["urgency"] == "high"),
    }
