"""
The platform admin panel.

Every other surface in this product is tenant-scoped, and the tests for them
ask "can one workspace see another's data?" — where the answer must be no.
This one is the inverse: /admin/* crosses every tenant boundary on purpose. It
exists so the operator of the platform can see who their customers are, what
they pay and what they cost.

Which makes the only question that matters a different one: **who gets in.**
A tenant-scoping bug leaks one workspace to one other. A bug here leaks every
workspace to anybody.

There was exactly one way to become an admin, and it was a public endpoint
that deleted every user in the database and then created an admin with a
hardcoded password. It is gone, and the last test in this file is the one that
keeps it gone.
"""

from __future__ import annotations

import uuid

import pytest
from sqlmodel import Session, select

from backend.app.auth import hash_password
from backend.app.database import engine
from backend.app.models import ApiUsage, Business, BusinessModule, Membership, UserAccount
from backend.app.platform import seed_business
from backend.app.tenancy import set_current_business_id


def _account(label: str, is_admin: bool = False):
    suffix = uuid.uuid4().hex[:6]
    creds = {"username": f"{label}{suffix}", "password": "a-test-password-123"}
    with Session(engine) as s:
        user = UserAccount(
            username=creds["username"],
            password_hash=hash_password(creds["password"]),
            role="manager",
            active=True,
            is_admin=is_admin,
        )
        s.add(user)
        s.flush()
        business = Business(name=f"{label} {suffix}", industry="general", active=True)
        s.add(business)
        s.flush()
        bid = business.id
        set_current_business_id(bid)
        try:
            seed_business(s, business, user, role="owner")
            s.commit()
        finally:
            set_current_business_id(1)
    return {"business_id": bid, "creds": creds, "username": creds["username"]}


def _headers(client, account):
    login = client.post("/auth/login", json=account["creds"])
    assert login.status_code == 200, login.text
    return {
        "Authorization": f"Bearer {login.json()['token']}",
        "X-Business-Id": str(account["business_id"]),
    }


@pytest.fixture
def platform(client):
    """One platform admin and one ordinary operator, in separate workspaces."""
    admin = _account("padmin", is_admin=True)
    tenant = _account("tenant", is_admin=False)
    yield {
        "client": client,
        "admin": admin,
        "tenant": tenant,
        "admin_headers": _headers(client, admin),
        "tenant_headers": _headers(client, tenant),
    }
    set_current_business_id(1)


ADMIN_ROUTES = [
    ("GET", "/admin/customers"),
    ("GET", "/admin/customers/1"),
    ("GET", "/admin/analytics"),
]


# ===========================================================================
# Who gets in
# ===========================================================================

@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_an_ordinary_operator_is_refused(platform, method, path):
    """
    The whole point. A signed-in customer is not a platform admin, and these
    routes hand back every other customer's name, plan and spend.

    The message is asserted too: a 403 from some unrelated membership check
    would pass a bare status assertion while saying nothing about whether the
    admin flag is what stopped them.
    """
    response = platform["client"].request(
        method, path, headers=platform["tenant_headers"]
    )
    assert response.status_code == 403, f"{method} {path} let a tenant in"
    assert "Admin access required" in response.json()["detail"]


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_a_signed_out_visitor_is_refused(platform, method, path):
    response = platform["client"].request(method, path)
    assert response.status_code == 401


def test_an_admin_gets_in(platform):
    """
    The other half. A test that only checks tenants are refused would also
    pass if the panel were broken for everybody.
    """
    for path in ("/admin/customers", "/admin/analytics"):
        response = platform["client"].get(path, headers=platform["admin_headers"])
        assert response.status_code == 200, f"{path}: {response.text}"

    detail = platform["client"].get(
        f"/admin/customers/{platform['tenant']['business_id']}",
        headers=platform["admin_headers"],
    )
    assert detail.status_code == 200, detail.text


def test_updating_a_customer_is_refused_to_an_operator(platform):
    """
    The one route here that writes. A tenant able to reach it could set their
    own monthly price to zero.
    """
    response = platform["client"].patch(
        f"/admin/customers/{platform['tenant']['business_id']}",
        headers=platform["tenant_headers"],
        json={"monthly_price_cents": 0},
    )
    assert response.status_code == 403


def test_a_tenant_cannot_discount_themselves(platform):
    """The same thing, checked by its effect rather than its status code."""
    bid = platform["tenant"]["business_id"]
    with Session(engine) as s:
        business = s.get(Business, bid)
        business.monthly_price_cents = 11_900
        s.add(business)
        s.commit()

    platform["client"].patch(
        f"/admin/customers/{bid}",
        headers=platform["tenant_headers"],
        json={"monthly_price_cents": 0, "plan": "free"},
    )

    with Session(engine) as s:
        assert s.get(Business, bid).monthly_price_cents == 11_900
        assert s.get(Business, bid).plan != "free"


def test_the_admin_flag_is_off_by_default():
    """
    Nobody becomes a platform admin by signing up. It is granted with database
    access, through scripts/grant_admin.py.
    """
    assert UserAccount.model_fields["is_admin"].default is False


def test_a_manager_role_is_not_a_platform_admin(platform):
    """
    Two different words that both read as "admin". A workspace manager runs
    their own business; a platform admin sees everybody's.
    """
    with Session(engine) as s:
        user = s.exec(
            select(UserAccount).where(
                UserAccount.username == platform["tenant"]["username"]
            )
        ).first()
        assert user.role == "manager"
        assert user.is_admin is False

    response = platform["client"].get(
        "/admin/customers", headers=platform["tenant_headers"]
    )
    assert response.status_code == 403


# ===========================================================================
# What an admin actually sees
# ===========================================================================

def test_the_customer_list_spans_every_workspace(platform):
    """
    The one place in the product where crossing the tenant boundary is the
    feature. If this narrowed to the admin's own workspace the panel would be
    useless.
    """
    listed = platform["client"].get(
        "/admin/customers", headers=platform["admin_headers"]
    ).json()
    ids = {row["id"] for row in listed}
    assert platform["admin"]["business_id"] in ids
    assert platform["tenant"]["business_id"] in ids, "the panel cannot see other customers"


def test_each_customer_row_names_its_owner(platform):
    listed = platform["client"].get(
        "/admin/customers", headers=platform["admin_headers"]
    ).json()
    row = next(r for r in listed if r["id"] == platform["tenant"]["business_id"])
    assert row["owner"] == platform["tenant"]["username"]


def test_a_workspace_with_no_owner_does_not_break_the_list(platform):
    """
    An orphaned workspace — the owner's membership deactivated, say — must not
    take down the whole panel with it. The page has to render for the other
    customers.
    """
    with Session(engine) as s:
        orphan = Business(name="Orphan", industry="general", active=True)
        s.add(orphan)
        s.commit()
        s.refresh(orphan)
        orphan_id = orphan.id

    listed = platform["client"].get(
        "/admin/customers", headers=platform["admin_headers"]
    )
    assert listed.status_code == 200
    row = next(r for r in listed.json() if r["id"] == orphan_id)
    assert row["owner"] == "N/A"


def test_profit_is_revenue_minus_what_the_assistant_cost(platform):
    """
    The number the whole panel exists for. If it is wrong, it is wrong in the
    direction of thinking a customer is profitable when they are not.
    """
    bid = platform["tenant"]["business_id"]
    with Session(engine) as s:
        business = s.get(Business, bid)
        business.monthly_price_cents = 11_900
        business.claude_api_cost_cents = 340
        s.add(business)
        s.commit()

    listed = platform["client"].get(
        "/admin/customers", headers=platform["admin_headers"]
    ).json()
    row = next(r for r in listed if r["id"] == bid)
    assert row["profit_cents"] == 11_560


def test_a_customer_costing_more_than_they_pay_shows_a_loss(platform):
    """A negative number here is the signal. Clamping it at zero would hide it."""
    bid = platform["tenant"]["business_id"]
    with Session(engine) as s:
        business = s.get(Business, bid)
        business.monthly_price_cents = 2_900
        business.claude_api_cost_cents = 5_000
        s.add(business)
        s.commit()

    listed = platform["client"].get(
        "/admin/customers", headers=platform["admin_headers"]
    ).json()
    row = next(r for r in listed if r["id"] == bid)
    assert row["profit_cents"] == -2_100


def test_the_list_shows_only_enabled_modules(platform):
    bid = platform["tenant"]["business_id"]
    with Session(engine) as s:
        rows = s.exec(
            select(BusinessModule).where(BusinessModule.business_id == bid)
        ).all()
        for row in rows:
            row.enabled = row.module_key in {"scheduling", "home"}
            s.add(row)
        s.commit()

    listed = platform["client"].get(
        "/admin/customers", headers=platform["admin_headers"]
    ).json()
    row = next(r for r in listed if r["id"] == bid)
    assert set(row["modules"]) == {"scheduling", "home"}


def test_detail_shows_disabled_modules_too(platform):
    """
    The list answers "what are they using", the detail answers "what could
    they switch on" — so the detail keeps the ones that are off.
    """
    bid = platform["tenant"]["business_id"]
    with Session(engine) as s:
        rows = s.exec(
            select(BusinessModule).where(BusinessModule.business_id == bid)
        ).all()
        for row in rows:
            row.enabled = row.module_key == "scheduling"
            s.add(row)
        s.commit()

    detail = platform["client"].get(
        f"/admin/customers/{bid}", headers=platform["admin_headers"]
    ).json()
    states = {m["key"]: m["enabled"] for m in detail["modules"]}
    assert states["scheduling"] is True
    assert any(value is False for value in states.values())


def test_detail_carries_the_usage_history(platform):
    bid = platform["tenant"]["business_id"]
    with Session(engine) as s:
        s.add(ApiUsage(business_id=bid, date="2026-09-10", feature="agent",
                       tokens_used=1_200, cost_cents=3))
        s.add(ApiUsage(business_id=bid, date="2026-09-11", feature="assistant",
                       tokens_used=800, cost_cents=2))
        s.commit()

    detail = platform["client"].get(
        f"/admin/customers/{bid}", headers=platform["admin_headers"]
    ).json()
    history = {row["date"]: row for row in detail["usage_history"]}
    assert history["2026-09-10"]["tokens"] == 1_200
    assert history["2026-09-11"]["feature"] == "assistant"


def test_an_unknown_customer_is_a_404_not_a_crash(platform):
    response = platform["client"].get(
        "/admin/customers/999999", headers=platform["admin_headers"]
    )
    assert response.status_code == 404


# ===========================================================================
# Platform analytics
# ===========================================================================

def test_analytics_totals_every_workspace(platform):
    response = platform["client"].get(
        "/admin/analytics", headers=platform["admin_headers"]
    ).json()
    assert response["total_customers"] >= 2
    assert response["total_profit_cents"] == (
        response["total_revenue_cents"] - response["total_api_cost_cents"]
    )


def test_the_average_survives_an_empty_platform(platform):
    """
    A platform with no customers is the state on day one, and a division by
    zero on the dashboard is a bad first impression of your own product.
    """
    response = platform["client"].get(
        "/admin/analytics", headers=platform["admin_headers"]
    )
    assert response.status_code == 200
    body = response.json()
    if body["total_customers"]:
        assert body["avg_revenue_per_customer_cents"] == (
            body["total_revenue_cents"] // body["total_customers"]
        )


# ===========================================================================
# The way in that used to exist
# ===========================================================================

def test_the_public_database_wipe_is_gone(client):
    """
    /auth/seed-businesses was reachable with no token, guarded only by a header
    string committed to a public repository, and it deleted every user and
    every business before creating an admin with a hardcoded password. One
    request from anybody who had read the repo.

    It stays deleted.
    """
    from backend.app.main import PUBLIC_PATHS

    assert "/auth/seed-businesses" not in PUBLIC_PATHS
    assert client.post("/auth/seed-businesses").status_code in (401, 404, 405)


def test_no_public_path_can_destroy_data(client):
    """
    The general form of that mistake. Anything reachable without a token is
    reachable by the entire internet, so nothing on that list may delete.
    """
    import json

    from backend.app.main import PUBLIC_PATHS, PUBLIC_PREFIXES

    spec = json.loads(client.get("/openapi.json").text)
    offenders = []
    for path, methods in spec["paths"].items():
        public = path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES)
        if public and "delete" in methods:
            offenders.append(path)
    assert not offenders, f"public routes that delete: {offenders}"


def test_nothing_hands_out_the_admin_flag_over_http(client):
    """
    Platform admin is granted with database access, never by a request. The
    check is crude on purpose: if a route ever starts accepting is_admin, this
    fails and somebody has to justify it.
    """
    import json

    spec = json.loads(client.get("/openapi.json").text)
    schemas = spec.get("components", {}).get("schemas", {})
    offenders = [
        name for name, schema in schemas.items()
        if "is_admin" in (schema.get("properties") or {})
    ]
    assert not offenders, f"request bodies that accept is_admin: {offenders}"
