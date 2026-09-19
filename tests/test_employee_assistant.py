"""
The assistant an employee is allowed to have.

The business assistant is handed the company — every invoice, bill, expense and
task, every contact, and every colleague's hours and pay band. On a forty-person
restaurant that is 46,110 tokens. Giving that to a line cook asking when they
are on next would be a breach, so there is a second context that answers from
one person's own record and nothing else.

The important tests here do not check that the right things are present. They
check that the wrong things are absent, against a workspace deliberately filled
with the things that must not appear: other people on higher pay, unpaid bills,
expenses, invoices, suppliers, and a draft rota nobody has published.

A guard that only asserts the happy path would pass on a context builder that
returned the entire database with the employee's name at the top.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, timedelta

import pytest
from sqlmodel import Session, select

from backend.app.auth import hash_password
from backend.app.database import engine
from backend.app.employee_assistant import employee_context, hourly_rate_for
from backend.app.models import (
    Bill,
    Business,
    Contact,
    Employee,
    EmployeePosition,
    Expense,
    Invoice,
    ManagerSettings,
    Membership,
    Position,
    RecurringAvailability,
    Schedule,
    ScheduleShift,
    UserAccount,
)
from backend.app.tenancy import set_current_business_id

SECRETS = {
    "invoice_number": "INV-SECRET-9001",
    "bill_number": "BILL-SECRET-9002",
    "supplier": "Clandestine Produce Ltd",
    "expense_note": "walk-in compressor replacement",
    "colleague": "Priya The Better Paid",
    "colleague_rate": 41.75,
    "draft_position": "Secret Midnight Shift",
}


@pytest.fixture
def shop(client):
    """One employee, one much better paid colleague, and a lot of money."""
    suffix = uuid.uuid4().hex[:6]
    signup = client.post("/auth/signup", json={
        "username": f"owner{suffix}",
        "password": "a-real-password-123",
        "business_name": f"Leaky {suffix}",
    })
    assert signup.status_code == 200, signup.text
    bid = signup.json()["business"]["id"]
    set_current_business_id(bid)

    with Session(engine) as s:
        settings = s.exec(select(ManagerSettings)).first()
        if not settings:
            settings = ManagerSettings(business_id=bid)
        settings.employee_hourly_rate = 17.50
        settings.gm_hourly_rate = 33.00
        s.add(settings)

        front = Position(business_id=bid, name="Front", department="General", active=True)
        secret = Position(business_id=bid, name=SECRETS["draft_position"],
                          department="General", active=True)
        s.add(front); s.add(secret); s.commit(); s.refresh(front); s.refresh(secret)

        me = Employee(business_id=bid, name="Sam Ordinary", department="General",
                      role="employee", active=True, max_hours_per_week=32)
        them = Employee(business_id=bid, name=SECRETS["colleague"], department="General",
                        role="gm", active=True,
                        hourly_rate_override=SECRETS["colleague_rate"])
        s.add(me); s.add(them); s.commit(); s.refresh(me); s.refresh(them)

        s.add(EmployeePosition(business_id=bid, employee_id=me.id, position_id=front.id))
        s.add(RecurringAvailability(business_id=bid, employee_id=me.id,
                                    rule_type="available", day_of_week=0,
                                    start_time="09:00", end_time="17:00"))

        account = UserAccount(username=f"sam{suffix}",
                              password_hash=hash_password("a-real-password-123"),
                              role="employee", active=True, employee_id=me.id)
        s.add(account); s.flush()
        s.add(Membership(business_id=bid, user_id=account.id, role="employee", active=True))

        monday = (date.today() - timedelta(days=date.today().weekday())).isoformat()

        published = Schedule(business_id=bid, week_start=monday, status="published", version=1)
        draft = Schedule(business_id=bid, week_start=monday, status="draft", version=2)
        s.add(published); s.add(draft); s.commit()
        s.refresh(published); s.refresh(draft)

        # Mine, published.
        s.add(ScheduleShift(business_id=bid, schedule_id=published.id, date=monday,
                            employee_id=me.id, position_id=front.id, role="employee",
                            start_time="09:00", end_time="17:00"))
        # A colleague's, published — must not appear.
        s.add(ScheduleShift(business_id=bid, schedule_id=published.id, date=monday,
                            employee_id=them.id, position_id=front.id, role="gm",
                            start_time="07:00", end_time="15:00"))
        # Mine, but only in the draft — must not appear either.
        s.add(ScheduleShift(business_id=bid, schedule_id=draft.id, date=monday,
                            employee_id=me.id, position_id=secret.id, role="employee",
                            start_time="23:00", end_time="03:00"))

        vendor = Contact(business_id=bid, name=SECRETS["supplier"],
                         contact_type="vendor", active=True)
        s.add(vendor); s.commit(); s.refresh(vendor)
        s.add(Invoice(business_id=bid, number=SECRETS["invoice_number"],
                      customer_id=vendor.id, issue_date=monday, due_date=monday,
                      status="sent", total_cents=999_00, paid_cents=0))
        s.add(Bill(business_id=bid, number=SECRETS["bill_number"], vendor_id=vendor.id,
                   bill_date=monday, due_date=monday, status="open",
                   total_cents=888_00, paid_cents=0))
        s.add(Expense(business_id=bid, expense_date=monday, account_id=1,
                      payment_account_id=1, amount_cents=777_00,
                      description=SECRETS["expense_note"]))
        s.commit()
        account_id = account.id

    yield {"client": client, "business_id": bid, "user_id": account_id}
    set_current_business_id(1)


def _context(shop) -> dict:
    set_current_business_id(shop["business_id"])
    with Session(engine) as session:
        user = session.get(UserAccount, shop["user_id"])
        return employee_context(session, user)


def _as_text(context: dict) -> str:
    return json.dumps(context, default=str).lower()


# ===========================================================================
# What must not be in it
# ===========================================================================

@pytest.mark.parametrize("label,secret", sorted(
    (k, v) for k, v in SECRETS.items() if isinstance(v, str)
))
def test_the_context_does_not_contain(shop, label, secret):
    """
    Each of these is in the same database, reachable from the same session, and
    would be in the business assistant's context. None may be here.
    """
    assert secret.lower() not in _as_text(shop and _context(shop))


def test_it_does_not_contain_anybody_elses_pay(shop):
    """
    Two ways this leaks and both are checked: the colleague's own override, and
    the pay bands on ManagerSettings. Handing over the settings object to
    explain somebody's wage discloses every role's — and the first version of
    this test only looked for the override, so leaking the settings object left
    it green.
    """
    text = _as_text(_context(shop))
    assert str(SECRETS["colleague_rate"]) not in text     # their override, 41.75
    assert "33.0" not in text                              # the GM band on settings
    assert "gm_hourly_rate" not in text
    assert "shift_lead_hourly_rate" not in text


def test_it_does_not_contain_any_money_the_business_owes_or_is_owed(shop):
    text = _as_text(_context(shop))
    for amount in ("99900", "88800", "77700", "999.0", "888.0", "777.0"):
        assert amount not in text


def test_every_shift_in_it_belongs_to_them(shop):
    """
    Checked against the database rather than against a start time. The first
    version asserted no shift began at 07:00, which is only the colleague's
    shift while the fixture says so — and it stayed green when the employee
    filter was deleted, because a different bug changed which rota got picked.
    """
    context = _context(shop)
    set_current_business_id(shop["business_id"])
    with Session(engine) as session:
        user = session.get(UserAccount, shop["user_id"])
        mine = {
            (row.date, row.start_time)
            for row in session.exec(
                select(ScheduleShift).where(ScheduleShift.employee_id == user.employee_id)
            ).all()
        }
    for shift in context["your_shifts"]:
        assert (shift["date"], shift["start"]) in mine, (
            f"{shift} is somebody else's shift"
        )


def test_an_unpublished_shift_is_not_in_it(shop):
    """
    A draft is a manager's working document. Telling somebody they are on at
    23:00 before it is published is how a draft becomes a promise.
    """
    context = _context(shop)
    assert all(shift["start"] != "23:00" for shift in context["your_shifts"])
    assert SECRETS["draft_position"] not in _as_text(context)


def test_it_is_small_enough_to_ask_a_question_with(shop):
    """
    The business context measured 46,110 tokens on a forty-person restaurant,
    which is six questions a month out of the included allowance. This one has
    to be cheap or per-employee access is not affordable at any price.
    """
    characters = len(json.dumps(_context(shop), default=str))
    assert characters < 4_000, f"{characters} characters is not a personal context"


# ===========================================================================
# What must be in it
# ===========================================================================

def test_it_knows_who_they_are_and_what_they_earn(shop):
    you = _context(shop)["you"]
    assert you["name"] == "Sam Ordinary"
    assert you["hourly_rate"] == 17.50
    assert you["max_hours_per_week"] == 32


def test_it_knows_their_published_shift(shop):
    shifts = _context(shop)["your_shifts"]
    assert len(shifts) == 1
    assert shifts[0]["start"] == "09:00"
    assert shifts[0]["hours"] == 8.0


def test_it_can_answer_what_am_i_owed_this_week(shop):
    this_week = _context(shop)["your_hours"][0]
    assert this_week["hours"] == 8.0
    assert this_week["estimated_pay"] == round(8.0 * 17.50, 2)


def test_it_says_when_a_rota_is_not_published_yet(shop):
    """
    Next week has no published rota. "No shifts" and "not published yet" are
    different sentences and the second one is the true one.
    """
    next_week = _context(shop)["your_hours"][1]
    assert next_week["published"] is False


def test_an_account_with_no_staff_record_gets_nothing_rather_than_something(shop):
    set_current_business_id(shop["business_id"])
    with Session(engine) as session:
        user = session.get(UserAccount, shop["user_id"])
        user.employee_id = None
        assert employee_context(session, user) == {"linked": False}


# ===========================================================================
# The rule that keeps it that way
# ===========================================================================

def test_pay_is_computed_rather_than_handed_over():
    """
    ManagerSettings holds the rate for every role. Returning it to tell somebody
    their own wage would tell them everybody's.
    """
    settings = ManagerSettings(employee_hourly_rate=15.0, shift_lead_hourly_rate=20.0,
                               gm_hourly_rate=30.0)
    assert hourly_rate_for(Employee(name="a", department="x", role="employee"), settings) == 15.0
    assert hourly_rate_for(Employee(name="b", department="x", role="gm"), settings) == 30.0
    assert hourly_rate_for(
        Employee(name="c", department="x", role="employee", hourly_rate_override=25.0), settings
    ) == 25.0


def test_the_context_is_built_by_name_and_never_spread():
    """
    The rule that makes this hold next year: every value is typed out. No
    model.dict(), no **row, no SQLModel passed through — so a field added to
    Employee or ManagerSettings cannot arrive here on its own.
    """
    import inspect

    from backend.app import employee_assistant

    source = inspect.getsource(employee_assistant.employee_context)
    for spread in (".dict()", ".model_dump()", "**row", "**employee", "**settings"):
        assert spread not in source, f"{spread} would let unreviewed fields through"


# ===========================================================================
# Reaching it
# ===========================================================================
#
# It lives under /my/ deliberately. That prefix is already what
# authentication_middleware lets employees through, so giving staff an
# assistant widened no permission anywhere — which matters, because the
# alternative was editing the one line standing between them and the business
# assistant's forty-six thousand tokens of company finances.

def test_an_employee_can_reach_their_own_assistant(shop):
    signin = shop["client"].post("/auth/login", json={
        "username": _username(shop), "password": "a-real-password-123",
    })
    assert signin.status_code == 200, signin.text

    response = shop["client"].post(
        "/my/assistant/chat",
        json={"message": "when am I on this week"},
        headers={
            "Authorization": f"Bearer {signin.json()['token']}",
            "X-Business-Id": str(shop["business_id"]),
        },
    )
    # No API key is configured in the suite, so the call cannot reach a model.
    # 403 would mean the permission gate refused, which is the thing being
    # checked; anything else means they got through it.
    assert response.status_code != 403, (
        "an employee cannot reach the assistant built for them"
    )


def test_it_needed_no_change_to_the_employee_allowlist():
    """
    The whole point of the /my/ prefix. If a later version moves this endpoint
    and widens the allowlist to compensate, the business assistant goes with
    it — see tests/test_assistant_exposure.py.
    """
    import inspect

    from backend.app import employee_assistant, main

    assert 'prefix="/my"' in inspect.getsource(employee_assistant)

    source = inspect.getsource(main.authentication_middleware)
    block = source[source.index("employee_allowed = ") : source.index("if user.role !=")]
    assert block.count("path.startswith") + block.count("path ==") == 3


def _username(shop) -> str:
    set_current_business_id(shop["business_id"])
    with Session(engine) as session:
        return session.get(UserAccount, shop["user_id"]).username
