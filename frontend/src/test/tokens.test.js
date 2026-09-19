/**
 * The design system's blind spot: colour and spacing written in JavaScript.
 *
 * theme.test.js checks the stylesheets, and every stylesheet passes. Then this
 * was found in components and pages, where it had never been looked at:
 *
 *   Button.tsx     var(--text-muted), 1px solid #e5e7eb, borderRadius '6px',
 *                  transition cubic-bezier(0.4, 0, 0.2, 1) — a second easing
 *                  curve competing with --ease
 *   Card.tsx       var(--shadow-sm), var(--shadow-lg), var(--shadow-glow),
 *                  borderColor #f0f0f0, padding '24px'
 *   FinancePage    six pre-redesign colours passed as props — #2f6fed blue,
 *                  #7259e9 purple, #e07a00 orange — on the page about money,
 *                  where mint and rose already mean something specific
 *
 * Four of those tokens do not exist. `var(--shadow-glow)` resolving to nothing
 * makes the whole box-shadow declaration invalid, so the card had no shadow at
 * all rather than a wrong one — the kind of failure that looks like a design
 * choice.
 *
 * VISUAL_DIRECTION.md recommends adopting Button, Card and Input across all
 * twenty pages. Doing that as written would have repainted them in the
 * pre-redesign palette: the fifth time in this project that a second design
 * system quietly won, and the first time a document recommended it.
 *
 * So: the same rules as the stylesheets, applied to the code.
 */

import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const SRC = path.resolve(__dirname, "..");

/** Every .js/.jsx/.ts/.tsx under src, excluding the tests themselves. */
function sourceFiles(dir = SRC, found = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name !== "test") sourceFiles(full, found);
    } else if (/\.(js|jsx|ts|tsx)$/.test(entry.name)) {
      found.push(full);
    }
  }
  return found;
}

const relative = (f) => path.relative(SRC, f).replace(/\\/g, "/");

/**
 * Source with comments and import paths removed.
 *
 * Comments are stripped because the good files explain their colour choices by
 * naming the hex — Charts.jsx documents "rose #D9788D out / mint #77D8C2 in",
 * which is exactly the discipline we want, and a check that punished it would
 * teach people to stop writing it down.
 */
function code(file) {
  return fs
    .readFileSync(file, "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/.*$/gm, "$1");
}

// ---------------------------------------------------------------- tokens

describe("every token used is a token that exists", () => {
  const theme = fs.readFileSync(path.join(SRC, "theme.css"), "utf8");
  const defined = new Set(
    [...theme.matchAll(/^\s*(--[\w-]+)\s*:/gm)].map((m) => m[1]),
  );

  it("found the definitions to check against", () => {
    expect(defined.size).toBeGreaterThan(20);
  });

  const used = new Map();
  for (const file of sourceFiles()) {
    for (const [, token] of code(file).matchAll(/var\((--[\w-]+)/g)) {
      if (!used.has(token)) used.set(token, new Set());
      used.get(token).add(relative(file));
    }
  }

  it("has tokens to check", () => {
    expect(used.size).toBeGreaterThan(0);
  });

  it("references no token theme.css does not define", () => {
    // A var() naming nothing does not fall back and does not warn. It makes
    // the declaration invalid, so the property is simply absent — which reads
    // as a deliberately flat design rather than a bug.
    const missing = {};
    for (const [token, files] of used) {
      if (!defined.has(token)) missing[token] = [...files].sort();
    }
    expect(missing).toEqual({});
  });
});

// ---------------------------------------------------------------- colour

describe("colour lives in the stylesheets, not in the components", () => {
  // Greyscale is allowed for the same reason it is allowed in the CSS: a
  // shadow is an absence of light, and it means the same in every theme.
  const HEX = /#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b/g;
  const RGB = /rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/g;

  function chromatic(file) {
    const src = code(file);
    const found = [];

    for (const [whole, digits] of src.matchAll(HEX)) {
      const full =
        digits.length === 3
          ? digits
              .split("")
              .map((c) => c + c)
              .join("")
          : digits;
      const [r, g, b] = [0, 2, 4].map((i) => parseInt(full.slice(i, i + 2), 16));
      if (!(r === g && g === b)) found.push(whole);
    }
    for (const [whole, r, g, b] of src.matchAll(RGB)) {
      if (!(r === g && g === b)) found.push(whole);
    }
    return found;
  }

  const files = sourceFiles();

  it("has components to check", () => {
    expect(files.length).toBeGreaterThan(10);
  });

  it.each(files.map(relative))("%s names no colour of its own", (rel) => {
    expect(chromatic(path.join(SRC, rel))).toEqual([]);
  });
});

// ----------------------------------------------------------------- motion

describe("there is one easing curve", () => {
  it("defines it once, in the theme", () => {
    const theme = fs.readFileSync(path.join(SRC, "theme.css"), "utf8");
    expect(theme).toMatch(/--ease:\s*cubic-bezier/);
  });

  it("is never restated anywhere else", () => {
    // Button.tsx carried cubic-bezier(0.4, 0, 0.2, 1) against the theme's
    // (0.22, 0.72, 0.2, 1). Two curves in one product is two products.
    const offenders = [];
    for (const file of sourceFiles()) {
      if (/cubic-bezier/.test(code(file))) offenders.push(relative(file));
    }
    for (const entry of fs.readdirSync(SRC)) {
      if (!entry.endsWith(".css") || entry === "theme.css") continue;
      const css = fs
        .readFileSync(path.join(SRC, entry), "utf8")
        .replace(/\/\*[\s\S]*?\*\//g, "");
      if (/cubic-bezier/.test(css)) offenders.push(entry);
    }
    expect(offenders).toEqual([]);
  });
});
