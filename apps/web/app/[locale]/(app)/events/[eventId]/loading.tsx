import { EventsLoading } from "@/components/events/EventsLoading";

// Streaming loading UI for the Event detail route — Next.js shows this
// while the page's server component awaits getEvent().
export default function Loading() {
  return <EventsLoading />;
}
