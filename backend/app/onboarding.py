"""
Getting a new workspace to the point where the product can do something.

The landing page sells well and hands off to a blank room: an empty dashboard,
twenty-one tabs, and every tile reading $0.00. That is the first ninety seconds
of this product, and for most trials it is the only ninety seconds.

This is deliberately not a wizard. A wizard is a thing people abandon halfway
and can never find again, and it asks for information before it has earned the
right to. What this does instead is *measure* — it reads the workspace and
reports what is actually there, so the checklist is true whether somebody
followed it, ignored it, or did the work months ago in a different order.

The steps are ordered by what unlocks the most. Staff before a rota, because a
rota needs people. A rota before preflight, because preflight needs a rota.
Nothing here asks for anything the product will not immediately use.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlmodel import Session, func, select

from backend.app.database import get_session
from backend.app.models import (
    Contact,
    Employee,
    InventoryItem,
    Invoice,
    JournalEntry,
    Position,
    Schedule,
    Service,
    Subscription,
)
from backend.app.platform import business_context

router = APIRouter(prefix="/platform", tags=["platform"])


def _count(session: Session, model, business_id: int, *extra) -> int:
    statement = select(func.count()).select_from(model).where(model.business_id == business_id)
    for clause in extra:
        statement = statement.where(clause)
    return session.exec(statement).one()


def _steps(session: Session, business_id: int, modules: set[str]) -> List[dict]:
    """
    What is done, what is next, and what each one unlocks.

    Only steps for modules the workspace actually has. Telling somebody to add
    staff when they bought the books is noise, and noise in a checklist is how
    checklists get ignored.
    """
    steps: List[dict] = []

    def step(key, *, title, why, done, tab, action, modules_needed=None):
        if modules_needed and not (set(modules_needed) & modules):
            return
        steps.append({
            "key": key, "title": title, "why": why,
            "done": bool(done), "tab": tab, "action": action,
        })

    # --- people, and everything that needs them -----------------------------
    staff = _count(session, Employee, business_id, Employee.active == True)  # noqa: E712
    step(
        "staff",
        title="Add your team",
        why="Rotas, availability and labor cost all start here.",
        done=staff > 0,
        tab="manager",
        action="Add people",
        modules_needed=["scheduling"],
    )

    step(
        "positions",
        title="Say what people do",
        why="Positions are how the scheduler knows who can cover what.",
        done=_count(session, Position, business_id, Position.active == True) > 0,  # noqa: E712
        tab="manager",
        action="Add positions",
        modules_needed=["scheduling"],
    )

    step(
        "rota",
        title="Build a week",
        why="Then Preflight can check it against labor law, bookings, cost and stock — "
            "the thing nothing else does.",
        done=_count(session, Schedule, business_id) > 0,
        tab="manager",
        action="Build this week",
        modules_needed=["scheduling"],
    )

    # --- money -------------------------------------------------------------
    step(
        "contacts",
        title="Add a customer",
        why="Invoices, bookings and history all hang off one contact record.",
        done=_count(session, Contact, business_id, Contact.active == True) > 0,  # noqa: E712
        tab="contacts",
        action="Add a contact",
        modules_needed=["sales", "purchasing", "team", "booking"],
    )

    step(
        "invoice",
        title="Raise an invoice",
        why="It posts to the ledger as you issue it, so the books keep themselves.",
        done=_count(session, Invoice, business_id) > 0,
        tab="sales",
        action="New invoice",
        modules_needed=["sales"],
    )

    step(
        "books",
        title="Record something you spent",
        why="Every entry is double-checked against the chart of accounts you already have.",
        done=_count(session, JournalEntry, business_id) > 0,
        tab="accounting",
        action="Record an expense",
        modules_needed=["accounting"],
    )

    # --- stock and guests ---------------------------------------------------
    step(
        "stock",
        title="Add what you keep in stock",
        why="With a recipe attached, shrinkage becomes a number instead of a feeling.",
        done=_count(session, InventoryItem, business_id, InventoryItem.active == True) > 0,  # noqa: E712
        tab="inventory",
        action="Add an item",
        modules_needed=["inventory"],
    )

    step(
        "services",
        title="List what you sell appointments for",
        why="That is what your public booking page offers.",
        done=_count(session, Service, business_id, Service.active == True) > 0,  # noqa: E712
        tab="bookings",
        action="Add a service",
        modules_needed=["booking"],
    )

    # --- the last one, and only once there is something worth paying for ----
    subscribed = session.exec(
        select(Subscription).where(Subscription.business_id == business_id)
    ).first()
    step(
        "billing",
        title="Start your subscription",
        why="Unlimited users and every location, on every plan.",
        done=bool(subscribed and subscribed.status in {"active", "trialing"}),
        tab="billing",
        action="See the plan",
    )

    return steps


@router.get("/onboarding")
def onboarding(context=Depends(business_context), session: Session = Depends(get_session)):
    business_id = context[0]

    from backend.app.billing import enabled_modules

    modules = set(enabled_modules(session, business_id))
    steps = _steps(session, business_id, modules)

    done = [s for s in steps if s["done"]]
    todo = [s for s in steps if not s["done"]]

    return {
        "steps": steps,
        "done": len(done),
        "total": len(steps),
        # The one to do now. Ordered by what unlocks the most, so the first
        # undone step is always the right next move.
        "next": todo[0] if todo else None,
        # Once everything is done the checklist has no further job, and a
        # finished checklist that will not go away is clutter.
        "complete": not todo,
    }
