/**
 * EventAssignments API — `GET /api/event-assignments`,
 * `GET /api/event-assignments/{assignment_id}`,
 * `POST /api/event-assignments` (docs/06 §4d).
 *
 * Reads: ordered by id; responsibility embedded, event/person by id.
 * Creation: always PENDING (provisional, TBD-D10/A6 — carried, never
 * transitioned by the frontend); unknown event/person → 404, unknown
 * responsibility code → 422. No update/delete/approval endpoints
 * exist (docs/06 §4e: defined, unimplemented).
 */

import { apiGet, apiPost } from "./client";
import type { EventAssignmentCreate, EventAssignmentRead } from "./types";

export function getEventAssignments(): Promise<EventAssignmentRead[]> {
  return apiGet<EventAssignmentRead[]>("/api/event-assignments");
}

export function getEventAssignment(
  assignmentId: string,
): Promise<EventAssignmentRead> {
  return apiGet<EventAssignmentRead>(
    `/api/event-assignments/${encodeURIComponent(assignmentId)}`,
  );
}

export function createEventAssignment(
  payload: EventAssignmentCreate,
): Promise<EventAssignmentRead> {
  return apiPost<EventAssignmentRead>("/api/event-assignments", payload);
}
