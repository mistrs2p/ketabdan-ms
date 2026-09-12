/**
 * Calendar-system preference types (Jalali vs Gregorian display).
 *
 * The backend stores every instant as timezone-aware ISO-8601
 * (docs/06 §4c); the calendar system is purely a *presentation*
 * choice made by the viewer. Nothing here touches stored data —
 * switching systems re-labels the same instants, never converts or
 * rewrites them.
 */

/** The two supported display calendar systems. */
export type CalendarSystem = "persian" | "gregory";

export const CALENDAR_SYSTEMS: readonly CalendarSystem[] = [
  "persian",
  "gregory",
];

export function isCalendarSystem(value: unknown): value is CalendarSystem {
  return value === "persian" || value === "gregory";
}

/**
 * The default system for a locale when the user has not chosen one:
 * Persian for `fa`, Gregorian otherwise. A deliberate, documented
 * default — the user can always switch, and the choice persists.
 */
export function defaultCalendarSystemForLocale(locale: string): CalendarSystem {
  return locale.toLowerCase().startsWith("fa") ? "persian" : "gregory";
}
