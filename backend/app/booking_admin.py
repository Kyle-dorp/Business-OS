"""
Booking management — the operator's side of the booking module.

Services, opening hours, the diary, and no-show handling.

No-show protection is the one place a dedicated booking tool still genuinely
beat this product, and it has two halves. A deposit is what actually stops the
behaviour. Reliability history is what tells an operator *who* to ask for one.
Both are here; neither guesses.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field as PField
from sqlmodel import Session, select

from backend.app.auth import user_from_request
from backend.app.database import get_session
from backend.app.models import (
    Booking,
    BookingAvailability,
    Contact,
    Service,
    UserAccount,
    utc_now_iso,
)
from backend.app.tenancy import current_business_id

log = logging.getLogger(__name__)

router = APIRouter(prefix="/booking-admin", tags=["booking"])

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
OPEN_STATUSES = ("pending", "confirmed")


def _money(cents: int) -> float:
    return round((cents or 0) / 100, 2)


# ------------------------------------------------------------------ services

class ServiceIn(BaseModel):
    name: str = PField(min_length=1, max_length=120)
    description: str = ""
    duration_minutes: int = PField(default=30, ge=5, le=600)
    price: float = PField(default=0, ge=0)
    requires_deposit: bool = False
    deposit: float = PField(default=0, ge=0)
    cancellation_hours: int = PField(default=24, ge=0, le=336)


@router.get("/services")
def list_services(
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    business_id = current_business_id()
    rows = session.exec(
        select(Service).where(Service.business_id == business_id, Service.active == True)  # noqa: E712
    ).all()
    return {
        "services": [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "duration_minutes": s.duration_minutes,
                "price": s.price,
                "requires_deposit": s.requires_deposit,
                "deposit": _money(s.deposit_cents),
                "cancellation_hours": s.cancellation_hours,
            }
            for s in rows
        ]
    }


@router.post("/services")
def create_service(
    body: ServiceIn,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    business_id = current_business_id()

    if body.requires_deposit and body.deposit <= 0:
        raise HTTPException(400, "Set a deposit amount, or turn the deposit off.")
    if body.deposit > body.price and body.price > 0:
        raise HTTPException(400, "A deposit larger than the price will confuse people.")

    service = Service(
        business_id=business_id,
        name=body.name.strip(),
        description=body.description.strip(),
        duration_minutes=body.duration_minutes,
        price=body.price,
        requires_deposit=body.requires_deposit,
        deposit_cents=int(round(body.deposit * 100)),
        cancellation_hours=body.cancellation_hours,
    )
    session.add(service)
    session.commit()
    session.refresh(service)
    return {"id": service.id, "name": service.name}


@router.put("/services/{service_id}")
def update_service(
    service_id: int,
    body: ServiceIn,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    business_id = current_business_id()
    service = session.get(Service, service_id)
    if not service or service.business_id != business_id:
        raise HTTPException(404, "No such service.")

    if body.requires_deposit and body.deposit <= 0:
        raise HTTPException(400, "Set a deposit amount, or turn the deposit off.")

    service.name = body.name.strip()
    service.description = body.description.strip()
    service.duration_minutes = body.duration_minutes
    service.price = body.price
    service.requires_deposit = body.requires_deposit
    service.deposit_cents = int(round(body.deposit * 100))
    service.cancellation_hours = body.cancellation_hours
    session.add(service)
    session.commit()
    return {"saved": True}


@router.delete("/services/{service_id}")
def archive_service(
    service_id: int,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """
    Archived rather than deleted. Bookings reference it, and removing the row
    would leave every past appointment pointing at nothing.
    """
    business_id = current_business_id()
    service = session.get(Service, service_id)
    if not service or service.business_id != business_id:
        raise HTTPException(404, "No such service.")

    upcoming = session.exec(
        select(Booking).where(
            Booking.business_id == business_id,
            Booking.service_id == service_id,
            Booking.booking_date >= date.today().isoformat(),
            Booking.status.in_(OPEN_STATUSES),
        )
    ).all()
    if upcoming:
        raise HTTPException(
            409,
            f"{len(upcoming)} upcoming booking(s) still use this service. "
            "Move or cancel them first.",
        )

    service.active = False
    session.add(service)
    session.commit()
    return {"archived": True}


# -------------------------------------------------------------- availability

class AvailabilityIn(BaseModel):
    day_of_week: int = PField(ge=0, le=6)
    start_time: str
    end_time: str


def _minutes(hhmm: str) -> Optional[int]:
    try:
        h, m = hhmm.split(":")[:2]
        h, m = int(h), int(m)
    except (ValueError, AttributeError):
        return None
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return h * 60 + m


@router.get("/availability")
def list_availability(
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    business_id = current_business_id()
    rows = session.exec(
        select(BookingAvailability).where(
            BookingAvailability.business_id == business_id,
            BookingAvailability.active == True,  # noqa: E712
        )
    ).all()

    by_day: Dict[int, List[dict]] = defaultdict(list)
    for r in rows:
        by_day[r.day_of_week].append(
            {"id": r.id, "start_time": r.start_time, "end_time": r.end_time}
        )

    return {
        "days": [
            {
                "day_of_week": i,
                "name": DAY_NAMES[i],
                "windows": sorted(by_day.get(i, []), key=lambda w: w["start_time"]),
            }
            for i in range(7)
        ],
        "open_days": sorted(by_day.keys()),
    }


@router.post("/availability")
def add_availability(
    body: AvailabilityIn,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    business_id = current_business_id()

    start, end = _minutes(body.start_time), _minutes(body.end_time)
    if start is None or end is None:
        raise HTTPException(400, "Times must be HH:MM.")
    if end <= start:
        raise HTTPException(400, "The closing time has to be after the opening time.")

    # Overlapping windows on one day would generate the same slot twice.
    existing = session.exec(
        select(BookingAvailability).where(
            BookingAvailability.business_id == business_id,
            BookingAvailability.day_of_week == body.day_of_week,
            BookingAvailability.active == True,  # noqa: E712
        )
    ).all()
    for w in existing:
        w_start, w_end = _minutes(w.start_time), _minutes(w.end_time)
        if w_start is None or w_end is None:
            continue
        if start < w_end and end > w_start:
            raise HTTPException(
                409,
                f"That overlaps {DAY_NAMES[body.day_of_week]} "
                f"{w.start_time}–{w.end_time}. Edit that window instead.",
            )

    row = BookingAvailability(
        business_id=business_id,
        day_of_week=body.day_of_week,
        start_time=body.start_time,
        end_time=body.end_time,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"id": row.id}


@router.delete("/availability/{availability_id}")
def remove_availability(
    availability_id: int,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    business_id = current_business_id()
    row = session.get(BookingAvailability, availability_id)
    if not row or row.business_id != business_id:
        raise HTTPException(404, "No such opening window.")
    row.active = False
    session.add(row)
    session.commit()
    return {"removed": True}


# ------------------------------------------------------------------- diary

def _reliability(session: Session, business_id: int, email: str) -> dict:
    """
    A customer's history, by email.

    Counted across the whole workspace rather than per service, because a
    no-show is a fact about the person, not the treatment they booked.
    """
    if not email:
        return {"bookings": 0, "no_shows": 0, "late_cancellations": 0, "rating": "new"}

    rows = session.exec(
        select(Booking).where(
            Booking.business_id == business_id,
            Booking.customer_email == email.lower().strip(),
        )
    ).all()

    total = len(rows)
    no_shows = sum(1 for b in rows if b.no_show_at)
    completed = sum(1 for b in rows if b.status == "completed")

    if total == 0:
        rating = "new"
    elif no_shows == 0:
        rating = "reliable" if completed >= 2 else "new"
    elif no_shows / total >= 0.34:
        rating = "risky"
    else:
        rating = "watch"

    return {
        "bookings": total,
        "completed": completed,
        "no_shows": no_shows,
        "rating": rating,
        # The operator-facing consequence, said plainly rather than implied by
        # a colour. "Risky" means nothing on its own.
        "suggestion": {
            "risky": "Ask for a deposit before confirming.",
            "watch": "One no-show on record.",
            "reliable": "Good history.",
            "new": "First time here.",
        }[rating],
    }


@router.get("/diary")
def diary(
    days: int = 14,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """Upcoming bookings with each customer's history attached."""
    business_id = current_business_id()
    today = date.today()
    until = (today + timedelta(days=days)).isoformat()

    bookings = session.exec(
        select(Booking).where(
            Booking.business_id == business_id,
            Booking.booking_date >= today.isoformat(),
            Booking.booking_date <= until,
        )
    ).all()

    services = {
        s.id: s for s in session.exec(
            select(Service).where(Service.business_id == business_id)
        ).all()
    }

    rows = []
    for b in sorted(bookings, key=lambda x: (x.booking_date, x.booking_time)):
        service = services.get(b.service_id)
        rows.append({
            "id": b.id,
            "date": b.booking_date,
            "time": b.booking_time,
            "duration_minutes": b.duration_minutes,
            "customer_name": b.customer_name,
            "customer_email": b.customer_email,
            "customer_phone": b.customer_phone,
            "service": service.name if service else "Removed service",
            "price": b.price,
            "status": b.status,
            "deposit": _money(b.deposit_cents),
            "deposit_status": b.deposit_status,
            "notes": b.notes,
            "history": _reliability(session, business_id, b.customer_email),
        })

    open_rows = [r for r in rows if r["status"] in OPEN_STATUSES]
    return {
        "bookings": rows,
        "upcoming_count": len(open_rows),
        "committed_revenue": round(sum(r["price"] or 0 for r in open_rows), 2),
        "at_risk": [r for r in open_rows if r["history"]["rating"] == "risky"],
    }


class StatusIn(BaseModel):
    status: str


ALLOWED_TRANSITIONS = {"confirmed", "completed", "cancelled", "no_show"}


@router.put("/bookings/{booking_id}/status")
def set_status(
    booking_id: int,
    body: StatusIn,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """
    Mark a booking confirmed, completed, cancelled or a no-show.

    A no-show writes a timestamp as well as the status, so the history survives
    later edits — somebody rebooking the customer must not erase the record.
    """
    business_id = current_business_id()

    if body.status not in ALLOWED_TRANSITIONS:
        raise HTTPException(400, f"Status must be one of: {', '.join(sorted(ALLOWED_TRANSITIONS))}")

    booking = session.get(Booking, booking_id)
    if not booking or booking.business_id != business_id:
        raise HTTPException(404, "No such booking.")

    booking.status = body.status
    booking.updated_at = utc_now_iso()

    if body.status == "no_show":
        booking.no_show_at = utc_now_iso()
        if booking.deposit_status == "held":
            booking.deposit_status = "forfeited"
    elif body.status == "cancelled":
        booking.cancelled_at = utc_now_iso()
    elif body.status == "completed" and booking.deposit_status == "held":
        booking.deposit_status = "applied"

    session.add(booking)
    session.commit()

    return {
        "saved": True,
        "status": booking.status,
        "deposit_status": booking.deposit_status,
        "history": _reliability(session, business_id, booking.customer_email),
    }


@router.get("/no-shows")
def no_show_report(
    days: int = 90,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """
    What no-shows have cost, and who is responsible.

    The cost of a no-show is the slot, not the deposit — an empty 90-minute
    chair earns nothing, and that is the number worth showing.
    """
    business_id = current_business_id()
    since = (date.today() - timedelta(days=days)).isoformat()

    rows = session.exec(
        select(Booking).where(
            Booking.business_id == business_id,
            Booking.booking_date >= since,
        )
    ).all()

    no_shows = [b for b in rows if b.no_show_at]
    lost_revenue = sum(b.price or 0 for b in no_shows)
    lost_minutes = sum(b.duration_minutes or 0 for b in no_shows)
    recovered = sum(b.deposit_cents for b in no_shows if b.deposit_status == "forfeited")

    by_customer: Dict[str, dict] = {}
    for b in no_shows:
        key = b.customer_email or b.customer_name
        entry = by_customer.setdefault(
            key, {"name": b.customer_name, "email": b.customer_email, "count": 0, "value": 0.0}
        )
        entry["count"] += 1
        entry["value"] += b.price or 0

    completed = [b for b in rows if b.status == "completed"]
    denominator = len(no_shows) + len(completed)

    return {
        "period_days": days,
        "no_show_count": len(no_shows),
        "lost_revenue": round(lost_revenue, 2),
        "lost_hours": round(lost_minutes / 60, 1),
        "deposits_recovered": _money(recovered),
        "no_show_rate": round(len(no_shows) / denominator * 100, 1) if denominator else 0.0,
        "repeat_offenders": sorted(
            [v for v in by_customer.values() if v["count"] > 1],
            key=lambda v: -v["count"],
        ),
    }
