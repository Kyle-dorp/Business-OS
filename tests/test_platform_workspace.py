"""
What the app is told about itself when it loads.

/platform/workspace is the first authenticated call the frontend makes and the
only one it makes on every page. It returned the business, the role, the
locations and the module rows — and the module rows are keys. `inventory`,
`accounting`, `team`. Keys are not something a person can read.

That is most of why twenty-one pages read as one undifferentiated product
rather than ten modules somebody is paying for separately: the app knew which
module a page belonged to and could not say its name, so it said nothing, and
every page opened with a decorative eyebrow instead.

The registry rides along now. One call, one source of truth, and the frontend
never has to keep its own copy of what a module is called — which is the
mistake the landing page made for months.
"""

from __future__ import annotations

import uuid

import pytest
from sqlmodel import Session

from backend.app.database import engine
from backend.app.modules_registry import ALWAYS_ON, CATALOGUE
from backend.app.tenancy import set_current_business_id


@pytest.fixture
def shop(client):
    suffix = uuid.uuid4().hex[:6]
    response = client.post("/auth/signup", json={
        "username": f"ws{suffix}",
        "password": "a-real-password-123",
        "business_name": f"Workspace {suffix}",
    })
    assert response.status_code == 200, response.text
    body = response.json()
    yield {
        "client": client,
        "headers": {
            "Authorization": f"Bearer {body['token']}",
            "X-Business-Id": str(body["business"]["id"]),
        },
    }
    set_current_business_id(1)


def _workspace(shop) -> dict:
    response = shop["client"].get("/platform/workspace", headers=shop["headers"])
    assert response.status_code == 200, response.text
    return response.json()


def test_the_workspace_carries_the_catalogue(shop):
    body = _workspace(shop)
    assert "catalogue" in body, "the app cannot name a module it is only given a key for"
    assert len(body["catalogue"]) == len(CATALOGUE)


def test_every_module_row_can_be_given_a_name(shop):
    """
    The property that matters: for every module the workspace has switched on
    or off, the same response can say what it is called. A row without a
    matching catalogue entry is a page the app can gate but not describe.
    """
    body = _workspace(shop)
    named = {m["key"] for m in body["catalogue"]}
    unnameable = [row["module_key"] for row in body["modules"] if row["module_key"] not in named]
    assert unnameable == []


def test_the_catalogue_says_which_modules_are_never_charged_for(shop):
    """
    Overview, Settings and Notifications are always on. The tag in the topbar
    reads `billable` to decide whether to say anything about money, and a price
    beside Settings would simply be false.
    """
    body = _workspace(shop)
    free = {m["key"] for m in body["catalogue"] if not m["billable"]}
    assert free == set(ALWAYS_ON)


def test_it_carries_the_tagline_the_tag_shows_on_hover(shop):
    body = _workspace(shop)
    for module in body["catalogue"]:
        if module["billable"]:
            assert module["tagline"], f"{module['key']} has nothing to say for itself"


def test_it_is_still_one_call(shop):
    """
    The point of putting the catalogue here rather than behind its own endpoint
    is that the app already makes this call on every load. If somebody later
    strips it back out, the frontend will start needing a second request to
    render a label.
    """
    body = _workspace(shop)
    for key in ("business", "role", "modules", "catalogue", "user"):
        assert key in body, f"/platform/workspace no longer returns {key}"
