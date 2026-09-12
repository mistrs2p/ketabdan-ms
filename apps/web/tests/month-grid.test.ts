/**
 * Month-grid math tests for the datetime picker: Jalali⇄Gregorian day
 * parts, month lengths, month arithmetic, and the 42-cell grid —
 * all as pure functions over local-midnight Dates.
 */

import {
  addMonths,
  buildMonthGrid,
  combineDateAndTime,
  dateOf,
  dayPartsOf,
  isSameDay,
  monthLength,
  timeStringOf,
} from "@/components/datetime/monthGrid";

describe("monthGrid dayPartsOf", () => {
  it("converts a Gregorian date to Jalali parts", () => {
    // 2026-03-21 is Farvardin 1st, 1405.
    const parts = dayPartsOf(new Date(2026, 2, 21), "persian");
    expect(parts).toEqual({ year: 1405, month: 1, day: 1 });
  });

  it("returns Gregorian parts unchanged in the gregory system", () => {
    const parts = dayPartsOf(new Date(2026, 2, 21), "gregory");
    expect(parts).toEqual({ year: 2026, month: 3, day: 21 });
  });
});

describe("monthGrid monthLength", () => {
  it("gives Persian months 31 days except the last six", () => {
    expect(monthLength({ year: 1405, month: 1 }, "persian")).toBe(31);
    expect(monthLength({ year: 1405, month: 7 }, "persian")).toBe(30);
    expect(monthLength({ year: 1405, month: 12 }, "persian")).toBe(29); // 1405 is not a leap year
  });

  it("gives Gregorian months their conventional lengths", () => {
    expect(monthLength({ year: 2026, month: 2 }, "gregory")).toBe(28);
    expect(monthLength({ year: 2028, month: 2 }, "gregory")).toBe(29);
  });
});

describe("monthGrid dateOf / addMonths round-trip", () => {
  it("builds the real instant from Jalali parts", () => {
    const date = dateOf({ year: 1405, month: 1 }, 1, "persian");
    expect([date.getFullYear(), date.getMonth() + 1, date.getDate()]).toEqual(
      [2026, 3, 21],
    );
  });

  it("rolls months over the year boundary in both systems", () => {
    expect(addMonths({ year: 1405, month: 12 }, 1)).toEqual({
      year: 1406,
      month: 1,
    });
    expect(addMonths({ year: 2026, month: 1 }, -1)).toEqual({
      year: 2025,
      month: 12,
    });
  });
});

describe("monthGrid buildMonthGrid", () => {
  it("produces 42 cells starting at the week-start weekday", () => {
    // Farvardin 1405 starts on Gregorian 2026-03-21, a Saturday.
    // With a Saturday week start (fa), cell 0 is the 1st itself.
    const cells = buildMonthGrid({ year: 1405, month: 1 }, 6, "persian");
    expect(cells).toHaveLength(42);
    expect(cells[0].inMonth).toBe(true);
    expect(cells[0].day).toBe(1);
    // 31 days in the month, so 31 in-month cells.
    expect(cells.filter((c) => c.inMonth)).toHaveLength(31);
    // Every cell is a real local midnight Date.
    for (const cell of cells) {
      expect(cell.date.getHours()).toBe(0);
      expect(cell.date.getMinutes()).toBe(0);
    }
  });

  it("aligns on the same real days regardless of the system", () => {
    const persian = buildMonthGrid({ year: 1405, month: 1 }, 6, "persian");
    const gregorian = buildMonthGrid({ year: 2026, month: 3 }, 0, "gregory");
    expect(persian[0].date.getTime()).toBe(gregorian.find(
      (c) => c.day === 21,
    )!.date.getTime());
  });
});

describe("combineDateAndTime / timeStringOf / isSameDay", () => {
  it("combines a local date with HH:mm", () => {
    const combined = combineDateAndTime(new Date(2026, 2, 21), "17:05");
    expect(
      combined !== null &&
        combined.getFullYear() === 2026 &&
        combined.getMonth() === 2 &&
        combined.getDate() === 21 &&
        combined.getHours() === 17 &&
        combined.getMinutes() === 5,
    ).toBe(true);
  });

  it("rejects malformed or out-of-range times", () => {
    expect(combineDateAndTime(new Date(2026, 2, 21), "")).toBeNull();
    expect(combineDateAndTime(new Date(2026, 2, 21), "25:00")).toBeNull();
    expect(combineDateAndTime(new Date(2026, 2, 21), "12:99")).toBeNull();
  });

  it("formats and compares local times and days", () => {
    expect(timeStringOf(new Date(2026, 2, 21, 9, 5))).toBe("09:05");
    expect(isSameDay(new Date(2026, 2, 21, 23, 0), new Date(2026, 2, 21, 1, 0))).toBe(
      true,
    );
    expect(isSameDay(new Date(2026, 2, 21), new Date(2026, 2, 22))).toBe(false);
  });
});
