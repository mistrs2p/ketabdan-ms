/**
 * Auth API — `POST /api/auth/login`, `GET /api/auth/me` (docs/06 §4f).
 *
 * Pure API communication like the other `lib/api` domain modules: no
 * React, no state, no translation strings. Token persistence lives in
 * `storage.ts`; session state lives in the provider (`context.tsx`).
 * The Bearer header itself is attached by the shared client — this
 * module never handles headers.
 */

import { apiGet, apiPost } from "@/lib/api/client";
import type { AuthenticatedUser, LoginRequest, LoginResponse } from "./types";
import { saveAccessToken } from "./storage";

/**
 * Verify credentials and persist the issued access token.
 *
 * Throws `ApiError` (kind "server", status 401) on any login failure —
 * the backend's generic 401 carries no distinction between unknown
 * user / wrong password / inactive account, and the frontend preserves
 * that (docs/06 §4f anti-enumeration).
 */
export async function login(
  username: string,
  password: string,
): Promise<LoginResponse> {
  const payload: LoginRequest = { username, password };
  const response = await apiPost<LoginResponse>("/api/auth/login", payload);
  saveAccessToken(response.access_token);
  return response;
}

/**
 * Fetch the current authenticated user (`GET /api/auth/me`).
 *
 * The Bearer token is attached by the shared client; a 401 propagates
 * as `ApiError` — the caller (session provider) decides what that
 * means for state.
 */
export function getCurrentUser(): Promise<AuthenticatedUser> {
  return apiGet<AuthenticatedUser>("/api/auth/me");
}

/**
 * Terminate the local session.
 *
 * Client-side only by necessity: the backend has **no token-revocation
 * or logout endpoint** (docs/06 §4f — MVP scope; tokens simply expire).
 * No backend call is made and none is invented. Clearing the persisted
 * token is the whole of logout; the provider clears the user state on
 * top (context.tsx).
 */
export function logout(): void {
  saveAccessToken("");
}
