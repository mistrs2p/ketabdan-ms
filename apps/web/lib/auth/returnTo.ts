/**
 * Safe handling of the `returnTo` query parameter (Task 5.4).
 *
 * After an unauthenticated visitor is redirected from a protected route
 * to `/login?returnTo=<original path>`, a successful login sends them
 * back to that path. The value is attacker-controlled URL input, so it
 * is validated here before it ever reaches `router.replace` — the goal
 * is a closed set: internal, locale-prefixed application paths only.
 *
 * Accepted:  `/fa/dashboard`, `/en/events`, `/fa/people/123`, `/fa`
 * Rejected:  `https://evil.example` (absolute URL — no leading slash),
 *            `//evil.example` (protocol-relative),
 *            `/\evil.example` (backslash variant of the same),
 *            `javascript:alert(1)` (scheme),
 *            `/dashboard` (no locale prefix — not one of ours),
 *            `/fa/login…` (would loop back into the login page),
 *            anything containing `:` (any scheme separator, including
 *            ones smuggled into a query string).
 *
 * Returns `{locale, path}` with the locale stripped, ready for the
 * next-intl router (`router.replace(path)` — the router re-applies the
 * active locale), or `null` when the value is not a safe internal
 * target — the caller then falls back to `/dashboard`.
 */

import { locales } from "@/i18n/routing";

const LOCALE_PATH = new RegExp(`^/(${locales.join("|")})(/.*)?$`);

/** Split `/fa/events/42` into `{locale: "fa", path: "/events/42"}`. */
export function splitLocalePath(
  path: string,
): { locale: string; path: string } | null {
  const match = path.match(LOCALE_PATH);
  if (!match) return null;
  return { locale: match[1], path: match[2] ?? "/" };
}

/**
 * Validate a raw `returnTo` value and split it for the router.
 * `null` means "not safe / not present" — use the dashboard fallback.
 */
export function sanitizeReturnTo(
  raw: string | null | undefined,
): { locale: string; path: string } | null {
  if (!raw) return null;
  const value = raw.trim();
  if (!value) return null;

  // Must be a root-relative path — absolute URLs (`https://…`,
  // `javascript:…`) and bare relative paths are rejected outright.
  if (!value.startsWith("/")) return null;
  // Protocol-relative and its backslash twin.
  if (value.startsWith("//") || value.startsWith("/\\")) return null;
  // Any scheme separator or stray backslash anywhere (browsers accept
  // `\` in place of `/` in some contexts). Our own paths never contain
  // either, so rejecting both is strictly safer.
  if (value.includes(":") || value.includes("\\")) return null;

  const split = splitLocalePath(value);
  if (!split) return null;

  // The login route itself would bounce straight back — a redirect
  // loop. `/login`, `/login/…`, and `/login?…` all count (the query
  // string is part of the raw path here).
  if (split.path === "/login" || split.path.startsWith("/login/") || split.path.startsWith("/login?")) {
    return null;
  }

  return split;
}
