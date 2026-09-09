import { EventsLoading } from "@/components/events/EventsLoading";

// Streaming loading UI for the Create Event route — Next.js shows this
// while the page's server component resolves.
export default function Loading() {
  return <EventsLoading />;
}
