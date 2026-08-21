"""
Customer Management & CRM Module
Track customers, preferences, loyalty, communication history
"""

from sqlmodel import SQLModel, Field
from typing import Optional

class Customer(SQLModel, table=True):
    """Customer record"""
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    first_name: str
    last_name: str
    email: str = Field(index=True)
    phone: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    company_name: Optional[str] = None
    customer_type: str = "individual"  # individual, business, vip
    created_at: str

class CustomerPreferences(SQLModel, table=True):
    """Customer preferences & notes"""
    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(index=True)
    preferred_service: Optional[str] = None
    preferred_staff_member: Optional[int] = None
    allergies_or_restrictions: str = ""
    notes: str = ""
    tags: str = ""  # comma-separated tags

class PurchaseHistory(SQLModel, table=True):
    """Customer purchase/appointment record"""
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    customer_id: int = Field(index=True)
    transaction_type: str  # "appointment", "purchase", "payment"
    amount: float = 0
    description: str
    date: str = Field(index=True)

class LoyaltyAccount(SQLModel, table=True):
    """Loyalty/rewards program"""
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    customer_id: int = Field(index=True)
    points_balance: float = 0
    lifetime_spent: float = 0
    tier: str = "bronze"  # bronze, silver, gold, platinum
    last_activity: str

class CommunicationLog(SQLModel, table=True):
    """Track all customer communications"""
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    customer_id: int = Field(index=True)
    communication_type: str  # "email", "sms", "call", "in_person", "note"
    subject: str
    message: str
    sent_by: str  # staff member or system
    timestamp: str = Field(index=True)
