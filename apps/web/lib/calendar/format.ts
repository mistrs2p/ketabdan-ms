/**
 * Calendar-aware date/time formatting.
 *
 * One formatting entry point per presentation shape, each taking the
 * viewer's chosen calendar system alongside the locale. The system is
 * applied through Intl's calendar extension (-u-ca-persian /
 * -u-ca-gregory), so month names, day numbers and digits localize
 * automatically in every locale — no hand-maintained name tables.
 *
 * Pure presentation: every function takes an already-parsed Date (or
 * ISO string) and returns a label. Stored values are never rewritten;
 * switching the system re-labels the same instants.
 */

import type { CalendarSystem } from "./types";

/** Locale string with the calendar extension applied. */
export function calendarLocale(
  locale: string,
  system: CalendarSystem,
): string {
  try {
    // Intl.Locale accepts "fa", "en", or an already-tagged string and
    // applies/replaces the calendar option on top of it.
    return new Intl.Locale(locale, {
      calendar: system === "persian" ? "persian" : "gregory",
    }).toString();
  } catch {
    // Invalid locale string: fall back to the raw value so formatting
    // degrades to the runtime default instead of crashing.
    return locale;
  }
}

/** A formatter for the given options in the given calendar system. */
export function calendarFormatter(
  locale: string,
  system: CalendarSystem,
  options: Intl.DateTimeFormatOptions,
): Intl.DateTimeFormat {
  return new Intl.DateTimeFormat(calendarLocale(locale, system), options);
}

/**
 * Format a timezone-aware ISO-8601 instant for display (medium date +
 * short time). The wire value stays the backend's string untouched;
 * unparseable values show the raw string, never crash.
 */
export function formatDateTime(
  iso: string,
  locale: string,
  system: CalendarSystem,
): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso; // unparseable value: show the raw string, never crash
  }
  return calendarFormatter(locale, system, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

/**
 * Format a UTC-anchored date-only value (weekMath arithmetic) — always
 * with timeZone "UTC" so the displayed day matches the arithmetic.
 */
export function formatUtcDate(
  date: Date,
  locale: string,
  system: CalendarSystem,
  options: Intl.DateTimeFormatOptions,
): string {
  return calendarFormatter(locale, system, {
    ...options,
    timeZone: "UTC",
  }).format(date);
}
