"""
What a brand-new workspace contains.

This is the regression guard for the worst bug in this codebase.

/auth/setup created the user, the business and the membership, but never seeded
the workspace — so a new account had no chart of accounts, no location and no
module rows. Every signup produced a business that could not post a journal
entry, issue an invoice, or use the accounting module at all.

/platform/bootstrap could not repair it either: its guard sees the membership,
concludes the workspace is set up, and returns without seeding. The only path
that could have fixed it was the one path that never ran.

Two tests in test_platform.py were failing on exactly this, and had been for
some time. Nobody had run them.

Testing it needs a genuinely empty database, because "first user" only happens
once and other modules in this suite consume it. Rather than skip — a test that
always skips is a test that does not exist — this runs the whole first-run in a
fresh interpreter with its own database, and asserts on what comes back.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Runs inside a clean interpreter against an empty database, and prints one
# JSON line describing what signup produced.
PROBE = r"""
import json, os
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from backend.app.main import app
from backend.app.database import engine
from backend.app.models import Business, BusinessModule, LedgerAccount, Location, Membership
from backend.app.platform import DEFAULT_ACCOUNTS, MODULES

out = {"expected_accounts": len(DEFAULT_ACCOUNTS), "expected_modules": sorted(MODULES)}

with TestClient(app) as c:
    setup = c.post("/auth/setup", json={"username": "firstowner", "password": "correct-horse-battery"})
    out["setup_status"] = setup.status_code

    login = c.post("/auth/login", json={"username": "firstowner", "password": "correct-horse-battery"})
    token = login.json()["token"]
    auth = {"Authorization": "Bearer " + token}

    businesses = c.get("/platform/businesses", headers=auth).json()
    out["business_count"] = len(businesses)
    bid = businesses[0]["business"]["id"]
    h = dict(auth); h["X-Business-Id"] = str(bid)

    accounts = c.get("/platform/accounts", headers=h).json()
    out["accounts_via_api"] = len(accounts)
    out["subtypes"] = sorted({a["subtype"] for a in accounts})

    # Bootstrap runs on every app load; it must not duplicate or re-seed.
    c.post("/platform/bootstrap", headers=auth)
    c.post("/platform/bootstrap", headers=auth)
    out["accounts_after_bootstrap"] = len(c.get("/platform/accounts", headers=h).json())
    out["businesses_after_bootstrap"] = len(c.get("/platform/businesses", headers=auth).json())

with Session(engine) as s:
    opts = {"include_all_businesses": True}
    rows = lambda M: [r for r in s.exec(select(M).execution_options(**opts)).all()
                      if getattr(r, "business_id", None) == bid]
    out["locations"] = len(rows(Location))
    out["memberships"] = len(rows(Membership))
    out["membership_roles"] = sorted({r.role for r in rows(Membership)})
    out["modules_on"] = sorted(r.module_key for r in rows(BusinessModule) if r.enabled)

print("PROBE_JSON:" + json.dumps(out))
"""


@pytest.fixture(scope="module")
def signup():
    """Run a real first-run signup in an isolated interpreter and database."""
    db = Path(tempfile.gettempdir()) / f"eos_signup_{uuid.uuid4().hex[:8]}.db"
    env = {
        "DATABASE_URL": f"sqlite:///{db.as_posix()}",
        "JWT_SECRET": "test-secret-not-used-anywhere-real-32bytes",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONPATH": str(ROOT),
        "PATH": __import__("os").environ.get("PATH", ""),
        "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", ""),
    }

    result = subprocess.run(
        [sys.executable, "-c", PROBE],
        cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=180,
    )

    line = next(
        (l for l in result.stdout.splitlines() if l.startswith("PROBE_JSON:")), None
    )
    if line is None:
        pytest.fail(
            "first-run probe produced no result.\n"
            f"stdout:\n{result.stdout[-2000:]}\n\nstderr:\n{result.stderr[-2000:]}"
        )

    yield json.loads(line[len("PROBE_JSON:"):])

    try:
        db.unlink(missing_ok=True)
    except OSError:
        pass


# ------------------------------------------------------------------ the ledger

def test_signup_succeeds_on_an_empty_database(signup):
    assert signup["setup_status"] == 200
    assert signup["business_count"] == 1


def test_new_workspace_has_a_chart_of_accounts(signup):
    """
    The bug, stated as a test. Zero here means the ledger cannot accept a
    single entry, and this was zero for every account ever created.
    """
    assert signup["accounts_via_api"] == signup["expected_accounts"], (
        f"expected {signup['expected_accounts']} seeded accounts, "
        f"got {signup['accounts_via_api']}"
    )


@pytest.mark.parametrize(
    "subtype",
    ["cash", "accounts_receivable", "accounts_payable", "sales", "cost_of_goods_sold"],
)
def test_accounts_looked_up_by_subtype_exist(signup, subtype):
    """
    account_by_subtype raises 409 when one of these is missing, which reaches an
    operator as "Missing required ledger account" on their first invoice.
    """
    assert subtype in signup["subtypes"]


# ----------------------------------------------------------------- the rest

def test_new_workspace_has_a_location(signup):
    """Shifts attach to a location. Without one, scheduling has nowhere to put them."""
    assert signup["locations"] >= 1


def test_the_person_who_signs_up_owns_the_workspace(signup):
    assert signup["memberships"] == 1
    assert signup["membership_roles"] == ["owner"]


def test_every_module_is_switched_on(signup):
    """
    A new workspace should see everything before deciding what to turn off, and
    billing reads absent-as-enabled — an explicit row per module keeps both
    halves telling the same story.
    """
    assert signup["modules_on"] == signup["expected_modules"]


# --------------------------------------------------------------- the guard

def test_bootstrap_does_not_duplicate_anything(signup):
    """
    Bootstrap runs on every app load. Twice in a row must change nothing.
    """
    assert signup["accounts_after_bootstrap"] == signup["expected_accounts"]
    assert signup["businesses_after_bootstrap"] == 1
