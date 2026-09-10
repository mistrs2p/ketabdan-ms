/**
 * Frontend auth layer (Phase 5.3, docs/06 §4f/§4g).
 *
 * Separated concerns — one module per job, mirroring the lib/api
 * pattern:
 *
 * - `types.ts`   — backend contract types (login, /me projection)
 * - `storage.ts` — token persistence (localStorage MVP; see its
 *                  header for the documented XSS trade-off)
 * - `api.ts`     — login / getCurrentUser / logout API calls
 * - `context.tsx`— the React session provider (client component)
 * - `returnTo.ts`— safe `returnTo` path validation (Task 5.4)
 *
 * Authorization is NOT modeled here: the server is the source of truth
 * for permissions (docs/01 §4 rule 3); the frontend only knows the
 * authenticated identity.
 */

export {
  login,
  getCurrentUser,
  logout,
} from "./api";
export { AuthProvider, useAuth } from "./context";
export type { AuthSession, SessionStatus } from "./context";
export { sanitizeReturnTo, splitLocalePath } from "./returnTo";
export {
  saveAccessToken,
  readAccessToken,
  clearAccessToken,
} from "./storage";
export type {
  LoginRequest,
  LoginResponse,
  AuthenticatedUser,
} from "./types";
