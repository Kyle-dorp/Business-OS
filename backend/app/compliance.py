"""
Labor compliance checking.

This is the gap against Deputy, closed — and then passed, because these checks
run against a schedule *before* it is published, using booking load and revenue
forecast that a standalone scheduler does not have.

What this is: an advisory engine that flags likely violations and estimates
exposure, built from published rules for the jurisdictions below.

What this is not: legal advice, or a guarantee of compliance. Labor ordinances
change, carve-outs by headcount and industry are common, and collective
bargaining agreements override defaults. Every finding says which rule produced
it so a human can check it. The same honesty applies here as to payroll tax:
being confidently wrong about someone's legal exposure is worse than being
silent, so findings are phrased as "review this", never "you are compliant".

Rules encoded below are federal FLSA plus the major predictive-scheduling and
break-law jurisdictions. Adding one is a dict entry, not a code change.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from sqlmodel import Session, select

from backend.app.models import Employee, Schedule, ScheduleShift
from backend.app.ops_models import ComplianceProfile, EmployeeCompliance

log = logging.getLogger(__name__)


# --------------------------------------------------------------- rule table

@dataclass
class Rules:
    """Published labor rules for one jurisdiction. All hours are clock hours."""

    key: str
    name: str

    weekly_overtime_hours: int = 40
    daily_overtime_hours: Optional[int] = None       # CA-style daily OT
    double_time_hours: Optional[int] = None          # CA: over 12 in a day

    # Predictive scheduling / Fair Workweek
    advance_notice_days: int = 0
    predictability_pay: bool = False

    # "Clopening" — the gap between the end of one shift and the start of the next
    min_rest_hours: Optional[int] = None
    rest_premium_multiplier: float = 0.0             # 1.5 = time-and-a-half for the shift

    # Breaks
    meal_break_after_hours: Optional[float] = None
    meal_break_minutes: int = 30
    second_meal_after_hours: Optional[float] = None
    rest_break_per_hours: Optional[float] = None
    rest_break_minutes: int = 10

    # Consecutive-day limits (day-of-rest statutes)
    max_consecutive_days: Optional[int] = None

    # Only applies above this headcount. 0 = applies to everyone.
    applies_above_employees: int = 0
    industries: List[str] = field(default_factory=list)   # empty = all

    citation: str = ""


FEDERAL = Rules(
    key="federal",
    name="Federal (FLSA)",
    weekly_overtime_hours=40,
    citation="29 U.S.C. §207; 29 CFR Part 570 for minors",
)

JURISDICTIONS: Dict[str, Rules] = {
    "federal": FEDERAL,

    "ca": Rules(
        key="ca", name="California",
        weekly_overtime_hours=40, daily_overtime_hours=8, double_time_hours=12,
        meal_break_after_hours=5, meal_break_minutes=30,
        second_meal_after_hours=10,
        rest_break_per_hours=4, rest_break_minutes=10,
        max_consecutive_days=6,
        citation="Cal. Labor Code §§510, 512; IWC Wage Orders",
    ),
    "ny": Rules(
        key="ny", name="New York State",
        weekly_overtime_hours=40,
        meal_break_after_hours=6, meal_break_minutes=30,
        max_consecutive_days=6,
        citation="NY Labor Law §162",
    ),
    "nyc": Rules(
        key="nyc", name="New York City (Fair Workweek)",
        weekly_overtime_hours=40,
        advance_notice_days=14, predictability_pay=True,
        min_rest_hours=11, rest_premium_multiplier=0.0,
        meal_break_after_hours=6, meal_break_minutes=30,
        max_consecutive_days=6,
        industries=["food_service", "retail"],
        citation="NYC Admin Code §20-1201 et seq. ($100 premium for consented clopening)",
    ),
    "seattle": Rules(
        key="seattle", name="Seattle (Secure Scheduling)",
        weekly_overtime_hours=40,
        advance_notice_days=14, predictability_pay=True,
        min_rest_hours=10, rest_premium_multiplier=1.5,
        meal_break_after_hours=5, meal_break_minutes=30,
        rest_break_per_hours=4, rest_break_minutes=10,
        applies_above_employees=500,
        industries=["food_service", "retail"],
        citation="Seattle Municipal Code 14.22",
    ),
    "sf": Rules(
        key="sf", name="San Francisco (Formula Retail)",
        weekly_overtime_hours=40, daily_overtime_hours=8, double_time_hours=12,
        advance_notice_days=14, predictability_pay=True,
        meal_break_after_hours=5, meal_break_minutes=30,
        rest_break_per_hours=4,
        max_consecutive_days=6,
        industries=["retail", "food_service"],
        citation="SF Police Code Art. 33F/33G",
    ),
    "chicago": Rules(
        key="chicago", name="Chicago (Fair Workweek)",
        weekly_overtime_hours=40,
        advance_notice_days=14, predictability_pay=True,
        min_rest_hours=11, rest_premium_multiplier=1.25,
        applies_above_employees=100,
        industries=["food_service", "retail", "hospitality", "manufacturing"],
        citation="Chicago Municipal Code 6-110",
    ),
    "philadelphia": Rules(
        key="philadelphia", name="Philadelphia (Fair Workweek)",
        weekly_overtime_hours=40,
        advance_notice_days=14, predictability_pay=True,
        min_rest_hours=9, rest_premium_multiplier=0.0,
        applies_above_employees=250,
        industries=["food_service", "retail", "hospitality"],
        citation="Phila. Code Ch. 9-4600 ($40 premium for consented short rest)",
    ),
    "oregon": Rules(
        key="oregon", name="Oregon (Fair Work Week)",
        weekly_overtime_hours=40,
        advance_notice_days=14, predictability_pay=True,
        min_rest_hours=10, rest_premium_multiplier=1.5,
        meal_break_after_hours=6, meal_break_minutes=30,
        rest_break_per_hours=4,
        applies_above_employees=500,
        industries=["food_service", "retail", "hospitality"],
        citation="ORS 653.412 et seq.",
    ),
    "co": Rules(
        key="co", name="Colorado",
        weekly_overtime_hours=40, daily_overtime_hours=12,
        meal_break_after_hours=5, meal_break_minutes=30,
        rest_break_per_hours=4,
        citation="7 CCR 1103-1 (COMPS Order)",
    ),
    "wa": Rules(
        key="wa", name="Washington State",
        weekly_overtime_hours=40,
        meal_break_after_hours=5, meal_break_minutes=30,
        rest_break_per_hours=4,
        citation="WAC 296-126-092",
    ),
    "il": Rules(
        key="il", name="Illinois",
        weekly_overtime_hours=40,
        meal_break_after_hours=7.5, meal_break_minutes=20,
        max_consecutive_days=6,
        citation="820 ILCS 140 (One Day Rest in Seven Act)",
    ),
}


# Federal minor rules (29 CFR Part 570). States often go further.
MINOR_14_15 = {
    "max_hours_school_day": 3,
    "max_hours_school_week": 18,
    "max_hours_nonschool_day": 8,
    "max_hours_nonschool_week": 40,
    "earliest_hour": 7,
    "latest_hour": 19,            # 21 between 1 June and Labor Day
    "latest_hour_summer": 21,
}
MINOR_16_17 = {
    # Federal sets no hour limits at 16-17, but hazardous-occupation rules apply
    # and many states restrict nights on school evenings.
    "max_hours_school_day": 8,
    "max_hours_school_week": 48,
}


# --------------------------------------------------------------- finding type

@dataclass
class Finding:
    rule_code: str
    severity: str                 # info | warning | violation
    message: str
    employee_id: Optional[int] = None
    employee_name: str = ""
    date: str = ""
    exposure_cents: int = 0
    citation: str = ""

    def as_dict(self) -> dict:
        return {
            "rule_code": self.rule_code,
            "severity": self.severity,
            "message": self.message,
            "employee_id": self.employee_id,
            "employee_name": self.employee_name,
            "date": self.date,
            "exposure_cents": self.exposure_cents,
            "exposure": round(self.exposure_cents / 100, 2),
            "citation": self.citation,
        }


# --------------------------------------------------------------- helpers

def _minutes(hhmm: str) -> int:
    try:
        h, m = hhmm.split(":")[:2]
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return 0


def _shift_hours(shift: ScheduleShift) -> float:
    start, end = _minutes(shift.start_time), _minutes(shift.end_time)
    if end <= start:                      # crosses midnight
        end += 24 * 60
    return (end - start) / 60


def _age_on(dob: str, on: str) -> Optional[int]:
    if not dob:
        return None
    try:
        born = date.fromisoformat(dob)
        when = date.fromisoformat(on)
    except ValueError:
        return None
    return when.year - born.year - ((when.month, when.day) < (born.month, born.day))


def _is_summer(on: str) -> bool:
    """Federal minors may work until 21:00 between 1 June and Labor Day."""
    try:
        d = date.fromisoformat(on)
    except ValueError:
        return False
    return (d.month, d.day) >= (6, 1) and d.month <= 9


def resolve_rules(profile: Optional[ComplianceProfile]) -> Rules:
    """
    Pick the rule set, falling back to federal when a jurisdiction is unknown
    or its headcount/industry threshold isn't met.
    """
    if not profile:
        return FEDERAL

    rules = JURISDICTIONS.get((profile.jurisdiction or "federal").lower())
    if not rules:
        return FEDERAL

    if rules.applies_above_employees and profile.employee_count < rules.applies_above_employees:
        return FEDERAL
    if rules.industries and profile.industry not in rules.industries:
        return FEDERAL
    return rules


# --------------------------------------------------------------- checks

def check_schedule(
    session: Session,
    business_id: int,
    schedule_id: int,
    published_at: Optional[str] = None,
) -> List[Finding]:
    """
    Run every applicable rule over one schedule.

    `published_at` lets the advance-notice check run against the moment the
    schedule would actually go out, rather than now.
    """
    schedule = session.get(Schedule, schedule_id)
    if not schedule or schedule.business_id != business_id:
        return []

    profile = session.exec(
        select(ComplianceProfile).where(ComplianceProfile.business_id == business_id)
    ).first()
    rules = resolve_rules(profile)

    shifts = session.exec(
        select(ScheduleShift).where(
            ScheduleShift.schedule_id == schedule_id,
            ScheduleShift.business_id == business_id,
        )
    ).all()
    if not shifts:
        return []

    employees = {
        e.id: e for e in session.exec(
            select(Employee).where(Employee.business_id == business_id)
        ).all()
    }
    compliance = {
        c.employee_id: c for c in session.exec(
            select(EmployeeCompliance).where(EmployeeCompliance.business_id == business_id)
        ).all()
    }

    findings: List[Finding] = []
    by_employee: Dict[int, List[ScheduleShift]] = {}
    for s in shifts:
        by_employee.setdefault(s.employee_id, []).append(s)

    for emp_id, emp_shifts in by_employee.items():
        emp = employees.get(emp_id)
        name = emp.name if emp else f"Employee {emp_id}"
        comp = compliance.get(emp_id)
        rate_cents = comp.hourly_rate_cents if comp else 0
        exempt = comp.exempt if comp else False

        emp_shifts.sort(key=lambda s: (s.date, _minutes(s.start_time)))

        findings.extend(_check_hours(emp_id, name, emp_shifts, rules, rate_cents, exempt))
        findings.extend(_check_rest(emp_id, name, emp_shifts, rules, rate_cents))
        findings.extend(_check_breaks(emp_id, name, emp_shifts, rules))
        findings.extend(_check_consecutive(emp_id, name, emp_shifts, rules, profile))

        if (profile.track_minors if profile else True) and comp and comp.date_of_birth:
            findings.extend(_check_minor(emp_id, name, emp_shifts, comp))

    findings.extend(_check_notice(schedule, rules, published_at))
    return findings


def _check_hours(
    emp_id: int, name: str, shifts: List[ScheduleShift],
    rules: Rules, rate_cents: int, exempt: bool,
) -> List[Finding]:
    if exempt:
        return []

    out: List[Finding] = []
    weekly = sum(_shift_hours(s) for s in shifts)

    if weekly > rules.weekly_overtime_hours:
        over = weekly - rules.weekly_overtime_hours
        premium = int(over * rate_cents * 0.5) if rate_cents else 0
        out.append(Finding(
            rule_code="OT_WEEKLY",
            severity="warning",
            employee_id=emp_id, employee_name=name,
            message=(
                f"{name} is scheduled {weekly:.1f} hours — {over:.1f} over the "
                f"{rules.weekly_overtime_hours}-hour threshold. Overtime premium applies."
            ),
            exposure_cents=premium,
            citation=rules.citation,
        ))

    if rules.daily_overtime_hours:
        per_day: Dict[str, float] = {}
        for s in shifts:
            per_day[s.date] = per_day.get(s.date, 0) + _shift_hours(s)

        for day, hours in sorted(per_day.items()):
            if rules.double_time_hours and hours > rules.double_time_hours:
                over = hours - rules.double_time_hours
                out.append(Finding(
                    rule_code="OT_DOUBLE_TIME",
                    severity="warning",
                    employee_id=emp_id, employee_name=name, date=day,
                    message=(
                        f"{name} works {hours:.1f} hours on {day} — "
                        f"{over:.1f} hours at double time in {rules.name}."
                    ),
                    exposure_cents=int(over * rate_cents) if rate_cents else 0,
                    citation=rules.citation,
                ))
            elif hours > rules.daily_overtime_hours:
                over = hours - rules.daily_overtime_hours
                out.append(Finding(
                    rule_code="OT_DAILY",
                    severity="warning",
                    employee_id=emp_id, employee_name=name, date=day,
                    message=(
                        f"{name} works {hours:.1f} hours on {day}. {rules.name} pays daily "
                        f"overtime past {rules.daily_overtime_hours} hours."
                    ),
                    exposure_cents=int(over * rate_cents * 0.5) if rate_cents else 0,
                    citation=rules.citation,
                ))

    return out


def _check_rest(
    emp_id: int, name: str, shifts: List[ScheduleShift], rules: Rules, rate_cents: int,
) -> List[Finding]:
    """Clopening — too little rest between the end of one shift and the next."""
    if not rules.min_rest_hours:
        return []

    out: List[Finding] = []
    for prev, nxt in zip(shifts, shifts[1:]):
        try:
            prev_end = datetime.fromisoformat(f"{prev.date}T{prev.end_time}")
            next_start = datetime.fromisoformat(f"{nxt.date}T{nxt.start_time}")
        except ValueError:
            continue

        if _minutes(prev.end_time) <= _minutes(prev.start_time):
            prev_end += timedelta(days=1)          # previous shift crossed midnight
        if next_start <= prev_end:
            continue

        gap = (next_start - prev_end).total_seconds() / 3600
        if gap < rules.min_rest_hours:
            shift_hours = _shift_hours(nxt)
            premium = 0
            if rules.rest_premium_multiplier and rate_cents:
                premium = int(shift_hours * rate_cents * (rules.rest_premium_multiplier - 1))
            elif "nyc" in rules.key:
                premium = 10000        # flat $100 under NYC Fair Workweek
            elif "philadelphia" in rules.key:
                premium = 4000         # flat $40

            out.append(Finding(
                rule_code="REST_SHORT",
                severity="violation",
                employee_id=emp_id, employee_name=name, date=nxt.date,
                message=(
                    f"{name} has only {gap:.1f} hours off between {prev.date} and {nxt.date}. "
                    f"{rules.name} requires {rules.min_rest_hours}. Needs written consent "
                    f"and premium pay, or move the shift."
                ),
                exposure_cents=premium,
                citation=rules.citation,
            ))
    return out


def _check_breaks(
    emp_id: int, name: str, shifts: List[ScheduleShift], rules: Rules,
) -> List[Finding]:
    """
    Flag shifts long enough to require a meal break.

    Scheduling software can only say a break is *owed* — whether one was taken
    is a time-clock fact. Phrased accordingly.
    """
    if not rules.meal_break_after_hours:
        return []

    out: List[Finding] = []
    for s in shifts:
        hours = _shift_hours(s)
        if hours > rules.meal_break_after_hours:
            needed = 2 if (rules.second_meal_after_hours and hours > rules.second_meal_after_hours) else 1
            out.append(Finding(
                rule_code="MEAL_BREAK_DUE",
                severity="info",
                employee_id=emp_id, employee_name=name, date=s.date,
                message=(
                    f"{name}'s {hours:.1f}-hour shift on {s.date} requires "
                    f"{needed} unpaid meal break{'s' if needed > 1 else ''} of "
                    f"{rules.meal_break_minutes} minutes under {rules.name}."
                ),
                citation=rules.citation,
            ))
    return out


def _check_consecutive(
    emp_id: int, name: str, shifts: List[ScheduleShift],
    rules: Rules, profile: Optional[ComplianceProfile],
) -> List[Finding]:
    limit = rules.max_consecutive_days or (profile.max_consecutive_days if profile else None)
    if not limit:
        return []

    days = sorted({s.date for s in shifts})
    if not days:
        return []

    run = 1
    longest = 1
    run_start = days[0]
    worst_start = days[0]

    for prev, cur in zip(days, days[1:]):
        try:
            gap = (date.fromisoformat(cur) - date.fromisoformat(prev)).days
        except ValueError:
            continue
        if gap == 1:
            run += 1
            if run > longest:
                longest, worst_start = run, run_start
        else:
            run, run_start = 1, cur

    if longest > limit:
        return [Finding(
            rule_code="CONSECUTIVE_DAYS",
            severity="violation",
            employee_id=emp_id, employee_name=name, date=worst_start,
            message=(
                f"{name} works {longest} days in a row from {worst_start}. "
                f"{rules.name} requires a rest day after {limit}."
            ),
            citation=rules.citation,
        )]
    return []


def _check_minor(
    emp_id: int, name: str, shifts: List[ScheduleShift], comp: EmployeeCompliance,
) -> List[Finding]:
    out: List[Finding] = []
    per_day: Dict[str, float] = {}
    for s in shifts:
        per_day[s.date] = per_day.get(s.date, 0) + _shift_hours(s)

    total = sum(per_day.values())
    first_date = min(per_day) if per_day else ""
    age = _age_on(comp.date_of_birth, first_date) if first_date else None
    if age is None or age >= 18:
        return out

    limits = MINOR_14_15 if age < 16 else MINOR_16_17
    school = comp.is_student

    week_cap = limits.get(
        "max_hours_school_week" if school else "max_hours_nonschool_week",
        limits.get("max_hours_school_week", 40),
    )
    if total > week_cap:
        out.append(Finding(
            rule_code="MINOR_WEEKLY_HOURS",
            severity="violation",
            employee_id=emp_id, employee_name=name, date=first_date,
            message=(
                f"{name} is {age} and scheduled {total:.1f} hours. Federal limit is "
                f"{week_cap} in a {'school' if school else 'non-school'} week."
            ),
            citation="29 CFR §570.35",
        ))

    day_cap = limits.get(
        "max_hours_school_day" if school else "max_hours_nonschool_day",
        limits.get("max_hours_school_day", 8),
    )
    for day, hours in sorted(per_day.items()):
        if hours > day_cap:
            out.append(Finding(
                rule_code="MINOR_DAILY_HOURS",
                severity="violation",
                employee_id=emp_id, employee_name=name, date=day,
                message=(
                    f"{name} is {age} and works {hours:.1f} hours on {day}. "
                    f"Federal limit is {day_cap}."
                ),
                citation="29 CFR §570.35",
            ))

    if age < 16:
        for s in shifts:
            start_hour = _minutes(s.start_time) / 60
            end_hour = _minutes(s.end_time) / 60
            latest = MINOR_14_15["latest_hour_summer"] if _is_summer(s.date) else MINOR_14_15["latest_hour"]

            if start_hour < MINOR_14_15["earliest_hour"]:
                out.append(Finding(
                    rule_code="MINOR_TOO_EARLY",
                    severity="violation",
                    employee_id=emp_id, employee_name=name, date=s.date,
                    message=(
                        f"{name} is {age} and starts at {s.start_time} on {s.date}. "
                        f"No work before 07:00."
                    ),
                    citation="29 CFR §570.35",
                ))
            if 0 < end_hour <= 24 and end_hour > latest:
                out.append(Finding(
                    rule_code="MINOR_TOO_LATE",
                    severity="violation",
                    employee_id=emp_id, employee_name=name, date=s.date,
                    message=(
                        f"{name} is {age} and works until {s.end_time} on {s.date}. "
                        f"Cut-off is {latest:02d}:00."
                    ),
                    citation="29 CFR §570.35",
                ))

    return out


def _check_notice(
    schedule: Schedule, rules: Rules, published_at: Optional[str],
) -> List[Finding]:
    """Fair Workweek advance-notice requirement."""
    if not rules.advance_notice_days:
        return []

    try:
        week_start = date.fromisoformat(schedule.week_start)
    except ValueError:
        return []

    when = date.today()
    if published_at:
        try:
            when = datetime.fromisoformat(published_at.replace("Z", "+00:00")).date()
        except ValueError:
            pass

    notice = (week_start - when).days
    if notice < rules.advance_notice_days:
        short = rules.advance_notice_days - notice
        return [Finding(
            rule_code="ADVANCE_NOTICE",
            severity="violation",
            date=schedule.week_start,
            message=(
                f"{rules.name} requires {rules.advance_notice_days} days' notice. This schedule "
                f"gives {notice}. Publishing {short} day{'s' if short != 1 else ''} late may "
                f"trigger predictability pay for every shift."
            ),
            citation=rules.citation,
        )]
    return []


def summarize(findings: List[Finding]) -> dict:
    """Roll findings up into something a header bar can show."""
    violations = [f for f in findings if f.severity == "violation"]
    warnings = [f for f in findings if f.severity == "warning"]
    exposure = sum(f.exposure_cents for f in findings)

    if violations:
        verdict, headline = "blocked", f"{len(violations)} likely violation{'s' if len(violations) != 1 else ''} to resolve"
    elif warnings:
        verdict, headline = "review", f"{len(warnings)} thing{'s' if len(warnings) != 1 else ''} worth a look"
    else:
        verdict, headline = "clear", "Nothing flagged"

    return {
        "verdict": verdict,
        "headline": headline,
        "violations": len(violations),
        "warnings": len(warnings),
        "info": len([f for f in findings if f.severity == "info"]),
        "estimated_exposure_cents": exposure,
        "estimated_exposure": round(exposure / 100, 2),
        "findings": [f.as_dict() for f in findings],
        "disclaimer": (
            "Advisory only. Ordinances change and carve-outs are common — confirm "
            "anything flagged with your own counsel before relying on it."
        ),
    }
