/**
 * Frontend API error abstraction (docs/06 §4b error policy).
 *
 * The backend's error body is always FastAPI-native `{"detail": ...}`
 * where `detail` is either a plain string (domain errors, not-found,
 * unknown path, method) or a structured validation list (422). This
 * class preserves both plus the HTTP status so UI layers can branch on
 * the four cases the error policy distinguishes:
 *
 *   - validation error (422)
 *   - not found (404)
 *   - generic API/server failure (anything else, or network error)
 *
 * Success is simply the absence of a thrown ApiError.
 */

import type { ApiErrorDetail, ApiValidationIssue } from "./types";

export type ApiErrorKind = "validation" | "not-found" | "server" | "network";

export type ValidationIssue = ApiValidationIssue;

/** Normalized `detail` payload: string or validation issue list. */
export function validationIssues(
  error: ApiError,
): ValidationIssue[] | undefined {
  if (error.kind === "validation" && Array.isArray(error.detail)) {
    return error.detail;
  }
  return undefined;
}

/** Human-readable message for logging or fallback UI text. */
export function apiErrorMessage(error: ApiError): string {
  if (error.kind === "network") {
    return error.message;
  }
  if (typeof error.detail === "string") {
    return error.detail;
  }
  return error.message;
}

export class ApiError extends Error {
  readonly status: number | null;
  readonly detail: ApiErrorDetail | undefined;
  readonly kind: ApiErrorKind;

  constructor(
    kind: ApiErrorKind,
    message: string,
    status: number | null = null,
    detail: ApiErrorDetail | undefined = undefined,
  ) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
    this.detail = detail;
  }
}

/** Classify an HTTP status per the error policy (docs/06 §4b). */
export function kindForStatus(status: number): ApiErrorKind {
  if (status === 422) return "validation";
  if (status === 404) return "not-found";
  return "server";
}
