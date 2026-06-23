import os
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./test_business_os.db"
Path("test_business_os.db").unlink(missing_ok=True)

from fastapi.testclient import TestClient  # noqa: E402
from backend.app.main import app  # noqa: E402


def test_complete_multi_business_accounting_flow():
    with TestClient(app) as client:
        assert client.post("/auth/setup", json={"username": "owner", "password": "correct-horse"}).status_code == 200
        login = client.post("/auth/login", json={"username": "owner", "password": "correct-horse"})
        assert login.status_code == 200
        token = login.json()["token"]
        auth = {"Authorization": f"Bearer {token}"}

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

        templates = client.get("/platform/checklists/templates", headers=headers).json()
        assert any(row["category"] == "closing" for row in templates)
        run = client.post("/platform/checklists/runs", headers=headers, json={
            "template_id": templates[0]["id"], "run_date": "2026-06-18",
        }).json()
        completed_items = [{**item, "done": True} for item in run["items"]]
        completed = client.patch(f"/platform/checklists/runs/{run['id']}", headers=headers, json={
            "items": completed_items, "notes": "All done", "complete": True,
        })
        assert completed.status_code == 200
        assert completed.json()["status"] == "complete"

        closing = client.post("/platform/closing-reports", headers=headers, json={
            "report_date": "2026-06-18", "sales": 325.50, "cash_expected": 120,
            "cash_actual": 118.50, "labor_cost": 90, "waste": 4.25,
            "issues": "Register was short", "notes": "Reviewed by owner",
        })
        assert closing.status_code == 200
        assert closing.json()["sales_cents"] == 32550
        assert len(client.get("/platform/closing-reports", headers=headers).json()) == 1

        assert client.post("/platform/presets/warehouse/apply", headers=headers).status_code == 200
        preset_workspace = client.get("/platform/workspace", headers=headers).json()
        assert preset_workspace["business"]["industry"] == "warehouse"
        assert any(row["name"] == "Receiving" for row in client.get("/departments", headers=headers).json())
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
        login = client.post("/auth/login", json={"username": "owner", "password": "correct-horse"}).json()
        auth = {"Authorization": f"Bearer {login['token']}"}
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
