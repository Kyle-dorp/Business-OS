"""
Booking & Scheduling Module
Handles appointments, services, and customer bookings with Stripe integration
"""

from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class Service(SQLModel, table=True):
    """Service offered (haircut, grooming, etc.)"""
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    name: str
    description: str = ""
    duration_minutes: int = 30
    price: float
    stripe_price_id: Optional[str] = None  # Stripe Price ID
    active: bool = True

class Booking(SQLModel, table=True):
    """Customer booking/appointment"""
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    customer_name: str
    customer_email: str
    customer_phone: str
    service_id: int = Field(index=True)
    booking_date: str  # ISO format date
    booking_time: str  # HH:MM format
    duration_minutes: int
    status: str = "pending"  # pending, confirmed, completed, cancelled
    notes: str = ""
    price: float
    payment_status: str = "pending"  # pending, completed, failed
    stripe_payment_intent_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class BookingAvailability(SQLModel, table=True):
    """Business availability for bookings"""
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    day_of_week: int  # 0=Monday, 6=Sunday
    start_time: str  # HH:MM
    end_time: str    # HH:MM
    active: bool = True
