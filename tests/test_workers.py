"""
Running more than one worker.

A single uvicorn worker is a single Python process and therefore a single core,
and it served 142 authenticated requests a second while Railway's plan allowed
48 vCPU. The fix is `--workers`, and the thing that makes it dangerous is the
startup hook: uvicorn runs it once per worker, and `seed_defaults()` is a
series of check-then-inserts.

    settings = session.exec(select(ManagerSettings)).first()
    if not settings:
        settings = ManagerSettings()

Four workers booting together all read "no row" and all create one, so a fresh
deployment comes up with four copies of every default. A Postgres advisory lock
serialises them.

Serialising rather than skipping is the part worth testing. The later workers
still run the same function — they just run it after the first has committed,
find the rows, and create nothing. That only works if the function is safe to
run repeatedly, which is what the first test here actually checks rather than
assumes.
"""

from __future__ import annotations

import pathlib

from sqlmodel import Session, func, select

from backend.app.database import engine, startup_lock
from backend.app.models import Department, ManagerSettings

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _count(model) -> int:
    with Session(engine) as session:
        return session.exec(select(func.count()).select_from(model)).one()


def test_seeding_twice_creates_nothing_the_second_time():
    """
    The property the lock depends on. If this fails, serialising the workers is
    not enough and the startup hook needs a genuine skip.
    """
    from backend.app.main import seed_defaults

    seed_defaults()
    settings_after_first = _count(ManagerSettings)
    departments_after_first = _count(Department)

    seed_defaults()
    seed_defaults()

    assert _count(ManagerSettings) == settings_after_first
    assert _count(Department) == departments_after_first


def test_there_is_never_more_than_one_settings_row():
    """
    ManagerSettings is read with `.first()` everywhere. A second row is not a
    loud failure — it is a workspace that silently uses whichever one the
    database happens to return first.
    """
    from backend.app.main import seed_defaults

    seed_defaults()
    assert _count(ManagerSettings) <= 1


def test_the_lock_is_a_no_op_on_sqlite():
    """
    Development runs one process against SQLite, which has no advisory locks.
    Taking the lock must not fail there — it must simply do nothing.
    """
    with startup_lock():
        pass


def test_startup_takes_the_lock():
    source = (ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    start = source.index("def on_startup")
    body = source[start : source.index("\ndef ", start + 1)]

    # Comments are stripped first. The comment above the call explains why the
    # lock is there and names it, so the first version of this test passed with
    # the call deleted and only the explanation left — it was asserting on its
    # own documentation.
    code = "\n".join(line.split("#")[0] for line in body.splitlines())

    assert "startup_lock()" in code, (
        "on_startup no longer serialises its database work across workers"
    )


def test_the_container_runs_more_than_one_worker():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "--workers" in dockerfile, "back to a single worker"
    assert "WEB_CONCURRENCY" in dockerfile, (
        "the worker count should be tunable from the environment rather than "
        "needing a code change and a rebuild"
    )
