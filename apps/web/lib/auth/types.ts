/**
 * Frontend auth contract types (docs/06 §4f/§4g).
 *
 * These mirror the CURRENT backend auth schemas exactly — field names are
 * the backend's, unchanged. The authenticated user is only the `/me`
 * projection (`id`, `username`, `active`): the hash never appears in any
 * response, and authorization details (roles/permissions) are not part
 * of the identity contract — the server stays the source of truth
 * (docs/01 §4 rule 3), so nothing here models permissions.
 */

/** LoginRequest — request body for `POST /api/auth/login`. */
export interface LoginRequest {
  username: string;
  password: string;
}

/** LoginResponse — `POST /api/auth/login` success body. */
export interface LoginResponse {
  access_token: string;
  token_type: string;
  /** Seconds until the token expires. */
  expires_in: number;
}

/** AuthenticatedUser — the `GET /api/auth/me` projection. */
export interface AuthenticatedUser {
  id: string;
  username: string;
  active: boolean;
}
