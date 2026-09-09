import { setRequestLocale } from "next-intl/server";
import {
  getEvent,
  ApiError,
  type EventRead,
} from "@/lib/api";
import { EventDetail, EventDataError } from "@/components/events/EventDetail";
import { EventNotFound } from "@/components/events/EventNotFound";

type Props = { params: Promise<{ locale: string; eventId: string }> };

// Live backend data — render per request, never at build time.
export const dynamic = "force-dynamic";

// Event detail. Minimal and read-only: the existing single-event
// endpoint (GET /api/events/{event_id}) is the data source — no edit,
// no delete, no status controls, no assignment information yet.
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

  return <EventDetail event={event} />;
}
