/**
 * Access-token persistence (browser localStorage).
 *
 * **Security trade-off (deliberate, documented):** localStorage is the
 * MVP client-token strategy — simple, survives page refresh, and works
 * with the existing client-side fetch layer without a proxy. It is NOT
 * XSS-safe storage: any script running on the page can read it. A
 * future httpOnly-cookie / BFF approach would keep the token out of
 * JavaScript entirely at the cost of backend session changes; that
 * migration is a documented future option, not a current requirement.
 *
 * What this module guarantees regardless of the backing store:
 * - the token lives in exactly one place, read/written only through
 *   these functions;
 * - the password is NEVER persisted (only the issued access token);
 * - browser APIs are never touched during server rendering — every
 *   function checks for `window` first, so SSR/build render without
 *   hydration surprises;
 * - a missing/empty value is indistinguishable from "logged out".
 */

const TOKEN_STORAGE_KEY = "ketabdaneh.auth.access_token";

/** True when running in a browser (client-side) context. */
function isBrowser(): boolean {
  return typeof window !== "undefined";
}

/** Persist the access token. Empty/null tokens are treated as logout. */
export function saveAccessToken(token: string): void {
  if (!isBrowser()) return;
  if (token) {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
  } else {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
  }
}

/** Read the persisted access token; `null` when absent or server-side. */
export function readAccessToken(): string | null {
  if (!isBrowser()) return null;
  const token = window.localStorage.getItem(TOKEN_STORAGE_KEY);
  return token ? token : null;
}

/** Remove the persisted access token (logout / stale-session cleanup). */
export function clearAccessToken(): void {
  if (!isBrowser()) return;
  window.localStorage.removeItem(TOKEN_STORAGE_KEY);
}
