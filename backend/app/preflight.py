"""
Schedule preflight — the check that only works when everything shares a database.

Before a schedule is published, four questions get asked at once:

    1. Is it legal?            labor law, minors, rest, overtime, notice
    2. Is it staffed?          against bookings actually on the calendar
    3. Is it affordable?       labor cost against forecast revenue
    4. Can you serve it?       ingredient stock against forecast demand

Deputy can answer the first. A POS can approximate the third. Nothing on the
market answers all four in one pass, because answering them requires the
schedule, the booking calendar, the ledger and the stockroom to be the same
system. That is the entire product thesis, made concrete in one API call.

The verdict is deliberately blunt — publish, review, or fix — because it gets
read on a phone by someone with thirty seconds.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.app.auth import user_from_request
from backend.app.compliance import check_schedule, summarize
from backend.app.database import get_session
from backend.app.inventory_intel import (
    menu_engineering,
    record_count,
    recipe_cost_cents,
    theoretical_usage,
    variance_report,
)
from backend.app.models import (
    Booking,
    Employee,
    InventoryItem,
    Invoice,
    Schedule,
    ScheduleShift,
    Service,
    UserAccount,
)
from backend.app.ops_models import ComplianceProfile, EmployeeCompliance
from backend.app.tenancy import current_business_id

log = logging.getLogger(__name__)

router = APIRouter(prefix="/ops", tags=["operations"])


def _minutes(hhmm: str) -> int:
    try:
        h, m = hhmm.split(":")[:2]
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return 0


def _shift_hours(shift: ScheduleShift) -> float:
    start, end = _minutes(shift.start_time), _minutes(shift.end_time)
    if end <= start:
        end += 24 * 60
    return (end - start) / 60


# --------------------------------------------------------------- the checks

def _labor_cost(session: Session, business_id: int, shifts: List[ScheduleShift]) -> Dict[str, int]:
    """Scheduled labor cost in cents, per day and total."""
    rates = {
        c.employee_id: c.hourly_rate_cents
        for c in session.exec(
            select(EmployeeCompliance).where(EmployeeCompliance.business_id == business_id)
        ).all()
    }

    per_day: Dict[str, int] = {}
    for s in shifts:
        rate = rates.get(s.employee_id, 0)
        cost = round(_shift_hours(s) * rate)
        per_day[s.date] = per_day.get(s.date, 0) + cost
    return per_day


def _booking_demand(session: Session, business_id: int, days: List[str]) -> Dict[str, dict]:
    """Booked appointments and committed revenue per day."""
    if not days:
        return {}

    bookings = session.exec(
        select(Booking).where(
            Booking.business_id == business_id,
            Booking.booking_date >= min(days),
            Booking.booking_date <= max(days),
            Booking.status.in_(("pending", "confirmed")),
        )
    ).all()

    out: Dict[str, dict] = {d: {"count": 0, "revenue_cents": 0, "minutes": 0} for d in days}
    for b in bookings:
        row = out.setdefault(b.booking_date, {"count": 0, "revenue_cents": 0, "minutes": 0})
        row["count"] += 1
        row["revenue_cents"] += round((b.price or 0) * 100)
        row["minutes"] += b.duration_minutes or 0
    return out


def _forecast_revenue(session: Session, business_id: int, days: List[str]) -> int:
    """
    Expected revenue for the period, in cents.

    Committed booking revenue plus a trailing daily average from invoices — the
    average carries walk-in trade that bookings never capture.
    """
    if not days:
        return 0

    booked = sum(d["revenue_cents"] for d in _booking_demand(session, business_id, days).values())

    lookback_start = (date.today() - timedelta(days=28)).isoformat()
    invoices = session.exec(
        select(Invoice).where(
            Invoice.business_id == business_id,
            Invoice.issue_date >= lookback_start,
            Invoice.status != "void",
        )
    ).all()
    daily_avg = round(sum(i.total_cents for i in invoices) / 28) if invoices else 0

    return booked + daily_avg * len(days)


def _stock_risk(session: Session, business_id: int, days: List[str]) -> List[dict]:
    """Ingredients likely to run out before the period ends."""
    if not days:
        return []

    lookback_days = 14
    since = (date.today() - timedelta(days=lookback_days)).isoformat()
    usage = theoretical_usage(session, business_id, since)
    if not usage:
        return []

    risks: List[dict] = []
    for item_id, used_milli in usage.items():
        item = session.get(InventoryItem, item_id)
        if not item or item.business_id != business_id or not item.active:
            continue

        per_day = used_milli / lookback_days
        if per_day <= 0:
            continue

        needed = per_day * len(days)
        if item.quantity_milli < needed:
            days_left = item.quantity_milli / per_day if per_day else 0
            shortfall = needed - item.quantity_milli
            risks.append({
                "item": item.name,
                "sku": item.sku,
                "on_hand": round(item.quantity_milli / 1000, 2),
                "needed": round(needed / 1000, 2),
                "shortfall": round(shortfall / 1000, 2),
                "days_of_cover": round(days_left, 1),
                "severity": "high" if days_left < len(days) / 2 else "medium",
            })

    risks.sort(key=lambda r: r["days_of_cover"])
    return risks


# --------------------------------------------------------------- routes

class PreflightOut(BaseModel):
    verdict: str
    headline: str
    schedule_id: int
    week_start: str
    checks: dict
    blocking: List[str]
    advisories: List[str]


@router.get("/preflight/{schedule_id}", response_model=PreflightOut)
def preflight(
    schedule_id: int,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """
    Everything that could go wrong with this schedule, in one answer.

    Run it before publishing. Nothing here is guesswork about the future — it is
    the schedule measured against bookings already taken, stock already counted,
    and revenue already trending.
    """
    business_id = current_business_id()

    schedule = session.get(Schedule, schedule_id)
    if not schedule or schedule.business_id != business_id:
        raise HTTPException(404, "No such schedule.")

    shifts = session.exec(
        select(ScheduleShift).where(
            ScheduleShift.schedule_id == schedule_id,
            ScheduleShift.business_id == business_id,
        )
    ).all()

    days = sorted({s.date for s in shifts})
    blocking: List[str] = []
    advisories: List[str] = []

    # ---- 1. legal
    compliance = summarize(check_schedule(session, business_id, schedule_id))
    if compliance["violations"]:
        blocking.append(
            f"{compliance['violations']} likely labor-law violation"
            f"{'s' if compliance['violations'] != 1 else ''}"
        )
    if compliance["warnings"]:
        advisories.append(f"{compliance['warnings']} scheduling warning(s)")

    # ---- 2. staffed for what is actually booked
    demand = _booking_demand(session, business_id, days)
    coverage: List[dict] = []
    for day in days:
        booked_minutes = demand.get(day, {}).get("minutes", 0)
        staffed_minutes = sum(_shift_hours(s) * 60 for s in shifts if s.date == day)
        booked_count = demand.get(day, {}).get("count", 0)

        row = {
            "date": day,
            "bookings": booked_count,
            "booked_hours": round(booked_minutes / 60, 1),
            "staffed_hours": round(staffed_minutes / 60, 1),
        }
        # Service work rarely exceeds ~70% utilisation once turnaround is counted.
        if booked_minutes and staffed_minutes < booked_minutes / 0.7:
            row["status"] = "understaffed"
            blocking.append(f"{day} has {booked_count} bookings but too few staffed hours")
        elif staffed_minutes and booked_minutes and staffed_minutes > booked_minutes * 3:
            row["status"] = "possibly_overstaffed"
            advisories.append(f"{day} looks heavy for the booked load")
        else:
            row["status"] = "ok"
        coverage.append(row)

    # ---- 3. affordable
    per_day_cost = _labor_cost(session, business_id, shifts)
    labor_cents = sum(per_day_cost.values())
    forecast_cents = _forecast_revenue(session, business_id, days)
    labor_pct = round((labor_cents / forecast_cents) * 100, 1) if forecast_cents else None

    cost = {
        "labor_cost": round(labor_cents / 100, 2),
        "forecast_revenue": round(forecast_cents / 100, 2),
        "labor_percent": labor_pct,
        "per_day": {d: round(c / 100, 2) for d, c in sorted(per_day_cost.items())},
    }
    # Hospitality typically targets 25-35% labor. Past 40% the week loses money.
    if labor_pct is not None:
        if labor_pct > 40:
            cost["status"] = "over_budget"
            blocking.append(f"Labor is {labor_pct}% of forecast revenue")
        elif labor_pct > 33:
            cost["status"] = "tight"
            advisories.append(f"Labor at {labor_pct}% of forecast — tight but workable")
        else:
            cost["status"] = "healthy"
    else:
        cost["status"] = "no_forecast"
        advisories.append("No revenue history yet, so labor percentage can't be judged")

    # ---- 4. can you actually serve it
    stock = _stock_risk(session, business_id, days)
    for risk in stock:
        if risk["severity"] == "high":
            blocking.append(f"{risk['item']} runs out in {risk['days_of_cover']} days")
        else:
            advisories.append(f"{risk['item']} is tight for this week")

    verdict = "fix" if blocking else ("review" if advisories else "publish")
    headline = {
        "fix": f"{len(blocking)} thing{'s' if len(blocking) != 1 else ''} to sort before this goes out",
        "review": "Worth a look, nothing blocking",
        "publish": "Clear to publish",
    }[verdict]

    return PreflightOut(
        verdict=verdict,
        headline=headline,
        schedule_id=schedule_id,
        week_start=schedule.week_start,
        checks={
            "compliance": compliance,
            "coverage": coverage,
            "cost": cost,
            "stock": stock,
        },
        blocking=blocking,
        advisories=advisories,
    )


@router.get("/compliance/{schedule_id}")
def compliance_only(
    schedule_id: int,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """Labor-law check on its own, for the schedule editor's live warning bar."""
    return summarize(check_schedule(session, current_business_id(), schedule_id))


class ProfileIn(BaseModel):
    jurisdiction: str = "federal"
    industry: str = "general"
    employee_count: int = 0
    track_minors: bool = True


@router.put("/compliance/profile")
def set_profile(
    body: ProfileIn,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """Which labor rules apply. Wrong jurisdiction means wrong warnings."""
    business_id = current_business_id()
    profile = session.exec(
        select(ComplianceProfile).where(ComplianceProfile.business_id == business_id)
    ).first() or ComplianceProfile(business_id=business_id)

    profile.jurisdiction = body.jurisdiction
    profile.industry = body.industry
    profile.employee_count = body.employee_count or len(session.exec(
        select(Employee).where(Employee.business_id == business_id)
    ).all())
    profile.track_minors = body.track_minors
    session.add(profile)
    session.commit()
    return {"saved": True, "jurisdiction": profile.jurisdiction}


@router.get("/compliance/jurisdictions")
def jurisdictions():
    """Everything the rule engine knows, for the settings dropdown."""
    from backend.app.compliance import JURISDICTIONS
    return {
        "jurisdictions": [
            {
                "key": r.key,
                "name": r.name,
                "predictive_scheduling": bool(r.advance_notice_days),
                "advance_notice_days": r.advance_notice_days,
                "daily_overtime": r.daily_overtime_hours,
                "min_rest_hours": r.min_rest_hours,
                "citation": r.citation,
                "applies_above_employees": r.applies_above_employees,
                "industries": r.industries or ["all"],
            }
            for r in JURISDICTIONS.values()
        ],
        "disclaimer": (
            "Advisory only. Ordinances change and carve-outs are common — confirm "
            "anything flagged with your own counsel before relying on it."
        ),
    }


# --------------------------------------------------------------- inventory

@router.get("/inventory/variance")
def inventory_variance(
    days: int = 30,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """Unexplained shrinkage in dollars. The number nobody else can produce."""
    return variance_report(session, current_business_id(), days)


@router.get("/inventory/menu-engineering")
def menu_analysis(
    days: int = 30,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """Every recipe ranked by margin and volume."""
    return menu_engineering(session, current_business_id(), days)


@router.get("/inventory/recipe/{recipe_id}/cost")
def recipe_cost(
    recipe_id: int,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    return recipe_cost_cents(session, current_business_id(), recipe_id)


class CountIn(BaseModel):
    inventory_item_id: int
    counted_quantity: float
    notes: str = ""


@router.post("/inventory/count")
def submit_count(
    body: CountIn,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """Record a physical count and adjust stock to match reality."""
    return record_count(
        session,
        current_business_id(),
        body.inventory_item_id,
        int(round(body.counted_quantity * 1000)),
        user_id=user.id,
        notes=body.notes,
    )
