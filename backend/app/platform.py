from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from backend.app.auth import user_from_request
from backend.app.database import get_session
from backend.app.models import (
    AuditEvent, Bill, BillLine, Business, BusinessModule, ChecklistRun,
    ChecklistTemplate, ClosingReport, Contact, Department, Expense,
    InventoryItem, InventoryMovement, Invoice, InvoiceLine, JournalEntry,
    JournalLine, LedgerAccount, Location, ManagerSettings, Membership, Payment,
    Position, TaskItem, UIConfig, UserAccount,
)

router = APIRouter(prefix="/platform", tags=["business platform"])

MODULES = [
    "home", "team", "scheduling", "accounting", "sales", "purchasing",
    "tasks", "inventory", "reports", "assistant", "notifications", "settings",
]

PRESETS = {
    "food_service": {
        "label": "Food service", "description": "Restaurants, cafés, catering, and kitchens.",
        "departments": ["Front of House", "Back of House", "Management"],
        "modules": set(MODULES),
        "checklist": ["Lock entrances", "Count cash drawer", "Record waste", "Clean equipment", "Check refrigeration", "Set alarm"],
    },
    "warehouse": {
        "label": "Warehouse", "description": "Receiving, storage, picking, shipping, and office work.",
        "departments": ["Receiving", "Warehouse", "Shipping", "Office"],
        "modules": {"home", "team", "scheduling", "accounting", "purchasing", "tasks", "inventory", "reports", "assistant", "notifications", "settings"},
        "checklist": ["Secure loading doors", "Park equipment", "Verify outbound loads", "Record damaged stock", "Clear aisles", "Set alarm"],
    },
    "construction": {
        "label": "Construction / service", "description": "Crews, jobs, equipment, materials, and project costs.",
        "departments": ["Field Crews", "Project Management", "Office"],
        "modules": {"home", "team", "scheduling", "accounting", "sales", "purchasing", "tasks", "inventory", "reports", "assistant", "notifications", "settings"},
        "checklist": ["Secure tools and equipment", "Record site progress", "Log incidents", "Confirm tomorrow's crew", "Upload site notes"],
    },
    "retail": {
        "label": "Retail", "description": "Stores with sales floors, stockrooms, and cash close.",
        "departments": ["Sales Floor", "Stockroom", "Management"],
        "modules": set(MODULES),
        "checklist": ["Count cash drawers", "Reconcile sales", "Face shelves", "Secure high-value items", "Lock doors", "Set alarm"],
    },
    "office": {
        "label": "Office / professional", "description": "Client work, administration, billing, and projects.",
        "departments": ["Client Services", "Operations", "Administration"],
        "modules": {"home", "team", "accounting", "sales", "purchasing", "tasks", "reports", "assistant", "notifications", "settings"},
        "checklist": ["Review unfinished work", "Confirm tomorrow's appointments", "Secure sensitive files", "Record daily notes"],
    },
    "custom": {
        "label": "Custom", "description": "Start neutral and choose every tool yourself.",
        "departments": ["General"], "modules": {"home", "assistant", "settings"},
        "checklist": ["Review unfinished work", "Record issues", "Secure the workplace"],
    },
}
WRITE_ROLES = {"owner", "admin", "manager", "accountant"}
ADMIN_ROLES = {"owner", "admin"}

DEFAULT_ACCOUNTS = [
    # Assets
    ("1000", "Operating Bank", "asset", "cash"),
    ("1010", "Cash Drawer", "asset", "cash_drawer"),
    ("1100", "Accounts Receivable", "asset", "accounts_receivable"),
    ("1200", "Inventory", "asset", "inventory"),
    ("1500", "Equipment", "asset", "fixed_asset"),
    # Liabilities
    ("2000", "Accounts Payable", "liability", "accounts_payable"),
    ("2100", "Credit Card", "liability", "credit_card"),
    ("2200", "Sales Tax Payable", "liability", "sales_tax"),
    # Equity
    ("3000", "Owner Equity", "equity", "owner_equity"),
    ("3100", "Retained Earnings", "equity", "retained_earnings"),
    # Income
    ("4000", "Sales Revenue", "income", "sales"),
    ("4100", "Service Revenue", "income", "services"),
    ("4200", "Catering Revenue", "income", "catering"),
    # Cost of goods
    ("5000", "Cost of Goods Sold", "expense", "cost_of_goods_sold"),
    ("5100", "Food Cost - Proteins", "expense", "food_cost_protein"),
    ("5200", "Food Cost - Bread & Bakery", "expense", "food_cost_bread"),
    ("5300", "Food Cost - Produce & Dairy", "expense", "food_cost_produce"),
    ("5400", "Paper & Packaging", "expense", "food_cost_packaging"),
    ("5500", "Food Cost - Beverages", "expense", "food_cost_beverage"),
    # Operating expenses
    ("6000", "Payroll Expense", "expense", "payroll"),
    ("6100", "Rent Expense", "expense", "rent"),
    ("6200", "Utilities Expense", "expense", "utilities"),
    ("6300", "Supplies Expense", "expense", "supplies"),
    ("6400", "Card Processing Fees", "expense", "card_fees"),
    ("6500", "Marketing & Advertising", "expense", "marketing"),
    ("6600", "Insurance", "expense", "insurance"),
    ("6700", "Repairs & Maintenance", "expense", "repairs"),
    ("6900", "Other Expense", "expense", "other"),
]

FOOD_COST_SUBTYPES = frozenset({
    "cost_of_goods_sold", "food_cost_protein", "food_cost_bread",
    "food_cost_produce", "food_cost_packaging", "food_cost_beverage",
})


class BusinessCreate(BaseModel):
    name: str
    legal_name: str = ""
    industry: str = "general"
    location_name: str = "Main location"


class ContactPayload(BaseModel):
    contact_type: Literal["customer", "vendor", "both"] = "customer"
    name: str
    company_name: str = ""
    email: str = ""
    phone: str = ""
    billing_address: str = ""
    tax_id: str = ""
    notes: str = ""


class LinePayload(BaseModel):
    description: str
    quantity: float = 1
    unit_price: float = 0
    tax_rate: float = 0
    account_id: Optional[int] = None


class InvoicePayload(BaseModel):
    customer_id: int
    issue_date: str = Field(default_factory=lambda: date.today().isoformat())
    due_date: str
    notes: str = ""
    lines: list[LinePayload]


class BillPayload(BaseModel):
    vendor_id: int
    number: str = ""
    bill_date: str = Field(default_factory=lambda: date.today().isoformat())
    due_date: str
    notes: str = ""
    lines: list[LinePayload]


class PaymentPayload(BaseModel):
    amount: float
    payment_date: str = Field(default_factory=lambda: date.today().isoformat())
    account_id: int
    reference: str = ""


class ExpensePayload(BaseModel):
    expense_date: str = Field(default_factory=lambda: date.today().isoformat())
    vendor_id: Optional[int] = None
    account_id: int
    payment_account_id: int
    amount: float
    description: str = ""
    reference: str = ""
    location_id: Optional[int] = None


class JournalLinePayload(BaseModel):
    account_id: int
    description: str = ""
    debit: float = 0
    credit: float = 0


class JournalPayload(BaseModel):
    entry_date: str = Field(default_factory=lambda: date.today().isoformat())
    memo: str = ""
    lines: list[JournalLinePayload]


class TaskPayload(BaseModel):
    title: str
    description: str = ""
    status: str = "todo"
    priority: str = "normal"
    due_date: str = ""
    assigned_user_id: Optional[int] = None
    location_id: Optional[int] = None


class InventoryPayload(BaseModel):
    sku: str
    name: str
    item_type: str = "inventory"
    unit: str = "each"
    quantity: float = 0
    reorder_level: float = 0
    unit_cost: float = 0
    sales_price: float = 0
    location_id: Optional[int] = None


class InventoryAdjustPayload(BaseModel):
    quantity_change: float
    reason: str = "adjustment"
    reference: str = ""


class ModuleUpdate(BaseModel):
    enabled: bool


class ChecklistPayload(BaseModel):
    name: str
    description: str = ""
    items: list[str]
    category: str = "general"


class ChecklistRunPayload(BaseModel):
    template_id: int
    run_date: str = Field(default_factory=lambda: date.today().isoformat())


class ChecklistRunUpdate(BaseModel):
    items: list[dict]
    notes: str = ""
    complete: bool = False


class ClosingReportPayload(BaseModel):
    report_date: str = Field(default_factory=lambda: date.today().isoformat())
    location_id: Optional[int] = None
    sales: float = 0
    card_sales: float = 0
    sales_tax: float = 0
    cash_expected: float = 0
    cash_actual: float = 0
    labor_cost: float = 0
    waste: float = 0
    issues: str = ""
    notes: str = ""


class ClosingReportPostPayload(BaseModel):
    bank_account_id: int


class PresetRecommendationPayload(BaseModel):
    description: str


class SalesTaxRemitPayload(BaseModel):
    amount: float
    period: str  # e.g. "Q2 2025"
    bank_account_id: int


class UIConfigPatch(BaseModel):
    patch: dict = {}


def cents(amount: float) -> int:
    return round(amount * 100)


def current_user(request: Request) -> UserAccount:
    return user_from_request(request)


def _membership(session: Session, user_id: int, business_id: int) -> Membership:
    membership = session.exec(select(Membership).where(
        Membership.user_id == user_id,
        Membership.business_id == business_id,
        Membership.active == True,  # noqa: E712
    )).first()
    if not membership:
        raise HTTPException(403, "You do not have access to this business")
    return membership


def business_context(
    user: UserAccount = Depends(current_user),
    session: Session = Depends(get_session),
    x_business_id: Optional[int] = Header(default=None),
) -> tuple[int, Membership, UserAccount]:
    memberships = session.exec(select(Membership).where(
        Membership.user_id == user.id, Membership.active == True  # noqa: E712
    )).all()
    if not memberships:
        raise HTTPException(409, "Create a business workspace first")
    business_id = x_business_id or memberships[0].business_id
    return business_id, _membership(session, user.id, business_id), user


def require_write(context=Depends(business_context)):
    if context[1].role not in WRITE_ROLES:
        raise HTTPException(403, "This role has view-only access")
    return context


def audit(session: Session, business_id: int, user_id: int, action: str,
          entity_type: str = "", entity_id: Optional[int] = None, detail: Optional[dict] = None):
    session.add(AuditEvent(
        business_id=business_id, user_id=user_id, action=action,
        entity_type=entity_type, entity_id=entity_id,
        detail_json=json.dumps(detail or {}, default=str),
    ))


def seed_business(session: Session, business: Business, user: UserAccount, role: str = "owner"):
    session.add(Membership(business_id=business.id, user_id=user.id, role=role))
    session.add(Location(business_id=business.id, name="Main location"))
    for module in MODULES:
        session.add(BusinessModule(business_id=business.id, module_key=module, enabled=True))
    for code, name, account_type, subtype in DEFAULT_ACCOUNTS:
        session.add(LedgerAccount(
            business_id=business.id, code=code, name=name, account_type=account_type,
            subtype=subtype, system=True,
        ))
    settings = session.exec(select(ManagerSettings).where(
        ManagerSettings.business_id == business.id
    ).execution_options(include_all_businesses=True)).first()
    if not settings:
        session.add(ManagerSettings(business_id=business.id, store_name=business.name))
    departments = session.exec(select(Department).where(
        Department.business_id == business.id
    ).execution_options(include_all_businesses=True)).first()
    if not departments:
        session.add(Department(business_id=business.id, name="General"))


def account_by_subtype(session: Session, business_id: int, subtype: str) -> LedgerAccount:
    account = session.exec(select(LedgerAccount).where(
        LedgerAccount.business_id == business_id, LedgerAccount.subtype == subtype
    )).first()
    if not account:
        raise HTTPException(409, f"Missing required ledger account: {subtype}")
    return account


def post_entry(session: Session, business_id: int, user_id: int, entry_date: str,
               memo: str, source_type: str, source_id: Optional[int], lines: list[dict]):
    if not lines or sum(x["debit_cents"] for x in lines) != sum(x["credit_cents"] for x in lines):
        raise HTTPException(400, "Journal entry debits and credits must balance")
    if sum(x["debit_cents"] for x in lines) <= 0:
        raise HTTPException(400, "Journal entry amount must be greater than zero")
    valid_ids = set(session.exec(select(LedgerAccount.id).where(
        LedgerAccount.business_id == business_id, LedgerAccount.active == True  # noqa: E712
    )).all())
    if any(line["account_id"] not in valid_ids for line in lines):
        raise HTTPException(400, "Journal entry contains an invalid account")
    entry = JournalEntry(
        business_id=business_id, entry_date=entry_date, memo=memo,
        source_type=source_type, source_id=source_id, created_by_user_id=user_id,
    )
    session.add(entry)
    session.flush()
    for line in lines:
        session.add(JournalLine(business_id=business_id, journal_entry_id=entry.id, **line))
    return entry


@router.post("/bootstrap")
def bootstrap(user=Depends(current_user), session: Session = Depends(get_session)):
    existing = session.exec(select(Membership).where(Membership.user_id == user.id)).first()
    if not existing:
        business = Business(name="My Business", industry="general")
        session.add(business)
        session.flush()
        seed_business(session, business, user)
        for existing_user in session.exec(select(UserAccount).where(UserAccount.id != user.id)).all():
            session.add(Membership(
                business_id=business.id, user_id=existing_user.id,
                role="manager" if existing_user.role == "manager" else "employee",
            ))
        audit(session, business.id, user.id, "business.bootstrap", "business", business.id)
        session.commit()
    return list_businesses(user, session)


@router.get("/businesses")
def list_businesses(user=Depends(current_user), session: Session = Depends(get_session)):
    memberships = session.exec(select(Membership).where(
        Membership.user_id == user.id, Membership.active == True  # noqa: E712
    )).all()
    result = []
    for membership in memberships:
        business = session.get(Business, membership.business_id)
        if business and business.active:
            result.append({"business": business, "role": membership.role})
    return result


@router.post("/businesses")
def create_business(payload: BusinessCreate, user=Depends(current_user), session: Session = Depends(get_session)):
    if not payload.name.strip():
        raise HTTPException(400, "Business name is required")
    business = Business(name=payload.name.strip(), legal_name=payload.legal_name.strip(), industry=payload.industry)
    session.add(business)
    session.flush()
    seed_business(session, business, user)
    location = session.exec(select(Location).where(Location.business_id == business.id)).first()
    location.name = payload.location_name.strip() or "Main location"
    audit(session, business.id, user.id, "business.create", "business", business.id)
    session.commit()
    session.refresh(business)
    return business


@router.get("/workspace")
def workspace(context=Depends(business_context), session: Session = Depends(get_session)):
    business_id, membership, user = context
    return {
        "business": session.get(Business, business_id), "role": membership.role,
        "locations": session.exec(select(Location).where(Location.business_id == business_id)).all(),
        "modules": session.exec(select(BusinessModule).where(BusinessModule.business_id == business_id)).all(),
        "user": {"id": user.id, "username": user.username},
    }


@router.put("/modules/{module_key}")
def update_module(module_key: str, payload: ModuleUpdate, context=Depends(require_write), session: Session = Depends(get_session)):
    business_id, membership, user = context
    if membership.role not in ADMIN_ROLES:
        raise HTTPException(403, "Owner or admin access required")
    if module_key not in MODULES:
        raise HTTPException(404, "Unknown module")
    if module_key in {"home", "settings"} and not payload.enabled:
        raise HTTPException(400, "Overview and Settings always stay available")
    record = session.exec(select(BusinessModule).where(
        BusinessModule.business_id == business_id, BusinessModule.module_key == module_key
    )).first()
    if not record:
        record = BusinessModule(business_id=business_id, module_key=module_key)
    record.enabled = payload.enabled
    session.add(record)
    audit(session, business_id, user.id, "module.update", "business_module", record.id, {"module": module_key, "enabled": payload.enabled})
    session.commit(); session.refresh(record)
    return record


@router.get("/dashboard")
def dashboard(context=Depends(business_context), session: Session = Depends(get_session)):
    business_id = context[0]
    invoices = session.exec(select(Invoice).where(Invoice.business_id == business_id, Invoice.status != "void")).all()
    bills = session.exec(select(Bill).where(Bill.business_id == business_id, Bill.status != "void")).all()
    tasks = session.exec(select(TaskItem).where(TaskItem.business_id == business_id)).all()
    items = session.exec(select(InventoryItem).where(InventoryItem.business_id == business_id, InventoryItem.active == True)).all()  # noqa: E712
    return {
        "receivables_cents": sum(max(0, x.total_cents - x.paid_cents) for x in invoices),
        "payables_cents": sum(max(0, x.total_cents - x.paid_cents) for x in bills),
        "open_invoices": sum(x.status not in {"paid", "void"} for x in invoices),
        "open_bills": sum(x.status not in {"paid", "void"} for x in bills),
        "open_tasks": sum(x.status not in {"done", "cancelled"} for x in tasks),
        "low_stock_items": sum(x.quantity_milli <= x.reorder_level_milli for x in items),
    }


@router.get("/contacts")
def contacts(contact_type: Optional[str] = None, context=Depends(business_context), session: Session = Depends(get_session)):
    statement = select(Contact).where(Contact.business_id == context[0], Contact.active == True)  # noqa: E712
    records = session.exec(statement).all()
    return [x for x in records if not contact_type or x.contact_type in {contact_type, "both"}]


@router.post("/contacts")
def create_contact(payload: ContactPayload, context=Depends(require_write), session: Session = Depends(get_session)):
    business_id, _, user = context
    contact = Contact(business_id=business_id, **payload.model_dump())
    session.add(contact); session.flush()
    audit(session, business_id, user.id, "contact.create", "contact", contact.id)
    session.commit(); session.refresh(contact)
    return contact


@router.get("/accounts")
def accounts(context=Depends(business_context), session: Session = Depends(get_session)):
    return session.exec(select(LedgerAccount).where(
        LedgerAccount.business_id == context[0], LedgerAccount.active == True  # noqa: E712
    ).order_by(LedgerAccount.code)).all()


@router.get("/invoices")
def invoices(context=Depends(business_context), session: Session = Depends(get_session)):
    return session.exec(select(Invoice).where(Invoice.business_id == context[0]).order_by(Invoice.id.desc())).all()


@router.post("/invoices")
def create_invoice(payload: InvoicePayload, context=Depends(require_write), session: Session = Depends(get_session)):
    business_id, _, user = context
    customer = session.get(Contact, payload.customer_id)
    if not customer or customer.business_id != business_id or customer.contact_type not in {"customer", "both"}:
        raise HTTPException(400, "Invalid customer")
    if not payload.lines:
        raise HTTPException(400, "Add at least one invoice line")
    line_values = []
    for line in payload.lines:
        base = round(line.quantity * line.unit_price * 100)
        tax = round(base * line.tax_rate / 100)
        line_values.append((line, base, tax))
    subtotal = sum(x[1] for x in line_values); tax_total = sum(x[2] for x in line_values)
    count = len(session.exec(select(Invoice.id).where(Invoice.business_id == business_id)).all()) + 1
    invoice = Invoice(
        business_id=business_id, customer_id=payload.customer_id, number=f"INV-{count:05d}",
        issue_date=payload.issue_date, due_date=payload.due_date, notes=payload.notes,
        subtotal_cents=subtotal, tax_cents=tax_total, total_cents=subtotal + tax_total,
    )
    session.add(invoice); session.flush()
    for line, base, tax in line_values:
        session.add(InvoiceLine(
            business_id=business_id, invoice_id=invoice.id, description=line.description,
            quantity_milli=round(line.quantity * 1000), unit_price_cents=cents(line.unit_price),
            tax_rate_basis_points=round(line.tax_rate * 100), line_total_cents=base + tax,
        ))
    audit(session, business_id, user.id, "invoice.create", "invoice", invoice.id)
    session.commit(); session.refresh(invoice)
    return invoice


@router.post("/invoices/{invoice_id}/post")
def post_invoice(invoice_id: int, context=Depends(require_write), session: Session = Depends(get_session)):
    business_id, _, user = context
    invoice = session.get(Invoice, invoice_id)
    if not invoice or invoice.business_id != business_id: raise HTTPException(404, "Invoice not found")
    if invoice.status != "draft": raise HTTPException(409, "Only draft invoices can be posted")
    ar = account_by_subtype(session, business_id, "accounts_receivable")
    revenue = account_by_subtype(session, business_id, "sales")
    tax_account = session.exec(select(LedgerAccount).where(
        LedgerAccount.business_id == business_id, LedgerAccount.subtype == "sales_tax",
        LedgerAccount.active == True,  # noqa: E712
    )).first()
    if tax_account and invoice.tax_cents > 0:
        lines = [
            {"account_id": ar.id, "description": invoice.number, "debit_cents": invoice.total_cents, "credit_cents": 0},
            {"account_id": revenue.id, "description": invoice.number, "debit_cents": 0, "credit_cents": invoice.subtotal_cents},
            {"account_id": tax_account.id, "description": "Sales tax collected", "debit_cents": 0, "credit_cents": invoice.tax_cents},
        ]
    else:
        lines = [
            {"account_id": ar.id, "description": invoice.number, "debit_cents": invoice.total_cents, "credit_cents": 0},
            {"account_id": revenue.id, "description": invoice.number, "debit_cents": 0, "credit_cents": invoice.total_cents},
        ]
    post_entry(session, business_id, user.id, invoice.issue_date, f"Invoice {invoice.number}", "invoice", invoice.id, lines)
    invoice.status = "sent"; audit(session, business_id, user.id, "invoice.post", "invoice", invoice.id)
    session.commit(); session.refresh(invoice)
    return invoice


@router.post("/invoices/{invoice_id}/payments")
def receive_payment(invoice_id: int, payload: PaymentPayload, context=Depends(require_write), session: Session = Depends(get_session)):
    business_id, _, user = context
    invoice = session.get(Invoice, invoice_id)
    if not invoice or invoice.business_id != business_id: raise HTTPException(404, "Invoice not found")
    amount = cents(payload.amount)
    if amount <= 0 or amount > invoice.total_cents - invoice.paid_cents: raise HTTPException(400, "Invalid payment amount")
    bank = session.get(LedgerAccount, payload.account_id)
    if not bank or bank.business_id != business_id: raise HTTPException(400, "Invalid payment account")
    ar = account_by_subtype(session, business_id, "accounts_receivable")
    payment = Payment(business_id=business_id, direction="received", payment_date=payload.payment_date,
        amount_cents=amount, contact_id=invoice.customer_id, invoice_id=invoice.id,
        account_id=bank.id, reference=payload.reference)
    session.add(payment); session.flush()
    post_entry(session, business_id, user.id, payload.payment_date, f"Payment for {invoice.number}", "payment", payment.id, [
        {"account_id": bank.id, "description": payload.reference, "debit_cents": amount, "credit_cents": 0},
        {"account_id": ar.id, "description": invoice.number, "debit_cents": 0, "credit_cents": amount},
    ])
    invoice.paid_cents += amount; invoice.status = "paid" if invoice.paid_cents == invoice.total_cents else "partial"
    audit(session, business_id, user.id, "payment.receive", "payment", payment.id)
    session.commit(); return payment


@router.get("/bills")
def bills(context=Depends(business_context), session: Session = Depends(get_session)):
    return session.exec(select(Bill).where(Bill.business_id == context[0]).order_by(Bill.id.desc())).all()


@router.post("/bills")
def create_bill(payload: BillPayload, context=Depends(require_write), session: Session = Depends(get_session)):
    business_id, _, user = context
    vendor = session.get(Contact, payload.vendor_id)
    if not vendor or vendor.business_id != business_id or vendor.contact_type not in {"vendor", "both"}: raise HTTPException(400, "Invalid vendor")
    if not payload.lines: raise HTTPException(400, "Add at least one bill line")
    lines = []
    for line in payload.lines:
        account = session.get(LedgerAccount, line.account_id) if line.account_id else None
        if not account or account.business_id != business_id: raise HTTPException(400, "Every bill line needs a valid expense account")
        lines.append((line, round(line.quantity * line.unit_price * 100)))
    subtotal = sum(x[1] for x in lines)
    bill = Bill(business_id=business_id, vendor_id=payload.vendor_id, number=payload.number,
        bill_date=payload.bill_date, due_date=payload.due_date, notes=payload.notes,
        subtotal_cents=subtotal, total_cents=subtotal)
    session.add(bill); session.flush()
    for line, total in lines:
        session.add(BillLine(business_id=business_id, bill_id=bill.id, account_id=line.account_id,
            description=line.description, quantity_milli=round(line.quantity * 1000),
            unit_cost_cents=cents(line.unit_price), line_total_cents=total))
    audit(session, business_id, user.id, "bill.create", "bill", bill.id)
    session.commit(); session.refresh(bill); return bill


@router.post("/bills/{bill_id}/post")
def post_bill(bill_id: int, context=Depends(require_write), session: Session = Depends(get_session)):
    business_id, _, user = context
    bill = session.get(Bill, bill_id)
    if not bill or bill.business_id != business_id: raise HTTPException(404, "Bill not found")
    if bill.status != "draft": raise HTTPException(409, "Only draft bills can be posted")
    lines = session.exec(select(BillLine).where(BillLine.business_id == business_id, BillLine.bill_id == bill.id)).all()
    ap = account_by_subtype(session, business_id, "accounts_payable")
    journal_lines = [{"account_id": x.account_id, "description": x.description, "debit_cents": x.line_total_cents, "credit_cents": 0} for x in lines]
    journal_lines.append({"account_id": ap.id, "description": bill.number, "debit_cents": 0, "credit_cents": bill.total_cents})
    post_entry(session, business_id, user.id, bill.bill_date, f"Bill {bill.number}", "bill", bill.id, journal_lines)
    bill.status = "open"; audit(session, business_id, user.id, "bill.post", "bill", bill.id)
    session.commit(); session.refresh(bill); return bill


@router.post("/bills/{bill_id}/payments")
def pay_bill(bill_id: int, payload: PaymentPayload, context=Depends(require_write), session: Session = Depends(get_session)):
    business_id, _, user = context
    bill = session.get(Bill, bill_id)
    if not bill or bill.business_id != business_id: raise HTTPException(404, "Bill not found")
    amount = cents(payload.amount)
    if amount <= 0 or amount > bill.total_cents - bill.paid_cents: raise HTTPException(400, "Invalid payment amount")
    bank = session.get(LedgerAccount, payload.account_id)
    if not bank or bank.business_id != business_id: raise HTTPException(400, "Invalid payment account")
    ap = account_by_subtype(session, business_id, "accounts_payable")
    payment = Payment(business_id=business_id, direction="paid", payment_date=payload.payment_date,
        amount_cents=amount, contact_id=bill.vendor_id, bill_id=bill.id, account_id=bank.id, reference=payload.reference)
    session.add(payment); session.flush()
    post_entry(session, business_id, user.id, payload.payment_date, f"Payment for bill {bill.number}", "payment", payment.id, [
        {"account_id": ap.id, "description": bill.number, "debit_cents": amount, "credit_cents": 0},
        {"account_id": bank.id, "description": payload.reference, "debit_cents": 0, "credit_cents": amount},
    ])
    bill.paid_cents += amount; bill.status = "paid" if bill.paid_cents == bill.total_cents else "partial"
    audit(session, business_id, user.id, "payment.pay", "payment", payment.id)
    session.commit(); return payment


@router.get("/expenses")
def expenses(context=Depends(business_context), session: Session = Depends(get_session)):
    return session.exec(select(Expense).where(Expense.business_id == context[0]).order_by(Expense.id.desc())).all()


@router.post("/expenses")
def create_expense(payload: ExpensePayload, context=Depends(require_write), session: Session = Depends(get_session)):
    business_id, _, user = context; amount = cents(payload.amount)
    if amount <= 0: raise HTTPException(400, "Expense amount must be greater than zero")
    for account_id in (payload.account_id, payload.payment_account_id):
        account = session.get(LedgerAccount, account_id)
        if not account or account.business_id != business_id: raise HTTPException(400, "Invalid ledger account")
    expense = Expense(business_id=business_id, amount_cents=amount, **payload.model_dump(exclude={"amount"}))
    session.add(expense); session.flush()
    post_entry(session, business_id, user.id, payload.expense_date, payload.description or "Expense", "expense", expense.id, [
        {"account_id": payload.account_id, "description": payload.reference, "debit_cents": amount, "credit_cents": 0},
        {"account_id": payload.payment_account_id, "description": payload.reference, "debit_cents": 0, "credit_cents": amount},
    ])
    audit(session, business_id, user.id, "expense.create", "expense", expense.id)
    session.commit(); session.refresh(expense); return expense


@router.get("/journal")
def journal(context=Depends(business_context), session: Session = Depends(get_session)):
    entries = session.exec(select(JournalEntry).where(JournalEntry.business_id == context[0]).order_by(JournalEntry.id.desc())).all()
    return [{"entry": entry, "lines": session.exec(select(JournalLine).where(JournalLine.journal_entry_id == entry.id, JournalLine.business_id == context[0])).all()} for entry in entries]


@router.post("/journal")
def create_journal(payload: JournalPayload, context=Depends(require_write), session: Session = Depends(get_session)):
    business_id, _, user = context
    lines = [{"account_id": x.account_id, "description": x.description,
              "debit_cents": cents(x.debit), "credit_cents": cents(x.credit)} for x in payload.lines]
    entry = post_entry(session, business_id, user.id, payload.entry_date, payload.memo, "manual", None, lines)
    audit(session, business_id, user.id, "journal.create", "journal_entry", entry.id)
    session.commit(); session.refresh(entry); return entry


def account_balances(session: Session, business_id: int, start: Optional[str] = None, end: Optional[str] = None):
    accounts = session.exec(select(LedgerAccount).where(LedgerAccount.business_id == business_id)).all()
    entries = session.exec(select(JournalEntry).where(JournalEntry.business_id == business_id, JournalEntry.status == "posted")).all()
    entry_ids = {x.id for x in entries if (not start or x.entry_date >= start) and (not end or x.entry_date <= end)}
    lines = session.exec(select(JournalLine).where(JournalLine.business_id == business_id)).all()
    totals = {a.id: {"debit_cents": 0, "credit_cents": 0} for a in accounts}
    for line in lines:
        if line.journal_entry_id in entry_ids:
            totals[line.account_id]["debit_cents"] += line.debit_cents
            totals[line.account_id]["credit_cents"] += line.credit_cents
    return accounts, totals


@router.get("/reports/trial-balance")
def trial_balance(as_of: Optional[str] = None, context=Depends(business_context), session: Session = Depends(get_session)):
    accounts, totals = account_balances(session, context[0], end=as_of)
    rows = []
    for account in accounts:
        net = totals[account.id]["debit_cents"] - totals[account.id]["credit_cents"]
        rows.append({"account": account, "debit_cents": max(net, 0), "credit_cents": max(-net, 0)})
    return {"rows": rows, "total_debits_cents": sum(x["debit_cents"] for x in rows), "total_credits_cents": sum(x["credit_cents"] for x in rows)}


@router.get("/reports/profit-loss")
def profit_loss(start: Optional[str] = None, end: Optional[str] = None, context=Depends(business_context), session: Session = Depends(get_session)):
    accounts, totals = account_balances(session, context[0], start, end)
    income = []; expenses_out = []
    for account in accounts:
        if account.account_type == "income":
            income.append({"account": account, "amount_cents": totals[account.id]["credit_cents"] - totals[account.id]["debit_cents"]})
        elif account.account_type == "expense":
            expenses_out.append({"account": account, "amount_cents": totals[account.id]["debit_cents"] - totals[account.id]["credit_cents"]})
    total_income = sum(x["amount_cents"] for x in income); total_expenses = sum(x["amount_cents"] for x in expenses_out)
    return {"income": income, "expenses": expenses_out, "total_income_cents": total_income,
            "total_expenses_cents": total_expenses, "net_income_cents": total_income - total_expenses}


@router.get("/reports/balance-sheet")
def balance_sheet(as_of: Optional[str] = None, context=Depends(business_context), session: Session = Depends(get_session)):
    accounts, totals = account_balances(session, context[0], end=as_of)
    sections = {"asset": [], "liability": [], "equity": []}
    for account in accounts:
        if account.account_type in sections:
            normal_debit = account.account_type == "asset"
            amount = (totals[account.id]["debit_cents"] - totals[account.id]["credit_cents"]) * (1 if normal_debit else -1)
            sections[account.account_type].append({"account": account, "amount_cents": amount})
    sections["totals"] = {key: sum(x["amount_cents"] for x in sections[key]) for key in ("asset", "liability", "equity")}
    return sections


@router.get("/tasks")
def list_tasks(context=Depends(business_context), session: Session = Depends(get_session)):
    return session.exec(select(TaskItem).where(TaskItem.business_id == context[0]).order_by(TaskItem.id.desc())).all()


@router.post("/tasks")
def create_task(payload: TaskPayload, context=Depends(require_write), session: Session = Depends(get_session)):
    business_id, _, user = context
    task = TaskItem(business_id=business_id, created_by_user_id=user.id, **payload.model_dump())
    session.add(task); session.flush(); audit(session, business_id, user.id, "task.create", "task", task.id)
    session.commit(); session.refresh(task); return task


@router.patch("/tasks/{task_id}")
def update_task(task_id: int, payload: TaskPayload, context=Depends(require_write), session: Session = Depends(get_session)):
    business_id, _, user = context; task = session.get(TaskItem, task_id)
    if not task or task.business_id != business_id: raise HTTPException(404, "Task not found")
    for key, value in payload.model_dump().items(): setattr(task, key, value)
    audit(session, business_id, user.id, "task.update", "task", task.id); session.commit(); session.refresh(task); return task


def _ensure_closing_template(session: Session, business_id: int) -> None:
    existing = session.exec(select(ChecklistTemplate).where(
        ChecklistTemplate.business_id == business_id, ChecklistTemplate.category == "closing",
        ChecklistTemplate.active == True,  # noqa: E712
    )).first()
    if not existing:
        session.add(ChecklistTemplate(
            business_id=business_id, name="Closing checklist", category="closing",
            description="Reusable end-of-day checks.",
            items_json=json.dumps(["Review unfinished work", "Record issues", "Secure the workplace"]),
        ))
        session.commit()


@router.get("/checklists/templates")
def checklist_templates(context=Depends(business_context), session: Session = Depends(get_session)):
    _ensure_closing_template(session, context[0])
    return session.exec(select(ChecklistTemplate).where(
        ChecklistTemplate.business_id == context[0], ChecklistTemplate.active == True  # noqa: E712
    ).order_by(ChecklistTemplate.name)).all()


@router.post("/checklists/templates")
def create_checklist_template(payload: ChecklistPayload, context=Depends(require_write), session: Session = Depends(get_session)):
    business_id, _, user = context
    items = [item.strip() for item in payload.items if item.strip()]
    if not payload.name.strip() or not items:
        raise HTTPException(400, "Checklist name and at least one item are required")
    template = ChecklistTemplate(business_id=business_id, name=payload.name.strip(), description=payload.description.strip(),
        category=payload.category, items_json=json.dumps(items))
    session.add(template); session.flush(); audit(session, business_id, user.id, "checklist.create", "checklist_template", template.id)
    session.commit(); session.refresh(template); return template


def _run_dict(run: ChecklistRun, template: Optional[ChecklistTemplate] = None):
    try: items = json.loads(run.items_json or "[]")
    except (TypeError, ValueError): items = []
    return {**run.model_dump(), "items": items, "template_name": template.name if template else "Checklist"}


@router.get("/checklists/runs")
def checklist_runs(context=Depends(business_context), session: Session = Depends(get_session)):
    runs = session.exec(select(ChecklistRun).where(ChecklistRun.business_id == context[0]).order_by(ChecklistRun.id.desc()).limit(100)).all()
    templates = {row.id: row for row in session.exec(select(ChecklistTemplate).where(ChecklistTemplate.business_id == context[0])).all()}
    return [_run_dict(run, templates.get(run.template_id)) for run in runs]


@router.post("/checklists/runs")
def start_checklist(payload: ChecklistRunPayload, context=Depends(require_write), session: Session = Depends(get_session)):
    business_id, _, user = context; template = session.get(ChecklistTemplate, payload.template_id)
    if not template or template.business_id != business_id: raise HTTPException(404, "Checklist not found")
    items = [{"label": label, "done": False} for label in json.loads(template.items_json or "[]")]
    run = ChecklistRun(business_id=business_id, template_id=template.id, run_date=payload.run_date,
        items_json=json.dumps(items), created_by_user_id=user.id)
    session.add(run); session.flush(); audit(session, business_id, user.id, "checklist.start", "checklist_run", run.id)
    session.commit(); session.refresh(run); return _run_dict(run, template)


@router.patch("/checklists/runs/{run_id}")
def update_checklist_run(run_id: int, payload: ChecklistRunUpdate, context=Depends(require_write), session: Session = Depends(get_session)):
    business_id, _, user = context; run = session.get(ChecklistRun, run_id)
    if not run or run.business_id != business_id: raise HTTPException(404, "Checklist run not found")
    run.items_json = json.dumps([{"label": str(item.get("label", "")).strip(), "done": bool(item.get("done"))} for item in payload.items])
    run.notes = payload.notes
    if payload.complete:
        run.status = "complete"; run.completed_by_user_id = user.id; run.completed_at = datetime.now(timezone.utc).isoformat()
    session.add(run); audit(session, business_id, user.id, "checklist.complete" if payload.complete else "checklist.update", "checklist_run", run.id)
    session.commit(); session.refresh(run); return _run_dict(run, session.get(ChecklistTemplate, run.template_id))


@router.get("/closing-reports")
def closing_reports(context=Depends(business_context), session: Session = Depends(get_session)):
    return session.exec(select(ClosingReport).where(ClosingReport.business_id == context[0]).order_by(ClosingReport.report_date.desc(), ClosingReport.id.desc()).limit(100)).all()


@router.post("/closing-reports")
def create_closing_report(payload: ClosingReportPayload, context=Depends(require_write), session: Session = Depends(get_session)):
    business_id, _, user = context
    report = ClosingReport(business_id=business_id, location_id=payload.location_id, report_date=payload.report_date,
        sales_cents=cents(payload.sales), card_sales_cents=cents(payload.card_sales),
        sales_tax_cents=cents(payload.sales_tax), cash_expected_cents=cents(payload.cash_expected),
        cash_actual_cents=cents(payload.cash_actual), labor_cost_cents=cents(payload.labor_cost),
        waste_cents=cents(payload.waste), issues=payload.issues.strip(), notes=payload.notes.strip(), submitted_by_user_id=user.id)
    session.add(report); session.flush(); audit(session, business_id, user.id, "closing_report.create", "closing_report", report.id)
    session.commit(); session.refresh(report); return report


@router.post("/closing-reports/{report_id}/post")
def post_closing_report(report_id: int, payload: ClosingReportPostPayload, context=Depends(require_write), session: Session = Depends(get_session)):
    business_id, _, user = context
    report = session.get(ClosingReport, report_id)
    if not report or report.business_id != business_id:
        raise HTTPException(404, "Closing report not found")
    if report.sales_cents <= 0:
        raise HTTPException(400, "Cannot post a closing report with zero sales")
    existing = session.exec(select(JournalEntry).where(
        JournalEntry.business_id == business_id,
        JournalEntry.source_type == "closing_report",
        JournalEntry.source_id == report_id,
        JournalEntry.status == "posted",
    )).first()
    if existing:
        raise HTTPException(409, "This closing report has already been posted to the books")
    bank = session.get(LedgerAccount, payload.bank_account_id)
    if not bank or bank.business_id != business_id:
        raise HTTPException(400, "Invalid deposit account")
    revenue = account_by_subtype(session, business_id, "sales")
    tax_cents = report.sales_tax_cents
    revenue_cents = report.sales_cents - tax_cents
    lines = [
        {"account_id": bank.id, "description": f"Daily sales {report.report_date}", "debit_cents": report.sales_cents, "credit_cents": 0},
        {"account_id": revenue.id, "description": f"Daily sales {report.report_date}", "debit_cents": 0, "credit_cents": revenue_cents},
    ]
    if tax_cents > 0:
        tax_account = session.exec(select(LedgerAccount).where(
            LedgerAccount.business_id == business_id, LedgerAccount.subtype == "sales_tax",
            LedgerAccount.active == True,  # noqa: E712
        )).first()
        if tax_account:
            lines.append({"account_id": tax_account.id, "description": "Sales tax collected", "debit_cents": 0, "credit_cents": tax_cents})
        else:
            lines[1]["credit_cents"] = report.sales_cents
    post_entry(session, business_id, user.id, report.report_date, f"Daily sales {report.report_date}", "closing_report", report_id, lines)
    audit(session, business_id, user.id, "closing_report.post", "closing_report", report_id)
    session.commit()
    return {"posted": True, "date": report.report_date}


@router.get("/reports/ar-aging")
def ar_aging(context=Depends(business_context), session: Session = Depends(get_session)):
    business_id = context[0]
    today_str = date.today().isoformat()
    invoices = session.exec(select(Invoice).where(
        Invoice.business_id == business_id,
        Invoice.status.in_(["sent", "partial", "overdue"]),
    )).all()
    buckets: dict[str, list] = {"current": [], "1_30": [], "31_60": [], "61_90": [], "over_90": []}
    for inv in invoices:
        balance = inv.total_cents - inv.paid_cents
        if balance <= 0:
            continue
        days_past = (date.fromisoformat(today_str) - date.fromisoformat(inv.due_date)).days
        contact = session.get(Contact, inv.customer_id)
        row = {
            "invoice_number": inv.number, "due_date": inv.due_date,
            "customer": contact.name if contact else "Unknown",
            "days_past_due": max(0, days_past), "balance_cents": balance,
        }
        if days_past <= 0: buckets["current"].append(row)
        elif days_past <= 30: buckets["1_30"].append(row)
        elif days_past <= 60: buckets["31_60"].append(row)
        elif days_past <= 90: buckets["61_90"].append(row)
        else: buckets["over_90"].append(row)
    totals = {k: sum(x["balance_cents"] for x in v) for k, v in buckets.items()}
    return {"buckets": buckets, "totals": totals, "grand_total_cents": sum(totals.values())}


@router.get("/reports/ap-aging")
def ap_aging(context=Depends(business_context), session: Session = Depends(get_session)):
    business_id = context[0]
    today_str = date.today().isoformat()
    bills = session.exec(select(Bill).where(
        Bill.business_id == business_id,
        Bill.status.in_(["open", "partial"]),
    )).all()
    buckets: dict[str, list] = {"current": [], "1_30": [], "31_60": [], "61_90": [], "over_90": []}
    for bill in bills:
        balance = bill.total_cents - bill.paid_cents
        if balance <= 0:
            continue
        days_past = (date.fromisoformat(today_str) - date.fromisoformat(bill.due_date)).days
        contact = session.get(Contact, bill.vendor_id)
        row = {
            "bill_number": bill.number or f"Bill {bill.id}", "due_date": bill.due_date,
            "vendor": contact.name if contact else "Unknown",
            "days_past_due": max(0, days_past), "balance_cents": balance,
        }
        if days_past <= 0: buckets["current"].append(row)
        elif days_past <= 30: buckets["1_30"].append(row)
        elif days_past <= 60: buckets["31_60"].append(row)
        elif days_past <= 90: buckets["61_90"].append(row)
        else: buckets["over_90"].append(row)
    totals = {k: sum(x["balance_cents"] for x in v) for k, v in buckets.items()}
    return {"buckets": buckets, "totals": totals, "grand_total_cents": sum(totals.values())}


@router.get("/reports/food-cost")
def food_cost_report(start: Optional[str] = None, end: Optional[str] = None, context=Depends(business_context), session: Session = Depends(get_session)):
    business_id = context[0]
    accounts, totals = account_balances(session, business_id, start, end)
    sales_accounts = [a for a in accounts if a.account_type == "income"]
    food_accounts = [a for a in accounts if a.subtype in FOOD_COST_SUBTYPES]
    total_sales = sum(totals[a.id]["credit_cents"] - totals[a.id]["debit_cents"] for a in sales_accounts)
    total_food_cost = sum(totals[a.id]["debit_cents"] - totals[a.id]["credit_cents"] for a in food_accounts)
    pct = round(total_food_cost / total_sales * 100, 1) if total_sales > 0 else 0
    return {
        "total_sales_cents": total_sales,
        "total_food_cost_cents": total_food_cost,
        "food_cost_pct": pct,
        "breakdown": [
            {
                "account_name": a.name,
                "amount_cents": totals[a.id]["debit_cents"] - totals[a.id]["credit_cents"],
                "pct_of_sales": round((totals[a.id]["debit_cents"] - totals[a.id]["credit_cents"]) / total_sales * 100, 1) if total_sales > 0 else 0,
            }
            for a in food_accounts
        ],
    }


DEFAULT_UI_CONFIG: dict = {
    "theme": {
        "primary": "#2f6fed",
        "sidebar_bg": "#111c31",
        "accent": "#14835f",
        "page_bg": "#eef3f9",
        "font": "",
    },
    "branding": {
        "logo_letter": "O",
        "tagline": "Operations + accounting",
    },
    "nav_labels": {},
}


def _merged_ui_config(record: Optional["UIConfig"]) -> dict:
    import copy
    result = copy.deepcopy(DEFAULT_UI_CONFIG)
    if record:
        try:
            saved = json.loads(record.config_json or "{}")
            for section, values in saved.items():
                if isinstance(values, dict):
                    result[section] = {**result.get(section, {}), **values}
                else:
                    result[section] = values
        except Exception:
            pass
    return result


@router.post("/accounting/sales-tax/remit")
def remit_sales_tax(payload: SalesTaxRemitPayload, context=Depends(require_write), session: Session = Depends(get_session)):
    business_id, user = context
    amount_cents = round(payload.amount * 100)
    if amount_cents <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than zero")
    tax_acct = session.exec(select(LedgerAccount).where(LedgerAccount.business_id == business_id, LedgerAccount.subtype == "sales_tax")).first()
    if not tax_acct:
        raise HTTPException(status_code=400, detail="No Sales Tax Payable account found — check your chart of accounts")
    bank_acct = session.exec(select(LedgerAccount).where(LedgerAccount.id == payload.bank_account_id, LedgerAccount.business_id == business_id)).first()
    if not bank_acct:
        raise HTTPException(status_code=400, detail="Bank account not found")
    entry_date = utc_now_iso()[:10]
    post_entry(session, business_id, user.id, entry_date, f"CO sales tax remittance {payload.period}", "sales_tax_remit", 0, [
        {"account_id": tax_acct.id, "description": f"Sales tax paid {payload.period}", "debit_cents": amount_cents, "credit_cents": 0},
        {"account_id": bank_acct.id, "description": f"Sales tax paid {payload.period}", "debit_cents": 0, "credit_cents": amount_cents},
    ])
    return {"ok": True, "amount_cents": amount_cents}


@router.get("/ui-config")
def get_ui_config(context=Depends(business_context), session: Session = Depends(get_session)):
    business_id = context[0]
    record = session.exec(select(UIConfig).where(UIConfig.business_id == business_id)).first()
    return _merged_ui_config(record)


@router.put("/ui-config")
def update_ui_config_endpoint(payload: UIConfigPatch, context=Depends(require_write), session: Session = Depends(get_session)):
    business_id, _, user = context
    record = session.exec(select(UIConfig).where(UIConfig.business_id == business_id)).first()
    if not record:
        record = UIConfig(business_id=business_id)
    try:
        existing = json.loads(record.config_json) if record.config_json else {}
    except Exception:
        existing = {}
    for section, values in payload.patch.items():
        if isinstance(values, dict):
            existing[section] = {**existing.get(section, {}), **values}
        else:
            existing[section] = values
    record.config_json = json.dumps(existing)
    record.updated_at = utc_now_iso()
    session.add(record)
    audit(session, business_id, user.id, "ui_config.update", "ui_config", record.id, {"sections": list(payload.patch.keys())})
    session.commit()
    session.refresh(record)
    return _merged_ui_config(record)


@router.get("/presets")
def list_presets(context=Depends(business_context)):
    return [{"key": key, "label": value["label"], "description": value["description"]} for key, value in PRESETS.items()]


def _apply_preset(session: Session, business_id: int, preset_key: str) -> None:
    preset = PRESETS[preset_key]
    business = session.get(Business, business_id)
    if business: business.industry = preset_key
    for module_key in MODULES:
        record = session.exec(select(BusinessModule).where(BusinessModule.business_id == business_id, BusinessModule.module_key == module_key)).first()
        if not record: record = BusinessModule(business_id=business_id, module_key=module_key)
        record.enabled = module_key in preset["modules"]; session.add(record)
    existing_names = {row.name.lower() for row in session.exec(select(Department).where(Department.business_id == business_id)).all()}
    for name in preset["departments"]:
        if name.lower() not in existing_names: session.add(Department(business_id=business_id, name=name))
    template = session.exec(select(ChecklistTemplate).where(ChecklistTemplate.business_id == business_id, ChecklistTemplate.category == "closing")).first()
    if not template: template = ChecklistTemplate(business_id=business_id, name="Closing checklist", category="closing")
    template.items_json = json.dumps(preset["checklist"]); template.description = f"Closing steps for {preset['label'].lower()}."; session.add(template)


@router.post("/presets/{preset_key}/apply")
def apply_preset(preset_key: str, context=Depends(require_write), session: Session = Depends(get_session)):
    business_id, membership, user = context
    if membership.role not in ADMIN_ROLES: raise HTTPException(403, "Owner or admin access required")
    if preset_key not in PRESETS: raise HTTPException(404, "Unknown business preset")
    _apply_preset(session, business_id, preset_key); audit(session, business_id, user.id, "preset.apply", "business", business_id, {"preset": preset_key})
    session.commit(); return {"applied": preset_key}


@router.post("/presets/recommend")
def recommend_preset(payload: PresetRecommendationPayload, context=Depends(business_context)):
    description = payload.description.strip().lower()
    key = "custom"
    keyword_map = {
        "food_service": ["restaurant", "cafe", "coffee", "food", "kitchen", "catering", "bar"],
        "warehouse": ["warehouse", "shipping", "receiving", "distribution", "storage"],
        "construction": ["construction", "contractor", "job site", "crew", "plumbing", "electric", "landscaping"],
        "retail": ["retail", "store", "shop", "boutique"],
        "office": ["office", "consulting", "agency", "law", "professional", "clinic"],
    }
    for candidate, words in keyword_map.items():
        if any(word in description for word in words): key = candidate; break
    if os.getenv("ANTHROPIC_API_KEY") and description:
        try:
            from anthropic import Anthropic
            response = Anthropic().messages.create(model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"), max_tokens=20,
                system="Classify the business. Reply with exactly one key: food_service, warehouse, construction, retail, office, custom.",
                messages=[{"role": "user", "content": payload.description}])
            answer = "".join(block.text for block in response.content if getattr(block, "type", "") == "text").strip().lower()
            if answer in PRESETS: key = answer
        except Exception: pass
    preset = PRESETS[key]
    return {"key": key, "label": preset["label"], "description": preset["description"]}


@router.get("/inventory")
def inventory(context=Depends(business_context), session: Session = Depends(get_session)):
    return session.exec(select(InventoryItem).where(InventoryItem.business_id == context[0], InventoryItem.active == True)).all()  # noqa: E712


@router.post("/inventory")
def create_inventory_item(payload: InventoryPayload, context=Depends(require_write), session: Session = Depends(get_session)):
    business_id, _, user = context
    item = InventoryItem(business_id=business_id, quantity_milli=round(payload.quantity * 1000),
        reorder_level_milli=round(payload.reorder_level * 1000), unit_cost_cents=cents(payload.unit_cost),
        sales_price_cents=cents(payload.sales_price), **payload.model_dump(exclude={"quantity", "reorder_level", "unit_cost", "sales_price"}))
    session.add(item); session.flush(); audit(session, business_id, user.id, "inventory.create", "inventory_item", item.id)
    session.commit(); session.refresh(item); return item


@router.post("/inventory/{item_id}/adjust")
def adjust_inventory(item_id: int, payload: InventoryAdjustPayload, context=Depends(require_write), session: Session = Depends(get_session)):
    business_id, _, user = context; item = session.get(InventoryItem, item_id)
    if not item or item.business_id != business_id: raise HTTPException(404, "Inventory item not found")
    change = round(payload.quantity_change * 1000); item.quantity_milli += change
    movement = InventoryMovement(business_id=business_id, item_id=item.id, movement_date=date.today().isoformat(),
        quantity_milli=change, reason=payload.reason, reference=payload.reference, created_by_user_id=user.id)
    session.add(movement); audit(session, business_id, user.id, "inventory.adjust", "inventory_item", item.id, {"change_milli": change})
    session.commit(); session.refresh(item); return item


@router.get("/audit")
def audit_log(context=Depends(business_context), session: Session = Depends(get_session)):
    if context[1].role not in ADMIN_ROLES | {"manager", "accountant"}: raise HTTPException(403, "Audit access required")
    return session.exec(select(AuditEvent).where(AuditEvent.business_id == context[0]).order_by(AuditEvent.id.desc()).limit(250)).all()
