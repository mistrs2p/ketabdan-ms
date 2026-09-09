import { EventsLoading } from "@/components/events/EventsLoading";

// Streaming loading UI for the Events route — Next.js shows this while
// the page's server component awaits getEvents().
export default function Loading() {
  return <EventsLoading />;
}
