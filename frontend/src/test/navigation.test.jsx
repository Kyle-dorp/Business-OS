/**
 * The navigation.
 *
 * Twenty-one flat entries was not a navigation, it was an inventory — and it
 * meant a new workspace's first impression was twenty-one things nobody had
 * set up. They sit behind six groups now.
 *
 * The thing worth guarding is that grouping stayed a change to how the list is
 * drawn and nothing else. Every tab id is addressed from somewhere: the router
 * in App.jsx, the saved-tab restore in localStorage, the dashboard tiles'
 * onNavigate, the onboarding checklist's `tab`, and the attention rows. A
 * renamed id breaks those silently — the button still renders, it just goes
 * nowhere.
 */

import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const SRC = path.resolve(__dirname, "..");
const app = fs.readFileSync(path.join(SRC, "App.jsx"), "utf8");

/** Every leaf id in MANAGER_TABS, groups flattened. */
function tabIds() {
  const block = app.slice(app.indexOf("const MANAGER_TABS"), app.indexOf("\n];", app.indexOf("const MANAGER_TABS")));
  return [...block.matchAll(/\bid:\s*"([\w-]+)"/g)].map((m) => m[1]);
}

function groups() {
  const block = app.slice(app.indexOf("const MANAGER_TABS"), app.indexOf("\n];", app.indexOf("const MANAGER_TABS")));
  return [...block.matchAll(/\bgroup:\s*"([\w &]+)"/g)].map((m) => m[1]);
}

describe("the shape of it", () => {
  it("is six groups, not twenty-one flat entries", () => {
    expect(groups()).toEqual(["Money", "People", "Stock", "Guests", "Work", "Settings"]);
  });

  it("keeps Today and Ask at the top level", () => {
    // The two that are not a category: where you land, and the thing you ask.
    const block = app.slice(app.indexOf("const MANAGER_TABS"), app.indexOf("\n];", app.indexOf("const MANAGER_TABS")));
    // Exactly two spaces: grouped items are indented four, and \s* matched
    // both, so this originally "found" all twenty-one.
    const loose = [...block.matchAll(/^ {2}\{ id: "([\w-]+)"/gm)].map((m) => m[1]);
    expect(loose).toEqual(["home", "ask"]);
  });

  it("still reaches every destination", () => {
    expect(tabIds()).toHaveLength(21);
    expect(new Set(tabIds()).size).toBe(21);
  });
});

describe("grouping changed the drawing and nothing else", () => {
  // Every id the rest of the app navigates to by name. If grouping had renamed
  // one, the button would render and go nowhere.
  const addressed = [
    "home", "sales", "purchasing", "accounting", "finance", "reports",
    "manager", "availability", "preflight", "compliance", "assistant",
    "inventory", "inventory-intel", "bookings", "contacts",
    "tasks", "notifications", "ask", "settings", "billing", "security",
  ];

  it.each(addressed)("%s is still a real destination", (id) => {
    expect(tabIds()).toContain(id);
  });

  it("every id the router renders has a way to get to it", () => {
    // activeTab === "x" in the render, with no nav entry, is a dead page.
    const rendered = [...app.matchAll(/activeTab === "([\w-]+)"/g)].map((m) => m[1]);
    const employeeOnly = new Set(["my-availability", "requests"]);
    const orphans = [...new Set(rendered)]
      .filter((id) => !employeeOnly.has(id))
      .filter((id) => !tabIds().includes(id));

    expect(orphans).toEqual([]);
  });

  it("every destination the dashboard sends people to exists", () => {
    // TodayPage and the onboarding checklist both navigate by tab id.
    const today = fs.readFileSync(path.join(SRC, "pages", "TodayPage.jsx"), "utf8");
    const targets = [...today.matchAll(/onNavigate\?\.\("([\w-]+)"\)/g)].map((m) => m[1]);

    expect(targets.length).toBeGreaterThan(0);
    for (const t of targets) expect(tabIds()).toContain(t);
  });
});

describe("the drawer is readable without the icons", () => {
  it("hides the glyphs from screen readers", () => {
    // The icon language is ⌂ ◎ $ ↓ ≡ ↗ ✓ □ ◉ ◷ ▦ ◈ ⚖ ◑ ✦ ◇ ● ⛨ ⚙ — several of
    // those are announced as punctuation, and one is announced as a currency.
    // The label carries the meaning.
    expect(app).toMatch(/className="nav-icon" aria-hidden="true"/);
  });

  it("marks which page you are on for assistive tech, not just visually", () => {
    expect(app).toMatch(/aria-current=\{activeTab === tab\.id \? "page" : undefined\}/);
  });

  it("gives the notification count a label rather than a bare number", () => {
    expect(app).toMatch(/aria-label=\{`\$\{notificationCount\} unread`\}/);
  });
});
