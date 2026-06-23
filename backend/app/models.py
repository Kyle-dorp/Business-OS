from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel
from backend.app.tenancy import current_business_id


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Employee(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(default_factory=current_business_id, index=True)
    name: str
    department: str
    role: str = "employee"  # employee, shift_lead, gm
    min_hours_per_week: int = 0
    max_hours_per_week: int = 40
    # Legacy only. Role-based pay is used instead.
    hourly_rate_override: Optional[float] = None
    active: bool = True


class Position(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(default_factory=current_business_id, index=True)
    name: str
    department: str
    active: bool = True


class Department(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(default_factory=current_business_id, index=True)
    name: str = Field(index=True)
    active: bool = True


class EmployeePosition(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(default_factory=current_business_id, index=True)
    employee_id: int = Field(index=True)
    position_id: int = Field(index=True)
    trainee: bool = False
    preferred: bool = False


class RecurringAvailability(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(default_factory=current_business_id, index=True)
    employee_id: int = Field(index=True)
    rule_type: str  # unavailable or preferred
    day_of_week: int = -1  # -1 any day, 0 Monday - 6 Sunday
    start_time: str = ""
    end_time: str = ""


class TemporaryUnavailability(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(default_factory=current_business_id, index=True)
    employee_id: int = Field(index=True)
    start_date: str
    end_date: str
    start_time: str = ""
    end_time: str = ""


class ManagerSettings(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(default_factory=current_business_id, index=True)
    store_name: str = "Business"
    employee_hourly_rate: float = 18.20
    shift_lead_hourly_rate: float = 19.20
    gm_hourly_rate: float = 19.20
    # Legacy single target, kept for compatibility.
    default_labor_percent: float = 19.0
    min_labor_percent: float = 18.0
    max_labor_percent: float = 20.0
    schedule_extra_with_trainee: bool = True
    store_open_time: str = "10:30"
    store_close_time: str = "21:00"


class LaborProjection(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(default_factory=current_business_id, index=True)
    date: str = Field(index=True)  # YYYY-MM-DD
    start_time: str = ""  # blank means whole day
    end_time: str = ""
    projected_sales: Optional[float] = None
    # Legacy single percent. New UI stores a range.
    labor_percent: Optional[float] = None
    min_labor_percent: Optional[float] = None
    max_labor_percent: Optional[float] = None
    max_labor_hours: Optional[float] = None
    max_labor_dollars: Optional[float] = None
    note: str = ""  # legacy only; no longer shown in the UI


class CoverageRule(SQLModel, table=True):
    """A staffing-demand rule shown to users as a Projected Crew target."""

    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(default_factory=current_business_id, index=True)
    name: str
    # A specific date wins over day_of_week. Blank date means recurring.
    date: str = ""
    day_of_week: int = -1  # -1 every day
    start_time: str
    end_time: str

    # Legacy single-target fields.
    target_type: str = "multi"
    position_id: Optional[int] = None
    department: Optional[str] = None
    role: Optional[str] = None

    # JSON arrays stored as text for portable SQLite.
    position_ids_json: str = "[]"
    departments_json: str = "[]"
    roles_json: str = "[]"

    minimum_count: int = 1
    preferred_count: int = 1
    hard_minimum: bool = True
    active: bool = True


class Schedule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(default_factory=current_business_id, index=True)
    week_start: str = Field(index=True)
    version: int = 1
    status: str = "draft"  # draft, needs_review, published
    created_at: str = Field(default_factory=utc_now_iso)
    source_schedule_id: Optional[int] = None
    generation_scope: str = "full_week"
    labor_tolerance_percent: float = 0.0
    staffing_level: str = "balanced"  # lean, balanced, full


class ScheduleShift(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(default_factory=current_business_id, index=True)
    schedule_id: int = Field(index=True)
    date: str = Field(index=True)
    employee_id: int
    position_id: Optional[int] = None
    role: str = "employee"
    start_time: str
    end_time: str
    locked: bool = False
    source_rule_id: Optional[int] = None


class ScheduleWarning(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(default_factory=current_business_id, index=True)
    schedule_id: int = Field(index=True)
    date: str = ""
    severity: str = "warning"  # info, warning, error
    code: str
    message: str
    shift_id: Optional[int] = None


class AssistantMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(default_factory=current_business_id, index=True)
    user_id: Optional[int] = Field(default=None, index=True)
    thread_id: Optional[int] = Field(default=None, index=True)
    role: str
    content: str
    actions_json: str = "[]"
    applied: bool = False
    created_at: str = Field(default_factory=utc_now_iso)


class UserAccount(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True)
    password_hash: str
    role: str = "employee"  # manager or employee
    employee_id: Optional[int] = Field(default=None, index=True)
    active: bool = True
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)


class AvailabilityRequest(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(default_factory=current_business_id, index=True)
    user_id: int = Field(index=True)
    employee_id: int = Field(index=True)
    request_type: str = "day_off"  # day_off, recurring_change, temporary_change
    title: str = ""
    start_date: str = ""
    end_date: str = ""
    day_of_week: int = -1
    start_time: str = ""
    end_time: str = ""
    rule_type: str = "unavailable"
    reason: str = ""
    status: str = "pending"  # pending, approved, denied
    manager_note: str = ""
    created_at: str = Field(default_factory=utc_now_iso)
    reviewed_at: str = ""
    reviewed_by_user_id: Optional[int] = None


class AssistantThread(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(default_factory=current_business_id, index=True)
    user_id: int = Field(index=True)
    title: str = "Scheduling setup"
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)


class AssistantMemory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(default_factory=current_business_id, index=True)
    user_id: int = Field(index=True)
    content: str = ""
    updated_at: str = Field(default_factory=utc_now_iso)


# Multi-business platform ---------------------------------------------------


class Business(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    legal_name: str = ""
    industry: str = "general"
    currency: str = "USD"
    fiscal_year_start_month: int = 1
    active: bool = True
    created_at: str = Field(default_factory=utc_now_iso)


class Location(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    name: str
    address: str = ""
    timezone: str = "America/Denver"
    active: bool = True


class Membership(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    user_id: int = Field(index=True)
    role: str = "employee"  # owner, admin, manager, accountant, employee
    active: bool = True
    created_at: str = Field(default_factory=utc_now_iso)


class BusinessModule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    module_key: str = Field(index=True)
    enabled: bool = True


class Contact(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    contact_type: str = "customer"  # customer, vendor, both
    name: str = Field(index=True)
    company_name: str = ""
    email: str = ""
    phone: str = ""
    billing_address: str = ""
    tax_id: str = ""
    notes: str = ""
    active: bool = True
    created_at: str = Field(default_factory=utc_now_iso)


class LedgerAccount(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    code: str = Field(index=True)
    name: str
    account_type: str  # asset, liability, equity, income, expense
    subtype: str = ""
    active: bool = True
    system: bool = False


class JournalEntry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    entry_date: str = Field(index=True)
    memo: str = ""
    source_type: str = "manual"
    source_id: Optional[int] = Field(default=None, index=True)
    status: str = "posted"  # draft, posted, void
    created_by_user_id: int = Field(index=True)
    created_at: str = Field(default_factory=utc_now_iso)


class JournalLine(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    journal_entry_id: int = Field(index=True)
    account_id: int = Field(index=True)
    description: str = ""
    debit_cents: int = 0
    credit_cents: int = 0


class Invoice(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    customer_id: int = Field(index=True)
    number: str = Field(index=True)
    issue_date: str
    due_date: str
    status: str = "draft"  # draft, sent, partial, paid, void, overdue
    notes: str = ""
    subtotal_cents: int = 0
    tax_cents: int = 0
    total_cents: int = 0
    paid_cents: int = 0
    created_at: str = Field(default_factory=utc_now_iso)


class InvoiceLine(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    invoice_id: int = Field(index=True)
    description: str
    quantity_milli: int = 1000
    unit_price_cents: int = 0
    tax_rate_basis_points: int = 0
    line_total_cents: int = 0


class Bill(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    vendor_id: int = Field(index=True)
    number: str = ""
    bill_date: str
    due_date: str
    status: str = "draft"
    notes: str = ""
    subtotal_cents: int = 0
    tax_cents: int = 0
    total_cents: int = 0
    paid_cents: int = 0
    created_at: str = Field(default_factory=utc_now_iso)


class BillLine(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    bill_id: int = Field(index=True)
    account_id: int = Field(index=True)
    description: str
    quantity_milli: int = 1000
    unit_cost_cents: int = 0
    line_total_cents: int = 0


class Payment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    direction: str  # received, paid
    payment_date: str
    amount_cents: int
    contact_id: Optional[int] = Field(default=None, index=True)
    invoice_id: Optional[int] = Field(default=None, index=True)
    bill_id: Optional[int] = Field(default=None, index=True)
    account_id: int = Field(index=True)
    reference: str = ""
    created_at: str = Field(default_factory=utc_now_iso)


class Expense(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    location_id: Optional[int] = Field(default=None, index=True)
    expense_date: str = Field(index=True)
    vendor_id: Optional[int] = Field(default=None, index=True)
    account_id: int = Field(index=True)
    payment_account_id: int = Field(index=True)
    amount_cents: int
    description: str = ""
    reference: str = ""
    created_at: str = Field(default_factory=utc_now_iso)


class TaskItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    location_id: Optional[int] = Field(default=None, index=True)
    title: str
    description: str = ""
    status: str = "todo"
    priority: str = "normal"
    due_date: str = ""
    assigned_user_id: Optional[int] = Field(default=None, index=True)
    created_by_user_id: int = Field(index=True)
    created_at: str = Field(default_factory=utc_now_iso)


class ChecklistTemplate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    name: str
    description: str = ""
    items_json: str = "[]"
    category: str = "general"
    active: bool = True
    created_at: str = Field(default_factory=utc_now_iso)


class ChecklistRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    template_id: int = Field(index=True)
    run_date: str = Field(index=True)
    status: str = "open"
    items_json: str = "[]"
    notes: str = ""
    created_by_user_id: int = Field(index=True)
    completed_by_user_id: Optional[int] = Field(default=None, index=True)
    created_at: str = Field(default_factory=utc_now_iso)
    completed_at: str = ""


class ClosingReport(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    location_id: Optional[int] = Field(default=None, index=True)
    report_date: str = Field(index=True)
    sales_cents: int = 0
    cash_expected_cents: int = 0
    cash_actual_cents: int = 0
    labor_cost_cents: int = 0
    waste_cents: int = 0
    issues: str = ""
    notes: str = ""
    submitted_by_user_id: int = Field(index=True)
    created_at: str = Field(default_factory=utc_now_iso)


class InventoryItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    location_id: Optional[int] = Field(default=None, index=True)
    sku: str = Field(index=True)
    name: str
    item_type: str = "inventory"  # inventory, supply, asset, service
    unit: str = "each"
    quantity_milli: int = 0
    reorder_level_milli: int = 0
    unit_cost_cents: int = 0
    sales_price_cents: int = 0
    active: bool = True


class InventoryMovement(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    item_id: int = Field(index=True)
    movement_date: str = Field(index=True)
    quantity_milli: int
    reason: str = "adjustment"
    reference: str = ""
    created_by_user_id: int = Field(index=True)
    created_at: str = Field(default_factory=utc_now_iso)


class AuditEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    user_id: int = Field(index=True)
    action: str = Field(index=True)
    entity_type: str = ""
    entity_id: Optional[int] = None
    detail_json: str = "{}"
    created_at: str = Field(default_factory=utc_now_iso)
