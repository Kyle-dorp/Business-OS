/**
 * The billing screen.
 *
 * This is the page where a person decides what to pay, so the number on it is
 * a promise. Two ways that promise can break without anything looking wrong:
 *
 *   The price and the toggles can drift apart. The price comes from the server
 *   on a debounce; if that request fails, the last good price stays on screen
 *   next to toggles that have moved on.
 *
 *   A save can half-succeed. Modules are saved one request at a time, so a
 *   failure halfway leaves the server holding a different set from the one the
 *   screen is showing — and the screen keeps showing the operator's version.
 *
 * Most of what follows is about those two.
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => vi.fn());
vi.mock("../api", () => ({ api }));

import BillingPage from "../pages/BillingPage.jsx";

const MODULES = [
  { key: "home", name: "Home", billable: false, enabled: true, tagline: "Your day", description: "", market_price: 0 },
  { key: "scheduling", name: "Scheduling", billable: true, enabled: true, tagline: "Rotas", description: "", market_price: 45, replaces: "Deputy" },
  { key: "accounting", name: "Books", billable: true, enabled: true, tagline: "Ledger", description: "", market_price: 60 },
  { key: "booking", name: "Bookings", billable: true, enabled: false, tagline: "Diary", description: "", market_price: 30 },
];

const CATALOGUE = {
  modules: MODULES,
  first_module_cents: 2900,
  each_additional_cents: 1000,
};

function quote(overrides = {}) {
  return {
    status: "active",
    monthly_cents: 3900,
    module_count: 2,
    stitched_cents: 10500,
    saving_cents: 6600,
    needs_subscription: false,
    in_grace: false,
    current_period_end: "2026-10-14T00:00:00+00:00",
    ...overrides,
  };
}

function respond({ q = quote(), preview, previewFails = false, onCall } = {}) {
  api.mockImplementation((path, options) => {
    onCall?.(path, options);
    if (path === "/billing/catalogue") return Promise.resolve(CATALOGUE);
    if (path === "/billing/quote") return Promise.resolve(q);
    if (path === "/billing/preview") {
      if (previewFails) return Promise.reject(new Error("preview unavailable"));
      return Promise.resolve(preview || q);
    }
    if (path === "/billing/sync") return Promise.resolve({ synced: true });
    return Promise.resolve({});
  });
}

beforeEach(() => {
  api.mockReset();
});

// ------------------------------------------------------------- the price

describe("the price on the page", () => {
  it("shows what the workspace pays today", async () => {
    respond();
    render(<BillingPage />);

    expect(await screen.findByText("$39")).toBeInTheDocument();
    expect(screen.getByText("/month")).toBeInTheDocument();
  });

  it("explains the ladder rather than only the total", async () => {
    respond();
    render(<BillingPage />);

    expect(await screen.findByText(/2 modules/)).toBeInTheDocument();
    expect(screen.getByText(/\$29 for the first/)).toBeInTheDocument();
    expect(screen.getByText(/\$10 each after/)).toBeInTheDocument();
  });

  it("says module, singular, when there is one", async () => {
    respond({ q: quote({ module_count: 1, monthly_cents: 2900 }) });
    render(<BillingPage />);

    expect(await screen.findByText(/^1 module —/)).toBeInTheDocument();
  });

  it("says so plainly when nothing billable is selected", async () => {
    respond({ q: quote({ module_count: 0, monthly_cents: 0, stitched_cents: 0 }) });
    render(<BillingPage />);

    expect(await screen.findByText("No billable modules selected.")).toBeInTheDocument();
  });

  it("shows what the same stack costs bought separately", async () => {
    respond();
    render(<BillingPage />);

    expect(await screen.findByText("$105")).toBeInTheDocument();
    expect(screen.getByText("$66/mo")).toBeInTheDocument();
  });

  it("hides the comparison when there is nothing to compare", async () => {
    respond({ q: quote({ stitched_cents: 0, saving_cents: 0 }) });
    render(<BillingPage />);

    await screen.findByText("$39");
    expect(screen.queryByText("Bought separately")).not.toBeInTheDocument();
  });

  it("re-prices from the server as modules are toggled", async () => {
    // The page never does the arithmetic itself, so it cannot disagree with
    // the invoice. This is what proves it asks.
    respond({ preview: quote({ monthly_cents: 4900, module_count: 3 }) });
    render(<BillingPage />);

    await screen.findByText("$39");
    await userEvent.click(screen.getByRole("button", { name: /Bookings/ }));

    expect(await screen.findByText("$49")).toBeInTheDocument();
  });
});

// ------------------------------------------------------------- the toggles

describe("choosing modules", () => {
  it("marks what is on", async () => {
    respond();
    render(<BillingPage />);

    const scheduling = await screen.findByRole("button", { name: /Scheduling/ });
    expect(scheduling).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /Bookings/ })).toHaveAttribute(
      "aria-pressed", "false",
    );
  });

  it("an always-on module cannot be switched off", async () => {
    // Losing the home screen is not a saving.
    respond();
    render(<BillingPage />);

    const home = await screen.findByRole("button", { name: /Home/ });
    expect(home).toBeDisabled();
    expect(screen.getByText("always on")).toBeInTheDocument();
  });

  it("shows what a module replaces, since that is the argument", async () => {
    respond();
    render(<BillingPage />);

    expect(await screen.findByText("Replaces Deputy")).toBeInTheDocument();
  });

  it("offers save and reset only once something has changed", async () => {
    respond();
    render(<BillingPage />);

    await screen.findByText("$39");
    expect(screen.queryByRole("button", { name: "Save changes" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Bookings/ }));
    expect(await screen.findByRole("button", { name: "Save changes" })).toBeInTheDocument();
  });

  it("reset puts the toggles back to what is saved", async () => {
    respond();
    render(<BillingPage />);

    await screen.findByText("$39");
    await userEvent.click(screen.getByRole("button", { name: /Bookings/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Reset" }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Bookings/ })).toHaveAttribute(
        "aria-pressed", "false",
      ));
    expect(screen.queryByRole("button", { name: "Save changes" })).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------- saving

describe("saving", () => {
  it("saves only what changed", async () => {
    const calls = [];
    respond({ onCall: (path, options) => calls.push([path, options?.method]) });
    render(<BillingPage />);

    await screen.findByText("$39");
    await userEvent.click(screen.getByRole("button", { name: /Bookings/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Save changes" }));

    await waitFor(() => {
      const puts = calls.filter(([, method]) => method === "PUT");
      expect(puts).toHaveLength(1);
      expect(puts[0][0]).toBe("/platform/modules/booking");
    });
  });

  it("says the subscription was updated when it was", async () => {
    respond();
    render(<BillingPage />);

    await screen.findByText("$39");
    await userEvent.click(screen.getByRole("button", { name: /Bookings/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Save changes" }));

    expect(await screen.findByText(/Stripe will prorate/)).toBeInTheDocument();
  });

  it("a failed Stripe sync does not undo saved module changes", async () => {
    // The modules are already saved by then. Reporting a failure that makes
    // somebody re-toggle everything is worse than the sync being late.
    api.mockImplementation((path) => {
      if (path === "/billing/catalogue") return Promise.resolve(CATALOGUE);
      if (path === "/billing/quote") return Promise.resolve(quote());
      if (path === "/billing/preview") return Promise.resolve(quote());
      if (path === "/billing/sync") return Promise.reject(new Error("Stripe unreachable"));
      return Promise.resolve({});
    });
    render(<BillingPage />);

    await screen.findByText("$39");
    await userEvent.click(screen.getByRole("button", { name: /Bookings/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Save changes" }));

    expect(await screen.findByText("Saved.")).toBeInTheDocument();
    expect(screen.queryByText(/Stripe unreachable/)).not.toBeInTheDocument();
  });

  it("a failed save does not leave the screen claiming a state the server does not have", async () => {
    // Modules are saved one request at a time. If one fails, the screen must
    // not keep showing the operator's toggles as though they were saved —
    // that is how somebody ends up believing they pay for four modules and
    // being billed for three.
    api.mockImplementation((path, options) => {
      if (path === "/billing/catalogue") return Promise.resolve(CATALOGUE);
      if (path === "/billing/quote") return Promise.resolve(quote());
      if (path === "/billing/preview") return Promise.resolve(quote());
      if (options?.method === "PUT") return Promise.reject(new Error("Workspace not found."));
      return Promise.resolve({});
    });
    render(<BillingPage />);

    await screen.findByText("$39");
    await userEvent.click(screen.getByRole("button", { name: /Bookings/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Save changes" }));

    expect(await screen.findByText("Workspace not found.")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Bookings/ })).toHaveAttribute(
        "aria-pressed", "false",
      ));
  });

  it("tells the rest of the app that modules moved", async () => {
    const onModulesChanged = vi.fn();
    respond();
    render(<BillingPage onModulesChanged={onModulesChanged} />);

    await screen.findByText("$39");
    await userEvent.click(screen.getByRole("button", { name: /Bookings/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(onModulesChanged).toHaveBeenCalled());
  });
});

// -------------------------------------------------------- subscription state

describe("where the subscription stands", () => {
  it.each([
    ["active", "Active"],
    ["trialing", "Trial"],
    ["past_due", "Payment failed"],
    ["canceled", "Cancelled"],
    ["incomplete_expired", "Expired"],
  ])("renders %s as %s", async (status, label) => {
    respond({ q: quote({ status }) });
    render(<BillingPage />);

    expect(await screen.findByText(label)).toBeInTheDocument();
  });

  it("an unrecognised status does not render a blank badge", async () => {
    respond({ q: quote({ status: "something_new" }) });
    render(<BillingPage />);

    expect(await screen.findByText("No subscription")).toBeInTheDocument();
  });

  it("a failed payment is explained, not just flagged", async () => {
    respond({ q: quote({ status: "past_due", in_grace: true }) });
    render(<BillingPage />);

    expect(await screen.findByText(/payment did not go through/i)).toBeInTheDocument();
    expect(screen.getByText(/Everything still works/)).toBeInTheDocument();
  });

  it("offers checkout to somebody with no subscription", async () => {
    respond({ q: quote({ needs_subscription: true, status: "none" }) });
    render(<BillingPage />);

    expect(await screen.findByRole("button", { name: "Start subscription" })).toBeEnabled();
  });

  it("will not start a subscription for nothing", async () => {
    // The backend refuses this with a 400. Letting somebody click through to
    // Stripe and be told there is nothing to buy is a worse way to learn it.
    respond({ q: quote({ needs_subscription: true, module_count: 0, monthly_cents: 0 }) });
    render(<BillingPage />);

    expect(await screen.findByRole("button", { name: "Start subscription" })).toBeDisabled();
  });

  it("offers the portal to somebody already subscribed", async () => {
    respond();
    render(<BillingPage />);

    expect(await screen.findByRole("button", { name: "Manage billing" })).toBeInTheDocument();
  });

  it("shows the renewal date as a date, not a timestamp", async () => {
    respond();
    render(<BillingPage />);

    expect(await screen.findByText("Renews 2026-10-14")).toBeInTheDocument();
  });
});

// ------------------------------------------------------------ before data

describe("loading and failure", () => {
  it("shows the shape of the page while it loads", async () => {
    api.mockImplementation(() => new Promise(() => {}));
    render(<BillingPage />);

    expect(screen.getByRole("status", { name: "Loading your plan" })).toBeInTheDocument();
  });

  it("offers a retry when the plan will not load", async () => {
    api.mockImplementation(() => Promise.reject(new Error("Workspace not found.")));
    render(<BillingPage />);

    expect(await screen.findByText("Workspace not found.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("translates a bare network failure into something actionable", async () => {
    api.mockImplementation(() => Promise.reject(new Error("Failed to fetch")));
    render(<BillingPage />);

    expect(await screen.findByText(/check your connection/i)).toBeInTheDocument();
    expect(screen.queryByText(/Failed to fetch/)).not.toBeInTheDocument();
  });
});
