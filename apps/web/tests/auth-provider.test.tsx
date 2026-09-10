/**
 * Session provider tests — the auth state machine over a mocked
 * transport: no token → unauthenticated; token + valid /me →
 * authenticated; token + 401 → token cleared + unauthenticated; login
 * / logout state transitions; the app-wide 401 listener path.
 */

import { act, render, screen, waitFor } from "@testing-library/react";
import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";


import { ApiError } from "@/lib/api/errors";
import { AuthProvider, useAuth } from "@/lib/auth/context";

const KEY = "ketabdaneh.auth.access_token";
const BASE = "http://api.test";

const ME = { id: "u-1", username: "smoke-user", active: true };

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Render a probe component exposing the session through data-testid. */
function Probe() {
  const { user, isAuthenticated, isLoading, login, logout } = useAuth();
  return (
    <div>
      <span data-testid="status">
        {isLoading
          ? "loading"
          : isAuthenticated
            ? "authenticated"
            : "unauthenticated"}
      </span>
      <span data-testid="username">{user?.username ?? "none"}</span>
      <button type="button" onClick={() => login("smoke-user", "pass-1234")}>
        probe-login
      </button>
      <button type="button" onClick={() => logout()}>
        probe-logout
      </button>
    </div>
  );
}

function renderProvider() {
  return render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", BASE);
  window.localStorage.clear();
  document.body.innerHTML = ""; // isolate each render (no shared DOM)
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("session restoration", () => {
  it("becomes unauthenticated immediately when no token is stored", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");

    renderProvider();

    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent(
        "unauthenticated",
      ),
    );
    expect(screen.getByTestId("username")).toHaveTextContent("none");
    // No token → /me is never called.
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("restores the session when a token exists and /me succeeds", async () => {
    window.localStorage.setItem(KEY, "jwt-1");
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse(200, ME));

    renderProvider();

    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent("authenticated"),
    );
    expect(screen.getByTestId("username")).toHaveTextContent("smoke-user");
    // Restoration is exactly one /me call — never repeated.
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${BASE}/api/auth/me`);
    expect((init.headers as Record<string, string>).Authorization).toBe(
      "Bearer jwt-1",
    );
  });

  it("clears the token and goes unauthenticated when /me returns 401", async () => {
    window.localStorage.setItem(KEY, "stale-jwt");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(401, { detail: "Not authenticated" }),
    );

    renderProvider();

    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent(
        "unauthenticated",
      ),
    );
    expect(window.localStorage.getItem(KEY)).toBeNull();
    // No retry loop: /me was called once, then the state settled.
    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
  });
});

describe("login / logout transitions", () => {
  it("login stores the token and sets the user from /me", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/auth/login")) {
        return jsonResponse(200, {
          access_token: "jwt-2",
          token_type: "bearer",
          expires_in: 3600,
        });
      }
      if (url.endsWith("/api/auth/me")) {
        return jsonResponse(200, ME);
      }
      return jsonResponse(404, { detail: "unexpected" });
    });

    renderProvider();

    await act(async () => {
      screen.getByRole("button", { name: "probe-login" }).click();
    });

    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent("authenticated"),
    );
    expect(screen.getByTestId("username")).toHaveTextContent("smoke-user");
    expect(window.localStorage.getItem(KEY)).toBe("jwt-2");
  });

  it("logout clears the token and the user state", async () => {
    window.localStorage.setItem(KEY, "jwt-1");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(200, ME));

    renderProvider();
    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent("authenticated"),
    );

    act(() => {
      screen.getByRole("button", { name: "probe-logout" }).click();
    });

    expect(screen.getByTestId("status")).toHaveTextContent("unauthenticated");
    expect(screen.getByTestId("username")).toHaveTextContent("none");
    expect(window.localStorage.getItem(KEY)).toBeNull();
  });
});

describe("app-wide 401 (token-carrying request rejected)", () => {
  it("flips to unauthenticated when any authenticated call 401s", async () => {
    window.localStorage.setItem(KEY, "jwt-1");
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(200, ME))
      .mockResolvedValueOnce(
        jsonResponse(401, { detail: "Not authenticated" }),
      );

    renderProvider();
    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent("authenticated"),
    );

    // A later authenticated business call (e.g. the persons list) 401s.
    const { getPersons } = await import("@/lib/api/persons");
    await expect(getPersons()).rejects.toBeInstanceOf(ApiError);

    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent(
        "unauthenticated",
      ),
    );
    expect(window.localStorage.getItem(KEY)).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});

describe("useAuth outside the provider", () => {
  it("throws a clear error when no provider is mounted", () => {
    expect(() => renderHook(() => useAuth())).toThrow(
      /must be used inside <AuthProvider>/,
    );
  });
});
