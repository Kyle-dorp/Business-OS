/**
 * Empty, loading and error states.
 *
 * These three are what a person sees on their first day, on a slow connection,
 * and when something breaks — the three moments where an app either feels
 * finished or doesn't. They are also the screens nobody looks at twice, which
 * is why they get tested here rather than noticed in production.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AsyncBoundary, Empty, ErrorState, Loading } from "../components/States.jsx";

describe("empty", () => {
  it("says what is missing rather than 'no data'", () => {
    render(<Empty title="No schedules to check yet">Build one under Scheduling.</Empty>);

    expect(screen.getByText("No schedules to check yet")).toBeInTheDocument();
    expect(screen.getByText(/Build one under Scheduling/)).toBeInTheDocument();
  });

  it("offers the action that fixes it", async () => {
    const onAction = vi.fn();
    render(<Empty title="Nothing yet" action={onAction} actionLabel="Add a service" />);

    await userEvent.click(screen.getByRole("button", { name: "Add a service" }));
    expect(onAction).toHaveBeenCalledOnce();
  });

  it("shows no button when there is nothing to do", () => {
    render(<Empty title="Nothing yet" />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("hides its decorative icon from screen readers", () => {
    const { container } = render(<Empty title="Nothing yet" icon="◈" />);
    expect(container.querySelector(".state-icon")).toHaveAttribute("aria-hidden", "true");
  });
});

describe("errors", () => {
  it("shows a message written for a person", () => {
    render(<ErrorState error="Add at least one invoice line" />);
    expect(screen.getByText("Add at least one invoice line")).toBeInTheDocument();
  });

  it("accepts an Error object as well as a string", () => {
    render(<ErrorState error={new Error("Workspace not found.")} />);
    expect(screen.getByText("Workspace not found.")).toBeInTheDocument();
  });

  it("replaces a raw network failure with something actionable", () => {
    // "Failed to fetch" tells a person on a shift nothing they can act on.
    render(<ErrorState error={new Error("Failed to fetch")} />);

    expect(screen.queryByText(/Failed to fetch/)).not.toBeInTheDocument();
    expect(screen.getByText(/check your connection/i)).toBeInTheDocument();
  });

  it("recognises a network failure whatever the browser called it", () => {
    for (const message of ["NetworkError when attempting to fetch", "Load failed"]) {
      const { unmount } = render(<ErrorState error={new Error(message)} />);
      expect(screen.getByText(/check your connection/i)).toBeInTheDocument();
      unmount();
    }
  });

  it("never renders an empty message", () => {
    render(<ErrorState error={undefined} />);
    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
  });

  it("retries when asked", async () => {
    const onRetry = vi.fn();
    render(<ErrorState error="Nope" onRetry={onRetry} />);

    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("offers no retry button when retrying is not possible", () => {
    render(<ErrorState error="Nope" />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("loading", () => {
  it("announces itself to a screen reader", () => {
    render(<Loading label="Running four checks" />);
    expect(screen.getByRole("status", { name: "Running four checks" })).toBeInTheDocument();
  });

  it("draws the shape of what is coming, not a spinner", () => {
    const { container } = render(<Loading lines={4} />);
    expect(container.querySelectorAll(".skeleton")).toHaveLength(4);
  });

  it("draws taller blocks for table-ish content", () => {
    const { container } = render(<Loading rows={3} />);
    expect(container.querySelectorAll(".skeleton.tall")).toHaveLength(3);
  });
});

describe("the three together", () => {
  it("loading wins over everything", () => {
    render(
      <AsyncBoundary loading error="boom" empty>
        <p>data</p>
      </AsyncBoundary>,
    );
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.queryByText("boom")).not.toBeInTheDocument();
  });

  it("an error hides stale content rather than showing it as current", () => {
    // Showing last week's numbers under a failed refresh is worse than showing
    // nothing: the figures look live and are not.
    render(
      <AsyncBoundary error="Couldn't reach the server">
        <p>last week's numbers</p>
      </AsyncBoundary>,
    );
    expect(screen.queryByText("last week's numbers")).not.toBeInTheDocument();
  });

  it("empty is only reached once loading and error are done", () => {
    render(
      <AsyncBoundary empty emptyState={<Empty title="Nothing here" />}>
        <p>data</p>
      </AsyncBoundary>,
    );
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
  });

  it("renders the content when there is content", () => {
    render(
      <AsyncBoundary>
        <p>data</p>
      </AsyncBoundary>,
    );
    expect(screen.getByText("data")).toBeInTheDocument();
  });
});
