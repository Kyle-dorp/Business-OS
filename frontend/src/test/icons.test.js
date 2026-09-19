/**
 * The icon set.
 *
 * The navigation ran on a typographic alphabet. It looked deliberate, because
 * it was consistent, and it had a problem consistency cannot fix: `$` marked
 * both Sales & invoices and Finance, and `◉` marked both Stock intelligence
 * and Plan & billing — two destinations related by nothing at all.
 *
 * Ten of twenty-two entries shared a glyph with something else, so the icon
 * could not be the thing you navigated by. That is the property this file
 * guards: every destination has an icon, and no two destinations in the same
 * menu have the same one.
 *
 * Keys rather than imported components, so the set can be checked as data
 * without rendering anything.
 */

import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { ICONS } from "../icons.jsx";

const SRC = path.resolve(__dirname, "..");
const app = fs.readFileSync(path.join(SRC, "App.jsx"), "utf8");

function tabs(constName) {
  const start = app.indexOf(`const ${constName}`);
  if (start < 0) return [];
  const block = app.slice(start, app.indexOf("\n];", start));
  return [...block.matchAll(/id: "([\w-]+)", label: "([^"]+)", icon: "([^"]+)"/g)].map((m) => ({
    id: m[1],
    label: m[2],
    icon: m[3],
  }));
}

const manager = tabs("MANAGER_TABS");
const employee = tabs("EMPLOYEE_TABS");

describe("every destination has an icon", () => {
  it("found the navigation to check", () => {
    expect(manager.length).toBeGreaterThan(15);
    expect(employee.length).toBeGreaterThan(2);
  });

  it.each([...manager, ...employee].map((t) => [t.label, t.icon]))(
    "%s names an icon the set defines (%s)",
    (_label, icon) => {
      expect(Object.keys(ICONS)).toContain(icon);
    },
  );

  it("no longer stores a typographic glyph", () => {
    // Anything outside a-z, 0-9 and a hyphen is the old alphabet coming back.
    const glyphs = [...manager, ...employee].filter((t) => !/^[a-z0-9-]+$/.test(t.icon));
    expect(glyphs).toEqual([]);
  });
});

describe("no two destinations share an icon", () => {
  function duplicates(list) {
    const seen = new Map();
    const clashes = {};
    for (const tab of list) {
      if (seen.has(tab.icon)) {
        clashes[tab.icon] = [seen.get(tab.icon), tab.label];
      }
      seen.set(tab.icon, tab.label);
    }
    return clashes;
  }

  it("in the manager navigation", () => {
    // This is the assertion that would have failed before: `$` on Sales and
    // Finance, `◉` on Stock intelligence and Plan & billing.
    expect(duplicates(manager)).toEqual({});
  });

  it("in the employee navigation", () => {
    expect(duplicates(employee)).toEqual({});
  });

  it("except where the two menus mean the same thing", () => {
    // Availability and My availability are one concept seen from two sides,
    // and Home and Settings are the same destination. Sharing an icon across
    // the two menus is correct; sharing one inside a menu is not.
    const shared = employee
      .filter((e) => manager.some((m) => m.icon === e.icon))
      .map((e) => e.id)
      .sort();
    expect(shared).toEqual(["home", "my-availability", "settings"]);
  });
});

describe("the icon does not get announced twice", () => {
  const source = fs.readFileSync(path.join(SRC, "icons.jsx"), "utf8");

  it("is decorative unless it is given a label", () => {
    // The label beside it already says where the link goes. "calendar days,
    // Scheduling" is worse than "Scheduling".
    expect(source).toMatch(/aria-hidden=\{label \? undefined : "true"\}/);
  });

  it("takes itself out of the tab order", () => {
    expect(source).toMatch(/focusable="false"/);
  });

  it("draws every icon at one size and one weight", () => {
    // Mixed stroke weights are the fastest way to make a real icon set look
    // like clip art.
    expect(source).toMatch(/strokeWidth=\{1\.5\}/);
    expect(source).toMatch(/size = 18/);
  });
});
