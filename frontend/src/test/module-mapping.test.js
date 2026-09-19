/**
 * Ten modules, twenty-one pages, and nothing on screen connecting them.
 *
 * "I look through the website and every single one seems to be just the same
 * books/inventory, I just don't get how there's ten separate ones."
 *
 * That was a fair report. The navigation lists pages, billing lists modules,
 * and the two lists never referred to each other. Scheduling is four pages.
 * Bookkeeping is two. Nothing said so, and every page opened with a decorative
 * eyebrow — BUSINESS OS, FINANCIAL CONTROL CENTER, THE OPERATING LOOP,
 * twenty-eight of them, none repeating and none informative.
 *
 * The mapping already existed: every tab in MANAGER_TABS carries a `module`.
 * The nav has always known which module a page belongs to. It just never said.
 *
 * These check that it keeps saying it, and that the mapping stays honest — a
 * tab pointing at a module that does not exist would put a price on a page
 * nobody can buy.
 */

import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const SRC = path.resolve(__dirname, "..");
const app = fs.readFileSync(path.join(SRC, "App.jsx"), "utf8");

/** Module keys the product actually sells, read from the backend registry. */
function registryKeys() {
  const registry = fs.readFileSync(
    path.resolve(SRC, "..", "..", "backend", "app", "modules_registry.py"),
    "utf8",
  );
  return [...registry.matchAll(/^\s*key="([\w-]+)"/gm)].map((m) => m[1]);
}

function tabsWithModules() {
  return [...app.matchAll(/id: "([\w-]+)", label: "([^"]+)"[^}]*?module: "([\w-]+)"/g)].map(
    (m) => ({ id: m[1], label: m[2], module: m[3] }),
  );
}

describe("every page belongs to a module somebody can buy", () => {
  it("found the tabs and the registry", () => {
    expect(tabsWithModules().length).toBeGreaterThan(10);
    expect(registryKeys().length).toBeGreaterThan(10);
  });

  it("names no module the product does not sell", () => {
    // The webhook once wrote module_key "scheduler", which is not a module,
    // and a cancelled customer kept $119/month of product as a result. A tab
    // pointing at a key that does not exist is the same mistake in the other
    // direction — a page nobody can be charged for or cut off from.
    const keys = new Set(registryKeys());
    const strays = tabsWithModules().filter((t) => !keys.has(t.module));
    expect(strays).toEqual([]);
  });

  // Every module that is charged for. Listed rather than parsed out of the
  // registry: `billable` defaults to True and is only written on the three
  // that are free, so a regex for it finds nothing and a test built on one
  // passes by finding nothing — which is how a check ends up guarding air.
  const BILLABLE = [
    "scheduling", "inventory", "accounting", "sales", "purchasing",
    "team", "booking", "tasks", "reports", "assistant",
  ];

  it.each(BILLABLE)("%s is reachable from the navigation", (key) => {
    // A module with no page is a line on an invoice and nothing on screen.
    expect(new Set(tabsWithModules().map((t) => t.module))).toContain(key);
  });

  it("charges for nothing the registry does not list", () => {
    expect(BILLABLE.filter((k) => !registryKeys().includes(k))).toEqual([]);
  });
});

describe("the app says which module you are in", () => {
  it("renders the tag in the topbar, once, where every page passes through", () => {
    // In the topbar rather than on each page: one place that already knows the
    // open tab, instead of an edit to twenty files that the twenty-first will
    // forget.
    expect(app).toMatch(/<ModuleTag\s+moduleKey=\{moduleOfTab\(activeTab\)\}/);
    expect(app.match(/<ModuleTag/g) || []).toHaveLength(1);
  });

  it("reads the module from the navigation rather than a second mapping", () => {
    // Two lists of which page belongs to which module is two lists that
    // disagree. This one is derived from the tabs the nav is built from.
    expect(app).toMatch(/function moduleOfTab/);
    expect(app).toMatch(/flatten\(MANAGER_TABS\)\.find/);
  });

  it("tells billing which pages each module unlocks", () => {
    expect(app).toMatch(/function pagesByModule/);
    expect(app).toMatch(/<BillingPage[^>]*pages=\{pagesByModule\(\)\}/);
  });
});

describe("the tag does not make claims about money it should not", () => {
  const tag = fs.readFileSync(path.join(SRC, "components", "ModuleTag.jsx"), "utf8");

  it("says nothing about price for the modules that are never charged for", () => {
    // Overview, Settings and Notifications are always on and never billed.
    // A price beside Settings would simply be false.
    expect(tag).toMatch(/if \(!module\.billable\)/);
  });

  it("distinguishes a module that is switched off", () => {
    expect(tag).toMatch(/is-off/);
  });

  it("renders nothing rather than guessing when the catalogue has not loaded", () => {
    expect(tag).toMatch(/if \(!module\) return null/);
  });
});
