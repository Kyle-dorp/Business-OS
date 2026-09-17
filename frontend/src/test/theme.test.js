/**
 * The design language, checked rather than trusted.
 *
 * Three times now a second stylesheet has quietly won a specificity fight and
 * repainted the app: index.css with its Tailwind base, App.css with the
 * pre-redesign auth screen and topbar, and src/styles/ with an entire cyan
 * design system that was one import away from going live. Each was invisible
 * in review and obvious on screen.
 *
 * And --faint shipped at 3.17:1 against the ground — below the 4.5 body floor
 * — while carrying labels, metadata and timestamps on every screen. Nothing
 * caught it because nothing was looking.
 *
 * These are the checks that would have caught all four.
 */

import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const SRC = path.resolve(__dirname, "..");
const read = (f) => fs.readFileSync(path.join(SRC, f), "utf8");

// Comments explain what was removed and why, and they name the things they
// removed — so a scan for "does this file still define --ink" finds the note
// saying it no longer does. Strip them before looking at declarations.
const code = (f) => read(f).replace(/\/\*[\s\S]*?\*\//g, "");

// ---------------------------------------------------------------- contrast

function luminance(hex) {
  const h = hex.replace("#", "");
  const channels = [0, 2, 4].map((i) => {
    const v = parseInt(h.slice(i, i + 2), 16) / 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

function contrast(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

function tokens() {
  const css = read("theme.css");
  const block = css.slice(css.indexOf(":root"), css.indexOf("}", css.indexOf(":root")));
  const found = {};
  for (const [, name, value] of block.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})/g)) {
    found[name] = value;
  }
  return found;
}

describe("colour tokens against the ground", () => {
  const t = tokens();
  const ground = t.void;

  it("defines the ground it is all measured against", () => {
    expect(ground).toMatch(/^#[0-9a-fA-F]{6}$/);
  });

  // Everything that carries words. --faint is in here deliberately: it holds
  // labels and metadata, which are read, so it is body text.
  it.each(["ink", "ink-2", "muted", "faint"])(
    "--%s carries text and clears the 4.5:1 body floor",
    (name) => {
      expect(contrast(t[name], ground)).toBeGreaterThanOrEqual(4.5);
    },
  );

  it.each(["amber", "amber-hot", "mint", "rose"])(
    "--%s is legible on the ground",
    (name) => {
      expect(contrast(t[name], ground)).toBeGreaterThanOrEqual(4.5);
    },
  );

  it("keeps its hierarchy — each step quieter than the one above", () => {
    // If --faint ever overtakes --muted, de-emphasis stops meaning anything.
    const ink = contrast(t.ink, ground);
    const ink2 = contrast(t["ink-2"], ground);
    const muted = contrast(t.muted, ground);
    const faint = contrast(t.faint, ground);

    expect(ink).toBeGreaterThan(ink2);
    expect(ink2).toBeGreaterThan(muted);
    expect(muted).toBeGreaterThan(faint);
  });
});

// ------------------------------------------------------- one design system

describe("only one design system in the tree", () => {
  it("has no second stylesheet defining the same tokens", () => {
    // src/styles/design-tokens.css defined --bg, --surface, --text and a cyan
    // --accent on a white ground, dead in the tree and one import from live.
    expect(fs.existsSync(path.join(SRC, "styles"))).toBe(false);
  });

  it("does not ship a CSS framework nothing uses", () => {
    const root = path.resolve(SRC, "..");
    expect(fs.existsSync(path.join(root, "tailwind.config.js"))).toBe(false);

    const pkg = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8"));
    expect(Object.keys(pkg.devDependencies)).not.toContain("tailwindcss");
  });

  it("only theme.css defines the palette tokens", () => {
    // Any other file defining --ink or --amber is a second source of truth,
    // and the loser of that fight changes with import order.
    const offenders = fs
      .readdirSync(SRC)
      .filter((f) => f.endsWith(".css") && f !== "theme.css")
      .filter((f) => /--(?:ink|amber|void|mint|rose|muted|faint)\s*:/.test(code(f)));

    expect(offenders).toEqual([]);
  });
});

// ----------------------------------------------------- the old palette

describe("the pre-redesign palette is gone", () => {
  const legacy = /#(?:2f6fed|2258c7|7259e9|152033|172033|eef3f9|fafcff|00d9ff)\b/i;

  it.each(fs.readdirSync(SRC).filter((f) => f.endsWith(".css")))(
    "%s has no blue-and-purple leftovers",
    (file) => {
      expect(code(file)).not.toMatch(legacy);
    },
  );

  it("App.css no longer paints the root element", () => {
    // Its :root block set a light background, a dark ink and its own font
    // stack, over a design built for warm near-black.
    expect(code("App.css")).not.toMatch(/^:root\s*\{/m);
  });

  it("App.css has no near-opaque white surfaces left", () => {
    const whites = code("App.css").match(
      /rgba\(\s*25[0-5]\s*,\s*25[0-5]\s*,\s*25[0-5]\s*,\s*(?:0?\.[5-9]\d*|1)\s*\)/g,
    );
    expect(whites).toBeNull();
  });
});
