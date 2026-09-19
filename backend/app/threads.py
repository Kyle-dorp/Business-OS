"""
The chat library: conversations you can come back to.

Two of the three assistants had no memory of a conversation beyond the browser
tab it happened in. The business agent took a `thread_id` the client made up and
a `history` array the client kept, so closing the tab lost the thread — and
anybody reading the database could see messages but not which conversation they
belonged to.

They are stored now, all three surfaces in one table, because a chat library is
one list to the person reading it. Splitting the storage by assistant would mean
merging it back on every read and getting the ordering wrong.

Compaction
----------
A long thread costs more every turn: the whole history is re-sent each time, on
top of a business context that is already 46,000 tokens on a large workspace.
Past a threshold the older turns are replaced by a summary of them, which is
kept as a real message so the person can see it happened rather than watching
their conversation quietly lose its memory.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.app.auth import user_from_request
from backend.app.database import get_session
from backend.app.models import (
    AssistantMessage,
    AssistantThread,
    UserAccount,
    utc_now_iso,
)
from backend.app.tenancy import current_business_id

router = APIRouter(prefix="/threads", tags=["threads"])

# Which assistant a thread belongs to.
SURFACES = ("scheduling", "business", "personal")

# How many turns a thread carries before the older ones are folded into a
# summary. Chosen so a normal back-and-forth is never touched: most
# conversations with an assistant about a rota are under a dozen turns, and the
# ones that are not are the ones costing real money.
COMPACT_AFTER_TURNS = 24
KEEP_RECENT_TURNS = 8

SUMMARY_ROLE = "summary"


class ThreadOut(BaseModel):
    id: int
    title: str
    surface: str
    archived: bool
    updated_at: str
    message_count: int
    preview: str


class NewThread(BaseModel):
    surface: str = "business"
    title: str = ""


class RenameThread(BaseModel):
    title: str


def _owned(session: Session, thread_id: int, user: UserAccount) -> AssistantThread:
    """
    A thread, if it is this person's.

    Checked on the user as well as the workspace. A manager and an employee in
    the same business are both inside the tenant boundary, and one of them can
    see the company's finances — so "same workspace" is not the same question
    as "your conversation".
    """
    thread = session.get(AssistantThread, thread_id)
    if not thread or thread.business_id != current_business_id():
        raise HTTPException(404, "That conversation does not exist.")
    if thread.user_id != user.id:
        raise HTTPException(403, "That is somebody else's conversation.")
    return thread


def _title_from(message: str) -> str:
    """
    A name for a thread, taken from the first thing said in it.

    Better than "New chat" for finding something a week later, and cheaper than
    asking a model to name it — which would mean paying for a title.
    """
    cleaned = " ".join(message.split())
    if len(cleaned) <= 48:
        return cleaned or "New chat"
    return cleaned[:47].rsplit(" ", 1)[0] + "…"


def get_or_create(
    session: Session,
    user: UserAccount,
    *,
    surface: str,
    thread_id: Optional[int] = None,
    first_message: str = "",
) -> AssistantThread:
    if thread_id:
        return _owned(session, thread_id, user)

    thread = AssistantThread(
        business_id=current_business_id(),
        user_id=user.id,
        surface=surface,
        title=_title_from(first_message),
    )
    session.add(thread)
    session.commit()
    session.refresh(thread)
    return thread


def add_message(
    session: Session, thread: AssistantThread, role: str, content: str
) -> AssistantMessage:
    message = AssistantMessage(
        business_id=thread.business_id,
        user_id=thread.user_id,
        thread_id=thread.id,
        role=role,
        content=content,
    )
    session.add(message)
    thread.updated_at = utc_now_iso()
    session.add(thread)
    session.commit()
    session.refresh(message)
    return message


def history_for(session: Session, thread: AssistantThread) -> list[dict]:
    """
    The turns to send to the model, oldest first.

    A summary message is sent as an assistant turn describing what came before,
    which is what makes compaction invisible to the model and visible to the
    person.
    """
    rows = session.exec(
        select(AssistantMessage)
        .where(AssistantMessage.thread_id == thread.id)
        # Time first, then id as the tie-break: a compaction summary is
        # back-dated to the turns it replaces, so ordering by id alone would
        # put it last. See compact().
        .order_by(AssistantMessage.created_at, AssistantMessage.id)
    ).all()

    out: list[dict] = []
    for row in rows:
        if row.role == SUMMARY_ROLE:
            out.append({"role": "assistant", "content": f"[Earlier in this conversation: {row.content}]"})
        elif row.role in ("user", "assistant"):
            out.append({"role": row.role, "content": row.content})
    return out


def needs_compaction(session: Session, thread: AssistantThread) -> bool:
    count = session.exec(
        select(AssistantMessage).where(AssistantMessage.thread_id == thread.id)
    ).all()
    return len(count) > COMPACT_AFTER_TURNS


def compact(session: Session, thread: AssistantThread, summary: str) -> int:
    """
    Replace the older turns with one summary of them.

    Returns how many messages were folded. The summary is stored as a message
    rather than on the thread so it appears in the transcript where it happened
    — somebody scrolling up should find "earlier in this conversation" rather
    than a gap where their history used to be.
    """
    rows = session.exec(
        select(AssistantMessage)
        .where(AssistantMessage.thread_id == thread.id)
        # Time first, then id as the tie-break: a compaction summary is
        # back-dated to the turns it replaces, so ordering by id alone would
        # put it last. See compact().
        .order_by(AssistantMessage.created_at, AssistantMessage.id)
    ).all()

    if len(rows) <= KEEP_RECENT_TURNS:
        return 0

    older = rows[: len(rows) - KEEP_RECENT_TURNS]

    # The oldest message becomes the summary rather than a new row being added.
    #
    # Ordering is by id, and a new row gets the next one — so an inserted
    # summary sorts after the eight turns it is supposed to come before.
    # Somebody scrolling up would find "earlier in this conversation" at the
    # bottom, and the model would be handed a recap as the most recent thing
    # said. Back-dating created_at does not help: utc_now_iso has microsecond
    # resolution and thirty messages written in a loop share a timestamp, so
    # the id tie-break puts it last anyway.
    #
    # Reusing the oldest row keeps its id, which is its place in the
    # conversation. An existing summary is always older[0], so folding twice
    # overwrites it rather than stacking a summary of a summary.
    folded = older[0]
    folded.role = SUMMARY_ROLE
    folded.content = summary
    session.add(folded)

    for row in older[1:]:
        session.delete(row)

    session.commit()
    return len(older) - 1


# ===========================================================================
# The library
# ===========================================================================

@router.get("", response_model=list[ThreadOut])
def list_threads(
    surface: str = "",
    include_archived: bool = False,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """Your conversations, newest first."""
    query = select(AssistantThread).where(
        AssistantThread.business_id == current_business_id(),
        AssistantThread.user_id == user.id,
    )
    if surface:
        query = query.where(AssistantThread.surface == surface)
    if not include_archived:
        query = query.where(AssistantThread.archived == False)  # noqa: E712

    threads = sorted(
        session.exec(query).all(), key=lambda row: row.updated_at, reverse=True
    )

    out = []
    for thread in threads:
        messages = session.exec(
            select(AssistantMessage)
            .where(AssistantMessage.thread_id == thread.id)
            .order_by(AssistantMessage.id)
        ).all()
        first_user = next((m.content for m in messages if m.role == "user"), "")
        out.append(ThreadOut(
            id=thread.id,
            title=thread.title,
            surface=thread.surface,
            archived=thread.archived,
            updated_at=thread.updated_at,
            message_count=len(messages),
            preview=" ".join(first_user.split())[:120],
        ))
    return out


@router.post("", response_model=ThreadOut)
def create_thread(
    payload: NewThread,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    if payload.surface not in SURFACES:
        raise HTTPException(400, f"Unknown assistant: {payload.surface}")

    thread = AssistantThread(
        business_id=current_business_id(),
        user_id=user.id,
        surface=payload.surface,
        title=payload.title or "New chat",
    )
    session.add(thread)
    session.commit()
    session.refresh(thread)
    return ThreadOut(
        id=thread.id, title=thread.title, surface=thread.surface,
        archived=False, updated_at=thread.updated_at, message_count=0, preview="",
    )


@router.get("/{thread_id}")
def read_thread(
    thread_id: int,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    thread = _owned(session, thread_id, user)
    messages = session.exec(
        select(AssistantMessage)
        .where(AssistantMessage.thread_id == thread.id)
        # Time first, then id as the tie-break: a compaction summary is
        # back-dated to the turns it replaces, so ordering by id alone would
        # put it last. See compact().
        .order_by(AssistantMessage.created_at, AssistantMessage.id)
    ).all()
    return {
        "id": thread.id,
        "title": thread.title,
        "surface": thread.surface,
        "archived": thread.archived,
        "messages": [
            {"role": row.role, "content": row.content, "at": row.created_at}
            for row in messages
        ],
    }


@router.patch("/{thread_id}")
def rename_thread(
    thread_id: int,
    payload: RenameThread,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    thread = _owned(session, thread_id, user)
    title = " ".join(payload.title.split())
    if not title:
        raise HTTPException(400, "A conversation needs a name.")
    thread.title = title[:80]
    thread.updated_at = utc_now_iso()
    session.add(thread)
    session.commit()
    return {"id": thread.id, "title": thread.title}


@router.post("/{thread_id}/archive")
def archive_thread(
    thread_id: int,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """
    Archived rather than deleted.

    A conversation with an assistant about the business is a record of what was
    asked and what it answered, and quietly destroying that on a misclick is
    worse than a longer list.
    """
    thread = _owned(session, thread_id, user)
    thread.archived = True
    thread.updated_at = utc_now_iso()
    session.add(thread)
    session.commit()
    return {"id": thread.id, "archived": True}


@router.delete("/{thread_id}")
def delete_thread(
    thread_id: int,
    session: Session = Depends(get_session),
    user: UserAccount = Depends(user_from_request),
):
    """Actually gone, messages and all. Asked for explicitly."""
    thread = _owned(session, thread_id, user)
    for message in session.exec(
        select(AssistantMessage).where(AssistantMessage.thread_id == thread.id)
    ).all():
        session.delete(message)
    session.delete(thread)
    session.commit()
    return {"deleted": thread_id}
