"""
Which paths bypass authentication.

This is the highest-consequence list in the codebase. Everything on it is
reachable by the entire internet; everything off it 401s. Two mistakes are
easy to make here and neither is visible at a glance:

  - Forgetting a genuinely public path, which silently breaks a customer-facing
    flow. The Stripe webhook and public booking were both broken this way.
  - Using a prefix where an exact match belongs, which opens every future path
    under it. `/billing/webhook` as a prefix would also expose
    `/billing/webhook-test` the day somebody adds one.

So the boundary is pinned rather than assumed.
"""

from __future__ import annotations

import pytest

from backend.app.main import PUBLIC_PATHS, PUBLIC_PREFIXES


def is_public(path: str) -> bool:
    """Mirrors the check in authentication_middleware."""
    return path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES)


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/health",
        "/openapi.json",
        "/docs",
        "/auth/login",
        "/auth/setup",
        "/auth/setup-status",
        # Stripe cannot hold a bearer token; it authenticates by signature.
        "/billing/webhook",
        # Someone redeeming a reset code cannot sign in by definition.
        "/security/reset/redeem",
        # Google sign-in happens before a session exists.
        "/auth/google/config",
        "/auth/google/login",
        # Customers booking an appointment are not users.
        "/public/book/1",
        "/public/book/42/slots",
        "/public/book/42/next-available",
        "/public/book/42/book",
        "/public/book/42/cancel/7",
    ],
)
def test_reachable_without_a_token(path):
    assert is_public(path), f"{path} must be reachable without signing in"


@pytest.mark.parametrize(
    "path",
    [
        # Billing, except the webhook itself.
        "/billing/quote",
        "/billing/preview",
        "/billing/checkout",
        "/billing/portal",
        "/billing/sync",
        "/billing/report-ai-usage",
        "/billing/subscription",
        # The agent reads and writes business data.
        "/agent/chat",
        "/agent/usage",
        "/agent/proposals/1/confirm",
        "/agent/support/tickets",
        # Operations.
        "/ops/preflight/1",
        "/ops/compliance/1",
        "/ops/compliance/profile",
        "/ops/compliance/jurisdictions",
        "/ops/inventory/variance",
        "/ops/inventory/count",
        # Issuing a reset code is a manager action and needs a session —
        # only redeeming one is public.
        "/security/reset/issue",
        "/security/lockouts",
        # Linking Google requires proving you already own the account.
        "/auth/google/link",
        "/auth/google/unlink",
        "/auth/google/status",
        # Core business data.
        "/platform/invoices",
        "/platform/reports/profit-loss",
        "/employees",
        "/schedules",
        "/payroll/periods",
        "/admin/customers",
    ],
)
def test_requires_a_token(path):
    assert not is_public(path), f"{path} must NOT be reachable without signing in"


@pytest.mark.parametrize(
    "path",
    [
        "/billing/webhooks-fake",
        "/billing/webhook-test",
        "/billing/webhookextra",
        "/publicity",
        "/public-data",
        "/docsomething",
    ],
)
def test_near_misses_do_not_slip_through_on_a_prefix(path):
    """
    Paths that merely *look* like a public one.

    `/publicity` and `/billing/webhook-test` are the shapes that a careless
    prefix would wave through. None of these routes exist today, which is
    exactly why the test matters — it holds when one does.
    """
    assert not is_public(path), f"{path} slipped past the auth boundary"


def test_webhook_is_an_exact_match_not_a_prefix():
    assert "/billing/webhook" in PUBLIC_PATHS
    assert not any(p.startswith("/billing") for p in PUBLIC_PREFIXES)


def test_no_prefix_is_dangerously_short():
    """A one- or two-character prefix would open most of the API."""
    for prefix in PUBLIC_PREFIXES:
        assert len(prefix) >= 5, f"{prefix!r} is too broad to be safe"
        assert prefix.startswith("/"), f"{prefix!r} must be rooted"
