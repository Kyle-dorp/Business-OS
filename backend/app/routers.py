"""
API routers for all new modules:
- inventory
- payroll
- invoicing
- customers
- team_communication
- analytics
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select
from datetime import datetime, timezone
from typing import Optional

from backend.app.database import get_session
from backend.app.auth import manager_from_request
from backend.app.tenancy import current_business_id
from backend.app.modules.inventory import InventoryItem, InventoryTransaction, Supplier
from backend.app.modules.payroll import PayrollPeriod, EmployeePayroll, TaxWithholding, PayStub
from backend.app.modules.invoicing import Invoice, InvoiceLineItem, Payment, RecurringBilling
from backend.app.modules.customers import Customer, CustomerPreferences, PurchaseHistory, LoyaltyAccount, CommunicationLog
from backend.app.modules.team_communication import TeamChannel, ChannelMessage, DirectMessage, ShiftNote, Announcement, ShiftSwapRequest, FileShare
from backend.app.modules.analytics import DailyMetrics, StaffPerformance, RevenueByService, CustomerInsight, Forecast, CustomReport, Dashboard
from backend.app.modules.booking import Service, Booking, BookingAvailability

from pydantic import BaseModel
from typing import Optional

# ============================================================================
# INVENTORY ROUTER
# ============================================================================

inventory_router = APIRouter(prefix="/inventory", tags=["inventory"])

class InventoryItemCreate(BaseModel):
    name: str
    sku: str
    quantity: int = 0
    reorder_level: int = 0
    unit_cost: float = 0
    unit_price: float = 0
    notes: Optional[str] = None

@inventory_router.get("/items")
def list_inventory_items(session: Session = Depends(get_session)):
    business_id = current_business_id()
    return session.exec(
        select(InventoryItem).where(InventoryItem.business_id == business_id)
    ).all()

@inventory_router.post("/items")
def create_inventory_item(payload: InventoryItemCreate, request: Request, session: Session = Depends(get_session)):
    manager_from_request(request)
    item = InventoryItem(
        business_id=current_business_id(),
        **payload.model_dump()
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item

@inventory_router.patch("/items/{item_id}")
def update_inventory_item(item_id: int, payload: InventoryItemCreate, request: Request, session: Session = Depends(get_session)):
    manager_from_request(request)
    item = session.get(InventoryItem, item_id)
    if not item or item.business_id != current_business_id():
        raise HTTPException(status_code=404, detail="Item not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item

@inventory_router.delete("/items/{item_id}")
def delete_inventory_item(item_id: int, request: Request, session: Session = Depends(get_session)):
    manager_from_request(request)
    item = session.get(InventoryItem, item_id)
    if not item or item.business_id != current_business_id():
        raise HTTPException(status_code=404, detail="Item not found")
    session.delete(item)
    session.commit()
    return {"deleted": True}

@inventory_router.post("/transactions")
def record_transaction(item_id: int, transaction_type: str, quantity: int, request: Request, session: Session = Depends(get_session)):
    manager_from_request(request)
    item = session.get(InventoryItem, item_id)
    if not item or item.business_id != current_business_id():
        raise HTTPException(status_code=404, detail="Item not found")

    transaction = InventoryTransaction(
        business_id=current_business_id(),
        item_id=item_id,
        transaction_type=transaction_type,
        quantity_change=quantity,
        recorded_at=datetime.now(timezone.utc).isoformat()
    )
    session.add(transaction)

    if transaction_type == "purchase":
        item.quantity += quantity
    elif transaction_type == "sale":
        item.quantity -= quantity
    elif transaction_type == "return":
        item.quantity += quantity
    elif transaction_type == "adjustment":
        item.quantity = quantity

    session.add(item)
    session.commit()
    session.refresh(transaction)
    return transaction

# ============================================================================
# CUSTOMERS/CRM ROUTER
# ============================================================================

customers_router = APIRouter(prefix="/customers", tags=["customers"])

class CustomerCreate(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = ""
    address: Optional[str] = ""
    city: Optional[str] = ""
    state: Optional[str] = ""
    zip_code: Optional[str] = ""
    company_name: Optional[str] = None

@customers_router.get("/")
def list_customers(session: Session = Depends(get_session)):
    business_id = current_business_id()
    return session.exec(
        select(Customer).where(Customer.business_id == business_id)
    ).all()

@customers_router.post("/")
def create_customer(payload: CustomerCreate, request: Request, session: Session = Depends(get_session)):
    manager_from_request(request)
    customer = Customer(
        business_id=current_business_id(),
        created_at=datetime.now(timezone.utc).isoformat(),
        **payload.model_dump()
    )
    session.add(customer)
    session.commit()
    session.refresh(customer)

    # Create loyalty account
    loyalty = LoyaltyAccount(
        business_id=current_business_id(),
        customer_id=customer.id,
        last_activity=datetime.now(timezone.utc).isoformat()
    )
    session.add(loyalty)
    session.commit()

    return customer

@customers_router.get("/{customer_id}")
def get_customer(customer_id: int, session: Session = Depends(get_session)):
    customer = session.get(Customer, customer_id)
    if not customer or customer.business_id != current_business_id():
        raise HTTPException(status_code=404, detail="Customer not found")

    prefs = session.exec(
        select(CustomerPreferences).where(CustomerPreferences.customer_id == customer_id)
    ).first()

    loyalty = session.exec(
        select(LoyaltyAccount).where(LoyaltyAccount.customer_id == customer_id)
    ).first()

    history = session.exec(
        select(PurchaseHistory).where(PurchaseHistory.customer_id == customer_id)
    ).all()

    return {
        **customer.model_dump(),
        "preferences": prefs,
        "loyalty": loyalty,
        "purchase_history": history
    }

@customers_router.patch("/{customer_id}")
def update_customer(customer_id: int, payload: CustomerCreate, request: Request, session: Session = Depends(get_session)):
    manager_from_request(request)
    customer = session.get(Customer, customer_id)
    if not customer or customer.business_id != current_business_id():
        raise HTTPException(status_code=404, detail="Customer not found")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(customer, key, value)

    session.add(customer)
    session.commit()
    session.refresh(customer)
    return customer

@customers_router.post("/{customer_id}/log-communication")
def log_communication(customer_id: int, communication_type: str, subject: str, message: str, request: Request, session: Session = Depends(get_session)):
    manager_from_request(request)
    customer = session.get(Customer, customer_id)
    if not customer or customer.business_id != current_business_id():
        raise HTTPException(status_code=404, detail="Customer not found")

    log_entry = CommunicationLog(
        business_id=current_business_id(),
        customer_id=customer_id,
        communication_type=communication_type,
        subject=subject,
        message=message,
        sent_by="system",
        timestamp=datetime.now(timezone.utc).isoformat()
    )
    session.add(log_entry)
    session.commit()
    session.refresh(log_entry)
    return log_entry

# ============================================================================
# INVOICING ROUTER
# ============================================================================

invoicing_router = APIRouter(prefix="/invoicing", tags=["invoicing"])

class InvoiceCreate(BaseModel):
    customer_id: int
    description: str
    amount: float
    tax_rate: float = 0.0
    due_date: Optional[str] = None

@invoicing_router.get("/invoices")
def list_invoices(session: Session = Depends(get_session)):
    business_id = current_business_id()
    return session.exec(
        select(Invoice).where(Invoice.business_id == business_id).order_by(Invoice.id.desc())
    ).all()

@invoicing_router.post("/invoices")
def create_invoice(payload: InvoiceCreate, request: Request, session: Session = Depends(get_session)):
    manager_from_request(request)
    business_id = current_business_id()

    invoice = Invoice(
        business_id=business_id,
        customer_id=payload.customer_id,
        amount=payload.amount,
        tax_amount=payload.amount * payload.tax_rate,
        total_cents=int((payload.amount * (1 + payload.tax_rate)) * 100),
        paid_cents=0,
        status="draft",
        created_at=datetime.now(timezone.utc).isoformat()
    )
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
    return invoice

@invoicing_router.patch("/invoices/{invoice_id}")
def update_invoice(invoice_id: int, payload: InvoiceCreate, request: Request, session: Session = Depends(get_session)):
    manager_from_request(request)
    invoice = session.get(Invoice, invoice_id)
    if not invoice or invoice.business_id != current_business_id():
        raise HTTPException(status_code=404, detail="Invoice not found")

    invoice.amount = payload.amount
    invoice.tax_amount = payload.amount * payload.tax_rate
    invoice.total_cents = int((payload.amount * (1 + payload.tax_rate)) * 100)

    session.add(invoice)
    session.commit()
    session.refresh(invoice)
    return invoice

@invoicing_router.post("/invoices/{invoice_id}/send")
def send_invoice(invoice_id: int, request: Request, session: Session = Depends(get_session)):
    manager_from_request(request)
    invoice = session.get(Invoice, invoice_id)
    if not invoice or invoice.business_id != current_business_id():
        raise HTTPException(status_code=404, detail="Invoice not found")

    invoice.status = "sent"
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
    return invoice

@invoicing_router.post("/invoices/{invoice_id}/pay")
def record_payment(invoice_id: int, amount_cents: int, method: str, request: Request, session: Session = Depends(get_session)):
    manager_from_request(request)
    invoice = session.get(Invoice, invoice_id)
    if not invoice or invoice.business_id != current_business_id():
        raise HTTPException(status_code=404, detail="Invoice not found")

    payment = Payment(
        business_id=current_business_id(),
        invoice_id=invoice_id,
        amount_cents=amount_cents,
        method=method,
        created_at=datetime.now(timezone.utc).isoformat()
    )
    session.add(payment)

    invoice.paid_cents += amount_cents
    if invoice.paid_cents >= invoice.total_cents:
        invoice.status = "paid"

    session.add(invoice)
    session.commit()
    session.refresh(payment)
    return payment

# ============================================================================
# PAYROLL ROUTER
# ============================================================================

payroll_router = APIRouter(prefix="/payroll", tags=["payroll"])

class PayrollCreate(BaseModel):
    period_name: str
    start_date: str
    end_date: str

@payroll_router.get("/periods")
def list_payroll_periods(session: Session = Depends(get_session)):
    business_id = current_business_id()
    return session.exec(
        select(PayrollPeriod).where(PayrollPeriod.business_id == business_id)
    ).all()

@payroll_router.post("/periods")
def create_payroll_period(payload: PayrollCreate, request: Request, session: Session = Depends(get_session)):
    manager_from_request(request)
    period = PayrollPeriod(
        business_id=current_business_id(),
        period_name=payload.period_name,
        start_date=payload.start_date,
        end_date=payload.end_date,
        status="draft",
        created_at=datetime.now(timezone.utc).isoformat()
    )
    session.add(period)
    session.commit()
    session.refresh(period)
    return period

@payroll_router.post("/periods/{period_id}/process")
def process_payroll(period_id: int, request: Request, session: Session = Depends(get_session)):
    manager_from_request(request)
    period = session.get(PayrollPeriod, period_id)
    if not period or period.business_id != current_business_id():
        raise HTTPException(status_code=404, detail="Period not found")

    period.status = "processed"
    session.add(period)
    session.commit()
    session.refresh(period)
    return period

# ============================================================================
# TEAM COMMUNICATION ROUTER
# ============================================================================

team_comm_router = APIRouter(prefix="/team", tags=["team"])

class ChannelCreate(BaseModel):
    name: str
    description: str = ""
    is_private: bool = False

class MessageCreate(BaseModel):
    message: str
    attachments_json: str = "[]"

@team_comm_router.get("/channels")
def list_channels(session: Session = Depends(get_session)):
    business_id = current_business_id()
    return session.exec(
        select(TeamChannel).where(TeamChannel.business_id == business_id)
    ).all()

@team_comm_router.post("/channels")
def create_channel(payload: ChannelCreate, request: Request, session: Session = Depends(get_session)):
    manager_from_request(request)
    channel = TeamChannel(
        business_id=current_business_id(),
        name=payload.name,
        description=payload.description,
        is_private=payload.is_private,
        created_at=datetime.now(timezone.utc).isoformat()
    )
    session.add(channel)
    session.commit()
    session.refresh(channel)
    return channel

@team_comm_router.get("/channels/{channel_id}/messages")
def get_channel_messages(channel_id: int, session: Session = Depends(get_session)):
    return session.exec(
        select(ChannelMessage).where(ChannelMessage.channel_id == channel_id).order_by(ChannelMessage.created_at)
    ).all()

@team_comm_router.post("/channels/{channel_id}/messages")
def post_message(channel_id: int, payload: MessageCreate, request: Request, session: Session = Depends(get_session)):
    from backend.app.auth import user_from_request
    user = user_from_request(request)

    message = ChannelMessage(
        business_id=current_business_id(),
        channel_id=channel_id,
        user_id=user.id,
        message=payload.message,
        attachments_json=payload.attachments_json,
        created_at=datetime.now(timezone.utc).isoformat()
    )
    session.add(message)
    session.commit()
    session.refresh(message)
    return message

@team_comm_router.get("/announcements")
def list_announcements(session: Session = Depends(get_session)):
    business_id = current_business_id()
    return session.exec(
        select(Announcement).where(Announcement.business_id == business_id).order_by(Announcement.created_at.desc())
    ).all()

@team_comm_router.post("/announcements")
def create_announcement(title: str, message: str, priority: str = "normal", request: Request = None, session: Session = Depends(get_session)):
    from backend.app.auth import user_from_request
    user = user_from_request(request)
    manager_from_request(request)

    announcement = Announcement(
        business_id=current_business_id(),
        title=title,
        message=message,
        priority=priority,
        created_by=user.id,
        created_at=datetime.now(timezone.utc).isoformat(),
        read_by_json="[]"
    )
    session.add(announcement)
    session.commit()
    session.refresh(announcement)
    return announcement

# ============================================================================
# ANALYTICS ROUTER
# ============================================================================

analytics_router = APIRouter(prefix="/analytics", tags=["analytics"])

@analytics_router.get("/metrics")
def get_metrics(date: Optional[str] = None, session: Session = Depends(get_session)):
    business_id = current_business_id()
    query = select(DailyMetrics).where(DailyMetrics.business_id == business_id)
    if date:
        query = query.where(DailyMetrics.date == date)
    return session.exec(query.order_by(DailyMetrics.date.desc()).limit(30)).all()

@analytics_router.get("/staff-performance")
def get_staff_performance(period: Optional[str] = None, session: Session = Depends(get_session)):
    business_id = current_business_id()
    query = select(StaffPerformance).where(StaffPerformance.business_id == business_id)
    if period:
        query = query.where(StaffPerformance.period == period)
    return session.exec(query.order_by(StaffPerformance.period.desc()).limit(50)).all()

@analytics_router.get("/revenue-by-service")
def get_revenue_by_service(session: Session = Depends(get_session)):
    business_id = current_business_id()
    return session.exec(
        select(RevenueByService).where(RevenueByService.business_id == business_id).order_by(RevenueByService.date.desc()).limit(100)
    ).all()

@analytics_router.get("/customer-insights")
def get_customer_insights(session: Session = Depends(get_session)):
    business_id = current_business_id()
    return session.exec(
        select(CustomerInsight).where(CustomerInsight.business_id == business_id)
    ).all()

@analytics_router.get("/dashboard")
def get_dashboard(session: Session = Depends(get_session)):
    from backend.app.auth import user_from_request, manager_from_request
    request = None  # Placeholder - would come from FastAPI context
    business_id = current_business_id()

    dashboards = session.exec(
        select(Dashboard).where(Dashboard.business_id == business_id)
    ).all()

    return {
        "dashboards": dashboards,
        "default": dashboards[0] if dashboards else None
    }

# ============================================================================
# BOOKING ROUTER
# ============================================================================

booking_router = APIRouter(prefix="/booking", tags=["booking"])

class ServiceCreate(BaseModel):
    name: str
    description: str = ""
    duration_minutes: int = 30
    price: float
    stripe_price_id: Optional[str] = None

class BookingCreate(BaseModel):
    customer_name: str
    customer_email: str
    customer_phone: str
    service_id: int
    booking_date: str
    booking_time: str
    notes: str = ""

@booking_router.get("/services")
def list_services(session: Session = Depends(get_session)):
    business_id = current_business_id()
    return session.exec(
        select(Service).where(Service.business_id == business_id, Service.active == True)
    ).all()

@booking_router.post("/services")
def create_service(payload: ServiceCreate, request: Request, session: Session = Depends(get_session)):
    manager_from_request(request)
    service = Service(
        business_id=current_business_id(),
        **payload.model_dump()
    )
    session.add(service)
    session.commit()
    session.refresh(service)
    return service

@booking_router.get("/bookings")
def list_bookings(status: Optional[str] = None, session: Session = Depends(get_session)):
    business_id = current_business_id()
    query = select(Booking).where(Booking.business_id == business_id)
    if status:
        query = query.where(Booking.status == status)
    return session.exec(query.order_by(Booking.booking_date.desc())).all()

@booking_router.post("/bookings")
def create_booking(payload: BookingCreate, session: Session = Depends(get_session)):
    service = session.get(Service, payload.service_id)
    if not service or service.business_id != current_business_id():
        raise HTTPException(status_code=404, detail="Service not found")
    
    booking = Booking(
        business_id=current_business_id(),
        **payload.model_dump(),
        duration_minutes=service.duration_minutes,
        price=service.price
    )
    session.add(booking)
    session.commit()
    session.refresh(booking)
    return booking

@booking_router.get("/availability")
def get_availability(day_of_week: int, session: Session = Depends(get_session)):
    business_id = current_business_id()
    return session.exec(
        select(BookingAvailability).where(
            BookingAvailability.business_id == business_id,
            BookingAvailability.day_of_week == day_of_week,
            BookingAvailability.active == True
        )
    ).all()
