import os

from sqlalchemy import event, inspect, text
from sqlalchemy.orm import with_loader_criteria
from sqlmodel import SQLModel, Session, create_engine

from backend.app import models  # noqa: F401
from backend.app.tenancy import current_business_id

TENANT_MODELS = (
    models.Employee, models.Position, models.Department, models.EmployeePosition,
    models.RecurringAvailability, models.TemporaryUnavailability,
    models.ManagerSettings, models.LaborProjection, models.CoverageRule,
    models.Schedule, models.ScheduleShift, models.ScheduleWarning,
    models.AssistantMessage, models.AvailabilityRequest,
    models.AssistantThread, models.AssistantMemory,
)


@event.listens_for(Session, "do_orm_execute")
def _scope_scheduler_queries(execute_state):
    if not execute_state.is_select or execute_state.execution_options.get("include_all_businesses"):
        return
    business_id = current_business_id()
    statement = execute_state.statement
    for model in TENANT_MODELS:
        statement = statement.options(with_loader_criteria(
            model, lambda row: row.business_id == business_id,
            include_aliases=True, track_closure_variables=False,
        ))
    execute_state.statement = statement

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///schedule_assistant.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args=connect_args,
)


def _add_column_if_missing(table: str, column: str, sql_type: str, default_sql: str, *, nullable: bool = False) -> None:
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return
    existing = {item["name"] for item in inspector.get_columns(table)}
    if column in existing:
        return
    null_sql = "" if nullable else " NOT NULL"
    with engine.begin() as connection:
        connection.execute(
            text(
                f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}{null_sql} "
                f"DEFAULT {default_sql}"
            )
        )


def apply_lightweight_migrations() -> None:
    """Add compatible columns without deleting the user's existing database."""
    for table in (
        "employee", "position", "employeeposition", "recurringavailability",
        "temporaryunavailability", "managersettings", "laborprojection",
        "coveragerule", "schedule", "scheduleshift", "schedulewarning",
        "assistantmessage", "availabilityrequest", "assistantthread", "assistantmemory",
    ):
        _add_column_if_missing(table, "business_id", "INTEGER", "1")
    # Manager settings from older builds.
    _add_column_if_missing("managersettings", "employee_hourly_rate", "FLOAT", "18.2")
    _add_column_if_missing("managersettings", "shift_lead_hourly_rate", "FLOAT", "19.2")
    _add_column_if_missing("managersettings", "gm_hourly_rate", "FLOAT", "19.2")
    _add_column_if_missing("managersettings", "default_labor_percent", "FLOAT", "19.0")
    _add_column_if_missing("managersettings", "min_labor_percent", "FLOAT", "18.0")
    _add_column_if_missing("managersettings", "max_labor_percent", "FLOAT", "20.0")
    _add_column_if_missing("managersettings", "schedule_extra_with_trainee", "BOOLEAN", "1")
    _add_column_if_missing("managersettings", "store_open_time", "VARCHAR", "'10:30'")
    _add_column_if_missing("managersettings", "store_close_time", "VARCHAR", "'21:00'")


    # Upgrade the previous 18–22 starter range to the new 18–20 default.
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE managersettings "
                "SET max_labor_percent = 20.0, default_labor_percent = 19.0 "
                "WHERE min_labor_percent = 18.0 AND max_labor_percent = 22.0"
            )
        )

    # Labor projection range fields.
    _add_column_if_missing("laborprojection", "min_labor_percent", "FLOAT", "NULL", nullable=True)
    _add_column_if_missing("laborprojection", "max_labor_percent", "FLOAT", "NULL", nullable=True)
    _add_column_if_missing("laborprojection", "max_labor_hours", "FLOAT", "NULL", nullable=True)
    _add_column_if_missing("laborprojection", "max_labor_dollars", "FLOAT", "NULL", nullable=True)
    _add_column_if_missing("laborprojection", "note", "VARCHAR", "''")

    # Projected Crew / legacy coverage fields.
    _add_column_if_missing("coveragerule", "date", "VARCHAR", "''")
    _add_column_if_missing("coveragerule", "position_ids_json", "VARCHAR", "'[]'")
    _add_column_if_missing("coveragerule", "departments_json", "VARCHAR", "'[]'")
    _add_column_if_missing("coveragerule", "roles_json", "VARCHAR", "'[]'")

    # Schedule comparison mode.
    _add_column_if_missing("schedule", "staffing_level", "VARCHAR", "'balanced'")

    # Persistent assistant conversations.
    _add_column_if_missing("assistantmessage", "user_id", "INTEGER", "NULL", nullable=True)
    _add_column_if_missing("assistantmessage", "thread_id", "INTEGER", "NULL", nullable=True)
    _add_column_if_missing("assistantmessage", "actions_json", "VARCHAR", "'[]'")
    _add_column_if_missing("assistantmessage", "applied", "BOOLEAN", "0")


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    apply_lightweight_migrations()


def get_session():
    with Session(engine) as session:
        yield session
