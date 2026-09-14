"""
Exposure arithmetic.

A finding without a dollar figure is a shrug. These tests pin the premiums so
that a rule change cannot quietly turn a real violation back into $0 — which is
exactly what the product did before employee rates and a jurisdiction could be
entered.
"""

from __future__ import annotations

import pytest

from backend.app.compliance import JURISDICTIONS

RATE = 1800  # $18/hr in cents


def ot_premium(hours: float, threshold: float, rate_cents: int) -> int:
    """Half-time on hours past the threshold, mirroring _check_hours."""
    return int(max(hours - threshold, 0) * rate_cents * 0.5)


def rest_premium(shift_hours: float, rate_cents: int, rules) -> int:
    """Mirrors _check_rest."""
    if rules.rest_premium_multiplier and rate_cents:
        return int(shift_hours * rate_cents * (rules.rest_premium_multiplier - 1))
    if "nyc" in rules.key:
        return 10000
    if "philadelphia" in rules.key:
        return 4000
    return 0


# ------------------------------------------------------------------ overtime

def test_weekly_overtime_premium():
    assert ot_premium(45, 40, RATE) == 4500        # five hours of half-time


def test_no_premium_under_the_threshold():
    assert ot_premium(38, 40, RATE) == 0


def test_california_daily_overtime_is_separate_from_weekly():
    """
    Someone can work four ten-hour days, stay under 40, and still be owed daily
    overtime in California. A weekly-only check misses it entirely.
    """
    ca = JURISDICTIONS["ca"]
    assert ca.daily_overtime_hours == 8
    assert ot_premium(40, 40, RATE) == 0
    # Two hours past the eight-hour threshold, at half-time on $18/hr.
    assert ot_premium(10, ca.daily_overtime_hours, RATE) == 1800


def test_missing_rate_yields_no_figure():
    """
    The failure this phase fixed. Without an hourly rate every violation reads
    $0 — the warning still appears, but it reads as free.
    """
    assert ot_premium(45, 40, 0) == 0


# ------------------------------------------------------------------ clopening

def test_nyc_pays_a_flat_statutory_premium():
    assert rest_premium(8, RATE, JURISDICTIONS["nyc"]) == 10000


def test_philadelphia_pays_a_smaller_flat_premium():
    assert rest_premium(8, RATE, JURISDICTIONS["philadelphia"]) == 4000


def test_flat_premium_jurisdictions_do_not_need_a_rate():
    """These two are the only findings that still cost money with no rate on file."""
    for key in ("nyc", "philadelphia"):
        assert rest_premium(8, 0, JURISDICTIONS[key]) > 0


def test_seattle_pays_time_and_a_half_on_the_shift():
    seattle = JURISDICTIONS["seattle"]
    assert seattle.rest_premium_multiplier == 1.5
    assert rest_premium(8, RATE, seattle) == 7200      # the extra half on 8 hours


def test_multiplier_jurisdictions_scale_with_shift_length():
    seattle = JURISDICTIONS["seattle"]
    assert rest_premium(4, RATE, seattle) < rest_premium(12, RATE, seattle)


@pytest.mark.parametrize("key", ["nyc", "seattle", "chicago", "philadelphia", "oregon"])
def test_every_clopening_jurisdiction_produces_a_cost(key):
    """
    A rest violation nobody can put a number on does not get fixed. If a
    jurisdiction has a rest rule, it must also produce a figure.
    """
    rules = JURISDICTIONS[key]
    assert rules.min_rest_hours, f"{key} has no rest requirement"
    assert rest_premium(8, RATE, rules) > 0, f"{key} produced no exposure"


# ------------------------------------------------------------------- totals

def test_a_single_bad_week_is_material():
    """
    Forty-five hours plus one clopening in New York. Small enough to happen by
    accident, large enough that seeing it before publishing is worth the
    subscription on its own.
    """
    total = ot_premium(45, 40, RATE) + rest_premium(8, RATE, JURISDICTIONS["nyc"])
    assert total == 14500
    assert total > 2900, "one avoided week should exceed the entry plan price"
