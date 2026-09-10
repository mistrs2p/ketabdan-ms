// Dashboard aggregation — pure in-memory derivation from the three
// existing list endpoints (persons, events, event-assignments). There
// is deliberately NO dashboard backend endpoint: one events request +
// one assignments request + one persons request, correlated here
// (never N+1 per-event calls).
//
// Wording is careful and derived only from what the data supports
// (task §22): "upcoming" = planned_at in the future; "unassigned" =
// zero assignments. No "at risk"/"overdue"/"problematic" — those
// concepts are not defined by the backend. No percentages: with small
// samples they mislead. Task/attendance/performance inferences are
// absent by design.
import type {
  EventAssignmentRead,
  EventRead,
  PersonRead,
} from "@/lib/api";

/** A future event with its assignment count, nearest first. */
export interface UpcomingEvent {
  event: EventRead;
  assignmentCount: number;
}

/** Result of correlating events with assignments. */
export interface DashboardEvents {
  /** Future events, nearest first (ties by title for stability). */
  upcoming: UpcomingEvent[];
  /** Events with zero assignments — the operational exception list. */
  unassigned: EventRead[];
  /** Events with at least one assignment. */
  assigned: EventRead[];
  /** Count of assignments referencing existing events. */
  assignmentCount: number;
}

function parseInstant(iso: string): number | null {
  const time = new Date(iso).getTime();
  return Number.isNaN(time) ? null : time;
}

// Correlate the two datasets. Malformed planned_at values are treated
// as non-upcoming (never crash, never guessed); backend ordering of
// the events list is not relied on — this ordering is dashboard-only.
export function buildDashboardEvents(
  events: EventRead[],
  assignments: EventAssignmentRead[],
): DashboardEvents {
  const counts = new Map<string, number>();
  for (const assignment of assignments) {
    counts.set(assignment.event_id, (counts.get(assignment.event_id) ?? 0) + 1);
  }

  const now = Date.now();
  const upcoming: UpcomingEvent[] = [];
  const unassigned: EventRead[] = [];
  const assigned: EventRead[] = [];

  for (const event of events) {
    const count = counts.get(event.id) ?? 0;
    if (count === 0) {
      unassigned.push(event);
    } else {
      assigned.push(event);
    }
    const time = parseInstant(event.planned_at);
    if (time !== null && time >= now) {
      upcoming.push({ event, assignmentCount: count });
    }
  }

  upcoming.sort((a, b) => {
    const at = parseInstant(a.event.planned_at) ?? 0;
    const bt = parseInstant(b.event.planned_at) ?? 0;
    if (at !== bt) return at - bt;
    return a.event.title.localeCompare(b.event.title);
  });

  return {
    upcoming,
    unassigned,
    assigned,
    assignmentCount: assignments.length,
  };
}

// People counts. Role distribution uses the roles already embedded in
// PersonRead (backend reference data) — no extra request.
export interface DashboardPeople {
  total: number;
  active: number;
  inactive: number;
  /** Role code → count of people holding it. */
  roleCounts: { code: string; name: string; count: number }[];
}

export function buildDashboardPeople(people: PersonRead[]): DashboardPeople {
  const active = people.filter((p) => p.active).length;
  const byCode = new Map<string, { name: string; count: number }>();
  for (const person of people) {
    for (const role of person.roles) {
      const entry = byCode.get(role.code) ?? { name: role.name, count: 0 };
      entry.count += 1;
      byCode.set(role.code, entry);
    }
  }
  const roleCounts = [...byCode.entries()]
    .map(([code, { name, count }]) => ({ code, name, count }))
    .sort((a, b) => a.name.localeCompare(b.name));

  return {
    total: people.length,
    active,
    inactive: people.length - active,
    roleCounts,
  };
}

/** Count events per status value, known D-002 set first. */
export function countByStatus(
  events: EventRead[],
): { status: string; count: number }[] {
  const order = ["DRAFT", "SCHEDULED", "IN_PROGRESS", "COMPLETED", "CANCELLED"];
  const counts = new Map<string, number>();
  for (const event of events) {
    counts.set(event.status, (counts.get(event.status) ?? 0) + 1);
  }
  return [
    ...order.filter((status) => counts.has(status)).map((status) => ({
      status,
      count: counts.get(status) as number,
    })),
    // Unknown statuses (none exist today) still surface, ordered by name.
    ...[...counts.entries()]
      .filter(([status]) => !order.includes(status))
      .map(([status, count]) => ({ status, count }))
      .sort((a, b) => a.status.localeCompare(b.status)),
  ];
}
