/**
 * Token storage tests — save / read / remove through lib/auth/storage,
 * including the SSR guard (no window → no crash, no storage access).
 */

import {
  saveAccessToken,
  readAccessToken,
  clearAccessToken,
} from "@/lib/auth/storage";

const KEY = "ketabdaneh.auth.access_token";

beforeEach(() => {
  window.localStorage.clear();
});

describe("saveAccessToken", () => {
  it("persists the token under the app key", () => {
    saveAccessToken("token-abc");
    expect(window.localStorage.getItem(KEY)).toBe("token-abc");
  });

  it("treats an empty token as logout (removes the entry)", () => {
    saveAccessToken("token-abc");
    saveAccessToken("");
    expect(window.localStorage.getItem(KEY)).toBeNull();
  });
});

describe("readAccessToken", () => {
  it("returns the saved token", () => {
    saveAccessToken("token-abc");
    expect(readAccessToken()).toBe("token-abc");
  });

  it("returns null when nothing is saved", () => {
    expect(readAccessToken()).toBeNull();
  });
});

describe("clearAccessToken", () => {
  it("removes the saved token", () => {
    saveAccessToken("token-abc");
    clearAccessToken();
    expect(window.localStorage.getItem(KEY)).toBeNull();
    expect(readAccessToken()).toBeNull();
  });

  it("is a no-op when nothing is saved", () => {
    expect(() => clearAccessToken()).not.toThrow();
  });
});
