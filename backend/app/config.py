"""
Reading configuration out of the environment, safely.

A Stripe secret key was set in Railway as `"sk_live_..."` — with the quotes as
part of the value. Every Stripe call then failed with "Invalid API Key", while
`bool(STRIPE_SECRET_KEY)` was perfectly true, so the app believed it was
configured and the dashboard said nothing was wrong.

That is a tedious thing to debug and an easy thing to do: paste a quoted value
into a variables UI, or copy a line out of a .env file, and the quotes travel
with it. Same for a trailing space or a newline picked up from a terminal.

So nothing reads a credential raw. `env()` strips whitespace and one matching
pair of surrounding quotes, and `require()` refuses a value that still looks
wrong rather than letting it fail later at the vendor.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

log = logging.getLogger(__name__)


def env(name: str, default: str = "") -> str:
    """
    The value, cleaned of the ways a copy-paste mangles it.

    Strips surrounding whitespace, then one matching pair of quotes — once, so
    a value that genuinely begins and ends with a quote character is not eaten
    repeatedly.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default

    value = raw.strip()
    for quote in ('"', "'"):
        if len(value) >= 2 and value[0] == quote and value[-1] == quote:
            value = value[1:-1].strip()
            break

    if value != raw and raw.strip() != value:
        log.info("%s had surrounding quotes or whitespace; using the cleaned value", name)

    return value or default


# What each kind of credential is supposed to start with. Catching this at boot
# turns "why is checkout returning 502" into a line in the startup log.
PREFIXES = {
    "STRIPE_SECRET_KEY": ("sk_test_", "sk_live_", "rk_test_", "rk_live_"),
    "STRIPE_PUBLIC_KEY": ("pk_test_", "pk_live_"),
    "STRIPE_WEBHOOK_SECRET": ("whsec_",),
    "STRIPE_PRICE_BASE": ("price_",),
    "STRIPE_PRICE_MODULE": ("price_",),
    "STRIPE_PRICE_AI_OVERAGE": ("price_",),
    "ANTHROPIC_API_KEY": ("sk-ant-",),
    "RESEND_API_KEY": ("re_",),
}


def malformed(name: str, value: str) -> Optional[str]:
    """A complaint about this value, or None if it looks right."""
    if not value:
        return None
    expected = PREFIXES.get(name)
    if expected and not value.startswith(expected):
        shown = value[:6] + "…" if len(value) > 6 else "…"
        return (f"{name} starts with {shown!r}; expected one of "
                f"{', '.join(expected)}. A pasted value that kept its quotes "
                f"is the usual cause.")
    return None


def check_all() -> list[str]:
    """
    Every configured credential that does not look like what it claims to be.

    Reported at startup and surfaced at /health, because the failure mode this
    exists for is one where everything looks configured and nothing works.
    """
    problems = []
    for name in PREFIXES:
        complaint = malformed(name, env(name))
        if complaint:
            problems.append(complaint)
    return problems


def stripe_mode() -> str:
    """Which Stripe is in use — worth saying out loud on a health check."""
    key = env("STRIPE_SECRET_KEY")
    if not key:
        return "unconfigured"
    if key.startswith(("sk_test_", "rk_test_")):
        return "test"
    if key.startswith(("sk_live_", "rk_live_")):
        return "live"
    return "malformed"


# What checkout needs before it can run at all. Naming the missing one is the
# difference between "Stripe not configured" — which sends somebody to check
# the key they already set — and "STRIPE_PUBLIC_KEY is not set".
STRIPE_REQUIRED = (
    "STRIPE_SECRET_KEY",
    "STRIPE_PUBLIC_KEY",
    "STRIPE_PRICE_BASE",
    "STRIPE_PRICE_MODULE",
)
STRIPE_OPTIONAL = ("STRIPE_WEBHOOK_SECRET", "STRIPE_PRICE_AI_OVERAGE")


def stripe_missing() -> list[str]:
    """The variables checkout needs that are not set."""
    return [name for name in STRIPE_REQUIRED if not env(name)]


def stripe_report() -> dict:
    """
    Everything somebody needs to know about Stripe without opening Railway.

    Booleans rather than values — this is a public endpoint, and "is it set"
    is the whole question anyway.
    """
    missing = stripe_missing()
    report = {
        "mode": stripe_mode(),
        "ready_for_checkout": not missing,
        "set": {name: bool(env(name)) for name in STRIPE_REQUIRED + STRIPE_OPTIONAL},
    }
    if missing:
        report["missing"] = missing
    # Payments arrive but nothing activates without this one, which is the
    # quietest way for a billing integration to be broken.
    if not env("STRIPE_WEBHOOK_SECRET"):
        report["warning"] = (
            "STRIPE_WEBHOOK_SECRET is not set. Checkout will work and the "
            "subscription will never activate, because the webhook that grants "
            "access cannot be verified."
        )
    return report
