/**
 * Calendar preference layer (lib/calendar).
 *
 * Public surface: the provider/hook for the viewer's chosen calendar
 * system (Jalali vs Gregorian display), the storage behind it, and the
 * calendar-aware Intl formatting helpers. See types.ts for the
 * presentation-only contract.
 */

export { CalendarProvider, useCalendarSystem } from "./context";
export {
  calendarFormatter,
  calendarLocale,
  formatDateTime,
  formatUtcDate,
} from "./format";
export {
  readCalendarSystem,
  saveCalendarSystem,
} from "./storage";
export {
  CALENDAR_SYSTEMS,
  defaultCalendarSystemForLocale,
  isCalendarSystem,
  type CalendarSystem,
} from "./types";
