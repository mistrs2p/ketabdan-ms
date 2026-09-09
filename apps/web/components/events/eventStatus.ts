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
// the instant or drops the offset. Uses the runtime locale so fa sees
// Persian digits/month names and en sees Western ones — no Jalali
// conversion (explicitly out of scope), no date library.
export function formatEventDateTime(
  iso: string,
  locale: string,
): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso; // unparseable value: show the raw string, never crash
  }
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}
