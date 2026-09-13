"""
Google sign-in.

Deliberately scoped: this is an *additional* way for owners and managers to get
in, not a replacement for passwords. Accounts here are provisioned by a manager
for staff — a line cook has no work Google account — so password auth stays the
primary path and Google is a convenience for the people who run the place.

Two security properties matter and both are easy to get wrong:

  1. The ID token is verified against Google's public keys, server-side, every
     time. A token the browser hands us is a claim, not proof. Anyone can POST
     a forged JSON blob to this endpoint.

  2. Google sign-in never creates an account. It links to one that already
     exists. Auto-provisioning would mean anyone with a Google account could
     conjure themselves a login on your platform; linking means an owner must
     have been invited first, exactly like every other account here.

Required env vars:
    GOOGLE_CLIENT_ID       from the Google Cloud OAuth consent screen
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.app.auth import create_access_token, user_from_request
from backend.app.database import get_session
from backend.app.models import AuditEvent, Membership, UserAccount, utc_now_iso
from backend.app.tenancy import current_business_id

log = logging.getLogger(__name__)

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_TOKENINFO = "https://oauth2.googleapis.com/tokeninfo"

# Google's own endpoint does signature, expiry and issuer checking for us.
# Verifying JWTs by hand against the JWKS is a well-known source of subtle bugs
# (unchecked `alg`, stale key cache, missing audience check); deferring to the
# issuer is the boring correct choice at this scale.
ALLOWED_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}

# Only these roles may link Google. Staff stay on manager-issued credentials.
LINKABLE_ROLES = {"owner", "admin", "manager"}

router = APIRouter(prefix="/auth/google", tags=["auth"])


class GoogleProfile(BaseModel):
    subject: str
    email: str
    email_verified: bool
    name: str = ""
    picture: str = ""


async def verify_google_token(credential: str) -> GoogleProfile:
    """Exchange an ID token for a verified profile, or refuse."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(503, "Google sign-in is not configured on this deployment.")

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(GOOGLE_TOKENINFO, params={"id_token": credential})
    except httpx.HTTPError:
        log.exception("Could not reach Google to verify a token")
        raise HTTPException(502, "Could not reach Google to verify that sign-in.")

    if response.status_code != 200:
        raise HTTPException(401, "That Google sign-in could not be verified.")

    claims = response.json()

    # Audience is the check that matters most. Without it, a token minted for
    # any other Google app would be accepted here.
    if claims.get("aud") != GOOGLE_CLIENT_ID:
        log.warning("Rejected a Google token issued for a different audience")
        raise HTTPException(401, "That sign-in was issued for a different application.")

    if claims.get("iss") not in ALLOWED_ISSUERS:
        raise HTTPException(401, "That sign-in came from an unexpected issuer.")

    if claims.get("email_verified") not in (True, "true"):
        raise HTTPException(403, "Verify your email address with Google first.")

    subject = claims.get("sub")
    email = (claims.get("email") or "").lower().strip()
    if not subject or not email:
        raise HTTPException(401, "That Google account did not return an email address.")

    return GoogleProfile(
        subject=subject,
        email=email,
        email_verified=True,
        name=claims.get("name", ""),
        picture=claims.get("picture", ""),
    )


class CredentialIn(BaseModel):
    credential: str


@router.get("/config")
def google_config():
    """Lets the sign-in page know whether to render the Google button at all."""
    return {"enabled": bool(GOOGLE_CLIENT_ID), "client_id": GOOGLE_CLIENT_ID}


@router.post("/login")
async def google_login(
    body: CredentialIn,
    session: Session = Depends(get_session),
):
    """
    Sign in with a previously linked Google account.

    Matching is by provider subject first — Google's stable id — falling back to
    a verified email. Subject first matters: a user can change their Gmail
    address, and matching on email alone would either lock them out or, worse,
    hand their account to whoever inherits the old address.
    """
    profile = await verify_google_token(body.credential)

    user = session.exec(
        select(UserAccount).where(UserAccount.provider_subject == profile.subject)
    ).first()

    if not user:
        candidate = session.exec(
            select(UserAccount).where(UserAccount.email == profile.email)
        ).first()
        # Only adopt an email match if that account has opted into Google.
        # Otherwise anyone who can obtain a Google account at a known address
        # could sign in as a password user.
        if candidate and candidate.auth_provider == "google":
            candidate.provider_subject = profile.subject
            session.add(candidate)
            session.commit()
            user = candidate

    if not user:
        raise HTTPException(
            403,
            "No account here is linked to that Google address. Sign in with your "
            "username and password first, then link Google from Settings.",
        )

    if not user.active:
        raise HTTPException(403, "That account is disabled.")

    user.updated_at = utc_now_iso()
    session.add(user)
    session.commit()

    log.info("Google sign-in for %r", user.username)
    return {
        "token": create_access_token(user),
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "is_admin": user.is_admin,
            "email": user.email,
        },
    }


@router.post("/link")
async def link_google(
    body: CredentialIn,
    session: Session = Depends(get_session),
    actor: UserAccount = Depends(user_from_request),
):
    """
    Attach a Google account to the signed-in user.

    Requires an existing session, which is what makes this safe: the person
    proving they own the Google account is already proving they own this one.
    """
    business_id = current_business_id()
    membership = session.exec(
        select(Membership).where(
            Membership.business_id == business_id,
            Membership.user_id == actor.id,
            Membership.active == True,  # noqa: E712
        )
    ).first()

    if not actor.is_admin and not (membership and membership.role in LINKABLE_ROLES):
        raise HTTPException(
            403,
            "Google sign-in is available to owners, admins and managers. Staff "
            "accounts use the credentials their manager issued.",
        )

    profile = await verify_google_token(body.credential)

    taken = session.exec(
        select(UserAccount).where(UserAccount.provider_subject == profile.subject)
    ).first()
    if taken and taken.id != actor.id:
        raise HTTPException(409, "That Google account is already linked to another user.")

    email_clash = session.exec(
        select(UserAccount).where(UserAccount.email == profile.email)
    ).first()
    if email_clash and email_clash.id != actor.id:
        raise HTTPException(409, "Another account here already uses that email address.")

    actor.email = profile.email
    actor.email_verified = True
    actor.auth_provider = "google"
    actor.provider_subject = profile.subject
    actor.updated_at = utc_now_iso()
    session.add(actor)

    session.add(AuditEvent(
        business_id=business_id,
        user_id=actor.id,
        action="security.google_linked",
        entity_type="user",
        entity_id=actor.id,
        detail_json=f'{{"email": "{profile.email}"}}',
    ))
    session.commit()

    log.info("Google linked to %r (%s)", actor.username, profile.email)
    return {"linked": True, "email": profile.email, "name": profile.name}


@router.post("/unlink")
def unlink_google(
    session: Session = Depends(get_session),
    actor: UserAccount = Depends(user_from_request),
):
    """
    Detach Google and fall back to password auth.

    Refused if the account has no usable password, which would otherwise lock
    the user out of their own workspace with no way back in.
    """
    if not actor.password_hash:
        raise HTTPException(
            409,
            "Set a password before unlinking Google, or you will not be able to sign in.",
        )

    actor.auth_provider = "password"
    actor.provider_subject = None
    actor.updated_at = utc_now_iso()
    session.add(actor)
    session.commit()

    return {"linked": False}


@router.get("/status")
def google_status(actor: UserAccount = Depends(user_from_request)):
    return {
        "configured": bool(GOOGLE_CLIENT_ID),
        "linked": actor.auth_provider == "google",
        "email": actor.email,
    }
