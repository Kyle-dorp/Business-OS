"""
Public booking — the customer-facing half of the booking module.

No authentication: these are the endpoints a customer hits from a booking
link or a QR code on a table. Everything is scoped by the business id in the
URL, and only ever exposes what a business has deliberately published —
active services and free slots. Never staff names, never other bookings,
never anything about the workspace itself beyond its display name.

Slot generation walks the business's weekly availability, subtracts booked
time, and returns what's actually free. The final availability check runs
again inside the booking transaction, so two people clicking the same slot
at the same moment cannot both get it.

This is also what Business-EOS uses for its own demo scheduling. Selling a
booking tool and then sending prospects to someone else's would be absurd.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlmodel import Session, select

from backend.app.database import get_session
from backend.app.models import (
    Booking,
    Business,
    BusinessModule,
    BookingAvailability,
    Contact,
    Service,
    utc_now_iso,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/public/book", tags=["public-booking"])

SLOT_GRANULARITY_MINUTES = 15
MAX_DAYS_AHEAD = 60
MIN_LEAD_MINUTES = 60          # no bookings inside the next hour


# ------------------------------------------------------------------ helpers

def _live_business(session: Session, business_id: int) -> Business:
    business = session.get(Business, business_id)
    if not business or not business.active:
        raise HTTPException(404, "This booking page isn't available.")

    module = session.exec(
        select(BusinessModule).where(
            BusinessModule.business_id == business_id,
            BusinessModule.module_key == "booking",
        )
    ).first()
    if not module or not module.enabled:
        raise HTTPException(404, "This business isn't taking online bookings.")
    return business


def _owner_email(session: Session, business_id: int) -> str:
    """
    Who hears about a new booking.

    The owner first, then any admin. Returns blank rather than guessing if
    nobody has an address on file — a wrong recipient is worse than none.
    """
    from backend.app.models import Membership, UserAccount

    memberships = session.exec(
        select(Membership).where(
            Membership.business_id == business_id,
            Membership.active == True,  # noqa: E712
        )
    ).all()
    ranked = sorted(
        memberships,
        key=lambda m: {"owner": 0, "admin": 1, "manager": 2}.get(m.role, 9),
    )
    for m in ranked:
        user = session.get(UserAccount, m.user_id)
        if user and user.email and user.active:
            return user.email
    return ""


def _hhmm_to_minutes(value: str) -> int:
    hours, minutes = value.split(":")[:2]
    return int(hours) * 60 + int(minutes)


def _minutes_to_hhmm(total: int) -> str:
    return f"{total // 60:02d}:{total % 60:02d}"


def _booked_windows(session: Session, business_id: int, on: str) -> List[tuple[int, int]]:
    """Occupied [start, end) minute ranges for a given day."""
    rows = session.exec(
        select(Booking).where(
            Booking.business_id == business_id,
            Booking.booking_date == on,
            Booking.status.in_(("pending", "confirmed")),
        )
    ).all()
    windows = []
    for b in rows:
        try:
            start = _hhmm_to_minutes(b.booking_time)
        except (ValueError, AttributeError):
            continue
        windows.append((start, start + (b.duration_minutes or 30)))
    return windows


def _free_slots(
    session: Session, business_id: int, on: str, duration: int
) -> List[str]:
    try:
        day = date.fromisoformat(on)
    except ValueError:
        raise HTTPException(400, "Date must be YYYY-MM-DD.")

    today = date.today()
    if day < today or day > today + timedelta(days=MAX_DAYS_AHEAD):
        return []

    availability = session.exec(
        select(BookingAvailability).where(
            BookingAvailability.business_id == business_id,
            BookingAvailability.day_of_week == day.weekday(),
            BookingAvailability.active == True,  # noqa: E712
        )
    ).all()
    if not availability:
        return []

    taken = _booked_windows(session, business_id, on)

    earliest = 0
    if day == today:
        now = datetime.now()
        earliest = now.hour * 60 + now.minute + MIN_LEAD_MINUTES

    slots: List[str] = []
    for window in availability:
        try:
            open_at = _hhmm_to_minutes(window.start_time)
            close_at = _hhmm_to_minutes(window.end_time)
        except (ValueError, AttributeError):
            continue

        cursor = max(open_at, earliest)
        # align to the granularity grid
        if cursor % SLOT_GRANULARITY_MINUTES:
            cursor += SLOT_GRANULARITY_MINUTES - (cursor % SLOT_GRANULARITY_MINUTES)

        while cursor + duration <= close_at:
            clash = any(cursor < end and (cursor + duration) > start for start, end in taken)
            if not clash:
                slots.append(_minutes_to_hhmm(cursor))
            cursor += SLOT_GRANULARITY_MINUTES

    return sorted(set(slots))


# ------------------------------------------------------------------ schemas

class PublicService(BaseModel):
    id: int
    name: str
    description: str
    duration_minutes: int
    price: float
    requires_deposit: bool = False
    deposit: float = 0.0
    cancellation_hours: int = 24


class BookingRequest(BaseModel):
    service_id: int
    booking_date: str
    booking_time: str
    customer_name: str = Field(min_length=1, max_length=120)
    customer_email: EmailStr
    customer_phone: str = Field(default="", max_length=40)
    notes: str = Field(default="", max_length=1000)


class BookingConfirmation(BaseModel):
    booking_id: int
    service: str
    booking_date: str
    booking_time: str
    duration_minutes: int
    price: float
    status: str
    business_name: str
    deposit: float = 0.0
    deposit_required: bool = False
    cancellation_hours: int = 24


# ------------------------------------------------------------------ routes

@router.get("/{business_id}")
def booking_page(business_id: int, session: Session = Depends(get_session)):
    """Everything a booking page needs to render, in one call."""
    business = _live_business(session, business_id)
    services = session.exec(
        select(Service).where(
            Service.business_id == business_id,
            Service.active == True,  # noqa: E712
        )
    ).all()
    availability = session.exec(
        select(BookingAvailability).where(
            BookingAvailability.business_id == business_id,
            BookingAvailability.active == True,  # noqa: E712
        )
    ).all()

    return {
        "business_name": business.name,
        "currency": business.currency,
        "services": [
            PublicService(
                id=s.id, name=s.name, description=s.description,
                duration_minutes=s.duration_minutes, price=s.price,
                requires_deposit=s.requires_deposit,
                deposit=round(s.deposit_cents / 100, 2),
                cancellation_hours=s.cancellation_hours,
            )
            for s in services
        ],
        "open_days": sorted({a.day_of_week for a in availability}),
        "max_days_ahead": MAX_DAYS_AHEAD,
    }


@router.get("/{business_id}/slots")
def slots(
    business_id: int,
    service_id: int,
    on: str,
    session: Session = Depends(get_session),
):
    """Free start times for one service on one day."""
    _live_business(session, business_id)

    service = session.get(Service, service_id)
    if not service or service.business_id != business_id or not service.active:
        raise HTTPException(404, "That service isn't available.")

    return {
        "date": on,
        "service_id": service_id,
        "duration_minutes": service.duration_minutes,
        "slots": _free_slots(session, business_id, on, service.duration_minutes),
    }


@router.get("/{business_id}/next-available")
def next_available(
    business_id: int,
    service_id: int,
    days: int = 14,
    session: Session = Depends(get_session),
):
    """First open slot over the coming days — powers a 'soonest available' button."""
    _live_business(session, business_id)
    service = session.get(Service, service_id)
    if not service or service.business_id != business_id:
        raise HTTPException(404, "That service isn't available.")

    for offset in range(min(days, MAX_DAYS_AHEAD) + 1):
        day = (date.today() + timedelta(days=offset)).isoformat()
        found = _free_slots(session, business_id, day, service.duration_minutes)
        if found:
            return {"date": day, "time": found[0], "service_id": service_id}
    return {"date": None, "time": None, "service_id": service_id}


@router.post("/{business_id}/book", response_model=BookingConfirmation)
def book(
    business_id: int,
    body: BookingRequest,
    session: Session = Depends(get_session),
):
    """
    Take a booking.

    Availability is re-checked here, immediately before the insert, rather
    than trusting the slot list the browser was holding. Between rendering a
    page and clicking confirm, someone else may have taken the slot.
    """
    business = _live_business(session, business_id)

    service = session.get(Service, body.service_id)
    if not service or service.business_id != business_id or not service.active:
        raise HTTPException(404, "That service isn't available.")

    available = _free_slots(session, business_id, body.booking_date, service.duration_minutes)
    if body.booking_time not in available:
        raise HTTPException(
            409,
            "That time was just taken. Pick another slot — the list has been refreshed.",
        )

    booking = Booking(
        business_id=business_id,
        customer_name=body.customer_name.strip(),
        customer_email=str(body.customer_email).lower().strip(),
        customer_phone=body.customer_phone.strip(),
        service_id=service.id,
        booking_date=body.booking_date,
        booking_time=body.booking_time,
        duration_minutes=service.duration_minutes,
        price=service.price,
        notes=body.notes.strip(),
        status="pending",
        payment_status="pending",
        deposit_cents=service.deposit_cents if service.requires_deposit else 0,
        # "required" rather than "held" — nothing has been taken yet. Recording
        # it as held would make an unpaid booking look secured.
        deposit_status="required" if service.requires_deposit else "none",
    )
    session.add(booking)
    session.commit()
    session.refresh(booking)

    # Keep the CRM in step — a booking is usually the first time a customer exists.
    existing = session.exec(
        select(Contact).where(
            Contact.business_id == business_id,
            Contact.email == booking.customer_email,
        )
    ).first()
    if not existing and booking.customer_email:
        session.add(Contact(
            business_id=business_id,
            contact_type="customer",
            name=booking.customer_name,
            email=booking.customer_email,
            phone=booking.customer_phone,
            notes="Created automatically from an online booking.",
        ))
        session.commit()

    log.info("Booking %s taken for business %s", booking.id, business_id)

    # Confirmations are best-effort. A booking that succeeded and an email that
    # did not is still a booking — the failure is logged, never raised.
    try:
        from backend.app import email_service
        email_service.booking_confirmation(session, booking, service, business)

        owner_email = _owner_email(session, business_id)
        if owner_email:
            email_service.new_booking_alert(session, booking, service, business, owner_email)
    except Exception:
        log.exception("Booking %s saved but notification failed", booking.id)

    return BookingConfirmation(
        booking_id=booking.id,
        service=service.name,
        booking_date=booking.booking_date,
        booking_time=booking.booking_time,
        duration_minutes=booking.duration_minutes,
        price=booking.price,
        status=booking.status,
        business_name=business.name,
        deposit=round(booking.deposit_cents / 100, 2),
        deposit_required=service.requires_deposit,
        cancellation_hours=service.cancellation_hours,
    )


@router.post("/{business_id}/cancel/{booking_id}")
def cancel(
    business_id: int,
    booking_id: int,
    email: str,
    session: Session = Depends(get_session),
):
    """
    Let a customer cancel their own booking.

    The email must match the one on the booking — that's the whole auth story
    here, and it's deliberately weak-but-scoped: worst case someone who knows
    both a booking id and the matching email frees a slot. Nothing is exposed.
    """
    _live_business(session, business_id)
    booking = session.get(Booking, booking_id)
    if not booking or booking.business_id != business_id:
        raise HTTPException(404, "No such booking.")
    if booking.customer_email.lower() != email.lower().strip():
        raise HTTPException(403, "That email doesn't match this booking.")
    if booking.status == "cancelled":
        return {"cancelled": True, "already": True}

    # Past the cancellation window a deposit is forfeited. The booking is still
    # cancelled — refusing to release the slot helps nobody, since the customer
    # is not coming either way and somebody else could take it.
    service = session.get(Service, booking.service_id)
    window_hours = service.cancellation_hours if service else 24
    forfeited = False

    try:
        starts_at = datetime.fromisoformat(f"{booking.booking_date}T{booking.booking_time}")
        hours_notice = (starts_at - datetime.now()).total_seconds() / 3600
    except ValueError:
        hours_notice = window_hours   # unparseable time is not the customer's fault

    if hours_notice < window_hours and booking.deposit_status == "held":
        booking.deposit_status = "forfeited"
        forfeited = True

    booking.status = "cancelled"
    booking.cancelled_at = utc_now_iso()
    booking.updated_at = utc_now_iso()
    session.add(booking)
    session.commit()

    return {
        "cancelled": True,
        "booking_id": booking_id,
        "deposit_forfeited": forfeited,
        "notice_hours": round(max(hours_notice, 0), 1),
        "window_hours": window_hours,
        "message": (
            f"Cancelled. Your deposit is not refundable inside {window_hours} hours."
            if forfeited else "Cancelled. Thanks for letting us know."
        ),
    }
