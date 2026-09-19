/**
 * The assistant's surfaces: the meter, the library, and the bubble.
 *
 * The meter this replaces read `tokens_used` against `included_allowance` and
 * told somebody they had used 43% of 650,000 tokens. Nobody can act on that,
 * and measured against the real context sizes the same percentage meant
 * sixty-five questions on a small workspace and six on a large one — wildly
 * different situations, rendered identically.
 *
 * Those fields no longer exist. The wallet reports money. A component still
 * reading the old shape would render NaN and nobody would notice until a
 * customer asked what it meant, so the first test here is that nothing does.
 */

import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const SRC = path.resolve(__dirname, "..");
const read = (f) => fs.readFileSync(path.join(SRC, f), "utf8");

// The token-era fields, gone from every response the backend now sends.
const RETIRED = [
  "tokens_used",
  "included_allowance",
  "remaining_included",
  "tokens_this_month",
  "overage_rate_per_1k_cents",
  "hard_ceiling",
];

function sources() {
  const found = [];
  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (entry.name !== "test") walk(full);
      } else if (/\.(jsx|js)$/.test(entry.name)) {
        found.push(full);
      }
    }
  };
  walk(SRC);
  return found;
}

describe("nothing still reads the token-era usage shape", () => {
  it("has files to check", () => {
    expect(sources().length).toBeGreaterThan(10);
  });

  it.each(RETIRED)("%s appears nowhere", (field) => {
    const offenders = sources()
      .filter((file) => {
        const src = fs
          .readFileSync(file, "utf8")
          .replace(/\/\*[\s\S]*?\*\//g, "")
          .replace(/(^|[^:])\/\/.*$/gm, "$1");
        return src.includes(field);
      })
      .map((file) => path.relative(SRC, file).replace(/\\/g, "/"));

    expect(offenders).toEqual([]);
  });
});

describe("the credit meter", () => {
  const meter = read("components/CreditMeter.jsx");

  it("reads the wallet", () => {
    expect(meter).toContain('api("/ai/usage")');
  });

  it("shows money rather than a percentage of something nobody can picture", () => {
    expect(meter).toMatch(/\$\{value\.toFixed\(2\)\}/);
    expect(meter).toContain("money(usage.remaining)");
  });

  it("says the credit is sold at cost", () => {
    // The whole pitch. "Pay for what you use" is only true if the number the
    // customer pays is the number we pay, and the meter is where somebody
    // finds out whether that is what is happening.
    //
    // Whitespace is flattened first: JSX wraps prose across lines wherever the
    // formatter put it, and a test that fails because a sentence broke after
    // "buy" instead of after "does" is a test about line length.
    const prose = meter.replace(/\s+/g, " ");
    expect(prose).toMatch(/no markup/i);
    expect(prose).toMatch(/does not expire/i);
  });

  it("warns before it runs out rather than only after", () => {
    // Being told "you have used your credit" is only fair to somebody who
    // could see it coming.
    expect(meter).toContain("is-low");
    expect(meter).toContain("is-empty");
  });

  it("hides rather than erroring in the middle of a conversation", () => {
    expect(meter).toMatch(/if \(error \|\| !usage\) return null/);
  });

  it("only fetches the owner-only breakdown when somebody opens it", () => {
    expect(meter).toMatch(/if \(!open \|\| breakdown\) return;/);
  });
});

describe("the chat library", () => {
  const library = read("components/ChatLibrary.jsx");

  it("lists the threads for one assistant at a time", () => {
    expect(library).toMatch(/\/threads\?surface=/);
  });

  it("offers a new chat", () => {
    expect(library).toContain("New chat");
  });

  it("archives rather than deletes", () => {
    // A conversation with an assistant about the business is a record of what
    // was asked and answered. Destroying it on a misclick is worse than a
    // longer list.
    expect(library).toMatch(/\/archive/);
    expect(library).not.toMatch(/method: "DELETE"/);
  });

  it("moves you somewhere when you archive the thread you are reading", () => {
    expect(library).toMatch(/if \(id === activeId\) onNew\?\.\(\)/);
  });
});

describe("the assistant page", () => {
  const page = read("pages/AgentPage.jsx");

  it("no longer sends the transcript from the browser", () => {
    // The server reads the thread from the database. Sending history as well
    // would mean two accounts of the same conversation, and the client's would
    // be the one that could be edited.
    expect(page).not.toMatch(/history,?\s*\}\)/);
    expect(page).toMatch(/body: JSON\.stringify\(\{ message, thread_id: threadId \}\)/);
  });

  it("can open a stored conversation", () => {
    expect(page).toMatch(/api\(`\/threads\/\$\{id\}`\)/);
  });

  it("draws a compaction summary as a note rather than as a message", () => {
    // It is not something somebody said. Rendering it in a speech bubble would
    // claim it was.
    expect(page).toContain("agent-summary");
    expect(page).toMatch(/Earlier in this conversation/);
  });
});

describe("the bubble", () => {
  const bubble = read("components/AssistantBubble.jsx");

  it("starts a new conversation every time it opens", () => {
    // It is the quick-question surface. Resuming what was said two days ago
    // would put every passing question on top of a transcript nobody
    // remembers, and charge for re-sending it.
    const effect = bubble.slice(bubble.indexOf("if (!open) return;"));
    expect(effect).toMatch(/setThreadId\(null\)/);
  });

  it("still starts a fresh one when the page changes which assistant answers", () => {
    expect(bubble).toMatch(/\}, \[scheduling\]\)/);
  });
});

describe("Ask sits on its own at the end of the navigation", () => {
  const app = read("App.jsx");

  it("is outside every group", () => {
    const block = app.slice(
      app.indexOf("const MANAGER_TABS"),
      app.indexOf("\n];", app.indexOf("const MANAGER_TABS")),
    );
    const loose = [...block.matchAll(/^ {2}\{ id: "([\w-]+)"/gm)].map((m) => m[1]);
    expect(loose).toEqual(["home", "ask"]);
  });

  it("is last", () => {
    const block = app.slice(
      app.indexOf("const MANAGER_TABS"),
      app.indexOf("\n];", app.indexOf("const MANAGER_TABS")),
    );
    const ids = [...block.matchAll(/\bid: "([\w-]+)"/g)].map((m) => m[1]);
    expect(ids[ids.length - 1]).toBe("ask");
  });
});

describe("the bubble sends staff to the assistant built for them", () => {
  const bubble = read("components/AssistantBubble.jsx");
  const app = read("App.jsx");

  it("routes an employee to their own endpoint", () => {
    // The other two are handed the whole business — every invoice, every bill
    // and every colleague's pay band — and refuse an employee outright, which
    // they have always done. The bubble is shown to employees deliberately,
    // and until this it sent them at an endpoint that answered 403 every time.
    expect(bubble).toMatch(/isEmployee[\s\S]{0,80}\/my\/assistant\/chat/);
  });

  it("is told who is asking", () => {
    expect(app).toMatch(/isEmployee=\{user\.role !== "manager"\}/);
  });

  it("does not apply the scheduling split to staff", () => {
    // An employee's assistant answers from their own record either way, so
    // routing them to the scheduling one would just be a 403 with extra steps.
    expect(bubble).toMatch(/!isEmployee && SCHEDULING_PAGES\.has\(page\)/);
  });
});
