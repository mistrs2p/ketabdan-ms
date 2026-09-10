import { CalendarLoading } from "@/components/calendar/CalendarLoading";

// Streaming loading UI for the Calendar route — Next.js shows this
// while the page's server component awaits getEvents().
export default function Loading() {
  return <CalendarLoading />;
}
