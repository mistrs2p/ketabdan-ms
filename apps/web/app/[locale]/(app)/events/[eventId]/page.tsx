import { getTranslations, setRequestLocale } from "next-intl/server";
import type { Metadata } from "next";
import { EventDetailLoader } from "@/components/events/EventDetailLoader";

type Props = { params: Promise<{ locale: string; eventId: string }> };

// The shell renders per request; the business data itself is fetched
// client-side (see EventDetailLoader) because the access token lives
// in browser localStorage.
export const dynamic = "force-dynamic";

// Tab title — the section name (the event's own title is only known
// after the client-side fetch; a metadata-time fetch would duplicate
// it for no operational value).
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "app.pages.events" });
  return { title: t("title") };
}

// Event detail. The page is a thin server shell (metadata + locale);
// EventDetailLoader fetches the event, its assignments, and the people
// for the assignment form in the browser, where the auth token lives.
//
// The `key` remounts the loader when the eventId in the URL changes,
// so navigating between two event detail screens refetches.
export default async function Page({ params }: Props) {
  const { locale, eventId } = await params;
  setRequestLocale(locale);

  return <EventDetailLoader key={eventId} eventId={eventId} />;
}
