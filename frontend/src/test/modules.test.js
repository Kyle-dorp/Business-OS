/**
 * Every module parses and loads.
 *
 * This exists because a syntax error was committed and pushed.
 *
 * An import was inserted programmatically "after the last line starting with
 * `import `", and in ManagerPage.jsx that line was `import {` — the opening of
 * a multi-line statement. The new import landed between the brace and its
 * contents:
 *
 *     import {
 *     import { Loading } from "../components/States";
 *       DAYS,
 *
 * The whole test suite passed. Every check that touches pages reads them as
 * *text* — regexes over source looking for class names and token references —
 * and text does not have to parse. `tsc --noEmit` passed too, because it does
 * not typecheck .jsx here. The page was a white screen with a Babel stack
 * trace in the console, and nothing in the repository disagreed.
 *
 * So: something has to actually load them. This is the cheapest possible
 * version — import every module and assert it produced something. It runs in
 * about a second and it catches the entire class.
 */

import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const SRC = path.resolve(__dirname, "..");

function modules(dir = SRC, found = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name !== "test") modules(full, found);
    } else if (/\.(jsx|tsx)$/.test(entry.name) || /^(api|utils|icons)\.(js|jsx)$/.test(entry.name)) {
      found.push(full);
    }
  }
  return found;
}

/**
 * The entry point is the one module that cannot be imported for inspection:
 * importing it *is* starting the app, and createRoot needs a #root that does
 * not exist in a test environment. Its job is four lines long, and the build
 * fails loudly if it breaks.
 */
const ENTRY = new Set(["main.tsx", "main.jsx"]);

// split/join rather than a regex: this file has been rewritten by script
// twice and both times the backslash in the pattern was eaten on the way in,
// leaving an unterminated regex. There is nothing to escape here.
const files = modules()
  .map((f) => path.relative(SRC, f).split(path.sep).join("/"))
  .filter((f) => !ENTRY.has(f));

describe("every module in the tree parses and loads", () => {
  it("found the modules to check", () => {
    // A smoke test that smoke-tests nothing is the thing it is guarding
    // against, one level up.
    expect(files.length).toBeGreaterThan(20);
    expect(files).toContain("pages/ManagerPage.jsx");
    expect(files).toContain("App.jsx");
  });

  it.each(files)("%s", async (rel) => {
    // A syntax error throws here. A bad import path throws here. A module that
    // runs something at import time and blows up throws here.
    const loaded = await import(/* @vite-ignore */ `../${rel}`);
    expect(loaded).toBeTypeOf("object");
  });
});
