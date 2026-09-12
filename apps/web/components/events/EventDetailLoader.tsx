"use client";

import {
  getEvent,
  getPersons,
  getEventAssignments,
  type EventAssignmentRead,
  type PersonRead,
} from "@/lib/api";
import { useApiData } from "@/hooks/useApiData";
import { EventDetail, EventDataError } from "./EventDetail";
import { EventNotFound } from "./EventNotFound";
import { EventsLoading } from "./EventsLoading";

// Client-side data loading for the event detail screen. A Client
// Component because the access token lives in browser localStorage,
// which the server page cannot read — the fetch must run in the
// browser, where the AuthGate has already confirmed the session.
//
// Data flow (all three fetches go out in parallel — none depends on
// another's result):
//   - the event itself: GET /api/events/{event_id};
//   - assignments: GET /api/event-assignments, filtered to this
//     event client-side (no dedicated /events/{id}/assignments
//     endpoint exists — docs/06 §4d is the contract);
//   - people for the assignment form's selector: GET /api/persons.
//
// The event is required (its failure replaces the page: 404 →
// not-found state, anything else → data-error state), while an
// assignments or people failure degrades only that section inside
// EventDetail.
//
// The page mounts this component with `key={eventId}`, so navigating
// between two event detail URLs remounts it and refetches — the
// useApiData hook runs once per mount by design.
export function EventDetailLoader({ eventId }: { eventId: string }) {
  const eventState = useApiData(() => getEvent(eventId));
  const assignmentsState = useApiData(getEventAssignments);
  const peopleState = useApiData(getPersons);

  if (eventState.status === "loading") {
    return <EventsLoading />;
  }
  if (eventState.status === "error") {
    return eventState.error.kind === "not-found" ? (
      <EventNotFound />
    ) : (
      <EventDataError />
    );
  }

  const assignments: EventAssignmentRead[] | undefined =
    assignmentsState.status === "success"
      ? assignmentsState.data.filter((a) => a.event_id === eventId)
      : undefined;

  const people: PersonRead[] | undefined =
    peopleState.status === "success" ? peopleState.data : undefined;

  return (
    <EventDetail
      event={eventState.data}
      initialAssignments={assignments}
      people={people}
    />
  );
}
