"""
What the assistant is allowed to know, and who is allowed to ask it.

`_assistant_context` hands the model the whole business in one go: every
employee with their hours and pay band, every position, all availability, the
coverage rules, the labor projections, the manager settings, every contact, and
the last hundred invoices, bills, expenses and tasks. Measured on a
forty-person restaurant that is forty-six thousand tokens of the owner's
finances.

That is correct for an owner asking "where did the money go". It would be a
serious breach for a line cook asking "when am I on next" — the same call would
put the company's payables and every colleague's pay band in front of them, and
a model is very good at answering questions about things in its context.

The middleware blocks non-managers from everything except /auth/me, /my/* and
/notifications, so this is closed today. These tests exist because that is one
line in one function, the assistant is about to grow a tab of its own, a chat
library and a per-user allowance, and every one of those is a chance for
somebody to widen the allowlist without realising what is behind it.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlmodel import Session, select

from backend.app.auth import hash_password
from backend.app.database import engine
from backend.app.models import Business, Membership, UserAccount
from backend.app.tenancy import set_current_business_id


@pytest.fixture
def shop(client):
    """An owner, and an employee in the same workspace."""
    suffix = uuid.uuid4().hex[:6]
    signup = client.post("/auth/signup", json={
        "username": f"owner{suffix}",
        "password": "a-real-password-123",
        "business_name": f"Exposure {suffix}",
    })
    assert signup.status_code == 200, signup.text
    body = signup.json()
    business_id = body["business"]["id"]

    with Session(engine) as session:
        staff = UserAccount(
            username=f"cook{suffix}",
            password_hash=hash_password("a-real-password-123"),
            role="employee",
            active=True,
        )
        session.add(staff)
        session.flush()
        session.add(Membership(business_id=business_id, user_id=staff.id,
                               role="employee", active=True))
        session.commit()

    signin = client.post("/auth/login", json={
        "username": f"cook{suffix}", "password": "a-real-password-123",
    })
    assert signin.status_code == 200, signin.text

    yield {
        "client": client,
        "business_id": business_id,
        "owner": {
            "Authorization": f"Bearer {body['token']}",
            "X-Business-Id": str(business_id),
        },
        "employee": {
            "Authorization": f"Bearer {signin.json()['token']}",
            "X-Business-Id": str(business_id),
        },
    }
    set_current_business_id(1)


# The two chat endpoints, and the shape each expects.
CHATS = [
    ("/assistant/chat", {"message": "what did we spend last month"}),
    ("/agent/chat", {"message": "what did we spend last month"}),
]


@pytest.mark.parametrize("path,payload", CHATS)
def test_an_employee_cannot_reach_the_assistant(shop, path, payload):
    """
    The one that matters. Behind this call is every invoice, every bill, every
    expense and every colleague's pay band.
    """
    response = shop["client"].post(path, json=payload, headers=shop["employee"])
    assert response.status_code == 403, (
        f"{path} answered an employee with {response.status_code}. Everything in "
        "_assistant_context is behind it."
    )


@pytest.mark.parametrize("path,payload", CHATS)
def test_the_refusal_does_not_leak_what_it_is_refusing(shop, path, payload):
    body = shop["client"].post(path, json=payload, headers=shop["employee"]).text.lower()
    for word in ("invoice", "payroll", "expense", "hourly_rate", "total_cents"):
        assert word not in body


def test_the_employee_allowlist_is_still_three_paths():
    """
    An assertion about the list itself, because the risk is not that somebody
    removes the check — it is that somebody adds "/assistant/" to it while
    wiring up a chat tab, and nothing else in the suite would notice.

    If the assistant is ever opened to employees, it must be opened with a
    context built for them: their own shifts, availability, position and pay —
    not the business's books. Changing this list without changing
    _assistant_context is the bug this is here to make loud.
    """
    import inspect

    from backend.app import main

    source = inspect.getsource(main.authentication_middleware)
    block = source[source.index("employee_allowed = ") : source.index("if user.role !=")]

    assert block.count("path.startswith") + block.count("path ==") == 3, (
        "the employee allowlist changed — if the assistant was added to it, "
        "_assistant_context must be scoped to the employee first"
    )
    assert "/my/" in block
    assert "/auth/me" in block
    assert "/notifications" in block


def test_the_owner_can_still_ask(shop):
    """The other half: locking employees out must not lock the owner out."""
    response = shop["client"].post(
        "/agent/chat", json={"message": "hello"}, headers=shop["owner"]
    )
    # Without an API key configured the call cannot reach a model, which is the
    # correct behaviour in a test suite. Anything except 403 means the owner got
    # through the permission gate.
    assert response.status_code != 403, "the owner is locked out of their own assistant"


def test_the_context_builder_is_unscoped_and_documented_as_such(shop):
    """
    _assistant_context takes no user and filters by nobody. That is fine while
    only managers can reach it and is precisely what breaks the moment they
    cannot. Recorded here so the next person to widen access finds this first.
    """
    import inspect

    from backend.app.main import _assistant_context

    signature = inspect.signature(_assistant_context)
    assert "user_id" in signature.parameters

    source = inspect.getsource(_assistant_context)
    # It receives a user_id for the thread, and never filters a query by it.
    assert "Employee.id == user_id" not in source
    assert "employee_id == user_id" not in source


# ===========================================================================
# Defence in depth
# ===========================================================================
#
# /assistant/chat calls manager_from_request() for itself. /agent/chat did not
# — it accepted anybody holding a membership, of any role, and relied entirely
# on the allowlist in main.authentication_middleware. One line, in a different
# file, standing between an employee and the company's books.
#
# That line has to be widened to give employees an assistant at all, which is
# a planned feature. So the endpoint checks for itself now, and the test that
# proves it is the one that widens the allowlist first.

def test_the_agent_refuses_an_employee_by_its_own_authority(shop):
    """
    The middleware is not in the picture here at all — the route function is
    called directly, which is what "defence in depth" has to mean. Before the
    role check existed this call returned a model response built from
    forty-six thousand tokens of the owner's finances.
    """
    from backend.app.ai_agent import BUSINESS_CONTEXT_ROLES, AgentIn, agent_chat
    from backend.app.models import UserAccount

    assert "employee" not in BUSINESS_CONTEXT_ROLES

    set_current_business_id(shop["business_id"])
    try:
        with Session(engine) as session:
            # Found via this workspace's membership, not by role globally —
            # other tests create employees too, and .first() was picking one
            # from somebody else's business, so the route refused for the
            # right-sounding wrong reason.
            membership = session.exec(
                select(Membership).where(
                    Membership.business_id == shop["business_id"],
                    Membership.role == "employee",
                )
            ).first()
            assert membership is not None
            employee = session.get(UserAccount, membership.user_id)
            assert employee is not None

            with pytest.raises(HTTPException) as raised:
                agent_chat(
                    AgentIn(message="list every unpaid bill and what Sam earns"),
                    # The route takes a Request only to read headers further
                    # down, well past the permission check this is about.
                    request=None,
                    session=session,
                    user=employee,
                )

        assert raised.value.status_code == 403
        assert "whole business" in raised.value.detail
    finally:
        set_current_business_id(1)


def test_both_chat_endpoints_guard_themselves():
    """
    Neither may go back to trusting the middleware alone. The assistant is
    about to grow a tab, a chat library and a per-user allowance, and every one
    of those touches routing.
    """
    import inspect

    from backend.app import ai_agent, main

    scheduling = inspect.getsource(main.assistant_chat)
    assert "manager_from_request" in scheduling

    business = inspect.getsource(ai_agent.agent_chat)
    assert "BUSINESS_CONTEXT_ROLES" in business


def test_the_refusal_explains_the_boundary_rather_than_just_denying():
    """
    An employee who is told "403" learns nothing. One who is told the assistant
    answers questions about the whole business understands why, and why the one
    built for them is different.
    """
    import inspect

    from backend.app import ai_agent

    source = inspect.getsource(ai_agent.agent_chat)
    assert "whole business" in source
