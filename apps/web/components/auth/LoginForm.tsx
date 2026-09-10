"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/routing";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { sanitizeReturnTo } from "@/lib/auth/returnTo";
import { LocaleSwitcher } from "@/components/LocaleSwitcher";
import { ThemeToggle } from "@/components/ThemeToggle";

// The login form — the client boundary of the login page. Owns the
// field state, the required-field validation, the in-flight/disabled
// state, and the translation of ApiError kinds into localized messages.
//
// Error contract: a 401 (kind "server", status 401) is the generic
// invalid-credentials message — the backend deliberately does not
// distinguish unknown user / wrong password / inactive account, and the
// frontend preserves that (docs/06 §4f anti-enumeration). Network
// failures get their own message. Raw backend detail is never shown.
//
// Navigation (Task 5.4):
// - A visitor who is already authenticated (e.g. followed a link to
//   /login after a session restore) is sent to the dashboard — but
//   only AFTER restoration finishes (`isLoading === false`), never
//   during it, and never back to `/login` itself (no loops).
// - On successful login the user returns to the validated `returnTo`
//   path (set by the AuthGate redirect) or the dashboard. `replace`
//   keeps the login URL out of the history stack so Back stays in the
//   app. No token/credential ever lands in the URL.
export function LoginForm() {
  const t = useTranslations("login");
  const { login, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [usernameError, setUsernameError] = useState<string | undefined>();
  const [passwordError, setPasswordError] = useState<string | undefined>();
  const [formError, setFormError] = useState<string | undefined>();

  // Already-authenticated visitors: replace to the dashboard once, and
  // only after session restoration has settled (redirecting during
  // `isLoading` would bounce a user whose token is being validated).
  // The `submitting` guard matters: after a successful form login the
  // provider flips to authenticated while still on this page, and the
  // form's own navigation (returnTo/dashboard) must win — without the
  // guard both navigations would race and the effect's /dashboard
  // could clobber the returnTo target.
  const bouncedRef = useRef(false);
  useEffect(() => {
    if (isLoading || !isAuthenticated || submitting || bouncedRef.current) {
      return;
    }
    bouncedRef.current = true;
    router.replace("/dashboard");
  }, [isLoading, isAuthenticated, submitting, router]);

  // The validated post-login target: the sanitized `returnTo` from the
  // URL, or the dashboard fallback. Read once via the browser location
  // (validated before use — never a raw router.push of user input).
  const returnTarget = sanitizeReturnTo(
    typeof window === "undefined"
      ? null
      : new URLSearchParams(window.location.search).get("returnTo"),
  );

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return; // duplicate submission blocked

    // UI-level required checks only; every other rule is backend-owned.
    const trimmedUsername = username.trim();
    const hasUsernameError = !trimmedUsername;
    const hasPasswordError = !password;
    setUsernameError(hasUsernameError ? t("usernameRequired") : undefined);
    setPasswordError(hasPasswordError ? t("passwordRequired") : undefined);
    setFormError(undefined);
    if (hasUsernameError || hasPasswordError) return;

    setSubmitting(true);
    try {
      await login(trimmedUsername, password);
      // Safe internal path only: sanitizeReturnTo rejected absolute
      // URLs, protocol-relative URLs, schemes, and non-locale paths.
      if (returnTarget) {
        router.replace(returnTarget.path);
      } else {
        router.replace("/dashboard");
      }
    } catch (e) {
      const error =
        e instanceof ApiError ? e : new ApiError("server", String(e));
      if (error.status === 401) {
        setFormError(t("invalidCredentials"));
      } else if (error.kind === "network") {
        setFormError(t("networkError"));
      } else {
        setFormError(t("serverError"));
      }
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <LocaleSwitcher />
        <ThemeToggle />
      </div>
      <form
        onSubmit={handleSubmit}
        noValidate
        className="flex flex-col gap-5 rounded-lg border border-border bg-surface p-6"
      >
        {/* Username — required */}
        <div className="flex flex-col gap-1.5">
          <label htmlFor="login-username" className="text-sm font-medium">
            {t("usernameLabel")}
            <span aria-hidden="true" className="text-primary">
              {" *"}
            </span>
          </label>
          <input
            id="login-username"
            name="username"
            type="text"
            autoComplete="username"
            autoFocus
            value={username}
            onChange={(e) => {
              setUsername(e.target.value);
              if (usernameError) setUsernameError(undefined);
            }}
            required
            aria-required="true"
            aria-invalid={usernameError ? true : undefined}
            aria-describedby={usernameError ? "login-username-error" : undefined}
            disabled={submitting}
            className="rounded-lg border border-border bg-background px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-50"
          />
          {usernameError ? (
            <p
              id="login-username-error"
              className="text-sm text-primary"
              role="alert"
            >
              {usernameError}
            </p>
          ) : null}
        </div>

        {/* Password — required, always masked (type="password") */}
        <div className="flex flex-col gap-1.5">
          <label htmlFor="login-password" className="text-sm font-medium">
            {t("passwordLabel")}
            <span aria-hidden="true" className="text-primary">
              {" *"}
            </span>
          </label>
          <input
            id="login-password"
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              if (passwordError) setPasswordError(undefined);
            }}
            required
            aria-required="true"
            aria-invalid={passwordError ? true : undefined}
            aria-describedby={passwordError ? "login-password-error" : undefined}
            disabled={submitting}
            className="rounded-lg border border-border bg-background px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-50"
          />
          {passwordError ? (
            <p
              id="login-password-error"
              className="text-sm text-primary"
              role="alert"
            >
              {passwordError}
            </p>
          ) : null}
        </div>

        {formError ? (
          <p
            className="rounded-lg border border-border p-3 text-sm"
            role="alert"
          >
            {formError}
          </p>
        ) : null}

        <button
          type="submit"
          disabled={submitting}
          className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? t("submitting") : t("submit")}
        </button>
      </form>
    </div>
  );
}
