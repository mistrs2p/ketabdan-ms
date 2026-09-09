/**
 * Roles API — `GET /api/roles` (docs/06 §4).
 *
 * Read-only reference data (six permanent roles, seeded by migration
 * 0002). Roles have no write endpoints by design.
 */

import { apiGet } from "./client";
import type { RoleRead } from "./types";

export function getRoles(): Promise<RoleRead[]> {
  return apiGet<RoleRead[]>("/api/roles");
}
