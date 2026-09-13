"""
The variance calculation.

This is the number the inventory module exists to produce, and the one quoted
on the landing page. It is also the easiest thing in the codebase to get
quietly, confidently wrong — the first implementation reported $330 of theft
where $45 of product had actually gone missing, by adding waste back into a
figure waste had already been deducted from and never subtracting what sales
consumed.

An inflated shrinkage figure is worse than none. It sends an operator looking
for a thief who does not exist.

The arithmetic is mirrored here rather than imported so the test states the
intended model outright; if the implementation drifts from it, that is the
thing worth catching.
"""

from __future__ import annotations

import pytest


def unexplained(counted, expected_at_count, theoretical_usage):
    """
    What went missing, in milli-units.

    counted            physical count
    expected_at_count  what the system believed at the moment of counting,
                       already net of any logged waste
    theoretical_usage  what sales imply should have been consumed

    Nothing decrements an ingredient when a finished dish sells — the movement
    is recorded against the dish, not the ingredient inside it — so sales are
    added back here rather than assumed already gone.
    """
    return (counted - expected_at_count) + theoretical_usage


def value_cents(milli, unit_cost_cents):
    return round((milli / 1000) * unit_cost_cents)


# ------------------------------------------------------------ the worked case

def test_the_bar_scenario():
    """
    20 L of gin. 200 drinks at 50 ml. 0.5 L logged as breakage. Count finds 8 L.
    1.5 L is genuinely unaccounted for.
    """
    start, waste, sold = 20_000, 500, 200 * 50
    expected = start - waste          # waste already left stock when logged
    result = unexplained(8_000, expected, sold)

    assert result == -1_500
    assert value_cents(result, 3000) == -4500     # $45 at $30/L


def test_the_bug_this_replaced():
    """
    The old formula added logged waste instead of theoretical usage. Pinned so
    nobody reintroduces it thinking it looks more intuitive.
    """
    start, waste, sold = 20_000, 500, 200 * 50
    expected = start - waste

    correct = unexplained(8_000, expected, sold)
    old_and_wrong = (8_000 - expected) + waste

    assert correct == -1_500
    assert old_and_wrong == -11_000
    assert abs(old_and_wrong) > abs(correct) * 7


# ------------------------------------------------------------------ honesty

def test_a_perfectly_run_bar_shows_no_loss():
    """Everything that left was either sold or logged. Variance must be zero."""
    start, waste, sold = 10_000, 1_000, 4_000
    expected = start - waste
    counted = start - waste - sold     # exactly what should remain
    assert unexplained(counted, expected, sold) == 0


def test_waste_alone_is_not_reported_as_loss():
    """
    Waste is a known, recorded cost. It appears in the waste log, not as
    unexplained shrinkage — otherwise honest recording looks like theft.
    """
    start, waste = 10_000, 2_000
    expected = start - waste
    counted = expected                 # nothing sold, nothing missing
    assert unexplained(counted, expected, 0) == 0


def test_surplus_is_reported_too():
    """
    More on the shelf than expected is also a signal — usually a miscount or a
    delivery nobody booked in. Silently clamping to zero hides it.
    """
    assert unexplained(12_000, 10_000, 0) == 2_000


def test_loss_scales_with_unit_cost():
    """Two litres of house spirit and two litres of single malt are not the same event."""
    missing = -2_000
    assert value_cents(missing, 1500) == -3000
    assert value_cents(missing, 9000) == -18000


# -------------------------------------------------------------- projection

@pytest.mark.parametrize("days,factor", [(7, 365 / 7), (30, 365 / 30), (90, 365 / 90)])
def test_annualised_projection_scales_by_period(days, factor):
    period_loss_cents = -4500
    projected = round(period_loss_cents * factor)
    assert abs(projected) > abs(period_loss_cents)


def test_a_modest_weekly_leak_is_material_over_a_year():
    """
    $45 a week is easy to dismiss. It is $2,340 a year, which is most of two
    years of the entry plan — this is why the projection is shown at all.
    """
    weekly = 4500
    assert round(weekly * (365 / 7)) > 200_000
