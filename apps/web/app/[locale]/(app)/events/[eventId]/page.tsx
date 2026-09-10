import { setRequestLocale } from "next-intl/server";
import {
  getEvent,
  getPersons,
  getEventAssignments,
  ApiError,
  type EventRead,
  type PersonRead,
  type EventAssignmentRead,
} from "@/lib/api";
import { EventDetail, EventDataError } from "@/components/events/EventDetail";
import { EventNotFound } from "@/components/events/EventNotFound";

type Props = { params: Promise<{ locale: string; eventId: string }> };

// Live backend data — render per request, never at build time.
export const dynamic = "force-dynamic";

// Event detail. The server fetches everything the screen needs once:
// the event itself (GET /api/events/{event_id}), the assignments
// (GET /api/event-assignments — there is no dedicated
// /events/{id}/assignments endpoint; the list is filtered to this
// event here), and the people for the assignment form's selector
// (GET /api/persons). Each fetch fails independently: the event is
// required (its failure replaces the page), while an assignments or
// people failure degrades only that section.
export default async function Page({ params }: Props) {
  const { locale, eventId } = await params;
  setRequestLocale(locale);

  let event: EventRead;
  try {
    event = await getEvent(eventId);
  } catch (e) {
    const error = e instanceof ApiError ? e : new ApiError("server", String(e));
    if (error.kind === "not-found") {
      return <EventNotFound />;
    }
    // Network or server failure — localized error state.
    return <EventDataError />;
  }

  // The event exists; assignments and people load independently and
  // their failures render in place (EventDetail decides which section
  // degrades). Both calls go out in parallel — neither depends on the
  // other's result.
  const [assignmentsResult, peopleResult] = await Promise.allSettled([
    getEventAssignments(),
    getPersons(),
  ]);

  const assignments: EventAssignmentRead[] | undefined =
    assignmentsResult.status === "fulfilled"
      ? assignmentsResult.value.filter((a) => a.event_id === event.id)
      : undefined;

  const people: PersonRead[] | undefined =
    peopleResult.status === "fulfilled" ? peopleResult.value : undefined;

  return (
    <EventDetail
      event={event}
      initialAssignments={assignments}
      people={people}
    />
  );
}
