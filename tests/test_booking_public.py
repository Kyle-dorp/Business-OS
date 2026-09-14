"""
The public booking endpoints.

These are the only routes an unauthenticated stranger can reach, which makes
them the highest-risk surface in the product. Three things are worth proving
rather than assuming:

  1. Two people cannot take the same slot. The availability list a browser is
     holding goes stale the moment somebody else books, so the check has to
     happen inside the request, not before it.
  2. Nothing leaks. These endpoints must expose published services and free
     times, and nothing else about the workspace.
  3. A booking page that is not set up 404s rather than rendering empty.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlmodel import Session, select

from backend.app.database import engine
from backend.app.models import (
    Booking,
    BookingAvailability,
    Business,
    BusinessModule,
    Service,
)


def _next_weekday(weekday: int) -> str:
    """The next date falling on `weekday` (0=Monday), never today."""
    today = date.today()
    ahead = (weekday - today.weekday()) % 7 or 7
    return (today + timedelta(days=ahead)).isoformat()


@pytest.fixture(scope="module")
def shop(client_module):
    """
    A business with one bookable service and one open day.

    Built directly in the database: this module is testing the public
    endpoints, not the admin ones, and going through the UI path would make a
    failure here ambiguous about which half broke.
    """
    with Session(engine) as s:
        business = Business(name=f"Test Salon {uuid.uuid4().hex[:6]}", industry="general", active=True)
        s.add(business)
        s.flush()
        bid = business.id

        s.add(BusinessModule(business_id=bid, module_key="booking", enabled=True))
        service = Service(
            business_id=bid, name="Haircut", description="A trim",
            duration_minutes=60, price=40.0, active=True,
        )
        s.add(service)
        # Open 09:00-17:00 every day, so the test never depends on the weekday
        # it happens to run on.
        for day in range(7):
            s.add(BookingAvailability(
                business_id=bid, day_of_week=day,
                start_time="09:00", end_time="17:00", active=True,
            ))
        s.commit()
        s.refresh(service)
        return {"business_id": bid, "service_id": service.id, "client": client_module}


@pytest.fixture(scope="module")
def client_module():
    from fastapi.testclient import TestClient
    from backend.app.main import app

    with TestClient(app) as c:
        yield c


# ------------------------------------------------------------------ the page

def test_booking_page_returns_published_services(shop):
    r = shop["client"].get(f"/public/book/{shop['business_id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["business_name"]
    assert any(s["name"] == "Haircut" for s in body["services"])


def test_booking_page_needs_no_authentication(shop):
    """A customer is not a user. A bearer token must not be required."""
    r = shop["client"].get(f"/public/book/{shop['business_id']}")
    assert r.status_code != 401


def test_unknown_business_is_not_found(shop):
    assert shop["client"].get("/public/book/999999").status_code == 404


def test_business_with_no_services_is_not_found(shop):
    """
    A page with nothing on it looks broken rather than unconfigured, so it
    should not exist at all.
    """
    with Session(engine) as s:
        bare = Business(name="Bare Co", industry="general", active=True)
        s.add(bare)
        s.flush()
        s.add(BusinessModule(business_id=bare.id, module_key="booking", enabled=True))
        s.commit()
        bare_id = bare.id

    assert shop["client"].get(f"/public/book/{bare_id}").status_code == 404


def test_page_exposes_nothing_beyond_what_was_published(shop):
    """
    The response should carry the business name, its services and its open
    days. Staff, other bookings, revenue and internal ids must not appear.
    """
    body = shop["client"].get(f"/public/book/{shop['business_id']}").json()
    allowed = {"business_name", "currency", "services", "open_days", "max_days_ahead"}
    assert set(body) <= allowed, f"unexpected fields: {set(body) - allowed}"

    service_fields = set(body["services"][0])
    forbidden = {"business_id", "stripe_price_id", "deposit_cents"}
    assert not (service_fields & forbidden), f"leaked: {service_fields & forbidden}"


# --------------------------------------------------------------------- slots

def test_slots_are_offered_inside_opening_hours(shop):
    on = _next_weekday(date.today().weekday())
    r = shop["client"].get(
        f"/public/book/{shop['business_id']}/slots",
        params={"service_id": shop["service_id"], "on": on},
    )
    assert r.status_code == 200
    slots = r.json()["slots"]
    assert slots, "no slots offered on an open day"
    # A 60-minute service inside 09:00-17:00 cannot start at or after 16:00.
    assert all("09:00" <= t <= "16:00" for t in slots), f"slot outside hours: {slots}"


def test_no_slots_offered_in_the_past(shop):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    r = shop["client"].get(
        f"/public/book/{shop['business_id']}/slots",
        params={"service_id": shop["service_id"], "on": yesterday},
    )
    assert r.json()["slots"] == []


def test_malformed_date_is_rejected(shop):
    r = shop["client"].get(
        f"/public/book/{shop['business_id']}/slots",
        params={"service_id": shop["service_id"], "on": "not-a-date"},
    )
    assert r.status_code == 400


def test_service_from_another_business_is_not_bookable(shop):
    """Passing someone else's service id must not cross the tenant boundary."""
    with Session(engine) as s:
        other = Business(name="Other Co", industry="general", active=True)
        s.add(other)
        s.flush()
        foreign = Service(business_id=other.id, name="Massage", duration_minutes=30,
                          price=50.0, active=True)
        s.add(foreign)
        s.commit()
        s.refresh(foreign)
        foreign_id = foreign.id

    r = shop["client"].get(
        f"/public/book/{shop['business_id']}/slots",
        params={"service_id": foreign_id, "on": _next_weekday(2)},
    )
    assert r.status_code == 404


# ------------------------------------------------------------------ booking

def _book(shop, when, at, email=None):
    return shop["client"].post(
        f"/public/book/{shop['business_id']}/book",
        json={
            "service_id": shop["service_id"],
            "booking_date": when,
            "booking_time": at,
            "customer_name": "Sam Taylor",
            "customer_email": email or f"sam{uuid.uuid4().hex[:6]}@example.com",
            "customer_phone": "555-0100",
            "notes": "",
        },
    )


def test_a_booking_can_be_made(shop):
    on = _next_weekday(3)
    slots = shop["client"].get(
        f"/public/book/{shop['business_id']}/slots",
        params={"service_id": shop["service_id"], "on": on},
    ).json()["slots"]

    r = _book(shop, on, slots[0])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["booking_id"]
    assert body["booking_time"] == slots[0]


def test_the_same_slot_cannot_be_taken_twice(shop):
    """
    The race this is guarding. Two customers holding the same slot list, both
    clicking confirm — only one can win, and the loser must be told plainly
    rather than silently double-booked.
    """
    on = _next_weekday(4)
    slots = shop["client"].get(
        f"/public/book/{shop['business_id']}/slots",
        params={"service_id": shop["service_id"], "on": on},
    ).json()["slots"]
    contested = slots[0]

    first = _book(shop, on, contested)
    assert first.status_code == 200

    second = _book(shop, on, contested)
    assert second.status_code == 409, "a second booking took an occupied slot"
    assert "taken" in second.json()["detail"].lower()


def test_a_booked_slot_disappears_from_availability(shop):
    on = _next_weekday(5)
    before = shop["client"].get(
        f"/public/book/{shop['business_id']}/slots",
        params={"service_id": shop["service_id"], "on": on},
    ).json()["slots"]

    _book(shop, on, before[0])

    after = shop["client"].get(
        f"/public/book/{shop['business_id']}/slots",
        params={"service_id": shop["service_id"], "on": on},
    ).json()["slots"]

    assert before[0] not in after


def test_an_overlapping_slot_is_also_blocked(shop):
    """
    A 60-minute booking at 10:00 occupies 10:15 and 10:30 as start times too.
    Blocking only the exact start would let a second customer book into the
    middle of the first appointment.
    """
    on = _next_weekday(6)
    slots = shop["client"].get(
        f"/public/book/{shop['business_id']}/slots",
        params={"service_id": shop["service_id"], "on": on},
    ).json()["slots"]

    assert _book(shop, on, slots[0]).status_code == 200

    after = shop["client"].get(
        f"/public/book/{shop['business_id']}/slots",
        params={"service_id": shop["service_id"], "on": on},
    ).json()["slots"]

    # slots[1] and slots[2] start 15 and 30 minutes into a 60-minute booking.
    assert slots[1] not in after
    assert slots[2] not in after


def test_booking_a_time_that_was_never_offered_is_refused(shop):
    """03:00 is outside opening hours and must not be bookable by direct POST."""
    r = _book(shop, _next_weekday(1), "03:00")
    assert r.status_code == 409


def test_invalid_email_is_rejected(shop):
    r = shop["client"].post(
        f"/public/book/{shop['business_id']}/book",
        json={
            "service_id": shop["service_id"],
            "booking_date": _next_weekday(1),
            "booking_time": "11:00",
            "customer_name": "Sam",
            "customer_email": "not-an-email",
        },
    )
    assert r.status_code == 422


def test_a_booking_creates_a_crm_contact(shop):
    """Modules sharing a database is the product thesis; this is it in miniature."""
    from backend.app.models import Contact

    on = _next_weekday(2)
    slots = shop["client"].get(
        f"/public/book/{shop['business_id']}/slots",
        params={"service_id": shop["service_id"], "on": on},
    ).json()["slots"]

    email = f"newcustomer{uuid.uuid4().hex[:6]}@example.com"
    assert _book(shop, on, slots[-1], email=email).status_code == 200

    with Session(engine) as s:
        contacts = s.exec(
            select(Contact).execution_options(include_all_businesses=True)
        ).all()
    assert any(c.email == email and c.business_id == shop["business_id"] for c in contacts)


# ---------------------------------------------------------------- cancelling

def test_a_customer_can_cancel_with_their_own_email(shop):
    on = _next_weekday(1)
    slots = shop["client"].get(
        f"/public/book/{shop['business_id']}/slots",
        params={"service_id": shop["service_id"], "on": on},
    ).json()["slots"]

    email = f"canceller{uuid.uuid4().hex[:6]}@example.com"
    booking_id = _book(shop, on, slots[0], email=email).json()["booking_id"]

    r = shop["client"].post(
        f"/public/book/{shop['business_id']}/cancel/{booking_id}",
        params={"email": email},
    )
    assert r.status_code == 200
    assert r.json()["cancelled"] is True


def test_cancelling_with_the_wrong_email_is_refused(shop):
    """
    Weak auth, deliberately — but it must at least stop somebody cancelling
    another person's appointment by guessing an id.
    """
    on = _next_weekday(1)
    slots = shop["client"].get(
        f"/public/book/{shop['business_id']}/slots",
        params={"service_id": shop["service_id"], "on": on},
    ).json()["slots"]

    booking_id = _book(shop, on, slots[1], email="owner@example.com").json()["booking_id"]

    r = shop["client"].post(
        f"/public/book/{shop['business_id']}/cancel/{booking_id}",
        params={"email": "attacker@example.com"},
    )
    assert r.status_code == 403


def test_cancelling_frees_the_slot_again(shop):
    on = _next_weekday(0)
    slots = shop["client"].get(
        f"/public/book/{shop['business_id']}/slots",
        params={"service_id": shop["service_id"], "on": on},
    ).json()["slots"]

    email = f"freeing{uuid.uuid4().hex[:6]}@example.com"
    slot = slots[0]
    booking_id = _book(shop, on, slot, email=email).json()["booking_id"]

    shop["client"].post(
        f"/public/book/{shop['business_id']}/cancel/{booking_id}",
        params={"email": email},
    )

    after = shop["client"].get(
        f"/public/book/{shop['business_id']}/slots",
        params={"service_id": shop["service_id"], "on": on},
    ).json()["slots"]
    assert slot in after, "a cancelled slot was not released"
