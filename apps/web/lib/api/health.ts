/**
 * Health API — `GET /api/health` (docs/06 §4).
 *
 * Useful for connectivity checks; no database involved.
 */

import { apiGet } from "./client";
import type { HealthStatus } from "./types";

export function getHealth(): Promise<HealthStatus> {
  return apiGet<HealthStatus>("/api/health");
}
