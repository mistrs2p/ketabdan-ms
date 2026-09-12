// Month-grid math for the datetime picker, in the viewer's display
// calendar system. All Dates here are LOCAL midnights (wall-clock
// dates as the user perceives them); the display system only decides
// how a day is *labelled and grouped into months* — the produced Date
// is always the real Gregorian instant, so what the form submits is
// unchanged by the system choice.
//
// Persian months are converted exactly via jalaali-js (Borkowski
// algorithm); everything else is plain Date arithmetic.

import {
  jalaaliMonthLength,
  jalaaliToDateObject,
  toJalaali,
} from "jalaali-js";
import type { CalendarSystem } from "@/lib/calendar";

/** A month in the display calendar (system-dependent numbering). */
export interface CalendarMonth {
  year: number;
  month: number; // 1-12 in the display system
}

/** Day-of-month parts of a local Date in the display system. */
export function dayPartsOf(
  date: Date,
  system: CalendarSystem,
): { year: number; month: number; day: number } {
  if (system === "persian") {
    const { jy, jm, jd } = toJalaali(
      date.getFullYear(),
      date.getMonth() + 1,
      date.getDate(),
    );
    return { year: jy, month: jm, day: jd };
  }
  return {
    year: date.getFullYear(),
    month: date.getMonth() + 1,
    day: date.getDate(),
  };
}

/** Number of days in a display-calendar month. */
export function monthLength(
  month: CalendarMonth,
  system: CalendarSystem,
): number {
  if (system === "persian") {
    return jalaaliMonthLength(month.year, month.month);
  }
  // Gregorian: day 0 of the next month is the last day of this one.
  return new Date(month.year, month.month, 0).getDate();
}

/** Local midnight Date for a display-calendar day. */
export function dateOf(
  month: CalendarMonth,
  day: number,
  system: CalendarSystem,
): Date {
  if (system === "persian") {
    return jalaaliToDateObject(month.year, month.month, day);
  }
  return new Date(month.year, month.month - 1, day);
}

/** Shift a display-calendar month by whole months (negative allowed). */
export function addMonths(
  month: CalendarMonth,
  delta: number,
): CalendarMonth {
  // Both systems number months 1-12 with the year rolling over — the
  // arithmetic is identical; only the labels differ.
  const zeroBased = month.year * 12 + (month.month - 1) + delta;
  return {
    year: Math.floor(zeroBased / 12),
    month: (zeroBased % 12) + 1,
  };
}

export interface DayCell {
  /** Local midnight of the day (the real instant, Gregorian). */
  date: Date;
  /** Day-of-month number in the display system. */
  day: number;
  /** Whether the cell belongs to the viewed month. */
  inMonth: boolean;
}

/**
 * The 42 cells (six full weeks) of a month view, starting at the
 * week-start weekday. Leading/trailing cells belong to the adjacent
 * months — rendered muted but selectable, like most pickers.
 */
export function buildMonthGrid(
  view: CalendarMonth,
  weekStartDow: number,
  system: CalendarSystem,
): DayCell[] {
  const first = dateOf(view, 1, system);
  const leading = (first.getDay() - weekStartDow + 7) % 7;
  const start = new Date(first);
  start.setDate(start.getDate() - leading);
  return Array.from({ length: 42 }, (_, i) => {
    const date = new Date(start);
    date.setDate(start.getDate() + i);
    const parts = dayPartsOf(date, system);
    return {
      date,
      day: parts.day,
      inMonth: parts.year === view.year && parts.month === view.month,
    };
  });
}

/** True when two local Dates are the same calendar day. */
export function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

/**
 * Combine a local date with an "HH:mm" string into one Date. Empty or
 * malformed time yields null (an incomplete selection is not a value).
 */
export function combineDateAndTime(date: Date, hhmm: string): Date | null {
  const match = /^(\d{1,2}):(\d{2})$/.exec(hhmm);
  if (!match) return null;
  const hours = Number(match[1]);
  const minutes = Number(match[2]);
  if (hours > 23 || minutes > 59) return null;
  return new Date(
    date.getFullYear(),
    date.getMonth(),
    date.getDate(),
    hours,
    minutes,
  );
}

/** "HH:mm" (24h, input type=time format) of a Date's local time. */
export function timeStringOf(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
