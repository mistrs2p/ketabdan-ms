/**
 * `returnTo` sanitization tests (Task 5.4) — the open-redirect guard.
 * Every accepted value must be an internal, locale-prefixed
 * application path; everything else falls back to null (dashboard).
 */

import { describe, expect, it, vi } from "vitest";

// returnTo.ts reads the locale list from the routing module; mock it so
// the test never pulls next-intl/next into the jsdom environment.
vi.mock("@/i18n/routing", () => ({
  locales: ["fa", "en"],
  defaultLocale: "fa",
}));

import { sanitizeReturnTo, splitLocalePath } from "@/lib/auth/returnTo";

describe("accepted internal paths", () => {
  it.each([
    ["/fa/dashboard", "fa", "/dashboard"],
    ["/en/events", "en", "/events"],
    ["/fa/events/123", "fa", "/events/123"],
    ["/en/people/abc-42", "en", "/people/abc-42"],
    ["/fa", "fa", "/"],
  ])("%s → locale %s, path %s", (raw, locale, path) => {
    expect(sanitizeReturnTo(raw)).toEqual({ locale, path });
  });

  it("keeps query strings of internal paths", () => {
    expect(sanitizeReturnTo("/fa/events?tab=upcoming")).toEqual({
      locale: "fa",
      path: "/events?tab=upcoming",
    });
  });
});

describe("rejected values (open-redirect vectors)", () => {
  it.each([
    "https://evil.example",
    "http://evil.example/phish",
    "//evil.example", // protocol-relative
    "/\\evil.example", // backslash twin
    "\\/evil.example",
    "javascript:alert(1)",
    "data:text/html,hi",
    "/dashboard", // no locale prefix — not one of our paths
    "events", // not root-relative
    "fa/dashboard", // relative, not a path
    "/fa/login", // would loop straight back into login
    "/fa/login?returnTo=/fa/events",
    "/en/login/x",
    "/xx/dashboard", // unknown locale
  ])("%s → null", (raw) => {
    expect(sanitizeReturnTo(raw)).toBeNull();
  });

  it("rejects a colon anywhere — including smuggled into a query string", () => {
    // Any colon is rejected outright: our own returnTo values come from
    // usePathname (never contains a query), so this costs nothing and
    // closes every scheme-smuggling vector.
    expect(sanitizeReturnTo("/fa/redirect?next=https://evil.example")).toBeNull();
    expect(sanitizeReturnTo("/fa/a:b")).toBeNull();
  });

  it("treats absent/blank values as absent", () => {
    expect(sanitizeReturnTo(null)).toBeNull();
    expect(sanitizeReturnTo(undefined)).toBeNull();
    expect(sanitizeReturnTo("")).toBeNull();
    expect(sanitizeReturnTo("   ")).toBeNull();
  });
});

describe("splitLocalePath", () => {
  it("splits a locale-prefixed path", () => {
    expect(splitLocalePath("/en/people/new")).toEqual({
      locale: "en",
      path: "/people/new",
    });
  });

  it("returns null for non-locale paths", () => {
    expect(splitLocalePath("/dashboard")).toBeNull();
    expect(splitLocalePath("relative")).toBeNull();
  });
});
