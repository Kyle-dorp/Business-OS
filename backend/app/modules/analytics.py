"""
Analytics & Reporting Module
Revenue, staff performance, customer insights, forecasts
"""

from sqlmodel import SQLModel, Field
from typing import Optional

class DailyMetrics(SQLModel, table=True):
    """Daily business metrics snapshot"""
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    location_id: Optional[int] = Field(index=True)
    date: str = Field(unique=True, index=True)
    revenue: float = 0
    transactions_count: int = 0
    customers_count: int = 0
    staff_hours: float = 0
    labor_cost: float = 0
    labor_percent: float = 0  # labor_cost / revenue * 100
    avg_transaction_value: float = 0

class StaffPerformance(SQLModel, table=True):
    """Staff member performance metrics"""
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    employee_id: int = Field(index=True)
    period: str = Field(index=True)  # YYYY-MM
    hours_worked: float = 0
    customers_served: int = 0
    revenue_generated: float = 0
    appointments_completed: int = 0
    customer_rating: float = 0  # 1-5
    no_shows: int = 0
    tardies: int = 0

class RevenueByService(SQLModel, table=True):
    """Revenue breakdown by service/product"""
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    service_id: int = Field(index=True)
    date: str = Field(index=True)
    revenue: float = 0
    quantity_sold: int = 0

class CustomerInsight(SQLModel, table=True):
    """Customer segment analytics"""
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    segment: str  # "vip", "regular", "new", "inactive", "churn_risk"
    count: int = 0
    total_lifetime_value: float = 0
    avg_order_value: float = 0
    repeat_rate: float = 0  # % who return
    last_calculated: str

class Forecast(SQLModel, table=True):
    """Revenue/traffic forecasts"""
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    forecast_type: str  # "revenue", "traffic", "labor_need"
    date: str = Field(index=True)
    predicted_value: float
    confidence_level: float = 0.8  # 0-1
    created_at: str

class CustomReport(SQLModel, table=True):
    """User-created custom reports"""
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    name: str
    description: str = ""
    metrics_json: str  # JSON array of metrics to include
    filters_json: str = "{}"  # date range, location, etc.
    frequency: str = "manual"  # manual, daily, weekly, monthly
    email_recipients: str = ""  # comma-separated
    last_run: Optional[str] = None
    created_by: int = Field(index=True)

class Dashboard(SQLModel, table=True):
    """Customizable dashboard layout"""
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    user_id: int = Field(index=True)
    name: str
    widgets_json: str  # JSON array of widget configs
    is_default: bool = False
    created_at: str
