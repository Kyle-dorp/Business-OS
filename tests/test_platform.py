"""
End-to-end accounting across two businesses.

Database isolation is handled by conftest.py. This file used to set
DATABASE_URL itself, which only worked when it ran alone: database.py binds its
engine the first time it is imported, so by the time this module is collected
in a full suite the setting has no effect. It looked like isolation and was
not, which is why these tests passed individually and failed together.

It also assumed it owned the first user. Another module creating an account
first turned that into a 409 and the whole file went red for a reason that had
nothing to do with accounting.
"""

from fastapi.testclient import TestClient
from backend.app.main import app

OWNER = {"username": "owner", "password": "correct-horse"}


def _sign_in(client):
    """
    Sign in as the owner, creating the account whichever way is available.

    /auth/setup only works once per database. When another module has already
    used it, the account is created directly — the point of this file is the
    accounting flow, not the registration path, and racing for first-run makes
    the result depend on collection order.
    """
    setup = client.post("/auth/setup", json=OWNER)
    assert setup.status_code in (200, 409), setup.text

    if setup.status_code == 409:
        from sqlmodel import Session, select

        from backend.app.auth import hash_password
        from backend.app.database import engine
        from backend.app.models import UserAccount

        from backend.app.models import Business
        from backend.app.platform import seed_business
        from backend.app.tenancy import set_current_business_id

        with Session(engine) as session:
            existing = session.exec(
                select(UserAccount).where(UserAccount.username == OWNER["username"])
            ).first()
            if not existing:
                user = UserAccount(
                    username=OWNER["username"],
                    password_hash=hash_password(OWNER["password"]),
                    role="manager",
                    active=True,
                )
                session.add(user)
                session.flush()

                # A user with no membership is rejected by the auth middleware
                # before any route runs, so the workspace has to exist too —
                # the same thing /auth/setup does.
                business = Business(name="My Business", industry="general", active=True)
                session.add(business)
                session.flush()

                set_current_business_id(business.id)
                try:
                    seed_business(session, business, user, role="owner")
                    session.commit()
                finally:
                    set_current_business_id(1)

    login = client.post("/auth/login", json=OWNER)
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['token']}"}


def test_complete_multi_business_accounting_flow():
    with TestClient(app) as client:
        auth = _sign_in(client)

        bootstrap = client.post("/platform/bootstrap", headers=auth)
        assert bootstrap.status_code == 200
        business_id = bootstrap.json()[0]["business"]["id"]
        headers = {**auth, "X-Business-Id": str(business_id)}

        customer = client.post("/platform/contacts", headers=headers, json={"name": "Acme", "contact_type": "customer"}).json()
        vendor = client.post("/platform/contacts", headers=headers, json={"name": "Supply Co", "contact_type": "vendor"}).json()
        accounts = client.get("/platform/accounts", headers=headers).json()
        bank = next(x for x in accounts if x["subtype"] == "cash")
        supplies = next(x for x in accounts if x["subtype"] == "supplies")

        invoice = client.post("/platform/invoices", headers=headers, json={
            "customer_id": customer["id"], "due_date": "2026-07-01",
            "lines": [{"description": "Monthly service", "quantity": 2, "unit_price": 125}],
        }).json()
        assert invoice["total_cents"] == 25000
        assert client.post(f"/platform/invoices/{invoice['id']}/post", headers=headers).json()["status"] == "sent"
        assert client.post(f"/platform/invoices/{invoice['id']}/payments", headers=headers, json={
            "amount": 250, "account_id": bank["id"], "payment_date": "2026-06-18"
        }).status_code == 200

        assert client.post("/platform/expenses", headers=headers, json={
            "expense_date": "2026-06-18", "vendor_id": vendor["id"], "account_id": supplies["id"],
            "payment_account_id": bank["id"], "amount": 40, "description": "Shop supplies",
        }).status_code == 200
        profit = client.get("/platform/reports/profit-loss", headers=headers).json()
        assert profit["total_income_cents"] == 25000
        assert profit["total_expenses_cents"] == 4000
        assert profit["net_income_cents"] == 21000
        assistant = client.post("/assistant/chat", headers=headers, json={"message": "Are we profitable?"})
        assert assistant.status_code == 200
        assert "$210.00" in assistant.text
        trial = client.get("/platform/reports/trial-balance", headers=headers).json()
        assert trial["total_debits_cents"] == trial["total_credits_cents"]
        assert client.put("/platform/modules/inventory", headers=headers, json={"enabled": False}).status_code == 200
        workspace = client.get("/platform/workspace", headers=headers).json()
        assert next(x for x in workspace["modules"] if x["module_key"] == "inventory")["enabled"] is False
        employee = client.post("/employees", headers=headers, json={
            "name": "Tenant One Employee", "department": "General", "role": "employee",
            "min_hours_per_week": 0, "max_hours_per_week": 30,
        })
        assert employee.status_code == 200

        second = client.post("/platform/businesses", headers=auth, json={"name": "Second Business"}).json()
        second_headers = {**auth, "X-Business-Id": str(second["id"])}
        assert client.get("/platform/contacts", headers=second_headers).json() == []
        assert client.get("/platform/invoices", headers=second_headers).json() == []
        assert client.get("/employees", headers=second_headers).json() == []
        assert len(client.get("/employees", headers=headers).json()) == 1


def test_rejects_cross_tenant_contact_reference():
    with TestClient(app) as client:
        auth = _sign_in(client)
        businesses = client.get("/platform/businesses", headers=auth).json()
        first, second = businesses[0]["business"]["id"], businesses[1]["business"]["id"]
        first_headers = {**auth, "X-Business-Id": str(first)}
        second_headers = {**auth, "X-Business-Id": str(second)}
        foreign_customer = client.get("/platform/contacts", headers=first_headers).json()[0]
        response = client.post("/platform/invoices", headers=second_headers, json={
            "customer_id": foreign_customer["id"], "due_date": "2026-07-01",
            "lines": [{"description": "Should fail", "quantity": 1, "unit_price": 1}],
        })
        assert response.status_code == 400
