/**
 * AuthGate tests (Task 5.4) — the protected-(app)-group boundary:
 * loading state renders no protected content, unauthenticated
 * redirects to the locale-aware login with returnTo, authenticated
 * renders the shell, a mid-session 401 flips the guard to the
 * redirect, and locale is preserved through every redirect.
 */

import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthGate } from "@/components/auth/AuthGate";
import { UserMenu } from "@/components/layout/UserMenu";
import { AuthProvider } from "@/lib/auth/context";
import { saveAccessToken } from "@/lib/auth/storage";

const BASE = "http://api.test";
const KEY = "ketabdaneh.auth.access_token";
const ME = { id: "u-1", username: "smoke-user", active: true };

const replaceMock = vi.fn();
vi.mock("@/i18n/routing", () => ({
  useRouter: () => ({ push: vi.fn(), replace: replaceMock }),
  usePathname: () => "/dashboard",
  Link: ({ children }: { children: React.ReactNode }) => <a>{children}</a>,
  locales: ["fa", "en"],
  defaultLocale: "fa",
}));

// next-intl's usePathname (raw, locale-prefixed) is what returnTo needs.
const rawPathnameMock = vi.fn(() => "/fa/dashboard");
vi.mock("next/navigation", () => ({
  usePathname: () => rawPathnameMock(),
}));

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const MESSAGES = {
  en: {
    auth: { sessionLoading: "Restoring your session…" },
    login: { logout: "Sign out" },
    app: { header: { context: "Operations management panel" } },
  },
  fa: {
    auth: { sessionLoading: "در حال بازیابی نشست شما…" },
    login: { logout: "خروج" },
    app: { header: { context: "پنل مدیریت عملیات" } },
  },
};

/** The protected page content the gate must never leak. */
function Secret() {
  return <div data-testid="protected">business data</div>;
}

function renderGate(locale: "fa" | "en" = "fa") {
  return render(
    <NextIntlClientProvider locale={locale} messages={MESSAGES[locale]}>
      <AuthProvider>
        <AuthGate>
          <Secret />
        </AuthGate>
      </AuthProvider>
    </NextIntlClientProvider>,
  );
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", BASE);
  window.localStorage.clear();
  document.body.innerHTML = "";
  replaceMock.mockClear();
  rawPathnameMock.mockClear();
  rawPathnameMock.mockReturnValue("/fa/dashboard");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("loading state", () => {
  it("renders a loading state and no protected content while restoring", async () => {
    let resolveMe: (v: unknown) => void = () => {};
    vi.spyOn(globalThis, "fetch").mockReturnValue(
      new Promise((resolve) => {
        resolveMe = resolve;
      }),
    );
    saveAccessToken("jwt-1");

    renderGate("en");

    // Token present but /me unresolved: loading UI, never the secret.
    expect(screen.getByRole("status")).toHaveTextContent(
      "Restoring your session…",
    );
    expect(screen.queryByTestId("protected")).not.toBeInTheDocument();

    await act(async () => {
      resolveMe(jsonResponse(200, ME));
    });
    await waitFor(() =>
      expect(screen.getByTestId("protected")).toBeInTheDocument(),
    );
  });
});

describe("unauthenticated redirect", () => {
  it("redirects to the locale-aware login with returnTo, no protected UI", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");

    renderGate("fa");

    await waitFor(() => expect(replaceMock).toHaveBeenCalledTimes(1));
    expect(replaceMock).toHaveBeenCalledWith(
      { pathname: "/login", query: { returnTo: "/fa/dashboard" } },
      { locale: "fa" },
    );
    expect(screen.queryByTestId("protected")).not.toBeInTheDocument();
    // No token → /me was never even attempted.
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("keeps the en locale in the redirect", async () => {
    rawPathnameMock.mockReturnValue("/en/events");

    renderGate("en");

    await waitFor(() => expect(replaceMock).toHaveBeenCalledTimes(1));
    expect(replaceMock).toHaveBeenCalledWith(
      { pathname: "/login", query: { returnTo: "/en/events" } },
      { locale: "en" },
    );
  });

  it("redirects exactly once (no loops) while unauthenticated", async () => {
    renderGate("fa");

    await waitFor(() => expect(replaceMock).toHaveBeenCalledTimes(1));
    // Re-renders while the navigation is in flight must not re-fire.
    await act(async () => {});
    expect(replaceMock).toHaveBeenCalledTimes(1);
  });
});

describe("authenticated", () => {
  it("renders the protected content once /me validates the token", async () => {
    saveAccessToken("jwt-1");
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse(200, ME));

    renderGate("fa");

    await waitFor(() =>
      expect(screen.getByTestId("protected")).toBeInTheDocument(),
    );
    expect(replaceMock).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("falls back to the login redirect when the stored token is stale (401)", async () => {
    saveAccessToken("stale-jwt");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(401, { detail: "Not authenticated" }),
    );

    renderGate("fa");

    await waitFor(() => expect(replaceMock).toHaveBeenCalledTimes(1));
    expect(window.localStorage.getItem(KEY)).toBeNull();
    expect(screen.queryByTestId("protected")).not.toBeInTheDocument();
  });

  it("re-redirects after a mid-session 401 flips the provider state", async () => {
    saveAccessToken("jwt-1");
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(200, ME))
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Not authenticated" }));

    renderGate("fa");
    await waitFor(() =>
      expect(screen.getByTestId("protected")).toBeInTheDocument(),
    );

    // A later business call 401s (token-carrying): the 5.3 client
    // listener flips the provider; the gate must react by redirecting.
    const { getPersons } = await import("@/lib/api/persons");
    await expect(getPersons()).rejects.toBeInstanceOf(Error);

    await waitFor(() => expect(replaceMock).toHaveBeenCalledTimes(1));
    expect(window.localStorage.getItem(KEY)).toBeNull();
    expect(screen.queryByTestId("protected")).not.toBeInTheDocument();
  });
});

describe("UserMenu (logout + current-user display)", () => {
  it("shows the username and redirects to login on logout", async () => {
    saveAccessToken("jwt-1");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(200, ME));
    const user = userEvent.setup();

    render(
      <NextIntlClientProvider locale="fa" messages={MESSAGES.fa}>
        <AuthProvider>
          <UserMenu />
        </AuthProvider>
      </NextIntlClientProvider>,
    );

    await waitFor(() =>
      expect(screen.getByText("smoke-user")).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: "خروج" }));

    expect(window.localStorage.getItem(KEY)).toBeNull();
    await waitFor(() => expect(replaceMock).toHaveBeenCalledTimes(1));
    expect(replaceMock).toHaveBeenCalledWith(
      { pathname: "/login" },
      { locale: "fa" },
    );
  });

  it("renders nothing without a user", () => {
    const { container } = render(
      <NextIntlClientProvider locale="en" messages={MESSAGES.en}>
        <AuthProvider>
          <UserMenu />
        </AuthProvider>
      </NextIntlClientProvider>,
    );
    // No token → provider is unauthenticated; UserMenu renders nothing.
    expect(container.querySelector("button")).not.toBeInTheDocument();
    expect(screen.queryByText("smoke-user")).not.toBeInTheDocument();
  });
});
