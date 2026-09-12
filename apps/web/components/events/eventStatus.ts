import { formatDateTime, type CalendarSystem } from "@/lib/calendar";

// Known event statuses (backend D-002 set). The map only covers
// presentation — an unknown future status falls back to the raw backend
// value, never crashing and never being interpreted (docs/06 §4c:
// display only, transitions are TBD-D7 and out of scope).
export const KNOWN_EVENT_STATUSES = [
  "DRAFT",
  "SCHEDULED",
  "IN_PROGRESS",
  "COMPLETED",
  "CANCELLED",
] as const;

// Status label for the events UI: localized text for the known D-002
// values, the raw backend value for anything else (displayed safely,
// preserving the server's value — the UI never rewrites status).
export function eventStatusLabel(
  status: string,
  labels: Record<string, string>,
): string {
  return labels[status] ?? status;
}

// Format a timezone-aware ISO-8601 instant for presentation only. The
// wire value stays the backend's string untouched; this never changes
// the instant or drops the offset. The calendar system (Jalali vs
// Gregorian) is the viewer's display choice — applied via Intl's
// calendar extension, so month names, day numbers and digits localize
// automatically. Unparseable values show the raw string, never crash.
export function formatEventDateTime(
  iso: string,
  locale: string,
  system: CalendarSystem,
): string {
  return formatDateTime(iso, locale, system);
}
