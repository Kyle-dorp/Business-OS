"""
Preflight — the four-question check before a schedule goes out.

    1. Is it legal?      2. Is it staffed?
    3. Is it affordable? 4. Can you serve it?

This is the product's clearest differentiator and it had no coverage at all.
Running it found the failure a pre-publish check can least afford: on a
workspace where nobody had entered hourly rates, every shift cost zero, the
week computed as 0% labor, and the verdict came back **"Clear to publish"** on
a schedule that was actually 43% labor and losing money.

That is the state every new customer is in on day one.

So these tests lean on one idea: a check that answers confidently from data it
does not have is worse than one that says it cannot tell. Several of them run
the same schedule twice and assert the answer only changes when the underlying
facts do.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlmodel import Session

from backend.app.auth import hash_password
from backend.app.database import engine
from backend.app.models import (
    Booking, Business, Employee, Invoice, Schedule, ScheduleShift, Service, UserAccount,
)
from backend.app.ops_models import ComplianceProfile, EmployeeCompliance
from backend.app.platform import seed_business
from backend.app.preflight import _labor_cost, _minutes, _shift_hours, _unreadable_shifts
from backend.app.tenancy import set_current_business_id


def _bare_shift(start="09:00", end="17:00", employee_id=1, day="2026-09-14"):
    """An unsaved shift, for exercising the pure helpers."""
    return ScheduleShift(
        schedule_id=1, date=day, employee_id=employee_id,
        start_time=start, end_time=end,
    )


# ===========================================================================
# Reading a time off a shift
# ===========================================================================

@pytest.mark.parametrize("value,expected", [
    ("09:00", 540), ("00:00", 0), ("23:59", 1439), ("09:05", 545),
])
def test_a_real_time_parses(value, expected):
    assert _minutes(value) == expected


@pytest.mark.parametrize("value", ["9", "nine", "", None, "25:00", "09:99", "-1:00", ":"])
def test_anything_that_is_not_a_time_is_refused(value):
    """
    None rather than a number. "25:00" used to read as 1500 minutes and
    "09:99" as 639 — an hour and a minute that do not exist, accepted
    silently, then reasoned about as if they were real.
    """
    assert _minutes(value) is None


def test_preflight_and_the_scheduler_agree_on_what_a_time_is():
    """
    Two implementations of the same parsing in two files. The scheduler's was
    hardened after a row holding "9" took down a week of generation; this one
    was not, and kept the same bugs afterwards.

    They differ deliberately in what they *return* — the solver falls back to a
    default so one bad row cannot stop a week being built, preflight returns
    None so it can tell an operator. What must not differ is which strings
    count as valid.
    """
    from backend.app.scheduler import parse_time

    sentinel = -12345
    for value in ["09:00", "00:00", "23:59", "9", "", "25:00", "09:99", "-1:00", "nine"]:
        mine = _minutes(value)
        theirs = parse_time(value, sentinel)
        if mine is None:
            assert theirs == sentinel, f"{value!r}: preflight refuses it, the scheduler does not"
        else:
            assert theirs == mine, f"{value!r}: the two disagree on the value"


def test_an_ordinary_shift_is_its_length():
    assert _shift_hours(_bare_shift("09:00", "17:00")) == 8.0


def test_an_overnight_shift_wraps_past_midnight():
    """22:00 to 06:00 is eight hours, not minus sixteen."""
    assert _shift_hours(_bare_shift("22:00", "06:00")) == 8.0


@pytest.mark.parametrize("start,end", [
    ("bad", "bad"), ("", ""), ("9", "17:00"), ("09:00", "25:00"),
])
def test_an_unreadable_shift_is_zero_hours_not_twenty_four(start, end):
    """
    The bug this replaced. An unparseable time became 0, the overnight rule
    then saw end <= start and added a day, and a shift nobody could read
    contributed twenty-four hours of wages and twenty-four staffed hours —
    enough on its own to flip both the cost and the coverage verdict.
    """
    assert _shift_hours(_bare_shift(start, end)) == 0.0


def test_unreadable_shifts_are_listed_rather_than_swallowed():
    """Zero hours is only safe if somebody is told. This is the telling."""
    shifts = [
        _bare_shift("09:00", "17:00"),
        _bare_shift("bad", "17:00"),
        _bare_shift("09:00", "99:99"),
    ]
    assert len(_unreadable_shifts(shifts)) == 2


# ===========================================================================
# A real workspace
# ===========================================================================

@pytest.fixture
def shop(client):
    """A signed-in food-service workspace with a compliance profile."""
    suffix = uuid.uuid4().hex[:6]
    creds = {"username": f"pf{suffix}", "password": "a-test-password-123"}
    with Session(engine) as s:
        user = UserAccount(
            username=creds["username"], password_hash=hash_password(creds["password"]),
            role="manager", active=True,
        )
        s.add(user)
        s.flush()
        business = Business(name=f"Preflight {suffix}", industry="food_service", active=True)
        s.add(business)
        s.flush()
        bid = business.id
        set_current_business_id(bid)
        try:
            seed_business(s, business, user, role="owner")
            s.add(ComplianceProfile(business_id=bid, jurisdiction="federal",
                                    industry="food_service", active=True))
            s.commit()
        finally:
            set_current_business_id(1)

    login = client.post("/auth/login", json=creds)
    assert login.status_code == 200, login.text
    headers = {
        "Authorization": f"Bearer {login.json()['token']}",
        "X-Business-Id": str(bid),
    }
    # Next Monday, so the week is always in the future and never trips the
    # advance-notice rules by accident.
    monday = date.today() + timedelta(days=7 - date.today().weekday())

    yield {"business_id": bid, "headers": headers, "client": client, "monday": monday,
           "suffix": suffix}
    set_current_business_id(1)


def _week(shop, staff=3, days=5, hours=("09:00", "17:00"), rate_cents=1_800):
    """A schedule with `staff` people working `days` days. Returns the id."""
    with Session(engine) as s:
        set_current_business_id(shop["business_id"])
        try:
            schedule = Schedule(business_id=shop["business_id"],
                                week_start=shop["monday"].isoformat(), status="draft")
            s.add(schedule)
            s.flush()
            sid = schedule.id

            for n in range(staff):
                employee = Employee(
                    business_id=shop["business_id"], name=f"Staff {n} {uuid.uuid4().hex[:4]}",
                    department="front", role="employee", active=True,
                )
                s.add(employee)
                s.flush()
                if rate_cents is not None:
                    s.add(EmployeeCompliance(
                        business_id=shop["business_id"], employee_id=employee.id,
                        hourly_rate_cents=rate_cents,
                    ))
                for d in range(days):
                    s.add(ScheduleShift(
                        business_id=shop["business_id"], schedule_id=sid,
                        date=(shop["monday"] + timedelta(days=d)).isoformat(),
                        employee_id=employee.id,
                        start_time=hours[0], end_time=hours[1],
                    ))
            s.commit()
        finally:
            set_current_business_id(1)
    return sid


def _trade(shop, daily_cents=50_000, days=28):
    """Invoice history, which is what the revenue forecast is built from."""
    with Session(engine) as s:
        for d in range(days):
            s.add(Invoice(
                business_id=shop["business_id"], customer_id=0,
                number=f"INV-{shop['suffix']}-{uuid.uuid4().hex[:6]}",
                issue_date=(date.today() - timedelta(days=d)).isoformat(),
                due_date=date.today().isoformat(),
                total_cents=daily_cents, paid_cents=daily_cents, status="paid",
            ))
        s.commit()


def _run(shop, schedule_id):
    response = shop["client"].get(f"/ops/preflight/{schedule_id}", headers=shop["headers"])
    assert response.status_code == 200, response.text
    return response.json()


# ===========================================================================
# The bug: a confident answer from data it does not have
# ===========================================================================

def test_a_week_with_no_wage_data_is_not_cleared_to_publish(shop):
    """
    The headline. Identical schedule, identical staffing, real trade history —
    the only thing missing is anybody's hourly rate. That used to compute as
    0% labor and come back "Clear to publish".
    """
    _trade(shop)
    schedule_id = _week(shop, rate_cents=None)

    report = _run(shop, schedule_id)

    assert report["checks"]["cost"]["status"] == "no_wage_data"
    assert report["verdict"] != "publish", "cleared a week it could not price"


def test_a_missing_wage_is_reported_as_unknown_not_as_zero_percent(shop):
    """
    None and 0.0 are very different claims. One says "I cannot tell you", the
    other says "your labor is free".
    """
    _trade(shop)
    report = _run(shop, _week(shop, rate_cents=None))

    cost = report["checks"]["cost"]
    assert cost["labor_percent"] is None
    assert cost["status"] != "healthy"


def test_the_operator_is_told_which_shifts_have_no_wage(shop):
    _trade(shop)
    report = _run(shop, _week(shop, staff=2, days=5, rate_cents=None))

    assert report["checks"]["cost"]["shifts_without_a_wage"] == 10
    assert any("hourly rate" in note for note in report["advisories"])


def test_one_unpriced_employee_is_enough_to_withhold_the_percentage(shop):
    """
    A partially priced week is not a priced week. Reporting a percentage off
    two thirds of the wage bill is a number that looks authoritative and is
    simply wrong.
    """
    _trade(shop)
    schedule_id = _week(shop, staff=2, rate_cents=1_800)
    with Session(engine) as s:
        set_current_business_id(shop["business_id"])
        try:
            extra = Employee(business_id=shop["business_id"],
                             name=f"Unpriced {uuid.uuid4().hex[:4]}",
                             department="front", role="employee", active=True)
            s.add(extra)
            s.flush()
            s.add(ScheduleShift(
                business_id=shop["business_id"], schedule_id=schedule_id,
                date=shop["monday"].isoformat(), employee_id=extra.id,
                start_time="09:00", end_time="17:00",
            ))
            s.commit()
        finally:
            set_current_business_id(1)

    report = _run(shop, schedule_id)
    assert report["checks"]["cost"]["status"] == "no_wage_data"
    assert report["checks"]["cost"]["labor_percent"] is None


def test_with_wages_entered_the_same_week_gets_a_real_verdict(shop):
    """
    The other half. The fix must not simply refuse to judge everything — a
    priced week still has to get an answer.
    """
    _trade(shop, daily_cents=50_000)
    report = _run(shop, _week(shop, staff=3, days=5, rate_cents=1_800))

    cost = report["checks"]["cost"]
    assert cost["status"] != "no_wage_data"
    assert cost["labor_percent"] is not None
    assert cost["labor_cost"] == 2_160.00, "3 staff x 5 days x 8h x $18"


# ===========================================================================
# Is it affordable
# ===========================================================================

def test_labor_cost_is_hours_times_rate(shop):
    """Two people, three days, eight hours, $20 an hour."""
    schedule_id = _week(shop, staff=2, days=3, rate_cents=2_000)
    with Session(engine) as s:
        shifts = s.exec(
            ScheduleShift.__table__.select().where(
                ScheduleShift.__table__.c.schedule_id == schedule_id
            )
        ).all()
    rows = [ScheduleShift(**dict(r._mapping)) for r in shifts]

    with Session(engine) as s:
        per_day, unpriced = _labor_cost(s, shop["business_id"], rows)

    assert unpriced == 0
    assert sum(per_day.values()) == 2 * 3 * 8 * 2_000


def test_an_expensive_week_is_blocking(shop):
    """Past 40% of forecast revenue the week loses money, and that stops it."""
    _trade(shop, daily_cents=20_000)          # thin trade
    report = _run(shop, _week(shop, staff=3, days=5, rate_cents=2_500))

    assert report["checks"]["cost"]["status"] == "over_budget"
    assert report["verdict"] == "fix"
    assert any("Labor is" in item for item in report["blocking"])


def test_a_comfortable_week_is_healthy(shop):
    """Strong trade, modest roster — nothing to say."""
    _trade(shop, daily_cents=400_000)
    report = _run(shop, _week(shop, staff=1, days=2, rate_cents=1_500))

    assert report["checks"]["cost"]["status"] == "healthy"


def test_a_week_with_no_trade_history_says_so(shop):
    """
    No invoices and no bookings means no forecast. Same principle as the wage
    data: say you cannot tell, rather than inventing a percentage.
    """
    report = _run(shop, _week(shop, staff=1, days=1, rate_cents=1_500))

    assert report["checks"]["cost"]["status"] == "no_forecast"
    assert report["checks"]["cost"]["labor_percent"] is None
    assert any("revenue history" in note for note in report["advisories"])


def test_cost_is_broken_down_by_day(shop):
    """An operator fixes a week by moving one day, so the day is the unit."""
    _trade(shop)
    report = _run(shop, _week(shop, staff=2, days=3, rate_cents=1_800))

    per_day = report["checks"]["cost"]["per_day"]
    assert len(per_day) == 3
    assert all(value == 288.00 for value in per_day.values()), per_day


# ===========================================================================
# Is it staffed
# ===========================================================================

def _book(shop, day, count, minutes=60, price=40.0):
    with Session(engine) as s:
        set_current_business_id(shop["business_id"])
        try:
            service = Service(business_id=shop["business_id"], name="Cut",
                              duration_minutes=minutes, price=price, active=True)
            s.add(service)
            s.flush()
            for _ in range(count):
                s.add(Booking(
                    business_id=shop["business_id"], customer_name="Sam",
                    customer_email="sam@example.com", customer_phone="",
                    service_id=service.id, booking_date=day.isoformat(),
                    booking_time="10:00", duration_minutes=minutes,
                    price=price, status="confirmed",
                ))
            s.commit()
        finally:
            set_current_business_id(1)


def test_a_day_with_more_bookings_than_staff_is_blocking(shop):
    """
    Twenty hour-long appointments against one eight-hour shift. This is the
    check that only works because bookings and rotas are the same system.
    """
    schedule_id = _week(shop, staff=1, days=1, rate_cents=1_500)
    _book(shop, shop["monday"], count=20)

    report = _run(shop, schedule_id)
    coverage = report["checks"]["coverage"][0]

    assert coverage["status"] == "understaffed"
    assert coverage["bookings"] == 20
    assert report["verdict"] == "fix"


def test_a_quiet_day_with_a_full_roster_is_only_an_advisory(shop):
    """Overstaffed costs money; understaffed loses customers. Not the same."""
    schedule_id = _week(shop, staff=3, days=1, rate_cents=1_500)
    _book(shop, shop["monday"], count=1)

    report = _run(shop, schedule_id)
    coverage = report["checks"]["coverage"][0]

    assert coverage["status"] == "possibly_overstaffed"
    assert not any("bookings but too few" in item for item in report["blocking"])


def test_a_day_with_no_bookings_is_not_judged_on_coverage(shop):
    """
    A shop that does not take bookings must not be told every day is
    overstaffed.
    """
    report = _run(shop, _week(shop, staff=2, days=1, rate_cents=1_500))
    assert report["checks"]["coverage"][0]["status"] == "ok"


def test_coverage_counts_the_hours_booked_not_just_the_heads(shop):
    """Ten ten-minute appointments are not ten hours of work."""
    schedule_id = _week(shop, staff=1, days=1, rate_cents=1_500)
    _book(shop, shop["monday"], count=10, minutes=10)

    coverage = _run(shop, schedule_id)["checks"]["coverage"][0]
    assert coverage["booked_hours"] == pytest.approx(1.7, abs=0.1)
    assert coverage["status"] != "understaffed"


def test_a_cancelled_booking_does_not_demand_staff(shop):
    """Only pending and confirmed appointments are work."""
    schedule_id = _week(shop, staff=1, days=1, rate_cents=1_500)
    _book(shop, shop["monday"], count=20)
    with Session(engine) as s:
        set_current_business_id(shop["business_id"])
        try:
            rows = s.exec(
                Booking.__table__.select().where(
                    Booking.__table__.c.business_id == shop["business_id"]
                )
            ).all()
            for row in rows:
                booking = s.get(Booking, row._mapping["id"])
                booking.status = "cancelled"
                s.add(booking)
            s.commit()
        finally:
            set_current_business_id(1)

    coverage = _run(shop, schedule_id)["checks"]["coverage"][0]
    assert coverage["bookings"] == 0
    assert coverage["status"] == "ok"


# ===========================================================================
# Unreadable shifts, end to end
# ===========================================================================

def test_a_week_containing_an_unreadable_shift_is_blocking(shop):
    """
    Every number in the report understates a week it cannot fully read, so the
    report has to say so rather than quietly scoring the shift as nothing.
    """
    _trade(shop)
    schedule_id = _week(shop, staff=1, days=1, rate_cents=1_800)
    with Session(engine) as s:
        set_current_business_id(shop["business_id"])
        try:
            employee = Employee(business_id=shop["business_id"],
                                name=f"Odd {uuid.uuid4().hex[:4]}",
                                department="front", role="employee", active=True)
            s.add(employee)
            s.flush()
            s.add(EmployeeCompliance(business_id=shop["business_id"],
                                     employee_id=employee.id, hourly_rate_cents=1_800))
            s.add(ScheduleShift(
                business_id=shop["business_id"], schedule_id=schedule_id,
                date=shop["monday"].isoformat(), employee_id=employee.id,
                start_time="9", end_time="17:00",
            ))
            s.commit()
        finally:
            set_current_business_id(1)

    report = _run(shop, schedule_id)
    assert report["verdict"] == "fix"
    assert any("cannot be read" in item for item in report["blocking"])


# ===========================================================================
# The verdict itself
# ===========================================================================

def test_a_clean_week_is_cleared(shop):
    """
    The answer has to be reachable, or the check is just an obstacle. Priced
    staff, real trade, a light roster and no bookings to miss.
    """
    _trade(shop, daily_cents=400_000)
    report = _run(shop, _week(shop, staff=1, days=2, rate_cents=1_500))

    assert report["blocking"] == []
    assert report["advisories"] == [], report["advisories"]
    assert report["verdict"] == "publish"
    assert report["headline"] == "Clear to publish"


def test_advisories_alone_ask_for_a_look_not_a_fix(shop):
    _trade(shop)
    report = _run(shop, _week(shop, rate_cents=None))

    assert report["blocking"] == []
    assert report["advisories"]
    assert report["verdict"] == "review"
    assert report["headline"] == "Worth a look, nothing blocking"


def test_the_headline_counts_correctly(shop):
    """"1 thing" rather than "1 things" — it is read on a phone in seconds."""
    _trade(shop, daily_cents=20_000)
    report = _run(shop, _week(shop, staff=3, days=5, rate_cents=2_500))

    count = len(report["blocking"])
    expected = f"{count} thing{'s' if count != 1 else ''} to sort before this goes out"
    assert report["headline"] == expected


def test_the_report_names_the_week_it_judged(shop):
    schedule_id = _week(shop, staff=1, days=1, rate_cents=1_500)
    report = _run(shop, schedule_id)

    assert report["schedule_id"] == schedule_id
    assert report["week_start"] == shop["monday"].isoformat()


def test_all_four_checks_are_always_answered(shop):
    """
    The product thesis is that these four get answered together. A report
    missing one is not the feature.
    """
    report = _run(shop, _week(shop, staff=1, days=1, rate_cents=1_500))
    assert set(report["checks"]) == {"compliance", "coverage", "cost", "stock"}


# ===========================================================================
# The tenant boundary
# ===========================================================================

def test_another_businesss_schedule_is_not_visible(shop):
    """
    Preflight reads wages, revenue and stock. Returning somebody else's would
    leak more in one call than most routes here could.
    """
    suffix = uuid.uuid4().hex[:6]
    with Session(engine) as s:
        user = UserAccount(username=f"other{suffix}", password_hash=hash_password("x" * 12),
                           role="manager", active=True)
        s.add(user)
        s.flush()
        business = Business(name=f"Other {suffix}", industry="general", active=True)
        s.add(business)
        s.flush()
        other_id = business.id
        set_current_business_id(other_id)
        try:
            seed_business(s, business, user, role="owner")
            schedule = Schedule(business_id=other_id,
                                week_start=shop["monday"].isoformat(), status="draft")
            s.add(schedule)
            s.commit()
            s.refresh(schedule)
            their_schedule = schedule.id
        finally:
            set_current_business_id(1)

    response = shop["client"].get(
        f"/ops/preflight/{their_schedule}", headers=shop["headers"]
    )
    assert response.status_code == 404


def test_an_unknown_schedule_is_a_404(shop):
    response = shop["client"].get("/ops/preflight/999999", headers=shop["headers"])
    assert response.status_code == 404


def test_preflight_needs_a_signed_in_user(client):
    assert client.get("/ops/preflight/1").status_code == 401
