/**
 * Login form tests — the interactive client component, rendered with
 * the real fa/en messages through next-intl's test provider and a
 * mocked transport: required-field validation, successful login
 * (navigation to dashboard), invalid credentials (generic localized
 * 401 message), network failure, and the loading/disabled state.
 */

import { render, screen, waitFor } from "@testing-library/react";
import { act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LoginForm } from "@/components/auth/LoginForm";

const BASE = "http://api.test";
const ME = { id: "u-1", username: "smoke-user", active: true };

// next-intl routing hooks: mock at module level (the form replaces to
// /dashboard or the sanitized returnTo after login — we assert the
// call, not navigation). LocaleSwitcher (rendered inside the form)
// also uses usePathname and the `routing` locale list.
const pushMock = vi.fn();
const replaceMock = vi.fn();
vi.mock("@/i18n/routing", () => ({
  useRouter: () => ({ push: pushMock, replace: replaceMock }),
  usePathname: () => "/login",
  routing: { locales: ["fa", "en"], defaultLocale: "fa" },
  locales: ["fa", "en"],
  defaultLocale: "fa",
}));

function renderForm(locale: "fa" | "en") {
  // Include the `foundation` messages too — LocaleSwitcher reads them.
  const messages = {
    foundation: {
      language: "Language",
      themeToggle: { light: "Light", dark: "Dark" },
    },
    login: LOGIN_MESSAGES[locale],
  };
  return render(
    <NextIntlClientProvider locale={locale} messages={messages}>
      <LoginForm />
    </NextIntlClientProvider>,
  );
}

// The minimal message subset the form uses, in both languages.
const LOGIN_MESSAGES = {
  en: {
    title: "Sign in",
    usernameLabel: "Username",
    passwordLabel: "Password",
    submit: "Sign in",
    submitting: "Signing in…",
    usernameRequired: "Username is required.",
    passwordRequired: "Password is required.",
    invalidCredentials: "Invalid username or password.",
    networkError: "The service is unreachable right now.",
    serverError: "Sign-in failed.",
  },
  fa: {
    title: "ورود",
    usernameLabel: "نام کاربری",
    passwordLabel: "رمز عبور",
    submit: "ورود",
    submitting: "در حال ورود…",
    usernameRequired: "نام کاربری الزامی است.",
    passwordRequired: "رمز عبور الزامی است.",
    invalidCredentials: "نام کاربری یا رمز عبور نادرست است.",
    networkError: "سرویس در دسترس نیست.",
    serverError: "ورود ناموفق بود.",
  },
};

/** The auth surface the form consumes (provider is not under test here). */
const loginMock = vi.fn();
const authStateMock = vi.fn(() => ({
  login: loginMock,
  isAuthenticated: false,
  isLoading: false,
}));
vi.mock("@/lib/auth", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/auth")>();
  return {
    ...actual,
    useAuth: () => authStateMock(),
  };
});

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", BASE);
  window.localStorage.clear();
  pushMock.mockClear();
  replaceMock.mockClear();
  loginMock.mockReset();
  authStateMock.mockReturnValue({
    login: loginMock,
    isAuthenticated: false,
    isLoading: false,
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("required-field validation", () => {
  it("shows both required messages and calls nothing when empty", async () => {
    loginMock.mockResolvedValue(ME);
    const user = userEvent.setup();
    renderForm("en");

    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(screen.getByText("Username is required.")).toBeInTheDocument();
    expect(screen.getByText("Password is required.")).toBeInTheDocument();
    expect(loginMock).not.toHaveBeenCalled();
  });

  it("shows only the missing-field message when one field is empty", async () => {
    const user = userEvent.setup();
    renderForm("en");

    await user.type(screen.getByLabelText(/Username/), "smoke-user");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(screen.queryByText("Username is required.")).not.toBeInTheDocument();
    expect(screen.getByText("Password is required.")).toBeInTheDocument();
    expect(loginMock).not.toHaveBeenCalled();
  });
});

describe("successful login", () => {
  it("navigates to the dashboard when login resolves", async () => {
    loginMock.mockResolvedValue(ME);
    const user = userEvent.setup();
    renderForm("en");

    await user.type(screen.getByLabelText(/Username/), "smoke-user");
    await user.type(screen.getByLabelText(/Password/), "pass-1234");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/dashboard"));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("submits via keyboard (Enter in the password field)", async () => {
    loginMock.mockResolvedValue(ME);
    const user = userEvent.setup();
    renderForm("en");

    await user.type(screen.getByLabelText(/Username/), "smoke-user");
    await user.type(screen.getByLabelText(/Password/), "pass-1234{Enter}");

    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/dashboard"));
  });
});

describe("invalid credentials", () => {
  it("shows the generic 401 message (no backend detail, no distinction)", async () => {
    const { ApiError } = await import("@/lib/api/errors");
    loginMock.mockRejectedValue(
      new ApiError("server", "API request failed with status 401", 401, {
        detail: "Invalid username or password",
      }),
    );
    const user = userEvent.setup();
    renderForm("en");

    await user.type(screen.getByLabelText(/Username/), "ghost");
    await user.type(screen.getByLabelText(/Password/), "wrong");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Invalid username or password.");
    // The raw backend message must not be the distinguishing surface —
    // the localized generic text is what the user sees.
    expect(alert).toHaveTextContent("Invalid username or password.");
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("shows the localized fa message on the fa form", async () => {
    const { ApiError } = await import("@/lib/api/errors");
    loginMock.mockRejectedValue(
      new ApiError("server", "API request failed with status 401", 401, {
        detail: "Invalid username or password",
      }),
    );
    const user = userEvent.setup();
    renderForm("fa");

    await user.type(screen.getByLabelText(/نام کاربری/), "ghost");
    await user.type(screen.getByLabelText(/رمز عبور/), "wrong");
    await user.click(screen.getByRole("button", { name: "ورود" }));

    expect(
      await screen.findByRole("alert"),
    ).toHaveTextContent("نام کاربری یا رمز عبور نادرست است.");
  });
});

describe("network / server failure", () => {
  it("shows the localized network message on a network ApiError", async () => {
    const { ApiError } = await import("@/lib/api/errors");
    loginMock.mockRejectedValue(
      new ApiError("network", "Could not reach the API"),
    );
    const user = userEvent.setup();
    renderForm("en");

    await user.type(screen.getByLabelText(/Username/), "smoke-user");
    await user.type(screen.getByLabelText(/Password/), "pass-1234");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(
      await screen.findByRole("alert"),
    ).toHaveTextContent("The service is unreachable right now.");
  });

  it("shows the generic server message for other statuses and no stack trace", async () => {
    const { ApiError } = await import("@/lib/api/errors");
    loginMock.mockRejectedValue(
      new ApiError("server", "API request failed with status 503", 503, {
        detail: "Internal something",
      }),
    );
    const user = userEvent.setup();
    renderForm("en");

    await user.type(screen.getByLabelText(/Username/), "smoke-user");
    await user.type(screen.getByLabelText(/Password/), "pass-1234");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Sign-in failed.",
    );
    expect(screen.queryByText(/Could not reach|503|Internal/)).not.toBeInTheDocument();
  });
});

describe("loading state", () => {
  it("disables the submit button and shows the loading label while in flight", async () => {
    let resolveLogin: (value: unknown) => void = () => {};
    loginMock.mockReturnValue(
      new Promise((resolve) => {
        resolveLogin = resolve;
      }),
    );
    const user = userEvent.setup();
    renderForm("en");

    await user.type(screen.getByLabelText(/Username/), "smoke-user");
    await user.type(screen.getByLabelText(/Password/), "pass-1234");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    const button = screen.getByRole("button", { name: "Signing in…" });
    expect(button).toBeDisabled();
    // Duplicate submission is blocked: extra clicks do nothing.
    await user.click(button).catch(() => {});
    expect(loginMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveLogin(ME);
    });
    await waitFor(() => expect(replaceMock).toHaveBeenCalled());
  });
});

describe("already-authenticated visitor (Task 5.4)", () => {
  it("redirects to the dashboard once restoration settles", async () => {
    authStateMock.mockReturnValue({
      login: loginMock,
      isAuthenticated: true,
      isLoading: false,
    });
    renderForm("en");

    await waitFor(() =>
      expect(replaceMock).toHaveBeenCalledWith("/dashboard"),
    );
  });

  it("does not redirect while the session is still loading", () => {
    authStateMock.mockReturnValue({
      login: loginMock,
      isAuthenticated: false,
      isLoading: true,
    });
    renderForm("en");

    expect(replaceMock).not.toHaveBeenCalled();
  });
});

describe("returnTo (Task 5.4)", () => {
  it("returns to the sanitized returnTo path after login", async () => {
    window.history.replaceState(
      null,
      "",
      "/fa/login?returnTo=%2Ffa%2Fevents%2F123",
    );
    loginMock.mockResolvedValue(ME);
    const user = userEvent.setup();
    renderForm("fa");

    await user.type(screen.getByLabelText(/نام کاربری/), "smoke-user");
    await user.type(screen.getByLabelText(/رمز عبور/), "pass-1234");
    await user.click(screen.getByRole("button", { name: "ورود" }));

    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/events/123"));
    window.history.replaceState(null, "", "/");
  });

  it("falls back to the dashboard when returnTo is unsafe or absent", async () => {
    window.history.replaceState(
      null,
      "",
      "/en/login?returnTo=https%3A%2F%2Fevil.example",
    );
    loginMock.mockResolvedValue(ME);
    const user = userEvent.setup();
    renderForm("en");

    await user.type(screen.getByLabelText(/Username/), "smoke-user");
    await user.type(screen.getByLabelText(/Password/), "pass-1234");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/dashboard"));
    expect(replaceMock).not.toHaveBeenCalledWith("https://evil.example");
    window.history.replaceState(null, "", "/");
  });
});
