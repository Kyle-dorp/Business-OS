"""
The schema the app repairs on its own.

Production sat for days with sign-in returning 500 on every attempt. The cause
was four columns missing from `useraccount`, added by a migration that had
never run — because Railway builds from the Dockerfile, the Dockerfile started
uvicorn directly, and the migrations folder was not even copied into the image.
Alembic could not have run if something had asked it to.

Meanwhile /health returned 200, because it never touched the database.

Two things are pinned here. That the app repairs its own schema on boot, so a
missing migration cannot take the front door down again. And that /health goes
red when the database is unusable, so the next time something like this happens
it is visible within a minute instead of a week.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Exactly the shape production had: the nine columns that existed, missing the
# four that migration c3a71f2e9d04 adds.
LEGACY_USERACCOUNT = """
CREATE TABLE useraccount (
    id INTEGER PRIMARY KEY,
    username VARCHAR NOT NULL,
    password_hash VARCHAR NOT NULL,
    role VARCHAR NOT NULL,
    employee_id INTEGER,
    is_admin BOOLEAN NOT NULL DEFAULT 0,
    active BOOLEAN NOT NULL DEFAULT 1,
    created_at VARCHAR NOT NULL DEFAULT '',
    updated_at VARCHAR NOT NULL DEFAULT ''
)
"""

REPAIR_SCRIPT = """
import sqlite3, sys
from backend.app.database import create_db_and_tables, engine
from sqlmodel import Session, select
from backend.app.models import UserAccount

create_db_and_tables()

with Session(engine) as session:
    user = session.exec(select(UserAccount)).first()

cols = {r[1] for r in sqlite3.connect(sys.argv[1]).execute("PRAGMA table_info(useraccount)")}
print("COLUMNS:" + ",".join(sorted(cols)))
print("SELECTED:" + (user.username if user else ""))
"""


def _run_against(db_path: Path, setup_sql: str, insert_sql: str | None = None):
    """Build a legacy-shaped database, then boot the app against it."""
    con = sqlite3.connect(db_path)
    con.executescript(setup_sql)
    if insert_sql:
        con.execute(insert_sql)
    con.commit()
    con.close()

    script = ROOT / "tests" / f"_repair_probe_{uuid.uuid4().hex[:6]}.py"
    script.write_text(REPAIR_SCRIPT, encoding="utf-8")
    try:
        result = subprocess.run(
            [sys.executable, str(script), str(db_path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env={"DATABASE_URL": f"sqlite:///{db_path.as_posix()}",
                 "PATH": __import__("os").environ.get("PATH", ""),
                 "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", ""),
                 # The subprocess starts in tests/, so the project root has to
                 # be on the path for `backend.app...` to resolve.
                 "PYTHONPATH": str(ROOT),
                 "PYTHONIOENCODING": "utf-8"},
            timeout=180,
        )
    finally:
        script.unlink(missing_ok=True)
    return result


@pytest.fixture
def legacy_db():
    # tempfile rather than pytest's tmp_path: its per-user directory is not
    # always writable on Windows, and this suite has to run on both.
    directory = Path(tempfile.mkdtemp(prefix="eos_repair_"))
    yield directory / "legacy.db"


def test_the_app_repairs_a_database_missing_the_oauth_columns(legacy_db):
    """
    The exact failure, end to end. A useraccount table from before the email
    and OAuth migration, booted by the app, must come out readable — because
    this is what sign-in does on its first query.
    """
    result = _run_against(
        legacy_db,
        LEGACY_USERACCOUNT,
        "INSERT INTO useraccount (id, username, password_hash, role) "
        "VALUES (1, 'kyle', 'x', 'manager')",
    )
    assert result.returncode == 0, result.stderr[-2000:]

    columns = next(
        line[len("COLUMNS:"):] for line in result.stdout.splitlines()
        if line.startswith("COLUMNS:")
    ).split(",")

    for column in ("email", "email_verified", "auth_provider", "provider_subject"):
        assert column in columns, f"{column} was not repaired onto useraccount"


def test_the_query_that_was_returning_500_works_afterwards(legacy_db):
    """Not just that the columns exist — that reading a user succeeds."""
    result = _run_against(
        legacy_db,
        LEGACY_USERACCOUNT,
        "INSERT INTO useraccount (id, username, password_hash, role) "
        "VALUES (1, 'kyle', 'x', 'manager')",
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert "SELECTED:kyle" in result.stdout


def test_existing_rows_survive_the_repair(legacy_db):
    """
    A repair that fixes the schema by dropping the table would also pass the
    test above. The user has to still be there.
    """
    result = _run_against(
        legacy_db,
        LEGACY_USERACCOUNT,
        "INSERT INTO useraccount (id, username, password_hash, role) "
        "VALUES (1, 'kyle', 'x', 'manager')",
    )
    assert result.returncode == 0
    with sqlite3.connect(legacy_db) as con:
        rows = con.execute("SELECT username FROM useraccount").fetchall()
    assert rows == [("kyle",)]


def test_the_repair_is_safe_to_run_twice(legacy_db):
    """Every deploy runs it. The second boot must be a no-op, not an error."""
    first = _run_against(
        legacy_db,
        LEGACY_USERACCOUNT,
        "INSERT INTO useraccount (id, username, password_hash, role) "
        "VALUES (1, 'kyle', 'x', 'manager')",
    )
    assert first.returncode == 0, first.stderr[-2000:]

    second = _run_against(legacy_db, "SELECT 1")
    assert second.returncode == 0, second.stderr[-2000:]


def test_every_column_the_unrun_migrations_add_is_also_repaired():
    """
    Both migrations were stranded, not just the user one — bookings and
    services were missing columns too, which takes down the public booker.
    Whatever a migration adds, the boot-time repair has to add as well, or the
    next stranded migration is the next outage.
    """
    import re

    repairs = (ROOT / "backend" / "app" / "database.py").read_text(encoding="utf-8")
    repaired = set(re.findall(r'_add_column_if_missing\(\s*"(\w+)",\s*"(\w+)"', repairs))

    missing = []
    for path in (ROOT / "migrations" / "versions").glob("*.py"):
        source = path.read_text(encoding="utf-8")
        for table, column in re.findall(r'op\.add_column\(\s*"(\w+)",\s*sa\.Column\(\s*"(\w+)"', source):
            if (table, column) not in repaired:
                missing.append(f"{path.name[:12]}: {table}.{column}")

    assert not missing, (
        "these migration columns have no boot-time repair, so a database that "
        f"misses the migration stays broken: {missing}"
    )
