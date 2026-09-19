"""
Blocking work on the event loop.

FastAPI runs a `def` handler in a threadpool and an `async def` handler on the
event loop. Synchronous database work is therefore safe in the first and
serialises the entire process in the second — every other request waits, not
just the one doing the query.

`authentication_middleware` is `async def` and ran two synchronous queries — a
token lookup and a membership query — on every authenticated request. Measured
against a public path that also reads the database:

    public          c=1  167.8 req/s   c=24  217.0 req/s   p95    115ms
    authenticated   c=1   33.8 req/s   c=24    0.2 req/s   p95  22802ms
                                                           96/120 FAILED

It did not merely run slower. It stopped scaling and then fell over. After
moving both queries into a threadpool, a comparable authenticated endpoint
serves 142 req/s at c=1 and 116.9 at c=24 with nothing failing.

None of this needed load to matter: one fifty-person rota being published is
already past twenty-four concurrent requests.
"""

from __future__ import annotations

import pathlib
import re

APP = pathlib.Path(__file__).resolve().parents[1] / "backend" / "app"

# Signs a function body touches the database synchronously.
DB_WORK = re.compile(
    r"Session\(engine\)|session\.(exec|get|add|commit|refresh)\b|Depends\(get_session\)"
)

# Async handlers that still do synchronous database work, and why that is
# tolerable for now. Anything not on this list is a new regression.
#
# The OAuth handlers run once per sign-in rather than once per request, so they
# serialise a burst of people signing in at the same moment and nothing else.
# That is a real but much smaller problem than the middleware was, and the fix
# is the same shape when it is worth doing.
ACCEPTED = {
    ("oauth.py", "google_login"),
    ("oauth.py", "link_google"),
}


def _async_handlers_touching_the_database() -> set[tuple[str, str]]:
    found = set()
    for path in sorted(APP.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        for match in re.finditer(r"^async def (\w+)\(", source, re.M):
            start = match.start()
            # The body runs until the next top-level def/async def.
            following = [
                where
                for where in (
                    source.find("\ndef ", start + 1),
                    source.find("\nasync def ", start + 1),
                )
                if where > 0
            ]
            body = source[start : min(following + [len(source)])]
            if DB_WORK.search(body):
                found.add((path.name, match.group(1)))
    return found


def test_no_new_async_handler_blocks_the_event_loop():
    offenders = _async_handlers_touching_the_database() - ACCEPTED
    assert offenders == set(), (
        "These async handlers do synchronous database work, which blocks every "
        "other request in the process while they wait: "
        + ", ".join(f"{f}:{n}" for f, n in sorted(offenders))
        + ". Either make the handler a plain `def` so FastAPI runs it in a "
        "threadpool, or wrap the database work in run_in_threadpool()."
    )


def test_the_middleware_itself_is_off_the_event_loop():
    """
    The one that runs on literally every request. Worth its own assertion
    rather than only being covered by the set comparison above.
    """
    source = (APP / "main.py").read_text(encoding="utf-8")
    start = source.index("async def authentication_middleware")
    body = source[start : source.index("\n@app.", start + 1)]

    assert "run_in_threadpool(" in body, "the auth lookup is back on the event loop"
    assert not DB_WORK.search(body), "the middleware is querying the database inline again"


def test_the_accepted_list_has_not_gone_stale():
    """A name on the exemption list that no longer exists hides a real finding."""
    current = _async_handlers_touching_the_database()
    stale = ACCEPTED - current
    assert stale == set(), (
        "These are exempted but no longer block — remove them from ACCEPTED: "
        + ", ".join(f"{f}:{n}" for f, n in sorted(stale))
    )
