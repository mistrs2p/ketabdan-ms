"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/routing";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
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
// On success the router sends the user to the dashboard — the locale
// prefix stays intact (routing.push). No token/credential ever lands in
// the URL.
export function LoginForm() {
  const t = useTranslations("login");
  const { login } = useAuth();
  const router = useRouter();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [usernameError, setUsernameError] = useState<string | undefined>();
  const [passwordError, setPasswordError] = useState<string | undefined>();
  const [formError, setFormError] = useState<string | undefined>();

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
      router.push("/dashboard");
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
