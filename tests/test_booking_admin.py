"""
The operator's side of bookings.

Two things here decide real money. Customer reliability is what tells somebody
whether to ask for a deposit, and the no-show report is what says whether
deposits are worth having at all. A wrong rating either accuses a good customer
or lets a repeat offender book a ninety-minute slot for free.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlmodel import Session

from backend.app.booking_admin import DAY_NAMES, _minutes, _reliability
from backend.app.database import engine
from backend.app.models import Booking, Business, Service, utc_now_iso
from backend.app.tenancy import reset_current_business_id, set_current_business_id


@pytest.fixture
def diary():
    suffix = uuid.uuid4().hex[:6]
    with Session(engine) as s:
        business = Business(name=f"Diary Co {suffix}", industry="general", active=True)
        s.add(business)
        s.flush()
        bid = business.id
        service = Service(
            business_id=bid, name="Cut", duration_minutes=60, price=40.0, active=True
        )
        s.add(service)
        s.commit()
        s.refresh(service)
        sid = service.id

    # Booking is tenant-scoped: without this, every query in these tests is
    # filtered to business 1 and silently returns nothing. In the running app
    # the auth middleware sets this per request.
    token = set_current_business_id(bid)
    yield {"business_id": bid, "service_id": sid}
    reset_current_business_id(token)


def _booking(diary, email, status="completed", no_show=False, price=40.0, when=None):
    with Session(engine) as s:
        b = Booking(
            business_id=diary["business_id"],
            customer_name="Sam", customer_email=email, customer_phone="",
            service_id=diary["service_id"],
            booking_date=when or date.today().isoformat(),
            booking_time="10:00", duration_minutes=60,
            price=price, status=status,
            no_show_at=utc_now_iso() if no_show else None,
        )
        s.add(b)
        s.commit()
        s.refresh(b)
        return b.id


def _rate(diary, email):
    with Session(engine) as s:
        return _reliability(s, diary["business_id"], email)


# ------------------------------------------------------------- time parsing

@pytest.mark.parametrize("value,expected", [("09:00", 540), ("00:00", 0), ("23:59", 1439)])
def test_valid_opening_times_parse(value, expected):
    assert _minutes(value) == expected


@pytest.mark.parametrize("value", ["9", "nine", "", None, "25:00", "09:99", "-1:00"])
def test_invalid_opening_times_are_rejected(value):
    """
    Returning None rather than a number is what lets the caller refuse the row.
    Silently accepting "25:00" would publish a slot at an hour that does not
    exist.
    """
    assert _minutes(value) is None


def test_every_weekday_has_a_name():
    assert len(DAY_NAMES) == 7
    assert DAY_NAMES[0] == "Monday"
    assert DAY_NAMES[6] == "Sunday"


# -------------------------------------------------------------- reliability

def test_an_unknown_customer_is_new():
    with Session(engine) as s:
        assert _reliability(s, 1, "")["rating"] == "new"


def test_a_first_time_customer_is_not_treated_as_risky(diary):
    """
    Somebody with no history is new, not suspect. Asking a first-time customer
    for a deposit on no evidence is a good way to lose them.
    """
    email = f"first{uuid.uuid4().hex[:6]}@example.com"
    _booking(diary, email, status="pending")
    assert _rate(diary, email)["rating"] == "new"


def test_a_customer_who_keeps_turning_up_becomes_reliable(diary):
    email = f"good{uuid.uuid4().hex[:6]}@example.com"
    for _ in range(3):
        _booking(diary, email, status="completed")

    history = _rate(diary, email)
    assert history["rating"] == "reliable"
    assert history["no_shows"] == 0
    assert "Good history" in history["suggestion"]


def test_one_no_show_is_watched_rather_than_condemned(diary):
    """
    One missed appointment out of several is a bad day, not a pattern. Flagging
    it as risky would have an operator demanding a deposit over one occasion.
    """
    email = f"once{uuid.uuid4().hex[:6]}@example.com"
    for _ in range(4):
        _booking(diary, email, status="completed")
    _booking(diary, email, status="no_show", no_show=True)

    history = _rate(diary, email)
    assert history["rating"] == "watch"
    assert history["no_shows"] == 1


def test_a_repeat_offender_is_flagged_risky(diary):
    """A third of appointments missed is a pattern, and the suggestion says so."""
    email = f"bad{uuid.uuid4().hex[:6]}@example.com"
    _booking(diary, email, status="completed")
    _booking(diary, email, status="no_show", no_show=True)
    _booking(diary, email, status="no_show", no_show=True)

    history = _rate(diary, email)
    assert history["rating"] == "risky"
    assert "deposit" in history["suggestion"].lower()


def test_history_is_matched_case_insensitively(diary):
    """
    Somebody booking as Sam@Example.com and later sam@example.com is one
    person, and splitting their history would hide a no-show.
    """
    email = f"Case{uuid.uuid4().hex[:6]}@Example.COM"
    _booking(diary, email.lower(), status="no_show", no_show=True)
    _booking(diary, email.lower(), status="no_show", no_show=True)
    _booking(diary, email.lower(), status="completed")

    assert _rate(diary, email.upper())["no_shows"] == 2


def test_a_no_show_counts_even_after_the_booking_is_reused(diary):
    """
    no_show_at is a timestamp rather than only a status, so rebooking the same
    customer later cannot quietly erase the record.
    """
    email = f"stamp{uuid.uuid4().hex[:6]}@example.com"
    booking_id = _booking(diary, email, status="no_show", no_show=True)

    with Session(engine) as s:
        b = s.get(Booking, booking_id)
        b.status = "confirmed"          # somebody rebooks them
        s.add(b)
        s.commit()

    assert _rate(diary, email)["no_shows"] == 1, "the record was erased by a status change"


def test_one_businesss_history_does_not_follow_a_customer_elsewhere(diary):
    """
    Reliability is per workspace. A customer who let one salon down has no
    record at the next, which is both correct and the only defensible position.
    """
    email = f"shared{uuid.uuid4().hex[:6]}@example.com"
    _booking(diary, email, status="no_show", no_show=True)
    _booking(diary, email, status="no_show", no_show=True)

    with Session(engine) as s:
        other = Business(name="Elsewhere", industry="general", active=True)
        s.add(other)
        s.commit()
        s.refresh(other)
        other_id = other.id

    with Session(engine) as s:
        elsewhere = _reliability(s, other_id, email)
    assert elsewhere["rating"] == "new"
    assert elsewhere["no_shows"] == 0
