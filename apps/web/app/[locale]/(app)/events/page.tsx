import { getTranslations, setRequestLocale } from "next-intl/server";
import type { Metadata } from "next";
import { EventsPage } from "@/components/events/EventsPage";

type Props = { params: Promise<{ locale: string }> };

// The shell renders per request; the business data itself is fetched
// client-side (see EventsPage) because the access token lives in
// browser localStorage.
export const dynamic = "force-dynamic";

// Tab title from the existing app.pages.events.title message.
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "app.pages.events" });
  return { title: t("title") };
}

// Events list — replaces the placeholder (Phase 4). The shell,
// navigation, locale, direction, and theme all come from the existing
// app layout; this page only renders the events content.
export default async function Page({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);

  return <EventsPage />;
}
