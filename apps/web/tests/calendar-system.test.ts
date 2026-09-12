/**
 * Calendar-system tests: the preference types/defaults, the storage
 * persistence (SSR guard included), and the calendar-aware Intl
 * formatting that drives every date label in the app.
 */

import {
  defaultCalendarSystemForLocale,
  isCalendarSystem,
} from "@/lib/calendar/types";
import {
  readCalendarSystem,
  saveCalendarSystem,
} from "@/lib/calendar/storage";
import { formatDateTime, formatUtcDate } from "@/lib/calendar/format";

const KEY = "ketabdaneh.pref.calendar";

beforeEach(() => {
  window.localStorage.clear();
});

describe("defaultCalendarSystemForLocale", () => {
  it("defaults fa to the Persian (Jalali) calendar", () => {
    expect(defaultCalendarSystemForLocale("fa")).toBe("persian");
  });

  it("defaults non-fa locales to Gregorian", () => {
    expect(defaultCalendarSystemForLocale("en")).toBe("gregory");
  });
});

describe("isCalendarSystem", () => {
  it("accepts the two known systems", () => {
    expect(isCalendarSystem("persian")).toBe(true);
    expect(isCalendarSystem("gregory")).toBe(true);
  });

  it("rejects anything else (including the fa runtime default)", () => {
    expect(isCalendarSystem("islamic")).toBe(false);
    expect(isCalendarSystem("persian-alt")).toBe(false);
    expect(isCalendarSystem(null)).toBe(false);
  });
});

describe("calendar storage", () => {
  it("persists and reads back the choice", () => {
    saveCalendarSystem("persian");
    expect(readCalendarSystem()).toBe("persian");
  });

  it("returns null when nothing is saved", () => {
    expect(readCalendarSystem()).toBeNull();
  });

  it("treats an invalid stored value as no preference", () => {
    window.localStorage.setItem(KEY, "hijri");
    expect(readCalendarSystem()).toBeNull();
  });
});

describe("formatDateTime", () => {
  it("labels the same instant in the chosen calendar system", () => {
    const iso = "2026-03-21T10:30:00+00:00";
    // 2026-03-21 is 1405-01-01 Jalali — the Persian year rolls over.
    const persian = formatDateTime(iso, "fa", "persian");
    const gregorian = formatDateTime(iso, "fa", "gregory");
    expect(persian).toContain("۱۴۰۵");
    expect(gregorian).not.toContain("۱۴۰۵");
    expect(gregorian).toContain("۲۰۲۶");
  });

  it("returns the raw string for unparseable values, never crashing", () => {
    expect(formatDateTime("not-a-date", "fa", "persian")).toBe("not-a-date");
  });
});

describe("formatUtcDate", () => {
  it("formats the UTC-anchored day, not the local one", () => {
    // 2026-09-12T23:30 UTC is already Sep 13 in Tehran (+03:30).
    const date = new Date(Date.UTC(2026, 8, 12, 23, 30));
    const label = formatUtcDate(date, "en", "gregory", {
      dateStyle: "medium",
    });
    expect(label).toContain("Sep 12");
  });
});
