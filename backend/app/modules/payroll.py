"""
Payroll Management Module
Calculates pay, taxes, direct deposit, pay stubs
"""

from sqlmodel import SQLModel, Field
from typing import Optional

class PayrollPeriod(SQLModel, table=True):
    """Pay period definition"""
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    start_date: str
    end_date: str
    status: str = "draft"  # draft, processed, paid
    created_at: str

class EmployeePayroll(SQLModel, table=True):
    """Employee payroll record"""
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    employee_id: int = Field(index=True)
    payroll_period_id: int = Field(index=True)
    hours_worked: float
    hourly_rate: float
    gross_pay: float
    deductions: float
    taxes: float
    net_pay: float
    direct_deposit_account: Optional[str] = None
    status: str = "draft"  # draft, processed, paid

class TaxWithholding(SQLModel, table=True):
    """Tax info per employee"""
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    employee_id: int = Field(index=True)
    federal_withholding: float = 0
    state_withholding: float = 0
    local_withholding: float = 0
    fica_percentage: float = 0.0765

class PayStub(SQLModel, table=True):
    """Generated pay stub"""
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    employee_id: int = Field(index=True)
    payroll_period_id: int = Field(index=True)
    pdf_url: str = ""
    sent_at: Optional[str] = None
