"""
Invoicing & Billing Module
Generate invoices, track payments, manage billing
"""

from sqlmodel import SQLModel, Field
from typing import Optional

class Invoice(SQLModel, table=True):
    """Invoice document"""
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    customer_id: int = Field(index=True)
    invoice_number: str = Field(unique=True, index=True)
    issue_date: str
    due_date: str
    total_amount: float
    paid_amount: float = 0
    status: str = "draft"  # draft, sent, paid, overdue, cancelled
    payment_terms: str = "Net 30"
    created_at: str

class InvoiceLineItem(SQLModel, table=True):
    """Line items in invoice"""
    id: Optional[int] = Field(default=None, primary_key=True)
    invoice_id: int = Field(index=True)
    description: str
    quantity: float
    unit_price: float
    tax_rate: float = 0
    total: float

class Payment(SQLModel, table=True):
    """Payment record"""
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    invoice_id: int = Field(index=True)
    amount: float
    payment_method: str  # "credit_card", "bank_transfer", "cash", "check"
    reference_id: str = ""
    received_date: str
    created_at: str

class RecurringBilling(SQLModel, table=True):
    """Recurring invoice setup"""
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    customer_id: int = Field(index=True)
    frequency: str  # "weekly", "monthly", "quarterly", "yearly"
    amount: float
    next_invoice_date: str
    active: bool = True
