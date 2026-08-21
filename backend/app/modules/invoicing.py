"""
Invoicing & Billing Module
Generate invoices, track payments, manage billing

Note: Invoice and Payment are defined in backend.app.models to avoid duplication
"""

from sqlmodel import SQLModel, Field
from typing import Optional

class InvoiceLineItem(SQLModel, table=True):
    """Line items in invoice"""
    id: Optional[int] = Field(default=None, primary_key=True)
    invoice_id: int = Field(index=True)
    description: str
    quantity: float
    unit_price: float
    tax_rate: float = 0
    total: float


class RecurringBilling(SQLModel, table=True):
    """Recurring invoice setup"""
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    customer_id: int = Field(index=True)
    frequency: str  # "weekly", "monthly", "quarterly", "yearly"
    amount: float
    next_invoice_date: str
    active: bool = True
