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

/**
 * Every rgb/rgba in a stylesheet that names an actual colour.
 *
 * Greyscale is filtered out, not because it is harmless but because it is the
 * one thing that means the same in every theme: a shadow.
 */
function chromaticIn(file) {
  return [...code(file).matchAll(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/g)]
    .filter((m) => !(m[1] === m[2] && m[2] === m[3]))
    .map((m) => m[0]);
}

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

/** Hue angle in degrees, 0-360. */
function hue(hex) {
  const h = hex.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  if (max === min) return 0;
  const d = max - min;
  let deg;
  if (max === r) deg = ((g - b) / d) % 6;
  else if (max === g) deg = (b - r) / d + 2;
  else deg = (r - g) / d + 4;
  return (deg * 60 + 360) % 360;
}

/** Shortest distance between two hue angles, 0-180. */
function hueGap(a, b) {
  const gap = Math.abs(hue(a) - hue(b)) % 360;
  return gap > 180 ? 360 - gap : gap;
}

/**
 * Every hex a theme block defines, keyed by theme, with --accent, --accent-hot
 * and --accent-deep resolved through the chosen accent ramp.
 *
 * Resolving matters: the themes name rungs (var(--a-400)), not colours, so a
 * test that read the literal value would be checking the string "var(--a-400)"
 * against a ground and passing for the wrong reason.
 */
function ramps() {
  const css = read("theme.css");
  const found = {};
  for (const [, name, body] of css.matchAll(/\[data-accent="(\w+)"\]\s*\{([^}]*)\}/g)) {
    found[name] = Object.fromEntries(
      [...body.matchAll(/--(a-\d+):\s*(#[0-9a-fA-F]{6})/g)].map((m) => [m[1], m[2]]),
    );
  }
  // The default family is declared on :root alongside [data-accent="amber"].
  const amber = css.match(/:root,\s*\[data-accent="amber"\]\s*\{([^}]*)\}/);
  if (amber) {
    found.amber = Object.fromEntries(
      [...amber[1].matchAll(/--(a-\d+):\s*(#[0-9a-fA-F]{6})/g)].map((m) => [m[1], m[2]]),
    );
  }
  return found;
}

function themeBlock(name) {
  const css = read("theme.css");
  // indexOf rather than a regex: the selector for dark is `:root,
  // [data-theme="dark"]`, and a pattern general enough to match both that and
  // the plain selectors is harder to read than finding the brace.
  const selector = `[data-theme="${name}"]`;
  const at = css.indexOf(selector);
  if (at < 0) throw new Error(`no theme block for ${name}`);
  const open = css.indexOf("{", at);
  const close = css.indexOf("\n}", open);
  return css.slice(open + 1, close);
}

function tokens(theme, accent) {
  const body = themeBlock(theme);
  const ramp = ramps()[accent];
  const out = {};
  for (const [, name, value] of body.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})/g)) {
    out[name] = value;
  }
  for (const [, name, rung] of body.matchAll(/--([\w-]+):\s*var\(--(a-\d+)\)/g)) {
    out[name] = ramp[rung];
  }
  return out;
}

const THEMES = ["dark", "light", "neutral"];
const ACCENTS = ["amber", "indigo", "azure", "violet"];

describe.each(THEMES)("the %s theme", (theme) => {
  // The accent does not change the ground, so the ground-relative checks only
  // need running once per theme.
  const t = tokens(theme, "amber");
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

  it.each(["mint", "rose"])("--%s is legible on the ground", (name) => {
    // Money colours are read as numbers. A mint that works on a dark ground is
    // 1.7:1 on a white one, which is the whole reason light mode restates them.
    expect(contrast(t[name], ground)).toBeGreaterThanOrEqual(4.5);
  });

  it("keeps its hierarchy — each step quieter than the one above", () => {
    // If --faint ever overtakes --muted, de-emphasis stops meaning anything.
    const step = (name) => contrast(t[name], ground);
    expect(step("ink")).toBeGreaterThan(step("ink-2"));
    expect(step("ink-2")).toBeGreaterThan(step("muted"));
    expect(step("muted")).toBeGreaterThan(step("faint"));
  });

  it("separates the raised surface from the ground", () => {
    expect(t["void-lift"]).not.toBe(ground);
  });

  // The point of a ramp rather than a colour: an accent swap cannot quietly
  // drop something below the floor on one theme and not another.
  describe.each(ACCENTS)("with the %s accent", (accent) => {
    const a = tokens(theme, accent);

    it.each(["accent", "accent-hot"])("--%s is legible on the ground", (name) => {
      expect(contrast(a[name], ground)).toBeGreaterThanOrEqual(4.5);
    });

    it("never collides with the money colours", () => {
      // An accent that reads as mint or rose turns an interaction into a claim
      // about money — a button that looks like a loss.
      //
      // This asks for hue separation, not contrast. The first version of this
      // test used the contrast ratio and failed all twelve combinations, which
      // was the test being wrong rather than the palette: contrast measures
      // lightness, and an accent is *supposed* to sit at a similar lightness to
      // the money colours on the same ground. Two colours of equal lightness
      // and opposite hue are not remotely confusable.
      expect(hueGap(a.accent, a.mint)).toBeGreaterThanOrEqual(30);
      expect(hueGap(a.accent, a.rose)).toBeGreaterThanOrEqual(30);
    });
  });
});

describe("the themes are switchable at all", () => {
  it("writes both axes onto the document element", () => {
    const hook = read("hooks/useTheme.js");
    expect(hook).toMatch(/setAttribute\("data-theme"/);
    expect(hook).toMatch(/setAttribute\("data-accent"/);
  });

  it("follows the operating system until somebody chooses", () => {
    const hook = read("hooks/useTheme.js");
    expect(hook).toMatch(/prefers-color-scheme/);
  });

  it("survives storage being unavailable", () => {
    // A private window throws on localStorage access. Losing the whole app to
    // that would be a strange way to go.
    const hook = read("hooks/useTheme.js");
    const reads = hook.match(/localStorage/g) || [];
    const catches = hook.match(/catch/g) || [];
    expect(reads.length).toBeGreaterThan(0);
    expect(catches.length).toBeGreaterThanOrEqual(reads.length);
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
    // Any other file defining --ink or --accent is a second source of truth,
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

  it("the legacy stylesheet no longer paints the root element", () => {
    // Its :root block set a light background, a dark ink and its own font
    // stack, over a design built for warm near-black.
    expect(code("theme-legacy.css")).not.toMatch(/^:root\s*\{/m);
  });

  it("the legacy stylesheet has no near-opaque white surfaces left", () => {
    const whites = code("theme-legacy.css").match(
      /rgba\(\s*25[0-5]\s*,\s*25[0-5]\s*,\s*25[0-5]\s*,\s*(?:0?\.[5-9]\d*|1)\s*\)/g,
    );
    expect(whites).toBeNull();
  });
});

// ------------------------------------------------ the legacy file only shrinks

describe("the legacy stylesheet", () => {
  it("still exists, because twelve pages have not been restyled yet", () => {
    // Honest guard rather than an aspiration. The plan said "delete App.css
    // and nothing changes"; that was wrong — AssistantPage, ManagerPage,
    // AvailabilityPage, SettingsPage and eight more still need it. When the
    // last of them is restyled this test is what gets deleted, and the file
    // with it.
    expect(fs.existsSync(path.join(SRC, "theme-legacy.css"))).toBe(true);
    expect(fs.existsSync(path.join(SRC, "App.css"))).toBe(false);
  });

  it("holds no colour of its own", () => {
    // Every one of the times this file repainted the app, it did it by
    // supplying a colour the theme had not restated.
    //
    // The first version of this check only caught *opaque* rgb — alpha at or
    // above 0.5 — and the whole pre-redesign palette was still in here below
    // that line: a blue glow at .28, another at .20, a purple hero at .14, and
    // nine navy-tinted shadows. They survived the retheme, survived this test,
    // and were on screen the entire time.
    //
    // So the rule is no chromatic value at any alpha. Greyscale is allowed,
    // because a shadow is an absence of light rather than a colour, and it is
    // the one thing that can be stated literally without picking a side in a
    // theme.
    expect(chromaticIn("theme-legacy.css")).toEqual([]);
    expect(code("theme-legacy.css").match(/#[0-9a-fA-F]{3,8}/g)).toBeNull();
  });

  it("carries no colour in any of the other stylesheets either", () => {
    // Same rule, whole tree. theme.css states the palette; every other file
    // mixes from it. A literal anywhere else is a colour that cannot follow a
    // theme, which is how light mode would rot one page at a time.
    const offenders = {};
    for (const file of fs.readdirSync(SRC)) {
      if (!file.endsWith(".css") || file === "theme.css") continue;
      // theme-switch.css is the one exemption: a swatch has to show you the
      // theme you are not currently in, which cannot be mixed from the one you
      // are standing in.
      const literals =
        file === "theme-switch.css" ? [] : code(file).match(/#[0-9a-fA-F]{3,8}/g) || [];
      const chromatic = chromaticIn(file);
      if (literals.length || chromatic.length) offenders[file] = [...literals, ...chromatic];
    }
    expect(offenders).toEqual({});
  });

  it("defines no custom properties", () => {
    // It defined --text, --muted, --line, --surface and --shadow, all of which
    // theme.css owns. A second definition is a fight waiting for an import
    // order to change.
    expect(code("theme-legacy.css")).not.toMatch(/^\s*--[\w-]+\s*:/m);
  });

  it("is loaded before the design language, so the theme wins every tie", () => {
    const app = read("App.jsx");
    expect(app.indexOf("theme-legacy.css")).toBeLessThan(app.indexOf("theme.css"));
  });
});
