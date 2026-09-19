/**
 * Type is a scale too.
 *
 * The stylesheets carried sixty-two distinct font sizes and twelve distinct
 * font weights. The weights are the tell: 750, 780, 820, 850 and 950 are not
 * choices, they are guesses, and no two of them are distinguishable from each
 * other on screen.
 *
 * One declaration was 9px, which is not a size so much as a rumour.
 *
 * And `body` was 300. A light weight at small sizes erodes effective contrast
 * whatever the ratio says, so every measurement in the palette table was
 * flattering the real thing.
 *
 * Ten rungs and five weights now. The dense end of the ladder is spaced finely
 * because that is where most of an interface lives; the display end is spaced
 * widely because a heading two pixels bigger is not a different heading.
 */

import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const SRC = path.resolve(__dirname, "..");
const stylesheets = fs.readdirSync(SRC).filter((f) => f.endsWith(".css"));
const code = (f) =>
  fs.readFileSync(path.join(SRC, f), "utf8").replace(/\/\*[\s\S]*?\*\//g, "");

const RUNGS = [
  "--text-xs",
  "--text-sm",
  "--text-base",
  "--text-body",
  "--text-lg",
  "--text-xl",
  "--text-2xl",
  "--text-3xl",
  "--text-4xl",
  "--text-5xl",
];

// 400 regular, 500 medium, 600 semibold, 700 bold, 800 for display. Anything
// between those is a value somebody typed rather than chose.
const WEIGHTS = new Set(["400", "500", "600", "700", "800"]);

describe("the type ladder", () => {
  it("is defined", () => {
    const theme = fs.readFileSync(path.join(SRC, "theme.css"), "utf8");
    for (const rung of RUNGS) expect(theme).toContain(`${rung}:`);
  });

  it("has stylesheets to check", () => {
    expect(stylesheets.length).toBeGreaterThan(5);
  });

  it.each(stylesheets)("%s sizes everything from the ladder", (file) => {
    const literals = [...code(file).matchAll(/font-size\s*:\s*([\d.]+(?:px|rem|em))/g)].map(
      (m) => m[1],
    );
    expect(literals).toEqual([]);
  });

  it.each(stylesheets)("%s uses only the five weights", (file) => {
    const stray = [...code(file).matchAll(/font-weight\s*:\s*(\d{3})/g)]
      .map((m) => m[1])
      .filter((w) => !WEIGHTS.has(w));
    expect(stray).toEqual([]);
  });
});

describe("the body is readable", () => {
  const theme = fs.readFileSync(path.join(SRC, "theme.css"), "utf8");

  it("is not set in a light weight", () => {
    // 300 at fifteen or sixteen pixels is thin enough that the contrast ratio
    // stops describing what anybody actually sees.
    const body = theme.slice(theme.indexOf("\nbody {"));
    const rule = body.slice(0, body.indexOf("}"));
    const weight = rule.match(/font-weight\s*:\s*(\d{3})/);
    expect(weight).not.toBeNull();
    expect(Number(weight[1])).toBeGreaterThanOrEqual(400);
  });

  it("puts the prose floor at 16px", () => {
    // --text-body is the name other rules reach for when the thing is read
    // rather than scanned. It has to actually be 16px or the name lies.
    expect(theme).toMatch(/--text-body:\s*1rem;/);
  });

  it("has a smallest rung that is still a size", () => {
    const xs = theme.match(/--text-xs:\s*([\d.]+)rem/);
    expect(xs).not.toBeNull();
    expect(Number(xs[1]) * 16).toBeGreaterThanOrEqual(11);
  });
});

describe("the shared gutter", () => {
  it("is defined once", () => {
    const theme = fs.readFileSync(path.join(SRC, "theme.css"), "utf8");
    expect(theme).toMatch(/--gutter:\s*clamp\(/);
  });

  it("is what the one public-facing screen uses", () => {
    // PublicBookingPage is the only screen a stranger reaches without an
    // account. The app's own .page keeps a tighter clamp on purpose: it sits
    // inside a 1180px column, where a 72px gutter is margin nobody asked for.
    expect(code("theme-booking.css")).toMatch(/\.pb-screen[\s\S]*?var\(--gutter\)/);
  });
});
