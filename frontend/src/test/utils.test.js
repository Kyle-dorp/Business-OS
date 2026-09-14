/**
 * Week arithmetic.
 *
 * Every scheduling screen in the product is addressed by a week start, and a
 * week start is computed from a Date. Two classes of bug live here and neither
 * is visible by reading:
 *
 *   - Sunday. In JavaScript getDay() returns 0 for Sunday, so the naive
 *     "go back to Monday" lands a week in the future on exactly one day in
 *     seven — and the person who notices is the manager building next week's
 *     rota on a Sunday night, which is when rotas get built.
 *
 *   - Timezones. new Date("2026-09-14") parses as UTC midnight, which is the
 *     13th in any negative offset. Building the date from its parts is what
 *     stops a whole product silently disagreeing about what day it is.
 */

import { describe, expect, it, vi } from "vitest";

import {
  DAYS,
  DAY_NAMES,
  formatClock,
  formatRange,
  formatRole,
  fromIsoDate,
  mondayOf,
  shiftWeek,
  statusLabel,
  toIsoDate,
  weekDates,
} from "../utils.js";

// ------------------------------------------------------------- iso round trip

describe("dates as strings", () => {
  it("formats a date as YYYY-MM-DD", () => {
    expect(toIsoDate(new Date(2026, 8, 14))).toBe("2026-09-14");
  });

  it("pads single-digit months and days", () => {
    expect(toIsoDate(new Date(2026, 0, 5))).toBe("2026-01-05");
  });

  it("reads a date back as the same local day", () => {
    // The timezone trap. Parsed as UTC this is the 13th west of Greenwich.
    const parsed = fromIsoDate("2026-09-14");
    expect(parsed.getFullYear()).toBe(2026);
    expect(parsed.getMonth()).toBe(8);
    expect(parsed.getDate()).toBe(14);
  });

  it("round trips", () => {
    for (const iso of ["2026-01-01", "2026-02-28", "2026-12-31", "2024-02-29"]) {
      expect(toIsoDate(fromIsoDate(iso))).toBe(iso);
    }
  });
});

// ---------------------------------------------------------------- mondayOf

describe("finding the start of the week", () => {
  it("a Monday is its own week start", () => {
    expect(toIsoDate(mondayOf(new Date(2026, 8, 14)))).toBe("2026-09-14");
  });

  it("mid-week looks backwards", () => {
    expect(toIsoDate(mondayOf(new Date(2026, 8, 17)))).toBe("2026-09-14");
  });

  it("Sunday belongs to the week that is ending, not the one starting", () => {
    // The bug this exists for. 2026-09-20 is a Sunday; its week began on the
    // 14th. Getting this wrong sends a manager to next week's blank rota on
    // the night they sit down to build it.
    expect(toIsoDate(mondayOf(new Date(2026, 8, 20)))).toBe("2026-09-14");
  });

  it("works on every day of one week", () => {
    const week = [14, 15, 16, 17, 18, 19, 20].map(
      (day) => toIsoDate(mondayOf(new Date(2026, 8, day))),
    );
    expect(new Set(week)).toEqual(new Set(["2026-09-14"]));
  });

  it("strips the time so two calls on one day are equal", () => {
    const morning = mondayOf(new Date(2026, 8, 17, 8, 30));
    const evening = mondayOf(new Date(2026, 8, 17, 23, 59));
    expect(morning.getTime()).toBe(evening.getTime());
    expect(morning.getHours()).toBe(0);
  });

  it("does not modify the date it was given", () => {
    const original = new Date(2026, 8, 17, 12, 0);
    const before = original.getTime();
    mondayOf(original);
    expect(original.getTime()).toBe(before);
  });
});

// --------------------------------------------------------------- shiftWeek

describe("paging between weeks", () => {
  it("goes forward a week", () => {
    expect(shiftWeek("2026-09-14", 1)).toBe("2026-09-21");
  });

  it("goes back a week", () => {
    expect(shiftWeek("2026-09-14", -1)).toBe("2026-09-07");
  });

  it("crosses a month boundary", () => {
    expect(shiftWeek("2026-09-28", 1)).toBe("2026-10-05");
  });

  it("crosses a year boundary", () => {
    expect(shiftWeek("2026-12-28", 1)).toBe("2027-01-04");
  });

  it("crosses a leap day", () => {
    expect(shiftWeek("2024-02-26", 1)).toBe("2024-03-04");
  });

  it("always lands on the same weekday", () => {
    let week = "2026-09-14";
    for (let i = 0; i < 60; i += 1) {
      week = shiftWeek(week, 1);
      expect(fromIsoDate(week).getDay()).toBe(1);
    }
  });

  it("paging forward then back returns to where it started", () => {
    expect(shiftWeek(shiftWeek("2026-03-23", 1), -1)).toBe("2026-03-23");
  });
});

// --------------------------------------------------------------- weekDates

describe("the days of a week", () => {
  it("is seven consecutive days from the start", () => {
    expect(weekDates("2026-09-14")).toEqual([
      "2026-09-14", "2026-09-15", "2026-09-16", "2026-09-17",
      "2026-09-18", "2026-09-19", "2026-09-20",
    ]);
  });

  it("crosses a month end", () => {
    const days = weekDates("2026-09-28");
    expect(days[0]).toBe("2026-09-28");
    expect(days[6]).toBe("2026-10-04");
  });

  it("lines up with the day labels", () => {
    // The rota grid renders DAYS as column headings against these dates. If
    // the lengths ever diverge the whole grid is off by one.
    expect(weekDates("2026-09-14")).toHaveLength(DAYS.length);
    expect(DAYS).toHaveLength(7);
    expect(DAY_NAMES).toHaveLength(7);
    expect(DAY_NAMES[0]).toBe("Monday");
    expect(DAY_NAMES[6]).toBe("Sunday");
  });
});

// -------------------------------------------------------------- the clock

describe("showing a time", () => {
  it("renders morning and afternoon", () => {
    expect(formatClock("09:30")).toBe("9:30 AM");
    expect(formatClock("14:05")).toBe("2:05 PM");
  });

  it("midnight is 12 AM, not 0 AM", () => {
    expect(formatClock("00:00")).toBe("12:00 AM");
  });

  it("noon is 12 PM, not 0 PM", () => {
    // The classic pair. `hour % 12` is 0 at both ends, and whichever one gets
    // missed is wrong by twelve hours on a rota.
    expect(formatClock("12:00")).toBe("12:00 PM");
  });

  it("one minute before midnight is still PM", () => {
    expect(formatClock("23:59")).toBe("11:59 PM");
  });

  it("an absent time reads as any time rather than blank", () => {
    expect(formatClock("")).toBe("Any time");
    expect(formatClock(null)).toBe("Any time");
  });

  it("a range with neither end is a full day", () => {
    expect(formatRange("", "")).toBe("Full day");
    expect(formatRange(null, null)).toBe("Full day");
  });

  it("a range renders both ends", () => {
    expect(formatRange("09:00", "17:00")).toBe("9:00 AM – 5:00 PM");
  });
});

// -------------------------------------------------------------- vocabulary

describe("words shown to people", () => {
  it("spells out roles", () => {
    expect(formatRole("shift_lead")).toBe("Shift Lead");
    expect(formatRole("gm")).toBe("GM");
    expect(formatRole("employee")).toBe("Employee");
  });

  it("falls back to Employee rather than showing a raw key", () => {
    expect(formatRole("something_new")).toBe("Employee");
    expect(formatRole(undefined)).toBe("Employee");
  });

  it("spells out schedule status", () => {
    expect(statusLabel("needs_review")).toBe("Needs Review");
    expect(statusLabel("published")).toBe("Published");
    expect(statusLabel("draft")).toBe("Draft");
  });

  it("an unknown status reads as Draft rather than as itself", () => {
    // Anything not yet published is safe to call a draft; showing the raw
    // enum key to an operator is not.
    expect(statusLabel("weird")).toBe("Draft");
  });
});
