/**
 * Persons API — `GET /api/persons`, `POST /api/persons` (docs/06 §4a).
 *
 * Reads: ordered by name then id, roles embedded (sorted by code).
 * Creation: atomic person + memberships; unknown role codes → 422 with
 * the codes named in `detail` (ApiError kind "validation").
 */

import { apiGet, apiPost } from "./client";
import type { PersonCreate, PersonRead } from "./types";

export function getPersons(): Promise<PersonRead[]> {
  return apiGet<PersonRead[]>("/api/persons");
}

export function createPerson(payload: PersonCreate): Promise<PersonRead> {
  return apiPost<PersonRead>("/api/persons", payload);
}
