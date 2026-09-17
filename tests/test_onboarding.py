"""
The first ninety seconds.

The landing page sells well and hands off to a blank room: an empty dashboard,
twenty-one tabs, every tile reading $0.00. For most trials that is the only
ninety seconds the product gets.

This is not a wizard. A wizard is a thing people abandon halfway and can never
find again. It measures the workspace instead — which means the checklist is
true whether somebody followed it, ignored it, or did the work months ago in a
different order, and there is no separate "did they finish onboarding" flag to
drift out of sync with reality.

Two properties carry the whole idea. It must only ask for things the workspace
can actually use, so a books-only customer is never told to add staff. And the
first undone step must be the right next move, because that is the only
instruction most people will read.
"""

from __future__ import annotations

import uuid

import pytest
from sqlmodel import Session, select

from backend.app.auth import hash_password
from backend.app.database import engine
from backend.app.models import (
    Business, BusinessModule, Contact, Employee, InventoryItem, Position,
    Schedule, Service, Subscription, UserAccount,
)
from backend.app.platform import seed_business
from backend.app.tenancy import set_current_business_id


@pytest.fixture
def shop(client):
    suffix = uuid.uuid4().hex[:6]
    creds = {"username": f"ob{suffix}", "password": "a-real-password-123",
             "business_name": f"Onboard {suffix}"}
    signup = client.post("/auth/signup", json=creds)
    assert signup.status_code == 200, signup.text
    body = signup.json()

    yield {
        "business_id": body["business"]["id"],
        "client": client,
        "headers": {
            "Authorization": f"Bearer {body['token']}",
            "X-Business-Id": str(body["business"]["id"]),
        },
    }
    set_current_business_id(1)


def _state(shop):
    response = shop["client"].get("/platform/onboarding", headers=shop["headers"])
    assert response.status_code == 200, response.text
    return response.json()


def _keys(state):
    return [s["key"] for s in state["steps"]]


def _add(shop, *rows):
    with Session(engine) as s:
        for row in rows:
            s.add(row)
        s.commit()


def _only_modules(shop, keep):
    """Switch the workspace down to one module, the way billing would."""
    with Session(engine) as s:
        rows = s.exec(
            select(BusinessModule).where(BusinessModule.business_id == shop["business_id"])
        ).all()
        for row in rows:
            row.enabled = row.module_key in keep
            s.add(row)
        s.commit()


# ===========================================================================
# What a new workspace is told
# ===========================================================================

def test_a_new_workspace_has_everything_still_to_do(shop):
    state = _state(shop)

    assert state["done"] == 0
    assert state["complete"] is False
    assert state["total"] > 0


def test_the_first_step_is_the_one_that_unlocks_the_most(shop):
    """
    Staff before a rota, because a rota needs people; a rota before preflight,
    because preflight needs a rota. The first undone step is the only
    instruction most people will read, so it has to be the right one.
    """
    state = _state(shop)

    assert state["next"]["key"] == "staff"
    assert state["next"]["tab"] == "manager"
    assert state["next"]["action"]


def test_every_step_says_why_it_is_worth_doing(shop):
    """
    "Add your team" is a chore. "Rotas, availability and labor cost all start
    here" is a reason. A checklist without reasons is a form.
    """
    for step in _state(shop)["steps"]:
        assert step["why"], f"{step['key']} has no reason"
        assert step["title"]
        assert step["tab"], f"{step['key']} has nowhere to go"


def test_the_rota_step_names_the_thing_nothing_else_does(shop):
    rota = next(s for s in _state(shop)["steps"] if s["key"] == "rota")
    assert "Preflight" in rota["why"]


# ===========================================================================
# It measures rather than tracks
# ===========================================================================

def test_doing_the_work_completes_the_step(shop):
    assert not next(s for s in _state(shop)["steps"] if s["key"] == "staff")["done"]

    _add(shop, Employee(business_id=shop["business_id"], name="Sam",
                        department="General", role="employee", active=True))

    state = _state(shop)
    assert next(s for s in state["steps"] if s["key"] == "staff")["done"]
    assert state["done"] == 1


def test_it_notices_work_done_in_any_order(shop):
    """
    No wizard to follow means no wrong order. Somebody who raises an invoice
    before adding staff has done a real thing and the checklist says so.
    """
    _add(shop, Contact(business_id=shop["business_id"], name="Acme",
                       contact_type="customer", active=True))

    state = _state(shop)
    assert next(s for s in state["steps"] if s["key"] == "contacts")["done"]
    assert state["next"]["key"] == "staff", "the next step should still be the first undone one"


def test_an_inactive_record_does_not_count(shop):
    """A deactivated employee is not a team."""
    _add(shop, Employee(business_id=shop["business_id"], name="Gone",
                        department="General", role="employee", active=False))

    assert not next(s for s in _state(shop)["steps"] if s["key"] == "staff")["done"]


def test_finishing_everything_retires_the_checklist(shop):
    bid = shop["business_id"]
    _add(
        shop,
        Employee(business_id=bid, name="Sam", department="General", role="employee", active=True),
        Position(business_id=bid, name="Front", department="General", active=True),
        Schedule(business_id=bid, week_start="2026-09-14", status="draft"),
        Contact(business_id=bid, name="Acme", contact_type="customer", active=True),
        InventoryItem(business_id=bid, sku="GIN", name="Gin", unit="ml", active=True),
        Service(business_id=bid, name="Cut", duration_minutes=60, price=40.0, active=True),
        Subscription(business_id=bid, stripe_customer_id="cus_1",
                     stripe_subscription_id="sub_1", status="active",
                     plan="modular", current_period_end=""),
    )
    # The two that need a real posting rather than a row.
    accounts = shop["client"].get("/platform/accounts", headers=shop["headers"]).json()
    cash = next(a for a in accounts if a["subtype"] == "cash")
    equity = next(a for a in accounts if a["subtype"] == "owner_equity")
    shop["client"].post("/platform/journal", headers=shop["headers"], json={
        "entry_date": "2026-09-16", "memo": "opening",
        "lines": [
            {"account_id": cash["id"], "description": "x", "debit": 100.0, "credit": 0},
            {"account_id": equity["id"], "description": "x", "debit": 0, "credit": 100.0},
        ],
    })
    shop["client"].post("/platform/invoices", headers=shop["headers"], json={
        "customer_id": shop["client"].get("/platform/contacts", headers=shop["headers"]).json()[0]["id"],
        "issue_date": "2026-09-16", "due_date": "2026-09-30",
        "lines": [{"description": "Work", "quantity": 1, "unit_price": 100.0}],
    })

    state = _state(shop)
    assert state["complete"] is True, [s["key"] for s in state["steps"] if not s["done"]]
    assert state["next"] is None


# ===========================================================================
# It only asks for what the workspace can use
# ===========================================================================

def test_a_books_only_workspace_is_never_told_to_add_staff(shop):
    """
    Noise in a checklist is how checklists get ignored. Somebody who bought
    the ledger has no use for a rota step.
    """
    _only_modules(shop, {"accounting", "home", "settings", "notifications"})

    keys = _keys(_state(shop))
    assert "staff" not in keys
    assert "rota" not in keys
    assert "books" in keys


def test_a_scheduling_only_workspace_is_not_told_to_raise_invoices(shop):
    _only_modules(shop, {"scheduling", "home", "settings", "notifications"})

    keys = _keys(_state(shop))
    assert "staff" in keys
    assert "invoice" not in keys
    assert "stock" not in keys


def test_billing_is_asked_of_everybody(shop):
    """It is the one step that is not about a module."""
    _only_modules(shop, {"home", "settings", "notifications"})
    assert "billing" in _keys(_state(shop))


def test_a_trial_counts_as_subscribed(shop):
    _add(shop, Subscription(business_id=shop["business_id"], stripe_customer_id="cus_2",
                            stripe_subscription_id="sub_2", status="trialing",
                            plan="modular", current_period_end=""))

    assert next(s for s in _state(shop)["steps"] if s["key"] == "billing")["done"]


def test_a_cancelled_subscription_does_not(shop):
    _add(shop, Subscription(business_id=shop["business_id"], stripe_customer_id="cus_3",
                            stripe_subscription_id="sub_3", status="canceled",
                            plan="modular", current_period_end=""))

    assert not next(s for s in _state(shop)["steps"] if s["key"] == "billing")["done"]


# ===========================================================================
# The tenant boundary
# ===========================================================================

def test_another_workspace_cannot_complete_your_checklist(shop):
    suffix = uuid.uuid4().hex[:6]
    with Session(engine) as s:
        user = UserAccount(username=f"other{suffix}", password_hash=hash_password("x" * 12),
                           role="manager", active=True)
        s.add(user)
        s.flush()
        business = Business(name="Elsewhere", industry="general", active=True)
        s.add(business)
        s.flush()
        other_id = business.id
        set_current_business_id(other_id)
        try:
            seed_business(s, business, user, role="owner")
            s.commit()
        finally:
            set_current_business_id(1)

    _add(shop, Employee(business_id=other_id, name="Theirs",
                        department="General", role="employee", active=True))

    assert not next(s for s in _state(shop)["steps"] if s["key"] == "staff")["done"]


def test_the_checklist_needs_a_signed_in_user(client):
    assert client.get("/platform/onboarding").status_code == 401
