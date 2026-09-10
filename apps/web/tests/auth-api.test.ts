/**
 * Auth API tests — login / getCurrentUser / logout against a mocked
 * fetch (the shared client's transport), verifying the backend contract
 * (docs/06 §4f): request shapes, Bearer attachment, token persistence,
 * error propagation, and that logout clears persisted state.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/errors";
import * as authApi from "@/lib/auth/api";
import { readAccessToken } from "@/lib/auth/storage";

const BASE = "http://api.test";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", BASE);
  window.localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("login", () => {
  it("posts credentials and persists the returned token", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        jsonResponse(200, {
          access_token: "jwt-1",
          token_type: "bearer",
          expires_in: 3600,
        }),
      );

    const response = await authApi.login("smoke-user", "pass-1234");

    expect(response).toEqual({
      access_token: "jwt-1",
      token_type: "bearer",
      expires_in: 3600,
    });
    // Exactly the backend contract body — no extra fields.
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${BASE}/api/auth/login`);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      username: "smoke-user",
      password: "pass-1234",
    });
    // No Authorization header on login (no token yet), no persistence
    // of the password — only the token is stored.
    expect((init.headers as Record<string, string>).Authorization).toBeUndefined();
    expect(readAccessToken()).toBe("jwt-1");
    expect(window.localStorage.getItem("ketabdaneh.auth.access_token")).toBe(
      "jwt-1",
    );
  });

  it("propagates 401 as an ApiError and stores nothing", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(401, { detail: "Invalid username or password" }),
    );

    await expect(authApi.login("ghost", "nope")).rejects.toBeInstanceOf(
      ApiError,
    );
    // Login 401 is tokenless — no stale session to clear, nothing saved.
    expect(readAccessToken()).toBeNull();
  });
});

describe("getCurrentUser", () => {
  it("attaches the persisted token as Bearer and returns the /me body", async () => {
    window.localStorage.setItem("ketabdaneh.auth.access_token", "jwt-1");
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        jsonResponse(200, { id: "u-1", username: "smoke-user", active: true }),
      );

    const user = await authApi.getCurrentUser();

    expect(user).toEqual({ id: "u-1", username: "smoke-user", active: true });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${BASE}/api/auth/me`);
    expect(init.method).toBe("GET");
    expect((init.headers as Record<string, string>).Authorization).toBe(
      "Bearer jwt-1",
    );
  });

  it("sends no Authorization header when no token is stored", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse(401, { detail: "Not authenticated" }));

    await expect(authApi.getCurrentUser()).rejects.toBeInstanceOf(ApiError);

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    // Never a malformed "Bearer null" header.
    expect((init.headers as Record<string, string>).Authorization).toBeUndefined();
  });

  it("propagates a 401 for a stale token and clears it", async () => {
    window.localStorage.setItem("ketabdaneh.auth.access_token", "stale-jwt");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(401, { detail: "Not authenticated" }),
    );

    await expect(authApi.getCurrentUser()).rejects.toSatisfy(
      (e: unknown) => e instanceof ApiError && e.status === 401,
    );
    // The client's 401 handling removed the dead token.
    expect(readAccessToken()).toBeNull();
  });
});

describe("logout", () => {
  it("removes the persisted token and makes no backend call", () => {
    window.localStorage.setItem("ketabdaneh.auth.access_token", "jwt-1");
    const fetchMock = vi.spyOn(globalThis, "fetch");

    authApi.logout();

    expect(readAccessToken()).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
