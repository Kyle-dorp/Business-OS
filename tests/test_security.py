"""
Login throttling and reset codes.

The failure modes here are quiet ones. A window calculation that is off by a
timezone locks nobody out; a code alphabet with ambiguous characters produces
support calls nobody traces back to the font. Both are pinned.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.app.security import (
    ALPHABET,
    LOCKOUT_MINUTES,
    MAX_ATTEMPTS,
    RESET_CODE_TTL_MINUTES,
    WINDOW_MINUTES,
    _generate_code,
    _parse,
)


# ------------------------------------------------------------------- codes

def test_code_has_no_ambiguous_characters():
    """
    These get read aloud across a noisy kitchen. I/1 and O/0 are the pairs
    people mishear, and every mishearing is a support call.
    """
    assert not set("IO01") & set(ALPHABET)


def test_code_format_is_stable():
    for _ in range(50):
        code = _generate_code()
        assert len(code) == 9
        assert code[4] == "-"
        assert all(c in ALPHABET for c in code.replace("-", ""))


def test_codes_do_not_repeat():
    codes = {_generate_code() for _ in range(500)}
    assert len(codes) == 500, "generator produced a collision in 500 draws"


def test_keyspace_survives_the_throttle():
    """
    Eight characters from a 32-symbol alphabet against 8 guesses per 15 minutes.
    If either constant is ever loosened, this is the test that should complain.
    """
    keyspace = len(ALPHABET) ** 8
    guesses_per_year = (MAX_ATTEMPTS / WINDOW_MINUTES) * 60 * 24 * 365
    years_to_exhaust = keyspace / guesses_per_year
    assert years_to_exhaust > 100_000, f"only {years_to_exhaust:,.0f} years to brute force"


# ------------------------------------------------------------------ window

def _iso(minutes_ago: int, naive: bool = False) -> str:
    stamp = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return (stamp.replace(tzinfo=None) if naive else stamp).isoformat()


@pytest.mark.parametrize(
    "minutes_ago,should_count",
    [(0, True), (1, True), (WINDOW_MINUTES - 1, True), (WINDOW_MINUTES + 1, False), (120, False)],
)
def test_attempts_expire_at_the_window_edge(minutes_ago, should_count):
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=WINDOW_MINUTES)
    parsed = _parse(_iso(minutes_ago))
    assert parsed is not None
    assert (parsed >= cutoff) is should_count


def test_naive_timestamps_are_treated_as_utc():
    """
    utc_now_iso writes stamps without an offset. Comparing a naive datetime to
    an aware one raises TypeError in Python, so every attempt row would blow up
    the login route rather than throttle anything.
    """
    parsed = _parse(_iso(5, naive=True))
    assert parsed is not None
    assert parsed.tzinfo is not None
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=WINDOW_MINUTES)
    assert parsed >= cutoff


def test_parse_survives_garbage():
    assert _parse("") is None
    assert _parse("not a timestamp") is None
    assert _parse(None) is None


def test_trailing_z_is_accepted():
    stamp = datetime.now(timezone.utc).replace(microsecond=0)
    assert _parse(stamp.isoformat().replace("+00:00", "Z")) is not None


# --------------------------------------------------------------- constants

def test_limits_are_humane_but_useful():
    """
    Tight enough to stop guessing, loose enough that someone fat-fingering a
    password three times in a row never notices this exists.
    """
    assert 5 <= MAX_ATTEMPTS <= 12
    assert 5 <= WINDOW_MINUTES <= 60
    assert LOCKOUT_MINUTES >= 5


def test_reset_codes_expire_same_day():
    assert 5 <= RESET_CODE_TTL_MINUTES <= 120
