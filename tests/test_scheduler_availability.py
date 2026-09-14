"""
Availability blocking, and the solver end to end.

These are the rules that decide whether a person can be put on a shift. A bug
here does not throw — it rosters somebody who told you they were unavailable,
and the first anyone knows is when they do not turn up.

The end-to-end tests run the real OR-Tools solver against a small database.
That is slower than testing the helpers alone, but the helpers were never the
risk: the risk is the solver honouring a constraint the helpers reported
correctly, or quietly not honouring it.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlmodel import Session, select

from backend.app.database import engine
from backend.app.models import (
    Business,
    CoverageRule,
    Employee,
    EmployeePosition,
    ManagerSettings,
    Position,
    RecurringAvailability,
    ScheduleShift,
    TemporaryUnavailability,
)
from backend.app.scheduler import (
    generate_schedule,
    recurring_rule_blocks,
    temporary_rule_blocks,
)
from backend.app.tenancy import set_current_business_id

MONDAY = "2026-09-14"        # a known Monday
TUESDAY = "2026-09-15"
SUNDAY = "2026-09-20"


def _recurring(day_of_week=-1, start="", end="") -> RecurringAvailability:
    return RecurringAvailability(
        business_id=1, employee_id=1, rule_type="unavailable",
        day_of_week=day_of_week, start_time=start, end_time=end,
    )


def _temporary(start_date, end_date, start="", end="") -> TemporaryUnavailability:
    return TemporaryUnavailability(
        business_id=1, employee_id=1,
        start_date=start_date, end_date=end_date,
        start_time=start, end_time=end,
    )


# ------------------------------------------------------- recurring rules

def test_a_rule_for_every_day_blocks_every_day():
    """day_of_week -1 means "always", which is how a standing commitment is stored."""
    rule = _recurring(day_of_week=-1, start="09:00", end="17:00")
    for day in (MONDAY, TUESDAY, SUNDAY):
        assert recurring_rule_blocks(rule, day, 600, 660)


def test_a_weekday_rule_only_blocks_that_weekday():
    rule = _recurring(day_of_week=0, start="09:00", end="17:00")   # Mondays
    assert recurring_rule_blocks(rule, MONDAY, 600, 660)
    assert not recurring_rule_blocks(rule, TUESDAY, 600, 660)


def test_a_blank_window_blocks_the_whole_day():
    """
    No times means unavailable all day. Falling back to 00:00 for the start and
    the end of the day for the finish is what makes that work.
    """
    rule = _recurring(day_of_week=0, start="", end="")
    assert recurring_rule_blocks(rule, MONDAY, 0, 1)
    assert recurring_rule_blocks(rule, MONDAY, 1380, 1439)


def test_a_shift_touching_the_edge_of_a_rule_is_not_blocked():
    """
    Unavailable until 12:00, shift starts at 12:00. That is fine, and treating
    it as a clash would make every legitimate handover impossible.
    """
    rule = _recurring(day_of_week=0, start="09:00", end="12:00")
    assert not recurring_rule_blocks(rule, MONDAY, 720, 780)      # 12:00–13:00
    assert recurring_rule_blocks(rule, MONDAY, 719, 780)          # 11:59 overlaps


def test_partial_overlap_blocks():
    rule = _recurring(day_of_week=0, start="09:00", end="12:00")
    assert recurring_rule_blocks(rule, MONDAY, 660, 780)          # 11:00–13:00


def test_a_malformed_time_on_a_rule_does_not_crash():
    """
    Bad data on one availability row must not take down generation for the
    whole week. It falls back to a whole-day block, which is the safe direction
    — erring towards not scheduling somebody.
    """
    rule = _recurring(day_of_week=0, start="nine", end="five")
    assert recurring_rule_blocks(rule, MONDAY, 600, 660) is True


# ------------------------------------------------------- temporary rules

def test_a_holiday_blocks_inside_its_dates_only():
    rule = _temporary(MONDAY, TUESDAY)
    assert temporary_rule_blocks(rule, MONDAY, 600, 660)
    assert temporary_rule_blocks(rule, TUESDAY, 600, 660)
    assert not temporary_rule_blocks(rule, SUNDAY, 600, 660)


def test_the_boundary_days_of_a_holiday_are_included():
    """A holiday from the 14th to the 15th covers both, not the days between."""
    rule = _temporary(MONDAY, TUESDAY)
    assert temporary_rule_blocks(rule, MONDAY, 0, 1440)
    assert temporary_rule_blocks(rule, TUESDAY, 0, 1440)


def test_a_single_day_holiday_works():
    rule = _temporary(MONDAY, MONDAY)
    assert temporary_rule_blocks(rule, MONDAY, 600, 660)
    assert not temporary_rule_blocks(rule, TUESDAY, 600, 660)


def test_a_part_day_absence_only_blocks_those_hours():
    """A dentist appointment is not a day off."""
    rule = _temporary(MONDAY, MONDAY, start="14:00", end="16:00")
    assert not temporary_rule_blocks(rule, MONDAY, 540, 720)       # morning is fine
    assert temporary_rule_blocks(rule, MONDAY, 840, 900)           # 14:00–15:00 clashes


# --------------------------------------------------------- the solver

@pytest.fixture
def shop():
    """
    A minimal but real workspace: one position, three employees, and settings.
    Built per-test so one test's shifts cannot influence another's solve.
    """
    suffix = uuid.uuid4().hex[:6]
    with Session(engine) as s:
        business = Business(name=f"Rota Co {suffix}", industry="general", active=True)
        s.add(business)
        s.flush()
        bid = business.id

        set_current_business_id(bid)
        try:
            s.add(ManagerSettings(
                business_id=bid, store_name="Rota Co",
                employee_hourly_rate=18.00,
                min_labor_percent=10.0, max_labor_percent=90.0,
            ))
            position = Position(business_id=bid, name="Counter", department="General", active=True)
            s.add(position)
            s.flush()

            employees = []
            for name, role in (("Ana", "gm"), ("Ben", "shift_lead"), ("Cal", "employee")):
                e = Employee(
                    business_id=bid, name=name, department="General", role=role,
                    min_hours_per_week=0, max_hours_per_week=40, active=True,
                )
                s.add(e)
                employees.append(e)
            s.flush()

            # A position-targeted rule can only be filled by somebody assigned
            # to that position. Without these links the solver correctly
            # refuses to cover anything, which looks like a solver bug and is
            # actually missing data.
            for e in employees:
                s.add(EmployeePosition(
                    business_id=bid, employee_id=e.id, position_id=position.id
                ))

            ids = {e.name: e.id for e in employees}
            pid = position.id
            s.commit()
        finally:
            set_current_business_id(1)

    yield {"business_id": bid, "position_id": pid, "employees": ids}
    set_current_business_id(1)


def _rule(bid, pid, day_of_week, start="09:00", end="17:00", minimum=1):
    return CoverageRule(
        business_id=bid, name="Counter cover", day_of_week=day_of_week,
        start_time=start, end_time=end,
        position_ids_json=f"[{pid}]", minimum_count=minimum,
        preferred_count=minimum, hard_minimum=True, active=True,
    )


def _generate(shop, **kwargs):
    set_current_business_id(shop["business_id"])
    try:
        with Session(engine) as s:
            return generate_schedule(s, week_start=MONDAY, **kwargs)
    finally:
        set_current_business_id(1)


def _shifts(schedule_id, business_id):
    set_current_business_id(business_id)
    try:
        with Session(engine) as s:
            return s.exec(
                select(ScheduleShift).where(ScheduleShift.schedule_id == schedule_id)
            ).all()
    finally:
        set_current_business_id(1)


def test_generation_produces_a_schedule(shop):
    result = _generate(shop)
    assert result.get("id"), f"no schedule returned: {sorted(result)}"


def test_a_coverage_rule_is_filled(shop):
    """The basic contract: ask for one person on Monday, get one person on Monday."""
    set_current_business_id(shop["business_id"])
    try:
        with Session(engine) as s:
            s.add(_rule(shop["business_id"], shop["position_id"], day_of_week=0))
            s.commit()
    finally:
        set_current_business_id(1)

    result = _generate(shop)
    sid = result["id"]
    monday = [x for x in _shifts(sid, shop["business_id"]) if x.date == MONDAY]
    assert monday, "a hard-minimum rule went unfilled"


def test_an_unavailable_employee_is_not_scheduled(shop):
    """
    The one that matters in the real world. Everybody is blocked on Monday, so
    the rule cannot be satisfied — and the solver must leave it unfilled rather
    than roster somebody who said no.
    """
    bid = shop["business_id"]
    set_current_business_id(bid)
    try:
        with Session(engine) as s:
            s.add(_rule(bid, shop["position_id"], day_of_week=0))
            for emp_id in shop["employees"].values():
                s.add(RecurringAvailability(
                    business_id=bid, employee_id=emp_id, rule_type="unavailable",
                    day_of_week=0, start_time="", end_time="",
                ))
            s.commit()
    finally:
        set_current_business_id(1)

    result = _generate(shop)
    sid = result["id"]
    monday = [x for x in _shifts(sid, bid) if x.date == MONDAY]

    assert not monday, (
        "somebody was scheduled on a day they were marked unavailable: "
        f"{[(x.employee_id, x.start_time) for x in monday]}"
    )


def test_a_holiday_is_respected(shop):
    bid = shop["business_id"]
    set_current_business_id(bid)
    try:
        with Session(engine) as s:
            s.add(_rule(bid, shop["position_id"], day_of_week=1))    # Tuesday
            for emp_id in shop["employees"].values():
                s.add(TemporaryUnavailability(
                    business_id=bid, employee_id=emp_id,
                    start_date=TUESDAY, end_date=TUESDAY,
                    start_time="", end_time="",
                ))
            s.commit()
    finally:
        set_current_business_id(1)

    result = _generate(shop)
    sid = result["id"]
    assert not [x for x in _shifts(sid, bid) if x.date == TUESDAY]


def test_nobody_works_two_shifts_at_once(shop):
    """
    Two overlapping rules on the same day. With three employees available the
    solver can fill both, but it must not put the same person in both places.
    """
    bid = shop["business_id"]
    set_current_business_id(bid)
    try:
        with Session(engine) as s:
            s.add(_rule(bid, shop["position_id"], 0, "09:00", "13:00"))
            s.add(_rule(bid, shop["position_id"], 0, "11:00", "15:00"))
            s.commit()
    finally:
        set_current_business_id(1)

    result = _generate(shop)
    sid = result["id"]
    monday = [x for x in _shifts(sid, bid) if x.date == MONDAY]

    from backend.app.scheduler import overlap_minutes, parse_time

    for i, a in enumerate(monday):
        for b in monday[i + 1:]:
            if a.employee_id != b.employee_id:
                continue
            clash = overlap_minutes(
                parse_time(a.start_time), parse_time(a.end_time),
                parse_time(b.start_time), parse_time(b.end_time),
            )
            assert clash == 0, (
                f"employee {a.employee_id} double-booked: "
                f"{a.start_time}-{a.end_time} and {b.start_time}-{b.end_time}"
            )


def test_generation_is_deterministic_for_the_same_inputs(shop):
    """
    Two runs over identical data should agree on how many shifts are needed.
    A solver that returns a different answer each time makes every schedule an
    argument nobody can settle.
    """
    bid = shop["business_id"]
    set_current_business_id(bid)
    try:
        with Session(engine) as s:
            s.add(_rule(bid, shop["position_id"], day_of_week=0))
            s.commit()
    finally:
        set_current_business_id(1)

    first = _generate(shop)
    second = _generate(shop)

    a = len(_shifts(first["id"], bid))
    b = len(_shifts(second["id"], bid))
    assert a == b, f"same inputs produced {a} shifts then {b}"


def test_an_empty_workspace_does_not_crash(shop):
    """No rules and no demand is a valid week, not an error."""
    result = _generate(shop)
    assert result.get("id")
    assert _shifts(result["id"], shop["business_id"]) == []


def test_malformed_rule_times_do_not_take_down_generation(shop):
    """
    A single bad row used to raise out of parse_time and fail the whole week.
    It should now be survivable.
    """
    bid = shop["business_id"]
    set_current_business_id(bid)
    try:
        with Session(engine) as s:
            s.add(_rule(bid, shop["position_id"], 0, start="9", end="not-a-time"))
            s.commit()
    finally:
        set_current_business_id(1)

    result = _generate(shop)
    assert result.get("id"), "malformed rule times crashed generation"


def test_an_uncoverable_rule_is_reported_rather_than_dropped(shop):
    """
    Found while diagnosing a fixture of my own: when nobody can fill a rule the
    solver says so by name and time. Silently returning an empty week would
    leave a manager to notice the gap on the day.
    """
    bid = shop["business_id"]
    set_current_business_id(bid)
    try:
        with Session(engine) as s:
            s.add(_rule(bid, shop["position_id"], day_of_week=0))
            for emp_id in shop["employees"].values():
                s.add(RecurringAvailability(
                    business_id=bid, employee_id=emp_id, rule_type="unavailable",
                    day_of_week=0, start_time="", end_time="",
                ))
            s.commit()
    finally:
        set_current_business_id(1)

    result = _generate(shop)
    messages = " ".join(w["message"] for w in result["warnings"])
    assert "Could not cover" in messages, f"no warning raised: {result['warnings']}"
