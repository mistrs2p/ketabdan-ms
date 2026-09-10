"use client";

import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "@/i18n/routing";
import type { Locale } from "@/i18n/routing";
import { useAuth } from "@/lib/auth";

// Authenticated user identity + sign-out (Task 5.4), rendered in the
// Header. Shows only what the `/me` contract provides — the username.
// No roles/permissions are displayed or inferred; authorization stays
// server-side (docs/06 §4g).
//
// Logout is the 5.3 client-side semantics: clear the persisted token
// and session state — the backend has no revocation endpoint, none is
// invented — then replace to the locale-aware login page. `replace`
// keeps the logged-out page out of the history stack (Back after
// logout lands before it, and the AuthGate re-checks anyway).
export function UserMenu() {
  const t = useTranslations("login");
  const { user, logout } = useAuth();
  const router = useRouter();
  const locale = useLocale() as Locale;

  if (!user) return null; // the AuthGate guarantees a user; defensive

  function handleLogout() {
    logout();
    router.replace({ pathname: "/login" }, { locale });
  }

  return (
    <div className="flex min-w-0 items-center gap-2">
      <span
        className="hidden max-w-32 truncate text-sm text-muted-foreground sm:inline"
        title={user.username}
      >
        {user.username}
      </span>
      <button
        type="button"
        onClick={handleLogout}
        aria-label={t("logout")}
        className="shrink-0 rounded-lg border border-border bg-surface px-3 py-1.5 text-sm font-medium text-foreground hover:bg-primary/5"
      >
        {t("logout")}
      </button>
    </div>
  );
}
