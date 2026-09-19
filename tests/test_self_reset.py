"""
Getting back into your own account.

A reset code could only be issued by somebody already signed in who could
manage the account. That works for staff — a manager unlocks them — and leaves
the owner of a one-person workspace with nobody to ask. No self-service path,
no support desk, and the only way back into a business's own books was
somebody opening the production database.

It is the most common support request a product like this gets, and it had no
answer.

Most of what is tested here is what the endpoint refuses to tell you. A reset
request is an unauthenticated endpoint that takes a username, so every
difference between one response and another is a way to learn something about
somebody else's account.
"""

from __future__ import annotations

import uuid

import pytest
from sqlmodel import Session, select

from backend.app.auth import hash_password, verify_password
from backend.app.database import engine
from backend.app.models import UserAccount
from backend.app.security import PasswordReset, RESET_CODE_TTL_MINUTES
from backend.app.tenancy import set_current_business_id


@pytest.fixture
def account(client):
    """A real account with a recovery email, and one without."""
    suffix = uuid.uuid4().hex[:6]
    signup = client.post("/auth/signup", json={
        "username": f"owner{suffix}",
        "password": "a-real-password-123",
        "business_name": f"Locked Out {suffix}",
        "email": f"owner{suffix}@example.com",
    })
    assert signup.status_code == 200, signup.text

    with Session(engine) as s:
        no_email = UserAccount(
            username=f"noemail{suffix}",
            password_hash=hash_password("a-real-password-123"),
            role="manager", active=True,
        )
        s.add(no_email)
        s.commit()

    yield {
        "client": client,
        "username": f"owner{suffix}",
        "email": f"owner{suffix}@example.com",
        "no_email": f"noemail{suffix}",
    }
    set_current_business_id(1)


def _request(account, username: str):
    return account["client"].post("/security/reset/request", json={"username": username})


def _codes_for(username: str) -> list[PasswordReset]:
    with Session(engine) as s:
        user = s.exec(select(UserAccount).where(UserAccount.username == username)).first()
        if not user:
            return []
        return s.exec(
            select(PasswordReset).where(
                PasswordReset.user_id == user.id,
                PasswordReset.used == False,  # noqa: E712
            )
        ).all()


# ===========================================================================
# It works
# ===========================================================================

def test_asking_for_a_code_issues_one(account):
    assert _request(account, account["username"]).status_code == 200
    assert len(_codes_for(account["username"])) == 1


def test_the_code_is_never_stored(account):
    """
    Only its hash. Nobody reading the database later — including us — can
    recover a code and take an account with it.
    """
    _request(account, account["username"])
    pending = _codes_for(account["username"])[0]

    assert pending.code_hash
    assert len(pending.code_hash) > 20, "that is not a hash"
    assert not hasattr(pending, "code")


def test_asking_again_invalidates_the_first_code(account):
    """
    Two live codes is two chances to guess. The newest wins and the rest stop
    working, exactly as when a manager issues one.
    """
    _request(account, account["username"])
    first = _codes_for(account["username"])[0].code_hash

    _request(account, account["username"])
    live = _codes_for(account["username"])

    assert len(live) == 1
    assert live[0].code_hash != first


def test_the_code_actually_works_end_to_end(account):
    """
    The whole point. A code that issues but cannot be redeemed is a support
    ticket with extra steps.
    """
    _request(account, account["username"])

    # The code only exists in the email, which the suite cannot read — so it is
    # taken from the issuing path the same way redeem verifies it.
    from backend.app.security import _generate_code

    with Session(engine) as s:
        user = s.exec(
            select(UserAccount).where(UserAccount.username == account["username"])
        ).first()
        pending = s.exec(
            select(PasswordReset).where(
                PasswordReset.user_id == user.id,
                PasswordReset.used == False,  # noqa: E712
            )
        ).first()
        # Replace it with one we know, hashed the same way the real one is.
        known = _generate_code()
        pending.code_hash = hash_password(known)
        s.add(pending)
        s.commit()

    response = account["client"].post("/security/reset/redeem", json={
        "username": account["username"],
        "code": known,
        "new_password": "a-different-password-456",
    })
    assert response.status_code == 200, response.text

    with Session(engine) as s:
        user = s.exec(
            select(UserAccount).where(UserAccount.username == account["username"])
        ).first()
        assert verify_password("a-different-password-456", user.password_hash)


# ===========================================================================
# What it refuses to tell you
# ===========================================================================

def test_it_answers_the_same_for_an_account_that_does_not_exist(account):
    """
    The one that matters. An endpoint that says "no such user" is a way to
    find out which usernames are real, and a username here is half of a
    sign-in.
    """
    real = _request(account, account["username"])
    fake = _request(account, f"definitely-not-a-user-{uuid.uuid4().hex}")

    assert real.status_code == fake.status_code
    assert real.json() == fake.json()


def test_it_answers_the_same_for_an_account_with_no_email(account):
    """
    "That account has no recovery email" tells somebody the account exists.
    """
    with_email = _request(account, account["username"])
    without = _request(account, account["no_email"])

    assert with_email.json() == without.json()
    assert _codes_for(account["no_email"]) == [], "nothing to send it to"


def test_it_does_not_say_where_the_code_went(account):
    """
    "Sent to k***@gmail.com" tells somebody who guessed a username which
    provider to go after next.
    """
    body = _request(account, account["username"]).json()
    text = str(body).lower()

    assert account["email"] not in text
    assert "@" not in text
    assert "gmail" not in text and "example.com" not in text


def test_it_never_returns_the_code(account):
    """
    issue_reset returns the code, because a manager is standing next to the
    person. Nobody has identified anybody here.
    """
    body = _request(account, account["username"]).json()
    assert "code" not in body


# ===========================================================================
# What it refuses to do
# ===========================================================================

def test_it_does_not_unlock_a_throttled_account(account):
    """
    issue_reset clears the failure count, because a manager has identified the
    person in front of them. Doing that here would turn this into a way to
    reset the lockout on an account somebody is trying to break into.
    """
    import inspect

    from backend.app.security import issue_reset, request_reset

    assert "clear_failures" in inspect.getsource(issue_reset)
    assert "clear_failures" not in inspect.getsource(request_reset)


def test_asking_repeatedly_is_throttled(account):
    """
    Otherwise it is a way to send somebody unlimited email, and a way to
    invalidate their real code over and over while they try to use it.
    """
    for _ in range(12):
        _request(account, account["username"])

    # Throttled requests still answer identically — the whole design — so the
    # evidence is that it stopped issuing, not that it started refusing.
    assert len(_codes_for(account["username"])) <= 1

    from backend.app.security import MAX_ATTEMPTS, recent_failures

    with Session(engine) as s:
        assert recent_failures(s, f"reset-request:{account['username']}") >= MAX_ATTEMPTS


def test_an_inactive_account_gets_nothing(account):
    with Session(engine) as s:
        user = s.exec(
            select(UserAccount).where(UserAccount.username == account["username"])
        ).first()
        user.active = False
        s.add(user)
        s.commit()

    _request(account, account["username"])
    assert _codes_for(account["username"]) == []


def test_an_empty_username_is_not_an_error(account):
    """A blank field is a slip, not an attack. It answers the same as anything else."""
    assert _request(account, "   ").status_code == 200


def test_it_says_whether_recovery_is_possible_at_all(account):
    """
    Not whether *this* account can be recovered — whether the deployment can
    send email at all. Somebody staring at "a code is on its way" on a
    deployment with no mail configured is waiting for something that will
    never arrive.
    """
    body = _request(account, account["username"]).json()
    assert "recovery_possible" in body
    # The suite strips RESEND_API_KEY, so this deployment cannot send.
    assert body["recovery_possible"] is False


def test_the_code_expires(account):
    _request(account, account["username"])
    pending = _codes_for(account["username"])[0]

    from datetime import datetime, timedelta, timezone

    expires = datetime.fromisoformat(pending.expires_at)
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    life = expires - datetime.now(timezone.utc)

    assert life < timedelta(minutes=RESET_CODE_TTL_MINUTES + 1)
    assert life > timedelta(0)


def test_it_leaves_an_audit_trail(account):
    """
    Somebody asking to reset an account is worth recording whether or not it
    was them.
    """
    from backend.app.models import AuditEvent

    _request(account, account["username"])
    with Session(engine) as s:
        events = s.exec(
            select(AuditEvent).where(AuditEvent.action == "password.reset.self_requested")
        ).all()
    assert events, "a self-service reset left no trace"


# ===========================================================================
# Knowing whether any of this can work
# ===========================================================================
#
# The endpoint answers identically to everything, which is the right design and
# means it cannot tell anybody that the deployment has no mail configured. A
# locked-out owner would be told a code is on its way and wait for something
# that was never sent. /health is the only place that answer can live.

def test_health_says_whether_email_can_be_sent(client):
    checks = client.get("/health").json()["checks"]

    assert "email" in checks, "nothing reports whether mail works"
    assert "configured" in checks["email"]


def test_health_warns_when_reset_by_email_is_impossible(client):
    """
    conftest strips RESEND_API_KEY, so this deployment cannot send — which is
    exactly the state a fresh production deployment is in until somebody sets
    it, and exactly the state nobody would notice.
    """
    email = client.get("/health").json()["checks"]["email"]

    assert email["configured"] is False
    assert email["password_reset_by_email"] is False
    assert "locked-out owner" in email["warning"]


def test_the_signup_form_asks_for_a_recovery_email():
    """
    The reason this was not solvable before: SignupRequest has accepted an
    `email` since it was written, validates it, and the form never asked for
    one — so every account had none, and no amount of reset machinery can email
    a code to an address nobody gave.
    """
    import pathlib

    page = (pathlib.Path(__file__).resolve().parents[1]
            / "frontend" / "src" / "pages" / "AuthPage.jsx").read_text(encoding="utf-8")

    assert 'type="email"' in page
    assert "email: email.trim()" in page, "the form collects it but does not send it"


def test_the_request_endpoint_is_reachable_without_signing_in():
    """
    The failure that would make the whole feature pointless: somebody who
    cannot sign in cannot authenticate to reach the thing that lets them sign
    in. It answered 401 on the first run.
    """
    from backend.app.main import PUBLIC_PATHS

    assert "/security/reset/request" in PUBLIC_PATHS
    assert "/security/reset/redeem" in PUBLIC_PATHS
