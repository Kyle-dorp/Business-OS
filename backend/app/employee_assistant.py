"""
The assistant an employee is allowed to have.

There are two assistants in this product and they are not the same thing wearing
different hats.

The business assistant (`/agent/chat`, `/assistant/chat`) is handed the company:
every invoice, bill, expense and task, every contact, every position, the
coverage rules, the labor projections, and every colleague's hours and pay band.
Measured on a forty-person restaurant that is 46,110 tokens. It is the right
context for an owner asking where the money went, and it is a breach for a line
cook asking when they are on next.

This one answers from one person's own record and nothing else. Their shifts,
their availability, their positions, their hours, their pay, their requests,
their tasks.

Two rules hold it to that, and both are load-bearing:

1. **It is built, never spread.** Every value is copied into a fresh dict by
   name. No `model.dict()`, no `**row`, no passing a SQLModel through. A field
   added to Employee or ManagerSettings next year cannot appear here by
   accident, because appearing here requires somebody to type its name.

2. **Pay is computed, not fetched.** ManagerSettings holds the rate for every
   role in the business. Handing it over to tell somebody their own wage would
   disclose everyone's. Their rate is resolved to a single number and the
   settings object stays behind.

It lives at `/my/assistant/chat` on purpose: `/my/` is already the prefix the
authentication middleware lets employees through, so giving them an assistant
required widening no permission anywhere.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional

from sqlmodel import Session, select

from backend.app.models import (
    AvailabilityRequest,
    Employee,
    EmployeePosition,
    ManagerSettings,
    Position,
    RecurringAvailability,
    Schedule,
    ScheduleShift,
    TaskItem,
    TemporaryUnavailability,
    UserAccount,
)

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday",
             "Friday", "Saturday", "Sunday"]


def _monday(reference: Optional[date] = None) -> date:
    today = reference or date.today()
    return today - timedelta(days=today.weekday())


def _minutes(start: str, end: str) -> int:
    """Shift length, tolerating an overnight and refusing to guess at nonsense."""
    try:
        first = datetime.strptime(start, "%H:%M")
        last = datetime.strptime(end, "%H:%M")
    except (ValueError, TypeError):
        return 0
    span = int((last - first).total_seconds() // 60)
    return span + 24 * 60 if span < 0 else span


def hourly_rate_for(employee: Employee, settings: ManagerSettings) -> float:
    """
    One number: what this person earns an hour.

    Computed rather than handed over. `settings` carries the rate for every
    role in the business, so returning it to answer "what do I make" would
    answer "what does everybody make".
    """
    if employee.hourly_rate_override is not None:
        return float(employee.hourly_rate_override)
    by_role = {
        "gm": settings.gm_hourly_rate,
        "shift_lead": settings.shift_lead_hourly_rate,
    }
    return float(by_role.get(employee.role, settings.employee_hourly_rate))


def employee_context(
    session: Session,
    user: UserAccount,
    *,
    today: Optional[date] = None,
) -> dict[str, Any]:
    """
    Everything the employee assistant may see. Built key by key.

    Returns `{"linked": False}` when the account has no employee record — a
    manager poking at this endpoint, or an account created before anybody
    attached it to a person. There is nothing to answer from, and inventing a
    fallback here would mean inventing a scope.
    """
    if not user.employee_id:
        return {"linked": False}

    employee = session.get(Employee, user.employee_id)
    if not employee:
        return {"linked": False}

    settings = session.exec(select(ManagerSettings)).first() or ManagerSettings()
    rate = hourly_rate_for(employee, settings)

    # --- who they are ------------------------------------------------------
    context: dict[str, Any] = {
        "linked": True,
        "you": {
            "name": employee.name,
            "department": employee.department,
            "role": employee.role,
            "min_hours_per_week": employee.min_hours_per_week,
            "max_hours_per_week": employee.max_hours_per_week,
            "hourly_rate": round(rate, 2),
        },
    }

    # --- what they are trained on ------------------------------------------
    links = session.exec(
        select(EmployeePosition).where(EmployeePosition.employee_id == employee.id)
    ).all()
    positions = {
        row.id: row
        for row in session.exec(select(Position).where(Position.active == True)).all()  # noqa: E712
    }
    context["your_positions"] = [
        {
            "name": positions[link.position_id].name,
            "trainee": bool(getattr(link, "trainee", False)),
        }
        for link in links
        if link.position_id in positions
    ]

    # --- when they are on ---------------------------------------------------
    # Published only. A draft rota is a manager's working document and telling
    # somebody they are on Tuesday before it is published is how a draft
    # becomes a promise.
    monday = _monday(today)
    weeks = [(monday + timedelta(weeks=offset)).isoformat() for offset in (0, 1)]
    published = {
        row.week_start: row
        for row in sorted(
            session.exec(select(Schedule).where(Schedule.status == "published")).all(),
            key=lambda row: (row.version, row.id or 0),
        )
        if row.week_start in weeks
    }

    shifts: list[dict[str, Any]] = []
    worked_minutes = {week: 0 for week in weeks}
    for week, schedule in published.items():
        rows = session.exec(
            select(ScheduleShift)
            .where(ScheduleShift.schedule_id == schedule.id)
            .where(ScheduleShift.employee_id == employee.id)
        ).all()
        for shift in rows:
            span = _minutes(shift.start_time, shift.end_time)
            worked_minutes[week] += span
            shifts.append({
                "date": shift.date,
                "start": shift.start_time,
                "end": shift.end_time,
                "position": positions[shift.position_id].name
                if shift.position_id in positions else None,
                "hours": round(span / 60, 2),
            })

    context["your_shifts"] = sorted(shifts, key=lambda row: (row["date"], row["start"]))
    context["your_hours"] = [
        {
            "week_starting": week,
            "published": week in published,
            "hours": round(worked_minutes[week] / 60, 2),
            "estimated_pay": round(worked_minutes[week] / 60 * rate, 2),
        }
        for week in weeks
    ]

    # --- when they said they can work ---------------------------------------
    context["your_availability"] = [
        {
            "day": DAY_NAMES[row.day_of_week] if 0 <= row.day_of_week < 7 else "Unknown",
            "start": row.start_time,
            "end": row.end_time,
            "rule": row.rule_type,
        }
        for row in session.exec(
            select(RecurringAvailability).where(
                RecurringAvailability.employee_id == employee.id
            )
        ).all()
    ]

    # TemporaryUnavailability carries no reason field — dates and times only.
    context["your_time_off"] = [
        {
            "start": row.start_date,
            "end": row.end_date,
            "all_day": not (row.start_time or row.end_time),
            "start_time": row.start_time or "",
            "end_time": row.end_time or "",
        }
        for row in session.exec(
            select(TemporaryUnavailability).where(
                TemporaryUnavailability.employee_id == employee.id
            )
        ).all()
    ]

    context["your_requests"] = [
        {
            "type": row.request_type,
            "title": row.title or "",
            "status": row.status,
            "reason": row.reason or "",
            "start": row.start_date or "",
            "end": row.end_date or "",
        }
        for row in session.exec(
            select(AvailabilityRequest).where(
                AvailabilityRequest.employee_id == employee.id
            )
        ).all()
    ]

    # --- what has been asked of them ----------------------------------------
    context["your_tasks"] = [
        {"title": row.title, "status": row.status, "due": row.due_date or ""}
        for row in session.exec(
            select(TaskItem).where(TaskItem.assigned_user_id == user.id)
        ).all()
    ]

    return context


SYSTEM_PROMPT = """You are the assistant inside Business-EOS, talking to one member of staff about their own work.

You can see only their record: their shifts, availability, positions, hours, pay and requests. You cannot see the business's money, other people's pay or hours, suppliers, invoices, or anything a manager would see — not because it is hidden from you, but because it was never given to you.

If they ask about something outside their own record, say plainly that you can only see their own information and suggest they ask their manager. Do not guess, and do not reason about what the answer might be from what you can see.

Answer in one or two sentences unless they ask for detail. They are usually checking something between other tasks — when they are on, how many hours they have, whether a request went through.

Rotas that have not been published are not visible to you. If they ask about a week you have no shifts for, say the rota for that week is not published yet rather than saying they are not working."""


# ===========================================================================
# The endpoint
# ===========================================================================

import json  # noqa: E402
import logging  # noqa: E402

from fastapi import APIRouter, Depends, HTTPException  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from backend.app.auth import user_from_request  # noqa: E402
from backend.app.database import get_session  # noqa: E402

log = logging.getLogger(__name__)

# /my/ is already the prefix authentication_middleware lets employees through,
# so this needed no permission widened anywhere. That is the whole reason it
# lives here rather than beside the business assistant.
router = APIRouter(prefix="/my", tags=["my"])

MAX_TOKENS_PER_REPLY = 700
MAX_HISTORY_TURNS = 10


class Turn(BaseModel):
    role: str
    content: str


class MyAssistantIn(BaseModel):
    message: str
    history: list[Turn] = []
    thread_id: str = ""


class MyAssistantOut(BaseModel):
    reply: str
    thread_id: str
    tokens_in: int = 0
    tokens_out: int = 0


@router.post("/assistant/chat", response_model=MyAssistantOut)
def my_assistant_chat(
    body: MyAssistantIn,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """
    Answers from one person's own record.

    There is no role check here and that is deliberate — everyone who reaches
    this endpoint gets the same thing, which is their own context. A manager
    calling it sees their own shifts, not the business. The scope is not
    enforced by permission, it is enforced by what was fetched.
    """
    import uuid

    import anthropic

    from backend.app.ai_agent import MODEL, _api, _check_budget, _record_usage
    from backend.app.tenancy import current_business_id

    bid = current_business_id()
    _check_budget(session, bid)

    context = employee_context(session, user)
    if not context.get("linked"):
        raise HTTPException(
            400,
            "This account is not attached to a staff record yet, so there is "
            "nothing personal to answer from. Your manager can link it in "
            "Settings.",
        )

    messages = [
        {"role": turn.role, "content": turn.content}
        for turn in body.history[-MAX_HISTORY_TURNS:]
        if turn.role in ("user", "assistant")
    ]
    messages.append({"role": "user", "content": body.message})

    try:
        response = _api().messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS_PER_REPLY,
            system=(
                SYSTEM_PROMPT
                + f"\n\nToday is {date.today().isoformat()}."
                + "\n\nTheir record:\n"
                + json.dumps(context, default=str)
            ),
            messages=messages,
        )
    except anthropic.RateLimitError:
        raise HTTPException(429, "The assistant is busy. Try again in a moment.")
    except anthropic.APIStatusError:
        log.exception("Employee assistant call failed for business %s", bid)
        raise HTTPException(502, "The assistant couldn't be reached just now.")

    reply = "".join(block.text for block in response.content if block.type == "text")
    _record_usage(
        session, bid, response.usage.input_tokens, response.usage.output_tokens,
        feature="my-assistant",
    )

    return MyAssistantOut(
        reply=reply,
        thread_id=body.thread_id or uuid.uuid4().hex,
        tokens_in=response.usage.input_tokens,
        tokens_out=response.usage.output_tokens,
    )
