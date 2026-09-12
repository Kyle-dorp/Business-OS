"""
Tables backing the conversational agent and AI support.

Kept in their own module so the agent can be added without touching the
core schema. Import this from main.py before create_all() so the tables
are registered with SQLModel's metadata.
"""

from __future__ import annotations

from typing import Optional

from sqlmodel import Field, SQLModel

from backend.app.models import utc_now_iso
from backend.app.tenancy import current_business_id


class AgentProposal(SQLModel, table=True):
    """
    A write the agent wants to make, held until a human confirms it.

    The agent never mutates business data directly. It produces one of these,
    the operator sees exactly what will change, and only an explicit confirm
    executes it. That boundary is what makes it safe to let a language model
    near a general ledger: text that arrives from a customer record, an
    invoice note, or a supplier email cannot silently become an action.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(default_factory=current_business_id, index=True)
    user_id: int = Field(index=True)
    thread_id: str = Field(index=True)

    entity_type: str                       # contact | invoice | inventory_item | task | booking
    action: str                            # create | update | delete
    entity_id: Optional[int] = None        # None for create
    changes_json: str = "{}"               # the exact field set to write
    summary: str = ""                      # plain-English description shown to the operator

    status: str = Field(default="pending", index=True)   # pending | applied | rejected | expired
    prompt_excerpt: str = ""               # what the operator asked that produced this
    created_at: str = Field(default_factory=utc_now_iso)
    resolved_at: Optional[str] = None


class SupportTicket(SQLModel, table=True):
    """
    Raised when the assistant cannot answer something and a human is needed.

    The assistant answers what it can and escalates the rest rather than
    guessing — a wrong confident answer about someone's payroll or tax
    position is worse than no answer.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(default_factory=current_business_id, index=True)
    user_id: Optional[int] = Field(default=None, index=True)

    question: str
    context: str = ""
    urgency: str = "normal"                # low | normal | high
    contact_email: str = ""
    contact_phone: str = ""

    status: str = Field(default="open", index=True)   # open | answered | closed
    answer: str = ""
    created_at: str = Field(default_factory=utc_now_iso)
    answered_at: Optional[str] = None


class AgentThread(SQLModel, table=True):
    """Conversation continuity for the agent, scoped to one workspace."""

    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(default_factory=current_business_id, index=True)
    user_id: int = Field(index=True)
    thread_id: str = Field(index=True)
    role: str                              # user | assistant
    content: str
    created_at: str = Field(default_factory=utc_now_iso)
