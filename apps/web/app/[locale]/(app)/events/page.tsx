import { setRequestLocale } from "next-intl/server";
import { EventsPage } from "@/components/events/EventsPage";

type Props = { params: Promise<{ locale: string }> };

// Live backend data — render per request, never at build time.
export const dynamic = "force-dynamic";

// Events list — replaces the placeholder (Phase 4). The shell,
// navigation, locale, direction, and theme all come from the existing
// app layout; this page only renders the events content.
export default async function Page({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);

  return <EventsPage />;
}
