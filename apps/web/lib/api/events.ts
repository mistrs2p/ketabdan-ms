/**
 * Events API — `GET /api/events`, `GET /api/events/{event_id}`,
 * `POST /api/events` (docs/06 §4c).
 *
 * Reads: the calendar-oriented list (ordered by planned_at then id) and
 * the single read (unknown UUID → 404, ApiError kind "not-found").
 * Creation: always DRAFT; naive `planned_at` → 422.
 */

import { apiGet, apiPost } from "./client";
import type { EventCreate, EventRead } from "./types";

export function getEvents(): Promise<EventRead[]> {
  return apiGet<EventRead[]>("/api/events");
}

export function getEvent(eventId: string): Promise<EventRead> {
  return apiGet<EventRead>(`/api/events/${encodeURIComponent(eventId)}`);
}

export function createEvent(payload: EventCreate): Promise<EventRead> {
  return apiPost<EventRead>("/api/events", payload);
}
