"""
Tests for the labor compliance engine.

The rule math here decides whether an operator gets told they're about to break
the law, so the edge cases that are easy to get subtly wrong — shifts crossing
midnight, birthdays that haven't happened yet, jurisdictions that only apply
above a headcount — are pinned down explicitly.
"""

from __future__ import annotations

import pytest

from backend.app.compliance import (
    FEDERAL,
    JURISDICTIONS,
    Finding,
    _age_on,
    _is_summer,
    _minutes,
    _shift_hours,
    resolve_rules,
    summarize,
)
from backend.app.models import ScheduleShift
from backend.app.ops_models import ComplianceProfile


def shift(date_str: str, start: str, end: str, employee_id: int = 1) -> ScheduleShift:
    return ScheduleShift(
        business_id=1, schedule_id=1, date=date_str,
        employee_id=employee_id, start_time=start, end_time=end,
    )


# ----------------------------------------------------------------- time math

@pytest.mark.parametrize(
    "start,end,expected",
    [
        ("09:00", "17:00", 8.0),
        ("11:30", "20:15", 8.75),
        ("22:00", "02:00", 4.0),      # crosses midnight
        ("18:00", "02:30", 8.5),      # crosses midnight, half hour
        ("00:00", "08:00", 8.0),
    ],
)
def test_shift_length(start, end, expected):
    assert _shift_hours(shift("2026-09-11", start, end)) == expected


def test_minutes_parses_and_survives_garbage():
    assert _minutes("14:30") == 870
    assert _minutes("") == 0
    assert _minutes("not a time") == 0


# --------------------------------------------------------------- minor rules

def test_age_respects_birthday_not_yet_passed():
    # Born December, checked in September — still 16, not 17.
    assert _age_on("2009-12-01", "2026-09-12") == 16


def test_age_after_birthday():
    assert _age_on("2009-01-01", "2026-09-12") == 17


def test_age_blank_dob_returns_none():
    assert _age_on("", "2026-09-12") is None
    assert _age_on("garbage", "2026-09-12") is None


def test_summer_window_extends_minor_curfew():
    assert _is_summer("2026-07-04") is True
    assert _is_summer("2026-06-01") is True
    assert _is_summer("2026-01-15") is False
    assert _is_summer("2026-11-20") is False


# ------------------------------------------------------------ jurisdictions

def test_unknown_jurisdiction_falls_back_to_federal():
    profile = ComplianceProfile(business_id=1, jurisdiction="atlantis")
    assert resolve_rules(profile).key == FEDERAL.key


def test_no_profile_falls_back_to_federal():
    assert resolve_rules(None).key == FEDERAL.key


def test_headcount_threshold_gates_the_ordinance():
    """Seattle secure scheduling only bites above 500 employees."""
    small = ComplianceProfile(
        business_id=1, jurisdiction="seattle", industry="food_service", employee_count=20
    )
    assert resolve_rules(small).key == "federal"

    large = ComplianceProfile(
        business_id=1, jurisdiction="seattle", industry="food_service", employee_count=900
    )
    assert resolve_rules(large).key == "seattle"


def test_industry_gate_applies():
    """NYC Fair Workweek covers food service and retail, not a law firm."""
    covered = ComplianceProfile(
        business_id=1, jurisdiction="nyc", industry="food_service", employee_count=30
    )
    assert resolve_rules(covered).key == "nyc"

    not_covered = ComplianceProfile(
        business_id=1, jurisdiction="nyc", industry="professional", employee_count=30
    )
    assert resolve_rules(not_covered).key == "federal"


def test_california_has_daily_overtime_and_double_time():
    ca = JURISDICTIONS["ca"]
    assert ca.daily_overtime_hours == 8
    assert ca.double_time_hours == 12
    assert ca.meal_break_after_hours == 5


def test_predictive_scheduling_jurisdictions_require_notice():
    for key in ("nyc", "seattle", "chicago", "philadelphia", "oregon", "sf"):
        assert JURISDICTIONS[key].advance_notice_days == 14, key


def test_every_jurisdiction_carries_a_citation():
    """A finding without a source is a finding nobody can verify."""
    for key, rules in JURISDICTIONS.items():
        assert rules.citation, f"{key} has no citation"


# ------------------------------------------------------------------ summary

def test_summary_blocks_on_violation():
    out = summarize([
        Finding(rule_code="REST_SHORT", severity="violation", message="x"),
        Finding(rule_code="OT_WEEKLY", severity="warning", message="y"),
    ])
    assert out["verdict"] == "blocked"
    assert out["violations"] == 1
    assert out["warnings"] == 1


def test_summary_reviews_on_warning_only():
    out = summarize([Finding(rule_code="OT_WEEKLY", severity="warning", message="y")])
    assert out["verdict"] == "review"


def test_summary_clear_when_nothing_found():
    out = summarize([])
    assert out["verdict"] == "clear"
    assert out["estimated_exposure"] == 0


def test_summary_totals_exposure_in_dollars():
    out = summarize([
        Finding(rule_code="REST_SHORT", severity="violation", message="x", exposure_cents=10000),
        Finding(rule_code="REST_SHORT", severity="violation", message="x", exposure_cents=4000),
    ])
    assert out["estimated_exposure"] == 140.00


def test_summary_always_carries_the_disclaimer():
    """Advisory framing is not optional — it must survive any refactor."""
    assert "counsel" in summarize([])["disclaimer"]
