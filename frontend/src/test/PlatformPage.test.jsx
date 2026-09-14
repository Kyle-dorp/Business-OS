/**
 * The accounting screens.
 *
 * One component renders eight sections against the double-entry core, so the
 * money on it comes straight out of the ledger. Two things are worth pinning.
 *
 * Dates. Every form here defaults to "today", and today used to be computed
 * with toISOString(), which is UTC — so for anybody west of Greenwich in the
 * evening the default date on an invoice, a bill or an expense was tomorrow.
 * An expense dated tomorrow can land in the wrong accounting period, which is
 * the sort of error that surfaces at a reconciliation months later.
 *
 * Money. Every figure arrives in cents and must be rendered as currency, never
 * as a raw integer and never as NaN. $NaN on a balance sheet is not a display
 * glitch; it is somebody's books.
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => vi.fn());
vi.mock("../api", () => ({ api }));

import PlatformPage from "../pages/PlatformPage.jsx";

const ACCOUNTS = [
  { id: 1, code: "1000", name: "Operating Bank", account_type: "asset", subtype: "cash" },
  { id: 2, code: "2100", name: "Credit Card", account_type: "liability", subtype: "credit_card" },
  { id: 3, code: "6100", name: "Rent Expense", account_type: "expense", subtype: "rent" },
  { id: 4, code: "6300", name: "Supplies Expense", account_type: "expense", subtype: "supplies" },
  { id: 5, code: "4000", name: "Sales Revenue", account_type: "income", subtype: "sales" },
];

const CONTACTS = [
  { id: 1, name: "Acme", contact_type: "customer", email: "a@example.com", phone: "" },
  { id: 2, name: "Supply Co", contact_type: "vendor", email: "", phone: "555" },
  { id: 3, name: "Both Ltd", contact_type: "both", email: "", phone: "" },
];

function routes(overrides = {}) {
  const table = {
    "/platform/dashboard": {
      receivables_cents: 124_000, payables_cents: 80_000,
      open_invoices: 3, open_bills: 1, open_tasks: 5, low_stock_items: 2,
    },
    "/platform/contacts": CONTACTS,
    "/platform/accounts": ACCOUNTS,
    "/platform/invoices": [
      { id: 1, number: "INV-00001", issue_date: "2026-09-01", due_date: "2026-09-30",
        status: "sent", total_cents: 124_000, paid_cents: 40_000 },
    ],
    "/platform/bills": [
      { id: 1, number: "", bill_date: "2026-09-02", due_date: "2026-09-20",
        status: "open", total_cents: 80_000, paid_cents: 0 },
    ],
    "/platform/expenses": [
      { id: 1, expense_date: "2026-09-03", description: "", amount_cents: 12_500 },
    ],
    "/platform/reports/profit-loss": {
      total_income_cents: 500_000, total_expenses_cents: 320_000, net_income_cents: 180_000,
    },
    "/platform/reports/balance-sheet": { totals: { asset: 900_000, liability: 200_000 } },
    "/platform/reports/trial-balance": {
      rows: [{ account: { code: "1000", name: "Operating Bank" },
               debit_cents: 500_000, credit_cents: 0 }],
    },
    "/platform/tasks": [
      { id: 1, title: "Count stock", due_date: "", priority: "high", status: "open" },
    ],
    "/platform/inventory": [
      { id: 1, sku: "GIN1", name: "Gin", item_type: "inventory",
        quantity_milli: 20_000, reorder_level_milli: 5_000 },
    ],
    ...overrides,
  };
  api.mockImplementation((path, options) => {
    if (options?.method === "POST") return Promise.resolve({ id: 99 });
    if (path in table) {
      const value = table[path];
      return value instanceof Error ? Promise.reject(value) : Promise.resolve(value);
    }
    return Promise.resolve([]);
  });
  return table;
}

beforeEach(() => {
  api.mockReset();
  vi.useRealTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

// ============================================================ dates

describe("what date a form defaults to", () => {
  it("uses the local date, not the UTC one", async () => {
    // 7:30pm on the 14th. In any negative offset toISOString() gives the 15th,
    // so an invoice raised this evening was dated tomorrow.
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 8, 14, 19, 30));
    routes();

    render(<PlatformPage section="sales" />);
    const due = await screen.findByLabelText("Due date");

    expect(due).toHaveValue("2026-09-14");
  });

  it("is the same local date just before midnight", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 8, 14, 23, 59));
    routes();

    render(<PlatformPage section="purchasing" />);
    expect(await screen.findByLabelText("Due date")).toHaveValue("2026-09-14");
  });

  it("defaults the expense date the same way", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 8, 14, 21, 0));
    routes();

    render(<PlatformPage section="accounting" />);
    expect(await screen.findByLabelText("Date")).toHaveValue("2026-09-14");
  });
});

// ============================================================ money

describe("rendering money", () => {
  it("shows cents as currency on the dashboard", async () => {
    routes();
    render(<PlatformPage section="overview" />);

    expect(await screen.findByText("$1,240.00")).toBeInTheDocument();
    expect(screen.getByText("$800.00")).toBeInTheDocument();
  });

  it("shows the outstanding balance, not just the total", async () => {
    routes();
    render(<PlatformPage section="sales" />);

    const row = (await screen.findByText("INV-00001")).closest("tr");
    expect(within(row).getByText("$1,240.00")).toBeInTheDocument();
    expect(within(row).getByText("$840.00")).toBeInTheDocument();
  });

  it("never prints a raw cent figure", async () => {
    routes();
    render(<PlatformPage section="overview" />);

    await screen.findByText("$1,240.00");
    expect(screen.queryByText("124000")).not.toBeInTheDocument();
  });

  it("renders a missing figure as zero rather than NaN", async () => {
    // $NaN on a report is not a display glitch, it is somebody's books.
    routes({
      "/platform/reports/profit-loss": {},
      "/platform/reports/balance-sheet": { totals: {} },
      "/platform/reports/trial-balance": { rows: [] },
    });
    render(<PlatformPage section="reports" />);

    await screen.findByText("Financial reports");
    expect(screen.queryByText(/NaN/)).not.toBeInTheDocument();
  });

  it("shows a net loss as a negative, not as an absolute", async () => {
    routes({
      "/platform/reports/profit-loss": {
        total_income_cents: 100_000, total_expenses_cents: 250_000,
        net_income_cents: -150_000,
      },
    });
    render(<PlatformPage section="reports" />);

    expect(await screen.findByText("-$1,500.00")).toBeInTheDocument();
  });
});

// ============================================================ sections

describe("the overview", () => {
  it("leads with what is owed and what is owing", async () => {
    routes();
    render(<PlatformPage section="overview" />);

    expect(await screen.findByText("Money coming in")).toBeInTheDocument();
    expect(screen.getByText("3 open invoices")).toBeInTheDocument();
    expect(screen.getByText("Bills to pay")).toBeInTheDocument();
    expect(screen.getByText("1 open bills")).toBeInTheDocument();
  });

  it("reloads on demand", async () => {
    routes();
    render(<PlatformPage section="overview" />);

    await screen.findByText("Money coming in");
    const before = api.mock.calls.length;
    await userEvent.click(screen.getByRole("button", { name: "Refresh" }));

    await waitFor(() => expect(api.mock.calls.length).toBeGreaterThan(before));
  });
});

describe("customers and vendors", () => {
  it("lists them", async () => {
    routes();
    render(<PlatformPage section="contacts" />);

    expect(await screen.findByText("Acme")).toBeInTheDocument();
    expect(screen.getByText("Supply Co")).toBeInTheDocument();
  });

  it("shows a dash for a missing detail rather than an empty cell", async () => {
    routes();
    render(<PlatformPage section="contacts" />);

    const row = (await screen.findByText("Acme")).closest("tr");
    expect(within(row).getByText("—")).toBeInTheDocument();
  });

  it("saves a new contact and says so", async () => {
    routes();
    render(<PlatformPage section="contacts" />);

    await screen.findByText("Acme");
    await userEvent.type(screen.getByLabelText("Name"), "New Co");
    await userEvent.click(screen.getByRole("button", { name: "Save contact" }));

    expect(await screen.findByText("Saved successfully.")).toBeInTheDocument();
  });

  it("surfaces the reason a save was refused", async () => {
    routes();
    api.mockImplementation((path, options) => {
      if (options?.method === "POST") return Promise.reject(new Error("Name is required"));
      if (path === "/platform/contacts") return Promise.resolve(CONTACTS);
      return Promise.resolve([]);
    });
    render(<PlatformPage section="contacts" />);

    await screen.findByText("Acme");
    await userEvent.click(screen.getByRole("button", { name: "Save contact" }));

    expect(await screen.findByText("Name is required")).toBeInTheDocument();
  });
});

describe("invoicing", () => {
  it("only offers customers, not vendors", async () => {
    // Invoicing a supplier is a different document. The list is the guard.
    routes();
    render(<PlatformPage section="sales" />);

    const select = await screen.findByLabelText("Customer");
    const names = within(select).getAllByRole("option").map((o) => o.textContent);
    expect(names).toContain("Acme");
    expect(names).toContain("Both Ltd");
    expect(names).not.toContain("Supply Co");
  });

  it("sends the amount as an invoice line", async () => {
    const sent = [];
    routes();
    api.mockImplementation((path, options) => {
      if (options?.method === "POST") {
        sent.push([path, JSON.parse(options.body)]);
        return Promise.resolve({ id: 9 });
      }
      if (path === "/platform/contacts") return Promise.resolve(CONTACTS);
      if (path === "/platform/accounts") return Promise.resolve(ACCOUNTS);
      return Promise.resolve([]);
    });
    render(<PlatformPage section="sales" />);

    await screen.findByLabelText("Customer");
    await userEvent.selectOptions(screen.getByLabelText("Customer"), "1");
    await userEvent.type(screen.getByLabelText("Amount"), "250");
    await userEvent.click(screen.getByRole("button", { name: "Create draft" }));

    await waitFor(() => expect(sent).toHaveLength(1));
    const [path, body] = sent[0];
    expect(path).toBe("/platform/invoices");
    expect(body.customer_id).toBe(1);
    expect(body.lines[0].unit_price).toBe(250);
    expect(body.lines[0].quantity).toBe(1);
  });

  it("describes an unlabelled line rather than sending an empty one", async () => {
    const sent = [];
    api.mockImplementation((path, options) => {
      if (options?.method === "POST") {
        sent.push(JSON.parse(options.body));
        return Promise.resolve({ id: 9 });
      }
      if (path === "/platform/contacts") return Promise.resolve(CONTACTS);
      if (path === "/platform/accounts") return Promise.resolve(ACCOUNTS);
      return Promise.resolve([]);
    });
    render(<PlatformPage section="sales" />);

    await screen.findByLabelText("Customer");
    await userEvent.click(screen.getByRole("button", { name: "Create draft" }));

    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0].lines[0].description).toBe("Services");
  });
});

describe("purchasing", () => {
  it("only offers vendors", async () => {
    routes();
    render(<PlatformPage section="purchasing" />);

    const select = await screen.findByLabelText("Vendor");
    const names = within(select).getAllByRole("option").map((o) => o.textContent);
    expect(names).toContain("Supply Co");
    expect(names).toContain("Both Ltd");
    expect(names).not.toContain("Acme");
  });

  it("only offers expense accounts as a category", async () => {
    // Posting a bill against a bank account is how a ledger stops balancing.
    routes();
    render(<PlatformPage section="purchasing" />);

    const select = await screen.findByLabelText("Expense category");
    const names = within(select).getAllByRole("option").map((o) => o.textContent);
    expect(names).toContain("Rent Expense");
    expect(names).not.toContain("Operating Bank");
    expect(names).not.toContain("Sales Revenue");
  });

  it("names a bill that has no number of its own", async () => {
    routes();
    render(<PlatformPage section="purchasing" />);

    expect(await screen.findByText("Bill 1")).toBeInTheDocument();
  });
});

describe("bookkeeping", () => {
  it("shows income, expenses and the net between them", async () => {
    routes();
    render(<PlatformPage section="accounting" />);

    expect(await screen.findByText("$5,000.00")).toBeInTheDocument();
    expect(screen.getByText("$3,200.00")).toBeInTheDocument();
    expect(screen.getByText("$1,800.00")).toBeInTheDocument();
  });

  it("offers only real payment accounts to pay from", async () => {
    routes();
    render(<PlatformPage section="accounting" />);

    const select = await screen.findByLabelText("Paid from");
    const names = within(select).getAllByRole("option").map((o) => o.textContent);
    expect(names).toContain("Operating Bank");
    expect(names).toContain("Credit Card");
    expect(names).not.toContain("Rent Expense");
  });

  it("labels an unlabelled expense rather than leaving the cell blank", async () => {
    routes();
    render(<PlatformPage section="accounting" />);

    expect(await screen.findByText("Expense")).toBeInTheDocument();
  });
});

describe("inventory", () => {
  it("shows stock in units, not thousandths", async () => {
    routes();
    render(<PlatformPage section="inventory" />);

    const row = (await screen.findByText("Gin")).closest("tr");
    expect(within(row).getByText("20")).toBeInTheDocument();
    expect(within(row).getByText("5")).toBeInTheDocument();
  });
});

describe("reports", () => {
  it("shows the trial balance out of the ledger", async () => {
    routes();
    render(<PlatformPage section="reports" />);

    expect(await screen.findByText("Trial balance")).toBeInTheDocument();
    const row = screen.getByText("Operating Bank").closest("tr");
    expect(within(row).getByText("$5,000.00")).toBeInTheDocument();
  });
});

// ============================================================ empty and broken

describe("when there is nothing, or something went wrong", () => {
  it("says a table is empty rather than showing a bare header", async () => {
    routes({ "/platform/tasks": [] });
    render(<PlatformPage section="tasks" />);

    expect(await screen.findByText("Nothing here yet.")).toBeInTheDocument();
  });

  it("surfaces a load failure", async () => {
    api.mockImplementation(() => Promise.reject(new Error("Workspace not found.")));
    render(<PlatformPage section="overview" />);

    expect(await screen.findByText("Workspace not found.")).toBeInTheDocument();
  });
});
