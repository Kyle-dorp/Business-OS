"""
Creating a workspace.

Until now there was no way to. /auth/setup refuses as soon as a single
UserAccount exists anywhere on the platform, so after the very first account
the sign-in page was the only door and it had no handle — a prospective
customer could reach the site and simply could not get in.

The other half of this is what a new workspace arrives with. Signup used to add
a user, a business and a membership and nothing else, which left the workspace
with no chart of accounts, no location and no module rows: unable to post a
journal entry from its first second, and unrepairable afterwards because
/platform/bootstrap sees the membership and concludes the job is done. So most
of what follows checks that a brand-new account can actually do the thing it
signed up to do.
"""

from __future__ import annotations

import uuid

import pytest
from sqlmodel import Session, select

from backend.app.database import engine
from backend.app.models import Business, LedgerAccount, Membership, UserAccount
from backend.app.tenancy import set_current_business_id


def _creds(label="owner"):
    suffix = uuid.uuid4().hex[:8]
    return {
        "username": f"{label}{suffix}",
        "password": "a-real-password-123",
        "business_name": f"{label.title()} Co {suffix}",
    }


@pytest.fixture(autouse=True)
def _reset_tenant():
    yield
    set_current_business_id(1)


# ===========================================================================
# The door opens
# ===========================================================================

def test_anybody_can_create_a_workspace(client):
    """
    The whole point. /auth/setup works once per database, ever; this has to
    work for the second customer and the two-hundredth.
    """
    first = client.post("/auth/signup", json=_creds("first"))
    assert first.status_code == 200, first.text

    second = client.post("/auth/signup", json=_creds("second"))
    assert second.status_code == 200, second.text


def test_signing_up_signs_you_in(client):
    """
    Handing back a token rather than bouncing to the sign-in form. Being asked
    to type the password you just chose is the first thing a new customer
    would experience, and it reads as broken.
    """
    response = client.post("/auth/signup", json=_creds())
    body = response.json()

    assert body["token"]
    assert body["user"]["username"]
    assert body["business"]["id"]


def test_the_new_account_can_immediately_use_the_api(client):
    creds = _creds()
    body = client.post("/auth/signup", json=creds).json()
    headers = {
        "Authorization": f"Bearer {body['token']}",
        "X-Business-Id": str(body["business"]["id"]),
    }

    accounts = client.get("/platform/accounts", headers=headers)
    assert accounts.status_code == 200, accounts.text


def test_the_workspace_is_named_what_was_asked_for(client):
    creds = _creds()
    creds["business_name"] = "Kyle's Barbershop"
    body = client.post("/auth/signup", json=creds).json()

    assert body["business"]["name"] == "Kyle's Barbershop"


def test_a_workspace_with_no_name_still_gets_one(client):
    """An empty field should not produce a business called "" in the switcher."""
    creds = _creds()
    creds["business_name"] = "   "
    body = client.post("/auth/signup", json=creds).json()

    assert body["business"]["name"].strip()
    assert creds["username"] in body["business"]["name"]


def test_signing_in_afterwards_works(client):
    """
    Signup writes the password hash; login reads it. They have disagreed
    before — this is the round trip.
    """
    creds = _creds()
    client.post("/auth/signup", json=creds)

    login = client.post("/auth/login", json={
        "username": creds["username"], "password": creds["password"],
    })
    assert login.status_code == 200, login.text
    assert login.json()["token"]


def test_the_username_is_matched_case_insensitively_at_sign_in(client):
    creds = _creds()
    client.post("/auth/signup", json=creds)

    login = client.post("/auth/login", json={
        "username": creds["username"].upper(), "password": creds["password"],
    })
    assert login.status_code == 200, login.text


# ===========================================================================
# What the workspace arrives with
# ===========================================================================

def test_a_new_workspace_has_a_full_chart_of_accounts(client):
    """
    The bug that made every early signup useless. Without this there is no
    cash account, no accounts receivable, nothing to post against.
    """
    body = client.post("/auth/signup", json=_creds()).json()
    bid = body["business"]["id"]

    with Session(engine) as s:
        accounts = s.exec(
            select(LedgerAccount).where(LedgerAccount.business_id == bid)
            .execution_options(include_all_businesses=True)
        ).all()

    subtypes = {a.subtype for a in accounts}
    for required in ("cash", "accounts_receivable", "accounts_payable",
                     "sales", "owner_equity", "payroll", "payroll_liabilities"):
        assert required in subtypes, f"a new workspace has no {required} account"


def test_the_owner_is_a_member_of_their_own_workspace(client):
    """Without the membership the auth middleware 403s them out of their own app."""
    body = client.post("/auth/signup", json=_creds()).json()

    with Session(engine) as s:
        membership = s.exec(
            select(Membership).where(
                Membership.business_id == body["business"]["id"],
                Membership.user_id == body["user"]["id"],
            ).execution_options(include_all_businesses=True)
        ).first()

    assert membership is not None
    assert membership.role == "owner"
    assert membership.active


def test_a_new_workspace_can_post_a_journal_entry(client):
    """
    The end-to-end version of the same thing. A chart of accounts that cannot
    take an entry is decoration.
    """
    body = client.post("/auth/signup", json=_creds()).json()
    headers = {
        "Authorization": f"Bearer {body['token']}",
        "X-Business-Id": str(body["business"]["id"]),
    }

    accounts = client.get("/platform/accounts", headers=headers).json()
    cash = next(a for a in accounts if a["subtype"] == "cash")
    equity = next(a for a in accounts if a["subtype"] == "owner_equity")

    entry = client.post("/platform/journal", headers=headers, json={
        "entry_date": "2026-09-16",
        "memo": "opening capital",
        "lines": [
            {"account_id": cash["id"], "description": "capital", "debit": 1000.0, "credit": 0},
            {"account_id": equity["id"], "description": "capital", "debit": 0, "credit": 1000.0},
        ],
    })
    assert entry.status_code == 200, entry.text


def test_two_workspaces_cannot_see_each_other(client):
    """The tenant boundary, from the moment both exist."""
    one = client.post("/auth/signup", json=_creds("alpha")).json()
    two = client.post("/auth/signup", json=_creds("beta")).json()

    headers = {
        "Authorization": f"Bearer {one['token']}",
        "X-Business-Id": str(two["business"]["id"]),
    }
    response = client.get("/platform/accounts", headers=headers)
    assert response.status_code in (401, 403, 404), (
        "a new account reached another workspace by changing a header"
    )


# ===========================================================================
# What it refuses
# ===========================================================================

def test_a_taken_username_is_refused_with_a_useful_message(client):
    creds = _creds()
    assert client.post("/auth/signup", json=creds).status_code == 200

    again = client.post("/auth/signup", json={**creds, "business_name": "Another"})
    assert again.status_code == 409
    assert "taken" in again.json()["detail"].lower()


def test_a_username_differing_only_in_case_is_refused(client):
    """
    Sign-in matches case-insensitively. Allowing both "Kyle" and "kyle" to
    exist would mean neither could reliably log in.
    """
    creds = _creds()
    client.post("/auth/signup", json=creds)

    clash = client.post("/auth/signup", json={
        **creds, "username": creds["username"].upper(),
    })
    assert clash.status_code == 409


def test_a_short_password_is_refused(client):
    creds = _creds()
    creds["password"] = "short"
    response = client.post("/auth/signup", json=creds)

    assert response.status_code == 400
    assert "8 characters" in response.json()["detail"]


def test_a_short_username_is_refused(client):
    creds = _creds()
    creds["username"] = "ab"
    assert client.post("/auth/signup", json=creds).status_code == 400


def test_a_duplicate_email_is_refused(client):
    """
    Email is how a password reset finds an account. Two accounts sharing one
    would make that ambiguous.
    """
    shared = f"kyle{uuid.uuid4().hex[:6]}@example.com"
    first = _creds("mail")
    first["email"] = shared
    assert client.post("/auth/signup", json=first).status_code == 200

    second = _creds("mail2")
    second["email"] = shared.upper()
    response = client.post("/auth/signup", json=second)
    assert response.status_code == 409, response.text


def test_signing_up_without_an_email_is_allowed(client):
    """Email is useful, not required. Demanding one is a reason to bounce."""
    response = client.post("/auth/signup", json=_creds())
    assert response.status_code == 200


def test_a_malformed_email_is_refused(client):
    creds = _creds()
    creds["email"] = "not-an-email"
    assert client.post("/auth/signup", json=creds).status_code == 400


def test_an_absurd_business_name_is_refused(client):
    creds = _creds()
    creds["business_name"] = "x" * 500
    assert client.post("/auth/signup", json=creds).status_code == 400


# ===========================================================================
# The old route
# ===========================================================================

def test_the_first_run_route_still_refuses_once_a_user_exists(client):
    """
    /auth/setup keeps its guard. It is the self-hosted first-run path, and
    signup is the product one; loosening setup instead would have let anybody
    claim the very first account on a fresh deployment.
    """
    client.post("/auth/signup", json=_creds())

    response = client.post("/auth/setup", json={
        "username": f"late{uuid.uuid4().hex[:6]}", "password": "a-real-password-123",
    })
    assert response.status_code == 409


def test_signup_needs_no_token(client):
    """It is reachable before a session exists, by definition."""
    from backend.app.main import PUBLIC_PATHS

    assert "/auth/signup" in PUBLIC_PATHS
