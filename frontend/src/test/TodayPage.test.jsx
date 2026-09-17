/**
 * The first screen.
 *
 * The old one showed four numbers and a panel of marketing copy. The bar for
 * this one is that every tile says something a person would act on, and gets
 * them to the place they would act on it — so most of what follows checks that
 * a tile is a door, and that an empty workspace still gets a sentence rather
 * than a blank.
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => vi.fn());
vi.mock("../api", () => ({ api }));

import TodayPage from "../pages/TodayPage.jsx";

function payload(overrides = {}) {
  return {
    week: { state: "none", week_start: "2026-09-14" },
    money: {
      days: 30,
      series: Array.from({ length: 30 }, (_, i) => ({
        date: `2026-08-${String(i + 1).padStart(2, "0")}`,
        in: i % 3 === 0 ? 20_000 : 0,
        out: i % 5 === 0 ? 8_000 : 0,
      })),
      in_cents: 200_000,
      out_cents: 48_000,
      net_cents: 152_000,
      receivables_cents: 100_000,
      payables_cents: 45_000,
    },
    stock: [],
    attention: [],
    attention_count: 0,
    ...overrides,
  };
}

/** A workspace past its first day — the checklist is finished and gone. */
const SETUP_DONE = { steps: [], done: 0, total: 0, next: null, complete: true };

function respond(data, setup = SETUP_DONE) {
  api.mockImplementation((path) => {
    if (path === "/platform/onboarding") return Promise.resolve(setup);
    return Promise.resolve(data ?? payload());
  });
}

beforeEach(() => {
  api.mockReset();
});

// ===========================================================================
// This week's rota — the tile no competitor can draw
// ===========================================================================

describe("this week's rota", () => {
  it("says there is no rota rather than showing an empty tile", async () => {
    respond();
    render(<TodayPage />);

    expect(await screen.findByText("No rota yet")).toBeInTheDocument();
    expect(screen.getByText(/week of 2026-09-14/)).toBeInTheDocument();
  });

  it("sends you to build one", async () => {
    const onNavigate = vi.fn();
    respond();
    render(<TodayPage onNavigate={onNavigate} />);

    await userEvent.click(await screen.findByText("No rota yet"));
    expect(onNavigate).toHaveBeenCalledWith("manager");
  });

  it("shows the verdict and what is blocking it", async () => {
    respond(payload({
      week: {
        state: "checked", schedule_id: 5, week_start: "2026-09-14", status: "draft",
        verdict: "fix", headline: "2 things to sort before this goes out",
        blocking: ["Labor is 43.2% of forecast revenue", "Gin runs out in 2 days"],
        advisories: [],
      },
    }));
    render(<TodayPage />);

    expect(await screen.findByText("Needs sorting")).toBeInTheDocument();
    expect(screen.getByText("2 things to sort before this goes out")).toBeInTheDocument();
    expect(screen.getByText(/Labor is 43.2%/)).toBeInTheDocument();
  });

  it("says a clean week is clean rather than showing nothing", async () => {
    respond(payload({
      week: {
        state: "checked", schedule_id: 5, week_start: "2026-09-14", status: "draft",
        verdict: "publish", headline: "Clear to publish", blocking: [], advisories: [],
      },
    }));
    render(<TodayPage />);

    // The verdict badge and the headline both read "Clear to publish" on a
    // clean week. Both are expected; neither should be missing.
    expect(await screen.findAllByText("Clear to publish")).toHaveLength(2);
    expect(screen.getByText(/Legal, staffed, affordable and servable/)).toBeInTheDocument();
  });

  it("an unrecognised verdict does not render a blank badge", async () => {
    respond(payload({
      week: {
        state: "checked", schedule_id: 5, week_start: "2026-09-14", status: "draft",
        verdict: "brand_new", headline: "Something new", blocking: [], advisories: [],
      },
    }));
    render(<TodayPage />);

    expect(await screen.findByText("Something new")).toBeInTheDocument();
    expect(screen.getByText("Worth a look")).toBeInTheDocument();
  });

  it("opens preflight when there is a rota to look at", async () => {
    const onNavigate = vi.fn();
    respond(payload({
      week: {
        state: "checked", schedule_id: 5, week_start: "2026-09-14", status: "draft",
        verdict: "fix", headline: "1 thing to sort", blocking: ["Gin runs out"],
        advisories: [],
      },
    }));
    render(<TodayPage onNavigate={onNavigate} />);

    await userEvent.click(await screen.findByText("1 thing to sort"));
    expect(onNavigate).toHaveBeenCalledWith("preflight");
  });
});

// ===========================================================================
// Money
// ===========================================================================

describe("the money tile", () => {
  it("leads with the net, and says which way it went", async () => {
    respond();
    render(<TodayPage />);

    await waitFor(() => expect(screen.getByText("more in than out")).toBeInTheDocument());
    expect(screen.getByText("$1,520")).toBeInTheDocument();
  });

  it("a losing month says so rather than hiding the sign", async () => {
    respond(payload({
      money: { ...payload().money, in_cents: 20_000, out_cents: 90_000, net_cents: -70_000 },
    }));
    render(<TodayPage />);

    await waitFor(() => expect(screen.getByText("more out than in")).toBeInTheDocument());
    expect(screen.getByText("−$700")).toBeInTheDocument();
  });

  it("draws the shape of the month", async () => {
    respond();
    const { container } = render(<TodayPage />);

    await screen.findByText("more in than out");
    expect(container.querySelector(".today-cash-in")).toBeInTheDocument();
    expect(container.querySelector(".today-cash-out")).toBeInTheDocument();
  });

  it("does not draw a line for a direction with no movement", async () => {
    // A series of zeros renders as a flat rule along the axis, which reads as
    // a stray line rather than as "nothing went out".
    respond(payload({
      money: {
        ...payload().money,
        series: payload().money.series.map((d) => ({ ...d, out: 0 })),
        out_cents: 0,
      },
    }));
    const { container } = render(<TodayPage />);

    await screen.findByText("more in than out");
    expect(container.querySelector(".today-cash-in")).toBeInTheDocument();
    expect(container.querySelector(".today-cash-out")).not.toBeInTheDocument();
  });

  it("shows what is owed in both directions", async () => {
    respond();
    render(<TodayPage />);

    await screen.findByText("more in than out");
    expect(screen.getByText("$1,000")).toBeInTheDocument();
    expect(screen.getByText("$450")).toBeInTheDocument();
  });
});

// ===========================================================================
// Waiting on you
// ===========================================================================

describe("waiting on you", () => {
  it("lists what needs a human, worst first", async () => {
    respond(payload({
      attention: [
        { kind: "invoices", urgency: "high", text: "2 invoices overdue",
          detail: "$1,400 outstanding", tab: "sales" },
        { kind: "tasks", urgency: "low", text: "3 open tasks",
          detail: "Count the stockroom", tab: "tasks" },
      ],
      attention_count: 1,
    }));
    render(<TodayPage />);

    const rows = await screen.findAllByRole("button", { name: /overdue|open tasks/ });
    expect(rows[0]).toHaveTextContent("2 invoices overdue");
    expect(rows[0]).toHaveTextContent("$1,400 outstanding");
  });

  it("every row goes somewhere", async () => {
    // A list of problems with no route to the fix is a list of complaints.
    const onNavigate = vi.fn();
    respond(payload({
      attention: [
        { kind: "invoices", urgency: "high", text: "2 invoices overdue",
          detail: "$1,400 outstanding", tab: "sales" },
      ],
      attention_count: 1,
    }));
    render(<TodayPage onNavigate={onNavigate} />);

    await userEvent.click(await screen.findByRole("button", { name: /2 invoices overdue/ }));
    expect(onNavigate).toHaveBeenCalledWith("sales");
  });

  it("says nothing is waiting rather than showing an empty list", async () => {
    respond();
    render(<TodayPage />);

    expect(await screen.findByText("Nothing waiting")).toBeInTheDocument();
  });

  it("marks urgency so the eye lands on the worst one", async () => {
    respond(payload({
      attention: [
        { kind: "invoices", urgency: "high", text: "overdue", detail: "", tab: "sales" },
        { kind: "tasks", urgency: "low", text: "tasks", detail: "", tab: "tasks" },
      ],
      attention_count: 1,
    }));
    const { container } = render(<TodayPage />);

    await screen.findByText("overdue");
    expect(container.querySelector(".urgency-high")).toBeInTheDocument();
    expect(container.querySelector(".urgency-low")).toBeInTheDocument();
  });
});

// ===========================================================================
// What runs out
// ===========================================================================

describe("what runs out first", () => {
  it("names it and says how long is left", async () => {
    respond(payload({
      stock: [{ item: "Gin", sku: "GIN", on_hand: 1.5, needed: 11,
                shortfall: 9.5, days_of_cover: 1.9, severity: "high" }],
    }));
    render(<TodayPage />);

    expect(await screen.findByText("Gin")).toBeInTheDocument();
    expect(screen.getByText("1.9d left")).toBeInTheDocument();
  });

  it("falls back to a reason when there is no burn rate to project", async () => {
    // A new workspace has no movement history. "0d left" would be a guess
    // dressed as an answer.
    respond(payload({
      stock: [{ item: "Gin", sku: "GIN", on_hand: 0.5, needed: 5, shortfall: 4.5,
                days_of_cover: null, severity: "medium", reason: "at reorder level" }],
    }));
    render(<TodayPage />);

    expect(await screen.findByText("at reorder level")).toBeInTheDocument();
    expect(screen.queryByText(/0d left/)).not.toBeInTheDocument();
  });

  it("says stock is fine when it is", async () => {
    respond();
    render(<TodayPage />);

    expect(await screen.findByText("Nothing running low")).toBeInTheDocument();
  });
});

// ===========================================================================
// Loading and failure
// ===========================================================================

describe("before the data arrives", () => {
  it("shows the shape of what is coming", () => {
    api.mockImplementation(() => new Promise(() => {}));
    render(<TodayPage />);

    expect(screen.getByRole("status", { name: "Reading your workspace" })).toBeInTheDocument();
  });

  it("offers a retry when it will not load", async () => {
    api.mockImplementation(() => Promise.reject(new Error("Workspace not found.")));
    render(<TodayPage />);

    expect(await screen.findByText("Workspace not found.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("reloads on demand", async () => {
    respond();
    render(<TodayPage />);

    await screen.findByText("No rota yet");
    const before = api.mock.calls.length;
    await userEvent.click(screen.getByRole("button", { name: "Refresh" }));

    await waitFor(() => expect(api.mock.calls.length).toBeGreaterThan(before));
  });
});


// ===========================================================================
// Getting set up
// ===========================================================================

describe("the setup checklist", () => {
  const halfway = {
    done: 2,
    total: 5,
    complete: false,
    next: { key: "rota", title: "Build a week", why: "Then Preflight can check it.",
            tab: "manager", action: "Build this week" },
    steps: [
      { key: "staff", title: "Add your team", done: true, tab: "manager" },
      { key: "positions", title: "Say what people do", done: true, tab: "manager" },
      { key: "rota", title: "Build a week", done: false, tab: "manager" },
      { key: "contacts", title: "Add a customer", done: false, tab: "contacts" },
      { key: "billing", title: "Start your subscription", done: false, tab: "billing" },
    ],
  };

  it("leads with the one thing to do next", async () => {
    respond(payload(), halfway);
    render(<TodayPage />);

    // "Build a week" is both the headline and a row in the list below it —
    // the next step is always also a step.
    expect(await screen.findAllByText("Build a week")).toHaveLength(2);
    expect(screen.getByText("Then Preflight can check it.")).toBeInTheDocument();
  });

  it("says how far along they are", async () => {
    respond(payload(), halfway);
    render(<TodayPage />);

    expect(await screen.findByText("2 of 5")).toBeInTheDocument();
  });

  it("the action goes where the work is", async () => {
    const onNavigate = vi.fn();
    respond(payload(), halfway);
    render(<TodayPage onNavigate={onNavigate} />);

    await userEvent.click(await screen.findByRole("button", { name: "Build this week" }));
    expect(onNavigate).toHaveBeenCalledWith("manager");
  });

  it("every remaining step is its own door", async () => {
    const onNavigate = vi.fn();
    respond(payload(), halfway);
    render(<TodayPage onNavigate={onNavigate} />);

    await userEvent.click(await screen.findByRole("button", { name: /Add a customer/ }));
    expect(onNavigate).toHaveBeenCalledWith("contacts");
  });

  it("a finished step is not a door any more", async () => {
    respond(payload(), halfway);
    render(<TodayPage />);

    expect(await screen.findByRole("button", { name: /Add your team/ })).toBeDisabled();
  });

  it("disappears for good once there is nothing left on it", async () => {
    // A finished checklist that will not leave is clutter.
    respond();
    render(<TodayPage />);

    await screen.findByText("No rota yet");
    expect(screen.queryByText("GETTING SET UP")).not.toBeInTheDocument();
  });

  it("a checklist that will not load does not take the dashboard with it", async () => {
    api.mockImplementation((path) => {
      if (path === "/platform/onboarding") return Promise.reject(new Error("nope"));
      return Promise.resolve(payload());
    });
    render(<TodayPage />);

    expect(await screen.findByText("No rota yet")).toBeInTheDocument();
  });
});
