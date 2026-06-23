# Business OS

This project combines the original deterministic scheduling application with a multi-business operations and accounting platform.

## Included

- Multiple business workspaces and locations
- Owner, admin, manager, accountant, and employee membership roles
- Server-enforced tenant isolation, including inherited scheduler records
- Customers and vendors
- Draft and posted invoices, customer payments, bills, and vendor payments
- Expense capture and a double-entry general ledger
- Chart of accounts, journal, trial balance, profit and loss, and balance sheet
- Tasks, inventory/assets, stock movements, audit history, and dashboard metrics
- Original availability, employee, labor, schedule generation, publish, and request workflows
- Claude/Anthropic provider integration with reviewable scheduler actions
- SQLite for local development; PostgreSQL and Alembic support for deployment

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`, create the first manager account, and the first business workspace will be initialized automatically.

## Verify

```powershell
.\.venv\Scripts\python.exe -m pytest -q
cd frontend
npm run build
```

## Production configuration

Copy `.env.example` to `.env` locally. In Railway, configure the values directly as service variables:

- `DATABASE_URL` — PostgreSQL connection URL
- `JWT_SECRET` — long random production secret
- `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL`
- `CORS_ORIGINS` — comma-separated frontend origins
- `VITE_API_URL` — public API URL used during the frontend build

Run `alembic upgrade head` before starting the API. Keep staging and production on separate databases.

## Accounting boundary

The ledger supports operational bookkeeping and financial reporting. Tax filing, jurisdiction-specific payroll compliance, bank-feed reconciliation, certified financial statements, and accountant sign-off require additional integrations and professional review before commercial claims are made.
