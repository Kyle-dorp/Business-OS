"""
The chat library.

Two of the three assistants had no memory of a conversation beyond the browser
tab it happened in. The business agent took a thread id the client invented and
a history array the client kept, so closing the tab lost the thread. It did
write every turn to AgentThread — and nothing ever read those rows back, so the
record existed, cost a write, and was useless.

Conversations are stored and browsable now, all three surfaces in one table,
because a chat library is one list to the person reading it.

The assertions that matter here are the boundary ones. A thread is a record of
somebody asking an assistant about the business, and the business assistant can
see every invoice and every colleague's pay. Two people in the same workspace
are inside the same tenant boundary and must still not be able to read each
other's conversations.
"""

from __future__ import annotations

import uuid

import pytest
from sqlmodel import Session, select

from backend.app.auth import hash_password
from backend.app.database import engine
from backend.app.models import AssistantMessage, AssistantThread, Membership, UserAccount
from backend.app.tenancy import set_current_business_id
from backend.app.threads import (
    KEEP_RECENT_TURNS,
    SUMMARY_ROLE,
    _title_from,
    add_message,
    compact,
    get_or_create,
    history_for,
)


@pytest.fixture
def shop(client):
    """An owner and a second user in the same workspace."""
    suffix = uuid.uuid4().hex[:6]
    signup = client.post("/auth/signup", json={
        "username": f"own{suffix}", "password": "a-real-password-123",
        "business_name": f"Threads {suffix}",
    })
    assert signup.status_code == 200, signup.text
    body = signup.json()
    bid = body["business"]["id"]
    set_current_business_id(bid)

    with Session(engine) as s:
        other = UserAccount(username=f"two{suffix}",
                            password_hash=hash_password("a-real-password-123"),
                            role="manager", active=True)
        s.add(other); s.flush()
        s.add(Membership(business_id=bid, user_id=other.id, role="manager", active=True))
        s.commit()
        other_id = other.id

    second = client.post("/auth/login", json={
        "username": f"two{suffix}", "password": "a-real-password-123",
    })
    assert second.status_code == 200, second.text

    yield {
        "client": client,
        "business_id": bid,
        "owner_id": body["user"]["id"] if "user" in body else None,
        "other_id": other_id,
        "owner": {"Authorization": f"Bearer {body['token']}",
                  "X-Business-Id": str(bid)},
        "other": {"Authorization": f"Bearer {second.json()['token']}",
                  "X-Business-Id": str(bid)},
    }
    set_current_business_id(1)


def _user(shop, which="owner") -> UserAccount:
    set_current_business_id(shop["business_id"])
    with Session(engine) as s:
        if which == "other":
            return s.get(UserAccount, shop["other_id"])
        membership = s.exec(
            select(Membership).where(
                Membership.business_id == shop["business_id"],
                Membership.user_id != shop["other_id"],
            )
        ).first()
        return s.get(UserAccount, membership.user_id)


# ===========================================================================
# Naming and creating
# ===========================================================================

def test_a_thread_is_named_after_the_first_thing_said_in_it():
    """
    Better than "New chat" for finding something a week later, and cheaper than
    asking a model to name it — which would mean paying for a title.
    """
    assert _title_from("why is labour up this week") == "why is labour up this week"


def test_a_long_first_message_is_cut_at_a_word():
    title = _title_from("why is my labour percentage so much higher than it was "
                        "last month across both of the locations")
    assert len(title) <= 48
    assert not title.rstrip("…").endswith(" ")
    assert "…" in title


def test_an_empty_first_message_still_gets_a_name():
    assert _title_from("   ") == "New chat"


def test_creating_a_thread_stores_it(shop):
    user = _user(shop)
    set_current_business_id(shop["business_id"])
    with Session(engine) as s:
        thread = get_or_create(s, user, surface="business", first_message="hello")
        assert thread.id is not None
        assert thread.surface == "business"
        assert thread.archived is False


# ===========================================================================
# The boundary
# ===========================================================================

def test_you_cannot_read_somebody_elses_conversation(shop):
    """
    The one that matters. Both users are in the same workspace and inside the
    same tenant boundary, and a business-assistant thread is a transcript of
    somebody asking about invoices, payroll and pay bands.
    """
    owner = _user(shop)
    set_current_business_id(shop["business_id"])
    with Session(engine) as s:
        thread = get_or_create(s, owner, surface="business",
                               first_message="what did we pay Priya last month")
        thread_id = thread.id

    response = shop["client"].get(f"/threads/{thread_id}", headers=shop["other"])
    assert response.status_code == 403


def test_you_cannot_rename_somebody_elses_conversation(shop):
    owner = _user(shop)
    set_current_business_id(shop["business_id"])
    with Session(engine) as s:
        thread_id = get_or_create(s, owner, surface="business", first_message="x").id

    response = shop["client"].patch(f"/threads/{thread_id}",
                                    json={"title": "mine now"}, headers=shop["other"])
    assert response.status_code == 403


def test_you_cannot_delete_somebody_elses_conversation(shop):
    owner = _user(shop)
    set_current_business_id(shop["business_id"])
    with Session(engine) as s:
        thread_id = get_or_create(s, owner, surface="business", first_message="x").id

    assert shop["client"].delete(f"/threads/{thread_id}",
                                 headers=shop["other"]).status_code == 403


def test_the_list_shows_only_your_own(shop):
    owner = _user(shop)
    other = _user(shop, "other")
    set_current_business_id(shop["business_id"])
    with Session(engine) as s:
        get_or_create(s, owner, surface="business", first_message="the owner asked this")
        get_or_create(s, other, surface="business", first_message="the other one asked this")

    titles = [t["title"] for t in shop["client"].get("/threads", headers=shop["owner"]).json()]
    assert "the owner asked this" in titles
    assert "the other one asked this" not in titles


def test_a_missing_thread_is_not_found_rather_than_forbidden(shop):
    """
    404 rather than 403 for something that does not exist, or the difference
    between the two answers tells somebody which ids are real.
    """
    assert shop["client"].get("/threads/999999", headers=shop["owner"]).status_code == 404


# ===========================================================================
# The library
# ===========================================================================

def test_threads_are_listed_newest_first(shop):
    user = _user(shop)
    set_current_business_id(shop["business_id"])
    with Session(engine) as s:
        first_id = get_or_create(s, user, surface="business", first_message="older").id
        second = get_or_create(s, user, surface="business", first_message="newer")
        second_id = second.id
        add_message(s, second, "user", "newer")   # touches updated_at

    listed = shop["client"].get("/threads", headers=shop["owner"]).json()
    ids = [t["id"] for t in listed]
    assert ids.index(second_id) < ids.index(first_id)


def test_the_list_can_be_filtered_to_one_assistant(shop):
    user = _user(shop)
    set_current_business_id(shop["business_id"])
    with Session(engine) as s:
        get_or_create(s, user, surface="business", first_message="about the money")
        get_or_create(s, user, surface="personal", first_message="about my shifts")

    only = shop["client"].get("/threads?surface=personal", headers=shop["owner"]).json()
    assert [t["surface"] for t in only] == ["personal"]


def test_archiving_hides_it_without_destroying_it(shop):
    """
    A conversation with an assistant about the business is a record of what was
    asked and answered. Quietly destroying that on a misclick is worse than a
    longer list.
    """
    user = _user(shop)
    set_current_business_id(shop["business_id"])
    with Session(engine) as s:
        thread_id = get_or_create(s, user, surface="business", first_message="keep me").id

    shop["client"].post(f"/threads/{thread_id}/archive", headers=shop["owner"])

    visible = shop["client"].get("/threads", headers=shop["owner"]).json()
    assert thread_id not in [t["id"] for t in visible]

    with_archived = shop["client"].get("/threads?include_archived=true",
                                       headers=shop["owner"]).json()
    assert thread_id in [t["id"] for t in with_archived]


def test_deleting_takes_the_messages_with_it(shop):
    """An orphaned message is a transcript nobody can see and nobody can remove."""
    user = _user(shop)
    set_current_business_id(shop["business_id"])
    with Session(engine) as s:
        thread = get_or_create(s, user, surface="business", first_message="go away")
        add_message(s, thread, "user", "go away")
        add_message(s, thread, "assistant", "alright")
        thread_id = thread.id

    shop["client"].delete(f"/threads/{thread_id}", headers=shop["owner"])

    with Session(engine) as s:
        left = s.exec(
            select(AssistantMessage).where(AssistantMessage.thread_id == thread_id)
        ).all()
    assert left == []


# ===========================================================================
# Compaction
# ===========================================================================

def test_compaction_keeps_the_recent_turns_and_folds_the_rest(shop):
    user = _user(shop)
    set_current_business_id(shop["business_id"])
    with Session(engine) as s:
        thread = get_or_create(s, user, surface="business", first_message="start")
        for i in range(30):
            add_message(s, thread, "user" if i % 2 == 0 else "assistant", f"turn {i}")

        folded = compact(s, thread, "They asked about labour cost and stock.")

        rows = s.exec(
            select(AssistantMessage)
            .where(AssistantMessage.thread_id == thread.id)
            .order_by(AssistantMessage.id)
        ).all()

    assert folded == 30 - KEEP_RECENT_TURNS - 1, (
        'the oldest row is converted into the summary rather than deleted'
    )
    assert len(rows) == KEEP_RECENT_TURNS + 1, "the recent turns plus one summary"
    assert rows[0].role == SUMMARY_ROLE, 'the summary belongs at the top'
    assert rows[-1].content == "turn 29", "the most recent turn must survive"


def test_a_short_thread_is_left_alone(shop):
    user = _user(shop)
    set_current_business_id(shop["business_id"])
    with Session(engine) as s:
        thread = get_or_create(s, user, surface="business", first_message="brief")
        for i in range(4):
            add_message(s, thread, "user", f"turn {i}")

        assert compact(s, thread, "nothing to say") == 0


def test_the_summary_is_sent_to_the_model_as_context(shop):
    """
    Compaction has to be invisible to the model and visible to the person. The
    summary goes back as an assistant turn saying what came before, rather than
    as a gap where the conversation used to be.
    """
    user = _user(shop)
    set_current_business_id(shop["business_id"])
    with Session(engine) as s:
        thread = get_or_create(s, user, surface="business", first_message="start")
        for i in range(30):
            add_message(s, thread, "user" if i % 2 == 0 else "assistant", f"turn {i}")
        compact(s, thread, "They asked about labour cost.")

        turns = history_for(s, thread)

    assert any("Earlier in this conversation" in t["content"] for t in turns)
    assert all(t["role"] in ("user", "assistant") for t in turns), (
        "the model only understands user and assistant"
    )


def test_compaction_does_not_stack_summaries(shop):
    """
    Folding twice must not leave a summary of a summary of a summary — the
    older summary is swept up with everything else it describes.
    """
    user = _user(shop)
    set_current_business_id(shop["business_id"])
    with Session(engine) as s:
        thread = get_or_create(s, user, surface="business", first_message="start")
        for i in range(30):
            add_message(s, thread, "user", f"turn {i}")
        compact(s, thread, "first summary")
        for i in range(30):
            add_message(s, thread, "user", f"later {i}")
        compact(s, thread, "second summary")

        rows = s.exec(
            select(AssistantMessage).where(AssistantMessage.thread_id == thread.id)
        ).all()

    summaries = [row for row in rows if row.role == SUMMARY_ROLE]
    assert len(summaries) == 1
    assert summaries[0].content == "second summary"
