/**
 * The assistant bubble.
 *
 * One control on every page, two brains behind it. The thing worth testing is
 * the routing: the scheduling assistant is the only one that can act on a
 * rota, and the agent is the only one that can see the books. Sending
 * "regenerate Tuesday" to the agent gets a polite paragraph and no rota, and
 * the person asking would have no way to know why.
 *
 * The second thing is context. If the bubble does not carry the week, every
 * scheduling question needs a follow-up asking which week — which is exactly
 * the friction that stopped anybody using the full page.
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => vi.fn());
vi.mock("../api", () => ({ api }));

import AssistantBubble from "../components/AssistantBubble.jsx";

function respond(reply = {}) {
  api.mockImplementation(() =>
    Promise.resolve({ thread_id: 1, reply: "Here is what I found.", ...reply }));
}

const openBubble = async () =>
  userEvent.click(screen.getByRole("button", { name: /Ask the assistant/i }));

beforeEach(() => {
  api.mockReset();
});

// ===================================================== which brain answers

describe("routing to the right brain", () => {
  it.each(["manager", "availability", "preflight", "compliance"])(
    "uses the scheduling assistant on %s",
    async (page) => {
      respond();
      render(<AssistantBubble page={page} pageLabel="Scheduling" weekStart="2026-09-14" />);

      await openBubble();
      await userEvent.type(screen.getByRole("textbox"), "who is short");
      await userEvent.click(screen.getByRole("button", { name: "Ask" }));

      await waitFor(() => expect(api).toHaveBeenCalled());
      expect(api.mock.calls[0][0]).toBe("/assistant/chat");
    },
  );

  it.each(["home", "sales", "accounting", "inventory", "billing"])(
    "uses the agent on %s",
    async (page) => {
      respond();
      render(<AssistantBubble page={page} pageLabel="Home" />);

      await openBubble();
      await userEvent.type(screen.getByRole("textbox"), "how did last month go");
      await userEvent.click(screen.getByRole("button", { name: "Ask" }));

      await waitFor(() => expect(api).toHaveBeenCalled());
      expect(api.mock.calls[0][0]).toBe("/agent/chat");
    },
  );

  it("an unfamiliar page falls back to the agent", async () => {
    // A page added later must still have a working assistant rather than none.
    respond();
    render(<AssistantBubble page="something-new" pageLabel="New" />);

    await openBubble();
    await userEvent.type(screen.getByRole("textbox"), "hello");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));

    await waitFor(() => expect(api).toHaveBeenCalled());
    expect(api.mock.calls[0][0]).toBe("/agent/chat");
  });
});

// ========================================================= carrying context

describe("arriving knowing where you are", () => {
  it("sends the week with a scheduling question", async () => {
    respond();
    render(<AssistantBubble page="manager" pageLabel="Scheduling" weekStart="2026-09-14" scheduleId={7} />);

    await openBubble();
    await userEvent.type(screen.getByRole("textbox"), "make Tuesday lighter");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));

    await waitFor(() => expect(api).toHaveBeenCalled());
    const body = JSON.parse(api.mock.calls[0][1].body);
    expect(body.week_start).toBe("2026-09-14");
    expect(body.schedule_id).toBe(7);
  });

  it("names the week on screen, so it is obvious which one it means", async () => {
    respond();
    render(<AssistantBubble page="manager" pageLabel="Scheduling" weekStart="2026-09-14" />);

    await openBubble();
    expect(screen.getByText(/Week of 2026-09-14/)).toBeInTheDocument();
  });

  it("names the page when it is the agent", async () => {
    respond();
    render(<AssistantBubble page="sales" pageLabel="Sales & invoices" />);

    await openBubble();
    expect(screen.getByText(/You are on Sales & invoices/)).toBeInTheDocument();
  });

  it("offers starters worth asking from the page you are on", async () => {
    respond();
    const { unmount } = render(<AssistantBubble page="manager" pageLabel="Scheduling" />);
    await openBubble();
    expect(screen.getByRole("button", { name: /Regenerate Tuesday/ })).toBeInTheDocument();
    unmount();

    render(<AssistantBubble page="inventory" pageLabel="Inventory" />);
    await openBubble();
    expect(screen.getByRole("button", { name: /running low/ })).toBeInTheDocument();
  });

  it("a starter asks the question rather than filling the box", async () => {
    respond();
    render(<AssistantBubble page="home" pageLabel="Home" />);

    await openBubble();
    await userEvent.click(screen.getByRole("button", { name: "How did last month go?" }));

    await waitFor(() => expect(api).toHaveBeenCalled());
    expect(JSON.parse(api.mock.calls[0][1].body).message).toBe("How did last month go?");
  });
});

// ======================================================== the conversation

describe("the conversation", () => {
  it("shows the question and the answer", async () => {
    respond({ reply: "You took £4,200 last month." });
    render(<AssistantBubble page="home" pageLabel="Home" />);

    await openBubble();
    await userEvent.type(screen.getByRole("textbox"), "how did last month go");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));

    expect(await screen.findByText("You took £4,200 last month.")).toBeInTheDocument();
    expect(screen.getByText("how did last month go")).toBeInTheDocument();
  });

  it("carries the thread, so a follow-up is a follow-up", async () => {
    respond({ thread_id: 42 });
    render(<AssistantBubble page="home" pageLabel="Home" />);

    await openBubble();
    const box = screen.getByRole("textbox");
    await userEvent.type(box, "first");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));
    await screen.findByText("Here is what I found.");

    await userEvent.type(box, "and after that?");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));

    await waitFor(() => expect(api).toHaveBeenCalledTimes(2));
    expect(JSON.parse(api.mock.calls[1][1].body).thread_id).toBe(42);
  });

  it("changing brain starts a new conversation", async () => {
    // Carrying a rota transcript into a question about invoices would give the
    // model a conversation about shifts and a question about money.
    respond();
    const { rerender } = render(<AssistantBubble page="manager" pageLabel="Scheduling" />);

    await openBubble();
    await userEvent.type(screen.getByRole("textbox"), "who is short");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));
    await screen.findByText("Here is what I found.");

    rerender(<AssistantBubble page="sales" pageLabel="Sales" />);

    await waitFor(() =>
      expect(screen.queryByText("who is short")).not.toBeInTheDocument());
  });

  it("moving between two pages with the same brain keeps the conversation", async () => {
    respond();
    const { rerender } = render(<AssistantBubble page="sales" pageLabel="Sales" />);

    await openBubble();
    await userEvent.type(screen.getByRole("textbox"), "who owes me");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));
    await screen.findByText("Here is what I found.");

    rerender(<AssistantBubble page="accounting" pageLabel="Bookkeeping" />);
    expect(screen.getByText("who owes me")).toBeInTheDocument();
  });

  it("says when changes were proposed rather than silently dropping them", async () => {
    respond({ proposals: [{ id: 1, summary: "Raise the price" }] });
    render(<AssistantBubble page="home" pageLabel="Home" />);

    await openBubble();
    await userEvent.type(screen.getByRole("textbox"), "put prices up");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));

    expect(await screen.findByText(/1 change proposed/)).toBeInTheDocument();
  });
});

// ============================================================== failure

describe("when it cannot be reached", () => {
  it("gives the question back rather than losing it", async () => {
    // Somebody typed that. Clearing the box on a network blip means they type
    // it again, and the second time they do not bother.
    api.mockImplementation(() => Promise.reject(new Error("Failed to fetch")));
    render(<AssistantBubble page="home" pageLabel="Home" />);

    await openBubble();
    await userEvent.type(screen.getByRole("textbox"), "how did last month go");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));

    await waitFor(() =>
      expect(screen.getByRole("textbox")).toHaveValue("how did last month go"));
  });

  it("says what went wrong", async () => {
    api.mockImplementation(() => Promise.reject(new Error("Out of allowance")));
    render(<AssistantBubble page="home" pageLabel="Home" />);

    await openBubble();
    await userEvent.type(screen.getByRole("textbox"), "hello");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));

    expect(await screen.findByText("Out of allowance")).toBeInTheDocument();
  });

  it("does not leave a question hanging with no answer under it", async () => {
    api.mockImplementation(() => Promise.reject(new Error("nope")));
    render(<AssistantBubble page="home" pageLabel="Home" />);

    await openBubble();
    await userEvent.type(screen.getByRole("textbox"), "hello");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));

    await screen.findByText("nope");
    expect(document.querySelectorAll(".eos-turn.is-user")).toHaveLength(0);
  });
});

// ============================================================== behaviour

describe("opening and closing", () => {
  it("starts closed and out of the way", () => {
    render(<AssistantBubble page="home" pageLabel="Home" />);

    expect(screen.getByRole("button", { name: /Ask the assistant/i }))
      .toHaveAttribute("aria-expanded", "false");
  });

  it("escape closes it, because a panel that traps you is a modal", async () => {
    render(<AssistantBubble page="home" pageLabel="Home" />);

    await openBubble();
    expect(screen.getByRole("button", { name: /Close the assistant/i })).toBeInTheDocument();

    await userEvent.keyboard("{Escape}");
    expect(screen.getByRole("button", { name: /Ask the assistant/i })).toBeInTheDocument();
  });

  it("will not send an empty question", async () => {
    render(<AssistantBubble page="home" pageLabel="Home" />);

    await openBubble();
    expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();
  });

  it("marks itself when something is waiting", () => {
    const { container, rerender } = render(
      <AssistantBubble page="home" pageLabel="Home" attention={3} />);
    expect(container.querySelector(".eos-bubble.has-attention")).toBeInTheDocument();

    rerender(<AssistantBubble page="home" pageLabel="Home" attention={0} />);
    expect(container.querySelector(".eos-bubble.has-attention")).not.toBeInTheDocument();
  });

  it("stops marking itself once opened", async () => {
    // The ring means "there is something you have not seen". Opening it is
    // seeing it.
    const { container } = render(
      <AssistantBubble page="home" pageLabel="Home" attention={3} />);

    await openBubble();
    expect(container.querySelector(".eos-bubble.has-attention")).not.toBeInTheDocument();
  });
});
