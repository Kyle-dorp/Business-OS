"""
Reading credentials out of the environment.

A Stripe secret key was set in Railway as `"sk_live_..."` — quotes included in
the value. Every call to Stripe then failed on an invalid key, while
`bool(STRIPE_SECRET_KEY)` was perfectly true, so the app reported itself
configured and nothing anywhere said otherwise. Checkout simply did not work.

That is the worst shape a configuration bug can take: truthy, silent, and
indistinguishable from a working system until a customer tries to pay. These
tests are about making it loud.
"""

from __future__ import annotations

import pytest

from backend.app.config import check_all, env, malformed, stripe_mode


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for name in ("STRIPE_SECRET_KEY", "STRIPE_PUBLIC_KEY", "STRIPE_WEBHOOK_SECRET",
                 "STRIPE_PRICE_BASE", "ANTHROPIC_API_KEY", "RESEND_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    yield


# ===========================================================================
# The ways a pasted value arrives mangled
# ===========================================================================

def test_a_value_that_kept_its_quotes_is_cleaned(monkeypatch):
    """The actual bug. Pasting `"sk_live_..."` into a variables field."""
    monkeypatch.setenv("STRIPE_SECRET_KEY", '"sk_live_51ABC"')
    assert env("STRIPE_SECRET_KEY") == "sk_live_51ABC"


def test_single_quotes_too(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "'sk_live_51ABC'")
    assert env("STRIPE_SECRET_KEY") == "sk_live_51ABC"


def test_surrounding_whitespace_goes(monkeypatch):
    """A newline picked up from a terminal is the same failure with no quotes."""
    monkeypatch.setenv("STRIPE_SECRET_KEY", "  sk_live_51ABC\n")
    assert env("STRIPE_SECRET_KEY") == "sk_live_51ABC"


def test_quotes_and_whitespace_together(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", '  " sk_live_51ABC "  ')
    assert env("STRIPE_SECRET_KEY") == "sk_live_51ABC"


def test_only_one_pair_is_stripped(monkeypatch):
    """
    A value that genuinely begins and ends with a quote character must not be
    eaten repeatedly — stripping until there is nothing left would corrupt a
    legitimate secret.
    """
    monkeypatch.setenv("STRIPE_SECRET_KEY", '""double""')
    assert env("STRIPE_SECRET_KEY") == '"double"'


def test_an_unmatched_quote_is_left_alone(monkeypatch):
    """It could be part of the value. Guessing would be worse than leaving it."""
    monkeypatch.setenv("STRIPE_SECRET_KEY", '"sk_live_51ABC')
    assert env("STRIPE_SECRET_KEY") == '"sk_live_51ABC'


def test_a_missing_variable_gives_the_default():
    assert env("STRIPE_SECRET_KEY") == ""
    assert env("STRIPE_METER_EVENT_NAME", "assistant_tokens") == "assistant_tokens"


def test_a_variable_set_to_nothing_gives_the_default(monkeypatch):
    # Railway keeps an emptied variable rather than removing it.
    monkeypatch.setenv("STRIPE_METER_EVENT_NAME", "   ")
    assert env("STRIPE_METER_EVENT_NAME", "assistant_tokens") == "assistant_tokens"


# ===========================================================================
# Saying so, rather than failing at the vendor
# ===========================================================================

def test_a_key_that_is_not_a_key_is_reported(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "not-a-key-at-all")

    complaint = malformed("STRIPE_SECRET_KEY", env("STRIPE_SECRET_KEY"))
    assert complaint
    assert "sk_test_" in complaint


def test_the_complaint_does_not_print_the_secret(monkeypatch):
    """A health endpoint is read by people who should not see the key."""
    monkeypatch.setenv("STRIPE_SECRET_KEY", "wrong_but_secret_value_here")

    complaint = malformed("STRIPE_SECRET_KEY", env("STRIPE_SECRET_KEY"))
    assert "secret_value_here" not in complaint


def test_a_publishable_key_in_the_secret_slot_is_caught(monkeypatch):
    """An easy and expensive swap to make."""
    monkeypatch.setenv("STRIPE_SECRET_KEY", "pk_live_51ABC")
    assert malformed("STRIPE_SECRET_KEY", env("STRIPE_SECRET_KEY"))


def test_a_price_id_that_is_not_a_price_is_caught(monkeypatch):
    # A product id where a price id belongs fails at checkout with a message
    # nobody can act on.
    monkeypatch.setenv("STRIPE_PRICE_BASE", "prod_ABC123")
    assert malformed("STRIPE_PRICE_BASE", env("STRIPE_PRICE_BASE"))


def test_a_correct_key_draws_no_complaint(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_51ABC")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-abc")
    assert check_all() == []


def test_an_unset_credential_is_not_a_complaint():
    """Not configured is a state, not an error. Half the deployments are."""
    assert check_all() == []


# ===========================================================================
# Which Stripe is in use
# ===========================================================================

@pytest.mark.parametrize("key,expected", [
    ("sk_test_51ABC", "test"),
    ("rk_test_51ABC", "test"),
    ("sk_live_51ABC", "live"),
    ("rk_live_51ABC", "live"),
    ("garbage", "malformed"),
])
def test_the_mode_is_reported(monkeypatch, key, expected):
    """
    Worth saying out loud on a health check. "Am I about to charge a real
    card?" should not require reading an environment variable.
    """
    monkeypatch.setenv("STRIPE_SECRET_KEY", key)
    assert stripe_mode() == expected


def test_no_key_reads_as_unconfigured():
    assert stripe_mode() == "unconfigured"


def test_a_quoted_live_key_still_reads_as_live(monkeypatch):
    """The bug that started this: it was live all along, and unusable."""
    monkeypatch.setenv("STRIPE_SECRET_KEY", '"sk_live_51ABC"')
    assert stripe_mode() == "live"
