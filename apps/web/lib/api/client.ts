/**
 * The single fetch-based HTTP client for the backend API
 * (docs/01 §4 communication boundary).
 *
 * Every domain module (roles, persons, events, eventAssignments) goes
 * through `apiGet`/`apiPost` here — no fetch boilerplate is duplicated.
 * The client is plain TypeScript with no React or state concerns; it is
 * usable from server components, route handlers, and the browser alike.
 *
 * Configuration: `NEXT_PUBLIC_API_BASE_URL` (apps/web/.env.example),
 * read at call time so dev/test/prod differ by environment, never by
 * code. Base-URL joining is canonicalized here (trailing slashes are
 * tolerated on either side, never producing `//`).
 */

import { ApiError, kindForStatus } from "./errors";
import type { ApiErrorDetail } from "./types";

/** Resolved API base URL — trailing slash stripped, exactly once. */
export function apiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!configured) {
    throw new ApiError(
      "network",
      "NEXT_PUBLIC_API_BASE_URL is not configured (see apps/web/.env.example)",
    );
  }
  return configured.replace(/\/+$/, "");
}

/**
 * Join a base URL and a route path safely.
 * Handles both `"http://host"` and `"http://host/"` inputs for the base,
 * and both `"/api/..."` and `"api/..."` for the path.
 */
export function buildApiUrl(base: string, path: string): string {
  const cleanBase = base.replace(/\/+$/, "");
  const cleanPath = path.replace(/^\/+/, "");
  return `${cleanBase}/${cleanPath}`;
}

async function request<T>(
  path: string,
  init: RequestInit & { method: "GET" | "POST" },
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(buildApiUrl(apiBaseUrl(), path), {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init.body !== undefined
          ? { "Content-Type": "application/json" }
          : {}),
        ...init.headers,
      },
    });
  } catch (cause) {
    throw new ApiError(
      "network",
      `Could not reach the API at ${apiBaseUrl()}: ${cause instanceof Error ? cause.message : String(cause)}`,
      null,
      undefined,
    );
  }

  if (!response.ok) {
    const detail = await parseErrorDetail(response);
    throw new ApiError(
      kindForStatus(response.status),
      `API request failed with status ${response.status}`,
      response.status,
      detail,
    );
  }

  // 204-style empty bodies would fail JSON parsing; the current API
  // always returns JSON, but staying defensive costs nothing.
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

/** Best-effort extraction of the FastAPI `{"detail": ...}` body. */
async function parseErrorDetail(
  response: Response,
): Promise<ApiErrorDetail | undefined> {
  try {
    const body: unknown = await response.json();
    if (
      body !== null &&
      typeof body === "object" &&
      "detail" in body &&
      (typeof (body as { detail: unknown }).detail === "string" ||
        Array.isArray((body as { detail: unknown }).detail))
    ) {
      return (body as { detail: ApiErrorDetail }).detail;
    }
    return String(JSON.stringify(body));
  } catch {
    return undefined; // non-JSON error body (e.g. plain-text 500)
  }
}

/** GET a JSON resource. */
export async function apiGet<T>(path: string): Promise<T> {
  return request<T>(path, { method: "GET" });
}

/** POST a JSON body; returns the parsed JSON response. */
export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    body: JSON.stringify(body),
  });
}
