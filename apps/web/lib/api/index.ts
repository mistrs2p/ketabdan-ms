/**
 * Frontend API layer — the single typed client for the FastAPI backend
 * (docs/01 §4). Re-exported surface for consumers:
 *
 *   import { getPersons, ApiError } from "@/lib/api";
 *
 * Modules are pure API communication: no React, no state, no UI, no
 * translation strings, no business decisions (those stay backend-side,
 * docs/01 §3.1).
 */

export { apiBaseUrl, buildApiUrl, apiGet, apiPost } from "./client";
export {
  ApiError,
  apiErrorMessage,
  kindForStatus,
  validationIssues,
  type ApiErrorKind,
  type ValidationIssue,
} from "./errors";
export { getHealth } from "./health";
export { getRoles } from "./roles";
export { getPersons, createPerson } from "./persons";
export { getEvents, getEvent, createEvent } from "./events";
export {
  getEventAssignments,
  getEventAssignment,
  createEventAssignment,
} from "./eventAssignments";
export type {
  HealthStatus,
  RoleRead,
  PersonRead,
  PersonCreate,
  EventRead,
  EventCreate,
  EventResponsibilityRead,
  EventAssignmentRead,
  EventAssignmentCreate,
  ApiErrorDetail,
  ApiValidationIssue,
} from "./types";
