"""
Inventory Management Module
Tracks stock, reorders, costs, and multi-location inventory

Note: InventoryItem is defined in backend.app.models to avoid duplication
"""

from sqlmodel import SQLModel, Field
from typing import Optional

class InventoryTransaction(SQLModel, table=True):
    """Track inventory changes"""
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    item_id: int = Field(index=True)
    transaction_type: str  # "purchase", "sale", "return", "adjustment", "reorder"
    quantity_change: int
    notes: str = ""
    created_at: str = Field(index=True)

class Supplier(SQLModel, table=True):
    """Supplier information"""
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    name: str
    contact_email: str = ""
    contact_phone: str = ""
    address: str = ""
    reorder_lead_time: int = 0  # days
    active: bool = True
