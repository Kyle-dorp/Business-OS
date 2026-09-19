"""
The landing page and the product agreeing about what is for sale.

The landing page is the only thing most people will ever read about this
product, and it was maintained by hand against a catalogue that moved. By the
time anybody looked it was selling four modules that do not exist — Payroll
prep, Menus & QR ordering, Sales tracking, Team communication — and omitting
four that do: Bills & purchasing, Tasks, Reports and the assistant.

It also disagreed with itself. The headline says a stitched stack costs
$392/mo, which is the correct total from the registry; the interactive picker
below it could reach $550, because its list was a different list.

Nobody caught any of it, because the page is not deployed. That is being fixed
separately, and when it is, none of this can be allowed to be true.

The same failure has happened once before inside the product: modules_registry
opens by recording that it "previously described a set of modules that did not
exist" while billing validated against a third, invented set. The fix there was
one source of truth. This is that fix applied to the shop window.
"""

from __future__ import annotations

import pathlib
import re

from backend.app.modules_registry import (
    CATALOGUE,
    EACH_MODULE_CENTS,
    FIRST_MODULE_CENTS,
)

LANDING = pathlib.Path(__file__).resolve().parents[1] / "landing" / "index.html"
BILLABLE = [m for m in CATALOGUE if m.billable]


def _page() -> str:
    return LANDING.read_text(encoding="utf-8")


def _advertised() -> list[tuple[str, int]]:
    """The (name, market price) pairs the picker offers."""
    page = _page()
    start = page.index("var MODULES = [")
    block = page[start : page.index("];", start)]
    return [
        (m.group(1), int(m.group(2)))
        for m in re.finditer(r"name:'([^']+)'\s*,\s*market:(\d+)", block)
    ]


# ===========================================================================
# What is on the shelf
# ===========================================================================

def test_the_landing_page_exists():
    assert LANDING.exists(), "the landing page is the pitch; it cannot go missing"


def test_it_sells_exactly_what_the_product_has():
    assert sorted(name for name, _ in _advertised()) == sorted(m.name for m in BILLABLE)


def test_it_sells_nothing_that_does_not_exist():
    """
    The specific failure: four modules on the page that the product had never
    had. Somebody switching them on in the picker was pricing a stack they
    could not buy.
    """
    real = {m.name for m in BILLABLE}
    invented = [name for name, _ in _advertised() if name not in real]
    assert invented == []


def test_it_omits_nothing_the_product_does_have():
    advertised = {name for name, _ in _advertised()}
    missing = [m.name for m in BILLABLE if m.name not in advertised]
    assert missing == []


def test_every_comparison_price_matches_the_registry():
    """
    These are the numbers the whole pitch rests on. A module quoted at the
    wrong competitor price is a claim about somebody else's business.
    """
    registry = {m.name: m.market_price for m in BILLABLE}
    for name, market in _advertised():
        assert market == registry[name], f"{name} is quoted at ${market}, registry says ${registry[name]}"


# ===========================================================================
# The arithmetic the page performs in front of the reader
# ===========================================================================

def test_the_hero_card_compares_like_with_like():
    """
    The card animates six scattered subscriptions collapsing into one. It used
    to show six chips — including a payroll service and POS software, neither
    of which this product replaces — and then price six of ours at $79 against
    the ten-module stitched total of $392.

    The arithmetic was right and the comparison was not. Six against ten is the
    kind of claim that is fine until somebody counts.
    """
    page = _page()
    chips = [
        (m.group(1), int(m.group(2)))
        for m in re.finditer(
            r'<span class="cn">([^<]+)</span><span class="cp">\$(\d+)/mo</span>', page
        )
    ]
    assert chips, "the hero chips are gone"

    rows = re.search(r'<div class="u-rows">\s*(.*?)\s*</div>\s*<p', page, re.S)
    assert rows, "the unified card lists nothing"
    named = re.findall(r"<div>([^<]+)</div>", rows.group(1))

    assert len(named) == len(chips), "one chip per module, or the animation lies"

    was = int(re.search(r'class="u-was">\$(\d+)/mo', page).group(1))
    price = int(re.search(r'class="u-price">\$(\d+)/mo', page).group(1))

    assert was == sum(p for _, p in chips), "the struck-through price is not what the chips add up to"
    assert price == (FIRST_MODULE_CENTS + (len(named) - 1) * EACH_MODULE_CENTS) // 100


def test_the_hero_card_names_only_real_modules():
    """`Payroll prep` sat in this card for as long as the page existed."""
    page = _page()
    rows = re.search(r'<div class="u-rows">\s*(.*?)\s*</div>\s*<p', page, re.S)
    named = re.findall(r"<div>([^<]+)</div>", rows.group(1))

    real = {m.name for m in BILLABLE}
    assert [n for n in named if n not in real] == []


def test_the_picker_starts_where_the_page_animates_from():
    """
    The counter tweens from a hardcoded starting figure. If the default-on set
    changes and that number does not, the first thing a visitor sees is a
    number counting to the wrong place and stopping.
    """
    page = _page()
    shown = re.search(r"var shown = \{\s*stitched:(\d+),\s*eos:(\d+)\s*\}", page)
    assert shown, "the starting figures are gone"

    start = page.index("var MODULES = [")
    block = page[start : page.index("];", start)]
    on = [
        (m.group(1), int(m.group(2)))
        for m in re.finditer(r"name:'([^']+)'\s*,\s*market:(\d+)\s*,\s*on:true", block)
    ]

    assert sum(price for _, price in on) == int(shown.group(1))
    expected_ours = (FIRST_MODULE_CENTS + (len(on) - 1) * EACH_MODULE_CENTS) // 100
    assert int(shown.group(2)) == expected_ours


def test_the_page_quotes_the_price_the_product_charges():
    """
    The one number that turns into a card being charged. A landing page saying
    $29 while checkout bills something else is the worst sentence in software.
    """
    page = _page()
    # Parsed rather than string-matched: they are declared on one line as
    # `var FIRST = 29, EACH = 10;`, and a test that only passes for one
    # formatting of that is a test about formatting.
    first = re.search(r"\bFIRST\s*=\s*(\d+)", page)
    each = re.search(r"\bEACH\s*=\s*(\d+)", page)
    assert first and each, "the page no longer states its own pricing"

    assert int(first.group(1)) == FIRST_MODULE_CENTS // 100
    assert int(each.group(1)) == EACH_MODULE_CENTS // 100


def test_a_module_with_no_equivalent_does_not_claim_to_cost_nothing():
    """
    The assistant has a market price of 0, meaning nothing comparable is sold
    at this price — not that it is worth nothing. Rendering "$0/mo" beside it
    would say the opposite of what is meant.
    """
    assert "'no equivalent'" in _page()


# ===========================================================================
# Being reachable
# ===========================================================================
#
# The root used to serve the sign-in screen and landing/index.html was
# referenced by nothing — not the Dockerfile, not a route, not the build. The
# page nobody could see is the page that drifted.
#
# Moving the pitch to / moves the product to /app, and the first version of
# that change shipped an outage in local testing: /app was not in PUBLIC_PATHS,
# so the authentication middleware answered the only link into the product with
# "Sign in required". The landing page loaded, Sign in went nowhere, and there
# was no way to reach the app at all.

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import PUBLIC_PATHS, PUBLIC_PREFIXES, app  # noqa: E402


def test_the_root_serves_the_pitch_not_the_sign_in_screen():
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    body = response.text
    assert "Six logins" in body, "the root is not the landing page"


def test_the_app_is_reachable_without_a_token():
    """
    The assertion that would have caught the outage. /app renders the sign-in
    screen, so requiring a token to reach it means nobody can ever sign in.
    """
    assert "/app" in PUBLIC_PATHS
    with TestClient(app) as client:
        response = client.get("/app")
    assert response.status_code != 401, "the only way into the product needs a token"


def test_client_side_routes_under_the_app_are_reachable_too():
    assert "/app/" in PUBLIC_PREFIXES
    with TestClient(app) as client:
        assert client.get("/app/settings").status_code != 401


def test_the_public_prefixes_all_end_in_a_slash():
    """
    The file's own rule, restated where it can fail. "/app" as a prefix would
    also match /apply and /appointments — any route added later whose name
    merely starts with those characters would silently become public.
    """
    assert [p for p in PUBLIC_PREFIXES if not p.endswith("/")] == []


def test_the_landing_page_has_a_way_into_the_product():
    """
    It had none. Every call to action was an anchor or a mailto, so serving it
    at the root would have been a front door with no handle.
    """
    assert 'href="/app"' in _page()


def test_the_image_actually_contains_the_landing_page():
    """
    It was in the repository and in no image, which is the whole reason nobody
    ever saw it.
    """
    dockerfile = (LANDING.parents[1] / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY landing" in dockerfile


def test_signing_in_still_works():
    """A route being public must not mean it stopped being guarded elsewhere."""
    with TestClient(app) as client:
        assert client.get("/billing/catalogue").status_code == 401
