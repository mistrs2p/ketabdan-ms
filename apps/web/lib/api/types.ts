/**
 * Backend contract types (docs/06-BACKEND-API.md).
 *
 * These mirror the CURRENT Pydantic response/request schemas exactly —
 * field names are the backend's, unchanged. UUIDs are strings on the
 * wire; `planned_at` is an ISO-8601 timezone-aware instant string, kept
 * as a string for API transport and parsed where a UI needs a Date.
 *
 * No field is invented and none is added: OpenAPI → TypeScript code
 * generation stays deferred (docs/01 §7 TBD T3), so these types are
 * hand-maintained against docs/06 until that decision lands.
 */

/** `GET /api/health` response body. */
export interface HealthStatus {
  status: string;
}

/** RoleRead — a permanent organizational role (`GET /api/roles`). */
export interface RoleRead {
  id: string;
  code: string;
  name: string;
}

/** PersonRead — a branch member (`GET /api/persons`, `POST /api/persons`). */
export interface PersonRead {
  id: string;
  name: string;
  phone: string | null;
  active: boolean;
  roles: RoleRead[];
}

/** PersonCreate — request body for `POST /api/persons` (docs/06 §4a). */
export interface PersonCreate {
  name: string;
  phone?: string | null;
  active?: boolean;
  /** Stable machine codes of the seeded role reference data. */
  roles?: string[];
}

/** EventRead — an event (docs/06 §4c). */
export interface EventRead {
  id: string;
  title: string;
  type: string;
  /** ISO-8601 timezone-aware instant, e.g. "2026-09-19T17:00:00+03:30". */
  planned_at: string;
  status: string;
}

/** EventCreate — request body for `POST /api/events` (docs/06 §4c). */
export interface EventCreate {
  title: string;
  type: string;
  /**
   * ISO-8601 string with a timezone offset — the backend rejects naive
   * values (422). The caller is responsible for the offset.
   */
  planned_at: string;
}

/** EventResponsibilityRead — reference data embedded in assignments. */
export interface EventResponsibilityRead {
  id: string;
  code: string;
  name: string;
  active: boolean;
}

/** EventAssignmentRead — an assignment (docs/06 §4d). */
export interface EventAssignmentRead {
  id: string;
  event_id: string;
  person_id: string;
  responsibility: EventResponsibilityRead;
  /** PROVISIONAL backend placeholder set (TBD-D10/A6) — carried, not interpreted. */
  approval_status: string;
}

/** EventAssignmentCreate — request body for `POST /api/event-assignments`. */
export interface EventAssignmentCreate {
  event_id: string;
  person_id: string;
  /** Stable machine code of the seeded responsibility reference data. */
  responsibility: string;
}

/**
 * The `detail` value of a FastAPI error body — either a plain
 * human-readable string (domain errors, 404/405) or the structured
 * validation issue list (422). See docs/06 §4b.
 */
export type ApiErrorDetail = string | ApiValidationIssue[];

export interface ApiValidationIssue {
  type: string;
  loc: (string | number)[];
  msg: string;
}
