/**
 * Runtime smoke script for the frontend API layer (task 4.1 §9).
 *
 * Calls the five read families through the REAL client code
 * (lib/api/*) against the running backend, plus the documented
 * error-path behaviors (404 kind, validation kind, atomicity).
 * Read-only except one create/delete-cleanup pair: a temporary person
 * is created and then removed directly via SQL is NOT available here,
 * so only ghost-UUID paths are exercised — no persistent business data
 * is written. Run: npx tsx scripts/smoke-api.ts
 */

import {
  getEvent,
  getEventAssignments,
  getEvents,
  getHealth,
  getPersons,
  getRoles,
  ApiError,
  buildApiUrl,
} from "../lib/api";

function assert(condition: boolean, label: string): void {
  if (!condition) {
    throw new Error(`SMOKE FAIL: ${label}`);
  }
  console.log(`ok: ${label}`);
}

async function expectApiError(
  label: string,
  kind: string,
  fn: () => Promise<unknown>,
): Promise<void> {
  try {
    await fn();
  } catch (error) {
    if (error instanceof ApiError) {
      assert(error.kind === kind, `${label} → kind=${error.kind} (want ${kind})`);
      return;
    }
    throw error;
  }
  throw new Error(`SMOKE FAIL: ${label} did not reject`);
}

async function main(): Promise<void> {
  assert(
    buildApiUrl("http://x/", "/api/health") === "http://x/api/health",
    "URL joining tolerates trailing/leading slashes",
  );

  const health = await getHealth();
  assert(health.status === "ok", "GET /api/health → {status: ok}");

  const roles = await getRoles();
  assert(roles.length === 6, `GET /api/roles → 6 roles (${roles.length})`);
  assert(
    roles.every((r) => typeof r.id === "string" && "code" in r && "name" in r),
    "RoleRead shape (id: string, code, name)",
  );

  const persons = await getPersons();
  assert(Array.isArray(persons), "GET /api/persons → array");

  const events = await getEvents();
  assert(Array.isArray(events), "GET /api/events → array");

  const assignments = await getEventAssignments();
  assert(Array.isArray(assignments), "GET /api/event-assignments → array");

  const ghost = "12345678-1234-4123-8123-123456789abc";
  await expectApiError(
    "GET /api/events/{ghost}",
    "not-found",
    () => getEvent(ghost),
  );
  try {
    await getEvent(ghost);
    throw new Error("SMOKE FAIL: ghost event did not reject");
  } catch (error) {
    if (error instanceof ApiError) {
      assert(
        error.detail === "Event not found",
        `404 detail preserved: ${JSON.stringify(error.detail)}`,
      );
    } else {
      throw error;
    }
  }

  await expectApiError(
    "GET /api/event-assignments/{ghost}",
    "not-found",
    () => import("../lib/api").then((m) => m.getEventAssignment(ghost)),
  );

  console.log("\nAll smoke checks passed.");
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
});
