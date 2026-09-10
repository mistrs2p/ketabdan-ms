"use client";

/**
 * The protected-application boundary (Task 5.4).
 *
 * Mounted once, in the `(app)` route-group layout, around the AppShell:
 * every business page renders beneath it, `/login` deliberately does
 * not. This is the single guard — pages never re-implement auth checks.
 *
 * Why a client-side guard: the access token lives in browser
 * localStorage (the documented MVP strategy, docs/06 §4h), which
 * middleware and server components cannot read. Server/middleware
 * authentication would require the httpOnly-cookie/BFF migration that
 * this task explicitly defers. The guard therefore runs where the token
 * is — but it is race-safe against protected-content flashes:
 *
 * - While the session is being restored (`isLoading`), the gate renders
 *   only a loading state — the protected tree (shell + page) is never
 *   rendered, not even in the server HTML, because the gate's first
 *   render takes the loading branch before any effect runs.
 * - A token alone never renders the app: the 5.3 provider validates it
 *   against `GET /api/auth/me` first.
 * - Unauthenticated (including a mid-session 401 flipping the provider
 *   state) → replace to the locale-aware `/login?returnTo=<current>`.
 *   `replace` keeps the protected URL out of the history stack, so
 *   browser Back after an expiry does not land on a usable page.
 *
 * This gate is an *authentication* boundary only. It knows nothing
 * about roles/permissions — the backend remains the authorization
 * source (docs/06 §4g), so an authenticated-but-forbidden user still
 * gets the backend's 403 on the operation itself.
 */

import { useEffect, useRef } from "react";
import { useLocale, useTranslations } from "next-intl";
import { usePathname } from "next/navigation";
import { useRouter } from "@/i18n/routing";
import type { Locale } from "@/i18n/routing";
import { useAuth } from "@/lib/auth";

export function AuthGate({ children }: { children: React.ReactNode }) {
  const t = useTranslations("auth");
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const locale = useLocale() as Locale;
  // Raw, locale-prefixed path (e.g. /fa/events/123) — what `returnTo`
  // needs so the post-login redirect returns to the exact original URL.
  const pathname = usePathname();
  const redirecting = useRef(false);

  useEffect(() => {
    if (isLoading || isAuthenticated) return;
    // Fire once per fall-out-of-authenticated: the ref guards against
    // re-entry while the navigation is in flight (no redirect loops).
    if (redirecting.current) return;
    redirecting.current = true;
    router.replace(
      { pathname: "/login", query: { returnTo: pathname } },
      { locale },
    );
  }, [isLoading, isAuthenticated, pathname, locale, router]);

  if (isLoading) {
    // Same visual language as the route loading skeletons: surface
    // blocks + a status line, no shell, no business UI.
    return (
      <div
        className="flex min-h-dvh items-center justify-center bg-background p-4 text-foreground"
        role="status"
        aria-label={t("sessionLoading")}
      >
        <div className="flex w-full max-w-sm flex-col items-center gap-4">
          <div className="h-12 w-full animate-pulse rounded-lg bg-surface" />
          <div className="h-28 w-full animate-pulse rounded-lg bg-surface" />
          <span className="text-sm text-muted-foreground">
            {t("sessionLoading")}
          </span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null; // the redirect above is in flight
  }

  return children;
}
