"""
What the API exposes, as a whole.

Four times now the same fault has appeared in a different costume: two module
registries that disagreed, two AI surfaces with two budgets and two models, two
invoicing implementations, and a 580-line router file nothing called. Each was
invisible reading any single file, because each file was internally consistent.
Only the whole surface shows it.

So this pins the shape rather than the behaviour. Adding a new top-level
prefix, or a second route for a job that already has one, has to be a
deliberate act that changes this file.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.fixture(scope="module")
def spec():
    with TestClient(app) as c:
        return json.loads(c.get("/openapi.json").text)


@pytest.fixture(scope="module")
def paths(spec):
    return sorted(spec["paths"])


# Everything the product actually serves. A new entry here should mean somebody
# decided to add a surface, not that a file got imported.
KNOWN_PREFIXES = {
    "/agent",                   # the Ask agent
    "/assistant",               # the Scheduling AI page
    "/admin",                   # platform administration
    "/auth",                    # sign-in, accounts, memberships
    "/availability",            # staff availability
    "/availability-requests",
    "/billing",                 # subscriptions and Stripe
    "/booking-admin",           # the operator diary
    "/coverage-rules",
    "/crew-targets",
    "/debug",
    "/departments",
    "/docs", "/redoc", "/openapi.json",
    "/email",
    "/employee-positions",
    "/employees",
    "/health",
    "/labor-projections",
    "/manager-settings",
    "/my",                      # the employee's own view
    "/notifications",
    "/oauth", "/auth/google",
    "/ops",                     # operations: recipes, variance, waste, counts
    "/platform",                # the accounting and business core
    "/positions",
    "/public",                  # the customer-facing booker
    "/schedule-shifts",
    "/schedules",
    "/security",
    "/temporary-unavailability",
}

# Deleted deliberately. routers.py was a parallel API for jobs that already had
# working, tested implementations: three of its routes returned 500 on every
# call, one silently discarded five of the seven fields it was given, and the
# frontend referenced none of it.
DELETED_PREFIXES = (
    "/inventory/",
    "/customers/",
    "/invoicing/",
    "/payroll/",
    "/team/",
    "/analytics/",
    "/booking/",
)


def test_no_route_lives_under_a_deleted_prefix(paths):
    """
    These duplicated /platform/invoices, /platform/contacts,
    /platform/inventory, /platform/finance/payroll and /booking-admin. A second
    implementation of a job is how the two module registries came to disagree
    about what the product sells.
    """
    revived = [p for p in paths if p.startswith(DELETED_PREFIXES)]
    assert not revived, f"a deleted API surface came back: {revived}"


def test_every_route_belongs_to_a_known_surface(paths):
    """
    The check that would have caught routers.py on the day it was mounted.
    Nothing here says those routes were wrong — only that nobody decided to
    add them.
    """
    unknown = []
    for path in paths:
        if path in ("/", ""):
            continue
        top = "/" + path.lstrip("/").split("/")[0]
        if top not in KNOWN_PREFIXES and path not in KNOWN_PREFIXES:
            unknown.append(path)
    assert not unknown, (
        "routes under an unrecognised prefix — add it to KNOWN_PREFIXES if it "
        f"is deliberate: {unknown}"
    )


def test_no_two_routes_share_a_method_and_path(spec):
    """
    FastAPI takes the first match and never warns about the second. A shadowed
    route looks registered, appears in the docs, and can never be reached — a
    shape this project has hit before.
    """
    seen = {}
    duplicates = []
    for path, methods in spec["paths"].items():
        for method in methods:
            key = (method.upper(), path)
            if key in seen:
                duplicates.append(key)
            seen[key] = True
    assert not duplicates, f"shadowed routes: {duplicates}"


def test_each_money_job_has_exactly_one_surface(paths):
    """
    One place to create an invoice, one to run payroll, one to take a payment.
    Two implementations means one of them is the untested one, and no way to
    tell which a customer used.
    """
    def creators(*needles):
        return [p for p in paths if all(n in p for n in needles)]

    invoice_creators = [p for p in creators("invoice") if not p.endswith("}")]
    assert all(p.startswith("/platform") for p in invoice_creators), (
        f"invoicing exists outside /platform: {invoice_creators}"
    )

    payroll_paths = creators("payroll")
    assert all(p.startswith("/platform") for p in payroll_paths), (
        f"payroll exists outside /platform: {payroll_paths}"
    )


def test_the_customer_facing_booker_survived(paths):
    """
    Deleting the unused /booking/* routes must not have touched the public
    booker, which is a different thing with the same word in it.
    """
    public = [p for p in paths if p.startswith("/public/book/")]
    assert public, "the public booking routes are gone"
    assert any(p.endswith("/book") for p in public), "customers cannot book"
    assert any("cancel" in p for p in public), "customers cannot cancel"


def test_the_operator_diary_survived(paths):
    assert any(p.startswith("/booking-admin") for p in paths)


def test_the_accounting_core_survived(paths):
    for required in ("/platform/invoices", "/platform/contacts",
                     "/platform/inventory", "/platform/finance/payroll"):
        assert required in paths, f"{required} is gone"
