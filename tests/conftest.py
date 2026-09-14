"""
Test configuration.

The important job here is isolating the database. Without this, the suite runs
against whatever DATABASE_URL points at — which in development is
schedule_assistant.db, the working database. Running the tests would then
create businesses, users and ledger entries inside real data, and the first
symptom would be someone wondering why their workspace has an account called
"owner" in it.

DATABASE_URL is set before any application module is imported, because
database.py reads it at import time and builds the engine once.
"""

from __future__ import annotations

import os
import sys
import tempfile
import uuid
from pathlib import Path

# The project root, so `backend.app...` imports resolve when pytest is run from
# anywhere rather than only from the repository root.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# A fresh file per session. Fresh matters: several tests assert on first-run
# behaviour — the first user, the first business — which only happens once per
# database.
_TEST_DB = Path(tempfile.gettempdir()) / f"business_eos_test_{uuid.uuid4().hex[:8]}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"

# Deterministic secrets. Never the deployment's, which should not be readable
# from a test run in the first place.
os.environ.setdefault("JWT_SECRET", "test-secret-not-used-anywhere-real-32bytes")

# Third-party integrations stay off. A test suite that can reach Stripe,
# Anthropic or Resend is a test suite that can charge a card, spend tokens or
# email a customer.
for key in ("STRIPE_SECRET_KEY", "ANTHROPIC_API_KEY", "RESEND_API_KEY",
            "GOOGLE_CLIENT_ID", "EMAIL_FROM"):
    os.environ.pop(key, None)


import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _cleanup_database():
    """
    Create the schema once, and remove the file at the end.

    Table creation belongs here rather than in each module: it normally happens
    on application startup, so a test that exercises a function directly —
    without a TestClient — otherwise finds an empty database and fails with
    "no such table", which reads like a broken test rather than a missing
    fixture.
    """
    from backend.app.database import create_db_and_tables

    create_db_and_tables()
    yield
    try:
        _TEST_DB.unlink(missing_ok=True)
    except OSError:
        # A Windows file handle may still be open. A leftover file in the temp
        # directory is not worth failing a green suite over.
        pass


@pytest.fixture
def client():
    """A TestClient with startup run, for tests that exercise real routes."""
    from fastapi.testclient import TestClient
    from backend.app.main import app

    with TestClient(app) as c:
        yield c
