from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from backend.app.ai_service import (
    AssistantAction,
    AssistantDecision,
    ai_is_configured,
    decide_with_ai,
)
from backend.app.auth import (
    create_access_token,
    hash_password,
    manager_from_request,
    user_from_request,
    user_from_token,
    username_exists,
    verify_password,
)
from backend.app.database import create_db_and_tables, engine, get_session
from backend.app.models import (
    AssistantMemory,
    AssistantMessage,
    AssistantThread,
    AvailabilityRequest,
    Bill,
    Business,
    BusinessModule,
    ChecklistRun,
    ChecklistTemplate,
    ClosingReport,
    Contact,
    CoverageRule,
    Department,
    Employee,
    EmployeePosition,
    Expense,
    InventoryItem,
    Invoice,
    LaborProjection,
    LedgerAccount,
    ManagerSettings,
    Membership,
    Position,
    RecurringAvailability,
    Schedule,
    ScheduleShift,
    ScheduleWarning,
    TaskItem,
    TemporaryUnavailability,
    UIConfig,
    UserAccount,
)
from backend.app.tenancy import current_business_id, reset_current_business_id, set_current_business_id
from backend.app.scheduler import (
    generate_schedule,
    parse_time,
    recurring_rule_blocks,
    schedule_detail,
    temporary_rule_blocks,
)
from backend.app.platform import account_balances, router as platform_router
from backend.app.finance import router as finance_router


app = FastAPI(title="Business OS API", version="1.0.0")
app.include_router(platform_router)
app.include_router(finance_router)

cors_origins = [item.strip() for item in os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",") if item.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


VALID_ROLES = {"employee", "shift_lead", "gm"}


def _department_names(session: Session) -> set[str]:
    return {row.name for row in session.exec(select(Department).where(Department.active == True)).all()}  # noqa: E712


def _department_exists(session: Session, name: Optional[str]) -> bool:
    return bool(name and name in _department_names(session))


class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    min_hours_per_week: Optional[int] = None
    max_hours_per_week: Optional[int] = None
    active: Optional[bool] = None


class PositionUpdate(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None
    active: Optional[bool] = None


class EmployeePositionPayload(BaseModel):
    position_id: int
    trainee: bool = False
    preferred: bool = False


class EmployeePositionList(BaseModel):
    positions: list[EmployeePositionPayload]


class AvailabilityUpdate(BaseModel):
    rule_type: Optional[str] = None
    day_of_week: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class TemporaryAvailabilityUpdate(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class LaborProjectionUpdate(BaseModel):
    date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    projected_sales: Optional[float] = None
    labor_percent: Optional[float] = None
    min_labor_percent: Optional[float] = None
    max_labor_percent: Optional[float] = None
    max_labor_hours: Optional[float] = None
    max_labor_dollars: Optional[float] = None
    note: Optional[str] = None


class CoverageRulePayload(BaseModel):
    name: str
    date: str = ""
    day_of_week: int = -1
    start_time: str
    end_time: str
    position_ids: list[int] = Field(default_factory=list)
    departments: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    minimum_count: int = 1
    preferred_count: int = 1
    hard_minimum: bool = True
    active: bool = True


class GenerateScheduleRequest(BaseModel):
    week_start: str
    source_schedule_id: Optional[int] = None
    scope: str = "full_week"
    selected_date: Optional[str] = None
    labor_tolerance_percent: float = 0.0
    staffing_level: str = "balanced"


class ScheduleShiftUpdate(BaseModel):
    employee_id: Optional[int] = None
    position_id: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    locked: Optional[bool] = None


class ManualShiftCreate(BaseModel):
    date: str
    employee_id: int
    position_id: Optional[int] = None
    start_time: str
    end_time: str
    locked: bool = True


class ChatHistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    week_start: Optional[str] = None
    schedule_id: Optional[int] = None
    thread_id: Optional[int] = None


class AssistantApplyRequest(BaseModel):
    schedule_id: Optional[int] = None
    week_start: Optional[str] = None
    message_id: Optional[int] = None
    actions: list[AssistantAction]


class SetupAccountRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class AccountUpdateRequest(BaseModel):
    username: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: Literal["manager", "employee"] = "employee"
    employee_id: Optional[int] = None


class AdminUserUpdateRequest(BaseModel):
    username: Optional[str] = None
    role: Optional[Literal["manager", "employee"]] = None
    employee_id: Optional[int] = None
    active: Optional[bool] = None
    new_password: Optional[str] = None


class AvailabilityRequestPayload(BaseModel):
    request_type: Literal["day_off", "recurring_change", "temporary_change"] = "day_off"
    title: str = ""
    start_date: str = ""
    end_date: str = ""
    day_of_week: int = -1
    start_time: str = ""
    end_time: str = ""
    rule_type: Literal["unavailable", "preferred"] = "unavailable"
    reason: str = ""


class ReviewAvailabilityRequest(BaseModel):
    status: Literal["approved", "denied"]
    manager_note: str = ""


class AssistantMemoryUpdate(BaseModel):
    content: str = ""



def _user_dict(user: UserAccount) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "employee_id": user.employee_id,
        "active": user.active,
        "created_at": user.created_at,
    }


PUBLIC_PATHS = {
    "/",
    "/favicon.ico",
    "/robots.txt",
    "/health",
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
    "/auth/setup-status",
    "/auth/setup",
    "/auth/login",
}


@app.middleware("http")
async def authentication_middleware(request: Request, call_next):
    path = request.url.path
    if request.method == "OPTIONS" or path in PUBLIC_PATHS or path.startswith(("/docs", "/assets/")):
        return await call_next(request)

    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=401, content={"detail": "Sign in required"})

    try:
        user = user_from_token(authorization.removeprefix("Bearer ").strip())
    except HTTPException as error:
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=error.status_code, content={"detail": error.detail})

    request.state.user = user

    requested_business = request.headers.get("X-Business-Id")
    with Session(engine) as tenant_session:
        memberships = tenant_session.exec(select(Membership).where(
            Membership.user_id == user.id, Membership.active == True  # noqa: E712
        )).all()
    try:
        business_id = int(requested_business) if requested_business else (memberships[0].business_id if memberships else 1)
    except ValueError:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400, content={"detail": "Invalid business workspace"})
    if requested_business and path not in {"/platform/businesses", "/platform/bootstrap"} and not any(x.business_id == business_id for x in memberships):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=403, content={"detail": "You do not have access to this business"})
    tenant_token = set_current_business_id(business_id)

    employee_allowed = (
        path.startswith("/auth/me")
        or path.startswith("/my/")
        or path == "/notifications"
    )
    if user.role != "manager" and not employee_allowed:
        from fastapi.responses import JSONResponse

        reset_current_business_id(tenant_token)
        return JSONResponse(status_code=403, content={"detail": "Manager access required"})

    try:
        return await call_next(request)
    finally:
        reset_current_business_id(tenant_token)


@app.get("/auth/setup-status")
def setup_status():
    with Session(engine) as session:
        return {"needs_setup": session.exec(select(UserAccount)).first() is None}


@app.post("/auth/setup")
def setup_first_manager(payload: SetupAccountRequest):
    with Session(engine) as session:
        if session.exec(select(UserAccount)).first():
            raise HTTPException(status_code=409, detail="The manager account is already configured")
        username = payload.username.strip()
        if len(username) < 3:
            raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
        user = UserAccount(
            username=username,
            password_hash=hash_password(payload.password),
            role="manager",
            active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return {"token": create_access_token(user), "user": _user_dict(user)}


@app.post("/auth/login")
def login(payload: LoginRequest):
    with Session(engine) as session:
        users = session.exec(select(UserAccount)).all()
        user = next(
            (row for row in users if row.username.strip().lower() == payload.username.strip().lower()),
            None,
        )
        if not user or not user.active:
            raise HTTPException(status_code=401, detail="No account found with that username")
        if not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Wrong password")
        return {"token": create_access_token(user), "user": _user_dict(user)}


@app.get("/auth/me")
def get_me(request: Request):
    return _user_dict(user_from_request(request))


@app.patch("/auth/me")
def update_my_account(payload: AccountUpdateRequest, request: Request):
    current = user_from_request(request)
    with Session(engine) as session:
        user = session.get(UserAccount, current.id)
        if not user:
            raise HTTPException(status_code=404, detail="Account not found")
        if payload.username is not None:
            username = payload.username.strip()
            if len(username) < 3:
                raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
            if username_exists(username, exclude_user_id=user.id):
                raise HTTPException(status_code=409, detail="That username is already in use")
            user.username = username
        if payload.new_password:
            if not payload.current_password or not verify_password(payload.current_password, user.password_hash):
                raise HTTPException(status_code=400, detail="Current password is incorrect")
            user.password_hash = hash_password(payload.new_password)
        user.updated_at = datetime.now(timezone.utc).isoformat()
        session.add(user)
        session.commit()
        session.refresh(user)
        return {"token": create_access_token(user), "user": _user_dict(user)}


@app.get("/auth/users")
def list_users(request: Request):
    manager_from_request(request)
    with Session(engine) as session:
        member_ids = session.exec(select(Membership.user_id).where(
            Membership.business_id == current_business_id(), Membership.active == True  # noqa: E712
        )).all()
        return [_user_dict(row) for row in session.exec(select(UserAccount).where(UserAccount.id.in_(member_ids))).all()]


@app.post("/auth/users")
def create_user(payload: CreateUserRequest, request: Request):
    manager_from_request(request)
    username = payload.username.strip()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if username_exists(username):
        raise HTTPException(status_code=409, detail="That username is already in use")
    with Session(engine) as session:
        if payload.employee_id is not None and not session.get(Employee, payload.employee_id):
            raise HTTPException(status_code=404, detail="Employee not found")
        user = UserAccount(
            username=username,
            password_hash=hash_password(payload.password),
            role=payload.role,
            employee_id=payload.employee_id,
            active=True,
        )
        session.add(user)
        session.flush()
        session.add(Membership(
            business_id=current_business_id(), user_id=user.id,
            role="manager" if payload.role == "manager" else "employee",
        ))
        session.commit()
        session.refresh(user)
        return _user_dict(user)


@app.patch("/auth/users/{user_id}")
def update_user(user_id: int, payload: AdminUserUpdateRequest, request: Request):
    manager = manager_from_request(request)
    with Session(engine) as session:
        user = session.get(UserAccount, user_id)
        membership = session.exec(select(Membership).where(
            Membership.business_id == current_business_id(), Membership.user_id == user_id,
            Membership.active == True,  # noqa: E712
        )).first()
        if not user or not membership:
            raise HTTPException(status_code=404, detail="Account not found")
        if payload.username is not None:
            username = payload.username.strip()
            if username_exists(username, exclude_user_id=user.id):
                raise HTTPException(status_code=409, detail="That username is already in use")
            user.username = username
        if payload.role is not None:
            user.role = payload.role
            membership.role = "manager" if payload.role == "manager" else "employee"
        if payload.employee_id is not None:
            if not session.get(Employee, payload.employee_id):
                raise HTTPException(status_code=404, detail="Employee not found")
            user.employee_id = payload.employee_id
        if payload.active is not None:
            if user.id == manager.id and not payload.active:
                raise HTTPException(status_code=400, detail="You cannot disable your own account")
            user.active = payload.active
        if payload.new_password:
            user.password_hash = hash_password(payload.new_password)
        user.updated_at = datetime.now(timezone.utc).isoformat()
        session.add(user)
        session.commit()
        session.refresh(user)
        return _user_dict(user)


@app.get("/my/profile")
def my_profile(request: Request):
    user = user_from_request(request)
    if not user.employee_id:
        return {"user": _user_dict(user), "employee": None}
    with Session(engine) as session:
        employee = session.get(Employee, user.employee_id)
        return {"user": _user_dict(user), "employee": employee}


@app.get("/my/schedule")
def my_schedule(week_start: str, request: Request):
    user = user_from_request(request)
    if not user.employee_id:
        return {"schedule": None, "shifts": []}
    with Session(engine) as session:
        schedules = session.exec(
            select(Schedule).where(Schedule.week_start == week_start)
        ).all()
        published = sorted(
            [row for row in schedules if row.status == "published"],
            key=lambda row: (row.version, row.id or 0),
            reverse=True,
        )
        schedule = published[0] if published else None
        if not schedule:
            return {"schedule": None, "shifts": []}
        shifts = session.exec(
            select(ScheduleShift)
            .where(ScheduleShift.schedule_id == schedule.id)
            .where(ScheduleShift.employee_id == user.employee_id)
        ).all()
        return {"schedule": schedule, "shifts": shifts}


@app.get("/my/availability")
def my_availability(request: Request):
    user = user_from_request(request)
    if not user.employee_id:
        return {"recurring": [], "temporary": []}
    with Session(engine) as session:
        recurring = session.exec(
            select(RecurringAvailability).where(RecurringAvailability.employee_id == user.employee_id)
        ).all()
        temporary = session.exec(
            select(TemporaryUnavailability).where(TemporaryUnavailability.employee_id == user.employee_id)
        ).all()
        return {"recurring": recurring, "temporary": temporary}


@app.get("/my/requests")
def my_requests(request: Request):
    user = user_from_request(request)
    with Session(engine) as session:
        return session.exec(
            select(AvailabilityRequest).where(AvailabilityRequest.user_id == user.id)
        ).all()


@app.post("/my/requests")
def create_my_request(payload: AvailabilityRequestPayload, request: Request):
    user = user_from_request(request)
    if not user.employee_id:
        raise HTTPException(status_code=400, detail="This account is not linked to an employee")
    if payload.request_type in {"day_off", "temporary_change"} and not payload.start_date:
        raise HTTPException(status_code=400, detail="Choose a date")
    with Session(engine) as session:
        item = AvailabilityRequest(
            user_id=user.id,
            employee_id=user.employee_id,
            **payload.model_dump(),
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        return item


@app.get("/availability-requests")
def list_availability_requests(status: Optional[str] = None, request: Request = None):
    manager_from_request(request)
    with Session(engine) as session:
        rows = session.exec(select(AvailabilityRequest)).all()
        if status:
            rows = [row for row in rows if row.status == status]
        employees = {row.id: row.name for row in session.exec(select(Employee)).all()}
        return [
            {**row.model_dump(), "employee_name": employees.get(row.employee_id, "Employee")}
            for row in sorted(rows, key=lambda row: row.created_at, reverse=True)
        ]


@app.patch("/availability-requests/{request_id}")
def review_availability_request(
    request_id: int,
    payload: ReviewAvailabilityRequest,
    request: Request,
):
    manager = manager_from_request(request)
    with Session(engine) as session:
        item = session.get(AvailabilityRequest, request_id)
        if not item:
            raise HTTPException(status_code=404, detail="Request not found")
        if item.status != "pending":
            raise HTTPException(status_code=400, detail="This request was already reviewed")
        item.status = payload.status
        item.manager_note = payload.manager_note
        item.reviewed_at = datetime.now(timezone.utc).isoformat()
        item.reviewed_by_user_id = manager.id
        session.add(item)
        if payload.status == "approved":
            if item.request_type == "recurring_change":
                session.add(
                    RecurringAvailability(
                        employee_id=item.employee_id,
                        rule_type=item.rule_type,
                        day_of_week=item.day_of_week,
                        start_time=item.start_time,
                        end_time=item.end_time,
                    )
                )
            else:
                session.add(
                    TemporaryUnavailability(
                        employee_id=item.employee_id,
                        start_date=item.start_date,
                        end_date=item.end_date or item.start_date,
                        start_time=item.start_time,
                        end_time=item.end_time,
                    )
                )
        session.commit()
        session.refresh(item)
        return item


@app.get("/notifications")
def notifications(request: Request):
    user = user_from_request(request)
    with Session(engine) as session:
        if user.role == "manager":
            pending = session.exec(
                select(AvailabilityRequest).where(AvailabilityRequest.status == "pending")
            ).all()
            warnings = session.exec(select(ScheduleWarning)).all()
            return {
                "unread_count": len(pending),
                "pending_requests": len(pending),
                "schedule_warnings": len(warnings),
            }
        requests = session.exec(
            select(AvailabilityRequest).where(AvailabilityRequest.user_id == user.id)
        ).all()
        reviewed = [row for row in requests if row.status in {"approved", "denied"}]
        return {
            "unread_count": len(reviewed),
            "pending_requests": len([row for row in requests if row.status == "pending"]),
            "reviewed_requests": len(reviewed),
        }


def seed_defaults() -> None:
    with Session(engine) as session:
        settings = session.exec(select(ManagerSettings)).first()
        if not settings:
            settings = ManagerSettings()
        settings.store_name = "Business"
        settings.shift_lead_hourly_rate = settings.employee_hourly_rate + 1.0
        settings.gm_hourly_rate = settings.employee_hourly_rate + 1.0
        if settings.max_labor_percent < settings.min_labor_percent:
            settings.min_labor_percent, settings.max_labor_percent = (
                settings.max_labor_percent,
                settings.min_labor_percent,
            )
        settings.default_labor_percent = (
            settings.min_labor_percent + settings.max_labor_percent
        ) / 2
        session.add(settings)

        existing_positions = session.exec(select(Position)).all()
        used_position_ids = {row.position_id for row in session.exec(select(EmployeePosition)).all()}
        used_position_ids |= {row.position_id for row in session.exec(select(ScheduleShift)).all() if row.position_id}
        starter_names = {"register", "runner", "expo", "sandwich", "salad", "prep", "dish"}
        for position in existing_positions:
            if position.name.lower() in starter_names and position.id not in used_position_ids:
                session.delete(position)
        remaining_positions = [row for row in existing_positions if row.id in used_position_ids or row.name.lower() not in starter_names]
        existing_departments = session.exec(select(Department)).all()
        known = {row.name.lower() for row in existing_departments}
        department_names = {row.department for row in remaining_positions}
        department_names |= {row.department for row in session.exec(select(Employee)).all()}
        if not department_names:
            department_names = {"General"}
        for name in sorted(department_names):
            if name.lower() not in known:
                session.add(Department(name=name, active=True))
        session.commit()


@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()
    seed_defaults()


@app.get("/api/status")
def api_status():
    return {"message": "Scheduling Assistant backend is running"}


@app.get("/health")
def health_check():
    return {"status": "ok", "ai_configured": ai_is_configured()}


# ---------------------------------------------------------------------------
# Departments, employees, and position abilities
# ---------------------------------------------------------------------------


@app.get("/departments")
def list_departments(session: Session = Depends(get_session)):
    return session.exec(select(Department).where(Department.active == True).order_by(Department.name)).all()  # noqa: E712


@app.post("/departments")
def create_department(department: Department, session: Session = Depends(get_session)):
    department.name = department.name.strip()
    if not department.name:
        raise HTTPException(status_code=400, detail="Department name is required")
    if any(row.name.lower() == department.name.lower() for row in session.exec(select(Department)).all()):
        raise HTTPException(status_code=409, detail="That department already exists")
    session.add(department); session.commit(); session.refresh(department)
    return department


@app.delete("/departments/{department_id}")
def delete_department(department_id: int, session: Session = Depends(get_session)):
    department = session.get(Department, department_id)
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    if session.exec(select(Employee).where(Employee.department == department.name)).first() or session.exec(select(Position).where(Position.department == department.name)).first():
        raise HTTPException(status_code=409, detail="Move or remove this department's people and positions first")
    session.delete(department); session.commit()
    return {"deleted": True}


@app.get("/employees")
def list_employees(session: Session = Depends(get_session)):
    return session.exec(select(Employee)).all()


@app.post("/employees")
def create_employee(employee: Employee, session: Session = Depends(get_session)):
    employee.name = employee.name.strip()
    employee.hourly_rate_override = None
    if not employee.name:
        raise HTTPException(status_code=400, detail="Employee name cannot be blank")
    if not _department_exists(session, employee.department):
        raise HTTPException(status_code=400, detail="Choose an active department")
    if employee.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Invalid employee role")
    if employee.max_hours_per_week < employee.min_hours_per_week:
        raise HTTPException(status_code=400, detail="Maximum hours cannot be below minimum hours")
    session.add(employee)
    session.commit()
    session.refresh(employee)
    return employee


@app.patch("/employees/{employee_id}")
def update_employee(
    employee_id: int,
    update: EmployeeUpdate,
    session: Session = Depends(get_session),
):
    employee = session.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    values = update.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(employee, key, value)

    employee.name = employee.name.strip()
    employee.hourly_rate_override = None
    if not employee.name:
        raise HTTPException(status_code=400, detail="Employee name cannot be blank")
    if employee.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Invalid employee role")
    if employee.max_hours_per_week < employee.min_hours_per_week:
        raise HTTPException(status_code=400, detail="Maximum hours cannot be below minimum hours")

    session.add(employee)
    session.commit()
    session.refresh(employee)
    return employee


@app.delete("/employees/{employee_id}")
def delete_employee(employee_id: int, session: Session = Depends(get_session)):
    employee = session.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    for model in (EmployeePosition, RecurringAvailability, TemporaryUnavailability):
        for row in session.exec(select(model).where(model.employee_id == employee_id)).all():
            session.delete(row)

    employee.active = False
    session.add(employee)
    session.commit()
    return {"deleted": True}


@app.get("/employee-positions")
def list_employee_positions(
    employee_id: Optional[int] = None,
    session: Session = Depends(get_session),
):
    query = select(EmployeePosition)
    if employee_id is not None:
        query = query.where(EmployeePosition.employee_id == employee_id)
    return session.exec(query).all()


@app.put("/employees/{employee_id}/positions")
def replace_employee_positions(
    employee_id: int,
    payload: EmployeePositionList,
    session: Session = Depends(get_session),
):
    employee = session.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    for row in session.exec(
        select(EmployeePosition).where(EmployeePosition.employee_id == employee_id)
    ).all():
        session.delete(row)

    preferred_used = False
    saved = []
    for item in payload.positions:
        position = session.get(Position, item.position_id)
        if not position or not position.active or position.department != employee.department:
            continue
        preferred = item.preferred and not preferred_used
        preferred_used = preferred_used or preferred
        row = EmployeePosition(
            employee_id=employee_id,
            position_id=item.position_id,
            trainee=item.trainee,
            preferred=preferred,
        )
        session.add(row)
        saved.append(row)

    session.commit()
    for row in saved:
        session.refresh(row)
    return saved


# ---------------------------------------------------------------------------
# Positions
# ---------------------------------------------------------------------------


@app.get("/positions")
def list_positions(
    department: Optional[str] = None,
    include_inactive: bool = False,
    session: Session = Depends(get_session),
):
    positions = session.exec(select(Position)).all()
    if not include_inactive:
        positions = [position for position in positions if position.active]
    if department:
        positions = [position for position in positions if position.department == department]
    return positions


@app.post("/positions")
def create_position(position: Position, session: Session = Depends(get_session)):
    position.name = position.name.strip()
    if not position.name:
        raise HTTPException(status_code=400, detail="Position name cannot be blank")
    if not _department_exists(session, position.department):
        raise HTTPException(status_code=400, detail="Choose an active department")

    duplicate = next(
        (
            item
            for item in session.exec(select(Position)).all()
            if item.department == position.department
            and item.name.lower() == position.name.lower()
            and item.active
        ),
        None,
    )
    if duplicate:
        return duplicate

    session.add(position)
    session.commit()
    session.refresh(position)
    return position


@app.patch("/positions/{position_id}")
def update_position(
    position_id: int,
    update: PositionUpdate,
    session: Session = Depends(get_session),
):
    position = session.get(Position, position_id)
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    for key, value in update.model_dump(exclude_unset=True).items():
        setattr(position, key, value)
    position.name = position.name.strip()
    if not position.name:
        raise HTTPException(status_code=400, detail="Position name cannot be blank")
    if not _department_exists(session, position.department):
        raise HTTPException(status_code=400, detail="Choose an active department")
    session.add(position)
    session.commit()
    session.refresh(position)
    return position


def _coverage_rule_position_ids(rule: CoverageRule) -> list[int]:
    try:
        rows = json.loads(rule.position_ids_json or "[]")
        values = [int(item) for item in rows]
    except (TypeError, ValueError, json.JSONDecodeError):
        values = []
    if not values and rule.position_id:
        values = [rule.position_id]
    return values


@app.delete("/positions/{position_id}")
def delete_position(position_id: int, session: Session = Depends(get_session)):
    position = session.get(Position, position_id)
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")

    in_employee_use = session.exec(
        select(EmployeePosition).where(EmployeePosition.position_id == position_id)
    ).first()
    in_coverage_use = any(
        position_id in _coverage_rule_position_ids(rule)
        for rule in session.exec(select(CoverageRule)).all()
        if rule.active
    )
    if in_employee_use or in_coverage_use:
        raise HTTPException(
            status_code=409,
            detail="Remove this position from employees and coverage rules first",
        )

    position.active = False
    session.add(position)
    session.commit()
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


@app.get("/availability")
def list_availability(
    employee_id: Optional[int] = None,
    session: Session = Depends(get_session),
):
    query = select(RecurringAvailability)
    if employee_id is not None:
        query = query.where(RecurringAvailability.employee_id == employee_id)
    return session.exec(query).all()


@app.post("/availability")
def create_availability(
    availability: RecurringAvailability,
    session: Session = Depends(get_session),
):
    if availability.rule_type not in {"unavailable", "preferred"}:
        raise HTTPException(status_code=400, detail="Invalid availability rule type")
    session.add(availability)
    session.commit()
    session.refresh(availability)
    return availability


@app.patch("/availability/{availability_id}")
def update_availability(
    availability_id: int,
    update: AvailabilityUpdate,
    session: Session = Depends(get_session),
):
    availability = session.get(RecurringAvailability, availability_id)
    if not availability:
        raise HTTPException(status_code=404, detail="Availability rule not found")
    for key, value in update.model_dump(exclude_unset=True).items():
        setattr(availability, key, value)
    if availability.rule_type not in {"unavailable", "preferred"}:
        raise HTTPException(status_code=400, detail="Invalid availability rule type")
    session.add(availability)
    session.commit()
    session.refresh(availability)
    return availability


@app.delete("/availability/{availability_id}")
def delete_availability(
    availability_id: int,
    session: Session = Depends(get_session),
):
    availability = session.get(RecurringAvailability, availability_id)
    if not availability:
        raise HTTPException(status_code=404, detail="Availability rule not found")
    session.delete(availability)
    session.commit()
    return {"deleted": True}


@app.get("/temporary-unavailability")
def list_temporary_unavailability(
    employee_id: Optional[int] = None,
    session: Session = Depends(get_session),
):
    query = select(TemporaryUnavailability)
    if employee_id is not None:
        query = query.where(TemporaryUnavailability.employee_id == employee_id)
    return session.exec(query).all()


def _validate_temporary(item: TemporaryUnavailability) -> None:
    if not item.start_date:
        raise HTTPException(status_code=400, detail="Choose a start date")
    if not item.end_date:
        item.end_date = item.start_date
    if item.end_date < item.start_date:
        raise HTTPException(status_code=400, detail="End date cannot be before start date")


@app.post("/temporary-unavailability")
def create_temporary_unavailability(
    item: TemporaryUnavailability,
    session: Session = Depends(get_session),
):
    _validate_temporary(item)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@app.patch("/temporary-unavailability/{item_id}")
def update_temporary_unavailability(
    item_id: int,
    update: TemporaryAvailabilityUpdate,
    session: Session = Depends(get_session),
):
    item = session.get(TemporaryUnavailability, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Temporary rule not found")
    for key, value in update.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    _validate_temporary(item)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@app.delete("/temporary-unavailability/{item_id}")
def delete_temporary_unavailability(
    item_id: int,
    session: Session = Depends(get_session),
):
    item = session.get(TemporaryUnavailability, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Temporary rule not found")
    session.delete(item)
    session.commit()
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Manager settings and labor blocks
# ---------------------------------------------------------------------------


@app.get("/manager-settings")
def get_manager_settings(session: Session = Depends(get_session)):
    settings = session.exec(select(ManagerSettings)).first()
    if not settings:
        settings = ManagerSettings()
        session.add(settings)
        session.commit()
        session.refresh(settings)
    return settings


@app.put("/manager-settings")
def update_manager_settings(
    settings_update: ManagerSettings,
    session: Session = Depends(get_session),
):
    settings = session.exec(select(ManagerSettings)).first()
    if not settings:
        settings = settings_update
    else:
        for key, value in settings_update.model_dump(exclude={"id"}).items():
            setattr(settings, key, value)
    # Fixed store and wage policy: leadership is exactly +$1.
    settings.shift_lead_hourly_rate = settings.employee_hourly_rate + 1.0
    settings.gm_hourly_rate = settings.employee_hourly_rate + 1.0
    if settings.max_labor_percent < settings.min_labor_percent:
        settings.min_labor_percent, settings.max_labor_percent = (
            settings.max_labor_percent,
            settings.min_labor_percent,
        )
    settings.default_labor_percent = (
        settings.min_labor_percent + settings.max_labor_percent
    ) / 2
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return settings


@app.get("/labor-projections")
def list_labor_projections(
    week_start: Optional[str] = None,
    date_value: Optional[str] = None,
    session: Session = Depends(get_session),
):
    rows = session.exec(select(LaborProjection)).all()
    if date_value:
        rows = [row for row in rows if row.date == date_value]
    elif week_start:
        first = datetime.strptime(week_start, "%Y-%m-%d").date()
        dates = {(first + timedelta(days=index)).isoformat() for index in range(7)}
        rows = [row for row in rows if row.date in dates]
    return sorted(rows, key=lambda row: (row.date, row.start_time, row.end_time))


def _validate_projection(projection: LaborProjection, session: Session) -> None:
    has_limit = any(
        value is not None
        for value in (
            projection.projected_sales,
            projection.max_labor_hours,
            projection.max_labor_dollars,
        )
    )
    if not has_limit:
        raise HTTPException(status_code=400, detail="Enter at least one labor limit")
    if projection.start_time and not projection.end_time:
        raise HTTPException(status_code=400, detail="Choose an end time")
    if projection.end_time and not projection.start_time:
        raise HTTPException(status_code=400, detail="Choose a start time")
    if projection.start_time and parse_time(projection.end_time) <= parse_time(projection.start_time):
        raise HTTPException(status_code=400, detail="End time must be after start time")
    if projection.projected_sales is not None:
        settings = session.exec(select(ManagerSettings)).first() or ManagerSettings()
        if projection.min_labor_percent is None:
            projection.min_labor_percent = settings.min_labor_percent
        if projection.max_labor_percent is None:
            projection.max_labor_percent = settings.max_labor_percent
        if projection.max_labor_percent < projection.min_labor_percent:
            projection.min_labor_percent, projection.max_labor_percent = (
                projection.max_labor_percent,
                projection.min_labor_percent,
            )
        projection.labor_percent = (
            projection.min_labor_percent + projection.max_labor_percent
        ) / 2


@app.post("/labor-projections")
def create_labor_projection(
    projection: LaborProjection,
    session: Session = Depends(get_session),
):
    _validate_projection(projection, session)
    session.add(projection)
    session.commit()
    session.refresh(projection)
    return projection


@app.patch("/labor-projections/{projection_id}")
def update_labor_projection(
    projection_id: int,
    update: LaborProjectionUpdate,
    session: Session = Depends(get_session),
):
    projection = session.get(LaborProjection, projection_id)
    if not projection:
        raise HTTPException(status_code=404, detail="Labor projection not found")
    values = update.model_dump(exclude_unset=True)
    # Clear mutually exclusive budget fields whenever one family is explicitly supplied.
    if "projected_sales" in values and values["projected_sales"] is not None:
        projection.max_labor_hours = None
        projection.max_labor_dollars = None
    if "max_labor_hours" in values and values["max_labor_hours"] is not None:
        projection.projected_sales = None
        projection.labor_percent = None
        projection.min_labor_percent = None
        projection.max_labor_percent = None
        projection.max_labor_dollars = None
    if "max_labor_dollars" in values and values["max_labor_dollars"] is not None:
        projection.projected_sales = None
        projection.labor_percent = None
        projection.min_labor_percent = None
        projection.max_labor_percent = None
        projection.max_labor_hours = None
    for key, value in values.items():
        setattr(projection, key, value)
    _validate_projection(projection, session)
    session.add(projection)
    session.commit()
    session.refresh(projection)
    return projection


@app.delete("/labor-projections/{projection_id}")
def delete_labor_projection(
    projection_id: int,
    session: Session = Depends(get_session),
):
    projection = session.get(LaborProjection, projection_id)
    if not projection:
        raise HTTPException(status_code=404, detail="Labor projection not found")
    session.delete(projection)
    session.commit()
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Projected Crew targets (legacy endpoint name kept for compatibility)
# ---------------------------------------------------------------------------


def _clean_coverage_payload(payload: CoverageRulePayload, session: Session) -> CoverageRulePayload:
    payload.name = payload.name.strip()
    if not payload.name:
        raise HTTPException(status_code=400, detail="Crew target name cannot be blank")
    if not payload.start_time or not payload.end_time:
        raise HTTPException(status_code=400, detail="Crew target start and end times are required")
    if parse_time(payload.end_time) <= parse_time(payload.start_time):
        raise HTTPException(status_code=400, detail="Crew target end time must be after start time")
    payload.departments = [item for item in payload.departments if _department_exists(session, item)]
    payload.roles = [item for item in payload.roles if item in VALID_ROLES]
    active_position_ids = {
        item.id
        for item in session.exec(select(Position)).all()
        if item.active and item.id is not None
    }
    payload.position_ids = list(dict.fromkeys(
        item for item in payload.position_ids if item in active_position_ids
    ))
    payload.minimum_count = max(0, payload.minimum_count)
    payload.preferred_count = max(payload.minimum_count, payload.preferred_count)
    return payload


def _apply_coverage_payload(rule: CoverageRule, payload: CoverageRulePayload) -> None:
    rule.name = payload.name
    rule.date = payload.date
    rule.day_of_week = payload.day_of_week
    rule.start_time = payload.start_time
    rule.end_time = payload.end_time
    rule.target_type = "multi"
    rule.position_ids_json = json.dumps(payload.position_ids)
    rule.departments_json = json.dumps(payload.departments)
    rule.roles_json = json.dumps(payload.roles)
    # Keep first values in old fields for backward compatibility.
    rule.position_id = payload.position_ids[0] if payload.position_ids else None
    rule.department = payload.departments[0] if payload.departments else None
    rule.role = payload.roles[0] if payload.roles else None
    rule.minimum_count = payload.minimum_count
    rule.preferred_count = payload.preferred_count
    rule.hard_minimum = payload.hard_minimum
    rule.active = payload.active


def _coverage_dict(rule: CoverageRule) -> dict:
    def load(value: str) -> list:
        try:
            parsed = json.loads(value or "[]")
            return parsed if isinstance(parsed, list) else []
        except (TypeError, ValueError, json.JSONDecodeError):
            return []

    position_ids = load(rule.position_ids_json)
    departments = load(rule.departments_json)
    roles = load(rule.roles_json)
    if not position_ids and rule.position_id:
        position_ids = [rule.position_id]
    if not departments and rule.department:
        departments = [rule.department]
    if not roles and rule.role:
        roles = [rule.role]
    return {
        **rule.model_dump(),
        "position_ids": position_ids,
        "departments": departments,
        "roles": roles,
    }


@app.get("/coverage-rules")
@app.get("/crew-targets")
def list_coverage_rules(session: Session = Depends(get_session)):
    return [_coverage_dict(row) for row in session.exec(select(CoverageRule)).all()]


@app.post("/coverage-rules")
@app.post("/crew-targets")
def create_coverage_rule(
    payload: CoverageRulePayload,
    session: Session = Depends(get_session),
):
    payload = _clean_coverage_payload(payload, session)
    rule = CoverageRule(name=payload.name, start_time=payload.start_time, end_time=payload.end_time)
    _apply_coverage_payload(rule, payload)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return _coverage_dict(rule)


@app.patch("/coverage-rules/{rule_id}")
@app.patch("/crew-targets/{rule_id}")
def update_coverage_rule(
    rule_id: int,
    payload: CoverageRulePayload,
    session: Session = Depends(get_session),
):
    rule = session.get(CoverageRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Crew target not found")
    payload = _clean_coverage_payload(payload, session)
    _apply_coverage_payload(rule, payload)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return _coverage_dict(rule)


@app.delete("/coverage-rules/{rule_id}")
@app.delete("/crew-targets/{rule_id}")
def delete_coverage_rule(rule_id: int, session: Session = Depends(get_session)):
    rule = session.get(CoverageRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Crew target not found")
    session.delete(rule)
    session.commit()
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Schedules and manual edits
# ---------------------------------------------------------------------------


@app.get("/schedules")
def list_schedules(
    week_start: str,
    session: Session = Depends(get_session),
):
    rows = session.exec(select(Schedule).where(Schedule.week_start == week_start)).all()
    return sorted(rows, key=lambda row: row.version, reverse=True)


@app.get("/schedules/{schedule_id}")
def get_schedule(schedule_id: int, session: Session = Depends(get_session)):
    try:
        return schedule_detail(session, schedule_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/schedules/generate")
def create_or_regenerate_schedule(
    request: GenerateScheduleRequest,
    session: Session = Depends(get_session),
):
    try:
        return generate_schedule(
            session,
            week_start=request.week_start,
            source_schedule_id=request.source_schedule_id,
            scope=request.scope,
            selected_date=request.selected_date,
            labor_tolerance_percent=request.labor_tolerance_percent,
            staffing_level=request.staffing_level,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/schedules/{schedule_id}/publish")
def publish_schedule(schedule_id: int, session: Session = Depends(get_session)):
    schedule = session.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    for row in session.exec(select(Schedule).where(Schedule.week_start == schedule.week_start)).all():
        if row.status == "published":
            row.status = "draft"
            session.add(row)

    schedule.status = "published"
    session.add(schedule)
    session.commit()
    return schedule_detail(session, schedule_id)


@app.patch("/schedule-shifts/{shift_id}")
def update_schedule_shift(
    shift_id: int,
    update: ScheduleShiftUpdate,
    session: Session = Depends(get_session),
):
    shift = session.get(ScheduleShift, shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Schedule shift not found")
    for key, value in update.model_dump(exclude_unset=True).items():
        setattr(shift, key, value)
    if shift.employee_id:
        employee = session.get(Employee, shift.employee_id)
        if not employee or not employee.active:
            raise HTTPException(status_code=400, detail="Choose an active employee")
        shift.role = employee.role
    if parse_time(shift.end_time) <= parse_time(shift.start_time):
        raise HTTPException(status_code=400, detail="Shift end must be after start")
    shift.locked = True if update.locked is None else shift.locked
    session.add(shift)
    session.commit()
    session.refresh(shift)
    return shift


@app.post("/schedules/{schedule_id}/shifts")
def add_manual_schedule_shift(
    schedule_id: int,
    payload: ManualShiftCreate,
    session: Session = Depends(get_session),
):
    schedule = session.get(Schedule, schedule_id)
    employee = session.get(Employee, payload.employee_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    if not employee or not employee.active:
        raise HTTPException(status_code=400, detail="Choose an active employee")
    if parse_time(payload.end_time) <= parse_time(payload.start_time):
        raise HTTPException(status_code=400, detail="Shift end must be after start")
    shift = ScheduleShift(
        schedule_id=schedule_id,
        date=payload.date,
        employee_id=payload.employee_id,
        position_id=payload.position_id,
        role=employee.role,
        start_time=payload.start_time,
        end_time=payload.end_time,
        locked=payload.locked,
    )
    session.add(shift)
    session.commit()
    session.refresh(shift)
    return shift


@app.delete("/schedule-shifts/{shift_id}")
def delete_schedule_shift(shift_id: int, session: Session = Depends(get_session)):
    shift = session.get(ScheduleShift, shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Schedule shift not found")
    session.delete(shift)
    session.commit()
    return {"deleted": True}


# ---------------------------------------------------------------------------
# AI assistant: OpenAI when configured, deterministic fallback otherwise
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# AI assistant: OpenAI when configured, deterministic fallback otherwise
# ---------------------------------------------------------------------------


def _get_or_create_assistant_thread(session: Session, user_id: int, thread_id: Optional[int] = None) -> AssistantThread:
    if thread_id:
        thread = session.get(AssistantThread, thread_id)
        if thread and thread.user_id == user_id:
            return thread
    thread = session.exec(
        select(AssistantThread).where(AssistantThread.user_id == user_id)
    ).first()
    if not thread:
        thread = AssistantThread(user_id=user_id, title="Scheduling setup")
        session.add(thread)
        session.commit()
        session.refresh(thread)
    # Adopt chat rows from pre-login builds so the manager does not lose the
    # conversation during this upgrade.
    legacy_messages = session.exec(select(AssistantMessage)).all()
    changed = False
    for message in legacy_messages:
        if message.thread_id is None:
            message.thread_id = thread.id
            message.user_id = user_id
            session.add(message)
            changed = True
    if changed:
        session.commit()
    return thread


def _assistant_context(
    session: Session,
    request: ChatRequest,
    user_id: int,
    thread_id: int,
) -> dict:
    employees = session.exec(select(Employee).where(Employee.active == True)).all()  # noqa: E712
    positions = session.exec(select(Position).where(Position.active == True)).all()  # noqa: E712
    abilities = session.exec(select(EmployeePosition)).all()
    recurring = session.exec(select(RecurringAvailability)).all()
    temporary = session.exec(select(TemporaryUnavailability)).all()
    crew_targets = session.exec(select(CoverageRule).where(CoverageRule.active == True)).all()  # noqa: E712
    labor = session.exec(select(LaborProjection)).all()
    settings = session.exec(select(ManagerSettings)).first() or ManagerSettings()
    business_id = current_business_id()
    business = session.get(Business, business_id)
    contacts = session.exec(select(Contact).where(Contact.business_id == business_id, Contact.active == True)).all()  # noqa: E712
    invoices = session.exec(select(Invoice).where(Invoice.business_id == business_id).order_by(Invoice.id.desc()).limit(100)).all()
    bills = session.exec(select(Bill).where(Bill.business_id == business_id).order_by(Bill.id.desc()).limit(100)).all()
    expenses = session.exec(select(Expense).where(Expense.business_id == business_id).order_by(Expense.id.desc()).limit(100)).all()
    tasks = session.exec(select(TaskItem).where(TaskItem.business_id == business_id).order_by(TaskItem.id.desc()).limit(100)).all()
    checklist_templates = session.exec(select(ChecklistTemplate).where(ChecklistTemplate.business_id == business_id, ChecklistTemplate.active == True)).all()  # noqa: E712
    checklist_runs = session.exec(select(ChecklistRun).where(ChecklistRun.business_id == business_id).order_by(ChecklistRun.id.desc()).limit(50)).all()
    closing_reports = session.exec(select(ClosingReport).where(ClosingReport.business_id == business_id).order_by(ClosingReport.id.desc()).limit(30)).all()
    inventory = session.exec(select(InventoryItem).where(InventoryItem.business_id == business_id, InventoryItem.active == True)).all()  # noqa: E712
    modules = session.exec(select(BusinessModule).where(BusinessModule.business_id == business_id)).all()
    ledger_accounts, ledger_totals = account_balances(session, business_id)
    income_cents = sum(
        ledger_totals[row.id]["credit_cents"] - ledger_totals[row.id]["debit_cents"]
        for row in ledger_accounts if row.account_type == "income"
    )
    expense_cents = sum(
        ledger_totals[row.id]["debit_cents"] - ledger_totals[row.id]["credit_cents"]
        for row in ledger_accounts if row.account_type == "expense"
    )
    memory = session.exec(select(AssistantMemory).where(AssistantMemory.user_id == user_id)).first()
    history_rows = session.exec(
        select(AssistantMessage).where(AssistantMessage.thread_id == thread_id)
    ).all()
    history_rows = sorted(history_rows, key=lambda item: item.id or 0)
    selected_schedule = None
    if request.schedule_id:
        try:
            selected_schedule = schedule_detail(session, request.schedule_id)
        except ValueError:
            selected_schedule = None

    position_by_id = {row.id: row for row in positions}
    abilities_by_employee: dict[int, list[dict]] = {}
    for row in abilities:
        position = position_by_id.get(row.position_id)
        if not position:
            continue
        abilities_by_employee.setdefault(row.employee_id, []).append(
            {
                "position": position.name,
                "department": position.department,
                "trainee": row.trainee,
                "preferred": row.preferred,
            }
        )

    return {
        "business": {
            "id": business_id,
            "name": business.name if business else settings.store_name,
            "industry": business.industry if business else "general",
            "currency": business.currency if business else "USD",
            "enabled_modules": [row.module_key for row in modules if row.enabled],
        },
        "accounting": {
            "summary": {
                "accounts_receivable_cents": sum(max(0, row.total_cents - row.paid_cents) for row in invoices if row.status != "void"),
                "accounts_payable_cents": sum(max(0, row.total_cents - row.paid_cents) for row in bills if row.status != "void"),
                "income_cents": income_cents,
                "expenses_cents": expense_cents,
                "net_income_cents": income_cents - expense_cents,
            },
            "chart_of_accounts": [{"code": row.code, "name": row.name, "type": row.account_type, **ledger_totals[row.id]} for row in ledger_accounts],
            "invoices": [row.model_dump() for row in invoices],
            "bills": [row.model_dump() for row in bills],
            "recent_expenses": [row.model_dump() for row in expenses],
        },
        "contacts": [{"id": row.id, "name": row.name, "company": row.company_name, "type": row.contact_type} for row in contacts],
        "tasks": [row.model_dump() for row in tasks],
        "checklists": {
            "templates": [row.model_dump() for row in checklist_templates],
            "recent_runs": [row.model_dump() for row in checklist_runs],
        },
        "closing_reports": [row.model_dump() for row in closing_reports],
        "inventory": [row.model_dump() for row in inventory],
        "week_start": request.week_start,
        "employees": [
            {
                "id": row.id,
                "name": row.name,
                "department": row.department,
                "role": row.role,
                "min_hours": row.min_hours_per_week,
                "max_hours": row.max_hours_per_week,
                "positions": abilities_by_employee.get(row.id, []),
            }
            for row in employees
        ],
        "positions": [row.model_dump() for row in positions],
        "recurring_availability": [row.model_dump() for row in recurring],
        "temporary_unavailability": [row.model_dump() for row in temporary],
        "labor_projections": [row.model_dump() for row in labor],
        "projected_crew": [_coverage_dict(row) for row in crew_targets],
        "settings": {
            "store": settings.store_name,
            "base_hourly_rate": settings.employee_hourly_rate,
            "leadership_premium": 1.0,
            "min_labor_percent": settings.min_labor_percent,
            "max_labor_percent": settings.max_labor_percent,
            "schedule_extra_with_trainee": settings.schedule_extra_with_trainee,
            "store_open_time": settings.store_open_time,
            "store_close_time": settings.store_close_time,
        },
        "schedule": selected_schedule,
        "always_remember": memory.content if memory else "",
        "conversation_history": [
            {"role": item.role, "content": item.content}
            for item in history_rows
            if item.content.strip()
        ],
    }


POSITION_ALIASES = {
    "sandwich": "Sandwich",
    "sandwiches": "Sandwich",
    "sandwich station": "Sandwich",
    "salad": "Salad",
    "salads": "Salad",
    "dish": "Dish",
    "dishwasher": "Dish",
    "dishwashing": "Dish",
    "cashier": "Register",
    "cashiers": "Register",
    "register": "Register",
    "expo": "Expo",
    "runner": "Runner",
    "prep": "Prep",
}


def _normalize_ai_actions(decision: AssistantDecision, context: dict) -> AssistantDecision:
    saved_positions = context.get("positions") or []
    created_departments = {
        (action.name or action.employee_name or "").strip().lower(): action.department
        for action in decision.actions
        if action.type == "create_employee"
    }
    existing_create_keys = {
        ((action.department or "").upper(), (action.name or action.position_name or "").strip().lower())
        for action in decision.actions
        if action.type == "create_position"
    }
    added_position_actions: list[AssistantAction] = []

    def resolve(name: str, department: Optional[str]) -> str:
        raw = name.strip()
        alias = POSITION_ALIASES.get(raw.lower(), raw.title())
        candidates = [
            row for row in saved_positions
            if str(row.get("name", "")).strip().lower() == alias.lower()
            and (not department or row.get("department") == department)
        ]
        if candidates:
            return str(candidates[0]["name"])
        fallback_department = department or (saved_positions[0].get("department") if saved_positions else None) or "General"
        key = (fallback_department.upper(), alias.lower())
        if key not in existing_create_keys:
            added_position_actions.append(
                AssistantAction(
                    type="create_position",
                    name=alias,
                    position_name=alias,
                    department=fallback_department,
                    reason=f"Add the missing {fallback_department} position before assigning it.",
                )
            )
            existing_create_keys.add(key)
        return alias

    for action in decision.actions:
        if action.type == "set_employee_positions":
            employee_key = (action.employee_name or action.name or "").strip().lower()
            department = action.department or created_departments.get(employee_key)
            action.position_names = [resolve(name, department) for name in action.position_names]
            action.trainee_position_names = [resolve(name, department) for name in action.trainee_position_names]
            if action.preferred_position_name:
                action.preferred_position_name = resolve(action.preferred_position_name, department)
        elif action.type == "create_crew_target":
            department = action.departments[0] if len(action.departments) == 1 else None
            action.position_names = [resolve(name, department) for name in action.position_names]

    if added_position_actions:
        first_position_assignment = next(
            (index for index, action in enumerate(decision.actions) if action.type in {"set_employee_positions", "create_crew_target"}),
            len(decision.actions),
        )
        decision.actions[first_position_assignment:first_position_assignment] = added_position_actions
    return decision


@app.get("/assistant/status")
def assistant_status():
    return {
        "ai_configured": ai_is_configured(),
        "mode": "openai" if ai_is_configured() else "fallback",
    }


@app.get("/assistant/thread")
def assistant_thread(request: Request, session: Session = Depends(get_session)):
    user = manager_from_request(request)
    thread = _get_or_create_assistant_thread(session, user.id)
    memory = session.exec(select(AssistantMemory).where(AssistantMemory.user_id == user.id)).first()
    messages = session.exec(
        select(AssistantMessage).where(AssistantMessage.thread_id == thread.id)
    ).all()
    messages = sorted(messages, key=lambda item: item.id or 0)
    return {
        "thread": thread,
        "memory": memory.content if memory else "",
        "messages": [
            {
                **item.model_dump(),
                "actions": json.loads(item.actions_json or "[]"),
            }
            for item in messages
        ],
    }


@app.delete("/assistant/thread")
def clear_assistant_thread(request: Request, session: Session = Depends(get_session)):
    user = manager_from_request(request)
    thread = _get_or_create_assistant_thread(session, user.id)
    rows = session.exec(select(AssistantMessage).where(AssistantMessage.thread_id == thread.id)).all()
    for row in rows:
        session.delete(row)
    thread.updated_at = datetime.now(timezone.utc).isoformat()
    session.add(thread)
    session.commit()
    return {"cleared": True}


@app.put("/assistant/memory")
def update_assistant_memory(
    payload: AssistantMemoryUpdate,
    request: Request,
    session: Session = Depends(get_session),
):
    user = manager_from_request(request)
    memory = session.exec(select(AssistantMemory).where(AssistantMemory.user_id == user.id)).first()
    if not memory:
        memory = AssistantMemory(user_id=user.id)
    memory.content = payload.content.strip()
    memory.updated_at = datetime.now(timezone.utc).isoformat()
    session.add(memory)
    session.commit()
    session.refresh(memory)
    return memory


@app.post("/assistant/chat")
def assistant_chat(
    payload: ChatRequest,
    request: Request,
    session: Session = Depends(get_session),
):
    user = manager_from_request(request)
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be blank")
    thread = _get_or_create_assistant_thread(session, user.id, payload.thread_id)
    context = _assistant_context(session, payload, user.id, thread.id)
    decision, used_openai = decide_with_ai(message, context)
    decision = _normalize_ai_actions(decision, context)
    user_message = AssistantMessage(
        user_id=user.id,
        thread_id=thread.id,
        role="user",
        content=message,
    )
    assistant_message = AssistantMessage(
        user_id=user.id,
        thread_id=thread.id,
        role="assistant",
        content=decision.reply,
        actions_json=json.dumps([item.model_dump() for item in decision.actions]),
    )
    thread.updated_at = datetime.now(timezone.utc).isoformat()
    session.add(user_message)
    session.add(assistant_message)
    session.add(thread)
    session.commit()
    session.refresh(assistant_message)
    return {
        "thread_id": thread.id,
        "message_id": assistant_message.id,
        "reply": decision.reply,
        "actions": [item.model_dump() for item in decision.actions],
        "ai_used": used_openai,
    }


def _clone_schedule_exact(session: Session, schedule: Schedule) -> Schedule:
    existing = session.exec(select(Schedule).where(Schedule.week_start == schedule.week_start)).all()
    clone = Schedule(
        week_start=schedule.week_start,
        version=max([row.version for row in existing], default=0) + 1,
        status="draft",
        source_schedule_id=schedule.id,
        generation_scope="assistant_edit",
        labor_tolerance_percent=schedule.labor_tolerance_percent,
        staffing_level=schedule.staffing_level,
    )
    session.add(clone)
    session.commit()
    session.refresh(clone)

    old_shifts = session.exec(
        select(ScheduleShift).where(ScheduleShift.schedule_id == schedule.id)
    ).all()
    for shift in old_shifts:
        session.add(
            ScheduleShift(
                schedule_id=clone.id,
                date=shift.date,
                employee_id=shift.employee_id,
                position_id=shift.position_id,
                role=shift.role,
                start_time=shift.start_time,
                end_time=shift.end_time,
                locked=shift.locked,
                source_rule_id=shift.source_rule_id,
            )
        )
    old_warnings = session.exec(
        select(ScheduleWarning).where(ScheduleWarning.schedule_id == schedule.id)
    ).all()
    for warning in old_warnings:
        session.add(
            ScheduleWarning(
                schedule_id=clone.id,
                date=warning.date,
                severity=warning.severity,
                code=warning.code,
                message=warning.message,
                shift_id=None,
            )
        )
    session.commit()
    return clone


def _find_named_employee(session: Session, name: str) -> Employee:
    normalized = name.strip().lower()
    active = session.exec(select(Employee).where(Employee.active == True)).all()  # noqa: E712
    exact = [row for row in active if row.name.lower() == normalized]
    partial = [row for row in active if normalized in row.name.lower()]
    matches = exact or partial
    if len(matches) != 1:
        raise HTTPException(status_code=400, detail=f"Could not uniquely identify employee: {name}")
    return matches[0]


def _normalize_position_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.strip().lower()).strip()
    aliases = {
        "sandwich": "sandwich",
        "sandwiches": "sandwich",
        "salad": "salad",
        "salads": "salad",
        "dish": "dish",
        "dishes": "dish",
        "dishwasher": "dish",
        "dishwashers": "dish",
        "cashier": "register",
        "cashiers": "register",
        "register": "register",
        "registers": "register",
        "runner": "runner",
        "runners": "runner",
        "expo": "expo",
        "expeditor": "expo",
        "prep": "prep",
        "preparation": "prep",
    }
    return aliases.get(normalized, normalized.rstrip("s"))


def _find_position_by_name(
    session: Session,
    name: Optional[str],
    department: Optional[str] = None,
) -> Optional[Position]:
    if not name:
        return None
    normalized = _normalize_position_name(name)
    rows = session.exec(select(Position).where(Position.active == True)).all()  # noqa: E712
    matches = [
        row for row in rows
        if _normalize_position_name(row.name) == normalized
        and (department is None or row.department == department)
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _find_shift_for_action(
    session: Session,
    schedule_id: int,
    action: AssistantAction,
) -> ScheduleShift:
    rows = session.exec(select(ScheduleShift).where(ScheduleShift.schedule_id == schedule_id)).all()
    employees = {row.id: row for row in session.exec(select(Employee)).all()}
    positions = {row.id: row for row in session.exec(select(Position)).all()}

    if action.selected_date:
        rows = [row for row in rows if row.date == action.selected_date]
    if action.employee_name:
        target = action.employee_name.strip().lower()
        rows = [
            row for row in rows
            if target in (employees.get(row.employee_id).name.lower() if employees.get(row.employee_id) else "")
        ]
    if action.position_name:
        target = action.position_name.strip().lower()
        rows = [
            row for row in rows
            if target in (positions.get(row.position_id).name.lower() if positions.get(row.position_id) else "")
        ]
    if len(rows) != 1:
        raise HTTPException(
            status_code=400,
            detail="The requested shift was ambiguous. Include the employee, date, and position.",
        )
    return rows[0]


def _replacement_is_valid(session: Session, employee: Employee, shift: ScheduleShift) -> bool:
    if shift.position_id:
        ability = session.exec(
            select(EmployeePosition).where(
                EmployeePosition.employee_id == employee.id,
                EmployeePosition.position_id == shift.position_id,
            )
        ).first()
        if not ability:
            return False
    recurring = session.exec(
        select(RecurringAvailability).where(RecurringAvailability.employee_id == employee.id)
    ).all()
    temporary = session.exec(
        select(TemporaryUnavailability).where(TemporaryUnavailability.employee_id == employee.id)
    ).all()
    start = parse_time(shift.start_time)
    end = parse_time(shift.end_time)
    if any(
        rule.rule_type == "unavailable" and recurring_rule_blocks(rule, shift.date, start, end)
        for rule in recurring
    ):
        return False
    if any(temporary_rule_blocks(rule, shift.date, start, end) for rule in temporary):
        return False
    return True


def _apply_setup_action(session: Session, action: AssistantAction) -> str:
    if action.type == "create_employee":
        name = (action.name or action.employee_name or "").strip()
        if not name or not _department_exists(session, action.department):
            raise HTTPException(status_code=400, detail="Employee name and an active department are required")
        existing = session.exec(select(Employee).where(Employee.active == True)).all()  # noqa: E712
        if any(row.name.lower() == name.lower() for row in existing):
            return f"{name} already exists; no duplicate was added"
        employee = Employee(
            name=name,
            department=action.department,
            role=action.role if action.role in VALID_ROLES else "employee",
            min_hours_per_week=max(0, action.min_hours_per_week or 0),
            max_hours_per_week=max(action.min_hours_per_week or 0, action.max_hours_per_week or 40),
            active=True,
        )
        session.add(employee)
        session.commit()
        return f"Added {name} to {action.department}"

    if action.type == "update_employee":
        employee = _find_named_employee(session, action.employee_name or action.name or "")
        if action.name:
            employee.name = action.name.strip()
        if _department_exists(session, action.department) and action.department != employee.department:
            employee.department = action.department
            valid_position_ids = {
                row.id for row in session.exec(select(Position)).all()
                if row.active and row.department == employee.department
            }
            for ability in session.exec(
                select(EmployeePosition).where(EmployeePosition.employee_id == employee.id)
            ).all():
                if ability.position_id not in valid_position_ids:
                    session.delete(ability)
        if action.role in VALID_ROLES:
            employee.role = action.role
        if action.min_hours_per_week is not None:
            employee.min_hours_per_week = max(0, action.min_hours_per_week)
        if action.max_hours_per_week is not None:
            employee.max_hours_per_week = max(employee.min_hours_per_week, action.max_hours_per_week)
        session.add(employee)
        session.commit()
        return f"Updated {employee.name}"

    if action.type == "create_position":
        name = (action.name or action.position_name or "").strip()
        if not name or not _department_exists(session, action.department):
            raise HTTPException(status_code=400, detail="Position name and department are required")
        existing = _find_position_by_name(session, name, action.department)
        if existing:
            return f"{action.department} {name} already exists"
        session.add(Position(name=name, department=action.department, active=True))
        session.commit()
        return f"Added {name} to {action.department} positions"

    if action.type == "set_employee_positions":
        employee = _find_named_employee(session, action.employee_name or action.name or "")
        requested = list(dict.fromkeys(action.position_names))
        trainee_names = {name.lower() for name in action.trainee_position_names}
        preferred_name = (action.preferred_position_name or "").lower()
        rows: list[EmployeePosition] = []
        for name in requested:
            position = _find_position_by_name(session, name, employee.department)
            if not position:
                raise HTTPException(
                    status_code=400,
                    detail=f"Could not find {employee.department} position: {name}",
                )
            rows.append(
                EmployeePosition(
                    employee_id=employee.id,
                    position_id=position.id,
                    trainee=name.lower() in trainee_names,
                    preferred=name.lower() == preferred_name,
                )
            )
        if rows and not any(row.preferred for row in rows):
            rows[0].preferred = True
        for old in session.exec(
            select(EmployeePosition).where(EmployeePosition.employee_id == employee.id)
        ).all():
            session.delete(old)
        for row in rows:
            session.add(row)
        session.commit()
        return f"Updated positions for {employee.name}"

    if action.type == "add_recurring_availability":
        employee = _find_named_employee(session, action.employee_name or action.name or "")
        rule_type = action.rule_type or "unavailable"
        days = action.days_of_week or ([action.day_of_week] if action.day_of_week is not None else [-1])
        for day in days:
            session.add(
                RecurringAvailability(
                    employee_id=employee.id,
                    rule_type=rule_type,
                    day_of_week=day,
                    start_time=action.start_time or "",
                    end_time=action.end_time or "",
                )
            )
        session.commit()
        return f"Added {rule_type.replace('_', ' ')} for {employee.name}"

    if action.type == "add_temporary_unavailability":
        employee = _find_named_employee(session, action.employee_name or action.name or "")
        if not action.start_date:
            raise HTTPException(status_code=400, detail="Temporary unavailability needs a start date")
        session.add(
            TemporaryUnavailability(
                employee_id=employee.id,
                start_date=action.start_date,
                end_date=action.end_date or action.start_date,
                start_time=action.start_time or "",
                end_time=action.end_time or "",
            )
        )
        session.commit()
        return f"Added temporary unavailability for {employee.name}"

    if action.type == "create_labor_projection":
        if not action.date:
            raise HTTPException(status_code=400, detail="Labor projection needs a date")
        settings = session.exec(select(ManagerSettings)).first() or ManagerSettings()
        projection = LaborProjection(
            date=action.date,
            start_time="" if action.whole_day else (action.start_time or ""),
            end_time="" if action.whole_day else (action.end_time or ""),
            projected_sales=action.projected_sales,
            min_labor_percent=(
                action.min_labor_percent if action.min_labor_percent is not None else settings.min_labor_percent
            ),
            max_labor_percent=(
                action.max_labor_percent if action.max_labor_percent is not None else settings.max_labor_percent
            ),
            max_labor_hours=action.max_labor_hours,
            max_labor_dollars=action.max_labor_dollars,
        )
        _validate_projection(projection, session)
        session.add(projection)
        session.commit()
        return f"Added labor projection for {action.date}"

    if action.type == "create_crew_target":
        target_date = action.target_date or action.date or ""
        day = action.target_day_of_week if action.target_day_of_week is not None else (
            action.day_of_week if action.day_of_week is not None else -1
        )
        if not action.start_time or not action.end_time:
            raise HTTPException(status_code=400, detail="Projected Crew target needs start and end times")
        position_ids = []
        department_hint = action.departments[0] if len(action.departments) == 1 else None
        for name in action.position_names:
            position = _find_position_by_name(session, name, department_hint)
            if not position:
                raise HTTPException(status_code=400, detail=f"Could not uniquely find position: {name}")
            position_ids.append(position.id)
        payload = CoverageRulePayload(
            name=(action.name or "Crew target").strip(),
            date=target_date,
            day_of_week=day,
            start_time=action.start_time,
            end_time=action.end_time,
            position_ids=position_ids,
            departments=[item for item in action.departments if _department_exists(session, item)],
            roles=[item for item in action.roles if item in VALID_ROLES],
            minimum_count=max(0, action.minimum_count if action.minimum_count is not None else 1),
            preferred_count=max(0, action.preferred_count if action.preferred_count is not None else (action.minimum_count or 1)),
            hard_minimum=action.hard_minimum,
            active=True,
        )
        payload = _clean_coverage_payload(payload, session)
        rule = CoverageRule(name=payload.name, start_time=payload.start_time, end_time=payload.end_time)
        _apply_coverage_payload(rule, payload)
        session.add(rule)
        session.commit()
        return f"Added Projected Crew target: {payload.name}"

    if action.type == "update_manager_settings":
        settings = session.exec(select(ManagerSettings)).first() or ManagerSettings()
        if action.employee_hourly_rate is not None:
            settings.employee_hourly_rate = max(0, action.employee_hourly_rate)
        if action.min_labor_percent is not None:
            settings.min_labor_percent = max(0, action.min_labor_percent)
        if action.max_labor_percent is not None:
            settings.max_labor_percent = max(0, action.max_labor_percent)
        if settings.max_labor_percent < settings.min_labor_percent:
            settings.min_labor_percent, settings.max_labor_percent = (
                settings.max_labor_percent,
                settings.min_labor_percent,
            )
        if action.schedule_extra_with_trainee is not None:
            settings.schedule_extra_with_trainee = action.schedule_extra_with_trainee
        if action.store_open_time:
            settings.store_open_time = action.store_open_time
        if action.store_close_time:
            settings.store_close_time = action.store_close_time
        settings.shift_lead_hourly_rate = settings.employee_hourly_rate + 1
        settings.gm_hourly_rate = settings.employee_hourly_rate + 1
        settings.default_labor_percent = (
            settings.min_labor_percent + settings.max_labor_percent
        ) / 2
        session.add(settings)
        session.commit()
        return "Updated manager settings"

    if action.type == "update_ui_config":
        patch = action.ui_config_patch if isinstance(action.ui_config_patch, dict) else {}
        business_id = current_business_id()
        record = session.exec(select(UIConfig).where(UIConfig.business_id == business_id)).first()
        if not record:
            record = UIConfig(business_id=business_id)
        try:
            existing = json.loads(record.config_json) if record.config_json else {}
        except Exception:
            existing = {}
        for section, values in patch.items():
            if isinstance(values, dict):
                existing[section] = {**existing.get(section, {}), **values}
            else:
                existing[section] = values
        record.config_json = json.dumps(existing)
        from datetime import datetime, timezone
        record.updated_at = datetime.now(timezone.utc).isoformat()
        session.add(record)
        session.commit()
        sections = ", ".join(patch.keys())
        return f"UI config updated: {sections}"

    if action.type == "toggle_module":
        PROTECTED = {"home", "settings", "assistant"}
        VALID = {"team", "scheduling", "accounting", "sales", "purchasing", "tasks", "inventory", "reports", "assistant", "notifications"}
        key = (action.module_key or "").strip().lower()
        if not key or key not in VALID:
            raise HTTPException(status_code=400, detail=f"Unknown module '{key}'. Valid: {', '.join(sorted(VALID))}")
        if key in PROTECTED:
            raise HTTPException(status_code=400, detail=f"The '{key}' module cannot be hidden")
        business_id = current_business_id()
        record = session.exec(select(BusinessModule).where(BusinessModule.business_id == business_id, BusinessModule.module_key == key)).first()
        if not record:
            record = BusinessModule(business_id=business_id, module_key=key)
        record.enabled = action.module_enabled
        session.add(record)
        session.commit()
        state = "enabled" if action.module_enabled else "hidden"
        return f"Module '{key}' {state}"

    raise HTTPException(status_code=400, detail=f"Unsupported setup action: {action.type}")


@app.post("/assistant/apply")
def apply_assistant_actions(
    request: AssistantApplyRequest,
    session: Session = Depends(get_session),
):
    setup_types = {
        "create_employee",
        "update_employee",
        "create_position",
        "set_employee_positions",
        "add_recurring_availability",
        "add_temporary_unavailability",
        "create_labor_projection",
        "create_crew_target",
        "update_manager_settings",
        "update_ui_config",
        "toggle_module",
    }
    schedule_types = {"regenerate_schedule", "adjust_shift", "replace_shift_employee"}

    applied_messages: list[str] = []
    schedule: Optional[Schedule] = None
    if request.schedule_id is not None:
        schedule = session.get(Schedule, request.schedule_id)
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")

    for action in request.actions:
        if action.type in setup_types:
            applied_messages.append(_apply_setup_action(session, action))

    schedule_actions = [action for action in request.actions if action.type in schedule_types]
    if schedule_actions and schedule is None and not any(
        action.type == "regenerate_schedule" for action in schedule_actions
    ):
        raise HTTPException(status_code=400, detail="Select a schedule before applying shift edits")

    if schedule and schedule.status == "published" and schedule_actions:
        schedule = _clone_schedule_exact(session, schedule)

    regenerate_action: Optional[AssistantAction] = None
    for action in schedule_actions:
        if action.type == "regenerate_schedule":
            regenerate_action = action
            continue

        if schedule is None:
            raise HTTPException(status_code=400, detail="Select a schedule before editing a shift")
        shift = _find_shift_for_action(session, schedule.id, action)
        if action.type == "adjust_shift":
            if action.new_start_time:
                shift.start_time = action.new_start_time
            if action.new_end_time:
                shift.end_time = action.new_end_time
            if parse_time(shift.end_time) <= parse_time(shift.start_time):
                raise HTTPException(status_code=400, detail="The proposed shift times are invalid")
            shift.locked = True
            session.add(shift)
            applied_messages.append("Adjusted and locked the requested shift")

        elif action.type == "replace_shift_employee":
            if not action.replacement_employee_name:
                raise HTTPException(status_code=400, detail="A replacement employee is required")
            replacement = _find_named_employee(session, action.replacement_employee_name)
            if not _replacement_is_valid(session, replacement, shift):
                raise HTTPException(
                    status_code=400,
                    detail=f"{replacement.name} is unavailable or cannot work that position",
                )
            shift.employee_id = replacement.id
            shift.role = replacement.role
            shift.locked = True
            session.add(shift)
            applied_messages.append(f"Replaced the shift employee with {replacement.name}")
    session.commit()

    result_schedule = None
    if regenerate_action:
        week_start = request.week_start or (schedule.week_start if schedule else None)
        if not week_start:
            raise HTTPException(status_code=400, detail="Choose a week before generating a schedule")
        try:
            result_schedule = generate_schedule(
                session,
                week_start=week_start,
                source_schedule_id=schedule.id if schedule else None,
                scope=regenerate_action.scope,
                selected_date=regenerate_action.selected_date,
                labor_tolerance_percent=regenerate_action.labor_tolerance_percent,
                staffing_level=regenerate_action.staffing_level,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        applied_messages.append("Generated a new reviewable schedule version")
    elif schedule:
        result_schedule = schedule_detail(session, schedule.id)

    if request.message_id is not None:
        assistant_message = session.get(AssistantMessage, request.message_id)
        if assistant_message:
            assistant_message.applied = True
            session.add(assistant_message)
            session.commit()

    return {
        "message": ". ".join(applied_messages) or "No changes were applied",
        "schedule": result_schedule,
        "setup_changed": any(action.type in setup_types for action in request.actions),
    }


# In production the React build is served by the API, giving Railway one secure
# public service and avoiding cross-origin configuration for every deployment.
frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
