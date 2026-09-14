"""
The scheduler's primitives.

860 lines of constraint solving sit on top of half a dozen small functions, and
all of them were uncovered. These are the ones where a wrong answer does not
throw — it produces a schedule that looks fine and is not.

parse_time is the sharpest of them. It is called in 35 places, nearly all
inside generation, and it used to raise on any string without a colon: a single
row holding "9" instead of "09:00" took down the whole week with an unexplained
500. It also read "25:00" as 1500 and "09:99" as 639, which is worse than
crashing, because the solver then reasoned about a shift running past midnight
and produced a rota that was quietly wrong.
"""

from __future__ import annotations

import pytest

from backend.app.models import Employee, ManagerSettings
from backend.app.scheduler import (
    date_range,
    effective_rate,
    overlap_minutes,
    parse_time,
    role_matches,
)


# ---------------------------------------------------------------- parse_time

@pytest.mark.parametrize(
    "value,expected",
    [
        ("00:00", 0),
        ("09:00", 540),
        ("9:00", 540),        # a browser may omit the leading zero
        ("12:30", 750),
        ("23:59", 1439),
        ("09:30:45", 570),    # seconds are ignored, not rejected
    ],
)
def test_valid_times_parse(value, expected):
    assert parse_time(value) == expected


@pytest.mark.parametrize("value", ["", None])
def test_blank_falls_back_to_the_default(value):
    """
    Callers pass 0 for a start and 1440 for an end, so a blank end time means
    "until close" rather than "midnight exactly at the start of the day".
    """
    assert parse_time(value, default=0) == 0
    assert parse_time(value, default=1440) == 1440


@pytest.mark.parametrize("value", ["9", "nine", "09.00", "9am", "--", ":", "::"])
def test_unparseable_input_does_not_raise(value):
    """
    The regression this guards. Any of these used to raise ValueError from deep
    inside generation, taking down a whole week of scheduling.
    """
    assert parse_time(value, default=0) == 0


@pytest.mark.parametrize("value", ["25:00", "24:00", "09:99", "-1:00", "00:-5", "99:99"])
def test_out_of_range_is_rejected_rather_than_accepted(value):
    """
    Silently accepting these is worse than refusing them. "25:00" as 1500
    minutes produces a shift that runs past midnight, and the solver reasons
    about it as though that were intended.
    """
    assert parse_time(value, default=0) == 0


def test_midnight_and_end_of_day_are_distinguishable():
    """
    24:00 is not a valid clock time here. A caller wanting end-of-day passes
    1440 as the default and leaves the value blank.
    """
    assert parse_time("00:00") == 0
    assert parse_time("", default=1440) == 1440
    assert parse_time("23:59") == 1439


# ------------------------------------------------------------ overlap_minutes

@pytest.mark.parametrize(
    "a,b,expected",
    [
        ((540, 1020), (540, 1020), 480),   # identical
        ((540, 1020), (600, 660), 60),     # fully contained
        ((540, 660), (600, 720), 60),      # partial
        ((540, 600), (600, 660), 0),       # touching, not overlapping
        ((540, 600), (660, 720), 0),       # disjoint
        ((660, 720), (540, 600), 0),       # disjoint, reversed
    ],
)
def test_overlap(a, b, expected):
    assert overlap_minutes(a[0], a[1], b[0], b[1]) == expected


def test_touching_intervals_do_not_overlap():
    """
    A shift ending at 10:00 and one starting at 10:00 are back-to-back, not
    concurrent. Counting that as overlap would block every legitimate handover.
    """
    assert overlap_minutes(540, 600, 600, 660) == 0


def test_overlap_is_symmetric():
    assert overlap_minutes(540, 700, 600, 800) == overlap_minutes(600, 800, 540, 700)


def test_overlap_is_never_negative():
    assert overlap_minutes(600, 540, 700, 800) == 0


# ---------------------------------------------------------------- date_range

def test_a_week_is_seven_consecutive_days():
    days = date_range("2026-09-14")
    assert len(days) == 7
    assert days[0] == "2026-09-14"
    assert days[-1] == "2026-09-20"


def test_a_week_can_cross_a_year_boundary():
    """Rotas do not stop at New Year, and the last week of December spans it."""
    days = date_range("2026-12-28")
    assert days[0] == "2026-12-28"
    assert days[-1] == "2027-01-03"
    assert len(set(days)) == 7


def test_a_week_can_cross_a_leap_day():
    days = date_range("2028-02-26")
    assert "2028-02-29" in days, "a leap day was skipped"
    assert len(days) == 7


def test_days_are_strictly_increasing():
    days = date_range("2026-03-02")
    assert days == sorted(days)
    assert len(set(days)) == 7


# --------------------------------------------------------------- role_matches

def test_anyone_satisfies_a_plain_employee_requirement():
    for role in ("employee", "shift_lead", "gm"):
        assert role_matches(role, "employee")


def test_a_shift_lead_requirement_accepts_leads_and_gms():
    """A GM can cover a lead's slot. The hierarchy only runs one way."""
    assert role_matches("shift_lead", "shift_lead")
    assert role_matches("gm", "shift_lead")
    assert not role_matches("employee", "shift_lead")


def test_a_gm_requirement_accepts_only_a_gm():
    assert role_matches("gm", "gm")
    assert not role_matches("shift_lead", "gm")
    assert not role_matches("employee", "gm")


def test_seniority_does_not_run_downwards_by_accident():
    """
    The one that would be expensive: an employee silently satisfying a GM
    requirement means a shift that legally needed a manager did not have one.
    """
    assert not role_matches("employee", "gm")
    assert not role_matches("employee", "shift_lead")


# -------------------------------------------------------------- effective_rate

def _settings(rate: float = 18.20) -> ManagerSettings:
    return ManagerSettings(business_id=1, employee_hourly_rate=rate)


def test_a_regular_employee_is_paid_the_base_rate():
    e = Employee(business_id=1, name="Sam", department="General", role="employee")
    assert effective_rate(e, _settings(18.20)) == 18.20


@pytest.mark.parametrize("role", ["shift_lead", "gm"])
def test_seniority_carries_a_premium(role):
    e = Employee(business_id=1, name="Sam", department="General", role=role)
    assert effective_rate(e, _settings(18.20)) == 19.20


def test_the_premium_follows_the_base_rate():
    """Raise the base and the premium moves with it, rather than being fixed."""
    e = Employee(business_id=1, name="Sam", department="General", role="gm")
    assert effective_rate(e, _settings(25.00)) == 26.00


def test_an_unknown_role_is_paid_the_base_rate():
    """Unrecognised data should under-pay rather than over-pay by default."""
    e = Employee(business_id=1, name="Sam", department="General", role="wizard")
    assert effective_rate(e, _settings(18.20)) == 18.20
