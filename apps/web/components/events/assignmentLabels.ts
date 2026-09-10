// Known event responsibility codes — the six seeded by D-004
// (migration 0003, apps/api/alembic/versions/0003_…). The backend
// deliberately exposes NO /api/event-responsibilities endpoint yet
// (runtime creation is still TBD-D9, docs/06 §4d), so the selector
// options are this documented constant rather than a fetched list.
// Codes are stable machine keys; labels are localized in the UI.
//
// Responsibilities are NOT organizational roles (docs/06 §4d domain
// shape) — do not reuse the roles reference data here.
export const KNOWN_RESPONSIBILITY_CODES = [
  "pre_introduction",
  "welcome_reception",
  "technique_execution",
  "persuasion",
  "registration",
  "follow_up",
] as const;

// Human-readable label for a responsibility. The localized label wins
// for the six seeded codes; anything else falls back to the backend's
// reference-data `name` (assignments embed the full responsibility
// object), and finally to the raw code — an unknown code never crashes
// and never rewrites the server's value.
export function responsibilityLabel(
  code: string,
  labels: Record<string, string>,
  backendName?: string,
): string {
  return labels[code] ?? backendName ?? code;
}

// Known assignment approval statuses (PROVISIONAL backend set,
// TBD-D10/A6 — carried, never interpreted or transitioned by the UI).
export const KNOWN_APPROVAL_STATUSES = ["PENDING", "APPROVED"] as const;

// Same fallback pattern as eventStatusLabel: localized for the known
// values, raw backend value for anything else.
export function approvalStatusLabel(
  status: string,
  labels: Record<string, string>,
): string {
  return labels[status] ?? status;
}
