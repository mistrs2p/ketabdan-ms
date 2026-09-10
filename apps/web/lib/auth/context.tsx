"use client";

/**
 * Auth session provider — client-side session state on top of the auth
 * API (docs/06 §4f/§4g).
 *
 * Lifecycle:
 *
 * 1. **Initial state: `isLoading: true`, user unknown** while session
 *    restoration runs (exactly once per mount, guarded against races).
 * 2. No persisted token → unauthenticated. Token present → `GET
 *    /api/auth/me` decides: success → authenticated, 401 → token
 *    cleared + unauthenticated (a token alone never renders
 *    authenticated UI — the backend validates the actual session).
 * 3. Afterwards, any token-carrying API call returning 401 flips the
 *    state to unauthenticated through the client's 401 listener — no
 *    retry loops, no repeated `/me` calls beyond the one.
 *
 * Provider order: the app already wraps everything in
 * `NextIntlClientProvider` (locale) at the root; this provider nests
 * inside it because the login UI needs translations. It holds no
 * permissions/roles — authorization stays server-side (§4g); the
 * frontend only knows the `/me` identity.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { onUnauthorized } from "@/lib/api/client";
import * as authApi from "./api";
import { readAccessToken } from "./storage";
import type { AuthenticatedUser } from "./types";

export type SessionStatus = "authenticated" | "unauthenticated" | "loading";

export interface AuthSession {
  /** The `/me` identity — `null` unless authenticated. */
  user: AuthenticatedUser | null;
  /** Convenience: `user !== null`. */
  isAuthenticated: boolean;
  /** True while the initial session restoration is in flight. */
  isLoading: boolean;
  /**
   * Log in; resolves with the user on success. Throws the ApiError
   * otherwise (the login form translates it into a localized message).
   */
  login: (username: string, password: string) => Promise<AuthenticatedUser>;
  /** End the local session (no backend call — see api.ts logout). */
  logout: () => void;
  /** Re-run `/me` to refresh the identity from the server. */
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthSession | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthenticatedUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Session restoration runs exactly once per mount: the flag survives
  // StrictMode double-invocation, so `/me` is never called twice.
  const restorationStarted = useRef(false);

  useEffect(() => {
    if (restorationStarted.current) return;
    restorationStarted.current = true;

    const token = readAccessToken();
    if (!token) {
      setIsLoading(false);
      return;
    }
    authApi
      .getCurrentUser()
      .then((me) => {
        setUser(me);
        setIsLoading(false);
      })
      .catch(() => {
        // 401 (token stale — the client already cleared it) or network
        // failure: either way no authenticated session may be shown.
        // The token is gone only on 401; a network failure keeps it so
        // a refresh can retry once the backend is reachable again.
        setUser(null);
        setIsLoading(false);
      });
  }, []);

  // A token-carrying request came back 401 elsewhere in the app: the
  // server invalidated the session — drop to unauthenticated. (The
  // stale token itself is cleared inside the API client.)
  useEffect(
    () =>
      onUnauthorized(() => {
        setUser(null);
      }),
    [],
  );

  const login = useCallback(
    async (username: string, password: string): Promise<AuthenticatedUser> => {
      await authApi.login(username, password);
      const me = await authApi.getCurrentUser();
      setUser(me);
      return me;
    },
    [],
  );

  const logout = useCallback(() => {
    authApi.logout();
    setUser(null);
  }, []);

  const refreshUser = useCallback(async () => {
    const me = await authApi.getCurrentUser();
    setUser(me);
  }, []);

  const value = useMemo<AuthSession>(
    () => ({
      user,
      isAuthenticated: user !== null,
      isLoading,
      login,
      logout,
      refreshUser,
    }),
    [user, isLoading, login, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthSession {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return context;
}
