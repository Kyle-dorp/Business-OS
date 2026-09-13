"""
Login throttling and password recovery.

Two gaps this closes:

  1. Login had no brute-force protection at all. Cloudflare will absorb volume
     once it is in front, but an edge rule does not know that ten attempts
     against one username is different from ten attempts across ten. This does.

  2. There was no recovery path. A locked-out owner had to phone the developer.

Recovery is manager-initiated by default, because accounts here are created by
a manager for staff rather than self-registered, and most staff accounts have
no email address at all. A manager issues a one-time code and reads it out.

Where the account does have an address the code is emailed as well — but the
manager still sees it, because a reset that depends entirely on an email
landing is a reset that strands somebody when it goes to spam.

The platform admin can reset a manager, which closes the loop at the top.
"""

from __future__ import annotations

import logging
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field as PField
from sqlmodel import Field, Session, SQLModel, select

from backend.app.auth import hash_password, user_from_request
from backend.app.database import get_session
from backend.app.models import AuditEvent, Membership, UserAccount, utc_now_iso
from backend.app.tenancy import current_business_id

log = logging.getLogger(__name__)

# Deliberately generous enough that a real person fat-fingering a password
# three times in a row is unaffected, and tight enough that guessing is hopeless.
MAX_ATTEMPTS = 8
WINDOW_MINUTES = 15
LOCKOUT_MINUTES = 15

RESET_CODE_TTL_MINUTES = 30


class LoginAttempt(SQLModel, table=True):
    """
    One row per failed login.

    Recorded per username rather than per IP: a shared restaurant wifi puts the
    whole team behind one address, so IP-based limits would lock out honest
    staff the moment one person forgot their password.
    """

    __tablename__ = "login_attempt"

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True)
    attempted_at: str = Field(default_factory=utc_now_iso, index=True)
    source_ip: str = ""


class PasswordReset(SQLModel, table=True):
    """A one-time code a manager hands to someone who is locked out."""

    __tablename__ = "password_reset"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    code_hash: str                      # the code itself is never stored
    issued_by_user_id: int
    expires_at: str
    used: bool = Field(default=False, index=True)
    created_at: str = Field(default_factory=utc_now_iso)


# ------------------------------------------------------------------ throttle

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(ts: str) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        return None


def recent_failures(session: Session, username: str) -> int:
    """Failed attempts for this username inside the window, pruning as it reads."""
    cutoff = _now() - timedelta(minutes=WINDOW_MINUTES)

    rows = session.exec(
        select(LoginAttempt).where(LoginAttempt.username == username)
    ).all()

    live = 0
    for row in rows:
        when = _parse(row.attempted_at)
        if when is None or when < cutoff:
            session.delete(row)          # keeps the table from growing forever
        else:
            live += 1
    session.commit()
    return live


def check_not_locked(session: Session, username: str) -> None:
    """Raise before a password is even checked, so lockout costs no bcrypt time."""
    if recent_failures(session, username) >= MAX_ATTEMPTS:
        raise HTTPException(
            429,
            f"Too many failed sign-ins for this account. Try again in "
            f"{LOCKOUT_MINUTES} minutes, or ask a manager to reset your password.",
        )


def record_failure(session: Session, username: str, request: Optional[Request] = None) -> None:
    ip = ""
    if request and request.client:
        ip = request.client.host or ""
    session.add(LoginAttempt(username=username, source_ip=ip))
    session.commit()
    log.info("Failed sign-in for %r (%s in window)", username, recent_failures(session, username))


def clear_failures(session: Session, username: str) -> None:
    """Called on a successful sign-in — one good login wipes the slate."""
    for row in session.exec(select(LoginAttempt).where(LoginAttempt.username == username)).all():
        session.delete(row)
    session.commit()


# -------------------------------------------------------------------- resets

ALPHABET = string.ascii_uppercase + string.digits
# I, O, 0 and 1 are omitted — these codes get read aloud across a noisy kitchen.
ALPHABET = "".join(c for c in ALPHABET if c not in "IO01")


def _generate_code() -> str:
    return "-".join(
        "".join(secrets.choice(ALPHABET) for _ in range(4)) for _ in range(2)
    )


router = APIRouter(prefix="/security", tags=["security"])

MANAGER_ROLES = {"owner", "admin", "manager"}


def _can_manage(session: Session, actor: UserAccount, target: UserAccount) -> bool:
    """
    A manager may reset someone in a workspace they both belong to.
    A platform admin may reset anyone — that is the path back in when the owner
    is the one locked out.
    """
    if actor.is_admin:
        return True

    business_id = current_business_id()
    actor_membership = session.exec(
        select(Membership).where(
            Membership.business_id == business_id,
            Membership.user_id == actor.id,
            Membership.active == True,  # noqa: E712
        )
    ).first()
    if not actor_membership or actor_membership.role not in MANAGER_ROLES:
        return False

    target_membership = session.exec(
        select(Membership).where(
            Membership.business_id == business_id,
            Membership.user_id == target.id,
        )
    ).first()
    return bool(target_membership)


class IssueResetIn(BaseModel):
    username: str


class IssueResetOut(BaseModel):
    code: str
    expires_in_minutes: int
    username: str
    note: str


@router.post("/reset/issue", response_model=IssueResetOut)
def issue_reset(
    body: IssueResetIn,
    session: Session = Depends(get_session),
    actor: UserAccount = Depends(user_from_request),
):
    """
    Issue a one-time code for someone who is locked out.

    The code is returned once, to the manager, and only its hash is stored.
    Nobody — including whoever reads the database later — can recover it.
    """
    target = session.exec(
        select(UserAccount).where(UserAccount.username == body.username)
    ).first()
    if not target:
        raise HTTPException(404, "No account with that username.")
    if not _can_manage(session, actor, target):
        raise HTTPException(403, "You cannot reset that account.")

    # Any previous unused code stops working the moment a new one is issued.
    for old in session.exec(
        select(PasswordReset).where(
            PasswordReset.user_id == target.id,
            PasswordReset.used == False,  # noqa: E712
        )
    ).all():
        old.used = True
        session.add(old)

    code = _generate_code()
    session.add(PasswordReset(
        user_id=target.id,
        code_hash=hash_password(code),
        issued_by_user_id=actor.id,
        expires_at=(_now() + timedelta(minutes=RESET_CODE_TTL_MINUTES)).isoformat(),
    ))

    # Unlock them too, or they hand over a valid code to a throttled account.
    clear_failures(session, target.username)

    session.add(AuditEvent(
        business_id=current_business_id(),
        user_id=actor.id,
        action="security.reset_issued",
        entity_type="user",
        entity_id=target.id,
        detail_json=f'{{"username": "{target.username}"}}',
    ))
    session.commit()

    log.info("Reset code issued for %r by %r", target.username, actor.username)

    # If the account has an address, send it there too. The manager still sees
    # the code — an email that lands in spam should not strand somebody.
    emailed = False
    if target.email:
        try:
            from backend.app import email_service
            emailed = email_service.password_reset_code(
                session, target, code, RESET_CODE_TTL_MINUTES
            ).get("sent", False)
        except Exception:
            log.exception("Reset code for %r could not be emailed", target.username)

    return IssueResetOut(
        code=code,
        expires_in_minutes=RESET_CODE_TTL_MINUTES,
        username=target.username,
        note=(
            f"Also emailed to {target.email}. "
            "Read it to them as well — it is shown here once and cannot be retrieved."
            if emailed
            else "Read this to them directly. It is shown once and cannot be retrieved."
        ),
    )


class RedeemIn(BaseModel):
    username: str
    code: str
    new_password: str = PField(min_length=8, max_length=200)


@router.post("/reset/redeem")
def redeem_reset(
    body: RedeemIn,
    request: Request,
    session: Session = Depends(get_session),
):
    """
    Exchange a code for a new password. No sign-in required — the person using
    this cannot sign in, which is the entire point.
    """
    from backend.app.auth import verify_password

    generic = HTTPException(400, "That code is not valid, or it has expired.")

    user = session.exec(
        select(UserAccount).where(UserAccount.username == body.username)
    ).first()
    if not user:
        raise generic

    # Redeeming is throttled as hard as signing in — otherwise the reset
    # endpoint becomes a softer door into the same account.
    check_not_locked(session, f"reset:{body.username}")

    pending = session.exec(
        select(PasswordReset).where(
            PasswordReset.user_id == user.id,
            PasswordReset.used == False,  # noqa: E712
        )
    ).all()

    match = None
    for candidate in pending:
        expires = _parse(candidate.expires_at)
        if expires and expires < _now():
            candidate.used = True
            session.add(candidate)
            continue
        if verify_password(body.code.strip().upper(), candidate.code_hash):
            match = candidate
            break

    session.commit()

    if not match:
        record_failure(session, f"reset:{body.username}", request)
        raise generic

    user.password_hash = hash_password(body.new_password)
    user.updated_at = utc_now_iso()
    match.used = True
    session.add(user)
    session.add(match)

    clear_failures(session, user.username)
    clear_failures(session, f"reset:{body.username}")
    session.commit()

    log.info("Password reset redeemed for %r", user.username)
    return {"reset": True, "username": user.username}


@router.get("/lockouts")
def lockouts(
    session: Session = Depends(get_session),
    actor: UserAccount = Depends(user_from_request),
):
    """Who is currently throttled, so a manager can see why someone cannot get in."""
    business_id = current_business_id()
    membership = session.exec(
        select(Membership).where(
            Membership.business_id == business_id,
            Membership.user_id == actor.id,
            Membership.active == True,  # noqa: E712
        )
    ).first()
    if not (actor.is_admin or (membership and membership.role in MANAGER_ROLES)):
        raise HTTPException(403, "Manager access required.")

    cutoff = _now() - timedelta(minutes=WINDOW_MINUTES)
    counts: dict[str, int] = {}
    for row in session.exec(select(LoginAttempt)).all():
        when = _parse(row.attempted_at)
        if when and when >= cutoff and not row.username.startswith("reset:"):
            counts[row.username] = counts.get(row.username, 0) + 1

    return {
        "window_minutes": WINDOW_MINUTES,
        "max_attempts": MAX_ATTEMPTS,
        "accounts": [
            {"username": u, "failed_attempts": n, "locked": n >= MAX_ATTEMPTS}
            for u, n in sorted(counts.items(), key=lambda kv: -kv[1])
        ],
    }
