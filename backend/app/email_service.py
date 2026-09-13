"""
Transactional email, via Resend.

Two rules shape everything here.

**Email never breaks the thing that triggered it.** A booking that succeeded and
a confirmation that failed to send is a booking, not an error. Every send path
swallows its failure, records it, and returns — the caller is told whether it
worked but is never made to care.

**Every send is logged.** Silent email failure is the worst kind: the operator
believes the customer was told, the customer believes nothing was booked, and
nobody finds out until somebody does not turn up. The log is what makes that
visible.

On the markup: these templates are deliberately plain, light-background, and
inline-styled. The product's dark glow does not survive email — Gmail strips
most CSS, Outlook renders through Word, and client dark-mode inverts colours
unpredictably, which turns a carefully lit design into unreadable mud. A simple
light template that renders correctly everywhere beats a beautiful one that
renders correctly in Apple Mail.

Required env:
    RESEND_API_KEY      re_...
    EMAIL_FROM          "Business-EOS <hello@yourdomain.com>"  (verified domain)
    APP_URL             used to build links back into the product
"""

from __future__ import annotations

import html
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlmodel import Field, Session, SQLModel, select

from backend.app.models import utc_now_iso
from backend.app.tenancy import current_business_id

log = logging.getLogger(__name__)

RESEND_ENDPOINT = "https://api.resend.com/emails"
API_KEY = os.environ.get("RESEND_API_KEY", "")
FROM_ADDRESS = os.environ.get("EMAIL_FROM", "")
APP_URL = os.environ.get("APP_URL", "").rstrip("/")

TIMEOUT_SECONDS = 8


class EmailLog(SQLModel, table=True):
    """
    One row per attempt.

    Kept even on success so "did they get the confirmation?" has an answer
    other than a shrug.
    """

    __tablename__ = "email_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: Optional[int] = Field(default=None, index=True)

    to_address: str = Field(index=True)
    subject: str
    template: str = Field(index=True)      # booking_confirmation | support_escalation | ...

    status: str = Field(default="queued", index=True)   # sent | failed | skipped
    provider_id: str = ""                  # Resend's message id, for support queries
    error: str = ""

    # What the send was about, so a failure can be retried or chased without
    # reconstructing it from three other tables.
    reference_type: str = ""
    reference_id: Optional[int] = None

    created_at: str = Field(default_factory=utc_now_iso, index=True)


# ------------------------------------------------------------------ shell

def configured() -> bool:
    return bool(API_KEY and FROM_ADDRESS)


def _esc(value) -> str:
    return html.escape(str(value or ""))


def _shell(title: str, body_html: str, footer: str = "") -> str:
    """
    The one template everything else fills in.

    Table-based and inline-styled on purpose. Outlook renders HTML through Word,
    which does not support flexbox, grid, or most of the last decade of CSS.
    """
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{_esc(title)}</title></head>
<body style="margin:0;padding:0;background:#f5f4f2;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f5f4f2;padding:32px 12px;">
<tr><td align="center">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="max-width:520px;background:#ffffff;border-radius:12px;
                border:1px solid #e6e3df;overflow:hidden;">
    <tr><td style="padding:28px 32px 8px;">
      <div style="font:600 15px -apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
                  color:#1a1a1a;letter-spacing:-0.2px;">Business-EOS</div>
    </td></tr>
    <tr><td style="padding:8px 32px 28px;
               font:400 15px/1.65 -apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
               color:#3a3a3a;">
      {body_html}
    </td></tr>
    <tr><td style="padding:18px 32px 24px;border-top:1px solid #eeebe7;
               font:400 12px/1.6 -apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
               color:#8a8a8a;">
      {footer or "Sent by Business-EOS."}
    </td></tr>
  </table>
</td></tr></table>
</body></html>"""


def _button(label: str, url: str) -> str:
    """A link styled as a button. Not a <button> — email clients ignore those."""
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:22px 0;">'
        f'<tr><td style="background:#1a1a1a;border-radius:8px;">'
        f'<a href="{_esc(url)}" style="display:inline-block;padding:12px 22px;'
        f'font:600 14px -apple-system,BlinkMacSystemFont,Arial,sans-serif;'
        f'color:#ffffff;text-decoration:none;">{_esc(label)}</a>'
        f"</td></tr></table>"
    )


def _detail_rows(pairs) -> str:
    rows = "".join(
        f'<tr><td style="padding:6px 0;color:#8a8a8a;width:38%;">{_esc(k)}</td>'
        f'<td style="padding:6px 0;color:#1a1a1a;">{_esc(v)}</td></tr>'
        for k, v in pairs if v not in (None, "")
    )
    return f'<table role="presentation" width="100%" style="margin:18px 0;font-size:14px;">{rows}</table>'


# ------------------------------------------------------------------- send

def send(
    session: Session,
    *,
    to: str,
    subject: str,
    html_body: str,
    text_body: str,
    template: str,
    business_id: Optional[int] = None,
    reference_type: str = "",
    reference_id: Optional[int] = None,
    reply_to: Optional[str] = None,
) -> dict:
    """
    Send one email and record the attempt.

    Returns a result rather than raising. Callers are told what happened; none
    of them should abort their own work because of it.
    """
    entry = EmailLog(
        business_id=business_id,
        to_address=(to or "").lower().strip(),
        subject=subject,
        template=template,
        reference_type=reference_type,
        reference_id=reference_id,
    )

    if not entry.to_address:
        entry.status, entry.error = "skipped", "no recipient address"
        session.add(entry); session.commit()
        return {"sent": False, "reason": entry.error}

    if not configured():
        # Not an error. A deployment without email configured should still take
        # bookings; it just cannot tell anyone about them.
        entry.status, entry.error = "skipped", "email not configured"
        session.add(entry); session.commit()
        log.info("Email skipped (%s -> %s): not configured", template, entry.to_address)
        return {"sent": False, "reason": entry.error}

    payload = {
        "from": FROM_ADDRESS,
        "to": [entry.to_address],
        "subject": subject,
        "html": html_body,
        "text": text_body,
    }
    if reply_to:
        payload["reply_to"] = reply_to

    try:
        response = httpx.post(
            RESEND_ENDPOINT,
            json=payload,
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=TIMEOUT_SECONDS,
        )
        if response.status_code >= 400:
            entry.status = "failed"
            entry.error = f"{response.status_code}: {response.text[:280]}"
            log.warning("Resend rejected %s -> %s: %s", template, entry.to_address, entry.error)
        else:
            entry.status = "sent"
            entry.provider_id = (response.json() or {}).get("id", "")
    except Exception as exc:
        entry.status = "failed"
        entry.error = f"{exc.__class__.__name__}: {exc}"[:280]
        log.warning("Email send failed (%s -> %s): %s", template, entry.to_address, entry.error)

    session.add(entry)
    session.commit()
    return {"sent": entry.status == "sent", "reason": entry.error or None, "id": entry.provider_id}


def already_sent(session: Session, template: str, reference_type: str, reference_id: int) -> bool:
    """
    Guard against duplicates.

    A retried request or a double-clicked button must not send a customer two
    confirmations for one booking.
    """
    return bool(session.exec(
        select(EmailLog).where(
            EmailLog.template == template,
            EmailLog.reference_type == reference_type,
            EmailLog.reference_id == reference_id,
            EmailLog.status == "sent",
        )
    ).first())


# -------------------------------------------------------------- templates

def booking_confirmation(session: Session, booking, service, business) -> dict:
    """To the customer, immediately after they book."""
    if already_sent(session, "booking_confirmation", "booking", booking.id):
        return {"sent": False, "reason": "already sent"}

    when = f"{booking.booking_date} at {booking.booking_time}"
    deposit_line = ""
    if booking.deposit_cents:
        deposit_line = (
            f'<p style="margin:16px 0;padding:12px 14px;background:#fdf6ee;'
            f'border:1px solid #f0dfc6;border-radius:8px;color:#6b4a1f;">'
            f"A deposit of ${booking.deposit_cents / 100:.2f} is due, and is not "
            f"refundable if you cancel within {service.cancellation_hours} hours."
            f"</p>"
        )

    body = (
        f"<p>Hi {_esc(booking.customer_name)},</p>"
        f"<p>You're booked in with <strong>{_esc(business.name)}</strong>.</p>"
        + _detail_rows([
            ("What", service.name),
            ("When", when),
            ("How long", f"{booking.duration_minutes} minutes"),
            ("Price", f"${booking.price:.2f}" if booking.price else None),
        ])
        + deposit_line
        + f"<p>Need to change it? Just reply to this email."
        f" Free cancellation up to {service.cancellation_hours} hours before.</p>"
    )

    text = (
        f"Hi {booking.customer_name},\n\n"
        f"You're booked in with {business.name}.\n\n"
        f"{service.name}\n{when}\n{booking.duration_minutes} minutes\n\n"
        f"Free cancellation up to {service.cancellation_hours} hours before.\n"
    )

    return send(
        session,
        to=booking.customer_email,
        subject=f"Booked: {service.name} on {booking.booking_date}",
        html_body=_shell("Booking confirmed", body, f"Booked with {_esc(business.name)}."),
        text_body=text,
        template="booking_confirmation",
        business_id=business.id,
        reference_type="booking",
        reference_id=booking.id,
    )


def new_booking_alert(session: Session, booking, service, business, to_address: str) -> dict:
    """To the operator, so a booking is not something they discover later."""
    if already_sent(session, "new_booking_alert", "booking", booking.id):
        return {"sent": False, "reason": "already sent"}

    body = (
        f"<p><strong>{_esc(booking.customer_name)}</strong> booked "
        f"{_esc(service.name)}.</p>"
        + _detail_rows([
            ("When", f"{booking.booking_date} at {booking.booking_time}"),
            ("Email", booking.customer_email),
            ("Phone", booking.customer_phone),
            ("Notes", booking.notes),
        ])
        + (_button("Open the diary", f"{APP_URL}/") if APP_URL else "")
    )
    text = (
        f"{booking.customer_name} booked {service.name}\n"
        f"{booking.booking_date} at {booking.booking_time}\n"
        f"{booking.customer_email} {booking.customer_phone}\n"
    )

    return send(
        session,
        to=to_address,
        subject=f"New booking: {booking.customer_name}, {booking.booking_date}",
        html_body=_shell("New booking", body),
        text_body=text,
        template="new_booking_alert",
        business_id=business.id,
        reference_type="booking",
        reference_id=booking.id,
        reply_to=booking.customer_email or None,
    )


def support_escalation(session: Session, ticket, business, to_address: str) -> dict:
    """
    To the operator, when the assistant could not answer.

    These piled up silently before this existed — the whole point of escalating
    is that a person finds out.
    """
    if already_sent(session, "support_escalation", "ticket", ticket.id):
        return {"sent": False, "reason": "already sent"}

    urgency_colour = {"high": "#b3261e", "normal": "#6b4a1f", "low": "#666666"}.get(
        ticket.urgency, "#666666"
    )

    body = (
        f'<p style="color:{urgency_colour};font-weight:600;margin:0 0 12px;">'
        f"{_esc(ticket.urgency.title())} priority</p>"
        f"<p>The assistant could not answer this and handed it to a person.</p>"
        f'<blockquote style="margin:18px 0;padding:14px 16px;background:#f7f6f4;'
        f'border-left:3px solid #d8d4ce;border-radius:0 8px 8px 0;color:#1a1a1a;">'
        f"{_esc(ticket.question)}</blockquote>"
        + _detail_rows([("Workspace", business.name), ("Contact", ticket.contact_email)])
        + (_button("Open Business-EOS", f"{APP_URL}/") if APP_URL else "")
    )
    text = (
        f"[{ticket.urgency}] The assistant could not answer:\n\n"
        f"{ticket.question}\n\nWorkspace: {business.name}\n"
        f"Contact: {ticket.contact_email}\n"
    )

    return send(
        session,
        to=to_address,
        subject=f"[{ticket.urgency}] Someone needs a human — {business.name}",
        html_body=_shell("Support needed", body),
        text_body=text,
        template="support_escalation",
        business_id=business.id,
        reference_type="ticket",
        reference_id=ticket.id,
        reply_to=ticket.contact_email or None,
    )


def password_reset_code(session: Session, user, code: str, minutes: int) -> dict:
    """
    Emailed only when the account actually has an address.

    Most staff accounts will not — they are provisioned by a manager. The
    manager-read-it-aloud flow remains the primary path; this is a convenience
    for owners, not a replacement.
    """
    body = (
        f"<p>Hi {_esc(user.username)},</p>"
        f"<p>Someone asked to reset your Business-EOS password. "
        f"Use this code within {minutes} minutes:</p>"
        f'<p style="margin:20px 0;padding:16px;background:#f7f6f4;border-radius:10px;'
        f'text-align:center;font:600 26px \'SF Mono\',Menlo,monospace;'
        f'letter-spacing:4px;color:#1a1a1a;">{_esc(code)}</p>'
        f"<p>If this wasn't you, ignore this email — nothing has changed, and "
        f"your current password still works.</p>"
    )
    text = (
        f"Hi {user.username},\n\nYour Business-EOS reset code is {code}\n"
        f"It expires in {minutes} minutes.\n\n"
        f"If this wasn't you, ignore this email. Nothing has changed.\n"
    )

    return send(
        session,
        to=user.email or "",
        subject="Your Business-EOS reset code",
        html_body=_shell("Reset your password", body,
                         "If you did not request this, no action is needed."),
        text_body=text,
        template="password_reset",
        reference_type="user",
        reference_id=user.id,
    )


def booking_cancelled(session: Session, booking, service, business) -> dict:
    """To the customer, confirming a cancellation went through."""
    body = (
        f"<p>Hi {_esc(booking.customer_name)},</p>"
        f"<p>Your {_esc(service.name)} on {_esc(booking.booking_date)} at "
        f"{_esc(booking.booking_time)} has been cancelled.</p>"
        f"<p>Book again any time.</p>"
    )
    text = (
        f"Hi {booking.customer_name},\n\n"
        f"Your {service.name} on {booking.booking_date} at {booking.booking_time} "
        f"has been cancelled.\n"
    )
    return send(
        session,
        to=booking.customer_email,
        subject=f"Cancelled: {service.name} on {booking.booking_date}",
        html_body=_shell("Booking cancelled", body, f"{_esc(business.name)}"),
        text_body=text,
        template="booking_cancelled",
        business_id=business.id,
        reference_type="booking",
        reference_id=booking.id,
    )


# ------------------------------------------------------------------ status

from fastapi import APIRouter, Depends  # noqa: E402
from backend.app.auth import user_from_request  # noqa: E402
from backend.app.database import get_session  # noqa: E402
from backend.app.models import UserAccount  # noqa: E402

router = APIRouter(prefix="/email", tags=["email"])


@router.get("/status")
def email_status(
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """
    Whether email works, and what it has been doing.

    Surfaced in the product rather than left to server logs, because the person
    who needs to know a confirmation bounced is the operator, not whoever has
    shell access.
    """
    business_id = current_business_id()

    rows = session.exec(
        select(EmailLog)
        .where(EmailLog.business_id == business_id)
        .order_by(EmailLog.id.desc())
    ).all()

    recent = rows[:50]
    failed = [r for r in rows if r.status == "failed"]

    return {
        "configured": configured(),
        "from_address": FROM_ADDRESS if configured() else None,
        "sent": sum(1 for r in rows if r.status == "sent"),
        "failed": len(failed),
        "skipped": sum(1 for r in rows if r.status == "skipped"),
        "recent": [
            {
                "to": r.to_address,
                "subject": r.subject,
                "template": r.template,
                "status": r.status,
                "error": r.error,
                "at": r.created_at,
            }
            for r in recent
        ],
        "note": (
            "Email is not configured on this deployment. Bookings still work; "
            "nobody is told about them."
            if not configured()
            else None
        ),
    }
