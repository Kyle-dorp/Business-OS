/**
 * The preflight screen.
 *
 * The backend half of this was just fixed: a week with no hourly rates entered
 * used to come back "Clear to publish" with labor at 0%. It now returns
 * `labor_percent: null` and a `no_wage_data` status — which only helps if the
 * screen renders that honestly rather than turning null back into a number.
 *
 * So these tests feed the page the exact shapes the API now produces and check
 * what a person actually reads.
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => vi.fn());
vi.mock("../api", () => ({ api }));

import PreflightPage from "../pages/PreflightPage.jsx";

const SCHEDULE = { id: 5, week_start: "2026-09-14", status: "draft" };

function report(overrides = {}) {
  return {
    verdict: "publish",
    headline: "Clear to publish",
    schedule_id: 5,
    week_start: "2026-09-14",
    blocking: [],
    advisories: [],
    ...overrides,
    checks: {
      compliance: { findings: [], violations: 0, warnings: 0, estimated_exposure: 0,
                    disclaimer: "Guidance, not legal advice." },
      coverage: [],
      cost: { labor_cost: 2160, forecast_revenue: 5000, labor_percent: 43.2,
              status: "over_budget", per_day: {}, shifts_without_a_wage: 0 },
      stock: [],
      ...(overrides.checks || {}),
    },
  };
}

function respondWith(preflight) {
  api.mockImplementation((path) => {
    if (path === "/schedules") return Promise.resolve([SCHEDULE]);
    if (path.startsWith("/ops/preflight/")) return Promise.resolve(preflight);
    return Promise.resolve(null);
  });
}

beforeEach(() => {
  api.mockReset();
});

// ------------------------------------------------------- the verdict banner

describe("the verdict", () => {
  it("says clear when the week is clear", async () => {
    respondWith(report({ verdict: "publish", headline: "Clear to publish" }));
    render(<PreflightPage />);

    // The banner shows the verdict label and the headline, which for a clear
    // week are the same words. Both are expected; neither should be missing.
    expect(await screen.findAllByText("Clear to publish")).toHaveLength(2);
  });

  it("does not say clear when the week needs fixing", async () => {
    respondWith(report({
      verdict: "fix",
      headline: "2 things to sort before this goes out",
      blocking: ["Labor is 43.2% of forecast revenue", "Gin runs out in 2 days"],
    }));
    render(<PreflightPage />);

    expect(await screen.findByText("Needs sorting first")).toBeInTheDocument();
    expect(screen.queryByText("Clear to publish")).not.toBeInTheDocument();
  });

  it("lists what is blocking, in full", async () => {
    respondWith(report({
      verdict: "fix",
      headline: "2 things to sort before this goes out",
      blocking: ["Labor is 43.2% of forecast revenue", "Gin runs out in 2 days"],
    }));
    render(<PreflightPage />);

    const blocking = await screen.findByRole("heading", { name: "Blocking" });
    const section = blocking.closest("section");
    expect(within(section).getAllByRole("listitem")).toHaveLength(2);
    expect(within(section).getByText(/Gin runs out/)).toBeInTheDocument();
  });

  it("keeps advisories separate from blockers", async () => {
    respondWith(report({
      verdict: "review",
      headline: "Worth a look, nothing blocking",
      advisories: ["15 shifts have no hourly rate"],
    }));
    render(<PreflightPage />);

    expect(await screen.findByRole("heading", { name: "Worth knowing" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Blocking" })).not.toBeInTheDocument();
  });

  it("an unfamiliar verdict does not render an empty banner", async () => {
    // A new verdict shipped by the backend must degrade to something, not to a
    // crash on VERDICT[undefined].label.
    respondWith(report({ verdict: "brand_new", headline: "Something new" }));
    render(<PreflightPage />);

    expect(await screen.findByText("Something new")).toBeInTheDocument();
  });
});

// -------------------------------------------------------- money and unknowns

describe("the cost panel", () => {
  it("shows the labor share when it is known", async () => {
    respondWith(report());
    render(<PreflightPage />);

    expect(await screen.findByText("43.2%")).toBeInTheDocument();
    expect(screen.getByText("$2,160")).toBeInTheDocument();
  });

  it("shows an unknown labor share as unknown, not as a percentage", async () => {
    // The frontend half of the bug fixed in the backend this session. null must
    // not render as "0%", and it must not render as "—%" either, which reads
    // like a dash of a percent.
    respondWith(report({
      verdict: "review",
      headline: "Worth a look, nothing blocking",
      advisories: ["15 shifts have no hourly rate, so labor cost is incomplete"],
      checks: {
        cost: { labor_cost: 0, forecast_revenue: 5000, labor_percent: null,
                status: "no_wage_data", per_day: {}, shifts_without_a_wage: 15 },
      },
    }));
    render(<PreflightPage />);

    await screen.findByText("Worth a look");
    expect(screen.queryByText("0%")).not.toBeInTheDocument();
    expect(screen.queryByText("—%")).not.toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("explains why the share is missing", async () => {
    respondWith(report({
      verdict: "review",
      headline: "Worth a look, nothing blocking",
      advisories: ["15 shifts have no hourly rate, so labor cost is incomplete"],
      checks: {
        cost: { labor_cost: 0, forecast_revenue: 5000, labor_percent: null,
                status: "no_wage_data", per_day: {}, shifts_without_a_wage: 15 },
      },
    }));
    render(<PreflightPage />);

    expect(await screen.findByText(/no hourly rate/)).toBeInTheDocument();
    expect(screen.getByText("no wage data")).toBeInTheDocument();
  });

  it("renders a missing figure as a dash rather than NaN", async () => {
    respondWith(report({
      checks: {
        cost: { labor_cost: null, forecast_revenue: null, labor_percent: null,
                status: "no_forecast", per_day: {}, shifts_without_a_wage: 0 },
      },
    }));
    render(<PreflightPage />);

    await screen.findByText("Cost against forecast");
    expect(screen.queryByText(/NaN/)).not.toBeInTheDocument();
    expect(screen.queryByText("$null")).not.toBeInTheDocument();
  });
});

// -------------------------------------------------------------- the panels

describe("the four checks", () => {
  it("shows all four, always", async () => {
    respondWith(report());
    render(<PreflightPage />);

    await screen.findAllByText("Clear to publish");
    for (const heading of ["Labor law", "Staffed for what's booked",
                           "Cost against forecast", "Stock for the week"]) {
      expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
    }
  });

  it("says nothing is flagged rather than showing an empty list", async () => {
    respondWith(report());
    render(<PreflightPage />);

    expect(await screen.findByText("Nothing flagged.")).toBeInTheDocument();
    expect(screen.getByText("Nothing projected to run out.")).toBeInTheDocument();
  });

  it("renders a coverage row per day", async () => {
    respondWith(report({
      checks: {
        coverage: [
          { date: "2026-09-14", bookings: 20, booked_hours: 20, staffed_hours: 8,
            status: "understaffed" },
          { date: "2026-09-15", bookings: 2, booked_hours: 2, staffed_hours: 8, status: "ok" },
        ],
      },
    }));
    render(<PreflightPage />);

    expect(await screen.findByText("understaffed")).toBeInTheDocument();
    expect(screen.getByText("2026-09-14")).toBeInTheDocument();
    expect(screen.getByText("20 · 20h")).toBeInTheDocument();
  });

  it("shows the legal disclaimer wherever findings are shown", async () => {
    respondWith(report());
    render(<PreflightPage />);

    expect(await screen.findByText("Guidance, not legal advice.")).toBeInTheDocument();
  });

  it("shows what a stock shortfall actually costs the week", async () => {
    respondWith(report({
      checks: {
        stock: [{ item: "Gin", sku: "GIN1", on_hand: 1.5, needed: 11,
                  shortfall: 9.5, days_of_cover: 1.9, severity: "high" }],
      },
    }));
    render(<PreflightPage />);

    expect(await screen.findByText("Gin")).toBeInTheDocument();
    expect(screen.getByText("1.9d cover")).toBeInTheDocument();
    expect(screen.getByText(/short by 9.5/)).toBeInTheDocument();
  });
});

// ------------------------------------------------------------ before data

describe("before there is anything to check", () => {
  it("explains how to get a schedule rather than showing a blank page", async () => {
    api.mockImplementation((path) =>
      path === "/schedules" ? Promise.resolve([]) : Promise.resolve(null));
    render(<PreflightPage />);

    expect(await screen.findByText("No schedules to check yet")).toBeInTheDocument();
    expect(screen.getByText(/Build one under Scheduling/)).toBeInTheDocument();
  });

  it("surfaces a failure instead of an empty screen", async () => {
    api.mockImplementation((path) =>
      path === "/schedules"
        ? Promise.reject(new Error("Couldn't reach the server"))
        : Promise.resolve(null));
    render(<PreflightPage />);

    expect(await screen.findByText("Couldn't reach the server")).toBeInTheDocument();
  });

  it("says so when preflight itself fails on a schedule", async () => {
    api.mockImplementation((path) => {
      if (path === "/schedules") return Promise.resolve([SCHEDULE]);
      return Promise.reject(new Error("No such schedule."));
    });
    render(<PreflightPage />);

    expect(await screen.findByText("No such schedule.")).toBeInTheDocument();
  });

  it("picks the first schedule so the page is useful on arrival", async () => {
    respondWith(report());
    render(<PreflightPage />);

    await waitFor(() => expect(api).toHaveBeenCalledWith("/ops/preflight/5"));
  });

  it("re-runs when another week is chosen", async () => {
    api.mockImplementation((path) => {
      if (path === "/schedules") {
        return Promise.resolve([SCHEDULE, { id: 9, week_start: "2026-09-21", status: "draft" }]);
      }
      return Promise.resolve(report());
    });
    render(<PreflightPage />);

    await screen.findAllByText("Clear to publish");
    await userEvent.selectOptions(screen.getByLabelText("Schedule"), "9");

    await waitFor(() => expect(api).toHaveBeenCalledWith("/ops/preflight/9"));
  });
});
