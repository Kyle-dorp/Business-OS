"""
The module catalogue and the pricing ladder.

These two lists drifting apart is not a hypothetical: billing once validated
against a set of modules that did not exist, while the app gated tabs on a
different set entirely. Nothing looked broken because nothing had charged a
card yet. A subscription would have priced modules the product does not have
and billed nothing for the ones it does.

So the agreement between platform.MODULES and the catalogue is asserted, not
assumed, and the pricing ladder is pinned at every step.
"""

from __future__ import annotations

import pytest

from backend.app.modules_registry import (
    ALL_MODULES,
    ALWAYS_ON,
    BILLABLE_KEYS,
    CATALOGUE,
    EACH_MODULE_CENTS,
    FIRST_MODULE_CENTS,
    billable,
    catalogue_payload,
    quote_cents,
    stitched_cents,
)
from backend.app.platform import MODULES as PLATFORM_MODULES


# ------------------------------------------------------- the two registries

def test_catalogue_covers_every_platform_module():
    """Anything the app can gate a tab on must have a price and a description."""
    missing = set(PLATFORM_MODULES) - set(ALL_MODULES)
    assert not missing, f"platform modules with no catalogue entry: {sorted(missing)}"


def test_catalogue_invents_nothing():
    """A catalogued module the app cannot enable would be sold and never delivered."""
    extra = set(ALL_MODULES) - set(PLATFORM_MODULES)
    assert not extra, f"catalogued but not a real module: {sorted(extra)}"


def test_keys_are_unique():
    keys = [m.key for m in CATALOGUE]
    assert len(keys) == len(set(keys))


# ------------------------------------------------------------- always-on

def test_always_on_modules_are_never_billable():
    """A workspace with no overview, settings or notifications is not a workspace."""
    for key in ALWAYS_ON:
        assert key in ALL_MODULES, f"{key} is not catalogued"
        assert not ALL_MODULES[key].billable, f"{key} must not be chargeable"


def test_always_on_are_filtered_out_of_billing():
    assert billable(list(ALWAYS_ON)) == []


def test_always_on_have_no_market_price():
    """Comparing a free module against a competitor price would inflate savings."""
    for key in ALWAYS_ON:
        assert ALL_MODULES[key].market_price == 0


# --------------------------------------------------------------- the ladder

def test_no_modules_costs_nothing():
    assert quote_cents(0) == 0


def test_first_module_is_the_base_price():
    assert quote_cents(1) == FIRST_MODULE_CENTS


@pytest.mark.parametrize("n", range(2, 10))
def test_each_additional_module_adds_exactly_one_step(n):
    assert quote_cents(n) - quote_cents(n - 1) == EACH_MODULE_CENTS


def test_ladder_never_goes_backwards():
    prices = [quote_cents(n) for n in range(0, len(BILLABLE_KEYS) + 1)]
    assert prices == sorted(prices)


def test_full_stack_price_is_sane():
    """
    Every billable module at once should land between a point solution and the
    enterprise suites this undercuts. If a module is added and this fails, the
    pricing story needs revisiting rather than the test.
    """
    full = quote_cents(len(BILLABLE_KEYS))
    assert 8_000 < full < 20_000, f"full stack at ${full / 100:.0f} is outside the intended band"


# ---------------------------------------------------------- the comparison

def test_unknown_keys_are_dropped_not_priced():
    assert billable(["scheduling", "definitely-not-a-module"]) == ["scheduling"]


def test_stitched_comparison_only_counts_billable_modules():
    with_always_on = stitched_cents(["scheduling", *ALWAYS_ON])
    alone = stitched_cents(["scheduling"])
    assert with_always_on == alone


def test_multi_module_stacks_always_beat_buying_separately():
    """
    The whole pitch is that consolidating is cheaper. If any realistic stack of
    two or more is not, the pitch is wrong and the page would be lying.
    """
    for n in range(2, len(BILLABLE_KEYS) + 1):
        keys = BILLABLE_KEYS[:n]
        ours = quote_cents(n)
        theirs = stitched_cents(keys)
        assert ours < theirs, f"{n} modules: ${ours/100:.0f} here vs ${theirs/100:.0f} elsewhere"


# ------------------------------------------------------------------ payload

def test_payload_is_complete_for_the_billing_screen():
    required = {"key", "name", "tagline", "description", "icon",
                "billable", "market_price", "replaces"}
    for entry in catalogue_payload():
        assert required <= set(entry), f"{entry.get('key')} is missing {required - set(entry)}"


def test_every_billable_module_explains_itself():
    """A module somebody is asked to pay for needs to say what it does."""
    for m in CATALOGUE:
        if m.billable:
            assert m.name and m.tagline and m.description
            assert len(m.description) > 30, f"{m.key} description is too thin to sell"
