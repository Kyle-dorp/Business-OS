/**
 * Empty, loading and error — the three states a page spends most of its life in.
 *
 * States.jsx states the rules correctly and was imported by five of twenty
 * pages. The other fifteen each wrote their own, which is why the product had
 * thirteen different loading states, all of them a sentence:
 *
 *     <section className="card os-loading">Counting the cost…</section>
 *
 * The copy was good. The behaviour was not: a line of text is not the shape of
 * what is coming, so the layout jumped when the data landed, and a screen
 * reader got a paragraph that changed into a table.
 *
 * They are skeletons now, and the copy survives as the accessible label —
 * "Counting the cost" tells somebody far more than a spinner does.
 *
 * Nine pages still fetch without States at all. That list is here rather than
 * in a TODO because a list in a test can only get shorter.
 */

import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const SRC = path.resolve(__dirname, "..");
const PAGES = path.join(SRC, "pages");

const pages = fs.readdirSync(PAGES).filter((f) => f.endsWith(".jsx"));
const read = (f) => fs.readFileSync(path.join(PAGES, f), "utf8");
const code = (f) =>
  read(f)
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/.*$/gm, "$1");

/**
 * Pages that fetch and still hand-roll their own states.
 *
 * Every name here is work not yet done, and the test fails if a name is added
 * or if one on the list turns out no longer to need to be. AuthPage is on it
 * for a different reason: it is a form rather than a data view, its "state" is
 * a validation message, and States has nothing to offer it.
 */
const NOT_YET_CONVERTED = new Set([
  "AssistantPage.jsx",
  "AuthPage.jsx",
  "AvailabilityPage.jsx",
  "EmployeeAvailabilityPage.jsx",
  "EmployeeHomePage.jsx",
  "NotificationsPage.jsx",
  "RequestsPage.jsx",
  "SettingsPage.jsx",
]);

describe("nobody writes their own loading state", () => {
  it("has pages to check", () => {
    expect(pages.length).toBeGreaterThan(15);
  });

  it.each(pages)("%s does not hand-roll a loading state", (page) => {
    const src = code(page);

    // The class the thirteen hand-rolled ones shared.
    expect(src).not.toMatch(/os-loading/);

    // And the shape they took: a bare sentence rendered where content goes.
    // `label="Loading stock"` is fine — that is the accessible name on a
    // skeleton. `>Loading stock…<` is the thing being banned.
    const bare = [...src.matchAll(/>\s*(Loading|Please wait)[^<{]*</gi)].map((m) => m[0].trim());
    expect(bare).toEqual([]);
  });

  it("the skeleton is what renders, and it announces itself", () => {
    const states = fs.readFileSync(path.join(SRC, "components", "States.jsx"), "utf8");
    expect(states).toMatch(/className=\{?[`"]?skeleton/);
    // A silent skeleton is a blank region to anyone not looking at it.
    expect(states).toMatch(/role="status"/);
    expect(states).toMatch(/aria-label=\{label\}/);
  });
});

describe("the conversion list only shrinks", () => {
  function fetchesWithoutStates() {
    return pages.filter((p) => {
      const src = code(p);
      return /\bapi\(/.test(src) && !src.includes("components/States");
    });
  }

  it("names no page that has already been converted", () => {
    // A stale entry hides a page that regressed back off States.
    const outstanding = new Set(fetchesWithoutStates());
    const stale = [...NOT_YET_CONVERTED].filter((p) => !outstanding.has(p));
    expect(stale).toEqual([]);
  });

  it("gains no new page", () => {
    const added = fetchesWithoutStates().filter((p) => !NOT_YET_CONVERTED.has(p));
    expect(added).toEqual([]);
  });
});
