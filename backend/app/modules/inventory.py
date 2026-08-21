"""
Inventory Management Module
Tracks stock, reorders, costs, and multi-location inventory
"""

from sqlmodel import SQLModel, Field
from typing import Optional

class InventoryItem(SQLModel, table=True):
    """Product/item in inventory"""
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    location_id: Optional[int] = Field(index=True)  # null = all locations
    name: str
    sku: str = Field(unique=True, index=True)
    category: str
    quantity: int = 0
    reorder_level: int = 10
    reorder_quantity: int = 50
    unit_cost: float
    unit_price: float
    supplier_id: Optional[int] = None
    active: bool = True

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
