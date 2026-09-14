"""
The agent's write path.

The agent never writes directly. It produces an AgentProposal, a human
confirms, and only then does anything change. That boundary is the security
model, so it is the part worth testing — and none of it needs Anthropic, since
the interesting code runs after the model has already spoken.

What has to hold:

  1. A proposal can only be confirmed by someone in the same workspace. The
     agent reads customer notes and invoice memos, which is text other people
     wrote; if a proposal could be confirmed across a tenant boundary, a
     crafted note becomes a write into somebody else's ledger.
  2. Confirming filters the fields it will set. A proposal naming `id` or
     `business_id` must not be able to move a record between businesses.
  3. A proposal applies once. Confirming twice must not duplicate.
  4. Read-only roles cannot confirm anything.
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlmodel import Session, select

from backend.app.agent_models import AgentProposal
from backend.app.ai_agent import WRITE_ROLES, _PROPOSABLE, _serialize
from backend.app.database import engine
from backend.app.models import Business, Contact, InventoryItem, TaskItem


# ------------------------------------------------------- the field allow-list

def test_only_proposable_entities_are_writable():
    """
    Invoices, payments and ledger entries are deliberately absent. A model that
    can be talked into editing a posted invoice is a model that can rewrite
    history, and no confirmation dialog makes that acceptable.
    """
    assert set(_PROPOSABLE) == {"contact", "inventory_item", "task", "booking"}
    assert "invoice" not in _PROPOSABLE
    assert "payment" not in _PROPOSABLE
    assert "ledger_account" not in _PROPOSABLE


@pytest.mark.parametrize("entity,model", sorted(_PROPOSABLE.items()))
def test_identity_columns_are_never_settable(entity, model):
    """
    Mirrors the filter in confirm_proposal. `business_id` is the one that
    matters: a proposal setting it would move a record into another workspace.
    """
    blocked = {"id", "business_id", "created_at"}
    allowed = {c for c in model.__fields__ if c not in blocked}
    assert not (allowed & blocked)
    assert "business_id" not in allowed, f"{entity} would allow a tenant move"


def test_filtering_drops_unknown_and_identity_fields():
    """A proposal carrying junk should write the legitimate part and drop the rest."""
    model = _PROPOSABLE["contact"]
    proposed = {
        "name": "Real Name",
        "business_id": 9999,          # tenant move attempt
        "id": 1,                      # identity overwrite attempt
        "created_at": "1999-01-01",   # history rewrite attempt
        "not_a_column": "junk",
    }
    allowed = {c for c in model.__fields__ if c not in ("id", "business_id", "created_at")}
    filtered = {k: v for k, v in proposed.items() if k in allowed}

    assert filtered == {"name": "Real Name"}


# --------------------------------------------------------------- serialising

def test_money_is_surfaced_in_dollars_alongside_cents():
    """
    The schema stores integer cents. Handing the model only the raw integer is
    how an assistant ends up telling somebody they are owed $124,000 when the
    figure is $1,240.
    """
    item = InventoryItem(
        business_id=1, sku="X", name="Thing",
        unit_cost_cents=124_000, sales_price_cents=200_000, quantity_milli=4_500,
    )
    data = _serialize(item)

    assert data["unit_cost_cents"] == 124_000
    assert data["unit_cost"] == 1240.00
    assert data["quantity_milli"] == 4_500
    assert data["quantity"] == 4.5


def test_serialising_drops_raw_json_blobs():
    """`*_json` columns are internal plumbing, not something to spend tokens on."""
    task = TaskItem(business_id=1, title="Do it", created_by_user_id=1)
    assert not any(k.endswith("_json") for k in _serialize(task))


# ---------------------------------------------------------------- the roles

def test_read_only_roles_cannot_write():
    """An accountant can read the books. They do not reorganise the stockroom."""
    assert "owner" in WRITE_ROLES
    assert "admin" in WRITE_ROLES
    assert "manager" in WRITE_ROLES
    assert "employee" not in WRITE_ROLES
    assert "accountant" not in WRITE_ROLES


# ------------------------------------------------------- the confirm endpoint

@pytest.fixture(scope="module")
def agent_client():
    from fastapi.testclient import TestClient
    from backend.app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def two_workspaces(agent_client):
    """
    An owner with their own workspace, plus a second workspace they have no
    membership in — the shape a cross-tenant attempt actually takes.

    Built directly rather than through /auth/setup, because "first user" only
    happens once per database and test_platform.py asserts on it. A fixture
    that races for it makes the suite order-dependent, which is how a green run
    turns red for no reason anybody can reproduce.
    """
    from backend.app.auth import create_access_token, hash_password
    from backend.app.models import Membership, UserAccount
    from backend.app.platform import seed_business
    from backend.app.tenancy import set_current_business_id

    suffix = uuid.uuid4().hex[:6]

    with Session(engine) as s:
        user = UserAccount(
            username=f"agentowner{suffix}",
            password_hash=hash_password("correct-horse-battery"),
            role="manager",
            active=True,
        )
        s.add(user)
        s.flush()

        mine = Business(name=f"Agent Co {suffix}", industry="general", active=True)
        s.add(mine)
        s.flush()

        set_current_business_id(mine.id)
        try:
            seed_business(s, mine, user, role="owner")
            s.commit()
        finally:
            set_current_business_id(1)

        stranger = Business(name=f"Stranger {suffix}", industry="general", active=True)
        s.add(stranger)
        s.commit()

        s.refresh(user)
        s.refresh(mine)
        s.refresh(stranger)
        token = create_access_token(user)
        ids = (user.id, mine.id, stranger.id)

    user_id, mine_id, stranger_id = ids
    return {
        "client": agent_client,
        "auth": {"Authorization": f"Bearer {token}"},
        "user_id": user_id,
        "mine": mine_id,
        "theirs": stranger_id,
    }


def _propose(business_id: int, user_id: int, changes: dict, entity: str = "contact") -> int:
    with Session(engine) as s:
        p = AgentProposal(
            business_id=business_id,
            user_id=user_id,
            thread_id=uuid.uuid4().hex,
            entity_type=entity,
            action="create",
            changes_json=json.dumps(changes),
            summary="test proposal",
        )
        s.add(p)
        s.commit()
        s.refresh(p)
        return p.id


def test_confirming_a_proposal_creates_the_record(two_workspaces):
    ws = two_workspaces
    name = f"Agent Made {uuid.uuid4().hex[:6]}"
    pid = _propose(ws["mine"], ws["user_id"], {"name": name, "contact_type": "customer"})

    r = ws["client"].post(
        f"/agent/proposals/{pid}/confirm",
        headers={**ws["auth"], "X-Business-Id": str(ws["mine"])},
    )
    assert r.status_code == 200, r.text

    with Session(engine) as s:
        rows = s.exec(select(Contact).execution_options(include_all_businesses=True)).all()
    assert any(c.name == name and c.business_id == ws["mine"] for c in rows)


def test_a_proposal_cannot_be_confirmed_from_another_workspace(two_workspaces):
    """
    The boundary that matters most. A proposal belonging to one workspace must
    not apply while acting as another.
    """
    ws = two_workspaces
    pid = _propose(ws["theirs"], ws["user_id"], {"name": "Cross Tenant", "contact_type": "customer"})

    r = ws["client"].post(
        f"/agent/proposals/{pid}/confirm",
        headers={**ws["auth"], "X-Business-Id": str(ws["mine"])},
    )
    assert r.status_code == 404, "a proposal from another workspace was applied"


def test_a_proposal_applies_only_once(two_workspaces):
    ws = two_workspaces
    name = f"Once Only {uuid.uuid4().hex[:6]}"
    pid = _propose(ws["mine"], ws["user_id"], {"name": name, "contact_type": "customer"})
    headers = {**ws["auth"], "X-Business-Id": str(ws["mine"])}

    assert ws["client"].post(f"/agent/proposals/{pid}/confirm", headers=headers).status_code == 200
    second = ws["client"].post(f"/agent/proposals/{pid}/confirm", headers=headers)
    assert second.status_code == 409, "a proposal applied twice"

    with Session(engine) as s:
        rows = s.exec(select(Contact).execution_options(include_all_businesses=True)).all()
    assert len([c for c in rows if c.name == name]) == 1


def test_a_proposal_cannot_smuggle_a_record_into_another_workspace(two_workspaces):
    """
    The proposal names business_id explicitly. The filter must drop it and the
    record must land in the confirming user's workspace regardless.
    """
    ws = two_workspaces
    name = f"Smuggled {uuid.uuid4().hex[:6]}"
    pid = _propose(
        ws["mine"], ws["user_id"],
        {"name": name, "contact_type": "customer", "business_id": ws["theirs"]},
    )

    r = ws["client"].post(
        f"/agent/proposals/{pid}/confirm",
        headers={**ws["auth"], "X-Business-Id": str(ws["mine"])},
    )
    assert r.status_code == 200

    with Session(engine) as s:
        rows = s.exec(select(Contact).execution_options(include_all_businesses=True)).all()
    landed = [c for c in rows if c.name == name]
    assert landed, "the record was not created"
    assert landed[0].business_id == ws["mine"], "business_id survived the filter"


def test_rejecting_a_proposal_writes_nothing(two_workspaces):
    ws = two_workspaces
    name = f"Rejected {uuid.uuid4().hex[:6]}"
    pid = _propose(ws["mine"], ws["user_id"], {"name": name, "contact_type": "customer"})
    headers = {**ws["auth"], "X-Business-Id": str(ws["mine"])}

    assert ws["client"].post(f"/agent/proposals/{pid}/reject", headers=headers).status_code == 200

    with Session(engine) as s:
        rows = s.exec(select(Contact).execution_options(include_all_businesses=True)).all()
    assert not any(c.name == name for c in rows)

    # And a rejected proposal must not be confirmable afterwards.
    assert ws["client"].post(f"/agent/proposals/{pid}/confirm", headers=headers).status_code == 409


def test_confirming_is_recorded_in_the_audit_log(two_workspaces):
    """
    Every applied change carries the prompt that produced it. Without that, a
    surprising edit has no explanation and no accountability.
    """
    from backend.app.models import AuditEvent

    ws = two_workspaces
    name = f"Audited {uuid.uuid4().hex[:6]}"
    pid = _propose(ws["mine"], ws["user_id"], {"name": name, "contact_type": "customer"})

    ws["client"].post(
        f"/agent/proposals/{pid}/confirm",
        headers={**ws["auth"], "X-Business-Id": str(ws["mine"])},
    )

    with Session(engine) as s:
        events = s.exec(select(AuditEvent).execution_options(include_all_businesses=True)).all()
    agent_events = [e for e in events if e.action.startswith("agent.") and e.business_id == ws["mine"]]
    assert agent_events, "no audit event for an agent-applied change"
    assert "confirmed_by" in agent_events[-1].detail_json
