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
    InventoryMovement,
    Invoice,
    Schedule,
    ScheduleShift,
    Service,
    UserAccount,
    utc_now_iso,
)
from backend.app.ops_models import (
    ComplianceProfile,
    EmployeeCompliance,
    Recipe,
    RecipeComponent,
    WasteLog,
)
from backend.app.tenancy import current_business_id

log = logging.getLogger(__name__)

router = APIRouter(prefix="/ops", tags=["operations"])


def _minutes(hhmm: str) -> Optional[int]:
    """
    "HH:MM" to minutes past midnight, or None when it is not a time.

    None rather than a fallback number, because the caller here has to be able
    to tell the difference. scheduler.parse_time returns a default instead, and
    that is right for the solver — a bad row should not take down a week's
    generation. It is wrong here: preflight exists to tell an operator what is
    wrong with their schedule, so a shift it cannot read is a thing to say out
    loud, not a thing to quietly score as zero.

    It used to read "25:00" as 1500 and "09:99" as 639, and return 0 for
    anything unparseable — which, combined with the overnight rule below, made
    an unreadable shift twenty-four hours long.
    """
    if not hhmm:
        return None
    parts = str(hhmm).split(":")
    if len(parts) < 2:
        return None
    try:
        hour, minute = int(parts[0]), int(parts[1])
    except (TypeError, ValueError):
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour * 60 + minute


def _shift_hours(shift: ScheduleShift) -> float:
    """
    Hours on the clock, or 0.0 for a shift whose times cannot be read.

    Zero is deliberate. The alternative — treating an unreadable shift as
    running to the same time next day — silently added twenty-four hours of
    wages and twenty-four staffed hours to the week, which is enough on its own
    to flip both the cost verdict and the coverage verdict.

    Unreadable shifts are counted separately and reported, so they cannot
    disappear into a zero.
    """
    start, end = _minutes(shift.start_time), _minutes(shift.end_time)
    if start is None or end is None:
        return 0.0
    if end <= start:
        end += 24 * 60      # a genuine overnight shift
    return (end - start) / 60


def _unreadable_shifts(shifts: List[ScheduleShift]) -> List[ScheduleShift]:
    return [
        s for s in shifts
        if _minutes(s.start_time) is None or _minutes(s.end_time) is None
    ]


# --------------------------------------------------------------- the checks

def _labor_cost(
    session: Session, business_id: int, shifts: List[ScheduleShift]
) -> tuple[Dict[str, int], int]:
    """
    Scheduled labor cost in cents per day, and how many shifts had no wage.

    That second number is the whole reason this returns a tuple. Rates live on
    EmployeeCompliance, which a workspace fills in some time after it starts
    scheduling — so on day one every rate is missing, every shift costs zero,
    and the week reads as 0% labor. "Clear to publish" is then a statement
    about data the product does not have, which is the one answer a pre-publish
    check must never give.
    """
    rates = {
        c.employee_id: c.hourly_rate_cents
        for c in session.exec(
            select(EmployeeCompliance).where(EmployeeCompliance.business_id == business_id)
        ).all()
    }

    per_day: Dict[str, int] = {}
    unpriced = 0
    for s in shifts:
        rate = rates.get(s.employee_id) or 0
        if rate <= 0:
            unpriced += 1
        cost = round(_shift_hours(s) * rate)
        per_day[s.date] = per_day.get(s.date, 0) + cost
    return per_day, unpriced


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

    # A shift whose start or end cannot be read contributes no hours and no
    # wages, so every number below quietly understates the week. Say so first.
    unreadable = _unreadable_shifts(shifts)
    if unreadable:
        noun = "shift" if len(unreadable) == 1 else "shifts"
        blocking.append(
            f"{len(unreadable)} {noun} have times that cannot be read "
            f"(for example {unreadable[0].start_time!r}-{unreadable[0].end_time!r})"
        )

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
    per_day_cost, unpriced_shifts = _labor_cost(session, business_id, shifts)
    labor_cents = sum(per_day_cost.values())
    forecast_cents = _forecast_revenue(session, business_id, days)
    labor_pct = round((labor_cents / forecast_cents) * 100, 1) if forecast_cents else None

    cost = {
        "labor_cost": round(labor_cents / 100, 2),
        "forecast_revenue": round(forecast_cents / 100, 2),
        "labor_percent": labor_pct,
        "per_day": {d: round(c / 100, 2) for d, c in sorted(per_day_cost.items())},
        "shifts_without_a_wage": unpriced_shifts,
    }
    # Hospitality typically targets 25-35% labor. Past 40% the week loses money.
    #
    # Order matters here. Missing wages are checked before the percentage,
    # because a week with no rates entered computes as 0% labor and reads as
    # healthy — which is exactly the state a new workspace is in, and exactly
    # the week an operator most wants a real answer about.
    if unpriced_shifts:
        cost["status"] = "no_wage_data"
        cost["labor_percent"] = None
        noun = "shift" if unpriced_shifts == 1 else "shifts"
        advisories.append(
            f"{unpriced_shifts} {noun} have no hourly rate, so labor cost is "
            "incomplete and the percentage can't be judged"
        )
    elif labor_pct is None:
        cost["status"] = "no_forecast"
        advisories.append("No revenue history yet, so labor percentage can't be judged")
    elif labor_pct > 40:
        cost["status"] = "over_budget"
        blocking.append(f"Labor is {labor_pct}% of forecast revenue")
    elif labor_pct > 33:
        cost["status"] = "tight"
        advisories.append(f"Labor at {labor_pct}% of forecast — tight but workable")
    else:
        cost["status"] = "healthy"

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


@router.get("/compliance/profile")
def get_profile(
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """Current rules, plus what they actually mean, for the settings screen."""
    from backend.app.compliance import resolve_rules

    business_id = current_business_id()
    profile = session.exec(
        select(ComplianceProfile).where(ComplianceProfile.business_id == business_id)
    ).first()

    headcount = len(session.exec(
        select(Employee).where(
            Employee.business_id == business_id,
            Employee.active == True,  # noqa: E712
        )
    ).all())

    rules = resolve_rules(profile)
    chosen = (profile.jurisdiction if profile else "federal")

    return {
        "jurisdiction": chosen,
        "industry": profile.industry if profile else "general",
        "employee_count": profile.employee_count if profile else headcount,
        "actual_headcount": headcount,
        "track_minors": profile.track_minors if profile else True,
        # What is genuinely in force, which may differ from what was chosen if a
        # headcount or industry threshold is not met. Saying so out loud beats
        # letting somebody believe they are covered when they are not.
        "effective": {
            "key": rules.key,
            "name": rules.name,
            "advance_notice_days": rules.advance_notice_days,
            "min_rest_hours": rules.min_rest_hours,
            "daily_overtime_hours": rules.daily_overtime_hours,
            "meal_break_after_hours": rules.meal_break_after_hours,
            "max_consecutive_days": rules.max_consecutive_days,
            "citation": rules.citation,
        },
        "falling_back": rules.key != chosen,
    }


class EmployeeComplianceIn(BaseModel):
    employee_id: int
    date_of_birth: str = ""
    exempt: bool = False
    is_student: bool = False
    hourly_rate: float = 0.0


@router.get("/compliance/employees")
def list_employee_compliance(
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """
    Every employee with the two facts the rule engine needs.

    Without a date of birth the minor rules never fire. Without an hourly rate
    every exposure figure reads $0, which makes a real violation look free.
    The UI uses `missing` to say so plainly.
    """
    business_id = current_business_id()

    employees = session.exec(
        select(Employee).where(
            Employee.business_id == business_id,
            Employee.active == True,  # noqa: E712
        )
    ).all()
    records = {
        c.employee_id: c
        for c in session.exec(
            select(EmployeeCompliance).where(EmployeeCompliance.business_id == business_id)
        ).all()
    }

    rows = []
    for e in employees:
        c = records.get(e.id)
        missing = []
        if not (c and c.date_of_birth):
            missing.append("date of birth")
        if not (c and c.hourly_rate_cents):
            missing.append("hourly rate")

        rows.append({
            "employee_id": e.id,
            "name": e.name,
            "department": e.department,
            "role": e.role,
            "date_of_birth": c.date_of_birth if c else "",
            "exempt": c.exempt if c else False,
            "is_student": c.is_student if c else False,
            "hourly_rate": round((c.hourly_rate_cents if c else 0) / 100, 2),
            "missing": missing,
        })

    return {
        "employees": rows,
        "complete": sum(1 for r in rows if not r["missing"]),
        "total": len(rows),
        "why_it_matters": (
            "Date of birth switches on the minor-hours rules. Hourly rate is what "
            "turns a violation into a dollar figure — without it every finding "
            "reads $0 and a real problem looks free."
        ),
    }


@router.put("/compliance/employees")
def upsert_employee_compliance(
    body: EmployeeComplianceIn,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    business_id = current_business_id()

    employee = session.get(Employee, body.employee_id)
    if not employee or employee.business_id != business_id:
        raise HTTPException(404, "No such employee in this workspace.")

    if body.date_of_birth:
        try:
            born = date.fromisoformat(body.date_of_birth)
        except ValueError:
            raise HTTPException(400, "Date of birth must be YYYY-MM-DD.")
        if born > date.today():
            raise HTTPException(400, "That date of birth is in the future.")
        if born.year < 1900:
            raise HTTPException(400, "That date of birth looks wrong.")

    record = session.exec(
        select(EmployeeCompliance).where(
            EmployeeCompliance.business_id == business_id,
            EmployeeCompliance.employee_id == body.employee_id,
        )
    ).first() or EmployeeCompliance(business_id=business_id, employee_id=body.employee_id)

    record.date_of_birth = body.date_of_birth
    record.exempt = body.exempt
    record.is_student = body.is_student
    record.hourly_rate_cents = int(round(body.hourly_rate * 100))
    record.updated_at = utc_now_iso()

    session.add(record)
    session.commit()

    return {"saved": True, "employee_id": body.employee_id}


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


# Declared after every literal /compliance/... path. FastAPI matches routes in
# declaration order, so anywhere earlier and GET /compliance/profile or
# /compliance/jurisdictions would bind here and fail parsing the word as an
# integer schedule id.
@router.get("/compliance/{schedule_id}")
def compliance_only(
    schedule_id: int,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """Labor-law check on its own, for the schedule editor's live warning bar."""
    return summarize(check_schedule(session, current_business_id(), schedule_id))


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


class RecipeIn(BaseModel):
    name: str
    sells_as_item_id: Optional[int] = None
    yield_quantity: float = 1.0
    notes: str = ""


class ComponentIn(BaseModel):
    inventory_item_id: int
    quantity: float
    waste_factor_percent: float = 0.0


@router.get("/inventory/recipes")
def list_recipes(
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """
    Every recipe with its cost, plus the items available to build one from.

    One call, because the builder needs both and two round trips on a phone in
    a stockroom is two chances to fail.
    """
    business_id = current_business_id()

    recipes = session.exec(
        select(Recipe).where(Recipe.business_id == business_id, Recipe.active == True)  # noqa: E712
    ).all()

    items = session.exec(
        select(InventoryItem).where(
            InventoryItem.business_id == business_id,
            InventoryItem.active == True,  # noqa: E712
        )
    ).all()

    out = []
    for r in recipes:
        cost = recipe_cost_cents(session, business_id, r.id)
        components = session.exec(
            select(RecipeComponent).where(
                RecipeComponent.business_id == business_id,
                RecipeComponent.recipe_id == r.id,
            )
        ).all()
        out.append({
            "id": r.id,
            "name": r.name,
            "sells_as_item_id": r.sells_as_item_id,
            "yield_quantity": round(r.yield_quantity_milli / 1000, 3),
            "notes": r.notes,
            "component_count": len(components),
            "components": [
                {
                    "id": c.id,
                    "inventory_item_id": c.inventory_item_id,
                    "quantity": round(c.quantity_milli / 1000, 3),
                    "waste_factor_percent": c.waste_factor_percent,
                }
                for c in components
            ],
            **{k: v for k, v in cost.items() if k not in ("recipe", "recipe_id", "components")},
        })

    return {
        "recipes": out,
        "items": [
            {
                "id": i.id,
                "name": i.name,
                "sku": i.sku,
                "unit": i.unit,
                "unit_cost": round(i.unit_cost_cents / 100, 2),
                "sales_price": round(i.sales_price_cents / 100, 2),
                "on_hand": round(i.quantity_milli / 1000, 3),
                "item_type": i.item_type,
            }
            for i in items
        ],
        "why_it_matters": (
            "Recipes are what turn a sale into an expected draw-down. Without "
            "them, variance has nothing to compare a count against and shrinkage "
            "stays invisible."
        ),
    }


@router.post("/inventory/recipes")
def create_recipe(
    body: RecipeIn,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    business_id = current_business_id()

    if not body.name.strip():
        raise HTTPException(400, "Give the recipe a name.")
    if body.yield_quantity <= 0:
        raise HTTPException(400, "Yield must be greater than zero.")

    if body.sells_as_item_id:
        sold = session.get(InventoryItem, body.sells_as_item_id)
        if not sold or sold.business_id != business_id:
            raise HTTPException(404, "That sellable item is not in this workspace.")

    recipe = Recipe(
        business_id=business_id,
        name=body.name.strip(),
        sells_as_item_id=body.sells_as_item_id,
        yield_quantity_milli=int(round(body.yield_quantity * 1000)),
        notes=body.notes.strip(),
    )
    session.add(recipe)
    session.commit()
    session.refresh(recipe)
    return {"id": recipe.id, "name": recipe.name}


@router.put("/inventory/recipes/{recipe_id}")
def update_recipe(
    recipe_id: int,
    body: RecipeIn,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    business_id = current_business_id()
    recipe = session.get(Recipe, recipe_id)
    if not recipe or recipe.business_id != business_id:
        raise HTTPException(404, "No such recipe.")
    if body.yield_quantity <= 0:
        raise HTTPException(400, "Yield must be greater than zero.")

    recipe.name = body.name.strip() or recipe.name
    recipe.sells_as_item_id = body.sells_as_item_id
    recipe.yield_quantity_milli = int(round(body.yield_quantity * 1000))
    recipe.notes = body.notes.strip()
    session.add(recipe)
    session.commit()
    return {"saved": True}


@router.delete("/inventory/recipes/{recipe_id}")
def archive_recipe(
    recipe_id: int,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """
    Archived, not deleted. Past variance reports were computed using this
    recipe, and removing it would silently rewrite history.
    """
    business_id = current_business_id()
    recipe = session.get(Recipe, recipe_id)
    if not recipe or recipe.business_id != business_id:
        raise HTTPException(404, "No such recipe.")
    recipe.active = False
    session.add(recipe)
    session.commit()
    return {"archived": True}


@router.post("/inventory/recipes/{recipe_id}/components")
def add_component(
    recipe_id: int,
    body: ComponentIn,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    business_id = current_business_id()

    recipe = session.get(Recipe, recipe_id)
    if not recipe or recipe.business_id != business_id:
        raise HTTPException(404, "No such recipe.")

    item = session.get(InventoryItem, body.inventory_item_id)
    if not item or item.business_id != business_id:
        raise HTTPException(404, "That ingredient is not in this workspace.")
    if body.quantity <= 0:
        raise HTTPException(400, "Quantity must be greater than zero.")
    if not 0 <= body.waste_factor_percent <= 100:
        raise HTTPException(400, "Waste factor must be between 0 and 100 percent.")

    existing = session.exec(
        select(RecipeComponent).where(
            RecipeComponent.business_id == business_id,
            RecipeComponent.recipe_id == recipe_id,
            RecipeComponent.inventory_item_id == body.inventory_item_id,
        )
    ).first()

    # Adding the same ingredient twice means editing it, not duplicating the
    # line — two rows for one ingredient would double-count in every report.
    component = existing or RecipeComponent(
        business_id=business_id,
        recipe_id=recipe_id,
        inventory_item_id=body.inventory_item_id,
    )
    component.quantity_milli = int(round(body.quantity * 1000))
    component.waste_factor_percent = body.waste_factor_percent
    session.add(component)
    session.commit()

    return recipe_cost_cents(session, business_id, recipe_id)


@router.delete("/inventory/components/{component_id}")
def remove_component(
    component_id: int,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    business_id = current_business_id()
    component = session.get(RecipeComponent, component_id)
    if not component or component.business_id != business_id:
        raise HTTPException(404, "No such ingredient line.")
    recipe_id = component.recipe_id
    session.delete(component)
    session.commit()
    return recipe_cost_cents(session, business_id, recipe_id)


class WasteIn(BaseModel):
    inventory_item_id: int
    quantity: float
    reason: str = "spoilage"
    notes: str = ""


WASTE_REASONS = ("spoilage", "breakage", "comp", "staff_meal", "prep_error")


@router.get("/inventory/waste")
def list_waste(
    days: int = 30,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    business_id = current_business_id()
    since = (date.today() - timedelta(days=days)).isoformat()

    rows = session.exec(
        select(WasteLog).where(
            WasteLog.business_id == business_id,
            WasteLog.occurred_at >= since,
        )
    ).all()

    items = {
        i.id: i for i in session.exec(
            select(InventoryItem).where(InventoryItem.business_id == business_id)
        ).all()
    }

    by_reason: Dict[str, int] = {}
    entries = []
    for w in sorted(rows, key=lambda r: r.occurred_at, reverse=True):
        item = items.get(w.inventory_item_id)
        by_reason[w.reason] = by_reason.get(w.reason, 0) + w.value_cents
        entries.append({
            "id": w.id,
            "item": item.name if item else "Unknown",
            "quantity": round(w.quantity_milli / 1000, 3),
            "value": round(w.value_cents / 100, 2),
            "reason": w.reason,
            "notes": w.notes,
            "occurred_at": w.occurred_at,
        })

    total = sum(w.value_cents for w in rows)
    return {
        "period_days": days,
        "entries": entries[:100],
        "total_value": round(total / 100, 2),
        "by_reason": {k: round(v / 100, 2) for k, v in sorted(by_reason.items(), key=lambda kv: -kv[1])},
        "reasons": list(WASTE_REASONS),
    }


@router.post("/inventory/waste")
def log_waste(
    body: WasteIn,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """
    Record deliberate loss, and take it out of stock.

    Logging waste is what makes variance mean anything. Unexplained variance
    with no waste log is just noise; what is left after waste is accounted for
    is the number worth chasing.
    """
    business_id = current_business_id()

    item = session.get(InventoryItem, body.inventory_item_id)
    if not item or item.business_id != business_id:
        raise HTTPException(404, "That item is not in this workspace.")
    if body.quantity <= 0:
        raise HTTPException(400, "Quantity must be greater than zero.")
    if body.reason not in WASTE_REASONS:
        raise HTTPException(400, f"Reason must be one of: {', '.join(WASTE_REASONS)}")

    milli = int(round(body.quantity * 1000))
    value_cents = round((milli / 1000) * item.unit_cost_cents)

    session.add(WasteLog(
        business_id=business_id,
        inventory_item_id=item.id,
        quantity_milli=milli,
        value_cents=value_cents,
        reason=body.reason,
        notes=body.notes.strip(),
        logged_by_user_id=user.id,
    ))

    # Waste has physically left the building, so stock follows it out with an
    # auditable movement rather than a silent adjustment.
    session.add(InventoryMovement(
        business_id=business_id,
        item_id=item.id,
        movement_date=date.today().isoformat(),
        quantity_milli=-milli,
        reason="waste",
        reference=f"{body.reason}: {body.notes.strip()[:80]}",
        created_by_user_id=user.id,
    ))
    item.quantity_milli = max(item.quantity_milli - milli, 0)
    session.add(item)
    session.commit()

    return {
        "logged": True,
        "value": round(value_cents / 100, 2),
        "remaining": round(item.quantity_milli / 1000, 3),
    }


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
