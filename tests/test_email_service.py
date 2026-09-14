"""
Transactional email.

Two properties matter more than delivery itself.

Email must never break what triggered it. A booking that succeeded and a
confirmation that failed is a booking, not an error — so every send path
records the failure and returns rather than raising into the caller.

And nothing user-supplied may reach an inbox unescaped. A customer name goes
straight into an email body, which makes it the same injection surface as a web
page, with the difference that nobody is watching.
"""

from __future__ import annotations

import uuid

import pytest
from sqlmodel import Session, select

from backend.app import email_service
from backend.app.database import engine


# ------------------------------------------------------------------ escaping

@pytest.mark.parametrize(
    "hostile",
    [
        "<script>alert(1)</script>",
        'Bobby "><img src=x onerror=alert(1)>',
        "<b>not bold</b>",
        "<a href='http://evil.example'>click</a>",
    ],
)
def test_markup_in_user_data_is_escaped(hostile):
    """A customer name is untrusted text, and an inbox renders HTML."""
    escaped = email_service._esc(hostile)
    assert "<" not in escaped
    assert ">" not in escaped


def test_escaping_preserves_ordinary_punctuation():
    """Over-escaping is its own bug: nobody wants to be greeted as O&#x27;Brien."""
    assert "OBrien" in email_service._esc("OBrien").replace("&#x27;", "")
    assert "Sons" in email_service._esc("Smith & Sons")


def test_none_becomes_empty_rather_than_the_word_none(self=None):
    assert email_service._esc(None) == ""


def test_the_shell_escapes_its_title():
    html = email_service._shell("<script>x</script>", "<p>body</p>")
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;" in html


def test_detail_rows_drop_empty_values():
    """A table row reading "Phone: —" is noise; omitting it is the point."""
    html = email_service._detail_rows([("Name", "Sam"), ("Phone", ""), ("Note", None)])
    assert "Sam" in html
    assert "Phone" not in html
    assert "Note" not in html


def test_a_button_is_a_link_not_a_button_element():
    """Email clients ignore <button>. A styled anchor is the only thing that works."""
    html = email_service._button("Open", "https://example.com/x")
    assert "<a href=" in html
    assert "<button" not in html


# ------------------------------------------------------------- configuration

def test_email_is_considered_unconfigured_without_both_settings(monkeypatch):
    monkeypatch.setattr(email_service, "API_KEY", "")
    monkeypatch.setattr(email_service, "FROM_ADDRESS", "")
    assert email_service.configured() is False

    monkeypatch.setattr(email_service, "API_KEY", "re_test")
    assert email_service.configured() is False, "a key without a from-address is not configured"

    monkeypatch.setattr(email_service, "FROM_ADDRESS", "Test <a@b.com>")
    assert email_service.configured() is True


def test_sending_without_configuration_is_skipped_not_failed(monkeypatch):
    """
    A deployment with no email set up should still take bookings; it just
    cannot tell anyone about them. Recording that as a failure would make a
    working system look broken.
    """
    monkeypatch.setattr(email_service, "API_KEY", "")
    monkeypatch.setattr(email_service, "FROM_ADDRESS", "")

    with Session(engine) as s:
        result = email_service.send(
            s, to="someone@example.com", subject="Hi", html_body="<p>x</p>",
            text_body="x", template="test_skip",
        )

    assert result["sent"] is False
    assert "not configured" in result["reason"]


def test_a_missing_recipient_is_skipped(monkeypatch):
    monkeypatch.setattr(email_service, "API_KEY", "re_test")
    monkeypatch.setattr(email_service, "FROM_ADDRESS", "Test <a@b.com>")

    with Session(engine) as s:
        result = email_service.send(
            s, to="", subject="Hi", html_body="<p>x</p>",
            text_body="x", template="test_no_recipient",
        )

    assert result["sent"] is False
    assert "recipient" in result["reason"]


def test_every_attempt_is_logged(monkeypatch):
    """
    Silent email failure is the worst kind: the operator believes the customer
    was told and the customer believes nothing was booked. The log is what
    makes that visible.
    """
    monkeypatch.setattr(email_service, "API_KEY", "")
    monkeypatch.setattr(email_service, "FROM_ADDRESS", "")
    template = f"logged_{uuid.uuid4().hex[:6]}"

    with Session(engine) as s:
        email_service.send(
            s, to="someone@example.com", subject="Hi", html_body="<p>x</p>",
            text_body="x", template=template,
        )

    with Session(engine) as s:
        rows = s.exec(
            select(email_service.EmailLog).where(email_service.EmailLog.template == template)
        ).all()
    assert len(rows) == 1
    assert rows[0].status == "skipped"


def test_a_provider_failure_is_recorded_rather_than_raised(monkeypatch):
    """The caller finished its work. An unreachable provider must not undo it."""
    monkeypatch.setattr(email_service, "API_KEY", "re_test")
    monkeypatch.setattr(email_service, "FROM_ADDRESS", "Test <a@b.com>")

    def explode(*args, **kwargs):
        raise ConnectionError("provider unreachable")

    monkeypatch.setattr(email_service.httpx, "post", explode)
    template = f"failed_{uuid.uuid4().hex[:6]}"

    with Session(engine) as s:
        result = email_service.send(
            s, to="someone@example.com", subject="Hi", html_body="<p>x</p>",
            text_body="x", template=template,
        )

    assert result["sent"] is False
    with Session(engine) as s:
        rows = s.exec(
            select(email_service.EmailLog).where(email_service.EmailLog.template == template)
        ).all()
    assert rows[0].status == "failed"
    assert "ConnectionError" in rows[0].error


def test_recipients_are_normalised(monkeypatch):
    """One person should not appear as three addresses in the log."""
    monkeypatch.setattr(email_service, "API_KEY", "")
    monkeypatch.setattr(email_service, "FROM_ADDRESS", "")
    template = f"norm_{uuid.uuid4().hex[:6]}"

    with Session(engine) as s:
        email_service.send(
            s, to="  Sam@Example.COM  ", subject="Hi", html_body="<p>x</p>",
            text_body="x", template=template,
        )

    with Session(engine) as s:
        row = s.exec(
            select(email_service.EmailLog).where(email_service.EmailLog.template == template)
        ).first()
    assert row.to_address == "sam@example.com"


# -------------------------------------------------------------- duplicates

def test_a_successful_send_blocks_a_repeat(monkeypatch):
    """
    A retried request or a double-clicked button must not send one customer two
    confirmations for one booking.
    """
    monkeypatch.setattr(email_service, "API_KEY", "re_test")
    monkeypatch.setattr(email_service, "FROM_ADDRESS", "Test <a@b.com>")

    class Ok:
        status_code = 200
        text = "{}"

        @staticmethod
        def json():
            return {"id": "msg_123"}

    monkeypatch.setattr(email_service.httpx, "post", lambda *a, **k: Ok())
    template = f"dup_{uuid.uuid4().hex[:6]}"
    reference_id = 4242

    with Session(engine) as s:
        assert not email_service.already_sent(s, template, "booking", reference_id)
        email_service.send(
            s, to="someone@example.com", subject="Hi", html_body="<p>x</p>",
            text_body="x", template=template,
            reference_type="booking", reference_id=reference_id,
        )

    with Session(engine) as s:
        assert email_service.already_sent(s, template, "booking", reference_id)


def test_a_failed_send_does_not_block_a_retry(monkeypatch):
    """Only a delivered message should suppress the next attempt."""
    monkeypatch.setattr(email_service, "API_KEY", "")
    monkeypatch.setattr(email_service, "FROM_ADDRESS", "")
    template = f"retry_{uuid.uuid4().hex[:6]}"

    with Session(engine) as s:
        email_service.send(
            s, to="someone@example.com", subject="Hi", html_body="<p>x</p>",
            text_body="x", template=template,
            reference_type="booking", reference_id=777,
        )
        assert not email_service.already_sent(s, template, "booking", 777)
