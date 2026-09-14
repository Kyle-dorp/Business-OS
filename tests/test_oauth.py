"""
Google sign-in verification.

The ID token a browser hands us is a claim, not proof. Anyone can POST a JSON
blob to this endpoint, so everything here depends on what happens between
receiving that string and trusting it.

Three checks carry the whole model, and each one is a known way to get this
wrong:

  aud   — without it, a token minted for any other Google application is
          accepted here. This is the classic OAuth mistake.
  iss   — the token must actually come from Google.
  email_verified — an unverified Google address proves nothing about who owns it.

And one product rule: signing in never creates an account. Auto-provisioning
would mean anybody with a Gmail address could conjure themselves a login.

Google is never contacted. The verification layer is exercised against
responses we control, which is the only way to test a rejection path.
"""

from __future__ import annotations

import pytest

from backend.app import oauth


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self):
        return self._payload


class FakeClient:
    """Stands in for httpx.AsyncClient, returning a scripted tokeninfo reply."""

    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, params=None):
        return self._response


def _install(monkeypatch, payload, status_code=200, client_id="our-app.apps.googleusercontent.com"):
    monkeypatch.setattr(oauth, "GOOGLE_CLIENT_ID", client_id)
    monkeypatch.setattr(
        oauth.httpx, "AsyncClient",
        lambda *a, **k: FakeClient(FakeResponse(payload, status_code)),
    )


def _valid_claims(client_id="our-app.apps.googleusercontent.com"):
    return {
        "aud": client_id,
        "iss": "https://accounts.google.com",
        "sub": "1234567890",
        "email": "owner@example.com",
        "email_verified": "true",
        "name": "Sam Owner",
    }


# ------------------------------------------------------------------ accepted

@pytest.mark.asyncio
async def test_a_well_formed_token_verifies(monkeypatch):
    _install(monkeypatch, _valid_claims())
    profile = await oauth.verify_google_token("token")
    assert profile.subject == "1234567890"
    assert profile.email == "owner@example.com"
    assert profile.email_verified is True


@pytest.mark.asyncio
async def test_email_is_normalised(monkeypatch):
    """Addresses arrive in whatever case the user typed; matching must not care."""
    claims = _valid_claims()
    claims["email"] = "  Owner@Example.COM  "
    _install(monkeypatch, claims)
    profile = await oauth.verify_google_token("token")
    assert profile.email == "owner@example.com"


@pytest.mark.asyncio
async def test_boolean_true_is_accepted_for_email_verified(monkeypatch):
    """Google's tokeninfo returns the string "true"; other paths return a bool."""
    claims = _valid_claims()
    claims["email_verified"] = True
    _install(monkeypatch, claims)
    assert (await oauth.verify_google_token("token")).email_verified is True


# ------------------------------------------------------------------ rejected

@pytest.mark.asyncio
async def test_a_token_for_another_application_is_rejected(monkeypatch):
    """
    The check that matters most. Without it, a token issued for any other
    Google app — one an attacker controls — would be accepted as proof of
    identity here.
    """
    claims = _valid_claims(client_id="someone-elses-app.apps.googleusercontent.com")
    _install(monkeypatch, claims)   # our client id stays the default

    with pytest.raises(oauth.HTTPException) as exc:
        await oauth.verify_google_token("token")
    assert exc.value.status_code == 401
    assert "different application" in exc.value.detail


@pytest.mark.asyncio
async def test_a_token_from_an_unexpected_issuer_is_rejected(monkeypatch):
    claims = _valid_claims()
    claims["iss"] = "https://accounts.evil.example"
    _install(monkeypatch, claims)

    with pytest.raises(oauth.HTTPException) as exc:
        await oauth.verify_google_token("token")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_an_unverified_email_is_rejected(monkeypatch):
    """An unverified Google address proves nothing about who controls it."""
    claims = _valid_claims()
    claims["email_verified"] = "false"
    _install(monkeypatch, claims)

    with pytest.raises(oauth.HTTPException) as exc:
        await oauth.verify_google_token("token")
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_a_rejected_token_from_google_is_not_trusted(monkeypatch):
    _install(monkeypatch, {"error": "invalid_token"}, status_code=400)

    with pytest.raises(oauth.HTTPException) as exc:
        await oauth.verify_google_token("token")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_a_token_without_a_subject_is_rejected(monkeypatch):
    """Matching is by subject. Without one there is nothing stable to match on."""
    claims = _valid_claims()
    del claims["sub"]
    _install(monkeypatch, claims)

    with pytest.raises(oauth.HTTPException) as exc:
        await oauth.verify_google_token("token")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_sign_in_is_refused_when_not_configured(monkeypatch):
    """
    A deployment without GOOGLE_CLIENT_ID must refuse rather than skip the
    audience check — an empty client id would otherwise match an empty aud.
    """
    monkeypatch.setattr(oauth, "GOOGLE_CLIENT_ID", "")

    with pytest.raises(oauth.HTTPException) as exc:
        await oauth.verify_google_token("token")
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_an_empty_audience_does_not_pass_when_unconfigured(monkeypatch):
    """
    The specific hole the previous test guards: token claims aud="" against an
    unset client id. It must fail on configuration, never match by accident.
    """
    claims = _valid_claims(client_id="")
    monkeypatch.setattr(oauth, "GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(
        oauth.httpx, "AsyncClient", lambda *a, **k: FakeClient(FakeResponse(claims))
    )

    with pytest.raises(oauth.HTTPException) as exc:
        await oauth.verify_google_token("token")
    assert exc.value.status_code == 503


# ------------------------------------------------------------- product rules

def test_only_owners_and_managers_may_link_google():
    """
    Staff accounts are provisioned by a manager and stay on those credentials.
    A line cook has no work Google account.
    """
    assert oauth.LINKABLE_ROLES == {"owner", "admin", "manager"}
    assert "employee" not in oauth.LINKABLE_ROLES


def test_both_google_issuer_spellings_are_accepted():
    """Google uses both, and rejecting either locks out real users."""
    assert "accounts.google.com" in oauth.ALLOWED_ISSUERS
    assert "https://accounts.google.com" in oauth.ALLOWED_ISSUERS


def test_config_endpoint_exposes_only_the_public_client_id():
    """
    The sign-in page needs this before anyone has authenticated, so it must
    carry nothing secret.
    """
    import inspect
    source = inspect.getsource(oauth.google_config)
    assert "client_secret" not in source
    assert "GOOGLE_CLIENT_SECRET" not in source
